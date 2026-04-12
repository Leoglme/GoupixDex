"""PokéWallet pricing lookup (auth) with user margin for suggested price."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.database import get_db
from core.deps import get_current_user
from models.margin_settings import MarginSettings
from models.user import User
from services import pricing_service

router = APIRouter(prefix="/pricing", tags=["pricing"])


def _round_eur(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 2)


def _margin_percent(db: Session, user_id: int) -> int:
    row = db.query(MarginSettings).filter(MarginSettings.user_id == user_id).first()
    if row is not None:
        return row.margin_percent
    return 20


@router.get("/lookup")
def lookup_prices(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    set_code: str = Query(..., min_length=1),
    card_number: str = Query(..., min_length=1),
    pokemon_name: str | None = Query(None),
) -> dict[str, Any]:
    """Resolve Cardmarket / TCGPlayer refs via PokéWallet; suggested price uses saved margin %."""
    margin = _margin_percent(db, user.id)
    pricing = pricing_service.fetch_card_prices(
        set_code.strip(),
        card_number.strip(),
        pokemon_name.strip() if pokemon_name else None,
    )
    avg = _round_eur(pricing.get("average_price"))
    suggested: float | None = None
    if avg is not None:
        suggested = _round_eur(float(avg) * (1.0 + margin / 100.0))

    card = pricing.get("card")
    set_name: str | None = None
    if isinstance(card, dict):
        info = card.get("card_info")
        if isinstance(info, dict):
            raw = info.get("set_name")
            set_name = str(raw).strip() if raw else None

    return {
        "cardmarket_eur": _round_eur(pricing.get("cardmarket_eur")),
        "tcgplayer_usd": _round_eur(pricing.get("tcgplayer_usd")),
        "average_price_eur": avg,
        "suggested_price_eur": suggested,
        "margin_percent_used": margin,
        "set_name": set_name,
        "error": pricing.get("error"),
    }
