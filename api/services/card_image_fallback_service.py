"""
Scans de repli pour les cartes que TCGdex liste sans ``image`` (galeries, promos, McDonald's, collections classiques…).

Sources, de la plus fidèle à la plus lointaine : CDN TCGdex par convention dans la langue demandée, images
anglaises TCGdex (listées ou par convention), données publiques pokemontcg.io (numéro imprimé ou nom anglais),
CDN Limitless pour les promos et énergies récentes, puis scans TCGplayer (via TCGCSV) pour les kits dresseur,
promos McDonald's et extensions japonaises que personne d'autre n'illustre. Les McDonald's exclusifs à la France
reprennent en dernier recours la carte d'origine de même nom et même illustrateur.
"""

from __future__ import annotations

import json
import re
import threading
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote

import httpx

from services.tcgdex_client_service import DEFAULT_BASE_URL, TcgdexClientService

_USER_AGENT = "GoupixDex/1.0 (+catalog; card-images)"
_TCGDEX_ASSETS_BASE = "https://assets.tcgdex.net"
_POKEMONTCG_CARDS_BASE = "https://raw.githubusercontent.com/PokemonTCG/pokemon-tcg-data/master/cards/en"
_LIMITLESS_CARDS_BASE = "https://limitlesstcg.nyc3.cdn.digitaloceanspaces.com/tpci"
_TCGCSV_BASE = "https://tcgcsv.com/tcgplayer"
_TCGPLAYER_ENGLISH_CATEGORY = 3
_TCGPLAYER_JAPANESE_CATEGORY = 85
_SPECIES_ENGLISH_NAMES_PATH = Path(__file__).resolve().parent.parent / "data" / "pokemon_species_en.json"
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
    "exu": "ex10",
    "hgssp": "hsp",
    "sm3.5": "sm35",
    "sm7.5": "sm75",
    "swsh4.5sv": "swsh45sv",
    "tk-ex-latia": "tk1a",
    "tk-ex-latio": "tk1b",
    "tk-ex-m": "tk2b",
    "tk-ex-p": "tk2a",
}

# Groupes TCGplayer anglais des sets TCGdex qu'aucune autre source n'illustre (kits dresseur, McDonald's, promos).
_TCGPLAYER_ENGLISH_GROUPS: dict[str, int] = {
    "2023sv": 23306,
    "2024sv": 24163,
    "ecard2": 1397,
    "mep": 24451,
    "mfb": 23330,
    "miscp": 2374,
    "svp": 22872,
    "swshp": 2545,
    "tk-bw-e": 1538,
    "tk-bw-z": 1538,
    "tk-dp-l": 1541,
    "tk-dp-m": 1541,
    "tk-hs-g": 1540,
    "tk-hs-r": 1540,
    "tk-sm-l": 2069,
    "tk-sm-r": 2069,
    "tk-xy-b": 1533,
    "tk-xy-latia": 1536,
    "tk-xy-latio": 1536,
    "tk-xy-n": 1532,
    "tk-xy-p": 1796,
    "tk-xy-su": 1796,
    "tk-xy-sy": 1532,
    "tk-xy-w": 1533,
    "xya": 1938,
}

# Groupes TCGplayer japonais dont le nom ne commence pas par le code TCGdex (extensions de 1996 à 2007, Start Deck 100).
_TCGPLAYER_JAPANESE_GROUPS: dict[str, int] = {
    "E1": 23730,
    "E2": 23731,
    "E3": 23732,
    "E4": 23733,
    "E5": 23734,
    "MC": 24567,
    "PCG1": 24117,
    "PCG2": 24114,
    "PCG3": 24135,
    "PCG4": 24103,
    "PCG5": 24101,
    "PCG6": 24085,
    "PCG7": 24084,
    "PCG8": 24099,
    "PCG9": 24090,
    "PCG10": 24053,
    "PMCG1": 23721,
    "PMCG2": 23722,
    "PMCG3": 23723,
    "PMCG4": 23724,
    "PMCG5": 23725,
    "PMCG6": 23726,
    "VS1": 24180,
    "neo1": 23727,
    "neo2": 23728,
    "neo3": 23720,
    "neo4": 23729,
    "web1": 24141,
}

# Collections McDonald's exclusives à la France : réimpressions de cartes existantes, absentes de TCGplayer.
_REPRINT_ARTWORK_SETS: frozenset[str] = frozenset({"2013bw", "2018sm-fr", "2019sm-fr"})
# Sets TCG Pocket (A1, A3a, P-A…) : même illustration parfois, mais pas des cartes physiques.
_POCKET_SET_ID_RE = re.compile(r"^(?:[AB]\d+[a-z]?|P-[AB])$")

