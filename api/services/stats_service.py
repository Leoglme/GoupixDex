"""Dashboard aggregates (DB + optional PokéWallet market value)."""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy.orm import Session

from models.article import Article
from services import article_service
from services.pricing_service import fetch_card_prices


def _as_utc(value: dt.datetime | None) -> dt.datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=dt.UTC)
    return value.astimezone(dt.UTC)


def _profit_eur(article: Article) -> float:
    if not article.is_sold or article.sell_price is None:
        return 0.0
    return float(article.sell_price - article.purchase_price)


def _hours_to_sell(article: Article) -> float | None:
    sold_at = _as_utc(article.sold_at)
    created_at = _as_utc(article.created_at)
    if sold_at is None or created_at is None:
        return None
    delta = sold_at - created_at
    return max(0.0, delta.total_seconds() / 3600.0)


def compute_dashboard_stats(
    db: Session,
    user_id: int,
    *,
    include_market: bool = False,
) -> dict[str, Any]:
    """Profit windows, rankings, Vinted revenue, optional sum of Cardmarket refs for inventory."""
    now = dt.datetime.now(dt.UTC)
    week_start = now - dt.timedelta(days=7)
    month_start = now - dt.timedelta(days=30)

    rows = article_service.list_articles_for_user(db, user_id)
    sold = [a for a in rows if a.is_sold]

    def in_week(a: Article) -> bool:
        sold_at = _as_utc(a.sold_at)
        return bool(sold_at and sold_at >= week_start)

    def in_month(a: Article) -> bool:
        sold_at = _as_utc(a.sold_at)
        return bool(sold_at and sold_at >= month_start)

    profit_week = sum(_profit_eur(a) for a in sold if in_week(a))
    profit_month = sum(_profit_eur(a) for a in sold if in_month(a))
    profit_total = sum(_profit_eur(a) for a in sold)

    vinted_revenue = sum(
        float(a.sell_price) for a in sold if a.sell_price is not None
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

    # Cumulative revenue by month (sell price of sold articles)
    monthly_revenue: dict[str, float] = {}
    for a in sold:
        sold_at = _as_utc(a.sold_at)
        if sold_at is None or a.sell_price is None:
            continue
        key = sold_at.strftime("%Y-%m")
        monthly_revenue[key] = monthly_revenue.get(key, 0.0) + float(a.sell_price)
    revenue_timeline: list[dict[str, Any]] = []
    cumulative_rev = 0.0
    for month_key in sorted(monthly_revenue.keys()):
        incremental = monthly_revenue[month_key]
        cumulative_rev += incremental
        revenue_timeline.append(
            {
                "month": month_key,
                "revenue_month_eur": round(incremental, 2),
                "revenue_cumulative_eur": round(cumulative_rev, 2),
            }
        )

    recent_sales = sorted(
        sold,
        key=lambda a: _as_utc(a.sold_at) or now,
        reverse=True,
    )[:30]
    recent_sales_payload = [
        {
            "article_id": a.id,
            "title": a.title,
            "pokemon_name": a.pokemon_name,
            "sold_at": a.sold_at.isoformat() if a.sold_at else None,
            "sell_price_eur": float(a.sell_price) if a.sell_price is not None else None,
            "purchase_price_eur": float(a.purchase_price),
            "profit_eur": round(_profit_eur(a), 2),
        }
        for a in recent_sales
    ]

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
        "profit_week_eur": round(profit_week, 2),
        "profit_month_eur": round(profit_month, 2),
        "profit_total_eur": round(profit_total, 2),
        "vinted_revenue_eur": round(vinted_revenue, 2),
        "inventory_count": inventory_count,
        "inventory_purchase_total_eur": round(inventory_purchase_total_eur, 2),
        "inventory_sell_total_eur": round(inventory_sell_total_eur, 2),
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
