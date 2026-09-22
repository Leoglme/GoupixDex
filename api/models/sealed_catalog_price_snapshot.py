"""Point de prix marché quotidien d'un produit scellé du catalogue, par ``idProduct`` Cardmarket."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class SealedCatalogPriceSnapshot(Base):
    """
    Prix guide figé pour un ``idProduct`` et une journée, indépendamment de qui possède le produit.

    Un point par ``(cardmarket_id_product, snapshot_date)`` : le job nocturne écrit la ligne du jour
    pour tous les scellés du guide, la consultation d'un produit du catalogue écrit le point du jour s'il manque.
    """

    __tablename__ = "sealed_catalog_price_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cardmarket_id_product: Mapped[int] = mapped_column(BigInteger(), index=True)
    snapshot_date: Mapped[dt.date] = mapped_column(Date())
    market_price_eur: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
    )
