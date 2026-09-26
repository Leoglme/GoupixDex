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
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, cast

import httpx

from services.card_image_fallback_service import fallback_card_images
from services.catalog_set_logos import enrich_browse_series_tree, enrich_set_visuals_row
from services.tcgdex_asset_url import (
    card_image_low_webp,
    enrich_series_brief_row,
    enrich_series_detail,
    enrich_set_brief_row,
    enrich_set_detail,
)
from services.catalog_limitless_ja_service import (
    apply_limitless_labels_to_series_detail,
    apply_limitless_labels_to_set_detail,
    latin_display_name_for_ja_set,
    limitless_jp_set_names_by_code,
)
from services.tcgdex_client_service import SUPPORTED_LOCALES, TcgdexClientService

_CACHE_TTL_SEC = 600.0
_CACHE_VERSION = "latin-labels-v9"
_CACHE_TTL_BROWSE_SEC = 3600.0
_CJK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
_GLUED_NUMBER_RE = re.compile(r"(?<=[a-z\u00e0-\u00ff]{3})(?=\d)")

# Sous-extensions que TCGdex s\u00e9pare mais que Cardmarket vend comme une seule extension.
_MERGED_SUBSET_PARENTS: dict[str, str] = {"30th-c": "30th"}

# Num\u00e9ros imprim\u00e9s de la Collection Classique (num\u00e9ros des cartes d'origine) ; TCGdex les num\u00e9rote 001 \u00e0 030.
_MERGED_PRINTED_NUMBERS: dict[str, str] = {
    "30th-c-001": "4/102",
    "30th-c-002": "5/109",
    "30th-c-003": "11/113",
    "30th-c-004": "11/101",
    "30th-c-005": "18/132",
    "30th-c-006": "19/109",
    "30th-c-007": "25/111",
    "30th-c-008": "33/181",
    "30th-c-009": "41/122",
    "30th-c-010": "43/146",
    "30th-c-011": "47/127",
    "30th-c-012": "50/185",
    "30th-c-013": "57/111",
    "30th-c-014": "58/102",
    "30th-c-015": "69/132",
    "30th-c-016": "85/124",
    "30th-c-017": "89/149",
    "30th-c-018": "94/102",
    "30th-c-019": "99/102",
    "30th-c-020": "100/102",
    "30th-c-021": "101/101",
    "30th-c-022": "106/106",
    "30th-c-023": "106/160",
    "30th-c-024": "106/105",
    "30th-c-025": "108/115",
    "30th-c-026": "114/264",
    "30th-c-027": "123/172",
    "30th-c-028": "138/202",
    "30th-c-029": "149/147",
    "30th-c-030": "203/193",
}


def readable_set_name(name: str) -> str:
    """Nom d'extension lisible : TCGdex colle parfois un mot et un nombre (\u00ab Collection Classique30\u1d49 \u00bb)."""
    return _GLUED_NUMBER_RE.sub(" ", name)


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

    def set(self, key: str, value: Any, ttl_seconds: float | None = None) -> None:
        ttl = ttl_seconds if ttl_seconds is not None else self._ttl
        with self._lock:
            self._store[key] = (time.monotonic() + ttl, value)


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


def _card_count_tuple(row: dict[str, Any]) -> tuple[int | None, int | None]:
    cc = row.get("cardCount")
    if not isinstance(cc, dict):
        return (None, None)
    total = cc.get("total")
    official = cc.get("official")
    t = int(total) if isinstance(total, int) else None
    o = int(official) if isinstance(official, int) else None
    return (t, o)


def _norm_set_id(set_id: str) -> str:
    return set_id.strip().lower()


def _find_label_set(ja_set: dict[str, Any], label_sets: list[dict[str, Any]]) -> dict[str, Any] | None:
    """
    Match a JA set to FR metadata — conservative rules only.

    Wrong logos/names are worse than Japanese labels: we never match on card total alone.
    """
    sid = ja_set.get("id")
    if isinstance(sid, str):
        sid_key = _norm_set_id(sid)
        for candidate in label_sets:
            if not isinstance(candidate, dict):
                continue
            cid = candidate.get("id")
            if isinstance(cid, str) and _norm_set_id(cid) == sid_key:
                return candidate

    ja_rd = ja_set.get("releaseDate") if isinstance(ja_set.get("releaseDate"), str) else ""
    ja_total, ja_official = _card_count_tuple(ja_set)

    if ja_rd:
        rd_matches: list[dict[str, Any]] = []
        for candidate in label_sets:
            if not isinstance(candidate, dict):
                continue
            c_rd = candidate.get("releaseDate") if isinstance(candidate.get("releaseDate"), str) else ""
            if c_rd != ja_rd:
                continue
            ct, co = _card_count_tuple(candidate)
            if ja_total is not None and ct == ja_total:
                rd_matches.append(candidate)
            elif ja_official is not None and co == ja_official:
                rd_matches.append(candidate)
        if len(rd_matches) == 1:
            return rd_matches[0]
        return None

    if ja_total is not None and ja_official is not None:
        count_matches = [
            c
            for c in label_sets
            if isinstance(c, dict) and _card_count_tuple(c) == (ja_total, ja_official)
        ]
        if len(count_matches) == 1:
            return count_matches[0]

    return None


