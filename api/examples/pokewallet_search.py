"""
Example: search PokéWallet by set code + number and print reference Cardmarket / TCGPlayer prices.

Requires ``POKE_WALLET_API_KEY`` in the environment or a ``.env`` file at the project root
(``python-dotenv`` is optional; load it from your app entrypoint if needed).
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

# Allow running as ``python examples/pokewallet_search.py`` from the ``api/`` directory.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(_ROOT / ".env")


def main() -> None:
    """Search SV8 / 112 (optional name filter) and print JSON with reference prices."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    _load_dotenv()

    from app_types.pokewallet import PokeWalletSearchOptions
    from services.pokewallet_client import PokeWalletClient
    from services.pokewallet_reference_prices import (
        pick_cardmarket_reference_eur,
        pick_tcgplayer_reference_usd,
    )

    example_set_code = "SV8"
    example_card_number = "112"
    example_pokemon_name: str | None = "Magneton"

    client = PokeWalletClient()
    opts: PokeWalletSearchOptions = {"limit": 20, "page": 1}
    if example_pokemon_name:
        opts["pokemonName"] = example_pokemon_name

    search = client.search_by_set_code_and_number(example_set_code, example_card_number, opts)
    results = search.get("results", [])
    if not results:
        print("No results for", example_set_code, example_card_number)
        return

    first = results[0]
    cardmarket_prices = (first.get("cardmarket") or {}).get("prices") or []
    tcgplayer_prices = (first.get("tcgplayer") or {}).get("prices") or []

    cardmarket_ref = pick_cardmarket_reference_eur(cardmarket_prices)
    tcgplayer_ref = pick_tcgplayer_reference_usd(tcgplayer_prices)

    info = first.get("card_info", {})
    out = {
        "name": info.get("name"),
        "set": info.get("set_name"),
        "cardmarket_reference_eur": cardmarket_ref,
        "tcgplayer_reference_usd": tcgplayer_ref,
        "cardmarket_prices": cardmarket_prices,
        "tcgplayer_prices": tcgplayer_prices,
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
