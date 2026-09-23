"""Build listing fields from TCGdex card data + optional PokéWallet pricing."""

from __future__ import annotations

from typing import Any

from app_types.groq_vision import GroqVisionCardCollectorResult
from app_types.tcgdex import TcgdexCardDetail, TcgdexSetDetail
from services import pricing_service
from services.collection_card_lookup_service import fetch_card_for_collection
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
    try:
        set_detail = client.get_set("en", set_id)
        card_en = client.get_card("en", tcgdx_card_id)
    except (RuntimeError, ValueError):
        # Set japonais seulement (SV4M, M1S…) : TCGdex n'a pas de fiche anglaise pour cette carte.
        return _preview_without_english_card(
            tcgdx_card_id=tcgdx_card_id,
            set_id=set_id,
            local_raw=local_raw,
            pokewallet_set_code=pokewallet_set_code,
            browse_locale=browse_locale,
            client=client,
        )
    resolved_code = (pokewallet_set_code or "").strip().upper() or infer_pokewallet_set_code(set_detail)
    if not resolved_code:
        return {
            "error": "Could not infer PokéWallet set_code from TCGdex set; pass pokewallet_set_code explicitly.",
            "tcgdx_card_id": tcgdx_card_id,
        }

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

    image_base = card_en.get("image")
    return _preview_payload(
        tcgdx_card_id=tcgdx_card_id,
        set_id=set_id,
        local_raw=local_raw,
        resolved_code=resolved_code,
        number_pw=number_pw,
        name_en=name_en,
        name_fr=name_fr,
        name_ja=name_ja,
        set_name_en=set_name_en,
        rarity=rarity,
        image_base=image_base if isinstance(image_base, str) else None,
        browse_locale=browse_locale,
    )


def _preview_without_english_card(
    *,
    tcgdx_card_id: str,
    set_id: str,
    local_raw: str,
    pokewallet_set_code: str | None,
    browse_locale: str | None,
    client: TcgdexClientService,
) -> dict[str, Any]:
    """
    Aperçu d'une carte sans fiche anglaise sur TCGdex (sets japonais) : métadonnées multi-langue via la
    résolution de l'ajout en collection (garde-fou dexId compris) plutôt qu'une lecture anglaise en dur.
    """
    locale = (browse_locale or "").strip().lower()
    meta = fetch_card_for_collection(
        tcgdex_card_id=tcgdx_card_id,
        physical_language=locale if locale in SUPPORTED_LOCALES else "ja",
        tcgdex=client,
    )
    image_low = meta.get("image_url")
    image_base = image_low[: -len("/low.webp")] if isinstance(image_low, str) and image_low.endswith("/low.webp") else None
    name_en = str(meta.get("card_name_en") or "")
    market_price = meta.get("market_price_eur")
    return _preview_payload(
        tcgdx_card_id=tcgdx_card_id,
        set_id=set_id,
        local_raw=local_raw,
        resolved_code=(pokewallet_set_code or "").strip().upper() or str(meta.get("set_code") or set_id.upper()),
        number_pw=str(meta["card_number"]),
        name_en=name_en,
        name_fr=str(meta.get("card_name_fr") or name_en),
        name_ja=meta.get("card_name_ja"),
        set_name_en=str(meta.get("set_name") or ""),
        rarity=str(meta.get("rarity") or ""),
        image_base=image_base,
        browse_locale=browse_locale,
        fallback_cardmarket_eur=float(market_price) if isinstance(market_price, (int, float)) else None,
    )


def _preview_payload(
    *,
    tcgdx_card_id: str,
    set_id: str,
    local_raw: str,
    resolved_code: str,
    number_pw: str,
    name_en: str,
    name_fr: str,
    name_ja: str | None,
    set_name_en: str,
    rarity: str,
    image_base: str | None,
    browse_locale: str | None,
    fallback_cardmarket_eur: float | None = None,
) -> dict[str, Any]:
    """
    Titre + description d'annonce, prix et image HD d'une carte à partir de ses faits TCGdex.
    ``fallback_cardmarket_eur`` sert de cote quand la recherche de prix par set/numéro ne répond pas.
    """
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
    cardmarket_eur = pricing.get("cardmarket_eur")
    average_price = pricing.get("average_price")
    if cardmarket_eur is None and fallback_cardmarket_eur is not None:
        cardmarket_eur = fallback_cardmarket_eur
        average_price = average_price if average_price is not None else fallback_cardmarket_eur
    image_url_high: str | None = None
    if image_base and image_base.strip():
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
            "cardmarket_eur": cardmarket_eur,
            "tcgplayer_usd": pricing.get("tcgplayer_usd"),
            "average_price_eur": average_price,
            "error": pricing.get("error"),
        },
        "image_url_high": image_url_high,
        "error": None,
    }
