"""
Set logo/symbol resolution beyond raw TCGdex API fields.

Limitless TCG hosts many JP (and some EN promo) set logos on S3 — see
``https://s3.limitlesstcg.com/sets/jp/{code}.png`` and ``…/sets/en/{CODE}.png``.
"""

from __future__ import annotations

import threading
from typing import Any

import httpx

from services.tcgdex_asset_url import (
    fill_missing_set_visuals,
    normalize_set_logo_url,
    tcgdx_asset_url_with_webp,
)

_USER_AGENT = "GoupixDex/1.0 (+catalog-logos)"
_HEAD_CACHE: dict[str, bool] = {}
_HEAD_LOCK = threading.Lock()


def _head_ok(url: str) -> bool:
    with _HEAD_LOCK:
        cached = _HEAD_CACHE.get(url)
        if cached is not None:
            return cached
    try:
        resp = httpx.head(
            url,
            headers={"User-Agent": _USER_AGENT},
            timeout=20.0,
            follow_redirects=True,
        )
        ok = resp.is_success
    except httpx.HTTPError:
        ok = False
    with _HEAD_LOCK:
        _HEAD_CACHE[url] = ok
    return ok


def limitless_set_logo_url(locale: str, set_id: str) -> str | None:
    """Return a Limitless CDN logo URL when the asset exists, else ``None``."""
    loc = (locale or "").strip().lower()
    sid = (set_id or "").strip()
    if not sid:
        return None
    if loc == "ja":
        url = f"https://s3.limitlesstcg.com/sets/jp/{sid}.png"
    else:
        url = f"https://s3.limitlesstcg.com/sets/en/{sid.upper()}.png"
    return url if _head_ok(url) else None


def apply_limitless_logo_to_row(row: dict[str, Any], locale: str) -> None:
    """Set ``logo`` from Limitless when TCGdex omitted it."""
    if row.get("logo"):
        return
    sid = row.get("id")
    if not isinstance(sid, str):
        return
    url = limitless_set_logo_url(locale, sid)
    if url:
        row["logo"] = url
        row.pop("cover", None)


def enrich_set_visuals_row(
    row: dict[str, Any],
    *,
    locale: str,
    serie_id: str | None,
    verify_limitless: bool = True,
) -> None:
    """
    Full visual enrichment for a set brief: TCGdex normalize → Limitless logo → CDN fallbacks.

    When ``verify_limitless`` is false, Limitless URLs are applied without HEAD (build-time speed).
    """
    loc = (locale or "").strip().lower()
    sid = row.get("id")
    if not isinstance(sid, str):
        return

    raw_logo = row.get("logo")
    if isinstance(raw_logo, str) and raw_logo.strip():
        norm = normalize_set_logo_url(raw_logo)
        if norm:
            row["logo"] = norm
        else:
            row.pop("logo", None)

    raw_sym = row.get("symbol")
    if isinstance(raw_sym, str) and raw_sym.strip():
        row["symbol"] = tcgdx_asset_url_with_webp(raw_sym.strip()) or raw_sym.strip()

    if not row.get("logo"):
        if verify_limitless:
            apply_limitless_logo_to_row(row, loc)
        else:
            url = (
                f"https://s3.limitlesstcg.com/sets/jp/{sid}.png"
                if loc == "ja"
                else f"https://s3.limitlesstcg.com/sets/en/{sid.upper()}.png"
            )
            row["logo"] = url

    if not row.get("logo"):
        fill_missing_set_visuals(row, locale=loc, serie_id=serie_id)
    elif row.get("cover"):
        row.pop("cover", None)


def enrich_browse_series_tree(series_list: list[dict[str, Any]], locale: str, *, verify_limitless: bool = True) -> None:
    """Mutate browse payload in place (series → sets)."""
    for serie in series_list:
        if not isinstance(serie, dict):
            continue
        serie_id = serie.get("id")
        serie_key = serie_id if isinstance(serie_id, str) else None
        raw_logo = serie.get("logo")
        if isinstance(raw_logo, str):
            norm = normalize_set_logo_url(raw_logo)
            if norm:
                serie["logo"] = norm
            else:
                serie.pop("logo", None)
        sets = serie.get("sets")
        if not isinstance(sets, list):
            continue
        for row in sets:
            if isinstance(row, dict):
                enrich_set_visuals_row(
                    row,
                    locale=locale,
                    serie_id=serie_key,
                    verify_limitless=verify_limitless,
                )


def slim_browse_series_row(serie: dict[str, Any]) -> dict[str, Any]:
    """Keep only fields the catalogue browser UI needs."""
    out: dict[str, Any] = {
        "id": serie.get("id"),
        "name": serie.get("name"),
    }
    if isinstance(serie.get("display_name"), str):
        out["display_name"] = serie["display_name"]
    if isinstance(serie.get("releaseDate"), str):
        out["releaseDate"] = serie["releaseDate"]
    if isinstance(serie.get("logo"), str):
        out["logo"] = serie["logo"]
    sets_in = serie.get("sets")
    if isinstance(sets_in, list):
        out["sets"] = [slim_set_brief_row(s) for s in sets_in if isinstance(s, dict)]
    return out


def slim_set_brief_row(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": row.get("id"),
        "name": row.get("name"),
    }
    for key in ("display_name", "logo", "symbol", "cover", "releaseDate"):
        val = row.get(key)
        if isinstance(val, str) and val.strip():
            out[key] = val.strip()
    cc = row.get("cardCount")
    if isinstance(cc, dict):
        slim_cc: dict[str, int] = {}
        for k in ("total", "official"):
            v = cc.get(k)
            if isinstance(v, int):
                slim_cc[k] = v
        if slim_cc:
            out["cardCount"] = slim_cc
    return out
