"""
Resolve OCR output (printed ``set_code`` + ``card_number`` + language hint) into
a canonical TCGdex card id (``{setId}-{localId}``) consumable by
:mod:`services.collection_card_lookup_service`.

Strategy (cheap to expensive — first hit wins):

1. **Direct probe.** When OCR yielded a set code that *looks* like a TCGdex id
   (``sv03.5``, ``swsh07``, ``base1``), guess a few common ``localId`` forms
   (``25`` ↔ ``025`` ↔ ``H25``) and probe ``GET /{loc}/cards/{id}``.
2. **Name + localId search.** Otherwise hit ``GET /{loc}/cards?name=...`` so
   TCGdex narrows the candidate set for us, then filter client-side by
   numeric ``localId`` equality.
3. **Set-abbreviation disambiguation.** When step 2 returns multiple candidates,
   fetch only their *parent* set detail (small JSON), match TCGdex's official
   abbreviation against OCR ``set_code``, and pick the winning set.
4. **Recency tiebreaker.** When everything else is ambiguous, prefer the most
   recent block (``sv*`` > ``swsh*`` > ``sm*`` > older) — modern sets dominate
   the workflow.

All TCGdex calls go through a module-level TTL cache so a burst of 30 scans
in 30 seconds only does the network round-trip once per unique
``(locale, name, localId)`` triplet.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from typing import Any

import httpx

from services.tcgdex_client_service import (
    DEFAULT_BASE_URL,
    DEFAULT_TIMEOUT_SEC,
    DEFAULT_USER_AGENT,
    SUPPORTED_LOCALES,
    TcgdexClientService,
    infer_pokewallet_set_code,
    normalize_card_number_for_pokewallet,
)

logger = logging.getLogger(__name__)

_INDEX_TTL_SEC = 30 * 60.0
_SEARCH_TTL_SEC = 10 * 60.0
_CARD_HIT_TTL_SEC = 30 * 60.0
_SEARCH_PAGE_SIZE = 50

#: TCGdex set id prefixes ordered from newest to oldest. Picked for the
#: tiebreaker when multiple candidates remain (e.g. Pikachu appears in every
#: block — prefer the modern Scarlet/Violet print over Base Set when OCR can't
#: disambiguate via the printed set code).
_BLOCK_PRIORITY: tuple[str, ...] = (
    "sv", "A", "P-", "swsh", "sm", "xy", "bw", "hgss", "dp",
    "ex", "neo", "gym", "base", "fossil", "jungle",
)


class _LookupCache:
    """Thread-safe TTL cache shared across the FastAPI process."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._set_details: dict[tuple[str, str], tuple[float, dict[str, Any]]] = {}
        self._name_search: dict[tuple[str, str], tuple[float, list[dict[str, Any]]]] = {}
        self._card_hits: dict[tuple[str, str], tuple[float, bool]] = {}

    def get_set_detail(self, locale: str, set_id: str) -> dict[str, Any] | None:
        with self._lock:
            entry = self._set_details.get((locale, set_id))
            if entry is None:
                return None
            ts, value = entry
            if time.time() - ts > _INDEX_TTL_SEC:
                self._set_details.pop((locale, set_id), None)
                return None
            return dict(value)

    def store_set_detail(self, locale: str, set_id: str, value: dict[str, Any]) -> None:
        with self._lock:
            self._set_details[(locale, set_id)] = (time.time(), dict(value))

    def get_name_search(self, locale: str, name: str) -> list[dict[str, Any]] | None:
        with self._lock:
            entry = self._name_search.get((locale, name))
            if entry is None:
                return None
            ts, value = entry
            if time.time() - ts > _SEARCH_TTL_SEC:
                self._name_search.pop((locale, name), None)
                return None
            return list(value)

    def store_name_search(self, locale: str, name: str, value: list[dict[str, Any]]) -> None:
        with self._lock:
            self._name_search[(locale, name)] = (time.time(), list(value))

    def get_card_hit(self, locale: str, card_id: str) -> bool | None:
        with self._lock:
            entry = self._card_hits.get((locale, card_id))
            if entry is None:
                return None
            ts, exists = entry
            if time.time() - ts > _CARD_HIT_TTL_SEC:
                self._card_hits.pop((locale, card_id), None)
                return None
            return exists

    def remember_card_hit(self, locale: str, card_id: str, exists: bool) -> None:
        with self._lock:
            self._card_hits[(locale, card_id)] = (time.time(), exists)


_CACHE = _LookupCache()


def _normalise_abbrev(value: str | None) -> str:
    return (value or "").strip().upper()


def _looks_like_tcgdex_set_id(code: str) -> bool:
    """Heuristic: TCGdex set ids are lowercase alnum + dot only (``sv03.5``, ``swsh07.5``)."""
    return bool(code) and re.fullmatch(r"[a-z0-9.]+", code.lower()) is not None


