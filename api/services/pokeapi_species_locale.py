"""Read-only helpers for PokéAPI ``pokemon-species`` (localized names)."""

from __future__ import annotations

import json
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

POKEAPI_SPECIES_URL = "https://pokeapi.co/api/v2/pokemon-species"
FETCH_TIMEOUT_SEC = 8.0
FRENCH_LANGUAGE_NAME = "fr"


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


def fetch_french_species_name(english_species_name: str) -> str | None:
    """
    Fetch the official French species name for an English species name, or ``None`` on failure.

    Args:
        english_species_name: English Pokémon name as used in PokéAPI slugs (e.g. ``Ivysaur``).
    """
    trimmed = english_species_name.strip()
    if trimmed == "":
        return None
    slug = english_species_name_to_poke_api_slug(trimmed)
    if slug == "":
        return None
    url = f"{POKEAPI_SPECIES_URL}/{quote(slug, safe='')}"
    try:
        req = Request(url, headers={"Accept": "application/json"})
        with urlopen(req, timeout=FETCH_TIMEOUT_SEC) as resp:
            raw = resp.read().decode("utf-8")
        payload = cast(dict[str, Any], json.loads(raw))
        names = payload.get("names")
        if not isinstance(names, list):
            return None
        for entry in names:
            if not isinstance(entry, dict):
                continue
            lang_obj = entry.get("language")
            lang_name = lang_obj.get("name") if isinstance(lang_obj, dict) else None
            label = entry.get("name")
            if lang_name == FRENCH_LANGUAGE_NAME and isinstance(label, str):
                stripped = label.strip()
                if stripped:
                    return stripped
        return None
    except (OSError, HTTPError, URLError, json.JSONDecodeError, TimeoutError):
        return None
