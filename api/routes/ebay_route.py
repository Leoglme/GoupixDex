"""eBay OAuth, seller setup metadata, connection status."""

from __future__ import annotations

import datetime as dt
from typing import Annotated, Any
from urllib.parse import unquote

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from config import get_settings
from core.database import get_db
from core.deps import get_current_user
from core.security import decrypt_ebay_token, store_ebay_token
from models.user import User
from services.ebay_oauth_service import (
    build_authorization_url,
    ebay_oauth_configured,
    exchange_authorization_code,
)
from services.ebay_publish_service import ensure_ebay_access_token
from services.ebay_seller_metadata_service import (
    fetch_fulfillment_policies,
    fetch_inventory_locations,
    fetch_payment_policies,
    fetch_return_policies,
)
from services.user_settings_service import ebay_listing_config_complete, get_or_create_user_settings

router = APIRouter(prefix="/ebay", tags=["ebay"])


class EbayCodeBody(BaseModel):
    code: str = Field(min_length=4, max_length=4096)


def _settings_public_row(db: Session, user: User) -> dict[str, Any]:
    ms = get_or_create_user_settings(db, user.id)
    connected = bool(decrypt_ebay_token(user.ebay_refresh_token))
    app = get_settings()
    return {
        "margin_percent": ms.margin_percent,
        "vinted_enabled": bool(ms.vinted_enabled),
        "ebay_enabled": bool(ms.ebay_enabled),
        "ebay_marketplace_id": ms.ebay_marketplace_id,
        "ebay_category_id": ms.ebay_category_id,
        "ebay_merchant_location_key": ms.ebay_merchant_location_key,
        "ebay_fulfillment_policy_id": ms.ebay_fulfillment_policy_id,
        "ebay_payment_policy_id": ms.ebay_payment_policy_id,
        "ebay_return_policy_id": ms.ebay_return_policy_id,
        "ebay_connected": connected,
        "ebay_listing_config_complete": ebay_listing_config_complete(ms),
        "ebay_oauth_configured": ebay_oauth_configured(app),
        "ebay_environment": "sandbox" if app.ebay_use_sandbox else "production",
    }


@router.get("/oauth/authorize-url")
def ebay_authorize_url(
    state: Annotated[str, Query(min_length=4, max_length=256)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, str]:
    """Build the browser URL for eBay consent (User must open it)."""
    try:
        url = build_authorization_url(state=state)
    except RuntimeError as exc:
        if str(exc) == "ebay_oauth_not_configured":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="eBay OAuth is not configured on the server (EBAY_CLIENT_ID, EBAY_CLIENT_SECRET, EBAY_REDIRECT_URI).",
            ) from exc
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"authorization_url": url, "state": state}


@router.post("/oauth/exchange", status_code=status.HTTP_200_OK)
async def ebay_oauth_exchange(
    body: EbayCodeBody,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Exchange authorization ``code`` from redirect URL; stores tokens on the user row."""
    if not ebay_oauth_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="eBay OAuth is not configured on the server.",
        )
    code = unquote(body.code.strip())
    try:
        data = await exchange_authorization_code(code)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"eBay token exchange failed: {exc}",
        ) from exc

    refresh = data.get("refresh_token")
    access = data.get("access_token")
    if not refresh and not access:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="eBay response missing tokens.",
        )
    now = dt.datetime.now(dt.UTC)
    if refresh:
        user.ebay_refresh_token = store_ebay_token(str(refresh))
    if access:
        user.ebay_access_token = store_ebay_token(str(access))
        expires_in = int(data.get("expires_in", 7200))
        user.ebay_access_expires_at = now + dt.timedelta(seconds=expires_in)
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"ok": True, "ebay_connected": bool(decrypt_ebay_token(user.ebay_refresh_token))}


@router.post("/oauth/disconnect", status_code=status.HTTP_200_OK)
def ebay_oauth_disconnect(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, bool]:
    user.ebay_refresh_token = None
    user.ebay_access_token = None
    user.ebay_access_expires_at = None
    db.add(user)
    db.commit()
    return {"ok": True}


@router.get("/status")
def ebay_status(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Connection + listing readiness (no secrets)."""
    return _settings_public_row(db, user)


@router.get("/seller-setup")
async def ebay_seller_setup(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Locations + business policies for the authenticated seller (requires eBay connection)."""
    ms = get_or_create_user_settings(db, user.id)
    if not decrypt_ebay_token(user.ebay_refresh_token):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Connect eBay first (OAuth).",
        )
    try:
        token = await ensure_ebay_access_token(db, user)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    mp = (ms.ebay_marketplace_id or "EBAY_FR").strip()
    try:
        locations = await fetch_inventory_locations(token)
        fulfillment = await fetch_fulfillment_policies(token, mp)
        payment = await fetch_payment_policies(token, mp)
        returns = await fetch_return_policies(token, mp)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"eBay Account API error: {exc}",
        ) from exc
    return {
        "marketplace_id": mp,
        "locations": locations,
        "fulfillment_policies": fulfillment,
        "payment_policies": payment,
        "return_policies": returns,
    }
