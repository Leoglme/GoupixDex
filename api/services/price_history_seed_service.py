"""
Amorce de courbe de prix, commune aux cartes et aux produits scellés.

Trace uniquement les **vraies** moyennes glissantes présentes dans le guide Cardmarket
(avg30 à J-30, avg7 à J-7, avg1 à J-1, référence à J) : aucune donnée n'est inventée.
Un produit sans moyenne connue ne renvoie qu'un point (le prix du jour) ; sa courbe
réelle se construit ensuite au fil des snapshots quotidiens.
"""

from __future__ import annotations

import datetime as dt
from typing import Any
from zoneinfo import ZoneInfo

from services.cardmarket_local_price_service import get_price_api

_PARIS_TZ = ZoneInfo("Europe/Paris")


def synthesized_price_points(id_product: int | None) -> list[dict[str, Any]]:
    """Points d'amorce (J-30/J-7/J-1/J) pour un idProduct, limités aux moyennes réellement connues du guide."""
    if id_product is None:
        return []
    prices = get_price_api().get_card_prices(id_product)
    if prices is None:
        return []
    today = dt.datetime.now(_PARIS_TZ).date()
    plan = [(30, prices.avg30), (7, prices.avg7), (1, prices.avg1), (0, prices.reference_eur)]
    return [
        {"date": (today - dt.timedelta(days=days)).isoformat(), "price_eur": round(float(value), 2)}
        for days, value in plan
        if isinstance(value, (int, float)) and value > 0
    ]
