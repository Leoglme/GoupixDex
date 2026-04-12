"""Build listing title and description for scan / article flows."""

from __future__ import annotations

import re
from typing import Any

from app_types.groq_vision import GroqVisionCardCollectorResult


def _strip_set_code_prefix_from_expansion_name(set_name: str, set_code: str | None) -> str:
    """Remove a leading ``M1L:`` / ``SV7:`` style prefix when it duplicates ``set_code``."""
    trimmed_name = set_name.strip()
    if not trimmed_name:
        return ""
    trimmed_code = (set_code or "").strip()
    if not trimmed_code:
        return trimmed_name
    escaped = re.escape(trimmed_code)
    pattern = re.compile(rf"^{escaped}\s*:\s*", re.IGNORECASE)
    stripped = pattern.sub("", trimmed_name).strip()
    return stripped if stripped else trimmed_name


def _listing_language_label(ocr: GroqVisionCardCollectorResult) -> str:
    """Français when the printed name matches the French dex name (e.g. French-language card), else Japonais."""
    fr = (ocr.get("pokemon_name_french") or "").strip()
    printed = (ocr.get("pokemon_name") or "").strip()
    if fr and printed and fr == printed:
        return "Français"
    return "Japonais"


def build_title_and_description(
    ocr: GroqVisionCardCollectorResult,
    card_info: dict[str, Any] | None,
    condition_label: str = "Near Mint",
) -> tuple[str, str]:
    """
    Build a marketplace title and French description from OCR + optional PokéWallet card payload.

    Title pattern (nullable fields omitted or shortened as needed)::

        Gloupti / Gulpin sv7 112/102 AR - Stellar Miracle - Pokémon Japonais
    """
    ci = card_info or {}
    name_fr = (ocr.get("pokemon_name_french") or "").strip()
    name_en = (ocr.get("pokemon_name_english") or "").strip()
    printed = (ocr.get("pokemon_name") or "").strip()
    display_fr = name_fr or printed or name_en or "Pokémon"

    set_code = (ocr.get("set_code") or ci.get("set_code") or "").strip()
    card_number = (ocr.get("card_number") or ci.get("card_number") or "").strip()
    set_name_raw = (ci.get("set_name") or ocr.get("set_name_english") or "").strip()
    set_name = _strip_set_code_prefix_from_expansion_name(set_name_raw, set_code)
    variant = (ocr.get("card_variant_label") or "").strip()

    rarity = (ci.get("rarity") or ocr.get("rarity_english") or "").strip()
    lang_label = _listing_language_label(ocr)

    # Title: "Fr / En" + set lower + number + expansion + Pokémon + langue
    if name_fr and name_en:
        name_block = f"{name_fr} / {name_en}"
    elif name_fr:
        name_block = name_fr
    elif name_en:
        name_block = name_en
    else:
        name_block = "Pokémon"

    set_lower = set_code.lower() if set_code else ""
    code_number_variant: list[str] = []
    if set_lower:
        code_number_variant.append(set_lower)
    if card_number:
        code_number_variant.append(card_number)
    if variant:
        code_number_variant.append(variant)
    set_num = " ".join(code_number_variant)

    if set_name and set_num:
        title = f"{name_block} {set_num} - {set_name} - Pokémon {lang_label}"
    elif set_num:
        title = f"{name_block} {set_num} - Pokémon {lang_label}"
    elif set_name:
        title = f"{name_block} - {set_name} - Pokémon {lang_label}"
    else:
        title = f"{name_block} - Pokémon {lang_label}"
    title = title.replace("  ", " ").strip()

    lines = [
        f"Langue : {lang_label}",
    ]
    if set_name_raw:
        lines.append(f"Série : {set_name}")
    lines.append(f"Nom : {display_fr}" + (f" / {name_en}" if name_en and name_en != display_fr else ""))
    if card_number:
        line = f"Numéro : {card_number}"
        if variant:
            line += f" {variant}"
        if rarity:
            line += f" {rarity}"
        lines.append(line)
    elif rarity:
        lines.append(f"Rare : {rarity}")
    lines.append(f"État : {condition_label} / Mint")

    description = "\n".join(lines)
    return title, description
