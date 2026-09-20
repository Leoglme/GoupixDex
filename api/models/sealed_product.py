"""Produits scellés de la collection (ETB, coffrets, displays…), séparés des cartes."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

#: Types de produits scellés (valeur ``product_type`` en base), alignés sur les catégories Cardmarket.
SEALED_PRODUCT_TYPES: tuple[str, ...] = (
    "booster",
    "display",
    "theme_deck",
    "trainer_kit",
    "tin",
    "box_set",
    "etb",
    "blister",
    "autre",
)


class SealedProduct(Base):
    """
    Un produit scellé possédé par l'utilisateur (ETB, UPC, coffret, display…).

    Contrairement à :class:`models.collection_card.CollectionCard`, un scellé
    porte son **prix d'achat** (pour le pourcentage de gain) et son
    ``cardmarket_id_product`` sert au même guide de prix local que les cartes.
    La mise en vente reste déléguée à :class:`models.article.Article`
    (lié par ``article_id``).
    """

    __tablename__ = "sealed_products"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    #: Libellé affiché (ex. « ETB Étincelles Déferlantes »).
    name: Mapped[str] = mapped_column(String(255))
    #: Catégorie de produit (voir :data:`SEALED_PRODUCT_TYPES`).
    product_type: Mapped[str] = mapped_column(String(32), default="autre", server_default="autre")
    #: Nom du set / de l'édition, optionnel (ex. « Écarlate et Violet — Étincelles Déferlantes »).
    set_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    #: Langue du produit (``fr`` | ``en`` | ``ja`` …).
    language: Mapped[str] = mapped_column(String(8), default="fr", server_default="fr")
    image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer(), default=1, server_default="1")
    #: Prix d'achat unitaire payé, saisi par l'utilisateur (base du pourcentage de gain).
    purchase_price_eur: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text(), nullable=True)

    #: Identifiant produit Cardmarket (résolu depuis une URL Cardmarket ou saisi à la main).
    cardmarket_id_product: Mapped[int | None] = mapped_column(BigInteger(), nullable=True)
    #: URL Cardmarket d'origine, conservée pour rouvrir la fiche produit.
    cardmarket_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    #: Prix de référence marché en EUR (guide Cardmarket local, jamais la colonne ``low``).
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

    user: Mapped["User"] = relationship(back_populates="sealed_products")
    article: Mapped["Article | None"] = relationship("Article", foreign_keys=[article_id])
