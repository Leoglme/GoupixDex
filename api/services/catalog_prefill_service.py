"""Build listing fields from TCGdex card data + optional PokéWallet pricing."""

from __future__ import annotations

from typing import Any

from app_types.groq_vision import GroqVisionCardCollectorResult
from app_types.tcgdex import TcgdexCardDetail, TcgdexSetDetail
from services import pricing_service
from services.scan_service import build_title_and_description
from services.species_locale_names_service import fetch_species_locale_names
from services.tcgdex_client_service import (
    SUPPORTED_LOCALES,
    TcgdexClientService,
    infer_pokewallet_set_code,
    normalize_card_number_for_pokewallet,
    split_tcgdex_card_id,
    tcgdx_image_url_high,
)


def _pick_display_pokemon_name(
    browse_locale: str | None,
    name_en: str,
    name_fr: str,
    name_ja: str | None,
) -> str:
    """Prefer the catalog UI locale, then fall back so the article form matches the picker."""
    ja_s = (name_ja or "").strip()
    pool = {"en": name_en.strip(), "fr": name_fr.strip(), "ja": ja_s}
    raw = (browse_locale or "").strip().lower()
    loc = raw if raw in SUPPORTED_LOCALES else ""
    if not loc:
        order: tuple[str, ...] = ("en", "fr", "ja")
    elif loc == "ja":
        order = ("ja", "fr", "en")
    elif loc == "fr":
        order = ("fr", "en", "ja")
    else:
        order = ("en", "fr", "ja")
    for key in order:
        v = pool.get(key, "")
        if v:
            return v
    return name_en or name_fr or "Pokémon"


def build_catalog_card_preview(
    *,
    tcgdx_card_id: str,
    pokewallet_set_code: str | None = None,
    browse_locale: str | None = None,
    tcgdex: TcgdexClientService | None = None,
) -> dict[str, Any]:
    """
    Load EN/FR/JA card names from TCGdex, infer PokéWallet ``set_code`` + ``card_number``,
    run pricing lookup, and build title/description compatible with ``ArticleForm``.

    ``browse_locale`` controls which localized Pokémon name is suggested first in
    ``display_pokemon_name`` (``fr`` | ``en`` | ``ja``).
    """
    client = tcgdex or TcgdexClientService()
    set_id, local_raw = split_tcgdex_card_id(tcgdx_card_id)
    set_detail = client.get_set("en", set_id)
    resolved_code = (pokewallet_set_code or "").strip().upper() or infer_pokewallet_set_code(set_detail)
    if not resolved_code:
        return {
            "error": "Could not infer PokéWallet set_code from TCGdex set; pass pokewallet_set_code explicitly.",
            "tcgdx_card_id": tcgdx_card_id,
        }

    card_en = client.get_card("en", tcgdx_card_id)
    try:
        card_fr = client.get_card("fr", tcgdx_card_id)
    except (RuntimeError, ValueError):
        card_fr = card_en
    try:
        card_ja = client.get_card("ja", tcgdx_card_id)
    except (RuntimeError, ValueError):
        card_ja = card_en

    name_en = (card_en.get("name") or "").strip()
    name_fr = (card_fr.get("name") or "").strip() or name_en
    number_pw = normalize_card_number_for_pokewallet(local_raw)

    species = fetch_species_locale_names(name_en)
    name_tcgdex_ja = (card_ja.get("name") or "").strip()
    name_ja = name_tcgdex_ja or ((species.japanese or "").strip() or None)

    nested_set = card_en.get("set")
    set_name_en = ""
    if isinstance(nested_set, dict):
        raw_sn = nested_set.get("name")
        if isinstance(raw_sn, str):
            set_name_en = raw_sn.strip()

    rarity = ""
    raw_r = card_en.get("rarity")
    if isinstance(raw_r, str):
        rarity = raw_r.strip()

    display_name = _pick_display_pokemon_name(browse_locale, name_en, name_fr, name_ja)
    ocr: GroqVisionCardCollectorResult = {
        "set_code": resolved_code,
        "card_number": number_pw,
        "pokemon_name": display_name,
        "pokemon_name_english": name_en,
        "pokemon_name_french": name_fr,
        "set_name_english": set_name_en,
        "rarity_english": rarity,
    }
    card_info: dict[str, Any] = {
        "set_name": set_name_en,
        "set_code": resolved_code,
        "card_number": number_pw,
        "rarity": rarity,
    }
    title, description = build_title_and_description(ocr, card_info)
    if name_ja:
        j = str(name_ja).strip()
        if j and j != name_en and j != name_fr:
            description = f"{description}\nNom (JPN) : {j}"

    pricing = pricing_service.fetch_card_prices(resolved_code, number_pw, name_en)
    image_base = card_en.get("image")
    image_url_high: str | None = None
    if isinstance(image_base, str) and image_base.strip():
        image_url_high = tcgdx_image_url_high(image_base.strip())

    return {
        "tcgdx_card_id": tcgdx_card_id,
        "display_pokemon_name": display_name,
        "tcgdex": {
            "names": {"en": name_en, "fr": name_fr, "ja": name_ja},
            "set_id": set_id,
            "local_id": local_raw,
        },
        "pokewallet": {
            "set_code": resolved_code,
            "card_number": number_pw,
        },
        "listing_preview": {
            "title": title,
            "description": description,
            "suggested_price": None,
        },
        "pricing": {
            "cardmarket_eur": pricing.get("cardmarket_eur"),
            "tcgplayer_usd": pricing.get("tcgplayer_usd"),
            "average_price_eur": pricing.get("average_price"),
            "error": pricing.get("error"),
        },
        "image_url_high": image_url_high,
        "error": None,
    }
