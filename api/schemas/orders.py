"""Pydantic schemas for Cardmarket order endpoints."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class OrderLineUpdate(BaseModel):
    """PATCH body for a single purchase line."""

    pokemon_name: str | None = None
    set_code: str | None = None
    card_number: str | None = None
    language_code: str | None = None
    condition_label: str | None = None
    unit_price_eur: Decimal | None = Field(None, ge=0)
    quantity: int | None = Field(None, ge=1)

    @field_validator("pokemon_name", "set_code", "card_number", "language_code", "condition_label")
    @classmethod
    def strip_optional_strings(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip()
        return s if s else None


class OrderReimportBody(BaseModel):
    """Optional JSON fields alongside PDF upload on reimport."""

    confirm_linked_line_indexes: list[int] = Field(default_factory=list)
