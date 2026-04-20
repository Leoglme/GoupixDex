"""Aggregate price statistics (min / median / avg / max) over eBay market listings.

Also provides outlier detection to filter out obviously off-topic listings
(e.g. a card sleeve listed at 1 EUR when the real product sells for 90 EUR).
"""

from __future__ import annotations

from statistics import median
from typing import Iterable

from app_types.ebay_browse import MarketListing, MarketStats

#: MAD multiplier above which an item is considered a statistical outlier.
#: 3.5 is conservative (keeps ~99.9 % of a normal sample); we combine it with
#: a ratio-based safeguard below because MAD is unreliable on tiny samples.
_MAD_THRESHOLD = 3.5

#: Consistent rescaling factor for a normal distribution (so MAD * k ≈ sigma).
_MAD_SIGMA_SCALE = 1.4826

#: Ratio guard: an item is always an outlier when its price is < median / 5
#: or > median * 5, regardless of MAD (catches "1 EUR sleeve in ETB search").
_RATIO_LOW = 0.2
_RATIO_HIGH = 5.0

#: Minimum number of listings required to run MAD-based detection.
_MIN_FOR_MAD = 4


def aggregate_prices(listings: Iterable[MarketListing]) -> MarketStats:
    """
    Compute ``count`` / ``min`` / ``median`` / ``avg`` / ``max`` over listing prices (EUR).

    Zero or negative prices are ignored (they should already be filtered upstream).
    Returns a stats block with ``None`` values when the iterable is empty.
    """
    prices = [float(item["price_eur"]) for item in listings if item.get("price_eur")]
    prices = [p for p in prices if p > 0]
    if not prices:
        return {"count": 0, "min": None, "median": None, "max": None, "avg": None}
    prices_sorted = sorted(prices)
    return {
        "count": len(prices_sorted),
        "min": round(prices_sorted[0], 2),
        "median": round(median(prices_sorted), 2),
        "max": round(prices_sorted[-1], 2),
        "avg": round(sum(prices_sorted) / len(prices_sorted), 2),
    }


def partition_outliers(
    listings: list[MarketListing],
) -> tuple[list[MarketListing], list[MarketListing]]:
    """
    Split ``listings`` into ``(kept, outliers)`` based on price distribution.

    Strategy (applied on prices > 0):

    * Compute the median and a ratio guard: any price outside
      ``[median * 0.2, median * 5]`` is an outlier — catches the
      "1 EUR accessory in a 90 EUR product search" case even on small samples.
    * If enough items remain, run MAD-based detection (robust to outliers)
      to drop the remaining statistical stragglers.

    Non-priced listings are always kept.
    """
    if len(listings) < _MIN_FOR_MAD:
        return list(listings), []

    priced_pairs: list[tuple[int, float]] = [
        (i, float(l["price_eur"])) for i, l in enumerate(listings) if l.get("price_eur")
    ]
    if len(priced_pairs) < _MIN_FOR_MAD:
        return list(listings), []

    prices = [p for _, p in priced_pairs]
    med = median(prices)
    if med <= 0:
        return list(listings), []

    outlier_indexes: set[int] = set()

    for idx, price in priced_pairs:
        ratio = price / med
        if ratio < _RATIO_LOW or ratio > _RATIO_HIGH:
            outlier_indexes.add(idx)

    remaining = [(i, p) for i, p in priced_pairs if i not in outlier_indexes]
    if len(remaining) >= _MIN_FOR_MAD:
        rem_prices = [p for _, p in remaining]
        mad = median([abs(p - med) for p in rem_prices])
        if mad > 0:
            threshold = _MAD_THRESHOLD * _MAD_SIGMA_SCALE * mad
            for idx, price in remaining:
                if abs(price - med) > threshold:
                    outlier_indexes.add(idx)

    kept: list[MarketListing] = []
    outliers: list[MarketListing] = []
    for i, listing in enumerate(listings):
        if i in outlier_indexes:
            outliers.append(listing)
        else:
            kept.append(listing)
    return kept, outliers
