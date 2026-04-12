"""Scan card without persisting (OCR + pricing preview)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from core.database import get_db
from core.deps import get_current_user_optional
from models.margin_settings import MarginSettings
from models.user import User
from services import ocr_service, pricing_service
from services.scan_service import build_title_and_description

router = APIRouter(tags=["scan"])


def _round_eur(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 2)


def _margin_for_user(db: Session, user: User | None, form_margin: int) -> int:
    if user is None:
        return form_margin
    row = db.query(MarginSettings).filter(MarginSettings.user_id == user.id).first()
    if row is not None:
        return row.margin_percent
    return form_margin


@router.post("/scan-card")
async def scan_card(
    db: Annotated[Session, Depends(get_db)],
    file: UploadFile = File(...),
    margin_percent: int = Form(20),
    user: Annotated[User | None, Depends(get_current_user_optional)] = None,
) -> dict[str, Any]:
    """Run OCR + PokéWallet pricing; return suggested listing fields (no DB write)."""
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")

    ocr = ocr_service.extract_card_from_bytes(data, file.filename or "card.jpg")
    set_code = ocr.get("set_code")
    card_number = ocr.get("card_number")
    pokemon = ocr.get("pokemon_name_english") or ocr.get("pokemon_name")

    pricing = pricing_service.fetch_card_prices(set_code, card_number, pokemon)
    card = pricing.get("card")
    card_info: dict[str, Any] = {}
    if isinstance(card, dict):
        raw_info = card.get("card_info")
        if isinstance(raw_info, dict):
            card_info = raw_info

    margin = _margin_for_user(db, user, margin_percent)
    avg = _round_eur(pricing.get("average_price"))
    suggested: float | None = None
    if avg is not None:
        suggested = _round_eur(float(avg) * (1.0 + margin / 100.0))

    title, description = build_title_and_description(ocr, card_info)

    return {
        "ocr": dict(ocr),
        "pricing": {
            "cardmarket_eur": _round_eur(pricing.get("cardmarket_eur")),
            "tcgplayer_usd": _round_eur(pricing.get("tcgplayer_usd")),
            "average_price": avg,
            "margin_percent_used": margin,
            "suggested_price": suggested,
            "error": pricing.get("error"),
        },
        "listing_preview": {
            "title": title,
            "description": description,
            "suggested_price": suggested,
        },
    }
