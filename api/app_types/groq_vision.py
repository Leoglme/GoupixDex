"""Types for Groq vision OCR-style card extraction."""

from typing import Literal, NotRequired, TypedDict

GroqVisionImageMimeType = Literal["image/jpeg", "image/png", "image/webp"]


class GroqVisionExtractOptions(TypedDict, total=False):
    """Optional tuning for Groq vision extraction."""

    temperature: float
    model: str
    include_raw_assistant_json: bool
    resolve_english_name_from_poke_wallet: bool


class GroqVisionCardCollectorResult(TypedDict, total=False):
    """
    Pokémon TCG collector info inferred from a card photo (set code, number, name).
    ``None`` fields mean unreadable or absent per model (not guessed), except fraction parts
    derived from ``card_number`` when possible.
    """

    set_code: str | None
    card_number: str | None
    card_number_numerator: str | None
    card_number_denominator: str | None
    pokemon_name: str | None
    pokemon_name_english: str | None
    pokemon_name_french: str | None
    card_variant_label: str | None
    set_name_english: str | None
    rarity_english: str | None
    raw_assistant_json: NotRequired[str]
