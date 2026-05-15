"""
TCGdex-backed catalog routes (series / sets / cards) for stock pickers.

Series group extensions (``GET …/series``). Image URL rules follow
https://tcgdex.dev/assets (quality + extension for cards;
``logo.{ext}`` / ``symbol.{ext}`` for sets).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from core.database import get_db
from core.deps import get_current_user
from models.margin_settings import MarginSettings
from models.user import User
from services.catalog_prefill_service import build_catalog_card_preview
from services.tcgdex_asset_url import (
    enrich_series_brief_row,
    enrich_series_detail,
    enrich_set_brief_row,
    enrich_set_detail,
)
from services.tcgdex_client_service import SUPPORTED_LOCALES, TcgdexClientService

router = APIRouter(prefix="/catalog", tags=["catalog"])


def _merge_en_series_logos(rows: list[dict[str, Any]], en_rows: list[dict[str, Any]]) -> None:
    """Fill missing ``logo`` on series rows using EN list (same ``id``)."""
    logo_by_id: dict[str, str] = {}
    for er in en_rows:
        if not isinstance(er, dict):
            continue
        eid = er.get("id")
        if not isinstance(eid, str):
            continue
        el = er.get("logo")
        if isinstance(el, str) and el.strip():
            logo_by_id[eid] = el.strip()
    for row in rows:
        rid = row.get("id")
        if isinstance(rid, str) and not row.get("logo") and rid in logo_by_id:
            row["logo"] = logo_by_id[rid]


def _merge_en_set_briefs(rows: list[dict[str, Any]], en_rows: list[dict[str, Any]]) -> None:
    """Fill missing ``logo`` / ``symbol`` on set briefs using EN rows (same ``id``)."""
    logo_by_id: dict[str, str] = {}
    sym_by_id: dict[str, str] = {}
    for er in en_rows:
        if not isinstance(er, dict):
            continue
        eid = er.get("id")
        if not isinstance(eid, str):
            continue
        el = er.get("logo")
        if isinstance(el, str) and el.strip():
            logo_by_id[eid] = el.strip()
        sm = er.get("symbol")
        if isinstance(sm, str) and sm.strip():
            sym_by_id[eid] = sm.strip()
    for row in rows:
        if not isinstance(row, dict):
            continue
        rid = row.get("id")
        if not isinstance(rid, str):
            continue
        if not row.get("logo") and rid in logo_by_id:
            row["logo"] = logo_by_id[rid]
        if not row.get("symbol") and rid in sym_by_id:
            row["symbol"] = sym_by_id[rid]


def _round_eur(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 2)


def _margin_percent(db: Session, user_id: int) -> int:
    row = db.query(MarginSettings).filter(MarginSettings.user_id == user_id).first()
    if row is not None:
        return row.margin_percent
    return 20


@router.get("/sets")
def list_catalog_sets(
    user: Annotated[User, Depends(get_current_user)],
    locale: str = Query("en", min_length=2, max_length=8),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    name: str | None = Query(None, max_length=120),
) -> dict[str, Any]:
    """Paginated TCGdex set list with optional ``name`` filter."""
    loc = locale.strip().lower()
    if loc not in SUPPORTED_LOCALES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported locale {locale!r}; use one of: {', '.join(sorted(SUPPORTED_LOCALES))}",
        )
    client = TcgdexClientService()
    name_filter = name.strip() if name else None
    try:
        rows = client.list_sets(loc, page=page, per_page=per_page, name_contains=name_filter)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    logo_by_id: dict[str, str] = {}
    sym_by_id: dict[str, str] = {}
    if loc != "en":
        try:
            en_rows = client.list_sets("en", page=page, per_page=per_page, name_contains=name_filter)
            for er in en_rows:
                if not isinstance(er, dict):
                    continue
                eid = er.get("id")
                if not isinstance(eid, str):
                    continue
                el = er.get("logo")
                if isinstance(el, str) and el.strip():
                    logo_by_id[eid] = el.strip()
                sm = er.get("symbol")
                if isinstance(sm, str) and sm.strip():
                    sym_by_id[eid] = sm.strip()
        except RuntimeError:
            pass

    enriched: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        rid = row.get("id")
        if isinstance(rid, str):
            if not row.get("logo") and rid in logo_by_id:
                row["logo"] = logo_by_id[rid]
            if not row.get("symbol") and rid in sym_by_id:
                row["symbol"] = sym_by_id[rid]
        enrich_set_brief_row(row)
        enriched.append(row)

    return {"locale": loc, "page": page, "per_page": per_page, "sets": enriched}


@router.get("/series")
def list_catalog_series(
    user: Annotated[User, Depends(get_current_user)],
    locale: str = Query("en", min_length=2, max_length=8),
    name: str | None = Query(None, max_length=120),
) -> dict[str, Any]:
    """TCGdex series list for grouping extensions; optional ``name`` substring filter (id or name)."""
    loc = locale.strip().lower()
    if loc not in SUPPORTED_LOCALES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported locale {locale!r}; use one of: {', '.join(sorted(SUPPORTED_LOCALES))}",
        )
    client = TcgdexClientService()
    try:
        rows = client.list_series(loc)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    name_filter = name.strip().lower() if name else ""
    if name_filter:
        filtered: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            nid = (row.get("id") or "").lower()
            nname = (row.get("name") or "").lower()
            if name_filter in nid or name_filter in nname:
                filtered.append(row)
        rows = filtered

    if loc != "en":
        try:
            en_rows = client.list_series("en")
            _merge_en_series_logos(rows, en_rows)
        except RuntimeError:
            pass

    enriched: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, dict):
            enrich_series_brief_row(row)
            enriched.append(row)

    return {"locale": loc, "series": enriched}


@router.get("/series/{series_id}")
def get_catalog_series(
    user: Annotated[User, Depends(get_current_user)],
    series_id: str,
    locale: str = Query("en", min_length=2, max_length=8),
) -> dict[str, Any]:
    """One TCG series with nested set rows (logos merged from EN when needed)."""
    loc = locale.strip().lower()
    if loc not in SUPPORTED_LOCALES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported locale {locale!r}; use one of: {', '.join(sorted(SUPPORTED_LOCALES))}",
        )
    client = TcgdexClientService()
    sid = series_id.strip()
    try:
        detail = client.get_series(loc, sid)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if not isinstance(detail, dict):
        raise HTTPException(status_code=502, detail="Invalid TCGdex series payload")

    if loc != "en":
        try:
            en_detail = client.get_series("en", sid)
            if isinstance(en_detail, dict):
                if not detail.get("logo"):
                    el = en_detail.get("logo")
                    if isinstance(el, str) and el.strip():
                        detail["logo"] = el.strip()
                en_sets = en_detail.get("sets")
                sets = detail.get("sets")
                if isinstance(en_sets, list) and isinstance(sets, list):
                    en_list = [s for s in en_sets if isinstance(s, dict)]
                    loc_list = [s for s in sets if isinstance(s, dict)]
                    _merge_en_set_briefs(loc_list, en_list)
        except RuntimeError:
            pass

    enrich_series_detail(detail)
    return {"locale": loc, "series": detail}


@router.get("/sets/{set_id}")
def get_catalog_set(
    user: Annotated[User, Depends(get_current_user)],
    set_id: str,
    locale: str = Query("en", min_length=2, max_length=8),
) -> dict[str, Any]:
    """Full TCGdex set payload including card stubs for grid UIs."""
    loc = locale.strip().lower()
    if loc not in SUPPORTED_LOCALES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported locale {locale!r}; use one of: {', '.join(sorted(SUPPORTED_LOCALES))}",
        )
    client = TcgdexClientService()
    try:
        detail = client.get_set(loc, set_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if not isinstance(detail, dict):
        raise HTTPException(status_code=502, detail="Invalid TCGdex set payload")

    if loc != "en":
        try:
            en_detail = client.get_set("en", set_id)
            if isinstance(en_detail, dict):
                if not detail.get("logo"):
                    el = en_detail.get("logo")
                    if isinstance(el, str) and el.strip():
                        detail["logo"] = el.strip()
                if not detail.get("symbol"):
                    es = en_detail.get("symbol")
                    if isinstance(es, str) and es.strip():
                        detail["symbol"] = es.strip()
        except RuntimeError:
            pass

    enrich_set_detail(detail)
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

    ``browse_locale`` aligns ``display_pokemon_name`` with the catalogue language.
    ``suggested_price`` uses the same margin percent as ``GET /pricing/lookup``.
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

    suggested: float | None = None
    if avg is not None:
        suggested = _round_eur(float(avg) * (1.0 + margin / 100.0))
    lp = body["listing_preview"]
    if isinstance(lp, dict):
        lp["suggested_price"] = suggested

    body["margin_percent_used"] = margin
    return body
