"""
Scans de repli pour les cartes que TCGdex liste sans ``image`` (galeries, promos, McDonald's, collections classiques…).

Sources, de la plus fidèle à la plus lointaine : CDN TCGdex par convention dans la langue demandée, images
anglaises TCGdex (listées ou par convention), données publiques pokemontcg.io (numéro imprimé ou nom anglais),
puis CDN Limitless pour les promos et énergies récentes.
"""

from __future__ import annotations

import re
import threading
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx

from services.tcgdex_client_service import TcgdexClientService

_USER_AGENT = "GoupixDex/1.0 (+catalog; card-images)"
_TCGDEX_ASSETS_BASE = "https://assets.tcgdex.net"
_POKEMONTCG_CARDS_BASE = "https://raw.githubusercontent.com/PokemonTCG/pokemon-tcg-data/master/cards/en"
_LIMITLESS_CARDS_BASE = "https://limitlesstcg.nyc3.cdn.digitaloceanspaces.com/tpci"
_CACHE_TTL_SEC = 86400.0
_PROBE_WORKERS = 24
_PROBE_SAMPLE_SIZE = 3

# Codes Limitless des promos et énergies récentes, dont la numérotation suit celle de TCGdex.
_LIMITLESS_ENGLISH_CODES: dict[str, str] = {"mee": "MEE", "mep": "MEP", "sve": "SVE", "svp": "SVP"}

# Identifiants pokemontcg.io que la règle de conversion ne retrouve pas.
_POKEMONTCG_SET_IDS: dict[str, str] = {
    "2011bw": "mcd11",
    "2012bw": "mcd12",
    "2014xy": "mcd14",
    "2015xy": "mcd15",
    "2016xy": "mcd16",
    "2017sm": "mcd17",
    "2018sm": "mcd18",
    "2019sm": "mcd19",
    "2021swsh": "mcd21",
    "2022swsh": "mcd22",
    "30th": "me55",
    "30th-c": "me55c",
    "bog": "bp",
    "cel25cc": "cel25c",
    "hgssp": "hsp",
    "sm3.5": "sm35",
    "sm7.5": "sm75",
    "swsh4.5sv": "swsh45sv",
    "tk-ex-latia": "tk1a",
    "tk-ex-latio": "tk1b",
    "tk-ex-m": "tk2b",
    "tk-ex-p": "tk2a",
}

_SET_ID_RULE_RE = re.compile(r"^([a-z]+)0*(\d+)(\.5)?(.*)$", re.IGNORECASE)
_CARD_NUMBER_RE = re.compile(r"^([A-Z]*)0*(\d+)([A-Z]*)$")
_LEVEL_X_RE = re.compile(r"\blv\.?\s*x\b")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")

# Client partagé : garder les connexions ouvertes rend les centaines de requêtes HEAD quatre fois plus rapides.
_http = httpx.Client(
    headers={"User-Agent": _USER_AGENT},
    timeout=10.0,
    follow_redirects=True,
    limits=httpx.Limits(max_connections=_PROBE_WORKERS, max_keepalive_connections=_PROBE_WORKERS),
)


@dataclass(frozen=True)
class CardImageUrls:
    """Vignette de grille et image haute définition d'une carte."""

    low: str
    high: str


