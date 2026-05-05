"""Single line item inside a Cardmarket order."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base


class CardmarketOrderLine(Base):
    """One purchased card row from a Cardmarket PDF."""

    __tablename__ = "cardmarket_order_lines"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("cardmarket_orders.id", ondelete="CASCADE"), index=True)
    line_index: Mapped[int] = mapped_column(Integer(), default=0)
    quantity: Mapped[int] = mapped_column(Integer(), default=1)
    raw_label: Mapped[str] = mapped_column(Text())
    pokemon_key: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    card_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    language_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    condition_label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    set_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    variant_token: Mapped[str | None] = mapped_column(String(512), nullable=True)
    unit_price_eur: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    order: Mapped["CardmarketOrder"] = relationship("CardmarketOrder", back_populates="lines")
    articles: Mapped[list["Article"]] = relationship("Article", back_populates="order_line")
