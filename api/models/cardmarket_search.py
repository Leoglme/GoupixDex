"""Saved Cardmarket multi-card searches and last-run snapshot."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base


class CardmarketSearch(Base):
    """User-defined list of product URLs to aggregate sellers for."""

    __tablename__ = "cardmarket_searches"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
        onupdate=lambda: dt.datetime.now(dt.UTC),
    )

    urls: Mapped[list["CardmarketSearchUrl"]] = relationship(
        "CardmarketSearchUrl",
        back_populates="search",
        cascade="all, delete-orphan",
        order_by="CardmarketSearchUrl.sort_index",
    )
    result: Mapped["CardmarketSearchResult | None"] = relationship(
        "CardmarketSearchResult",
        back_populates="search",
        uselist=False,
        cascade="all, delete-orphan",
    )


class CardmarketSearchUrl(Base):
    """One product page URL belonging to a search."""

    __tablename__ = "cardmarket_search_urls"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    search_id: Mapped[int] = mapped_column(ForeignKey("cardmarket_searches.id", ondelete="CASCADE"), index=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    sort_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
    )

    search: Mapped["CardmarketSearch"] = relationship("CardmarketSearch", back_populates="urls")


class CardmarketSearchResult(Base):
    """Latest JSON snapshot for a search (one row per search)."""

    __tablename__ = "cardmarket_search_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    search_id: Mapped[int] = mapped_column(
        ForeignKey("cardmarket_searches.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    ran_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)

    search: Mapped["CardmarketSearch"] = relationship("CardmarketSearch", back_populates="result")
