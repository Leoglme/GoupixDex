"""
Browse-only TCGdex helpers for the catalog routes (series, sets, cards in set).

Adds two cross-cutting concerns the legacy ``catalog_route`` had to repeat:

* Light **in-process cache** with a 10-minute TTL (TCGdex data is essentially
  immutable for a browsing session — caching avoids re-paying network latency
  every time the user switches series).
* A **Latin display name** (``display_name``) on every payload returned to the
  front-end, so Japanese rows never show CJK characters in the UI: when the JA
  label is in Japanese script and an English equivalent exists, the EN name is
  used instead.
"""

from __future__ import annotations

import re
import threading
import time
from typing import Any

from services.tcgdex_asset_url import (
    enrich_series_brief_row,
    enrich_series_detail,
    enrich_set_brief_row,
    enrich_set_detail,
)
from services.tcgdex_client_service import SUPPORTED_LOCALES, TcgdexClientService

_CACHE_TTL_SEC = 600.0
_CJK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


def _is_japanese_script(text: str | None) -> bool:
    if not isinstance(text, str):
        return False
    return bool(_CJK_RE.search(text))


def _ensure_locale(locale: str) -> str:
    loc = (locale or "").strip().lower()
    if loc not in SUPPORTED_LOCALES:
        msg = f"Unsupported locale {locale!r}; use one of: {', '.join(sorted(SUPPORTED_LOCALES))}"
        raise ValueError(msg)
    return loc


class _TtlCache:
    """Thread-safe TTL cache (no eviction policy — TCGdex calls are tiny)."""

    def __init__(self, ttl_seconds: float = _CACHE_TTL_SEC) -> None:
        self._ttl = ttl_seconds
        self._lock = threading.Lock()
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if expires_at < time.monotonic():
                self._store.pop(key, None)
                return None
            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._store[key] = (time.monotonic() + self._ttl, value)


_cache = _TtlCache()


def _client() -> TcgdexClientService:
    return TcgdexClientService()


def _attach_display_name(row: dict[str, Any], en_lookup: dict[str, str] | None) -> None:
    """
    Always provide ``display_name`` (Latin script preferred).

    Falls back to EN when the localized ``name`` is in Japanese.
    """
    raw_name = row.get("name") if isinstance(row.get("name"), str) else ""
    if not _is_japanese_script(raw_name):
        row["display_name"] = raw_name or row.get("id") or ""
        return
    rid = row.get("id")
    en_name = en_lookup.get(rid) if en_lookup and isinstance(rid, str) else None
    row["display_name"] = en_name or raw_name or rid or ""


def _index_by_id(rows: list[dict[str, Any]], key: str = "name") -> dict[str, str]:
    out: dict[str, str] = {}
    for r in rows:
        rid = r.get("id")
        val = r.get(key)
        if isinstance(rid, str) and isinstance(val, str) and val.strip():
            out[rid] = val.strip()
    return out


def list_series_for_ui(locale: str, name_filter: str | None) -> list[dict[str, Any]]:
    """Series enriched with logos + ``display_name`` (Latin-fallback for JA)."""
    loc = _ensure_locale(locale)
    cache_key = f"series:{loc}:{(name_filter or '').strip().lower()}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    client = _client()
    rows_raw = client.list_series(loc)
    rows = [r for r in rows_raw if isinstance(r, dict)]
    if name_filter:
        q = name_filter.strip().lower()
        rows = [r for r in rows if q in (r.get("id") or "").lower() or q in (r.get("name") or "").lower()]

    en_name_lookup: dict[str, str] | None = None
    if loc == "ja":
        try:
            en_rows = client.list_series("en")
            en_name_lookup = _index_by_id(en_rows)
        except RuntimeError:
            en_name_lookup = None

    out: list[dict[str, Any]] = []
    for row in rows:
        enrich_series_brief_row(row)
        _attach_display_name(row, en_name_lookup)
        out.append(row)
    _cache.set(cache_key, out)
    return out


