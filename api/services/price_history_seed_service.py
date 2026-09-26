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

from services.cardmarket_local_price_service import (
    get_price_api,
    reference_eur_from_block,
)

_PARIS_TZ = ZoneInfo("Europe/Paris")


def synthesized_price_points(
    id_product: int | None, tcgdex_block: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    """Points d'amorce (J-30/J-7/J-1/J) limités aux moyennes connues du guide, ou du bloc Cardmarket de TCGdex en repli."""
    prices = get_price_api().get_card_prices(id_product) if id_product is not None else None
    if prices is not None:
        averages = [prices.avg30, prices.avg7, prices.avg1, prices.reference_eur]
    elif tcgdex_block is not None:
        averages = [
            tcgdex_block.get("avg30"),
            tcgdex_block.get("avg7"),
            tcgdex_block.get("avg1"),
            reference_eur_from_block(tcgdex_block),
        ]
    else:
        return []
    today = dt.datetime.now(_PARIS_TZ).date()
    plan = list(zip((30, 7, 1, 0), averages, strict=True))
    return [
        {"date": (today - dt.timedelta(days=days)).isoformat(), "price_eur": round(float(value), 2)}
        for days, value in plan
        if isinstance(value, (int, float)) and value > 0
    ]
