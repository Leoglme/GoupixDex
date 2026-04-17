"""PokéWallet pricing: Cardmarket EUR and TCGPlayer USD reference values."""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from app_types.pokewallet import PokeWalletCard
from config import get_settings
from services.poke_wallet_client_service import PokeWalletClientService
from services.poke_wallet_reference_prices_service import PokeWalletReferencePricesService

logger = logging.getLogger(__name__)


def fetch_card_prices(
    set_code: str | None,
    card_number: str | None,
    pokemon_name: str | None = None,
) -> dict[str, Any]:
    """
    Resolve Cardmarket EUR and TCGPlayer USD for a card via PokéWallet search.

    Returns:
        Dict with ``cardmarket_eur``, ``tcgplayer_usd``, ``average_price`` (EUR basis),
        ``card`` (first hit or None), and optional ``error`` message.
    """
    settings = get_settings()
    if not set_code or not card_number:
        return {
            "cardmarket_eur": None,
            "tcgplayer_usd": None,
            "average_price": None,
            "card": None,
            "error": "set_code and card_number are required for pricing lookup",
        }

    try:
        client = PokeWalletClientService()
    except ValueError as exc:
        logger.warning("PokeWallet client unavailable: %s", exc)
        return {
            "cardmarket_eur": None,
            "tcgplayer_usd": None,
            "average_price": None,
            "card": None,
            "error": str(exc),
        }

    opts: dict[str, object] = {"limit": 20, "page": 1}
    if pokemon_name:
        opts["pokemonName"] = pokemon_name.strip()

    try:
        search = client.search_by_set_code_and_number(set_code.strip(), card_number.strip(), opts)  # type: ignore[arg-type]
    except (RuntimeError, OSError, ValueError) as exc:
        logger.exception("PokeWallet search failed")
        return {
            "cardmarket_eur": None,
            "tcgplayer_usd": None,
            "average_price": None,
            "card": None,
            "error": str(exc),
        }

    results = search.get("results", [])
    if not results:
        return {
            "cardmarket_eur": None,
            "tcgplayer_usd": None,
            "average_price": None,
            "card": None,
            "error": "No PokéWallet results for this set code and number",
        }

    first: PokeWalletCard = results[0]
    cm_rows = (first.get("cardmarket") or {}).get("prices") or []
    tcg_rows = (first.get("tcgplayer") or {}).get("prices") or []

    cm_eur = PokeWalletReferencePricesService.pick_cardmarket_reference_eur(cm_rows)
    tcg_usd = PokeWalletReferencePricesService.pick_tcgplayer_reference_usd(tcg_rows)

    tcg_eur: float | None = None
    if tcg_usd is not None and tcg_usd > 0:
        tcg_eur = float(tcg_usd) * settings.usd_to_eur

    average: float | None = None
    if cm_eur is not None and cm_eur > 0 and tcg_eur is not None:
        average = (cm_eur + tcg_eur) / 2.0
    elif cm_eur is not None and cm_eur > 0:
        average = cm_eur
    elif tcg_eur is not None:
        average = tcg_eur

    return {
        "cardmarket_eur": float(cm_eur) if cm_eur is not None else None,
        "tcgplayer_usd": float(tcg_usd) if tcg_usd is not None else None,
        "average_price": average,
        "card": first,
        "error": None,
    }


def average_to_decimal(value: float | None) -> Decimal | None:
    """Convert optional float average to Decimal for persistence."""
    if value is None:
        return None
    return Decimal(str(round(value, 2)))