def _apply_label_set_assets(target: dict[str, Any], label: dict[str, Any]) -> None:
    name = label.get("name")
    if isinstance(name, str) and name.strip():
        target["display_name"] = name.strip()
    _apply_matched_set_visuals(target, label)


def _apply_matched_set_visuals(target: dict[str, Any], label: dict[str, Any]) -> None:
    if not target.get("logo") and isinstance(label.get("logo"), str):
        target["logo"] = label["logo"]
    if not target.get("symbol") and isinstance(label.get("symbol"), str):
        target["symbol"] = label["symbol"]


_JA_TO_EN_SERIES: dict[str, str] = {
    "M": "me",
    "SV": "sv",
    "S": "sm",
    "XY": "xy",
    "BW": "bw",
    "HGSS": "hgss",
    "DP": "dp",
    "EX": "ex",
    "ECARD": "ecard",
    "NEO": "neo",
    "BASE": "base",
}


def _apply_en_visuals_to_ja_sets(detail: dict[str, Any], client: TcgdexClientService) -> None:
    """Copy EN set logos/symbols onto JA rows when release/card-count matching is unambiguous."""
    ja_series_id = detail.get("id")
    if not isinstance(ja_series_id, str):
        return
    en_series_id = _JA_TO_EN_SERIES.get(ja_series_id.upper()) or ja_series_id.lower()
    try:
        en_detail = client.get_series("en", en_series_id)
    except (RuntimeError, ValueError):
        return
    if not isinstance(en_detail, dict):
        return
    en_sets = [s for s in (en_detail.get("sets") or []) if isinstance(s, dict)]
    for es in en_sets:
        enrich_set_brief_row(es)

    ja_sets = detail.get("sets")
    if not isinstance(ja_sets, list):
        return
    for js in ja_sets:
        if not isinstance(js, dict) or js.get("logo"):
            continue
        matched = _find_label_set(js, en_sets)
        if matched is not None:
            _apply_matched_set_visuals(js, matched)


def _fill_set_visuals_on_series(detail: dict[str, Any], locale: str) -> None:
    enrich_browse_series_tree([detail], locale, verify_limitless=True)


