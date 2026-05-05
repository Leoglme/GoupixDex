"""Cardmarket purchase order (imported from PDF)."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base


class CardmarketOrder(Base):
    """A Cardmarket order snapshot for one user."""

    __tablename__ = "cardmarket_orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    external_order_id: Mapped[str] = mapped_column(String(32), index=True)
    seller_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    seller_display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    seller_country_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    paid_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    shipped_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    items_subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    shipping_fee: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    order_total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    source_filename: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
    )

    lines: Mapped[list["CardmarketOrderLine"]] = relationship(
        "CardmarketOrderLine",
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="CardmarketOrderLine.line_index",
    )
