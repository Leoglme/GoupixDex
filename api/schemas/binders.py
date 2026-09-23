"""Pydantic bodies for thematic binders (classeurs)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class BinderCreateBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class BinderUpdateBody(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    color: str | None = Field(None, max_length=32)
    style: str | None = Field(None, max_length=32)
    page_grid: str | None = Field(None, max_length=8)
    page_count: int | None = Field(None, ge=0, le=400)
    pokedex_region: str | None = Field(None, max_length=16)
    pokedex_slots: dict[str, int] | None = None
    design: dict[str, Any] | None = None
    cover: dict[str, Any] | None = None
    cover_collection_card_ids: list[int] | None = None


class BinderReorderBody(BaseModel):
    binder_ids: list[int] = Field(..., min_length=1)


class BinderPlaceItemBody(BaseModel):
    collection_card_id: int
    pocket: int = Field(..., ge=0)


class BinderPlaceCatalogBody(BaseModel):
    tcgdex_card_id: str = Field(..., min_length=3, max_length=120)
    pocket: int = Field(..., ge=0)
    language: str = Field("fr", min_length=2, max_length=8)


class BinderSyncCatalogBody(BaseModel):
    """Remplace en lot la carte cible de plusieurs pochettes par une carte catalogue."""

    cards: list[BinderPlaceCatalogBody] = Field(..., min_length=1, max_length=400)


class BinderCustomCard(BaseModel):
    """Carte cible fournie explicitement (absente de TCGdex) — ex. image LimitlessTCG."""

    pocket: int = Field(..., ge=0)
    tcgdex_card_id: str = Field(..., min_length=2, max_length=120)
    display_name: str = Field(..., min_length=1, max_length=255)
    set_code: str | None = Field(None, max_length=64)
    set_name: str | None = Field(None, max_length=255)
    card_number: str | None = Field(None, max_length=64)
    language: str = Field("ja", min_length=2, max_length=8)
    image_url: str | None = Field(None, max_length=512)


class BinderPlaceCustomBody(BaseModel):
    """Place en lot des cartes cibles fournies explicitement (source hors TCGdex, ex. LimitlessTCG)."""

    cards: list[BinderCustomCard] = Field(..., min_length=1, max_length=200)


class BinderMovePocketBody(BaseModel):
    pocket_key: str = Field(..., min_length=3, max_length=64)
    to_pocket: int = Field(..., ge=0)


class BinderRemovePocketBody(BaseModel):
    pocket_key: str = Field(..., min_length=3, max_length=64)


class BinderPageCountBody(BaseModel):
    page_count: int = Field(..., ge=0, le=400)


class BinderAddItemsBody(BaseModel):
    collection_card_ids: list[int] = Field(..., min_length=1)


class BinderCoverUrlsBody(BaseModel):
    paths: list[str] = Field(default_factory=list, max_length=32)
