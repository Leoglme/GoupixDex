"""
Historique de prix marché par produit scellé (courbe d'évolution de la fiche).

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

from models.sealed_price_snapshot import SealedPriceSnapshot
from models.sealed_product import SealedProduct
from services.cardmarket_local_price_service import get_price_api

_PARIS_TZ = ZoneInfo("Europe/Paris")


def _today_paris() -> dt.date:
    """Date du jour en Europe/Paris (aligne les points sur le job nocturne)."""
    return dt.datetime.now(_PARIS_TZ).date()


def record_snapshot(db: Session, sealed_product_id: int, price_eur: float, *, when: dt.date | None = None) -> None:
    """Écrit (ou réécrit) le point de prix d'un produit pour une journée. Sans commit."""
    day = when or _today_paris()
    row = (
        db.query(SealedPriceSnapshot)
        .filter(
            SealedPriceSnapshot.sealed_product_id == sealed_product_id,
            SealedPriceSnapshot.snapshot_date == day,
        )
        .first()
    )
    value = Decimal(str(round(price_eur, 2)))
    if row is None:
        db.add(SealedPriceSnapshot(sealed_product_id=sealed_product_id, snapshot_date=day, market_price_eur=value))
    else:
        row.market_price_eur = value


def snapshot_all_sealed(db: Session) -> int:
    """Fige le point du jour pour chaque produit scellé ayant un prix marché connu."""
    rows = db.query(SealedProduct.id, SealedProduct.market_price_eur).filter(
        SealedProduct.market_price_eur.is_not(None)
    ).all()
    for sealed_id, price in rows:
        if price is not None:
            record_snapshot(db, sealed_id, float(price))
    db.commit()
    return len(rows)


def _synthesized_points(id_product: int | None) -> list[dict[str, Any]]:
    """Amorce approximative depuis les moyennes du guide (avg30 à J-30, avg7 à J-7, référence à J)."""
    if id_product is None:
        return []
    prices = get_price_api().get_card_prices(id_product)
    if prices is None:
        return []
    today = _today_paris()
    plan = [(30, prices.avg30), (7, prices.avg7), (1, prices.avg1), (0, prices.reference_eur)]
    points: list[dict[str, Any]] = []
    for days_ago, value in plan:
        if isinstance(value, (int, float)) and value > 0:
            points.append({"date": (today - dt.timedelta(days=days_ago)).isoformat(), "price_eur": round(float(value), 2)})
    return points


def price_history(db: Session, product: SealedProduct) -> dict[str, Any]:
    """
    Courbe de prix d'un produit : historique réel, complété par l'amorce approximative
    tant qu'il reste moins de deux points réels.
    """
    rows = (
        db.query(SealedPriceSnapshot)
        .filter(SealedPriceSnapshot.sealed_product_id == product.id)
        .order_by(SealedPriceSnapshot.snapshot_date.asc())
        .all()
    )
    real_points = [
        {"date": r.snapshot_date.isoformat(), "price_eur": round(float(r.market_price_eur), 2)} for r in rows
    ]
    if len(real_points) >= 2:
        return {"points": real_points, "approximate": False}

    seed = _synthesized_points(product.cardmarket_id_product)
    real_dates = {p["date"] for p in real_points}
    merged = [p for p in seed if p["date"] not in real_dates] + real_points
    merged.sort(key=lambda p: p["date"])
    return {"points": merged, "approximate": bool(seed) and len(real_points) < 2}