def _digits_only(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def _build_local_id_candidates(local_raw: str) -> list[str]:
    """
    Common printed/recorded variants of the local id. Order = most likely first.

    TCGdex stores ``25`` for old base sets but ``025`` for SV-era ones — and
    Trainer Gallery / Hidden Fates use letter-prefixed numbers (``TG02``,
    ``H25``). We probe a curated set rather than exhaust them all.
    """
    base = (local_raw or "").strip()
    if not base:
        return []
    digits_only = re.sub(r"^[A-Za-z]+", "", base)
    out: list[str] = [base]
    if digits_only and digits_only != base:
        out.append(digits_only)
    if digits_only.isdigit():
        try:
            n = int(digits_only)
        except ValueError:
            n = None
        if n is not None:
            for pat in ("{n}", "{n:0>3}", "{n:0>2}"):
                out.append(pat.format(n=n))
                for prefix in ("H", "TG", "GG", "SV", "SWSH"):
                    out.append(f"{prefix}{pat.format(n=n)}")
    seen: set[str] = set()
    dedup: list[str] = []
    for c in out:
        c_norm = c.strip()
        if not c_norm or c_norm in seen:
            continue
        seen.add(c_norm)
        dedup.append(c_norm)
    return dedup


def _candidate_locales(language: str | None) -> list[str]:
    lang = (language or "").strip().lower()
    if lang == "ja":
        return ["ja", "en"]
    if lang == "fr":
        return ["en", "fr", "ja"]
    if lang == "en":
        return ["en", "ja"]
    return ["en", "ja"]


def _card_exists_any_locale(client: TcgdexClientService, card_id: str) -> bool:
    """True when the card id resolves in *any* supported locale.

    Japan-only prints (e.g. ``m1s-051``) exist solely under ``ja``; the
    downstream :func:`fetch_card_for_collection` is now locale-resilient, so the
    resolver must not reject them just because EN 404s.
    """
    return any(_card_exists(client, loc, card_id) for loc in sorted(SUPPORTED_LOCALES))


def _card_exists(client: TcgdexClientService, locale: str, card_id: str) -> bool:
    cached = _CACHE.get_card_hit(locale, card_id)
    if cached is not None:
        return cached
    try:
        client.get_card(locale, card_id)
    except (RuntimeError, ValueError):
        _CACHE.remember_card_hit(locale, card_id, False)
        return False
    _CACHE.remember_card_hit(locale, card_id, True)
    return True


def _search_cards_by_name(locale: str, name: str) -> list[dict[str, Any]]:
    """``GET /{locale}/cards?name=...`` — narrow, with TTL cache."""
    key_name = name.strip().lower()
    cached = _CACHE.get_name_search(locale, key_name)
    if cached is not None:
        return cached
    url = f"{DEFAULT_BASE_URL}/{locale}/cards"
    params = {
        "name": name.strip(),
        "pagination:page": "1",
        "pagination:itemsPerPage": str(_SEARCH_PAGE_SIZE),
    }
    headers = {"Accept": "application/json", "User-Agent": DEFAULT_USER_AGENT}
    try:
        resp = httpx.get(url, params=params, headers=headers, timeout=DEFAULT_TIMEOUT_SEC)
    except httpx.HTTPError as exc:
        logger.warning("TCGdex name search failed locale=%s name=%r: %s", locale, name, exc)
        _CACHE.store_name_search(locale, key_name, [])
        return []
    if not resp.is_success:
        logger.warning("TCGdex name search HTTP %s locale=%s name=%r", resp.status_code, locale, name)
        _CACHE.store_name_search(locale, key_name, [])
        return []
    try:
        raw = resp.json()
    except ValueError:
        _CACHE.store_name_search(locale, key_name, [])
        return []
    rows: list[dict[str, Any]] = []
    if isinstance(raw, list):
        for r in raw:
            if isinstance(r, dict) and isinstance(r.get("id"), str):
                rows.append(dict(r))
    _CACHE.store_name_search(locale, key_name, rows)
    return rows


def _set_id_from_card_id(card_id: str) -> str:
    """``sv03.5-025`` → ``sv03.5`` (TCGdex ids always have a trailing ``-{localId}``)."""
    if "-" in card_id:
        return card_id.rsplit("-", 1)[0]
    return card_id


def _set_detail_cached(client: TcgdexClientService, locale: str, set_id: str) -> dict[str, Any]:
    cached = _CACHE.get_set_detail(locale, set_id)
    if cached is not None:
        return cached
    try:
        detail = client.get_set(locale, set_id)
    except (RuntimeError, ValueError):
        _CACHE.store_set_detail(locale, set_id, {})
        return {}
    raw = dict(detail)
    _CACHE.store_set_detail(locale, set_id, raw)
    return raw


def _block_rank(set_id: str) -> int:
    """Lower = newer. Used as a tiebreaker when several sets contain the same card."""
    s = set_id.lower()
    for idx, prefix in enumerate(_BLOCK_PRIORITY):
        if s.startswith(prefix.lower()):
            return idx
    return len(_BLOCK_PRIORITY) + 1


def _pick_best_candidate(
    candidates: list[dict[str, Any]],
    *,
    target_local_int: int | None,
    target_local_raw: str,
    target_set_code: str,
    locale: str,
    client: TcgdexClientService,
) -> dict[str, Any] | None:
    """Among multiple name-matching cards, pick the one matching set_code / localId / recency."""
    if not candidates:
        return None

    target_code = _normalise_abbrev(target_set_code)
    matches: list[dict[str, Any]] = []
    for c in candidates:
        local = str(c.get("localId") or "").strip()
        if not local:
            continue
        digits = _digits_only(local)
        if target_local_int is not None and digits.isdigit() and int(digits) == target_local_int:
            matches.append(c)
        elif local == target_local_raw:
            matches.append(c)

    if not matches:
        return None
    if len(matches) == 1:
        return matches[0]

    if target_code:
        for c in matches:
            sid = _set_id_from_card_id(c.get("id") or "")
            if not sid:
                continue
            detail = _set_detail_cached(client, locale, sid)
            if not detail:
                continue
            abbrev = infer_pokewallet_set_code(detail)  # type: ignore[arg-type]
            if abbrev and _normalise_abbrev(abbrev) == target_code:
                return c

    matches.sort(key=lambda c: _block_rank(_set_id_from_card_id(c.get("id") or "")))
    return matches[0]


def resolve_tcgdex_card_id_from_ocr(
    *,
    ocr_set_code: str | None,
    ocr_card_number: str | None,
    ocr_pokemon_name_english: str | None = None,
    ocr_pokemon_name: str | None = None,
    physical_language: str | None = None,
    client: TcgdexClientService | None = None,
) -> str | None:
    """
    Translate the OCR triplet (set abbreviation, collector number, language) into a
    TCGdex card id usable by :func:`services.collection_card_lookup_service.fetch_card_for_collection`.

    Returns ``None`` when nothing matches — callers should record a
    ``needs_review`` scan event and let the user disambiguate manually.
    """
    raw_local = (ocr_card_number or "").strip()
    if "/" in raw_local:
        raw_local = raw_local.split("/", 1)[0]
    if not raw_local:
        return None

    cl = client or TcgdexClientService()
    set_code_raw = (ocr_set_code or "").strip()
    digits = _digits_only(raw_local)
    target_local_int = int(digits) if digits.isdigit() else None

    # --- Strategy 1: OCR set code looks like a real TCGdex id → direct probe.
    if set_code_raw and _looks_like_tcgdex_set_id(set_code_raw):
        candidate_set_id = set_code_raw.lower()
        for candidate_local in _build_local_id_candidates(raw_local):
            cid = f"{candidate_set_id}-{candidate_local}"
            for locale in _candidate_locales(physical_language):
                if locale not in SUPPORTED_LOCALES:
                    continue
                if _card_exists(cl, locale, cid):
                    return cid

    # --- Strategy 2: search by Pokémon name + match localId.
    name_candidates: list[str] = []
    for raw_name in (ocr_pokemon_name_english, ocr_pokemon_name):
        if raw_name and isinstance(raw_name, str):
            trimmed = raw_name.strip()
            if trimmed and trimmed not in name_candidates:
                name_candidates.append(trimmed)

    seen_ids: set[str] = set()
    for locale in _candidate_locales(physical_language):
        if locale not in SUPPORTED_LOCALES:
            continue
        for name in name_candidates:
            rows = _search_cards_by_name(locale, name)
            if not rows:
                continue
            best = _pick_best_candidate(
                rows,
                target_local_int=target_local_int,
                target_local_raw=raw_local,
                target_set_code=set_code_raw,
                locale=locale,
                client=cl,
            )
            if best is None:
                continue
            cid = str(best.get("id") or "").strip()
            if not cid or cid in seen_ids:
                continue
            seen_ids.add(cid)
            # Final safety net: the id must resolve somewhere (any locale), so
            # downstream metadata fetch can't dead-end. Japan-only cards pass
            # here via ``ja`` even though EN/FR 404.
            if not _card_exists_any_locale(cl, cid):
                continue
            normalised = f"{_set_id_from_card_id(cid)}-{normalize_card_number_for_pokewallet(_digits_only(str(best.get('localId') or '')) or raw_local)}"
            if normalised != cid and _card_exists_any_locale(cl, normalised):
                return normalised
            return cid

    return None
