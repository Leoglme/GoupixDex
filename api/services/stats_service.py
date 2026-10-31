"""Dashboard aggregates: sales over a chosen period and the stock currently for sale."""

from __future__ import annotations

import bisect
import datetime as dt
import statistics
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from models.article import Article
from services import article_service

Period = Literal["daily", "weekly", "monthly"]
SALE_SOURCES: tuple[str, ...] = ("vinted", "ebay", "leboncoin")
#: Lignes de chaque liste du tableau de bord (dernières ventes, plus rentables, plus rapides).
DASHBOARD_LIST_LIMIT = 5
#: Articles du stock montrés sous « En vente depuis le plus longtemps ».
INVENTORY_LONGEST_LISTED_LIMIT = 3
#: Garde-fou sur le nombre de tranches de la courbe.
MAX_TIMELINE_BUCKETS = 5000


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


def _first_image_url(article: Article) -> str | None:
    """Première photo de l'article (celle des listes « Mes articles »), ``None`` sans photo."""
    return article.images[0].image_url if article.images else None


def article_sale_row_dict(article: Article) -> dict[str, Any]:
    """One sold article row for dashboard / sold-sales listings."""
    proceeds = _sale_proceeds_eur(article)
    hours_to_sell = _hours_to_sell(article)
    return {
        "article_id": article.id,
        "title": article.title,
        "pokemon_name": article.pokemon_name,
        "image_url": _first_image_url(article),
        "sold_at": article.sold_at.isoformat() if article.sold_at else None,
        "listing_price_eur": float(article.sell_price) if article.sell_price is not None else None,
        "sold_price_eur": float(article.sold_price) if article.sold_price is not None else None,
        "realized_price_eur": round(proceeds, 2) if proceeds is not None else None,
        "sale_source": article.sale_source,
        "purchase_price_eur": float(article.purchase_price),
        "profit_eur": round(_profit_eur(article), 2),
        "hours_to_sell": round(hours_to_sell, 1) if hours_to_sell is not None else None,
    }


def _inventory_row_dict(article: Article) -> dict[str, Any]:
    """Un article du stock pour « En vente depuis le plus longtemps »."""
    return {
        "article_id": article.id,
        "title": article.title,
        "pokemon_name": article.pokemon_name,
        "image_url": _first_image_url(article),
        "created_at": article.created_at.isoformat() if article.created_at else None,
        "sell_price_eur": float(article.sell_price) if article.sell_price is not None else None,
    }


def list_sold_sales(
    db: Session,
    user_id: int,
    *,
    sale_source: str | None = None,
) -> dict[str, Any]:
    """
    All sold articles for the user, newest first.

    ``sale_source`` may be ``vinted``, ``ebay``, ``leboncoin``, or omitted for every channel.
    """
    rows = article_service.list_articles_for_user(db, user_id)
    sold = [a for a in rows if a.is_sold]
    src = (sale_source or "").strip().lower()
    if src in SALE_SOURCES:
        sold = [a for a in sold if (a.sale_source or "").lower() == src]

    sold.sort(key=lambda a: _as_utc(a.sold_at) or dt.datetime.min.replace(tzinfo=dt.UTC), reverse=True)
    sales = [article_sale_row_dict(a) for a in sold]

    revenue_eur = sum(p for a in sold for p in [_sale_proceeds_eur(a)] if p is not None)
    profit_eur = sum(_profit_eur(a) for a in sold)
    channel_split = _channel_split(sold)

    return {
        "sales": sales,
        "count": len(sales),
        "revenue_eur": round(revenue_eur, 2),
        "profit_eur": round(profit_eur, 2),
        **{f"{source}_count": channel_split[f"{source}_count"] for source in SALE_SOURCES},
    }


def _channel_split(sold: list[Article]) -> dict[str, Any]:
    """Nombre de ventes et chiffre d’affaires de chaque canal (``vinted_count``, ``vinted_revenue_eur``…)."""
    split: dict[str, Any] = {}
    for source in SALE_SOURCES:
        sold_on_source = [a for a in sold if (a.sale_source or "").lower() == source]
        split[f"{source}_count"] = len(sold_on_source)
        split[f"{source}_revenue_eur"] = round(
            sum(p for a in sold_on_source for p in [_sale_proceeds_eur(a)] if p is not None), 2
        )
    return split


