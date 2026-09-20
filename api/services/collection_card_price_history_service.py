"""
Historique de prix marché par carte de collection (courbe d'évolution de la fiche).

Points **réels** figés chaque nuit (et à l'ajout). Tant que l'historique réel est
trop court, la courbe est complétée par une **amorce approximative** déduite des
moyennes glissantes du guide Cardmarket (avg30 / avg7 / trend) — vraies données,
mais moyennes, d'où le drapeau ``approximate``.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from models.collection_card import CollectionCard
from models.collection_card_price_snapshot import CollectionCardPriceSnapshot
from services.price_history_seed_service import synthesized_price_points

_PARIS_TZ = ZoneInfo("Europe/Paris")


def _today_paris() -> dt.date:
    """Date du jour en Europe/Paris (aligne les points sur le job nocturne)."""
    return dt.datetime.now(_PARIS_TZ).date()


def record_snapshot(db: Session, collection_card_id: int, price_eur: float, *, when: dt.date | None = None) -> None:
    """Écrit (ou réécrit) le point de prix d'une carte pour une journée. Sans commit."""
    day = when or _today_paris()
    row = (
        db.query(CollectionCardPriceSnapshot)
        .filter(
            CollectionCardPriceSnapshot.collection_card_id == collection_card_id,
            CollectionCardPriceSnapshot.snapshot_date == day,
        )
        .first()
    )
    value = Decimal(str(round(price_eur, 2)))
    if row is None:
        db.add(
            CollectionCardPriceSnapshot(
                collection_card_id=collection_card_id,
                snapshot_date=day,
                market_price_eur=value,
            )
        )
    else:
        row.market_price_eur = value


def snapshot_all_collection_cards(db: Session) -> int:
    """Fige le point du jour pour chaque carte ayant un prix marché connu."""
    rows = (
        db.query(CollectionCard.id, CollectionCard.market_price_eur)
        .filter(CollectionCard.market_price_eur.is_not(None))
        .all()
    )
    for card_id, price in rows:
        if price is not None:
            record_snapshot(db, card_id, float(price))
    db.commit()
    return len(rows)


def price_history(db: Session, card: CollectionCard) -> dict[str, Any]:
    """
    Courbe de prix d'une carte : historique réel, complété par l'amorce approximative
    tant qu'il reste moins de deux points réels.
    """
    rows = (
        db.query(CollectionCardPriceSnapshot)
        .filter(CollectionCardPriceSnapshot.collection_card_id == card.id)
        .order_by(CollectionCardPriceSnapshot.snapshot_date.asc())
        .all()
    )
    real_points = [
        {"date": r.snapshot_date.isoformat(), "price_eur": round(float(r.market_price_eur), 2)} for r in rows
    ]
    if len(real_points) >= 2:
        return {"points": real_points, "approximate": False}

    seed = synthesized_price_points(card.cardmarket_id_product)
    real_dates = {p["date"] for p in real_points}
    merged = [p for p in seed if p["date"] not in real_dates] + real_points
    merged.sort(key=lambda p: p["date"])
    return {"points": merged, "approximate": bool(seed) and len(real_points) < 2}
