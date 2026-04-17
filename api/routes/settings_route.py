"""Per-user margin settings (table ``settings``) and marketplace toggles."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from config import get_settings
from core.database import get_db
from core.deps import get_current_user
from core.security import decrypt_ebay_token
from models.user import User
from schemas.settings import SettingsResponse, SettingsUpdate
from services.ebay_oauth_service import ebay_oauth_configured
from services.user_settings_service import ebay_listing_config_complete, get_or_create_user_settings

router = APIRouter(prefix="/settings", tags=["settings"])


def _to_response(db: Session, user: User) -> SettingsResponse:
    s = get_or_create_user_settings(db, user.id)
    app = get_settings()
    return SettingsResponse(
        margin_percent=s.margin_percent,
        vinted_enabled=bool(s.vinted_enabled),
        ebay_enabled=bool(s.ebay_enabled),
        ebay_marketplace_id=s.ebay_marketplace_id,
        ebay_category_id=s.ebay_category_id,
        ebay_merchant_location_key=s.ebay_merchant_location_key,
        ebay_fulfillment_policy_id=s.ebay_fulfillment_policy_id,
        ebay_payment_policy_id=s.ebay_payment_policy_id,
        ebay_return_policy_id=s.ebay_return_policy_id,
        ebay_connected=bool(decrypt_ebay_token(user.ebay_refresh_token)),
        ebay_listing_config_complete=ebay_listing_config_complete(s),
        ebay_oauth_configured=ebay_oauth_configured(app),
        ebay_environment="sandbox" if app.ebay_use_sandbox else "production",
    )


@router.get("", response_model=SettingsResponse)
def get_margin_settings(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> SettingsResponse:
    return _to_response(db, user)


@router.put("", response_model=SettingsResponse)
def put_margin_settings(
    body: SettingsUpdate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> SettingsResponse:
    data = body.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update.",
        )
    s = get_or_create_user_settings(db, user.id)
    if "margin_percent" in data and data["margin_percent"] is not None:
        s.margin_percent = data["margin_percent"]
    if "vinted_enabled" in data and data["vinted_enabled"] is not None:
        s.vinted_enabled = bool(data["vinted_enabled"])
    if "ebay_enabled" in data and data["ebay_enabled"] is not None:
        s.ebay_enabled = bool(data["ebay_enabled"])
    if "ebay_marketplace_id" in data and data["ebay_marketplace_id"] is not None:
        s.ebay_marketplace_id = data["ebay_marketplace_id"].strip() or "EBAY_FR"
    for key in (
        "ebay_category_id",
        "ebay_merchant_location_key",
        "ebay_fulfillment_policy_id",
        "ebay_payment_policy_id",
        "ebay_return_policy_id",
    ):
        if key in data:
            val = data[key]
            if val is None or (isinstance(val, str) and not val.strip()):
                setattr(s, key, None)
            else:
                setattr(s, key, str(val).strip())
    db.commit()
    db.refresh(s)
    return _to_response(db, user)
