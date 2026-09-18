"""
Card pricing: local Cardmarket data first, PokéWallet as last-resort fallback.

Tier 1 (``source="cardmarket_local"``) resolves the printed set code / number
into a TCGdex card id, harvests the Cardmarket ``idProduct`` from the TCGdex
pricing block (TTL-cached) and prices it against the local daily price guide —
no quota, no PokéWallet call.

Tier 2 (``source="pokewallet"``) is the historical PokéWallet lookup, kept for
cards TCGdex has not mapped to a Cardmarket product yet.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from app_types.pokewallet import PokeWalletCard
from config import get_settings
from services.cardmarket_local_price_service import (
    fetch_pricing_block_for_card,
    resolve_market_price_eur,
)
from services.poke_wallet_client_service import PokeWalletClientService
from services.poke_wallet_reference_prices_service import PokeWalletReferencePricesService
from services.tcgdex_lookup_service import resolve_tcgdex_card_id_from_ocr

logger = logging.getLogger(__name__)


def _empty_result(error: str | None, source: str | None = None) -> dict[str, Any]:
    return {
        "cardmarket_eur": None,
        "tcgplayer_usd": None,
        "average_price": None,
        "card": None,
        "source": source,
        "error": error,
    }


def _average_eur(cardmarket_eur: float | None, tcgplayer_usd: float | None) -> float | None:
    """EUR-basis average of the two marketplaces (single-source value when one is missing)."""
    settings = get_settings()
    tcg_eur: float | None = None
    if tcgplayer_usd is not None and tcgplayer_usd > 0:
        tcg_eur = float(tcgplayer_usd) * settings.usd_to_eur
    if cardmarket_eur is not None and cardmarket_eur > 0 and tcg_eur is not None:
        return (cardmarket_eur + tcg_eur) / 2.0
    if cardmarket_eur is not None and cardmarket_eur > 0:
        return cardmarket_eur
    return tcg_eur


def _fetch_prices_via_cardmarket_local(
    set_code: str,
    card_number: str,
    pokemon_name: str | None,
) -> dict[str, Any] | None:
    """
    Tier 1: TCGdex resolution + local Cardmarket price guide.

    Returns ``None`` when the card cannot be resolved or has no Cardmarket
    reference yet — the caller then falls back to PokéWallet.
    """
    try:
        tcgdex_card_id = resolve_tcgdex_card_id_from_ocr(
            ocr_set_code=set_code,
            ocr_card_number=card_number,
            ocr_pokemon_name_english=pokemon_name,
        )
    except (RuntimeError, ValueError, OSError) as exc:
        logger.warning("TCGdex resolution failed for %s %s: %s", set_code, card_number, exc)
        return None
    if not tcgdex_card_id:
        return None

    block = fetch_pricing_block_for_card(tcgdex_card_id)
    if block is None:
        return None
    id_product = block.get("idProduct")
    cardmarket_eur = resolve_market_price_eur(
        id_product if isinstance(id_product, int) else None,
        block,
    )
    if cardmarket_eur is None:
        return None

    return {
        "cardmarket_eur": cardmarket_eur,
        "tcgplayer_usd": None,
        "average_price": _average_eur(cardmarket_eur, None),
        "card": None,
        "source": "cardmarket_local",
        "error": None,
    }


def _fetch_prices_via_pokewallet(
    set_code: str,
    card_number: str,
    pokemon_name: str | None,
) -> dict[str, Any]:
    """Tier 2: historical PokéWallet lookup (rate-limited external API)."""
    try:
        client = PokeWalletClientService()
    except ValueError as exc:
        logger.warning("PokeWallet client unavailable: %s", exc)
        return _empty_result(str(exc), source="pokewallet")

    opts: dict[str, object] = {"limit": 20, "page": 1}
    if pokemon_name:
        opts["pokemonName"] = pokemon_name.strip()

    try:
        search = client.search_by_set_code_and_number(set_code.strip(), card_number.strip(), opts)  # type: ignore[arg-type]
    except (RuntimeError, OSError, ValueError) as exc:
        logger.exception("PokeWallet search failed")
        return _empty_result(str(exc), source="pokewallet")

    results = search.get("results", [])
    if not results:
        return _empty_result("No PokéWallet results for this set code and number", source="pokewallet")

    first: PokeWalletCard = results[0]
    cm_rows = (first.get("cardmarket") or {}).get("prices") or []
    tcg_rows = (first.get("tcgplayer") or {}).get("prices") or []

    cm_eur = PokeWalletReferencePricesService.pick_cardmarket_reference_eur(cm_rows)
    tcg_usd = PokeWalletReferencePricesService.pick_tcgplayer_reference_usd(tcg_rows)

    return {
        "cardmarket_eur": float(cm_eur) if cm_eur is not None else None,
        "tcgplayer_usd": float(tcg_usd) if tcg_usd is not None else None,
        "average_price": _average_eur(
            float(cm_eur) if cm_eur is not None else None,
            float(tcg_usd) if tcg_usd is not None else None,
        ),
        "card": first,
        "source": "pokewallet",
        "error": None,
    }


def fetch_card_prices(
    set_code: str | None,
    card_number: str | None,
    pokemon_name: str | None = None,
) -> dict[str, Any]:
    """
    Resolve a card's reference prices (EUR basis).

    Returns:
        Dict with ``cardmarket_eur``, ``tcgplayer_usd``, ``average_price``,
        ``card`` (PokéWallet hit or None), ``source`` and optional ``error``.
    """
    if not set_code or not card_number:
        return _empty_result("set_code and card_number are required for pricing lookup")

    local = _fetch_prices_via_cardmarket_local(set_code.strip(), card_number.strip(), pokemon_name)
    if local is not None:
        return local

    return _fetch_prices_via_pokewallet(set_code, card_number, pokemon_name)


def average_to_decimal(value: float | None) -> Decimal | None:
    """Convert optional float average to Decimal for persistence."""
    if value is None:
        return None
    return Decimal(str(round(value, 2)))
