"""Point de prix marché quotidien d'un produit scellé (courbe d'évolution de la fiche)."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class SealedPriceSnapshot(Base):
    """
    Prix marché figé d'un produit scellé pour une journée.

    Un point par ``(sealed_product_id, snapshot_date)`` : le job nocturne écrit la
    ligne du jour après revalorisation, l'ajout écrit le point initial.
    """

    __tablename__ = "sealed_price_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sealed_product_id: Mapped[int] = mapped_column(
        ForeignKey("sealed_products.id", ondelete="CASCADE"),
        index=True,
    )
    snapshot_date: Mapped[dt.date] = mapped_column(Date())
    market_price_eur: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
    )
