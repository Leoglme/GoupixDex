"""HTTP client for the TCGdex public REST API (https://api.tcgdex.net/v2)."""

from __future__ import annotations

import json
from typing import Any, cast
from urllib.parse import quote, urlencode

import httpx

from app_types.tcgdex import TcgdexCardDetail, TcgdexSeriesDetail, TcgdexSetBrief, TcgdexSetDetail

DEFAULT_BASE_URL = "https://api.tcgdex.net/v2"
DEFAULT_TIMEOUT_SEC = 30.0
DEFAULT_USER_AGENT = "GoupixDex/1.0 (+catalog)"

# Locales we actively use in GoupixDex; others may work but are not validated here.
SUPPORTED_LOCALES = frozenset({"en", "fr", "ja"})
SETS_PER_PAGE_MAX = 100
SETS_PER_PAGE_DEFAULT = 50


class TcgdexClientService:
    """
    Read-only TCGdex client (no API key).

    Endpoints follow ``GET {base}/{locale}/sets`` and ``GET {base}/{locale}/cards/{id}``.
    """

    def __init__(self, base_url: str | None = None, timeout_sec: float = DEFAULT_TIMEOUT_SEC) -> None:
        self._base = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self._timeout = timeout_sec

    def list_sets(
        self,
        locale: str,
        page: int = 1,
        per_page: int = SETS_PER_PAGE_DEFAULT,
        name_contains: str | None = None,
    ) -> list[TcgdexSetBrief]:
        """
        List sets for a locale with optional server-side name filter.

        TCGdex returns a JSON array; pagination uses ``pagination:page`` and
        ``pagination:itemsPerPage`` query keys.
        """
        loc = _normalize_locale(locale)
        params: dict[str, str] = {
            "pagination:page": str(max(1, page)),
            "pagination:itemsPerPage": str(max(1, min(SETS_PER_PAGE_MAX, per_page))),
        }
        raw_name = (name_contains or "").strip()
        if raw_name:
            params["name"] = raw_name
        query = urlencode(params)
        path = f"/{quote(loc, safe='')}/sets?{query}"
        raw = self._fetch_json(path)
        if not isinstance(raw, list):
            return []
        out: list[TcgdexSetBrief] = []
        for row in raw:
            if isinstance(row, dict):
                out.append(cast(TcgdexSetBrief, row))
        return out

    def get_set(self, locale: str, set_id: str) -> TcgdexSetDetail:
        """Return full set JSON including the ``cards`` array."""
        loc = _normalize_locale(locale)
        sid = set_id.strip()
        if not sid:
            msg = "get_set: set_id must be non-empty"
            raise ValueError(msg)
        path = f"/{quote(loc, safe='')}/sets/{quote(sid, safe='')}"
        raw = self._fetch_json(path)
        if not isinstance(raw, dict):
            msg = "TCGdex set response was not a JSON object"
            raise RuntimeError(msg)
        return cast(TcgdexSetDetail, raw)

    def list_series(self, locale: str) -> list[dict[str, Any]]:
        """List TCG series for a locale (``GET /{locale}/series``)."""
        loc = _normalize_locale(locale)
        path = f"/{quote(loc, safe='')}/series"
        raw = self._fetch_json(path)
        if not isinstance(raw, list):
            return []
        return [cast(dict[str, Any], row) for row in raw if isinstance(row, dict)]

    def get_series(self, locale: str, series_id: str) -> TcgdexSeriesDetail:
        """Return full series JSON including the ``sets`` array."""
        loc = _normalize_locale(locale)
        sid = series_id.strip()
        if not sid:
            msg = "get_series: series_id must be non-empty"
            raise ValueError(msg)
        path = f"/{quote(loc, safe='')}/series/{quote(sid, safe='')}"
        raw = self._fetch_json(path)
        if not isinstance(raw, dict):
            msg = "TCGdex series response was not a JSON object"
            raise RuntimeError(msg)
        return cast(TcgdexSeriesDetail, raw)

    def get_card(self, locale: str, card_id: str) -> TcgdexCardDetail:
        """Return a single card by TCGdex id (e.g. ``sv03.5-025``)."""
        loc = _normalize_locale(locale)
        cid = card_id.strip()
        if not cid:
            msg = "get_card: card_id must be non-empty"
            raise ValueError(msg)
        path = f"/{quote(loc, safe='')}/cards/{quote(cid, safe='')}"
        raw = self._fetch_json(path)
        if not isinstance(raw, dict):
            msg = "TCGdex card response was not a JSON object"
            raise RuntimeError(msg)
        return cast(TcgdexCardDetail, raw)

    def _fetch_json(self, path: str) -> Any:
        normalized = path if path.startswith("/") else f"/{path}"
        url = f"{self._base}{normalized}"
        headers = {"Accept": "application/json", "User-Agent": DEFAULT_USER_AGENT}
        response = httpx.get(url, headers=headers, timeout=self._timeout)
        body_text = response.text
        if not response.is_success:
            msg = f"TCGdex request failed ({response.status_code} {response.reason_phrase}): {body_text}"
            raise RuntimeError(msg)
        try:
            return json.loads(body_text)
        except json.JSONDecodeError as exc:
            msg = "TCGdex response was not valid JSON"
            raise RuntimeError(msg) from exc


def _normalize_locale(locale: str) -> str:
    loc = locale.strip().lower()
    if loc not in SUPPORTED_LOCALES:
        msg = f"Unsupported TCGdex locale: {locale!r} (supported: {', '.join(sorted(SUPPORTED_LOCALES))})"
        raise ValueError(msg)
    return loc


def split_tcgdex_card_id(card_id: str) -> tuple[str, str]:
    """
    Split ``{setId}-{localId}`` into set and local number.

    Uses rsplit so set ids containing hyphens (e.g. ``sv03.5-025``) still work.
    """
    raw = card_id.strip()
    if "-" not in raw:
        msg = f"Invalid TCGdex card id (no hyphen): {card_id!r}"
        raise ValueError(msg)
    set_part, local = raw.rsplit("-", 1)
    set_part = set_part.strip()
    local = local.strip()
    if not set_part or not local:
        msg = f"Invalid TCGdex card id: {card_id!r}"
        raise ValueError(msg)
    return set_part, local


def infer_pokewallet_set_code(set_detail: TcgdexSetDetail) -> str | None:
    """
    Best-effort Cardmarket / PokéWallet style set code from TCGdex set JSON.

    Prefer ``abbreviation.official`` (e.g. ``MEW``), then ``tcgOnline``, then uppercased ``id``.
    """
    abbrev = set_detail.get("abbreviation")
    if isinstance(abbrev, dict):
        off = abbrev.get("official")
        if isinstance(off, str) and off.strip():
            return off.strip().upper()
    tcg_online = set_detail.get("tcgOnline")
    if isinstance(tcg_online, str) and tcg_online.strip():
        return tcg_online.strip().upper()
    sid = set_detail.get("id")
    if isinstance(sid, str) and sid.strip():
        return sid.strip().upper()
    return None


def normalize_card_number_for_pokewallet(local_id: str) -> str:
    """Strip useless leading zeros when the local id is purely numeric."""
    s = local_id.strip()
    if s.isdigit():
        stripped = s.lstrip("0")
        return stripped if stripped else "0"
    return s


def tcgdx_image_url_high(image_base: str) -> str:
    """
    Full card art URL for ``high`` + ``webp`` (pattern ``{quality}.{extension}``).

    https://tcgdex.dev/assets
    """
    base = image_base.rstrip("/")
    return f"{base}/high.webp"
