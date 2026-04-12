"""Read-only helpers for PokéAPI ``pokemon-species`` (localized names)."""

from __future__ import annotations

import json
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

POKEAPI_SPECIES_URL = "https://pokeapi.co/api/v2/pokemon-species"
FETCH_TIMEOUT_SEC = 8.0
# PokéAPI may return 403 without a descriptive User-Agent (see https://pokeapi.co/docs/v2#info).
DEFAULT_REQUEST_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "GoupixDex/1.0",
}
FRENCH_LANGUAGE_NAME = "fr"
JAPANESE_KANA_LANGUAGE_NAME = "ja-hrkt"
JAPANESE_LANGUAGE_NAME = "ja"


class SpeciesLocaleNames:
    """French and Japanese species labels from a single PokéAPI ``pokemon-species`` response."""

    __slots__ = ("french", "japanese")

    def __init__(self, french: str | None, japanese: str | None) -> None:
        self.french = french
        self.japanese = japanese


def english_species_name_to_poke_api_slug(english_species_name: str) -> str:
    """
    Map an English TCG-style species label to a PokéAPI species slug (best-effort).

    Args:
        english_species_name: e.g. ``Ivysaur``, ``Mr. Mime``.
    """
    trimmed = english_species_name.strip()
    lower = trimmed.lower()
    no_apostrophe = lower.replace("'", "").replace("'", "")
    no_dots = no_apostrophe.replace(".", "")
    hyphenated = "-".join(no_dots.split())
    return hyphenated.replace("♀", "-f").replace("♂", "-m")


def _pick_name_for_languages(
    names: list[Any],
    preferred_lang_codes: tuple[str, ...],
) -> str | None:
    for code in preferred_lang_codes:
        for entry in names:
            if not isinstance(entry, dict):
                continue
            lang_obj = entry.get("language")
            lang_name = lang_obj.get("name") if isinstance(lang_obj, dict) else None
            label = entry.get("name")
            if lang_name == code and isinstance(label, str):
                stripped = label.strip()
                if stripped:
                    return stripped
    return None


def fetch_species_locale_names(english_species_name: str) -> SpeciesLocaleNames:
    """
    Fetch official French and Japanese (katakana preferred) species names in one HTTP request.

    Args:
        english_species_name: English species label (e.g. ``Ivysaur``) used to build the PokéAPI slug.
    """
    trimmed = english_species_name.strip()
    if trimmed == "":
        return SpeciesLocaleNames(None, None)
    slug = english_species_name_to_poke_api_slug(trimmed)
    if slug == "":
        return SpeciesLocaleNames(None, None)
    url = f"{POKEAPI_SPECIES_URL}/{quote(slug, safe='')}"
    try:
        req = Request(url, headers=DEFAULT_REQUEST_HEADERS)
        with urlopen(req, timeout=FETCH_TIMEOUT_SEC) as resp:
            raw = resp.read().decode("utf-8")
        payload = cast(dict[str, Any], json.loads(raw))
        names = payload.get("names")
        if not isinstance(names, list):
            return SpeciesLocaleNames(None, None)
        fr = _pick_name_for_languages(names, (FRENCH_LANGUAGE_NAME,))
        ja = _pick_name_for_languages(names, (JAPANESE_KANA_LANGUAGE_NAME, JAPANESE_LANGUAGE_NAME))
        return SpeciesLocaleNames(fr, ja)
    except (OSError, HTTPError, URLError, json.JSONDecodeError, TimeoutError):
        return SpeciesLocaleNames(None, None)


def fetch_french_species_name(english_species_name: str) -> str | None:
    """
    Fetch the official French species name for an English species name, or ``None`` on failure.

    Args:
        english_species_name: English Pokémon name as used in PokéAPI slugs (e.g. ``Ivysaur``).
    """
    return fetch_species_locale_names(english_species_name).french
