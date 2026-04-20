"""eBay Browse API response + aggregated market search shapes."""

from __future__ import annotations

from typing import Literal, NotRequired, TypedDict


class EbayMoney(TypedDict, total=False):
    """Money block as returned by eBay (``value`` is a numeric string)."""

    value: str
    currency: str


class EbayImage(TypedDict, total=False):
    imageUrl: str


class EbaySeller(TypedDict, total=False):
    username: str
    feedbackPercentage: str
    feedbackScore: int


class EbayItemLocation(TypedDict, total=False):
    country: str
    postalCode: str
    stateOrProvince: str


class EbayCategoryInfo(TypedDict, total=False):
    categoryId: str
    categoryName: str


class EbayItemSummary(TypedDict, total=False):
    """One item summary block from ``/buy/browse/v1/item_summary/search``."""

    itemId: str
    title: str
    price: EbayMoney
    condition: str
    conditionId: str
    itemWebUrl: str
    itemLocation: EbayItemLocation
    seller: EbaySeller
    image: EbayImage
    thumbnailImages: list[EbayImage]
    additionalImages: list[EbayImage]
    categories: list[EbayCategoryInfo]
    buyingOptions: list[str]
    shippingOptions: list[dict]
    itemCreationDate: str
    itemEndDate: str


class EbayBrowseResponse(TypedDict, total=False):
    """Full response of ``/buy/browse/v1/item_summary/search``."""

    itemSummaries: list[EbayItemSummary]
    total: int
    next: str
    limit: int
    offset: int
    warnings: list[dict]


# --- Aggregated output for the GoupixDex internal API -----------------------


GradedFilter = Literal["raw", "psa", "cgc", "bgs", "all"]
ConditionFilter = Literal["new", "used", "all"]
SortOrder = Literal["price_asc", "price_desc", "relevance", "newly_listed"]


class MarketGradedInfo(TypedDict):
    """Grading info extracted from item aspects (when present)."""

    grader: str
    grade: str


class MarketStats(TypedDict):
    """Aggregate price stats over the returned listings (EUR)."""

    count: int
    min: float | None
    median: float | None
    max: float | None
    avg: float | None


class MarketListing(TypedDict, total=False):
    """Normalized listing returned to the frontend."""

    item_id: str
    title: str
    price_eur: float
    currency: str
    condition: str
    seller_username: str
    seller_country: str
    seller_feedback_score: int | None
    image_url: str | None
    listing_url: str
    buying_options: list[str]
    graded: NotRequired[MarketGradedInfo | None]


class MarketSearchResponse(TypedDict):
    """Top-level response from ``/ebay/market/search``."""

    query: str
    effective_query: str
    marketplace_id: str
    period_days: int
    filters_applied: dict
    stats: MarketStats
    items: list[MarketListing]
    outliers: list[MarketListing]
    outliers_excluded: int
    total_matches: int
    warnings: list[str]
