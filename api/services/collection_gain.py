"""Champs de plus-value d'une ligne possédée (valeur ligne, gain absolu, gain %).

Partagé entre les cartes (:mod:`services.collection_card_service`) et les produits
scellés (:mod:`services.sealed_product_service`) pour que le calcul reste identique
des deux côtés.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any


def gain_fields(
    market_price_eur: Decimal | None,
    purchase_price_eur: Decimal | None,
    quantity: int,
) -> dict[str, Any]:
    """
    Calcule la valeur de ligne, le gain absolu et le gain en pourcentage.

    Le gain n'est renseigné que si le prix marché et le prix d'achat sont tous deux
    connus ; le pourcentage n'est calculé que pour un prix d'achat strictement positif.
    """
    line_market = float(market_price_eur) * quantity if market_price_eur is not None else None
    line_purchase = float(purchase_price_eur) * quantity if purchase_price_eur is not None else None
    gain_eur: float | None = None
    gain_percent: float | None = None
    if market_price_eur is not None and purchase_price_eur is not None:
        gain_eur = round((float(market_price_eur) - float(purchase_price_eur)) * quantity, 2)
        if float(purchase_price_eur) > 0:
            gain_percent = round((float(market_price_eur) / float(purchase_price_eur) - 1.0) * 100.0, 1)
    return {
        "line_market_eur": round(line_market, 2) if line_market is not None else None,
        "line_purchase_eur": round(line_purchase, 2) if line_purchase is not None else None,
        "gain_eur": gain_eur,
        "gain_percent": gain_percent,
    }
