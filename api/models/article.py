"""Article (card listing) ORM model."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base


class Article(Base):
    """A Pokémon card article / inventory row."""

    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(512))
    description: Mapped[str] = mapped_column(Text())
    pokemon_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    set_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    card_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    condition: Mapped[str] = mapped_column(String(64), default="Near Mint")
    purchase_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    sell_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    is_sold: Mapped[bool] = mapped_column(Boolean(), default=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
    )
    sold_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="articles")
    images: Mapped[list["Image"]] = relationship(back_populates="article", cascade="all, delete-orphan")
