"""Build listing title and description for scan / article flows."""

from __future__ import annotations

from typing import Any

from app_types.groq_vision import GroqVisionCardCollectorResult


def build_title_and_description(
    ocr: GroqVisionCardCollectorResult,
    card_info: dict[str, Any] | None,
    condition_label: str = "Near Mint",
) -> tuple[str, str]:
    """
    Build a marketplace title and French description from OCR + optional PokéWallet card payload.

    Example title pattern:
    ``Herbizarre AR (M1L 065) Mega Brave - Ivysaur - 065/063 NM - Pokémon Japonais``
    """
    ci = card_info or {}
    name_fr = (ocr.get("pokemon_name_french") or "").strip()
    name_en = (ocr.get("pokemon_name_english") or "").strip()
    printed = (ocr.get("pokemon_name") or "").strip()
    display_fr = name_fr or printed or name_en or "Pokémon"

    set_code = (ocr.get("set_code") or ci.get("set_code") or "").strip()
    card_number = (ocr.get("card_number") or ci.get("card_number") or "").strip()
    set_name = (ci.get("set_name") or ocr.get("set_name_english") or "").strip()
    variant = (ocr.get("card_variant_label") or "").strip()

    rarity = (ci.get("rarity") or ocr.get("rarity_english") or "").strip()

    parts: list[str] = [display_fr]
    if variant:
        parts.append(variant)
    if set_code and card_number:
        parts.append(f"({set_code} {card_number})")
    elif set_code:
        parts.append(f"({set_code})")
    if set_name:
        parts.append(set_name)
    if name_en and name_en != display_fr:
        parts.append(f"- {name_en}")
    if card_number:
        parts.append(f"- {card_number}")
    parts.append(condition_label)
    parts.append("Pokémon")

    title = " ".join(p for p in parts if p).replace("  ", " ").strip()

    lines = [
        "Langue : Japonais",
    ]
    if set_name:
        lines.append(f"Série : {set_name}")
    lines.append(f"Nom : {display_fr}" + (f" / {name_en}" if name_en and name_en != display_fr else ""))
    if card_number:
        lines.append(f"Numéro : {card_number}" + (f" {rarity}" if rarity else ""))
    lines.append(f"État : {condition_label} / Mint")

    description = "\n".join(lines)
    return title, description
