"""Resolve TCGdex card metadata into the columns persisted on ``collection_cards``."""

from __future__ import annotations

from typing import Any, cast

from app_types.tcgdex import TcgdexSetDetail
from services.species_locale_names_service import fetch_species_locale_names
from services.tcgdex_client_service import (
    SUPPORTED_LOCALES,
    TcgdexClientService,
    infer_pokewallet_set_code,
    normalize_card_number_for_pokewallet,
    split_tcgdex_card_id,
)
from services.tcgdex_asset_url import card_image_low_webp, tcgdx_asset_url_with_webp


def _strip(value: Any) -> str:
    return str(value).strip() if isinstance(value, str) else ""


def _latin_display_name(en: str, fr: str, ja: str) -> str:
    """Always prefer a Latin-script name (FR → EN) — JA used only as last resort."""
    if fr:
        return fr
    if en:
        return en
    return ja or "Pokémon"


def _resolve_image_url(card_payload: dict[str, Any]) -> str | None:
    base = card_payload.get("image")
    if not isinstance(base, str) or not base.strip():
        return None
    return card_image_low_webp(base.strip())


def _set_name_from_card(card_payload: dict[str, Any]) -> str:
    nested = card_payload.get("set")
    if isinstance(nested, dict):
        nm = nested.get("name")
        if isinstance(nm, str):
            return nm.strip()
    return ""


def _set_logo_from_card(card_payload: dict[str, Any]) -> str | None:
    nested = card_payload.get("set")
    if isinstance(nested, dict):
        logo = nested.get("logo")
        if isinstance(logo, str) and logo.strip():
            return tcgdx_asset_url_with_webp(logo.strip())
    return None


def _locale_priority(physical_language: str) -> list[str]:
    """
    Locale order tried when resolving a card/set, best signal first.

    Japan-only sets (e.g. ``M1S`` / メガシンフォニア) have **no** EN or FR
    payload, so a hardcoded ``en`` read 404s. We always end up trying every
    supported locale; this just controls which one wins for primary fields.
    """
    lang = (physical_language or "").strip().lower()
    if lang == "ja":
        order = ["ja", "en", "fr"]
    elif lang == "fr":
        order = ["fr", "en", "ja"]
    else:
        order = ["en", "fr", "ja"]
    for loc in sorted(SUPPORTED_LOCALES):
        if loc not in order:
            order.append(loc)
    return order


def _first_resolvable_set(
    client: TcgdexClientService, set_id: str, locales: list[str]
) -> TcgdexSetDetail:
    for loc in locales:
        try:
            return client.get_set(loc, set_id)
        except (RuntimeError, ValueError):
            continue
    return cast(TcgdexSetDetail, {})


def fetch_card_for_collection(
    *,
    tcgdex_card_id: str,
    physical_language: str,
    fallback_name_en: str | None = None,
    tcgdex: TcgdexClientService | None = None,
) -> dict[str, Any]:
    """
    Build the row payload for a new ``CollectionCard`` from TCGdex EN / FR / JA.

    Resilient across locales: a card that only exists in ``ja`` (Japanese-only
    sets like ``M1S``) resolves fine instead of 404-ing on a hardcoded ``en``
    read. ``fallback_name_en`` (typically the OCR-derived English name) is used
    as the Latin display name when TCGdex has no EN/FR entry.

    Raises:
        ValueError: if the card id is invalid or it resolves in no locale.
    """
    cid = tcgdex_card_id.strip()
    if not cid:
        msg = "tcgdex_card_id is required."
        raise ValueError(msg)
    lang = physical_language.strip().lower() or "fr"
    if lang not in SUPPORTED_LOCALES:
        msg = f"Unsupported language {physical_language!r}; use one of: {', '.join(sorted(SUPPORTED_LOCALES))}"
        raise ValueError(msg)

    client = tcgdex or TcgdexClientService()
    set_id, local_raw = split_tcgdex_card_id(cid)
    locales = _locale_priority(lang)

    set_detail = _first_resolvable_set(client, set_id, locales)
    set_code = infer_pokewallet_set_code(set_detail) if set_detail else None

    cards_by_locale: dict[str, dict[str, Any]] = {}
    for loc in ("en", "fr", "ja"):
        try:
            cards_by_locale[loc] = dict(client.get_card(loc, cid))
        except (RuntimeError, ValueError):
            continue

    if not cards_by_locale:
        msg = f"TCGdex has no card {cid!r} in any supported locale."
        raise ValueError(msg)

    primary = next(
        (cards_by_locale[loc] for loc in locales if loc in cards_by_locale),
        next(iter(cards_by_locale.values())),
    )

    name_en = _strip(cards_by_locale.get("en", {}).get("name")) or _strip(fallback_name_en)
    name_ja = _strip(cards_by_locale.get("ja", {}).get("name"))
    name_fr = _strip(cards_by_locale.get("fr", {}).get("name")) or name_en

    if not name_ja and name_en:
        species = fetch_species_locale_names(name_en)
        name_ja = _strip(species.japanese)

    if not set_code:
        set_code = set_id.upper() or None

    rarity = _strip(primary.get("rarity"))
    image_url = _resolve_image_url(primary)

    set_name = _set_name_from_card(primary) or _strip(set_detail.get("name"))
    display_name = _latin_display_name(name_en, name_fr, name_ja)

    return {
        "tcgdex_card_id": cid,
        "tcgdex_set_id": set_id,
        "set_code": set_code,
        "set_name": set_name or None,
        "card_number": normalize_card_number_for_pokewallet(local_raw),
        "card_name_en": name_en or None,
        "card_name_fr": name_fr or None,
        "card_name_ja": name_ja or None,
        "display_name": display_name,
        "rarity": rarity or None,
        "language": lang,
        "image_url": image_url,
        "set_logo_url": _set_logo_from_card(primary),
    }