# Préfixes des noms japonais TCGdex (dont les graphies approximatives des Neo), écrits en anglais chez TCGplayer.
_JAPANESE_NAME_PREFIXES: dict[str, str] = {
    "わるい": "Dark ",
    "ダーク": "Dark ",
    "暗い": "Dark ",
    "やさしい": "Light ",
    "ライト": "Light ",
    "軽い": "Light ",
    "ひかる": "Shining ",
    "ロケット団の": "Rocket's ",
    "R団の": "Rocket's ",
    "エリカの": "Erika's ",
    "カスミの": "Misty's ",
    "タケシの": "Brock's ",
    "マチスの": "Lt. Surge's ",
    "ナツメの": "Sabrina's ",
    "キョウの": "Koga's ",
    "カツラの": "Blaine's ",
    "サカキの": "Giovanni's ",
    "ジョバンニの": "Giovanni's ",
    "イマクニ？の": "Imakuni?'s ",
}

_JAPANESE_ENERGY_TYPES: dict[str, str] = {
    "草": "Grass",
    "炎": "Fire",
    "水": "Water",
    "雷": "Lightning",
    "超": "Psychic",
    "闘": "Fighting",
    "悪": "Darkness",
    "鋼": "Metal",
}

_SET_ID_RULE_RE = re.compile(r"^([a-z]+)0*(\d+)(\.5)?(.*)$", re.IGNORECASE)
_CARD_NUMBER_RE = re.compile(r"^([A-Z]*)0*(\d+)([A-Z]*)$")
_LEVEL_X_RE = re.compile(r"\blv\.?\s*x\b")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_JAPANESE_ENERGY_RE = re.compile(r"基本(.)エネルギー")
_TCGPLAYER_NAME_SUFFIX_RE = re.compile(r"\s*\(.*?\)|\s+-\s+\S+$")

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


@dataclass(frozen=True)
class _TcgplayerCard:
    """Carte d'un groupe TCGplayer : numéro et nom comparables, variante d'impression, scans."""

    number: str
    name: str
    is_variant: bool
    urls: CardImageUrls


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

    if locale == "ja":
        found.update(_match_tcgplayer(locale, set_detail, _still_missing(missing, found), {}))
    else:
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
        found.update(_match_tcgplayer(locale, set_detail, _still_missing(missing, found), english_names))
        if set_id in _REPRINT_ARTWORK_SETS:
            found.update(_match_reprint_artwork(locale, set_detail, _still_missing(missing, found)))

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
    """Numéro comparable entre sources : « TG01 » = « TG1 », « 001 » = « 1 », « %3F » = « ? »."""
    raw = unquote(str(number or "")).strip().upper()
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


def _tcgplayer_json(path: str) -> list[dict[str, Any]]:
    """Résultats d'un export TCGCSV (mis en cache), vides quand il ne répond pas."""
    cache_key = f"tcgcsv:{path}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached
    results: list[dict[str, Any]] = []
    try:
        response = _http.get(f"{_TCGCSV_BASE}/{path}", timeout=30.0)
        payload = response.json() if response.status_code == 200 else {}
        raw = payload.get("results") if isinstance(payload, dict) else None
        results = [row for row in raw if isinstance(row, dict)] if isinstance(raw, list) else []
    except (httpx.HTTPError, ValueError):
        results = []
    _cache.set(cache_key, results)
    return results


def _tcgplayer_group(locale: str, set_id: str) -> tuple[int, int] | None:
    """Catégorie et groupe TCGplayer d'un set TCGdex, ``None`` quand TCGplayer ne le couvre pas."""
    if locale != "ja":
        english_group = _TCGPLAYER_ENGLISH_GROUPS.get(set_id)
        return (_TCGPLAYER_ENGLISH_CATEGORY, english_group) if english_group else None
    japanese_group = _TCGPLAYER_JAPANESE_GROUPS.get(set_id)
    if japanese_group:
        return _TCGPLAYER_JAPANESE_CATEGORY, japanese_group
    # Extensions récentes : TCGplayer préfixe le nom du groupe par le code du set (« S8: Fusion Arts »).
    code = re.compile(rf"^{re.escape(set_id)}[:\s]", re.IGNORECASE)
    groups = _tcgplayer_json(f"{_TCGPLAYER_JAPANESE_CATEGORY}/groups")
    matches = [group["groupId"] for group in groups if code.match(str(group.get("name") or ""))]
    return (_TCGPLAYER_JAPANESE_CATEGORY, matches[0]) if len(matches) == 1 else None