def list_sets_for_ui(
    locale: str, page: int, per_page: int, name_filter: str | None
) -> list[dict[str, Any]]:
    loc = _ensure_locale(locale)
    cache_key = f"sets:{loc}:{page}:{per_page}:{(name_filter or '').strip().lower()}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    client = _client()
    rows_raw = client.list_sets(loc, page=page, per_page=per_page, name_contains=name_filter)
    rows = [r for r in rows_raw if isinstance(r, dict)]

    en_name_lookup: dict[str, str] | None = None
    if loc != "en":
        try:
            en_rows = client.list_sets(
                "en", page=page, per_page=per_page, name_contains=name_filter
            )
            en_filtered = [r for r in en_rows if isinstance(r, dict)]
            for er in en_filtered:
                rid = er.get("id")
                if not isinstance(rid, str):
                    continue
                for row in rows:
                    if row.get("id") != rid:
                        continue
                    if not row.get("logo") and isinstance(er.get("logo"), str):
                        row["logo"] = er["logo"]
                    if not row.get("symbol") and isinstance(er.get("symbol"), str):
                        row["symbol"] = er["symbol"]
            if loc == "ja":
                en_name_lookup = _index_by_id(en_filtered)
        except RuntimeError:
            en_name_lookup = None

    out: list[dict[str, Any]] = []
    for row in rows:
        enrich_set_brief_row(row)
        _attach_display_name(row, en_name_lookup)
        out.append(row)
    _cache.set(cache_key, out)
    return out


def get_series_for_ui(locale: str, series_id: str) -> dict[str, Any]:
    loc = _ensure_locale(locale)
    sid = series_id.strip()
    cache_key = f"series_detail:{loc}:{sid}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    client = _client()
    detail = client.get_series(loc, sid)
    if not isinstance(detail, dict):
        msg = "Invalid TCGdex series payload"
        raise RuntimeError(msg)

    en_name_lookup: dict[str, str] | None = None
    if loc != "en":
        try:
            en_detail = client.get_series("en", sid)
            if isinstance(en_detail, dict):
                if not detail.get("logo") and isinstance(en_detail.get("logo"), str):
                    detail["logo"] = en_detail["logo"]
                en_sets = en_detail.get("sets")
                if isinstance(en_sets, list):
                    en_only = [s for s in en_sets if isinstance(s, dict)]
                    by_id = {s["id"]: s for s in en_only if isinstance(s.get("id"), str)}
                    for s in detail.get("sets") or []:
                        if not isinstance(s, dict):
                            continue
                        sid_ref = s.get("id")
                        en_ref = by_id.get(sid_ref) if isinstance(sid_ref, str) else None
                        if not en_ref:
                            continue
                        if not s.get("logo") and isinstance(en_ref.get("logo"), str):
                            s["logo"] = en_ref["logo"]
                        if not s.get("symbol") and isinstance(en_ref.get("symbol"), str):
                            s["symbol"] = en_ref["symbol"]
                    if loc == "ja":
                        en_name_lookup = _index_by_id(en_only)
        except RuntimeError:
            en_name_lookup = None

    enrich_series_detail(detail)
    sets = detail.get("sets")
    if isinstance(sets, list):
        for s in sets:
            if isinstance(s, dict):
                _attach_display_name(s, en_name_lookup)
    if loc == "ja":
        _attach_display_name(detail, en_name_lookup)
    else:
        nm = detail.get("name")
        detail["display_name"] = nm if isinstance(nm, str) else detail.get("id")

    _cache.set(cache_key, detail)
    return detail


def get_set_for_ui(locale: str, set_id: str) -> dict[str, Any]:
    loc = _ensure_locale(locale)
    sid = set_id.strip()
    cache_key = f"set_detail:{loc}:{sid}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    client = _client()
    detail = client.get_set(loc, sid)
    if not isinstance(detail, dict):
        msg = "Invalid TCGdex set payload"
        raise RuntimeError(msg)

    en_card_names: dict[str, str] | None = None
    if loc != "en":
        try:
            en_detail = client.get_set("en", sid)
            if isinstance(en_detail, dict):
                if not detail.get("logo") and isinstance(en_detail.get("logo"), str):
                    detail["logo"] = en_detail["logo"]
                if not detail.get("symbol") and isinstance(en_detail.get("symbol"), str):
                    detail["symbol"] = en_detail["symbol"]
                if loc == "ja":
                    en_cards = en_detail.get("cards")
                    if isinstance(en_cards, list):
                        en_card_names = {}
                        for ec in en_cards:
                            if not isinstance(ec, dict):
                                continue
                            ecid = ec.get("id")
                            enname = ec.get("name")
                            if isinstance(ecid, str) and isinstance(enname, str):
                                en_card_names[ecid] = enname.strip()
        except RuntimeError:
            en_card_names = None

    enrich_set_detail(detail)
    cards = detail.get("cards")
    if isinstance(cards, list):
        for c in cards:
            if not isinstance(c, dict):
                continue
            _attach_display_name(c, en_card_names)

    if loc == "ja":
        _attach_display_name(detail, None)
    else:
        nm = detail.get("name")
        detail["display_name"] = nm if isinstance(nm, str) else detail.get("id")

    _cache.set(cache_key, detail)
    return detail
