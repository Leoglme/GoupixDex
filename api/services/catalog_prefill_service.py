"""Build listing fields from TCGdex card data + optional PokéWallet pricing."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

from app_types.groq_vision import GroqVisionCardCollectorResult
from app_types.tcgdex import TcgdexCardDetail, TcgdexSetDetail
from services import pricing_service
from services.card_image_fallback_service import fallback_card_image, has_lettered_number
from services.cardmarket_local_price_service import (
    extract_cardmarket_block,
    extract_tcgplayer_usd,
    resolve_market_price_eur,
)
from services.collection_card_lookup_service import fetch_card_for_collection
from services.price_history_seed_service import synthesized_price_points
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
    # Les quatre lectures TCGdex sont indépendantes : en parallèle, l'aperçu s'ouvre en une seule attente réseau.
    with ThreadPoolExecutor(max_workers=4) as pool:
        set_future = pool.submit(client.get_set, "en", set_id)
        card_futures = {locale: pool.submit(client.get_card, locale, tcgdx_card_id) for locale in ("en", "fr", "ja")}
    try:
        set_detail = set_future.result()
        card_en = card_futures["en"].result()
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

    card_fr = _card_or(card_futures["fr"], card_en)
    card_ja = _card_or(card_futures["ja"], card_en)

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
    fallback_image = (
        fallback_card_image("en", dict(set_detail), local_raw)
        if not image_base or has_lettered_number(local_raw)
        else None
    )
    # L'id JA peut désigner une autre carte (id partagé JP/international) : seules les fiches EN/FR portent le prix.
    same_card_payloads: list[dict[str, Any]] = [dict(card_en), dict(card_fr)]
    cardmarket_block = extract_cardmarket_block(same_card_payloads)
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
        known_prices=_known_prices(cardmarket_block, extract_tcgplayer_usd(same_card_payloads)),
        cardmarket_block=cardmarket_block,
        fallback_image_url_high=fallback_image.high if fallback_image else None,
    )


def _card_or(future: Future[TcgdexCardDetail], fallback: TcgdexCardDetail) -> TcgdexCardDetail:
    """Carte lue en parallèle, ou ``fallback`` quand TCGdex ne l'a pas dans cette langue."""
    try:
        return future.result()
    except (RuntimeError, ValueError):
        return fallback


def _known_prices(cardmarket_block: dict[str, Any] | None, tcgplayer_usd: float | None) -> dict[str, Any] | None:
    """
    Prix d'une carte déjà identifiée, lus sur sa fiche TCGdex et le guide Cardmarket local, ``None`` s'il n'y en a aucun.
    Évite la résolution par code set + numéro (une vingtaine d'ids TCGdex devinés, 10 s) quand l'id exact est connu.
    """
    raw_id_product = cardmarket_block.get("idProduct") if cardmarket_block else None
    id_product = raw_id_product if isinstance(raw_id_product, int) else None
    cardmarket_eur = resolve_market_price_eur(id_product, cardmarket_block)
    if cardmarket_eur is None and tcgplayer_usd is None:
        return None
    return {
        "cardmarket_eur": cardmarket_eur,
        "tcgplayer_usd": tcgplayer_usd,
        "cardmarket_id_product": id_product,
        "average_price": pricing_service.average_eur(cardmarket_eur, tcgplayer_usd),
        "error": None,
    }


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
    id_product = meta.get("cardmarket_id_product")
    known_prices = (
        {
            "cardmarket_eur": float(market_price),
            "tcgplayer_usd": None,
            "cardmarket_id_product": id_product if isinstance(id_product, int) else None,
            "average_price": float(market_price),
            "error": None,
        }
        if isinstance(market_price, (int, float))
        else None
    )
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
        known_prices=known_prices,
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
    known_prices: dict[str, Any] | None = None,
    cardmarket_block: dict[str, Any] | None = None,
    fallback_image_url_high: str | None = None,
) -> dict[str, Any]:
    """
    Titre + description d'annonce, prix, amorce de courbe et image HD d'une carte à partir de ses faits TCGdex.
    ``known_prices`` évite la recherche de prix par set/numéro quand la carte est déjà cotée.
    ``fallback_image_url_high`` remplace l'image HD quand TCGdex n'a pas de scan exploitable.
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

    pricing = known_prices or pricing_service.fetch_card_prices(resolved_code, number_pw, name_en)
    raw_id_product = pricing.get("cardmarket_id_product")
    id_product = raw_id_product if isinstance(raw_id_product, int) else None
    image_url_high: str | None = fallback_image_url_high
    if image_url_high is None and image_base and image_base.strip():
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
            "cardmarket_id_product": id_product,
            "error": pricing.get("error"),
        },
        "price_history": {"points": synthesized_price_points(id_product, cardmarket_block), "approximate": True},
        "image_url_high": image_url_high,
        "error": None,
    }