class _TtlCache:
    """Cache mémoire à expiration, partagé entre threads."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        """Valeur encore valide pour cette clé, sinon ``None``."""
        with self._lock:
            entry = self._store.get(key)
            if entry is None or entry[0] < time.monotonic():
                return None
            return entry[1]

    def set(self, key: str, value: Any) -> None:
        """Mémorise une valeur pour la durée du cache."""
        with self._lock:
            self._store[key] = (time.monotonic() + _CACHE_TTL_SEC, value)


_cache = _TtlCache()


def fallback_card_images(locale: str, set_detail: dict[str, Any]) -> dict[str, CardImageUrls]:
    """Scans de repli des cartes d'un set TCGdex sans scan exploitable, indexés par ``localId``."""
    set_id = set_detail.get("id")
    if not isinstance(set_id, str):
        return {}
    cache_key = f"set:{locale}:{set_id}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    serie = set_detail.get("serie")
    serie_id = serie.get("id") if isinstance(serie, dict) else None
    cards = [card for card in set_detail.get("cards") or [] if isinstance(card, dict)]
    missing = [
        str(card["localId"]) for card in cards if isinstance(card.get("localId"), str) and not card.get("image")
    ] + _broken_lettered_images(cards)
    if not missing:
        _cache.set(cache_key, {})
        return {}

    has_serie = isinstance(serie_id, str) and bool(serie_id)
    found: dict[str, CardImageUrls] = {}
    if has_serie:
        found.update(_probe_tcgdex_convention(locale, str(serie_id), set_id, missing))

    if locale != "ja":
        english_cards = _english_cards_by_local_id(locale, set_detail)
        for local_id in _still_missing(missing, found):
            english_image = english_cards.get(local_id, {}).get("image")
            if not isinstance(english_image, str) or not english_image.strip():
                continue
            english_urls = _tcgdex_urls(english_image.strip())
            if _has_digit(local_id) or _asset_exists(english_urls.low):
                found[local_id] = english_urls
        if locale != "en" and has_serie:
            found.update(_probe_tcgdex_convention("en", str(serie_id), set_id, _still_missing(missing, found)))
        english_names = {
            local_id: _normalize_name(card.get("name")) for local_id, card in english_cards.items() if card.get("name")
        }
        found.update(_match_pokemontcg(set_id, _still_missing(missing, found), english_names))
        found.update(_probe_limitless_english(set_id, _still_missing(missing, found)))

    _cache.set(cache_key, found)
    return found


def fallback_card_image(locale: str, set_detail: dict[str, Any], local_id: str) -> CardImageUrls | None:
    """Scan de repli d'une carte précise d'un set TCGdex, ou ``None``."""
    return fallback_card_images(locale, set_detail).get(local_id)


def has_lettered_number(local_id: str) -> bool:
    """Vrai pour un numéro de carte sans chiffre (Mew R, G et B), dont TCGdex liste parfois un scan inexistant."""
    return not _has_digit(local_id)


def _has_digit(value: str) -> bool:
    """Vrai quand la chaîne contient au moins un chiffre."""
    return any(character.isdigit() for character in value)


def _broken_lettered_images(cards: list[dict[str, Any]]) -> list[str]:
    """Cartes à numéro sans chiffre dont le scan listé par TCGdex est absent de son CDN."""
    lettered = [
        card
        for card in cards
        if isinstance(card.get("localId"), str)
        and isinstance(card.get("image"), str)
        and has_lettered_number(card["localId"])
    ]
    exists = _assets_exist([f"{str(card['image']).rstrip('/')}/low.webp" for card in lettered])
    return [str(card["localId"]) for card, ok in zip(lettered, exists, strict=True) if not ok]


def _still_missing(local_ids: list[str], found: dict[str, CardImageUrls]) -> list[str]:
    """Cartes pas encore pourvues d'un scan, dans l'ordre d'origine."""
    return [local_id for local_id in local_ids if local_id not in found]


