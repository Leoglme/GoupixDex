"""
Amorce approximative de courbe de prix, commune aux cartes et aux produits scellés.

Déduit jusqu'à 4 points sur ~30 jours depuis les moyennes glissantes du guide
Cardmarket (avg30 à J-30, avg7 à J-7, avg1 à J-1, référence à J). Chaque point
retombe sur la meilleure moyenne disponible : la courbe couvre ~30 jours dès qu'un
prix est connu, même quand le guide n'a qu'une référence (courbe plate approximative).
"""

from __future__ import annotations

import datetime as dt
from typing import Any
from zoneinfo import ZoneInfo

from services.cardmarket_local_price_service import get_price_api

_PARIS_TZ = ZoneInfo("Europe/Paris")


def _first_positive(*values: float | None) -> float | None:
    """Première valeur strictement positive parmi celles fournies, sinon None."""
    for value in values:
        if isinstance(value, (int, float)) and value > 0:
            return round(float(value), 2)
    return None


def synthesized_price_points(id_product: int | None) -> list[dict[str, Any]]:
    """Amorce ~30 jours (J-30, J-7, J-1, J) pour un idProduct Cardmarket ; vide si aucun prix connu."""
    if id_product is None:
        return []
    prices = get_price_api().get_card_prices(id_product)
    if prices is None:
        return []
    at_30 = _first_positive(prices.avg30, prices.avg7, prices.avg1, prices.reference_eur)
    at_7 = _first_positive(prices.avg7, prices.avg1, prices.reference_eur, prices.avg30)
    at_1 = _first_positive(prices.avg1, prices.reference_eur, prices.avg7, prices.avg30)
    at_0 = _first_positive(prices.reference_eur, prices.avg1, prices.avg7, prices.avg30)
    today = dt.datetime.now(_PARIS_TZ).date()
    plan = [(30, at_30), (7, at_7), (1, at_1), (0, at_0)]
    return [
        {"date": (today - dt.timedelta(days=days)).isoformat(), "price_eur": price}
        for days, price in plan
        if price is not None
    ]
