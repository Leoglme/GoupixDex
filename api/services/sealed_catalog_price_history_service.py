"""
Historique de prix marché des produits scellés du catalogue, par ``idProduct`` Cardmarket.

Le guide Cardmarket ne publie aucune moyenne glissante pour les scellés (``avg1`` / ``avg7`` /
``avg30`` absents) : la courbe d'un produit que personne ne possède ne peut venir que de nos
propres relevés quotidiens du prix guide, partagés entre tous les utilisateurs.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from models.sealed_catalog_price_snapshot import SealedCatalogPriceSnapshot
from services.cardmarket_local_price_service import get_price_api, resolve_market_price_eur

_PARIS_TZ = ZoneInfo("Europe/Paris")

#: Catégories Cardmarket (``idCategory``) des scellés Pokémon présents dans le catalogue GoupixDex.
SEALED_GUIDE_CATEGORY_IDS: frozenset[int] = frozenset(
    {
        52,  # lots et produits divers
        53,  # displays (booster boxes)
        54,  # theme decks
        1013,  # trainer kits
        1014,  # displays et tins
        1015,  # coffrets (box sets)
        1016,  # Elite Trainer Boxes
        1083,  # blisters
    }
)


def _today_paris() -> dt.date:
    """Date du jour en Europe/Paris (aligne les points sur le job nocturne)."""
    return dt.datetime.now(_PARIS_TZ).date()


def _snapshot_to_point(row: SealedCatalogPriceSnapshot) -> dict[str, Any]:
    return {"date": row.snapshot_date.isoformat(), "price_eur": round(float(row.market_price_eur), 2)}


def record_catalog_snapshot(db: Session, id_product: int, price_eur: float, *, when: dt.date | None = None) -> None:
    """Écrit (ou réécrit) le point de prix guide d'un ``idProduct`` pour une journée. Sans commit."""
    day = when or _today_paris()
    row = (
        db.query(SealedCatalogPriceSnapshot)
        .filter(
            SealedCatalogPriceSnapshot.cardmarket_id_product == id_product,
            SealedCatalogPriceSnapshot.snapshot_date == day,
        )
        .first()
    )
    value = Decimal(str(round(price_eur, 2)))
    if row is None:
        db.add(SealedCatalogPriceSnapshot(cardmarket_id_product=id_product, snapshot_date=day, market_price_eur=value))
    else:
        row.market_price_eur = value


def ensure_today_catalog_snapshot(db: Session, id_product: int) -> None:
    """Pose le point du jour d'un produit consulté s'il manque encore, pour que sa courbe démarre à la première visite."""
    today = _today_paris()
    exists = (
        db.query(SealedCatalogPriceSnapshot.id)
        .filter(
            SealedCatalogPriceSnapshot.cardmarket_id_product == id_product,
            SealedCatalogPriceSnapshot.snapshot_date == today,
        )
        .first()
    )
    if exists is not None:
        return
    price = resolve_market_price_eur(id_product, None)
    if price is None:
        return
    record_catalog_snapshot(db, id_product, price, when=today)
    db.commit()


def snapshot_all_sealed_catalog(db: Session) -> int:
    """Fige le prix guide du jour de chaque scellé du guide Cardmarket ; renvoie le nombre de points écrits ou corrigés."""
    today = _today_paris()
    existing = {
        row.cardmarket_id_product: row
        for row in db.query(SealedCatalogPriceSnapshot).filter(SealedCatalogPriceSnapshot.snapshot_date == today).all()
    }
    written = 0
    for guide_row in get_price_api().rows():
        if guide_row.id_category not in SEALED_GUIDE_CATEGORY_IDS:
            continue
        price = resolve_market_price_eur(guide_row.id_product, None)
        if price is None:
            continue
        value = Decimal(str(price))
        current = existing.get(guide_row.id_product)
        if current is None:
            db.add(
                SealedCatalogPriceSnapshot(
                    cardmarket_id_product=guide_row.id_product,
                    snapshot_date=today,
                    market_price_eur=value,
                )
            )
            written += 1
        elif current.market_price_eur != value:
            current.market_price_eur = value
            written += 1
    db.commit()
    return written


def catalog_price_points(db: Session, id_product: int | None) -> list[dict[str, Any]]:
    """Points datés (croissants) relevés pour un ``idProduct`` ; vide sans identifiant."""
    if id_product is None:
        return []
    rows = (
        db.query(SealedCatalogPriceSnapshot)
        .filter(SealedCatalogPriceSnapshot.cardmarket_id_product == id_product)
        .order_by(SealedCatalogPriceSnapshot.snapshot_date.asc())
        .all()
    )
    return [_snapshot_to_point(row) for row in rows]