def _sales_by_channel(sold: list[Article]) -> list[dict[str, Any]]:
    """Chiffre d'affaires, bénéfice et nombre de ventes de chaque canal, dans l'ordre Vinted, eBay, Leboncoin."""
    return [
        {
            "sale_source": source,
            **_sales_totals([a for a in sold if (a.sale_source or "").lower() == source]),
        }
        for source in SALE_SOURCES
    ]


def _user_timezone(name: str | None) -> dt.tzinfo:
    """Fuseau IANA envoyé par le navigateur (jours et mois de la courbe), UTC s'il est inconnu."""
    if not name:
        return dt.UTC
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return dt.UTC


def _local(value: dt.datetime, tz: dt.tzinfo) -> dt.datetime:
    """Heure locale de l'utilisateur, sans fuseau (pour découper ses jours et ses mois)."""
    return value.astimezone(tz).replace(tzinfo=None)


def _auto_period(start: dt.datetime, end: dt.datetime) -> Period:
    """Granularité de la courbe d'après la durée affichée."""
    days = (end - start).total_seconds() / 86400
    if days <= 45:
        return "daily"
    if days <= 190:
        return "weekly"
    return "monthly"


def _next_bucket(cursor: dt.datetime, period: Period) -> dt.datetime:
    if period == "monthly":
        return (cursor.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
    return cursor + dt.timedelta(days=7 if period == "weekly" else 1)


def _timeline_bucket_starts(
    start: dt.datetime, end: dt.datetime, period: Period, tz: dt.tzinfo
) -> list[dt.datetime]:
    """Débuts locaux des tranches couvrant [start, end] : jours, semaines comptées depuis ``start``, mois calendaires."""
    cursor = _local(start, tz).replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "monthly":
        cursor = cursor.replace(day=1)
    local_end = _local(end, tz)
    buckets: list[dt.datetime] = []
    while cursor <= local_end and len(buckets) < MAX_TIMELINE_BUCKETS:
        buckets.append(cursor)
        cursor = _next_bucket(cursor, period)
    return buckets


def _sales_timeline(
    sold: list[Article], start: dt.datetime, end: dt.datetime, period: Period, tz: dt.tzinfo
) -> list[dict[str, Any]]:
    """Chiffre d'affaires, bénéfice et nombre de ventes de chaque tranche de la période."""
    bucket_starts = _timeline_bucket_starts(start, end, period, tz)
    totals = [{"revenue": 0.0, "profit": 0.0, "count": 0} for _ in bucket_starts]
    for article in sold:
        sold_at = _as_utc(article.sold_at)
        if sold_at is None:
            continue
        index = bisect.bisect_right(bucket_starts, _local(sold_at, tz)) - 1
        if index < 0:
            continue
        totals[index]["revenue"] += _sale_proceeds_eur(article) or 0.0
        totals[index]["profit"] += _profit_eur(article)
        totals[index]["count"] += 1
    return [
        {
            "date": bucket_start.replace(tzinfo=tz).astimezone(dt.UTC).isoformat(),
            "revenue_eur": round(total["revenue"], 2),
            "profit_eur": round(total["profit"], 2),
            "sales_count": total["count"],
        }
        for bucket_start, total in zip(bucket_starts, totals, strict=True)
    ]


def _sold_between(sold: list[Article], start: dt.datetime, end: dt.datetime, *, include_end: bool) -> list[Article]:
    """Ventes datées entre ``start`` et ``end`` (``end`` exclu sans ``include_end``)."""
    selected: list[Article] = []
    for article in sold:
        sold_at = _as_utc(article.sold_at)
        if sold_at is None or sold_at < start:
            continue
        if sold_at < end or (include_end and sold_at == end):
            selected.append(article)
    return selected


def _sales_totals(sold: list[Article]) -> dict[str, Any]:
    return {
        "revenue_eur": round(sum(p for a in sold for p in [_sale_proceeds_eur(a)] if p is not None), 2),
        "profit_eur": round(sum(_profit_eur(a) for a in sold), 2),
        "sales_count": len(sold),
    }


def compute_dashboard_stats(
    db: Session,
    user_id: int,
    *,
    range_start: dt.datetime | None = None,
    range_end: dt.datetime | None = None,
    period: Period | None = None,
    timezone: str | None = None,
) -> dict[str, Any]:
    """Ventes de la période choisie (chiffres, comparaison, courbe, canaux, listes) et stock en vente.

    Tout suit ``range_start``/``range_end`` sauf le stock, qui décrit les articles en vente aujourd'hui.
    La courbe commence à la première vente quand la période remonte plus loin (« Depuis toujours »),
    et la période précédente de même durée n'existe que si l'historique la couvre.
    ``period`` absent : jour, semaine ou mois selon la durée affichée.
    """
    now = dt.datetime.now(dt.UTC)
    range_end = _as_utc(range_end) or now
    range_start = _as_utc(range_start) or range_end - dt.timedelta(days=30)
    if range_start > range_end:
        range_start, range_end = range_end, range_start
    tz = _user_timezone(timezone)

    rows = article_service.list_articles_for_user(db, user_id)
    sold = [a for a in rows if a.is_sold]
    created_dates = [created for a in rows if (created := _as_utc(a.created_at)) is not None]
    sale_dates = [sold_at for a in sold if (sold_at := _as_utc(a.sold_at)) is not None]
    first_activity = min(created_dates, default=None)
    first_sale = min(sale_dates, default=first_activity)
    has_history_before_range = first_activity is not None and first_activity < range_start
    shown_start = range_start if has_history_before_range or first_sale is None else max(range_start, first_sale)

    sold_in_range = _sold_between(sold, range_start, range_end, include_end=True)
    previous_period: dict[str, Any] | None = None
    if has_history_before_range:
        previous_start = range_start - (range_end - range_start)
        previous_period = {
            "start": previous_start.isoformat(),
            "end": range_start.isoformat(),
            **_sales_totals(_sold_between(sold, previous_start, range_start, include_end=False)),
        }

    totals = _sales_totals(sold_in_range)
    timed_sales = [(a, hours) for a in sold_in_range if (hours := _hours_to_sell(a)) is not None]
    timeline_period = period or _auto_period(shown_start, range_end)

    by_recency = sorted(sold_in_range, key=lambda a: _as_utc(a.sold_at) or now, reverse=True)
    by_profit = sorted(sold_in_range, key=_profit_eur, reverse=True)
    by_speed = [a for a, _ in sorted(timed_sales, key=lambda timed: timed[1])]

    for_sale = [a for a in rows if not a.is_sold and a.offers_for_sale]
    longest_listed = sorted(for_sale, key=lambda a: _as_utc(a.created_at) or now)

    return {
        "range": {
            "start": shown_start.isoformat(),
            "end": range_end.isoformat(),
            "period": timeline_period,
        },
        "revenue_period_eur": totals["revenue_eur"],
        "profit_period_eur": totals["profit_eur"],
        "period_sales_count": totals["sales_count"],
        "median_hours_to_sell": round(statistics.median(h for _, h in timed_sales), 1) if timed_sales else None,
        "previous_period": previous_period,
        "sales_by_channel": _sales_by_channel(sold_in_range),
        "sales_timeline": _sales_timeline(sold_in_range, shown_start, range_end, timeline_period, tz),
        "recent_sales": [article_sale_row_dict(a) for a in by_recency[:DASHBOARD_LIST_LIMIT]],
        "top_profitable": [article_sale_row_dict(a) for a in by_profit[:DASHBOARD_LIST_LIMIT]],
        "fastest_sold": [article_sale_row_dict(a) for a in by_speed[:DASHBOARD_LIST_LIMIT]],
        "inventory_count": len(for_sale),
        "inventory_purchase_total_eur": round(sum(float(a.purchase_price) for a in for_sale), 2),
        "inventory_sell_total_eur": round(sum(float(a.sell_price) for a in for_sale if a.sell_price is not None), 2),
        "inventory_estimated_profit_eur": round(
            sum(float(a.sell_price) - float(a.purchase_price) for a in for_sale if a.sell_price is not None), 2
        ),
        "inventory_longest_listed": [
            _inventory_row_dict(a) for a in longest_listed[:INVENTORY_LONGEST_LISTED_LIMIT]
        ],
    }
