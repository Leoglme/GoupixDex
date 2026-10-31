"""Tableau de bord « Ventes » : tout suit la période choisie, sauf le stock en vente."""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import models  # noqa: F401 — enregistre tous les mappers (relations croisées entre modèles)
from models.article import Article
from models.base import Base
from models.image import Image
from services.stats_service import compute_dashboard_stats

NOW = dt.datetime(2026, 10, 31, 15, 0, tzinfo=dt.UTC)


@pytest.fixture
def db() -> Iterator[Session]:
    """Base SQLite en mémoire avec le schéma complet."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _article(
    db: Session,
    title: str,
    *,
    created_days_ago: float,
    sold_days_ago: float | None = None,
    purchase: str = "10",
    sold_price: str | None = None,
    sell_price: str | None = None,
    sale_source: str | None = None,
    offers_for_sale: bool = True,
) -> Article:
    article = Article(
        user_id=1,
        title=title,
        description="",
        purchase_price=Decimal(purchase),
        sell_price=Decimal(sell_price) if sell_price else None,
        sold_price=Decimal(sold_price) if sold_price else None,
        sale_source=sale_source,
        is_sold=sold_days_ago is not None,
        offers_for_sale=offers_for_sale,
        created_at=NOW - dt.timedelta(days=created_days_ago),
        sold_at=NOW - dt.timedelta(days=sold_days_ago) if sold_days_ago is not None else None,
    )
    db.add(article)
    db.commit()
    db.refresh(article)
    return article


def _last_days(days: int) -> tuple[dt.datetime, dt.datetime]:
    return NOW - dt.timedelta(days=days), NOW


def test_lists_and_totals_only_keep_sales_of_the_period(db: Session) -> None:
    _article(db, "Dracaufeu", created_days_ago=3, sold_days_ago=1, sold_price="90", purchase="40", sale_source="vinted")
    _article(db, "Mew", created_days_ago=60, sold_days_ago=40, sold_price="200", purchase="20", sale_source="ebay")

    start, end = _last_days(7)
    stats = compute_dashboard_stats(db, 1, range_start=start, range_end=end)

    assert stats["revenue_period_eur"] == 90
    assert stats["profit_period_eur"] == 50
    assert stats["period_sales_count"] == 1
    for listing in ("recent_sales", "top_profitable", "fastest_sold"):
        assert [row["title"] for row in stats[listing]] == ["Dracaufeu"]
    assert [channel["sales_count"] for channel in stats["sales_by_channel"]] == [1, 0, 0]
    assert stats["median_hours_to_sell"] == 48


def test_stock_ignores_the_period_and_withdrawn_articles(db: Session) -> None:
    oldest = _article(db, "Zacian", created_days_ago=74, sell_price="45", purchase="20")
    db.add(Image(article_id=oldest.id, image_url="https://img.example/zacian.jpg"))
    db.commit()
    _article(db, "Ronflex", created_days_ago=2, sell_price="6", purchase="1")
    _article(db, "Retiré", created_days_ago=90, sell_price="99", purchase="50", offers_for_sale=False)

    start, end = _last_days(7)
    stats = compute_dashboard_stats(db, 1, range_start=start, range_end=end)

    assert stats["inventory_count"] == 2
    assert stats["inventory_sell_total_eur"] == 51
    assert stats["inventory_purchase_total_eur"] == 21
    assert stats["inventory_estimated_profit_eur"] == 30
    assert [row["title"] for row in stats["inventory_longest_listed"]] == ["Zacian", "Ronflex"]
    assert stats["inventory_longest_listed"][0]["image_url"] == "https://img.example/zacian.jpg"


def test_previous_period_of_same_length_is_compared(db: Session) -> None:
    _article(db, "Ancien", created_days_ago=200, sold_days_ago=180, sold_price="5", purchase="1")
    _article(db, "Avant", created_days_ago=12, sold_days_ago=10, sold_price="30", purchase="10")
    _article(db, "Pendant", created_days_ago=4, sold_days_ago=2, sold_price="45", purchase="15")

    start, end = _last_days(7)
    stats = compute_dashboard_stats(db, 1, range_start=start, range_end=end)

    previous = stats["previous_period"]
    assert previous is not None
    assert (previous["revenue_eur"], previous["profit_eur"], previous["sales_count"]) == (30, 20, 1)


def test_whole_history_starts_at_first_sale_without_previous_period(db: Session) -> None:
    _article(db, "Premier", created_days_ago=80, sold_days_ago=60, sold_price="12", purchase="4")
    _article(db, "Stock", created_days_ago=90, sell_price="9", purchase="3")

    stats = compute_dashboard_stats(db, 1, range_start=dt.datetime(2000, 1, 1, tzinfo=dt.UTC), range_end=NOW)

    assert stats["previous_period"] is None
    assert stats["range"]["start"] == (NOW - dt.timedelta(days=60)).isoformat()
    assert stats["range"]["period"] == "weekly"
    assert len(stats["sales_timeline"]) == 9
    assert sum(point["sales_count"] for point in stats["sales_timeline"]) == 1


def test_timeline_days_follow_the_user_time_zone(db: Session) -> None:
    article = _article(db, "Nocturne", created_days_ago=20, sold_price="10", purchase="2")
    half_past_midnight_october_31_in_paris = dt.datetime(2026, 10, 30, 23, 30, tzinfo=dt.UTC)
    article.is_sold = True
    article.sold_at = half_past_midnight_october_31_in_paris
    db.commit()

    paris_start = dt.datetime(2026, 10, 24, 22, 0, tzinfo=dt.UTC)
    stats = compute_dashboard_stats(db, 1, range_start=paris_start, range_end=NOW, timezone="Europe/Paris")

    timeline = stats["sales_timeline"]
    assert len(timeline) == 7
    assert timeline[-1]["date"] == "2026-10-30T23:00:00+00:00"
    assert timeline[-1]["sales_count"] == 1
