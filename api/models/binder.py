"""Thematic card binders (TailTCG-style classeurs)."""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base


class Binder(Base):
    __tablename__ = "binders"

    id: Mapped[int] = mapped_column(BigInteger(), primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    color: Mapped[str | None] = mapped_column(String(32), nullable=True)
    style: Mapped[str] = mapped_column(String(32), default="binder", server_default="binder")
    page_grid: Mapped[str] = mapped_column(String(8), default="3x3", server_default="3x3")
    page_count: Mapped[int] = mapped_column(Integer(), default=0, server_default="0")
    pokedex_region: Mapped[str | None] = mapped_column(String(16), nullable=True)
    position: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    design: Mapped[dict[str, Any] | None] = mapped_column(JSON(), nullable=True)
    cover: Mapped[dict[str, Any] | None] = mapped_column(JSON(), nullable=True)
    cover_collection_card_ids: Mapped[list[int] | None] = mapped_column(JSON(), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
        onupdate=lambda: dt.datetime.now(dt.UTC),
    )

    user: Mapped["User"] = relationship(back_populates="binders")
    items: Mapped[list["BinderItem"]] = relationship(
        back_populates="binder",
        cascade="all, delete-orphan",
    )


class BinderItem(Base):
    __tablename__ = "binder_items"

    binder_id: Mapped[int] = mapped_column(
        BigInteger(),
        ForeignKey("binders.id", ondelete="CASCADE"),
        primary_key=True,
    )
    collection_card_id: Mapped[int] = mapped_column(
        BigInteger(),
        ForeignKey("collection_cards.id", ondelete="CASCADE"),
        primary_key=True,
    )
    position: Mapped[int] = mapped_column(Integer())
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
    )

    binder: Mapped[Binder] = relationship(back_populates="items")
    collection_card: Mapped["CollectionCard"] = relationship("CollectionCard")
