"""Point quotidien de valeur du portefeuille (cartes + scellés) pour les graphiques d'évolution."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class PortfolioValueSnapshot(Base):
    """
    Valeur figée du portefeuille d'un utilisateur pour une journée.

    Un point par ``(user_id, snapshot_date)`` (contrainte d'unicité) : le job
    nocturne réécrit la ligne du jour après avoir revalorisé cartes et scellés.
    Les courbes lisent l'historique tel quel — aucune reconstitution côté client.
    """

    __tablename__ = "portfolio_value_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    #: Jour du point de mesure (Europe/Paris).
    snapshot_date: Mapped[dt.date] = mapped_column(Date())

    #: Valeur marché des cartes ce jour-là (Σ prix × quantité).
    cards_market_eur: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"), server_default="0")
    #: Valeur marché des produits scellés ce jour-là (Σ prix × quantité).
    sealed_market_eur: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"), server_default="0")
    #: Valeur d'achat cumulée (Σ prix d'achat × quantité ; scellés uniquement, les cartes n'en portent pas).
    purchase_value_eur: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"), server_default="0")

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
        onupdate=lambda: dt.datetime.now(dt.UTC),
    )
