"""
TCGdex-backed catalog routes (series / sets / cards) for the picker UI.

Browse logic + JA-to-Latin display fallback live in
:mod:`services.catalog_browse_service` to keep this module a thin controller.
Image URL rules follow https://tcgdex.dev/assets.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from core.database import get_db
from core.deps import get_current_user
from models.margin_settings import MarginSettings
from models.user import User
from services.catalog_browse_service import (
    get_series_for_ui,
    get_set_for_ui,
    list_series_for_ui,
    list_sets_for_ui,
)
from services.catalog_prefill_service import build_catalog_card_preview
from services.tcgdex_client_service import SUPPORTED_LOCALES

router = APIRouter(prefix="/catalog", tags=["catalog"])


def _ensure_locale(locale: str) -> str:
    loc = locale.strip().lower()
    if loc not in SUPPORTED_LOCALES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported locale {locale!r}; use one of: {', '.join(sorted(SUPPORTED_LOCALES))}",
        )
    return loc


def _round_eur(value: float | None) -> float | None:
    return round(float(value), 2) if value is not None else None


def _margin_percent(db: Session, user_id: int) -> int:
    row = db.query(MarginSettings).filter(MarginSettings.user_id == user_id).first()
    return row.margin_percent if row is not None else 20


@router.get("/sets")
def list_catalog_sets(
    user: Annotated[User, Depends(get_current_user)],
    locale: str = Query("en", min_length=2, max_length=8),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    name: str | None = Query(None, max_length=120),
) -> dict[str, Any]:
    """Paginated TCGdex set list with optional ``name`` filter."""
    loc = _ensure_locale(locale)
    try:
        rows = list_sets_for_ui(loc, page=page, per_page=per_page, name_filter=name or None)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"locale": loc, "page": page, "per_page": per_page, "sets": rows}


@router.get("/series")
def list_catalog_series(
    user: Annotated[User, Depends(get_current_user)],
    locale: str = Query("en", min_length=2, max_length=8),
    name: str | None = Query(None, max_length=120),
) -> dict[str, Any]:
    """TCGdex series list for grouping extensions."""
    loc = _ensure_locale(locale)
    try:
        rows = list_series_for_ui(loc, name_filter=name or None)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"locale": loc, "series": rows}


@router.get("/series/{series_id}")
def get_catalog_series(
    user: Annotated[User, Depends(get_current_user)],
    series_id: str,
    locale: str = Query("en", min_length=2, max_length=8),
) -> dict[str, Any]:
    loc = _ensure_locale(locale)
    try:
        detail = get_series_for_ui(loc, series_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"locale": loc, "series": detail}


@router.get("/sets/{set_id}")
def get_catalog_set(
    user: Annotated[User, Depends(get_current_user)],
    set_id: str,
    locale: str = Query("en", min_length=2, max_length=8),
) -> dict[str, Any]:
    loc = _ensure_locale(locale)
    try:
        detail = get_set_for_ui(loc, set_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"locale": loc, "set": detail}


@router.get("/card-preview")
def get_catalog_card_preview(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    tcgdx_card_id: str = Query(..., min_length=3, max_length=120),
    pokewallet_set_code: str | None = Query(None, max_length=32),
    browse_locale: str | None = Query(
        None,
        min_length=2,
        max_length=8,
        description="Catalog UI locale for the suggested Pokémon name (en, fr, ja).",
    ),
) -> dict[str, Any]:
    """
    Resolve EN/FR/JA labels from TCGdex, map to PokéWallet codes, and attach pricing preview.

    Kept around for backwards compatibility with the legacy ``catalog`` page; the
    new ``Ma Collection`` flow uses ``POST /collection`` + ``prepare-article-prefill``.
    """
    bl = browse_locale.strip().lower() if browse_locale else None
    if bl and bl not in SUPPORTED_LOCALES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported browse_locale {browse_locale!r}; use one of: {', '.join(sorted(SUPPORTED_LOCALES))}",
        )
    try:
        body = build_catalog_card_preview(
            tcgdx_card_id=tcgdx_card_id.strip(),
            pokewallet_set_code=pokewallet_set_code.strip() if pokewallet_set_code else None,
            browse_locale=bl,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if body.get("error"):
        raise HTTPException(status_code=422, detail=body["error"])

    margin = _margin_percent(db, user.id)
    pricing_block = body.get("pricing")
    raw_avg = pricing_block.get("average_price_eur") if isinstance(pricing_block, dict) else None
    avg = _round_eur(raw_avg if isinstance(raw_avg, (int, float)) else None)

    suggested = None
    if avg is not None:
        suggested = _round_eur(float(avg) * (1.0 + margin / 100.0))
    lp = body["listing_preview"]
    if isinstance(lp, dict):
        lp["suggested_price"] = suggested

    body["margin_percent_used"] = margin
    return body
