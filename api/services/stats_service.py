"""Dashboard aggregates (DB + optional PokéWallet market value)."""

from __future__ import annotations

import datetime as dt
from typing import Any, Literal

from sqlalchemy.orm import Session

from models.article import Article
from services import article_service
from services.pricing_service import fetch_card_prices

Period = Literal["daily", "weekly", "monthly"]


def _as_utc(value: dt.datetime | None) -> dt.datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=dt.UTC)
    return value.astimezone(dt.UTC)


def _sale_proceeds_eur(article: Article) -> float | None:
    """Proceeds: ``sold_price`` when set, otherwise legacy fallback to ``sell_price``."""
    if article.sold_price is not None:
        return float(article.sold_price)
    if article.sell_price is not None:
        return float(article.sell_price)
    return None


def _profit_eur(article: Article) -> float:
    if not article.is_sold:
        return 0.0
    proceeds = _sale_proceeds_eur(article)
    if proceeds is None:
        return 0.0
    return proceeds - float(article.purchase_price)


def _hours_to_sell(article: Article) -> float | None:
    sold_at = _as_utc(article.sold_at)
    created_at = _as_utc(article.created_at)
    if sold_at is None or created_at is None:
        return None
    delta = sold_at - created_at
    return max(0.0, delta.total_seconds() / 3600.0)


def _bucket_key(value: dt.datetime, period: Period) -> dt.datetime:
    """Truncate a UTC datetime to the start of its daily/weekly/monthly bucket."""
    if period == "monthly":
        return value.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    base = value.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "weekly":
        # Monday as week start
        return base - dt.timedelta(days=base.weekday())
    return base


def _iter_buckets(start: dt.datetime, end: dt.datetime, period: Period) -> list[dt.datetime]:
    """Inclusive list of bucket starts covering [start, end]."""
    if start > end:
        start, end = end, start
    cursor = _bucket_key(start, period)
    last = _bucket_key(end, period)
    buckets: list[dt.datetime] = []
    safety = 0
    while cursor <= last and safety < 5000:
        buckets.append(cursor)
        if period == "monthly":
            year, month = cursor.year, cursor.month + 1
            if month > 12:
                month = 1
                year += 1
            cursor = cursor.replace(year=year, month=month, day=1)
        elif period == "weekly":
            cursor = cursor + dt.timedelta(days=7)
        else:
            cursor = cursor + dt.timedelta(days=1)
        safety += 1
    return buckets


