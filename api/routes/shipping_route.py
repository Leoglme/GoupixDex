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
from services.ebay_oauth_service import EbayOAuthError
from services.ebay_orders_service import list_unshipped_orders
from services.ebay_publish_service import ensure_ebay_access_token
from services.shipping_label_service import LabelAddress, render_labels_pdf
from services.stamp_overlay_service import decode_stamp_pdf_base64, overlay_stamps_on_labels_pdf
from services.user_settings_service import get_or_create_user_settings, sender_address_complete

router = APIRouter(prefix="/shipping", tags=["shipping"])


_STAMP_B64_MAX_LEN = 6_000_000


class ShippingLabelInput(BaseModel):
    """One recipient block. Edits made before printing never touch the eBay order."""

    full_name: str = Field(..., min_length=1, max_length=120)
    line1: str = Field(..., min_length=1, max_length=180)
    line2: str | None = Field(default=None, max_length=180)
    postal_code: str = Field(..., min_length=1, max_length=20)
    city: str = Field(..., min_length=1, max_length=80)
    state: str | None = Field(default=None, max_length=80)
    country_code: str | None = Field(default="FR", max_length=3)
    stamp_pdf_base64: str | None = Field(
        default=None,
        max_length=_STAMP_B64_MAX_LEN,
        description="Optional La Poste stamp PDF (single-page), base64 or data URL.",
    )


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
        token = await ensure_ebay_access_token(db, user, require_fulfillment_scope=True)
    except RuntimeError as exc:
        msg = str(exc)
        if msg.startswith("ebay_fulfillment_scope_missing"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "ebay_fulfillment_denied",
                    "message": msg.split(": ", 1)[-1],
                },
            ) from exc
        raise HTTPException(status_code=400, detail=msg) from exc

    ms = get_or_create_user_settings(db, user.id)
    mp = (ms.ebay_marketplace_id or "EBAY_FR").strip() or "EBAY_FR"

    try:
        orders = await list_unshipped_orders(token, marketplace_id=mp)
    except EbayOAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"eBay Fulfillment API error: {exc}",
        ) from exc
    return {"orders": orders, "count": len(orders)}


@router.post("/labels.pdf")
async def shipping_labels_pdf(
    body: ShippingLabelsBody,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],  # noqa: ARG001 (auth gate)
) -> Response:
    """
    Render the supplied recipient blocks as an A4 PDF (Avery L7173 — 99×57 mm, 8 per page).

    Each parcel uses **two** L7173 vignettes stacked vertically on the sheet (sender immediately below recipient).
    The sender vignette uses a crop rectangle nearly full sticker width; address stays on **one line** under the name when
    possible (font scales down, then ellipsis). Padding inside the crop marks is the same on top, bottom, left, and right.

    Optional ``stamp_pdf_base64`` per row (PDF from laposte.fr): artwork on page 1 is overlaid at **native scale**
    (no shrinking). Placement: **below** that parcel's sender vignette when the PDF grid leaves white space there (same
    column); otherwise **flush-right** on the page, centred vertically on that parcel's recipient+sender pair; if neither
    fits, an extra A4 page is appended for that stamp.
    """
    ms = get_or_create_user_settings(db, user.id)
    if not sender_address_complete(ms):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "sender_address_incomplete",
                "message": (
                    "Configurez votre adresse expéditeur dans Paramètres → Configuration "
                    "avant de générer les étiquettes."
                ),
            },
        )

    stamps_by_parcel: list[bytes | None] = []
    addresses: list[LabelAddress] = []
    for idx, row in enumerate(body.addresses):
        try:
            stamp_bytes = decode_stamp_pdf_base64(row.stamp_pdf_base64)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "invalid_stamp_pdf",
                    "parcel_index": idx,
                    "message": str(exc),
                },
            ) from exc
        stamps_by_parcel.append(stamp_bytes)
        addresses.append(
            LabelAddress(
                full_name=row.full_name.strip(),
                line1=row.line1.strip(),
                line2=row.line2.strip() if row.line2 else None,
                postal_code=row.postal_code.strip(),
                city=row.city.strip(),
                state=row.state.strip() if row.state else None,
                country_code=(row.country_code or "FR").strip().upper() or "FR",
            )
        )
    sender = LabelAddress(
        full_name=(ms.sender_full_name or "").strip(),
        line1=(ms.sender_line1 or "").strip(),
        line2=(ms.sender_line2 or "").strip() or None,
        postal_code=(ms.sender_postal_code or "").strip(),
        city=(ms.sender_city or "").strip(),
        state=None,
        country_code="FR",
    )
    pdf = render_labels_pdf(addresses, sender=sender)
    pdf = overlay_stamps_on_labels_pdf(pdf, stamps_by_parcel)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'inline; filename="goupixdex-etiquettes.pdf"',
            "Cache-Control": "no-store",
        },
    )
