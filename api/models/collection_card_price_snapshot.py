"""Point de prix marché quotidien d'une carte de collection (courbe d'évolution de la fiche)."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class CollectionCardPriceSnapshot(Base):
    """
    Prix marché figé d'une carte de collection pour une journée.

    Un point par ``(collection_card_id, snapshot_date)`` : le job nocturne écrit la
    ligne du jour après revalorisation, l'ajout écrit le point initial.
    """

    __tablename__ = "collection_card_price_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    collection_card_id: Mapped[int] = mapped_column(
        ForeignKey("collection_cards.id", ondelete="CASCADE"),
        index=True,
    )
    snapshot_date: Mapped[dt.date] = mapped_column(Date())
    market_price_eur: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
    )
