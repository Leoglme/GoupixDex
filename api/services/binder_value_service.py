"""
Courbe de valeur d'un classeur : agrège l'historique de prix de ses cartes.

Chaque pochette porte une carte de collection (possédée ou placeholder « manquante »).
On additionne, jour par jour, le prix marché de ces cartes :

- ``market_eur`` : valeur du classeur **complété** (cartes possédées + 1 exemplaire de
  chaque carte manquante) ;
- ``owned_eur`` : valeur réellement **possédée** (cartes en main, quantités incluses).

Chaque carte fournit sa série via ses snapshots réels, complétés par l'amorce
approximative du guide Cardmarket (J-30/J-7/J-1/J) tant que l'historique réel est court —
mêmes points que la courbe d'une fiche carte. Les prix sont reportés (forward-fill) sur
l'axe commun des dates avant sommation.
"""

from __future__ import annotations

import datetime as dt
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session, joinedload

from models.binder import Binder, BinderItem
from models.collection_card import CollectionCard
from models.collection_card_price_snapshot import CollectionCardPriceSnapshot
from services.portfolio_value_service import PERIOD_DAYS
from services.price_history_seed_service import synthesized_price_points

_PARIS_TZ = ZoneInfo("Europe/Paris")


def _period_cutoff(period: str) -> dt.date | None:
    """Date plancher d'une période du sélecteur (``None`` pour « tout »)."""
    days = PERIOD_DAYS.get(period)
    if days is None:
        return None
    return dt.datetime.now(_PARIS_TZ).date() - dt.timedelta(days=days - 1)


def _card_price_series(db: Session, card: CollectionCard) -> list[tuple[dt.date, float]]:
    """Série (date, prix) d'une carte : snapshots réels, sinon amorce Cardmarket."""
    rows = (
        db.query(CollectionCardPriceSnapshot)
        .filter(CollectionCardPriceSnapshot.collection_card_id == card.id)
        .order_by(CollectionCardPriceSnapshot.snapshot_date.asc())
        .all()
    )
    real = [(r.snapshot_date, round(float(r.market_price_eur), 2)) for r in rows]
    if len(real) >= 2:
        return real
    real_dates = {d for d, _ in real}
    seed = [
        (dt.date.fromisoformat(p["date"]), float(p["price_eur"]))
        for p in synthesized_price_points(card.cardmarket_id_product)
        if p["date"] not in {d.isoformat() for d in real_dates}
    ]
    merged = seed + real
    merged.sort(key=lambda point: point[0])
    return merged


def binder_value_timeline(db: Session, binder: Binder, period: str = "tout") -> list[dict[str, Any]]:
    """Historique de valeur du classeur, trié par date croissante et filtré par période."""
    items = (
        db.query(BinderItem)
        .options(joinedload(BinderItem.collection_card))
        .filter(BinderItem.binder_id == binder.id)
        .all()
    )
    series: dict[int, list[tuple[dt.date, float]]] = {}
    meta: dict[int, tuple[bool, int]] = {}
    all_dates: set[dt.date] = set()
    for bi in items:
        card = bi.collection_card
        if card is None:
            continue
        points = _card_price_series(db, card)
        if not points:
            continue
        series[card.id] = points
        is_owned = (not card.is_placeholder) and int(card.quantity) > 0
        meta[card.id] = (is_owned, int(card.quantity))
        all_dates.update(day for day, _ in points)

    if not all_dates:
        return []

    cutoff = _period_cutoff(period)
    cursor = {card_id: 0 for card_id in series}
    last_price: dict[int, float | None] = {card_id: None for card_id in series}
    timeline: list[dict[str, Any]] = []
    for day in sorted(all_dates):
        for card_id, points in series.items():
            while cursor[card_id] < len(points) and points[cursor[card_id]][0] <= day:
                last_price[card_id] = points[cursor[card_id]][1]
                cursor[card_id] += 1
        if cutoff is not None and day < cutoff:
            continue
        market_eur = 0.0
        owned_eur = 0.0
        for card_id, (is_owned, quantity) in meta.items():
            price = last_price[card_id]
            if price is None:
                continue
            market_eur += price * (quantity if is_owned else 1)
            if is_owned:
                owned_eur += price * quantity
        timeline.append(
            {
                "date": day.isoformat(),
                "market_eur": round(market_eur, 2),
                "owned_eur": round(owned_eur, 2),
            }
        )
    return timeline