def _index_card_names_by_local_id(set_detail: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    cards = set_detail.get("cards")
    if not isinstance(cards, list):
        return out
    for card in cards:
        if not isinstance(card, dict):
            continue
        local_id = card.get("localId")
        name = card.get("name")
        if isinstance(local_id, str) and isinstance(name, str) and name.strip():
            out[local_id] = name.strip()
    return out


def _build_fr_series_label_catalog(client: TcgdexClientService) -> list[dict[str, Any]]:
    """All FR series with nested sets (for cross-locale JA labelling)."""
    cache_key = f"fr_series_label_catalog:{_CACHE_VERSION}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    briefs = [b for b in client.list_series("fr") if _keep_series_row(b)]

    def _load_fr_series(series_id: str) -> dict[str, Any] | None:
        try:
            row = client.get_series("fr", series_id)
        except (RuntimeError, ValueError):
            return None
        if not isinstance(row, dict):
            return None
        enrich_series_detail(row)
        nm = row.get("name")
        if isinstance(nm, str) and nm.strip():
            row["display_name"] = nm.strip()
        return row

    out: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {
            pool.submit(_load_fr_series, str(b["id"])): b
            for b in briefs
            if isinstance(b.get("id"), str)
        }
        for fut in as_completed(futures):
            row = fut.result()
            if row is not None:
                out.append(row)

    _cache.set(cache_key, out)
    return out


def _best_fr_series_for_ja(
    ja_sets: list[dict[str, Any]], fr_catalog: list[dict[str, Any]]
) -> tuple[dict[str, Any] | None, int]:
    best: dict[str, Any] | None = None
    best_score = 0
    for fr_series in fr_catalog:
        fr_sets = [s for s in (fr_series.get("sets") or []) if isinstance(s, dict)]
        score = sum(1 for js in ja_sets if _find_label_set(js, fr_sets))
        if score > best_score:
            best_score = score
            best = fr_series
    return best, best_score


def _series_label_confident(ja_set_count: int, strict_matches: int) -> bool:
    if strict_matches < 1:
        return False
    if ja_set_count <= 3:
        return strict_matches >= 1
    return strict_matches >= 2 and strict_matches >= ja_set_count // 3


def _resolve_fr_set_for_ja(
    client: TcgdexClientService, ja_detail: dict[str, Any], set_id: str
) -> dict[str, Any] | None:
    """Find the French set payload that best labels a Japanese-only set id."""
    try:
        direct = client.get_set("fr", set_id)
        if isinstance(direct, dict):
            return direct
    except (RuntimeError, ValueError):
        pass

    fr_catalog = _build_fr_series_label_catalog(client)
    ja_brief = {
        "id": set_id,
        "releaseDate": ja_detail.get("releaseDate"),
        "cardCount": ja_detail.get("cardCount"),
    }
    ja_sets = [ja_brief]
    best_fr, score = _best_fr_series_for_ja(ja_sets, fr_catalog)
    matched: dict[str, Any] | None = None
    if best_fr is not None and score >= 1:
        fr_sets = [s for s in (best_fr.get("sets") or []) if isinstance(s, dict)]
        matched = _find_label_set(ja_brief, fr_sets)
    if matched is None:
        return None
    mid = matched.get("id")
    if not isinstance(mid, str):
        return None
    try:
        full = client.get_set("fr", mid)
        return full if isinstance(full, dict) else None
    except (RuntimeError, ValueError):
        return None


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
        enrich_set_visuals_row(row, locale=loc, serie_id=None, verify_limitless=True)
        _attach_display_name(row, en_name_lookup)
        out.append(row)
    _cache.set(cache_key, out)
    return out


def get_series_for_ui(locale: str, series_id: str) -> dict[str, Any]:
    loc = _ensure_locale(locale)
    sid = series_id.strip()
    cache_key = f"series_detail:{_CACHE_VERSION}:{loc}:{sid}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    client = _client()
    detail = client.get_series(loc, sid)
    if not isinstance(detail, dict):
        msg = "Invalid TCGdex series payload"
        raise RuntimeError(msg)

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
                        if loc == "ja" and not s.get("display_name"):
                            en_name = en_ref.get("name")
                            if isinstance(en_name, str) and en_name.strip():
                                s["display_name"] = en_name.strip()
        except RuntimeError:
            pass

    if loc == "ja":
        try:
            en_detail = client.get_series("en", sid)
            if isinstance(en_detail, dict):
                en_name = en_detail.get("name")
                if isinstance(en_name, str) and en_name.strip() and not _is_japanese_script(en_name):
                    detail["display_name"] = en_name.strip()
        except RuntimeError:
            pass

    enrich_series_detail(detail)
    sets = detail.get("sets")
    if isinstance(sets, list):
        typed_sets = [s for s in sets if isinstance(s, dict)]
        typed_sets.sort(
            key=lambda s: (s.get("releaseDate") or "", s.get("id") or ""),
            reverse=True,
        )
        detail["sets"] = typed_sets
        if loc == "ja":
            _apply_en_visuals_to_ja_sets(detail, client)
            apply_limitless_labels_to_series_detail(detail)
        else:
            for s in typed_sets:
                if not s.get("display_name"):
                    _attach_display_name(s, None)
        _fill_set_visuals_on_series(detail, loc)
    if loc != "ja":
        nm = detail.get("name")
        detail["display_name"] = nm if isinstance(nm, str) else detail.get("id")
    elif not detail.get("display_name") or _is_japanese_script(str(detail.get("display_name") or "")):
        series_fallback = {"M": "MEGA", "SV": "Scarlet & Violet", "S": "Sun & Moon"}.get(sid.upper())
        detail["display_name"] = series_fallback or sid.upper()

    _cache.set(cache_key, detail)
    return detail


def _set_id_from_card_id(card_id: str) -> str:
    i = card_id.rfind("-")
    return card_id[:i] if i != -1 else card_id


def _keep_series_row(row: dict[str, Any]) -> bool:
    sid = row.get("id")
    name = row.get("name") if isinstance(row.get("name"), str) else ""
    if sid == "tcgp":
        return False
    return "pocket" not in name.lower()


def browse_catalog_for_ui(locale: str) -> list[dict[str, Any]]:
    """
    All TCGdex series with nested sets (newest first), same shape as TailTCG ``catalogSeries``.

    Fetches each series detail in parallel; heavily cached for browsing sessions.
    """
    loc = _ensure_locale(locale)
    cache_key = f"browse:{_CACHE_VERSION}:{loc}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    if loc == "ja":
        limitless_jp_set_names_by_code()

    briefs = [b for b in list_series_for_ui(loc, None) if _keep_series_row(b)]
    details: list[dict[str, Any]] = []

    def _load_one(series_id: str) -> dict[str, Any] | None:
        try:
            return get_series_for_ui(loc, series_id)
        except RuntimeError:
            return None

    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {
            pool.submit(_load_one, str(b["id"])): b
            for b in briefs
            if isinstance(b.get("id"), str)
        }
        for fut in as_completed(futures):
            row = fut.result()
            if row is not None:
                details.append(row)

    def _sort_sets(sets: list[dict[str, Any]] | None) -> None:
        if not sets:
            return
        sets.sort(key=lambda s: (s.get("releaseDate") or ""), reverse=True)

    set_facts = _set_release_facts(
        loc,
        [
            str(row["id"])
            for serie in details
            for row in serie.get("sets") or []
            if isinstance(row, dict) and isinstance(row.get("id"), str)
        ],
    )
    ghost_set_ids = _ghost_set_ids(details, set_facts)
    for serie in details:
        sets = serie.get("sets")
        if isinstance(sets, list):
            typed = [s for s in sets if isinstance(s, dict) and str(s.get("id")) not in ghost_set_ids]
            for row in typed:
                release_date = set_facts.get(str(row.get("id")), (None, -1))[0]
                if release_date and not row.get("releaseDate"):
                    row["releaseDate"] = release_date
            _sort_sets(typed)
            serie["sets"] = typed

    details = [serie for serie in details if serie.get("sets")]
    details.sort(key=lambda s: (s.get("releaseDate") or ""), reverse=True)
    enrich_browse_series_tree(details, loc, verify_limitless=True)
    details = _merge_subset_rows(details, loc)
    _cache.set(cache_key, details, ttl_seconds=_CACHE_TTL_BROWSE_SEC)
    return details


def _ghost_set_ids(
    series_details: list[dict[str, Any]], set_facts: dict[str, tuple[str | None, int]]
) -> set[str]:
    """Fiches TCGdex fantômes : extension vide copiant une extension garnie (même nom, même date) ou nom répété en série."""
    rows = [row for serie in series_details for row in serie.get("sets") or [] if isinstance(row, dict)]
    name_counts = Counter(str(row.get("name")) for row in rows)
    filled_twins = {
        (str(row.get("name")), set_facts.get(str(row.get("id")), (None, -1))[0])
        for row in rows
        if set_facts.get(str(row.get("id")), (None, -1))[1] > 0
    }
    ghosts: set[str] = set()
    for row in rows:
        release_date, card_total = set_facts.get(str(row.get("id")), (None, -1))
        name = str(row.get("name"))
        if card_total == 0 and ((name, release_date) in filled_twins or name_counts[name] > 2):
            ghosts.add(str(row.get("id")))
    return ghosts


def _set_release_facts(loc: str, set_ids: list[str]) -> dict[str, tuple[str | None, int]]:
    """Date de sortie et nombre réel de cartes de chaque extension (absents des fiches de série TCGdex), -1 si illisible."""
    client = _client()

    def _facts(set_id: str) -> tuple[str | None, int]:
        try:
            detail = client.get_set(loc, set_id)
        except (RuntimeError, ValueError):
            return (None, -1)
        release_date = detail.get("releaseDate")
        cards = detail.get("cards")
        return (release_date if isinstance(release_date, str) else None, len(cards) if isinstance(cards, list) else -1)

    with ThreadPoolExecutor(max_workers=12) as pool:
        return dict(zip(set_ids, pool.map(_facts, set_ids), strict=True))


def _merge_subset_rows(series_details: list[dict[str, Any]], loc: str) -> list[dict[str, Any]]:
    """Copie du navigateur sans les sous-extensions fusionnées, leurs cartes comptées dans l'extension parente."""
    merged = [{**serie, "sets": [dict(row) for row in serie.get("sets") or []]} for serie in series_details]
    rows_by_id = {row["id"]: row for serie in merged for row in serie["sets"] if isinstance(row.get("id"), str)}
    absorbed: set[str] = set()
    for child_id, parent_id in _MERGED_SUBSET_PARENTS.items():
        child = rows_by_id.get(child_id)
        parent = rows_by_id.get(parent_id)
        if child is None or parent is None:
            continue
        absorbed.add(child_id)
        child_total = _card_count_tuple(child)[0]
        parent_count = parent.get("cardCount")
        if child_total and isinstance(parent_count, dict) and isinstance(parent_count.get("total"), int):
            parent["cardCount"] = {**parent_count, "total": parent_count["total"] + child_total}
    for serie in merged:
        serie["sets"] = [row for row in serie["sets"] if row.get("id") not in absorbed]
        if loc != "ja":
            for row in serie["sets"]:
                label = row.get("display_name") or row.get("name")
                if isinstance(label, str):
                    row["display_name"] = readable_set_name(label)
    return merged


def search_cards_for_ui(locale: str, query: str) -> list[dict[str, Any]]:
    """Card search by name (and optional trailing number), TailTCG-style."""
    loc = _ensure_locale(locale)
    q = query.strip()
    if len(q) < 2:
        return []

    cache_key = f"search:{loc}:{q.lower()}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    num_match = re.match(r"^(.*?)\s*(\d+)(?:\s*/\s*\d+)?$", q)
    name_part = num_match.group(1).strip() if num_match else q
    local_id_part = num_match.group(2) if num_match else None

    base = _client()._base  # noqa: SLF001 — shared TCGdex root
    headers = {"Accept": "application/json", "User-Agent": "GoupixDex/1.0 (+catalog)"}

    def _fetch(params: dict[str, str]) -> list[dict[str, Any]]:
        url = f"{base}/{loc}/cards"
        try:
            resp = httpx.get(url, params=params, headers=headers, timeout=30.0)
        except httpx.HTTPError:
            return []
        if not resp.is_success:
            return []
        raw = resp.json()
        if not isinstance(raw, list):
            return []
        return [dict(row) for row in raw if isinstance(row, dict)]

    params: dict[str, str] = {
        "pagination:page": "1",
        "pagination:itemsPerPage": "40",
    }
    if local_id_part and name_part:
        params["name"] = f"like:{name_part}"
        params["localId"] = f"like:{local_id_part}"
    elif local_id_part and not name_part:
        params["localId"] = f"like:{local_id_part}"
    else:
        params["name"] = f"like:{name_part or q}"

    rows = _fetch(params)
    if not rows and name_part and " " in name_part:
        first = name_part.split()[0]
        params = {
            "pagination:page": "1",
            "pagination:itemsPerPage": "40",
            "name": f"like:{first}",
        }
        if local_id_part:
            params["localId"] = f"like:{local_id_part}"
        rows = _fetch(params)

    set_name_by_id: dict[str, str] = {}
    name_locale = "fr" if loc == "ja" else loc
    try:
        for page in (1, 2, 3):
            for s in list_sets_for_ui(name_locale, page=page, per_page=100, name_filter=None):
                sid = s.get("id")
                if isinstance(sid, str):
                    dn = s.get("display_name") or s.get("name")
                    if isinstance(dn, str):
                        set_name_by_id[sid] = dn
    except RuntimeError:
        pass

    fr_card_labels: dict[tuple[str, str], str] = {}
    if loc == "ja":
        try:
            fr_url = f"{base}/fr/cards"
            fr_resp = httpx.get(
                fr_url,
                params={k: v for k, v in params.items()},
                headers=headers,
                timeout=30.0,
            )
            if fr_resp.is_success and isinstance(fr_resp.json(), list):
                for fc in fr_resp.json():
                    if not isinstance(fc, dict):
                        continue
                    fc_id = fc.get("id")
                    local_id = fc.get("localId")
                    fname = fc.get("name")
                    if (
                        isinstance(fc_id, str)
                        and isinstance(local_id, str)
                        and isinstance(fname, str)
                        and fname.strip()
                    ):
                        fr_card_labels[( _set_id_from_card_id(fc_id), local_id)] = fname.strip()
        except httpx.HTTPError:
            fr_card_labels = {}

    pocket_ids = {"tcgp"}
    out: list[dict[str, Any]] = []
    for row in rows:
        cid = row.get("id")
        if not isinstance(cid, str):
            continue
        set_id = _set_id_from_card_id(cid)
        if set_id in pocket_ids:
            continue
        if loc == "ja":
            local_id = row.get("localId")
            label_key = (set_id, local_id) if isinstance(local_id, str) else None
            fr_label = fr_card_labels.get(label_key) if label_key else None
            if fr_label:
                row["display_name"] = fr_label
            else:
                _attach_display_name(row, None)
        else:
            _attach_display_name(row, None)
        img = row.get("image")
        low = card_image_low_webp(img if isinstance(img, str) else None)
        if low:
            row["image_low"] = low
        row["set_id"] = set_id
        if loc == "ja":
            latin_set = latin_display_name_for_ja_set(set_id)
            row["set_name"] = latin_set or set_id.upper()
        else:
            set_name = set_name_by_id.get(set_id)
            row["set_name"] = readable_set_name(set_name) if set_name else set_id
        out.append(row)

    _cache.set(cache_key, out)
    return out


def get_set_for_ui(locale: str, set_id: str) -> dict[str, Any]:
    loc = _ensure_locale(locale)
    sid = set_id.strip()
    cache_key = f"set_detail:{_CACHE_VERSION}:{loc}:{sid}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    client = _client()
    detail = client.get_set(loc, sid)
    if not isinstance(detail, dict):
        msg = "Invalid TCGdex set payload"
        raise RuntimeError(msg)

    if loc != "en":
        try:
            en_detail = client.get_set("en", sid)
            if isinstance(en_detail, dict):
                if not detail.get("logo") and isinstance(en_detail.get("logo"), str):
                    detail["logo"] = en_detail["logo"]
                if not detail.get("symbol") and isinstance(en_detail.get("symbol"), str):
                    detail["symbol"] = en_detail["symbol"]
        except RuntimeError:
            pass

    enrich_set_detail(detail)
    serie_obj = detail.get("serie")
    serie_id = serie_obj.get("id") if isinstance(serie_obj, dict) else None
    enrich_set_visuals_row(
        detail,
        locale=loc,
        serie_id=serie_id if isinstance(serie_id, str) else None,
        verify_limitless=True,
    )
    if loc == "ja":
        apply_limitless_labels_to_set_detail(detail)
    else:
        cards = detail.get("cards")
        if isinstance(cards, list):
            for c in cards:
                if isinstance(c, dict):
                    _attach_display_name(c, None)
        nm = detail.get("name")
        detail["display_name"] = readable_set_name(nm) if isinstance(nm, str) else detail.get("id")

    _fill_missing_card_images(cast(dict[str, Any], detail), loc)
    _append_merged_subset_cards(cast(dict[str, Any], detail), loc)
    _cache.set(cache_key, detail)
    return detail


def _fill_missing_card_images(detail: dict[str, Any], loc: str) -> None:
    """Donne une vignette (``image_low``) aux cartes sans scan TCGdex exploitable à partir des scans de repli."""
    fallbacks = fallback_card_images(loc, detail)
    if not fallbacks:
        return
    for card in detail.get("cards") or []:
        if isinstance(card, dict):
            urls = fallbacks.get(str(card.get("localId")))
            if urls is not None:
                card["image_low"] = urls.low


def _append_merged_subset_cards(detail: dict[str, Any], loc: str) -> None:
    """Ajoute à une extension les cartes de ses sous-extensions fusionnées, avec leur numéro imprimé."""
    parent_id = detail.get("id")
    for child_id, merged_parent_id in _MERGED_SUBSET_PARENTS.items():
        if merged_parent_id != parent_id:
            continue
        try:
            child = get_set_for_ui(loc, child_id)
        except (RuntimeError, ValueError):
            continue
        child_cards: list[dict[str, Any]] = []
        for card in child.get("cards") or []:
            if not isinstance(card, dict):
                continue
            merged_card = {**card, "merged_from": child_id}
            printed_number = _MERGED_PRINTED_NUMBERS.get(str(card.get("id")))
            if printed_number:
                merged_card["display_local_id"] = printed_number
            child_cards.append(merged_card)
        if not child_cards:
            continue
        detail["cards"] = [*(detail.get("cards") or []), *child_cards]
        card_count = detail.get("cardCount")
        if isinstance(card_count, dict) and isinstance(card_count.get("total"), int):
            detail["cardCount"] = {**card_count, "total": card_count["total"] + len(child_cards)}
