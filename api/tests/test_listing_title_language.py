"""Titre d'annonce : la langue vient de la carte physique quand on la connaît, même avec un nom écrit en lettres latines."""

from __future__ import annotations

from typing import Any

from app_types.groq_vision import GroqVisionCardCollectorResult
from services.scan_service import build_title_and_description

_CARD_INFO: dict[str, Any] = {"set_name": "Mega Symphonia", "set_code": "M1S", "card_number": "070", "rarity": ""}


def _named(printed_name: str) -> GroqVisionCardCollectorResult:
    return {
        "set_code": "M1S",
        "card_number": "070",
        "pokemon_name": printed_name,
        "pokemon_name_english": "Helioptile",
        "pokemon_name_french": "Galvaran",
    }


def test_a_japanese_card_shown_with_its_latin_name_is_titled_japanese() -> None:
    title, description = build_title_and_description(_named("Galvaran"), _CARD_INFO, physical_language="ja")

    assert title.endswith("- Pokémon Japonais")
    assert description.startswith("Langue : Japonais")


def test_a_french_card_is_titled_french() -> None:
    title, _description = build_title_and_description(_named("Galvaran"), _CARD_INFO, physical_language="fr")

    assert title.endswith("- Pokémon Français")


def test_without_the_card_language_the_printed_name_still_decides() -> None:
    french_title, _ = build_title_and_description(_named("Galvaran"), _CARD_INFO)
    japanese_title, _ = build_title_and_description(_named("エリキテル"), _CARD_INFO)

    assert french_title.endswith("- Pokémon Français")
    assert japanese_title.endswith("- Pokémon Japonais")
