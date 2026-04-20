"""Shipping labels: list eBay buyer orders + render an A4 sheet of labels (Avery L7173)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.database import get_db
from core.deps import get_current_user
from core.security import decrypt_ebay_token
from models.user import User
from services.ebay_orders_service import list_unshipped_orders
from services.ebay_publish_service import ensure_ebay_access_token
from services.shipping_label_service import LabelAddress, render_labels_pdf

router = APIRouter(prefix="/shipping", tags=["shipping"])


class ShippingLabelInput(BaseModel):
    """One recipient block. Edits made before printing never touch the eBay order."""

    full_name: str = Field(..., min_length=1, max_length=120)
    line1: str = Field(..., min_length=1, max_length=180)
    line2: str | None = Field(default=None, max_length=180)
    postal_code: str = Field(..., min_length=1, max_length=20)
    city: str = Field(..., min_length=1, max_length=80)
    state: str | None = Field(default=None, max_length=80)
    country_code: str | None = Field(default="FR", max_length=3)


class ShippingLabelsBody(BaseModel):
    addresses: list[ShippingLabelInput] = Field(..., min_length=1, max_length=200)


@router.get("/ebay-orders")
async def shipping_ebay_orders(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """List eBay buyer orders that still need shipping (NOT_STARTED / IN_PROGRESS, last 90 days)."""
    if not decrypt_ebay_token(user.ebay_refresh_token):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Connect eBay first (OAuth).",
        )
    try:
        token = await ensure_ebay_access_token(db, user)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        orders = await list_unshipped_orders(token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"eBay Fulfillment API error: {exc}",
        ) from exc
    return {"orders": orders, "count": len(orders)}


@router.post("/labels.pdf")
async def shipping_labels_pdf(
    body: ShippingLabelsBody,
    user: Annotated[User, Depends(get_current_user)],  # noqa: ARG001 (auth gate)
) -> Response:
    """
    Render the supplied recipient blocks as an A4 PDF (Avery L7173 — 99×57 mm, 8 per page).

    Same endpoint serves both the in-app preview (iframe) and the final download — guarantees
    the on-screen rendering matches the printed output byte-for-byte.
    """
    addresses = [
        LabelAddress(
            full_name=row.full_name.strip(),
            line1=row.line1.strip(),
            line2=row.line2.strip() if row.line2 else None,
            postal_code=row.postal_code.strip(),
            city=row.city.strip(),
            state=row.state.strip() if row.state else None,
            country_code=(row.country_code or "FR").strip().upper() or "FR",
        )
        for row in body.addresses
    ]
    pdf = render_labels_pdf(addresses)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'inline; filename="goupixdex-etiquettes.pdf"',
            "Cache-Control": "no-store",
        },
    )
