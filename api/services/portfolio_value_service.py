"""
Valeur du portefeuille (cartes + produits scellés) : instantané du jour et historique.

- :func:`compute_portfolio_breakdown` agrège les lignes vivantes (cartes + scellés).
- :func:`upsert_today_snapshot` fige un point par jour (idempotent), écrit par le job nocturne.
- :func:`list_timeline` relit l'historique pour les courbes, filtré par période.
"""

from __future__ import annotations

import datetime as dt
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlalchemy.orm import Session

from models.collection_card import CollectionCard
from models.portfolio_value_snapshot import PortfolioValueSnapshot
from models.sealed_product import SealedProduct

_PARIS_TZ = ZoneInfo("Europe/Paris")

#: Nombre de jours d'historique par période du sélecteur (``None`` pour « tout »).
PERIOD_DAYS: dict[str, int | None] = {
    "1j": 1,
    "7j": 7,
    "1m": 30,
    "3m": 90,
    "6m": 180,
    "tout": None,
}


def _today_paris() -> dt.date:
    """Date du jour en Europe/Paris (aligne l'instantané sur le fuseau du job nocturne)."""
    return dt.datetime.now(_PARIS_TZ).date()


def compute_portfolio_breakdown(db: Session, user_id: int) -> dict[str, float]:
    """
    Valeurs vivantes du portefeuille d'un utilisateur.

    ``purchase_value_eur`` ne couvre que les scellés (les cartes de la collection
    ne portent pas de prix d'achat).
    """
    cards_market = db.query(
        func.coalesce(func.sum(CollectionCard.market_price_eur * CollectionCard.quantity), 0)
    ).filter(
        CollectionCard.user_id == user_id,
        CollectionCard.is_placeholder.is_(False),
    ).scalar()
    sealed_market = db.query(
        func.coalesce(func.sum(SealedProduct.market_price_eur * SealedProduct.quantity), 0)
    ).filter(SealedProduct.user_id == user_id).scalar()
    purchase_value = db.query(
        func.coalesce(func.sum(SealedProduct.purchase_price_eur * SealedProduct.quantity), 0)
    ).filter(SealedProduct.user_id == user_id).scalar()

    cards_market_eur = round(float(cards_market or 0), 2)
    sealed_market_eur = round(float(sealed_market or 0), 2)
    purchase_value_eur = round(float(purchase_value or 0), 2)
    return {
        "cards_market_eur": cards_market_eur,
        "sealed_market_eur": sealed_market_eur,
        "purchase_value_eur": purchase_value_eur,
        "total_market_eur": round(cards_market_eur + sealed_market_eur, 2),
    }


def upsert_today_snapshot(
    db: Session,
    user_id: int,
    breakdown: dict[str, float] | None = None,
) -> PortfolioValueSnapshot:
    """Écrit (ou réécrit) le point de valeur du jour pour un utilisateur. Sans commit."""
    values = breakdown if breakdown is not None else compute_portfolio_breakdown(db, user_id)
    today = _today_paris()
    row = (
        db.query(PortfolioValueSnapshot)
        .filter(
            PortfolioValueSnapshot.user_id == user_id,
            PortfolioValueSnapshot.snapshot_date == today,
        )
        .first()
    )
    if row is None:
        row = PortfolioValueSnapshot(user_id=user_id, snapshot_date=today)
        db.add(row)
    row.cards_market_eur = values["cards_market_eur"]
    row.sealed_market_eur = values["sealed_market_eur"]
    row.purchase_value_eur = values["purchase_value_eur"]
    return row


def snapshot_all_users(db: Session) -> int:
    """Fige le point du jour pour chaque utilisateur possédant au moins une carte ou un scellé."""
    card_user_ids = {uid for (uid,) in db.query(CollectionCard.user_id).distinct().all()}
    sealed_user_ids = {uid for (uid,) in db.query(SealedProduct.user_id).distinct().all()}
    user_ids = card_user_ids | sealed_user_ids
    for user_id in user_ids:
        upsert_today_snapshot(db, user_id)
    db.commit()
    return len(user_ids)


def _period_cutoff(period: str) -> dt.date | None:
    """Date plancher pour une période du sélecteur (``None`` pour « tout »)."""
    days = PERIOD_DAYS.get(period, None)
    if days is None:
        return None
    return _today_paris() - dt.timedelta(days=days - 1)


def list_timeline(db: Session, user_id: int, period: str = "tout") -> list[dict[str, Any]]:
    """Historique de valeur pour les courbes, filtré par période et trié par date croissante."""
    q = db.query(PortfolioValueSnapshot).filter(PortfolioValueSnapshot.user_id == user_id)
    cutoff = _period_cutoff(period)
    if cutoff is not None:
        q = q.filter(PortfolioValueSnapshot.snapshot_date >= cutoff)
    rows = q.order_by(PortfolioValueSnapshot.snapshot_date.asc()).all()
    timeline: list[dict[str, Any]] = []
    for r in rows:
        cards_eur = float(r.cards_market_eur)
        sealed_eur = float(r.sealed_market_eur)
        timeline.append(
            {
                "date": r.snapshot_date.isoformat(),
                "market_eur": round(cards_eur + sealed_eur, 2),
                "purchase_eur": round(float(r.purchase_value_eur), 2),
                "cards_eur": round(cards_eur, 2),
                "sealed_eur": round(sealed_eur, 2),
            }
        )
    return timeline
