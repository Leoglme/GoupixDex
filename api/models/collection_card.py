"""Personal Pokémon card collection (decoupled from sale articles)."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base


class CollectionCard(Base):
    """
    A card owned by the user, kept in their personal binder.

    Storage is intentionally **lean**: no price / condition / grading. Those fields
    only appear when the user decides to put the card up for sale via
    :class:`models.article.Article` (linked by ``article_id``).
    """

    __tablename__ = "collection_cards"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    #: TCGdex card identifier (e.g. ``sv03.5-025``); not unique per user (multiple languages allowed).
    tcgdex_card_id: Mapped[str] = mapped_column(String(120))
    tcgdex_set_id: Mapped[str] = mapped_column(String(64))
    set_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    set_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    card_number: Mapped[str] = mapped_column(String(64))

    card_name_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    card_name_fr: Mapped[str | None] = mapped_column(String(255), nullable=True)
    card_name_ja: Mapped[str | None] = mapped_column(String(255), nullable=True)
    #: Name to display in the UI (always a Latin-script label).
    display_name: Mapped[str] = mapped_column(String(255))

    rarity: Mapped[str | None] = mapped_column(String(64), nullable=True)
    #: Physical language of the card (``fr`` | ``en`` | ``ja`` …).
    language: Mapped[str] = mapped_column(String(8), default="fr", server_default="fr")
    image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer(), default=1, server_default="1")
    #: True when the row exists only to fill a binder slot (not owned physically).
    is_placeholder: Mapped[bool] = mapped_column(Boolean(), default=False, server_default="0", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text(), nullable=True)

    #: Cardmarket product id (harvested from TCGdex ``pricing.cardmarket.idProduct``).
    cardmarket_id_product: Mapped[int | None] = mapped_column(BigInteger(), nullable=True)
    #: Reference market price in EUR (Cardmarket sales-based, never the ``low`` column).
    market_price_eur: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    market_price_updated_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    article_id: Mapped[int | None] = mapped_column(
        ForeignKey("articles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
        onupdate=lambda: dt.datetime.now(dt.UTC),
    )

    user: Mapped["User"] = relationship(back_populates="collection_cards")
    article: Mapped["Article | None"] = relationship("Article", foreign_keys=[article_id])
