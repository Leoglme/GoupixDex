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
from services.cardmarket_local_price_service import fetch_tcgdex_pricing_snapshot, resolve_market_price_eur
from services.poke_wallet_client_service import PokeWalletClientService
from services.poke_wallet_reference_prices_service import PokeWalletReferencePricesService
from services.tcgdex_lookup_service import resolve_tcgdex_card_id_from_ocr

logger = logging.getLogger(__name__)


def _empty_result(error: str | None, source: str | None = None) -> dict[str, Any]:
    return {
        "cardmarket_eur": None,
        "tcgplayer_usd": None,
        "cardmarket_id_product": None,
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

    Returns ``None`` only when the card cannot be resolved on TCGdex — then the
    caller may fall back to PokéWallet. Once a TCGdex id exists, we never call
    PokéWallet (even when the guide has no price yet).
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

    block, tcgplayer_usd = fetch_tcgdex_pricing_snapshot(tcgdex_card_id)
    id_product = block.get("idProduct") if isinstance(block, dict) else None
    cardmarket_eur = resolve_market_price_eur(
        id_product if isinstance(id_product, int) else None,
        block,
    )
    if cardmarket_eur is not None or tcgplayer_usd is not None:
        if tcgplayer_usd is None:
            tcgplayer_usd = _pokewallet_tcgplayer_usd_only(
                set_code.strip(),
                card_number.strip(),
                pokemon_name,
            )
        return {
            "cardmarket_eur": cardmarket_eur,
            "tcgplayer_usd": tcgplayer_usd,
            "cardmarket_id_product": id_product if isinstance(id_product, int) else None,
            "average_price": _average_eur(cardmarket_eur, tcgplayer_usd),
            "card": None,
            "source": "cardmarket_local",
            "error": None,
        }

    if block is None:
        detail = "Cette carte n’a pas de fiche Cardmarket / TCGPlayer sur TCGdex."
    else:
        detail = "Prix Cardmarket indisponible (guide local ou carte non cotée)."
    return _empty_result(detail, source="cardmarket_local")


def _pokewallet_tcgplayer_usd_only(
    set_code: str,
    card_number: str,
    pokemon_name: str | None,
) -> float | None:
    """TCGPlayer USD from PokéWallet when TCGdex has Cardmarket but no TCGPlayer block."""
    try:
        client = PokeWalletClientService()
    except ValueError:
        return None

    opts: dict[str, object] = {"limit": 5, "page": 1}
    if pokemon_name:
        opts["pokemonName"] = pokemon_name.strip()

    try:
        search = client.search_by_set_code_and_number(set_code.strip(), card_number.strip(), opts)  # type: ignore[arg-type]
    except (RuntimeError, OSError, ValueError):
        return None

    results = search.get("results", [])
    if not results:
        return None

    first: PokeWalletCard = results[0]
    tcg_rows = (first.get("tcgplayer") or {}).get("prices") or []
    tcg_usd = PokeWalletReferencePricesService.pick_tcgplayer_reference_usd(tcg_rows)
    return float(tcg_usd) if tcg_usd is not None else None


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
        return _empty_result(
            "Aucune référence catalogue trouvée pour ce code set et ce numéro.",
            source="pokewallet",
        )

    first: PokeWalletCard = results[0]
    cm_rows = (first.get("cardmarket") or {}).get("prices") or []
    tcg_rows = (first.get("tcgplayer") or {}).get("prices") or []

    cm_eur = PokeWalletReferencePricesService.pick_cardmarket_reference_eur(cm_rows)
    tcg_usd = PokeWalletReferencePricesService.pick_tcgplayer_reference_usd(tcg_rows)

    return {
        "cardmarket_eur": float(cm_eur) if cm_eur is not None else None,
        "tcgplayer_usd": float(tcg_usd) if tcg_usd is not None else None,
        "cardmarket_id_product": None,
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
        return _empty_result("Le code set et le numéro de carte sont requis.")

    local = _fetch_prices_via_cardmarket_local(set_code.strip(), card_number.strip(), pokemon_name)
    if local is not None:
        return local

    return _fetch_prices_via_pokewallet(set_code, card_number, pokemon_name)


def average_to_decimal(value: float | None) -> Decimal | None:
    """Convert optional float average to Decimal for persistence."""
    if value is None:
        return None
    return Decimal(str(round(value, 2)))