def _english_cards_by_local_id(locale: str, set_detail: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Cartes anglaises du même set (noms et images de référence), vide pour le japonais ou si absent."""
    if locale == "ja":
        return {}
    detail: dict[str, Any] | None = set_detail
    if locale != "en":
        detail = _english_set_detail(str(set_detail.get("id")))
    cards = detail.get("cards") if isinstance(detail, dict) else None
    return {
        str(card["localId"]): card
        for card in cards or []
        if isinstance(card, dict) and isinstance(card.get("localId"), str)
    }


def _english_set_detail(set_id: str) -> dict[str, Any] | None:
    """Fiche anglaise d'un set TCGdex (mise en cache), ``None`` quand le set n'existe qu'en une autre langue."""
    cache_key = f"en-set:{set_id}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached or None
    try:
        detail: dict[str, Any] = dict(TcgdexClientService().get_set("en", set_id))
    except (RuntimeError, ValueError):
        detail = {}
    _cache.set(cache_key, detail)
    return detail or None


def _tcgdex_urls(image_base: str) -> CardImageUrls:
    """URLs basse et haute définition d'une base d'asset TCGdex."""
    base = image_base.rstrip("/")
    return CardImageUrls(low=f"{base}/low.webp", high=f"{base}/high.webp")


def _convention_base(asset_locale: str, serie_id: str, set_id: str, local_id: str) -> str:
    """Base d'asset TCGdex d'une carte selon la convention du CDN (casse d'origine en japonais)."""
    if asset_locale == "ja":
        return f"{_TCGDEX_ASSETS_BASE}/ja/{serie_id}/{set_id}/{quote(local_id, safe='')}"
    return f"{_TCGDEX_ASSETS_BASE}/{asset_locale}/{serie_id.lower()}/{set_id.lower()}/{quote(local_id, safe='')}"


def _asset_exists(url: str) -> bool:
    """Vrai quand l'asset répond 200 (requête HEAD)."""
    try:
        response = _http.head(url)
    except httpx.HTTPError:
        return False
    return response.status_code == 200


def _assets_exist(urls: list[str]) -> list[bool]:
    """Existence de chaque asset, vérifiée en parallèle et dans l'ordre des URLs."""
    if not urls:
        return []
    with ThreadPoolExecutor(max_workers=min(_PROBE_WORKERS, len(urls))) as pool:
        return list(pool.map(_asset_exists, urls))


def _probe_tcgdex_convention(
    asset_locale: str, serie_id: str, set_id: str, local_ids: list[str]
) -> dict[str, CardImageUrls]:
    """Scans présents sur le CDN TCGdex sans être listés par l'API ; échantillon d'abord, puis chaque carte."""
    if not local_ids:
        return {}
    step = max(1, len(local_ids) // _PROBE_SAMPLE_SIZE)
    sample = local_ids[::step][:_PROBE_SAMPLE_SIZE]
    bases = {local_id: _convention_base(asset_locale, serie_id, set_id, local_id) for local_id in local_ids}
    if not any(_assets_exist([f"{bases[local_id]}/low.webp" for local_id in sample])):
        return {}
    exists = _assets_exist([f"{bases[local_id]}/low.webp" for local_id in local_ids])
    return {local_id: _tcgdex_urls(bases[local_id]) for local_id, ok in zip(local_ids, exists, strict=True) if ok}


def _probe_limitless_english(set_id: str, local_ids: list[str]) -> dict[str, CardImageUrls]:
    """Scans Limitless des promos et énergies récentes que ni TCGdex ni pokemontcg.io n'ont encore."""
    code = _LIMITLESS_ENGLISH_CODES.get(set_id)
    numbered = [local_id for local_id in local_ids if local_id.isdigit()]
    if not code or not numbered:
        return {}
    bases = {local_id: f"{_LIMITLESS_CARDS_BASE}/{code}/{code}_{int(local_id):03d}_R_EN" for local_id in numbered}
    exists = _assets_exist([f"{bases[local_id]}_SM.png" for local_id in numbered])
    return {
        local_id: CardImageUrls(low=f"{bases[local_id]}_SM.png", high=f"{bases[local_id]}_LG.png")
        for local_id, ok in zip(numbered, exists, strict=True)
        if ok
    }


def pokemontcg_set_id(set_id: str) -> str:
    """Identifiant pokemontcg.io d'un set TCGdex (``sv03.5`` donne ``sv3pt5``, ``me01`` donne ``me1``)."""
    mapped = _POKEMONTCG_SET_IDS.get(set_id)
    if mapped:
        return mapped
    match = _SET_ID_RULE_RE.match(set_id)
    if not match:
        return set_id
    prefix, number, half, rest = match.groups()
    return f"{prefix}{number}{'pt5' if half else ''}{rest}"


def _pokemontcg_cards(pokemontcg_id: str) -> list[dict[str, Any]]:
    """Cartes d'un set pokemontcg.io (JSON public, mis en cache), vide si le set n'existe pas."""
    cache_key = f"pokemontcg:{pokemontcg_id}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached
    cards: list[dict[str, Any]] = []
    try:
        response = _http.get(f"{_POKEMONTCG_CARDS_BASE}/{quote(pokemontcg_id, safe='')}.json", timeout=20.0)
        payload = response.json() if response.status_code == 200 else []
        cards = [card for card in payload if isinstance(card, dict)] if isinstance(payload, list) else []
    except (httpx.HTTPError, ValueError):
        cards = []
    _cache.set(cache_key, cards)
    return cards


def _normalize_number(number: object) -> str:
    """Numéro comparable entre sources : « TG01 » = « TG1 », « 001 » = « 1 »."""
    raw = str(number or "").strip().upper()
    match = _CARD_NUMBER_RE.match(raw)
    return f"{match.group(1)}{match.group(2)}{match.group(3)}" if match else raw


def _normalize_name(name: object) -> str:
    """Nom comparable entre sources : minuscules sans accents ni ponctuation, sans le niveau « LV.X »."""
    decomposed = unicodedata.normalize("NFKD", str(name or "").lower())
    return _NON_ALNUM_RE.sub("", _LEVEL_X_RE.sub("", decomposed))


def _pokemontcg_urls(card: dict[str, Any] | None) -> CardImageUrls | None:
    """URLs d'une carte pokemontcg.io (``images.small`` / ``images.large``)."""
    images = card.get("images") if isinstance(card, dict) else None
    if not isinstance(images, dict):
        return None
    small = images.get("small")
    large = images.get("large")
    if not isinstance(small, str) or not small:
        return None
    return CardImageUrls(low=small, high=large if isinstance(large, str) and large else small)


def _match_pokemontcg(
    set_id: str, local_ids: list[str], english_names: dict[str, str]
) -> dict[str, CardImageUrls]:
    """Associe des cartes TCGdex à pokemontcg.io, par numéro quand la numérotation concorde, sinon par nom."""
    if not local_ids or not english_names:
        return {}
    cards = _pokemontcg_cards(pokemontcg_set_id(set_id))
    if not cards:
        return {}

    by_number: dict[str, dict[str, Any]] = {}
    by_name: dict[str, list[dict[str, Any]]] = {}
    for card in cards:
        by_number.setdefault(_normalize_number(card.get("number")), card)
        by_name.setdefault(_normalize_name(card.get("name")), []).append(card)
    for same_name_cards in by_name.values():
        same_name_cards.sort(key=lambda card: _normalize_number(card.get("number")).zfill(6))

    # Collection de rééditions (numéros d'origine) ou set différent : les numéros ne se correspondent pas.
    compared = [
        (local_id, name) for local_id, name in english_names.items() if _normalize_number(local_id) in by_number
    ]
    agreeing = sum(
        1 for local_id, name in compared if _normalize_name(by_number[_normalize_number(local_id)].get("name")) == name
    )
    numbering_agrees = len(compared) >= 0.8 * len(by_number) and agreeing >= 0.5 * max(1, len(compared))

    if numbering_agrees:
        numbered = {local_id: _pokemontcg_urls(by_number.get(_normalize_number(local_id))) for local_id in local_ids}
        return {local_id: urls for local_id, urls in numbered.items() if urls}

    # Par nom : les homonymes (deux moitiés d'une carte LÉGENDE) se répartissent dans l'ordre des numéros.
    wanted = set(local_ids)
    found: dict[str, CardImageUrls] = {}
    used_per_name: dict[str, int] = {}
    for local_id in sorted(english_names, key=lambda value: _normalize_number(value).zfill(6)):
        name = english_names[local_id]
        queue = by_name.get(name, [])
        index = used_per_name.get(name, 0)
        used_per_name[name] = index + 1
        urls = _pokemontcg_urls(queue[index]) if index < len(queue) else None
        if local_id in wanted and urls:
            found[local_id] = urls
    return found
