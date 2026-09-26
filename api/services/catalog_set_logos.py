"""
Set logo/symbol resolution beyond raw TCGdex API fields.

Japanese expansion art uses Pokécardex CDN (full logos), e.g.
``https://pokecardex.b-cdn.net/assets/images/logos_jp/M4.png``.

Limitless S3 (``…/sets/jp/{code}.png``) is a fallback only — many files are tiny placeholders.
EN promos may use ``…/sets/en/{CODE}.png``.
"""

from __future__ import annotations

import threading
from typing import Any

import httpx

from services.card_image_fallback_service import pokemontcg_set_id
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


_POKECARDEX_JP_BASE = "https://pokecardex.b-cdn.net/assets/images/logos_jp"


def _pokecardex_jp_code_candidates(set_id: str) -> list[str]:
    """TCGdex id variants (``M2a`` → ``M2A``, ``M-P`` → ``MP``)."""
    sid = (set_id or "").strip()
    if not sid:
        return []
    out: list[str] = []
    seen: set[str] = set()

    def add(code: str) -> None:
        c = code.strip()
        if c and c not in seen:
            seen.add(c)
            out.append(c)

    add(sid)
    add(sid.upper())
    if "-" in sid:
        add(sid.replace("-", ""))
    return out


def pokecardex_jp_set_logo_url(set_id: str) -> str | None:
    """Return Pokécardex JP logo URL when the PNG exists."""
    for code in _pokecardex_jp_code_candidates(set_id):
        url = f"{_POKECARDEX_JP_BASE}/{code}.png"
        if _head_ok(url):
            return url
    return None


# Sous-extensions sans logo propre : logo de l'extension ou de la collection promo dont elles sont issues.
_PARENT_SET_LOGOS: dict[str, str] = {
    "exu": "https://assets.tcgdex.net/{locale}/ex/ex10/logo.webp",
    "rc": "https://assets.tcgdex.net/en/bw/bw11/logo.webp",
    "wp": "https://images.pokemontcg.io/basep/logo.png",
}


def parent_set_logo_url(locale: str, set_id: str) -> str | None:
    """Logo de l'extension d'origine d'une sous-extension sans logo propre, quand l'image existe."""
    template = _PARENT_SET_LOGOS.get((set_id or "").strip().lower())
    if template is None:
        return None
    url = template.format(locale=locale)
    return url if _head_ok(url) else None


def pokemontcg_set_logo_url(set_id: str) -> str | None:
    """Logo anglais pokemontcg.io d'un set international quand l'image existe, sinon ``None``."""
    sid = (set_id or "").strip()
    if not sid:
        return None
    url = f"https://images.pokemontcg.io/{pokemontcg_set_id(sid)}/logo.png"
    return url if _head_ok(url) else None


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


def apply_external_logo_to_row(row: dict[str, Any], locale: str) -> None:
    """Set ``logo`` from Pokécardex (JA), pokemontcg.io or Limitless when TCGdex omitted it."""
    if row.get("logo"):
        return
    sid = row.get("id")
    if not isinstance(sid, str):
        return
    loc = (locale or "").strip().lower()
    url: str | None = None
    if loc == "ja":
        url = pokecardex_jp_set_logo_url(sid)
    else:
        url = parent_set_logo_url(loc, sid) or pokemontcg_set_logo_url(sid)
    if url is None:
        url = limitless_set_logo_url(loc, sid)
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
    Full visual enrichment: TCGdex → Pokécardex (JA) / Limitless → CDN fallbacks.

    When ``verify_limitless`` is false, external URLs are applied without HEAD (build-time only).
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
            apply_external_logo_to_row(row, loc)
        elif loc == "ja":
            codes = _pokecardex_jp_code_candidates(sid)
            row["logo"] = f"{_POKECARDEX_JP_BASE}/{codes[0]}.png" if codes else ""
            if not row["logo"]:
                row.pop("logo", None)
        else:
            row["logo"] = f"https://s3.limitlesstcg.com/sets/en/{sid.upper()}.png"

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