def _tcgplayer_number(printed_number: str) -> str:
    """Numéro comparable d'une carte TCGplayer (« 116/100 » donne « 116 »), vide quand elle n'en a pas."""
    return _normalize_number(printed_number.split("/")[0]) if printed_number else ""


def _tcgplayer_name(name: str) -> str:
    """Nom comparable à TCGdex : sans numéro ni mention entre parenthèses, « Nidoran♂ » écrit « Nidoran M »."""
    readable = _TCGPLAYER_NAME_SUFFIX_RE.sub("", name.replace("♂", " M").replace("♀", " F"))
    return _normalize_name(readable)


def _tcgplayer_cards(category: int, group_id: int) -> list[_TcgplayerCard]:
    """Cartes illustrées d'un groupe TCGplayer, dans l'ordre de l'export."""
    cards: list[_TcgplayerCard] = []
    for product in _tcgplayer_json(f"{category}/{group_id}/products"):
        image = product.get("imageUrl")
        if not isinstance(image, str) or not image.endswith("_200w.jpg"):
            continue
        extended = {
            str(field.get("name")): str(field.get("value"))
            for field in product.get("extendedData") or []
            if isinstance(field, dict)
        }
        name = str(product.get("name") or "")
        cards.append(
            _TcgplayerCard(
                number=_tcgplayer_number(extended.get("Number", "")),
                name=_tcgplayer_name(name),
                is_variant="(" in name,
                urls=CardImageUrls(
                    low=image.replace("_200w.jpg", "_400w.jpg"),
                    high=image.replace("_200w.jpg", "_in_1000x1000.jpg"),
                ),
            )
        )
    return cards


def _pick_tcgplayer_card(candidates: list[_TcgplayerCard], english_name: str | None) -> _TcgplayerCard | None:
    """Carte TCGplayer d'un numéro : le nom tranche entre homonymes (moitiés d'un kit), jamais au hasard."""
    if len(candidates) <= 1:
        return candidates[0] if candidates else None
    if english_name:
        return next((card for card in candidates if card.name == english_name), None)
    return next((card for card in candidates if not card.is_variant), candidates[0])


@cache
def _species_english_names() -> dict[int, str]:
    """Noms anglais des espèces par numéro de Pokédex national (``data/pokemon_species_en.json``)."""
    payload = json.loads(_SPECIES_ENGLISH_NAMES_PATH.read_text(encoding="utf-8"))
    return {int(dex): str(name) for dex, name in payload.items()}


def _japanese_english_name(japanese_name: str, dex_id: int | None) -> str | None:
    """Nom anglais TCGplayer d'une carte japonaise : énergie de base, ou préfixe (Dark, Rocket's…) + espèce."""
    energy = _JAPANESE_ENERGY_RE.fullmatch(japanese_name)
    if energy and energy.group(1) in _JAPANESE_ENERGY_TYPES:
        return f"{_JAPANESE_ENERGY_TYPES[energy.group(1)]} Energy"
    species = _species_english_names().get(dex_id) if dex_id is not None else None
    if species is None:
        return None
    prefix = next((english for japanese, english in _JAPANESE_NAME_PREFIXES.items() if japanese_name.startswith(japanese)), "")
    return f"{prefix}{species}"


def _japanese_card_english_names(set_detail: dict[str, Any], local_ids: list[str]) -> dict[str, str]:
    """Noms anglais comparables des cartes japonaises, d'après le numéro de Pokédex de chaque fiche TCGdex."""
    cards_by_local_id = {
        str(card["localId"]): card
        for card in set_detail.get("cards") or []
        if isinstance(card, dict) and isinstance(card.get("localId"), str) and isinstance(card.get("id"), str)
    }
    wanted = [cards_by_local_id[local_id] for local_id in local_ids if local_id in cards_by_local_id]
    if not wanted:
        return {}

    def dex_id_of(card: dict[str, Any]) -> int | None:
        """Premier numéro de Pokédex de la fiche japonaise, ``None`` pour un dresseur ou une fiche absente."""
        # Client partagé plutôt que TcgdexClientService : une centaine de fiches sur des connexions déjà ouvertes.
        try:
            response = _http.get(f"{DEFAULT_BASE_URL}/ja/cards/{quote(str(card['id']), safe='')}")
            dex_ids = response.json().get("dexId") if response.status_code == 200 else None
        except (httpx.HTTPError, ValueError, AttributeError):
            return None
        return dex_ids[0] if isinstance(dex_ids, list) and dex_ids and isinstance(dex_ids[0], int) else None

    with ThreadPoolExecutor(max_workers=min(_PROBE_WORKERS, len(wanted))) as pool:
        dex_ids = list(pool.map(dex_id_of, wanted))
    names: dict[str, str] = {}
    for card, dex_id in zip(wanted, dex_ids, strict=True):
        english = _japanese_english_name(str(card.get("name") or ""), dex_id)
        if english:
            names[str(card["localId"])] = _tcgplayer_name(english)
    return names


