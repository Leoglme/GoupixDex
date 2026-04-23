"""
Build final TCGdex CDN image URLs.

API responses often omit file extensions on asset bases (e.g. ``…/136``, ``…/logo``).
Official rules: cards use ``{quality}.{extension}`` (``low`` / ``high`` + ``webp`` recommended);
logos and symbols use ``logo.{extension}`` and ``symbol.{extension}``.

See: https://tcgdex.dev/assets
"""

from __future__ import annotations


def _has_image_extension(url: str) -> bool:
    lower = url.rsplit(".", 1)[-1].lower()
    return lower in ("webp", "png", "jpg", "jpeg")


def tcgdx_asset_url_with_webp(url: str | None) -> str | None:
    """
    Turn a base path like ``…/swsh3/logo`` or ``…/symbol`` into ``…/logo.webp`` / ``…/symbol.webp``.

    Matches TCGdex assets: logos and symbols are ``logo.{extension}`` and ``symbol.{extension}``.
    """
    if url is None:
        return None
    raw = url.strip()
    if not raw:
        return None
    if _has_image_extension(raw):
        return raw
    return f"{raw}.webp"


def normalize_set_logo_url(raw_logo: str | None) -> str | None:
    """Return ``logo`` with explicit ``.webp`` when the API omits an extension, else ``None``."""
    if not isinstance(raw_logo, str) or not raw_logo.strip():
        return None
    return tcgdx_asset_url_with_webp(raw_logo.strip())


def card_image_low_webp(image_base: str | None) -> str | None:
    """
    Card preview URL: ``{cardBase}/low.webp`` (``{quality}.{extension}`` per TCGdex assets doc).
    """
    if image_base is None:
        return None
    base = image_base.strip().rstrip("/")
    if not base:
        return None
    if base.endswith("/low.webp") or "/low." in base:
        return tcgdx_asset_url_with_webp(base) or base
    return f"{base}/low.webp"


def enrich_series_brief_row(row: dict[str, object]) -> None:
    """Mutate a TCGdex series row from ``GET …/series``: normalize ``logo`` URL."""
    raw_logo = row.get("logo")
    norm = normalize_set_logo_url(raw_logo if isinstance(raw_logo, str) else None)
    if norm:
        row["logo"] = norm
    else:
        row.pop("logo", None)


def enrich_series_detail(detail: dict[str, object]) -> None:
    """Normalize series ``logo`` and run ``enrich_set_brief_row`` on each nested set."""
    raw_logo = detail.get("logo")
    norm = normalize_set_logo_url(raw_logo if isinstance(raw_logo, str) else None)
    if norm:
        detail["logo"] = norm
    else:
        detail.pop("logo", None)
    sets = detail.get("sets")
    if not isinstance(sets, list):
        return
    for entry in sets:
        if isinstance(entry, dict):
            enrich_set_brief_row(entry)


def enrich_set_brief_row(row: dict[str, object]) -> None:
    """Mutate a TCGdex set-brief dict in place: normalize ``logo`` / ``symbol`` URLs."""
    raw_logo = row.get("logo")
    norm = normalize_set_logo_url(raw_logo if isinstance(raw_logo, str) else None)
    if norm:
        row["logo"] = norm
    else:
        row.pop("logo", None)
    raw_sym = row.get("symbol")
    if isinstance(raw_sym, str) and raw_sym.strip():
        row["symbol"] = tcgdx_asset_url_with_webp(raw_sym.strip()) or raw_sym.strip()


def enrich_set_detail(detail: dict[str, object]) -> None:
    """Mutate a full set payload: ``logo`` / ``symbol`` and add ``image_low`` on each card stub."""
    raw_logo = detail.get("logo")
    norm = normalize_set_logo_url(raw_logo if isinstance(raw_logo, str) else None)
    if norm:
        detail["logo"] = norm
    else:
        detail.pop("logo", None)
    raw_sym = detail.get("symbol")
    if isinstance(raw_sym, str) and raw_sym.strip():
        detail["symbol"] = tcgdx_asset_url_with_webp(raw_sym.strip()) or raw_sym.strip()
    cards = detail.get("cards")
    if not isinstance(cards, list):
        return
    for entry in cards:
        if not isinstance(entry, dict):
            continue
        img = entry.get("image")
        low = card_image_low_webp(img if isinstance(img, str) else None)
        if low:
            entry["image_low"] = low
