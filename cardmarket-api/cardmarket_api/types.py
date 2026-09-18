"""Typed views over Cardmarket's daily data files (price guide rows and reports)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PriceGuideRow:
    """
    One product's EUR aggregates from ``price_guide_{game}.json``.

    ``*_holo`` columns describe the product's reverse-holo variant (Poké Ball /
    Master Ball patterns on Japanese sets). Every aggregate mixes all listing
    languages and conditions — ``low`` is the single cheapest listing of the
    product and must never be used as a value reference.
    """

    id_product: int
    id_category: int
    avg: float | None
    low: float | None
    trend: float | None
    avg1: float | None
    avg7: float | None
    avg30: float | None
    avg_holo: float | None
    low_holo: float | None
    trend_holo: float | None
    avg1_holo: float | None
    avg7_holo: float | None
    avg30_holo: float | None


@dataclass(frozen=True, slots=True)
class CardmarketCardPrices:
    """Price view served to consumers; ``reference_eur`` is sales-based, never ``low``."""

    id_product: int
    reference_eur: float | None
    reverse_reference_eur: float | None
    trend: float | None
    avg1: float | None
    avg7: float | None
    avg30: float | None
    avg: float | None
    low: float | None
    #: ``createdAt`` of the guide snapshot these values come from (ISO string).
    guide_created_at: str | None


@dataclass(frozen=True, slots=True)
class PriceGuideRefreshReport:
    """Outcome of :meth:`cardmarket_api.price_api.CardmarketPriceApi.refresh`."""

    #: ``True`` when a new snapshot was downloaded and swapped in.
    refreshed: bool
    #: ``"network"`` | ``"not-modified"`` | ``"memory"`` | ``"disk"``
    source: str
    row_count: int
    created_at: str | None