def _match_tcgplayer(
    locale: str, set_detail: dict[str, Any], local_ids: list[str], english_names: dict[str, str]
) -> dict[str, CardImageUrls]:
    """Scans TCGplayer des cartes restantes : par numéro, sinon par nom anglais (extensions japonaises non numérotées)."""
    group = _tcgplayer_group(locale, str(set_detail.get("id") or "")) if local_ids else None
    if group is None:
        return {}
    cards = _tcgplayer_cards(*group)
    by_number: dict[str, list[_TcgplayerCard]] = {}
    for card in cards:
        if card.number:
            by_number.setdefault(card.number, []).append(card)

    found: dict[str, CardImageUrls] = {}
    # Numérotation fiable seulement si elle couvre le groupe : Neo 4 n'a qu'une carte numérotée sur 113.
    if 2 * sum(len(numbered) for numbered in by_number.values()) >= len(cards):
        for local_id in local_ids:
            picked = _pick_tcgplayer_card(by_number.get(_normalize_number(local_id), []), english_names.get(local_id))
            if picked is not None:
                found[local_id] = picked.urls
        return found

    names = english_names or _japanese_card_english_names(set_detail, local_ids)
    by_name: dict[str, list[_TcgplayerCard]] = {}
    for card in cards:
        by_name.setdefault(card.name, []).append(card)
    for local_id in local_ids:
        # Homonymes (deux Pikachu d'un deck) attribués dans l'ordre de l'export.
        queue = by_name.get(names.get(local_id, ""), [])
        if queue:
            found[local_id] = queue.pop(0).urls
    return found


def _tcgdex_json(path: str, params: dict[str, str] | None = None) -> Any:
    """Réponse JSON de l'API TCGdex lue sur le client partagé, ``None`` en cas d'échec."""
    try:
        response = _http.get(f"{DEFAULT_BASE_URL}/{path}", params=params)
    except httpx.HTTPError:
        return None
    if response.status_code != 200:
        return None
    try:
        return response.json()
    except ValueError:
        return None


def _original_artwork(locale: str, set_id: str, card: dict[str, Any]) -> CardImageUrls | None:
    """Scan de la carte d'origine d'une réimpression : même nom, même illustrateur, hors de ce set et de TCG Pocket."""
    detail = _tcgdex_json(f"{locale}/cards/{quote(str(card['id']), safe='')}")
    illustrator = detail.get("illustrator") if isinstance(detail, dict) else None
    if not isinstance(illustrator, str) or not illustrator:
        return None
    matches = _tcgdex_json(f"{locale}/cards", {"name": f"eq:{card.get('name')}", "illustrator": f"eq:{illustrator}"})
    for match in matches if isinstance(matches, list) else []:
        match_id = str(match.get("id") or "") if isinstance(match, dict) else ""
        match_set = match_id.rsplit("-", 1)[0]
        image = match.get("image") if isinstance(match, dict) else None
        if isinstance(image, str) and image and match_set != set_id and not _POCKET_SET_ID_RE.match(match_set):
            return _tcgdex_urls(image)
    return None


def _match_reprint_artwork(locale: str, set_detail: dict[str, Any], local_ids: list[str]) -> dict[str, CardImageUrls]:
    """Scans d'origine des réimpressions McDonald's françaises encore sans image."""
    set_id = str(set_detail.get("id") or "")
    wanted = [
        card
        for card in set_detail.get("cards") or []
        if isinstance(card, dict) and card.get("localId") in local_ids and isinstance(card.get("id"), str)
    ]
    if not wanted:
        return {}
    with ThreadPoolExecutor(max_workers=min(_PROBE_WORKERS, len(wanted))) as pool:
        artworks = list(pool.map(lambda card: _original_artwork(locale, set_id, card), wanted))
    return {str(card["localId"]): urls for card, urls in zip(wanted, artworks, strict=True) if urls is not None}