def compute_dashboard_stats(
    db: Session,
    user_id: int,
    *,
    include_market: bool = False,
    range_start: dt.datetime | None = None,
    range_end: dt.datetime | None = None,
    period: Period = "daily",
) -> dict[str, Any]:
    """Profit, revenue, channel split and per-period revenue timeline.

    The ``range_start``/``range_end``/``period`` arguments drive the windowed
    metrics ("profit_period_eur", "revenue_period_eur", split per channel and
    the ``revenue_timeline`` used by the chart). Totals (profit_total_eur,
    inventory…) ignore the range and reflect the whole catalogue.
    """
    now = dt.datetime.now(dt.UTC)
    if range_end is None:
        range_end = now
    if range_start is None:
        range_start = range_end - dt.timedelta(days=14)
    range_start = _as_utc(range_start) or now
    range_end = _as_utc(range_end) or now
    if range_start > range_end:
        range_start, range_end = range_end, range_start
    # Make the end inclusive (cover the full last day)
    range_end_inclusive = range_end.replace(hour=23, minute=59, second=59, microsecond=999_999)

    rows = article_service.list_articles_for_user(db, user_id)
    sold = [a for a in rows if a.is_sold]

    def in_range(a: Article) -> bool:
        sold_at = _as_utc(a.sold_at)
        return bool(sold_at and range_start <= sold_at <= range_end_inclusive)

    sold_in_range = [a for a in sold if in_range(a)]

    profit_period = sum(_profit_eur(a) for a in sold_in_range)
    revenue_period = sum(
        p for a in sold_in_range for p in [_sale_proceeds_eur(a)] if p is not None
    )
    period_sales_count = len(sold_in_range)

    profit_total = sum(_profit_eur(a) for a in sold)
    vinted_revenue_total = sum(
        p for a in sold for p in [_sale_proceeds_eur(a)] if p is not None
    )

    # Channel breakdown over the selected range (Vinted vs eBay)
    vinted_count = sum(1 for a in sold_in_range if a.sale_source == "vinted")
    ebay_count = sum(1 for a in sold_in_range if a.sale_source == "ebay")
    vinted_revenue_period = sum(
        p
        for a in sold_in_range
        if a.sale_source == "vinted"
        for p in [_sale_proceeds_eur(a)]
        if p is not None
    )
    ebay_revenue_period = sum(
        p
        for a in sold_in_range
        if a.sale_source == "ebay"
        for p in [_sale_proceeds_eur(a)]
        if p is not None
    )

    # Same split across all-time (used for the Vinted vs eBay pie)
    vinted_count_total = sum(1 for a in sold if a.sale_source == "vinted")
    ebay_count_total = sum(1 for a in sold if a.sale_source == "ebay")
    vinted_revenue_total_split = sum(
        p
        for a in sold
        if a.sale_source == "vinted"
        for p in [_sale_proceeds_eur(a)]
        if p is not None
    )
    ebay_revenue_total_split = sum(
        p
        for a in sold
        if a.sale_source == "ebay"
        for p in [_sale_proceeds_eur(a)]
        if p is not None
    )

    top_profitable = sorted(sold, key=_profit_eur, reverse=True)[:5]
    with_duration = [(a, _hours_to_sell(a)) for a in sold]
    with_duration = [(a, h) for a, h in with_duration if h is not None]
    fastest = sorted(with_duration, key=lambda x: x[1])[:5]

    unsold = [a for a in rows if not a.is_sold]
    inventory_count = len(unsold)
    inventory_purchase_total_eur = sum(float(a.purchase_price) for a in unsold)
    inventory_sell_total_eur = sum(
        float(a.sell_price) for a in unsold if a.sell_price is not None
    )
    inventory_estimated_profit_eur = sum(
        float(a.sell_price) - float(a.purchase_price)
        for a in unsold
        if a.sell_price is not None
    )

    # Revenue timeline: bucketed per period within the selected range
    buckets = _iter_buckets(range_start, range_end_inclusive, period)
    bucket_totals: dict[dt.datetime, float] = {b: 0.0 for b in buckets}
    for a in sold_in_range:
        sold_at = _as_utc(a.sold_at)
        proceeds = _sale_proceeds_eur(a)
        if sold_at is None or proceeds is None:
            continue
        key = _bucket_key(sold_at, period)
        if key in bucket_totals:
            bucket_totals[key] += proceeds
    revenue_timeline: list[dict[str, Any]] = [
        {
            "date": b.isoformat(),
            "revenue_eur": round(v, 2),
        }
        for b, v in bucket_totals.items()
    ]

    recent_sales = sorted(
        sold,
        key=lambda a: _as_utc(a.sold_at) or now,
        reverse=True,
    )[:30]
    recent_sales_payload = []
    for a in recent_sales:
        proceeds = _sale_proceeds_eur(a)
        recent_sales_payload.append(
            {
                "article_id": a.id,
                "title": a.title,
                "pokemon_name": a.pokemon_name,
                "sold_at": a.sold_at.isoformat() if a.sold_at else None,
                "listing_price_eur": float(a.sell_price) if a.sell_price is not None else None,
                "sold_price_eur": float(a.sold_price) if a.sold_price is not None else None,
                "realized_price_eur": round(proceeds, 2) if proceeds is not None else None,
                "sale_source": a.sale_source,
                "purchase_price_eur": float(a.purchase_price),
                "profit_eur": round(_profit_eur(a), 2),
            }
        )

    market_sum: float | None = None
    market_sum_unsold: float | None = None
    market_errors = 0
    if include_market:
        market_sum = 0.0
        market_sum_unsold = 0.0
        for a in rows:
            if not a.set_code or not a.card_number:
                continue
            p = fetch_card_prices(a.set_code, a.card_number, a.pokemon_name)
            if p.get("error"):
                market_errors += 1
            cm = p.get("cardmarket_eur")
            if cm is not None:
                v = float(cm)
                market_sum += v
                if not a.is_sold:
                    market_sum_unsold += v

    return {
        "range": {
            "start": range_start.isoformat(),
            "end": range_end.isoformat(),
            "period": period,
        },
        "profit_period_eur": round(profit_period, 2),
        "revenue_period_eur": round(revenue_period, 2),
        "period_sales_count": period_sales_count,
        "profit_total_eur": round(profit_total, 2),
        "vinted_revenue_eur": round(vinted_revenue_total, 2),
        "channel_split_period": {
            "vinted_count": vinted_count,
            "ebay_count": ebay_count,
            "vinted_revenue_eur": round(vinted_revenue_period, 2),
            "ebay_revenue_eur": round(ebay_revenue_period, 2),
        },
        "channel_split_total": {
            "vinted_count": vinted_count_total,
            "ebay_count": ebay_count_total,
            "vinted_revenue_eur": round(vinted_revenue_total_split, 2),
            "ebay_revenue_eur": round(ebay_revenue_total_split, 2),
        },
        "inventory_count": inventory_count,
        "inventory_purchase_total_eur": round(inventory_purchase_total_eur, 2),
        "inventory_sell_total_eur": round(inventory_sell_total_eur, 2),
        "inventory_estimated_profit_eur": round(inventory_estimated_profit_eur, 2),
        "estimated_cardmarket_inventory_eur": round(market_sum, 2) if market_sum is not None else None,
        "estimated_cardmarket_unsold_eur": round(market_sum_unsold, 2)
        if market_sum_unsold is not None
        else None,
        "market_lookup_errors": market_errors,
        "revenue_timeline": revenue_timeline,
        "recent_sales": recent_sales_payload,
        "top_profitable": [
            {
                "article_id": a.id,
                "title": a.title,
                "pokemon_name": a.pokemon_name,
                "profit_eur": round(_profit_eur(a), 2),
            }
            for a in top_profitable
        ],
        "fastest_sold": [
            {
                "article_id": a.id,
                "title": a.title,
                "pokemon_name": a.pokemon_name,
                "hours_to_sell": round(h, 1),
            }
            for a, h in fastest
        ],
    }
