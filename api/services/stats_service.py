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
    include_market: bool = True,
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

    weekly_map: dict[str, float] = {}
    for a in sold:
        sold_at = _as_utc(a.sold_at)
        if not sold_at:
            continue
        iso = sold_at.date().isocalendar()
        key = f"{iso.year}-W{iso.week:02d}"
        weekly_map[key] = weekly_map.get(key, 0.0) + _profit_eur(a)
    weekly_sold_profit = [
        {"week": k, "profit_eur": round(v, 2)} for k, v in sorted(weekly_map.items())
    ][-12:]

    market_sum: float | None = None
    market_errors = 0
    if include_market:
        market_sum = 0.0
        for a in rows:
            if not a.set_code or not a.card_number:
                continue
            p = fetch_card_prices(a.set_code, a.card_number, a.pokemon_name)
            if p.get("error"):
                market_errors += 1
            cm = p.get("cardmarket_eur")
            if cm is not None:
                market_sum += float(cm)

    return {
        "profit_week_eur": round(profit_week, 2),
        "profit_month_eur": round(profit_month, 2),
        "profit_total_eur": round(profit_total, 2),
        "vinted_revenue_eur": round(vinted_revenue, 2),
        "estimated_cardmarket_inventory_eur": round(market_sum, 2) if market_sum is not None else None,
        "market_lookup_errors": market_errors,
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
        "weekly_sold_profit": weekly_sold_profit,
    }
