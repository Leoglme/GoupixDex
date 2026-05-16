"""Pydantic schemas for the personal Pokémon card collection."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CollectionCardAddBody(BaseModel):
    """``POST /collection`` — add one TCGdex card to ``Ma Collection``."""

    tcgdex_card_id: str = Field(..., min_length=3, max_length=120)
    language: str = Field("fr", min_length=2, max_length=8)
    quantity: int = Field(1, ge=1, le=999)
    notes: str | None = Field(default=None, max_length=2000)


class CollectionCardUpdateBody(BaseModel):
    """``PATCH /collection/{id}`` — only set fields are applied."""

    quantity: int | None = Field(default=None, ge=1, le=999)
    language: str | None = Field(default=None, min_length=2, max_length=8)
    notes: str | None = Field(default=None, max_length=2000)


class CollectionCardPrepareSaleBody(BaseModel):
    """``POST /collection/{id}/prepare-article`` — bridge to an ``ArticleForm`` prefill."""

    #: Optional cardmarket / fallback price used by the front-end suggestion.
    refresh_pricing: bool = True
