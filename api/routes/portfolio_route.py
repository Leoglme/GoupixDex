"""
``/portfolio`` — valeur agrégée de la collection (cartes + produits scellés).

Alimente l'écran « Valeur » : chiffre total, répartition cartes/produits (donut),
plus-value des scellés et courbes d'évolution (marché vs achat).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from core.database import get_db
from core.deps import get_current_user
from models.collection_card import CollectionCard
from models.portfolio_value_snapshot import PortfolioValueSnapshot
from models.user import User
from services import portfolio_value_service, sealed_product_service

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("/summary")
def portfolio_summary(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Chiffres vivants : valeur totale, répartition cartes/produits, plus-value scellés."""
    breakdown = portfolio_value_service.compute_portfolio_breakdown(db, user.id)
    sealed_rows = sealed_product_service.list_sealed_for_user(db, user.id)
    sealed_stats = sealed_product_service.aggregate_sealed_stats(sealed_rows)

    cards_count = (
        db.query(func.count(CollectionCard.id))
        .filter(CollectionCard.user_id == user.id, CollectionCard.is_placeholder.is_(False))
        .scalar()
    ) or 0
    history_days = (
        db.query(func.count(PortfolioValueSnapshot.id))
        .filter(PortfolioValueSnapshot.user_id == user.id)
        .scalar()
    ) or 0

    return {
        "total_market_eur": breakdown["total_market_eur"],
        "cards_market_eur": breakdown["cards_market_eur"],
        "sealed_market_eur": breakdown["sealed_market_eur"],
        "purchase_value_eur": breakdown["purchase_value_eur"],
        "sealed_gain_eur": sealed_stats["gain_eur"],
        "sealed_gain_percent": sealed_stats["gain_percent"],
        "split": [
            {"label": "Cartes", "value": breakdown["cards_market_eur"]},
            {"label": "Produits scellés", "value": breakdown["sealed_market_eur"]},
        ],
        "cards_count": int(cards_count),
        "sealed_count": sealed_stats["unique_products"],
        "sealed_total_quantity": sealed_stats["total_quantity"],
        "history_days": int(history_days),
    }


@router.get("/timeline")
def portfolio_timeline(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    period: str = Query("tout", pattern="^(1j|7j|1m|3m|6m|tout)$"),
) -> dict[str, Any]:
    """Historique de valeur pour les courbes (marché vs achat), filtré par période."""
    return {
        "period": period,
        "points": portfolio_value_service.list_timeline(db, user.id, period),
    }
