"""
Limitless TCG (JP) — Latin display names for Japanese catalog rows.

TailTCG uses the same source (limitlesstcg.com/cards/jp) in ``scripts/catalog-sync.mjs``.
We fetch on demand with a long TTL cache instead of a local DB.
"""

from __future__ import annotations

import html as html_module
import re
import threading
import time
from typing import Any

import httpx

_USER_AGENT = "GoupixDex/1.0 (+catalog; limitless-labels)"
_INDEX_URL = "https://limitlesstcg.com/cards/jp"
_INDEX_TTL_SEC = 86400.0
_SET_CARDS_TTL_SEC = 3600.0

_strip_re = re.compile(r"<[^>]+>")
_index_link_re = re.compile(
    r'href="/cards/jp/([A-Za-z0-9+.\-]+)"[^>]*>(.*?)</a>',
    re.DOTALL,
)
_table_row_re = re.compile(r"<tr[^>]*>(.*?)</tr>", re.DOTALL)
_table_cell_re = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.DOTALL)


class _Cache:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            expires, val = entry
            if expires < time.monotonic():
                self._store.pop(key, None)
                return None
            return val

    def set(self, key: str, val: Any, ttl: float) -> None:
        with self._lock:
            self._store[key] = (time.monotonic() + ttl, val)


_cache = _Cache()


def code_key(code: str) -> str:
    """Comparable code between TCGdex and Limitless (SV-P ≡ SVP, SM1+ ≡ SM1p)."""
    return code.strip().upper().replace("+", "P").replace("-", "")


def _strip_html(raw: str) -> str:
    text = _strip_re.sub(" ", raw)
    text = html_module.unescape(text)
    return " ".join(text.split()).strip()


def _http_get_text(url: str) -> str | None:
    try:
        resp = httpx.get(
            url,
            headers={"User-Agent": _USER_AGENT, "Accept": "text/html"},
            timeout=45.0,
            follow_redirects=True,
        )
    except httpx.HTTPError:
        return None
    if not resp.is_success:
        return None
    return resp.text


def limitless_jp_set_names_by_code() -> dict[str, str]:
    """
    Limitless index: set code → English display name (Latin script).
    Keys are Limitless URL codes (e.g. ``M1S``, ``SV-P``).
    """
    cache_key = "limitless_jp_index_v1"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    page = _http_get_text(_INDEX_URL)
    if not page:
        _cache.set(cache_key, {}, _INDEX_TTL_SEC)
        return {}

    out: dict[str, str] = {}
    for m in _index_link_re.finditer(page):
        code = m.group(1)
        label = _strip_html(m.group(2))
        suffix = re.compile(rf"\s*{re.escape(code)}\s*$")
        label = suffix.sub("", label).strip()
        if code and label and code not in out:
            out[code] = label

    _cache.set(cache_key, out, _INDEX_TTL_SEC)
    return out


def _resolve_limitless_code(tcgdex_set_id: str, names_by_code: dict[str, str]) -> str | None:
    want = code_key(tcgdex_set_id)
    if tcgdex_set_id in names_by_code:
        return tcgdex_set_id
    for code in names_by_code:
        if code_key(code) == want:
            return code
    return None


def latin_display_name_for_ja_set(tcgdex_set_id: str) -> str | None:
    names = limitless_jp_set_names_by_code()
    code = _resolve_limitless_code(tcgdex_set_id, names)
    if code is None:
        return None
    return names.get(code)


def _parse_limitless_list_table(page: str) -> list[dict[str, str]]:
    start = page.find("<table")
    end = page.find("</table>", start)
    if start < 0 or end < 0:
        return []
    chunk = page[start:end]
    rows: list[dict[str, str]] = []
    for tr in _table_row_re.finditer(chunk):
        cells = [_strip_html(m.group(1)) for m in _table_cell_re.finditer(tr.group(1))]
        if len(cells) < 3 or cells[0] == "Set":
            continue
        rows.append({"no": cells[1], "name": cells[2]})
    return rows


def _normalize_local_id(local_id: str) -> str:
    if re.fullmatch(r"\d+", local_id):
        return local_id.zfill(3)
    return local_id.upper()


def limitless_en_card_names_for_set(tcgdex_set_id: str) -> dict[str, str]:
    """localId → English card name (Limitless translate=en)."""
    names_by_code = limitless_jp_set_names_by_code()
    code = _resolve_limitless_code(tcgdex_set_id, names_by_code)
    if code is None:
        return {}

    cache_key = f"limitless_jp_cards_en:{code}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    url = f"https://limitlesstcg.com/cards/jp/{code}?display=list&translate=en"
    page = _http_get_text(url)
    if not page:
        _cache.set(cache_key, {}, _SET_CARDS_TTL_SEC)
        return {}

    parsed = _parse_limitless_list_table(page)
    out: dict[str, str] = {}
    for row in parsed:
        no = row.get("no", "")
        name = row.get("name", "").strip()
        if no and name:
            out[_normalize_local_id(no)] = name
            out[no] = name

    _cache.set(cache_key, out, _SET_CARDS_TTL_SEC)
    return out


def apply_limitless_labels_to_series_detail(detail: dict[str, Any]) -> None:
    """Mutate JA series payload: Latin ``display_name`` on sets when Limitless knows them."""
    sets = detail.get("sets")
    if not isinstance(sets, list):
        return
    for row in sets:
        if not isinstance(row, dict):
            continue
        sid = row.get("id")
        if not isinstance(sid, str):
            continue
        latin = latin_display_name_for_ja_set(sid)
        if latin:
            row["display_name"] = latin
        elif not row.get("display_name"):
            row["display_name"] = sid.upper()


def apply_limitless_labels_to_set_detail(detail: dict[str, Any]) -> None:
    sid = detail.get("id")
    if not isinstance(sid, str):
        return
    latin_set = latin_display_name_for_ja_set(sid)
    if latin_set:
        detail["display_name"] = latin_set
    elif not detail.get("display_name"):
        detail["display_name"] = sid.upper()

    en_by_local = limitless_en_card_names_for_set(sid)
    cards = detail.get("cards")
    if not isinstance(cards, list) or not en_by_local:
        return
    for card in cards:
        if not isinstance(card, dict):
            continue
        local_id = card.get("localId")
        if not isinstance(local_id, str):
            continue
        en = en_by_local.get(local_id) or en_by_local.get(_normalize_local_id(local_id))
        if en:
            card["display_name"] = en
