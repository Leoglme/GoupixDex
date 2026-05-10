"""Pydantic bodies for Cardmarket saved searches."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CardmarketSearchCreateBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, max_length=255)
    urls: list[str] = Field(min_length=1)


class CardmarketSearchUpdateBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, max_length=255)
    urls: list[str] | None = None


class CardmarketSearchResultPutBody(BaseModel):
    """Worker pushes the aggregated scrape snapshot (JSON object)."""

    model_config = ConfigDict(extra="allow")

    payload: dict = Field(description="Full result object (cards, summaries, meta).")
