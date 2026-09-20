"""Schémas Pydantic pour les produits scellés de la collection."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

#: Types acceptés en entrée (miroir de :data:`models.sealed_product.SEALED_PRODUCT_TYPES`).
SealedProductType = Literal[
    "etb",
    "upc",
    "coffret",
    "tripack",
    "pokebox",
    "mini_tin",
    "display",
    "blister",
    "autre",
]


class SealedProductCreateBody(BaseModel):
    """``POST /sealed`` — ajoute un produit scellé à la collection."""

    name: str = Field(..., min_length=1, max_length=255)
    product_type: SealedProductType = "autre"
    set_name: str | None = Field(default=None, max_length=255)
    language: str = Field("fr", min_length=2, max_length=8)
    quantity: int = Field(1, ge=1, le=999)
    purchase_price_eur: float | None = Field(default=None, ge=0, le=1_000_000)
    notes: str | None = Field(default=None, max_length=2000)
    image_url: str | None = Field(default=None, max_length=512)
    cardmarket_id_product: int | None = Field(default=None, ge=1)
    cardmarket_url: str | None = Field(default=None, max_length=512)
    #: Prix marché saisi manuellement quand aucun ``idProduct`` n'est résolu.
    market_price_eur: float | None = Field(default=None, ge=0, le=1_000_000)


class SealedProductUpdateBody(BaseModel):
    """``PATCH /sealed/{id}`` — seuls les champs fournis sont appliqués."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    product_type: SealedProductType | None = None
    set_name: str | None = Field(default=None, max_length=255)
    language: str | None = Field(default=None, min_length=2, max_length=8)
    quantity: int | None = Field(default=None, ge=1, le=999)
    purchase_price_eur: float | None = Field(default=None, ge=0, le=1_000_000)
    notes: str | None = Field(default=None, max_length=2000)
    image_url: str | None = Field(default=None, max_length=512)
    cardmarket_id_product: int | None = Field(default=None, ge=1)
    cardmarket_url: str | None = Field(default=None, max_length=512)
    market_price_eur: float | None = Field(default=None, ge=0, le=1_000_000)


class CardmarketResolveBody(BaseModel):
    """``POST /sealed/resolve-cardmarket`` — pré-remplit un scellé depuis une fiche Cardmarket."""

    url: str = Field(..., min_length=8, max_length=1024)


class SealedProductPrepareSaleBody(BaseModel):
    """``POST /sealed/{id}/prepare-article-prefill`` — passerelle vers un prefill ``ArticleForm``."""

    refresh_pricing: bool = True
