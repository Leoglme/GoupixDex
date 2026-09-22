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
from services import sealed_catalog_price_history_service
from services.price_history_seed_service import synthesized_price_points

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


def merge_price_points(primary: list[dict[str, Any]], secondary: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fusionne deux séries datées : les points de ``primary`` gagnent sur ``secondary`` à date égale ; tri croissant."""
    primary_dates = {p["date"] for p in primary}
    merged = [p for p in secondary if p["date"] not in primary_dates] + list(primary)
    merged.sort(key=lambda p: p["date"])
    return merged


def _points_with_seed(points: list[dict[str, Any]], id_product: int | None) -> dict[str, Any]:
    """Complète une série trop courte (moins de deux points) par l'amorce guide ; ``approximate`` si l'amorce a ajouté une date."""
    if len(points) >= 2:
        return {"points": points, "approximate": False}
    seed = synthesized_price_points(id_product)
    merged = merge_price_points(points, seed)
    return {"points": merged, "approximate": len(merged) > len(points)}


def price_history(db: Session, product: SealedProduct) -> dict[str, Any]:
    """Courbe d'un produit possédé : ses snapshots, étendus par les relevés catalogue du même ``idProduct`` aux autres dates, puis par l'amorce guide s'il manque des points."""
    rows = (
        db.query(SealedPriceSnapshot)
        .filter(SealedPriceSnapshot.sealed_product_id == product.id)
        .order_by(SealedPriceSnapshot.snapshot_date.asc())
        .all()
    )
    real_points = [
        {"date": r.snapshot_date.isoformat(), "price_eur": round(float(r.market_price_eur), 2)} for r in rows
    ]
    catalog_points = sealed_catalog_price_history_service.catalog_price_points(db, product.cardmarket_id_product)
    return _points_with_seed(merge_price_points(real_points, catalog_points), product.cardmarket_id_product)


def catalog_price_history(db: Session, *, user_id: int, id_product: int | None) -> dict[str, Any]:
    """Courbe d'un produit du catalogue : celle du produit possédé s'il est dans la collection, sinon les relevés quotidiens du guide (point du jour posé à la première consultation)."""
    if id_product is None:
        return {"points": [], "approximate": False}
    owned = (
        db.query(SealedProduct)
        .filter(SealedProduct.user_id == user_id, SealedProduct.cardmarket_id_product == id_product)
        .order_by(SealedProduct.id.asc())
        .first()
    )
    if owned is not None:
        return price_history(db, owned)
    sealed_catalog_price_history_service.ensure_today_catalog_snapshot(db, id_product)
    points = sealed_catalog_price_history_service.catalog_price_points(db, id_product)
    return _points_with_seed(points, id_product)
