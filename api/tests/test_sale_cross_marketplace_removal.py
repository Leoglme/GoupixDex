"""Vente enregistrée sur une marketplace : quelles annonces des autres marketplaces sont retirées, et de quel article."""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from typing import Any

import pytest
from fastapi import BackgroundTasks
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import models  # noqa: F401
from models.article import Article
from models.base import Base
from models.user import User
from routes.articles import mark_sold
from schemas.articles import SoldPatch
from services.article_service import article_to_dict
from services.cross_marketplace_removal_service import run_background_ebay_removal_after_sale

USER_ID = 1
TITLE = "Piafabec / Spearow m1l 074/063 AR - Mega Brave - Pokémon Japonais"


@pytest.fixture
def db() -> Iterator[Session]:
    """Base SQLite en mémoire avec le schéma complet."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def listed_article(
    db: Session,
    *,
    vinted_id: int | None = 10161741375,
    leboncoin_listing_id: str | None = "3278046037",
    ebay_listing_id: str | None = "820179226113",
) -> Article:
    """Article en vente sur les marketplaces dont l'identifiant d'annonce est donné."""
    article = Article(
        user_id=USER_ID,
        title=TITLE,
        description="",
        purchase_price=Decimal("1.00"),
        sell_price=Decimal("2.50"),
        published_on_vinted=vinted_id is not None,
        vinted_id=vinted_id,
        published_on_leboncoin=leboncoin_listing_id is not None,
        leboncoin_listing_id=leboncoin_listing_id,
        published_on_ebay=ebay_listing_id is not None,
        ebay_listing_id=ebay_listing_id,
        ebay_inventory_sku=f"gpx{ebay_listing_id}" if ebay_listing_id else None,
    )
    db.add(article)
    db.commit()
    db.refresh(article)
    return article


def sell(db: Session, article: Article, sale_source: str) -> tuple[dict[str, Any], BackgroundTasks]:
    """Enregistre la vente ; renvoie la fiche vendue et les tâches lancées par l'API."""
    background_tasks = BackgroundTasks()
    sold_article = mark_sold(
        article.id,
        SoldPatch(sold_price=Decimal("2.50"), sale_source=sale_source),  # type: ignore[arg-type]
        background_tasks,
        db,
        User(id=USER_ID, email="leo@example.test"),
    )
    return sold_article, background_tasks


def ebay_removals_scheduled(background_tasks: BackgroundTasks) -> list[tuple[Any, ...]]:
    """Articles dont l'API retire l'annonce eBay après la réponse."""
    return [task.args for task in background_tasks.tasks if task.func is run_background_ebay_removal_after_sale]


@pytest.mark.parametrize(
    ("sale_source", "is_vinted_removed_by_pc", "is_leboncoin_removed_by_pc", "is_ebay_removed_by_api"),
    [
        ("ebay", True, True, False),
        ("vinted", False, True, True),
        ("leboncoin", True, False, True),
    ],
)
def test_a_sale_removes_the_listings_left_on_the_other_marketplaces(
    db: Session,
    sale_source: str,
    is_vinted_removed_by_pc: bool,
    is_leboncoin_removed_by_pc: bool,
    is_ebay_removed_by_api: bool,
) -> None:
    article = listed_article(db)

    sold_article, background_tasks = sell(db, article, sale_source)

    assert sold_article["is_sold"] is True
    assert sold_article["pending_vinted_unlist"] is is_vinted_removed_by_pc
    assert sold_article["pending_leboncoin_unlist"] is is_leboncoin_removed_by_pc
    assert ebay_removals_scheduled(background_tasks) == ([(article.id, USER_ID)] if is_ebay_removed_by_api else [])


@pytest.mark.parametrize("sale_source", ["ebay", "vinted", "leboncoin"])
def test_a_card_listed_only_where_it_sold_leaves_nothing_to_remove(db: Session, sale_source: str) -> None:
    article = listed_article(
        db,
        vinted_id=10161741375 if sale_source == "vinted" else None,
        leboncoin_listing_id="3278046037" if sale_source == "leboncoin" else None,
        ebay_listing_id="820179226113" if sale_source == "ebay" else None,
    )

    sold_article, background_tasks = sell(db, article, sale_source)

    assert sold_article["pending_vinted_unlist"] is False
    assert sold_article["pending_leboncoin_unlist"] is False
    assert ebay_removals_scheduled(background_tasks) == []


@pytest.mark.parametrize("sale_source", ["ebay", "vinted", "leboncoin"])
def test_selling_one_copy_leaves_the_other_copy_on_sale_everywhere(db: Session, sale_source: str) -> None:
    sold_copy = listed_article(db)
    kept_copy = listed_article(
        db, vinted_id=10161810119, leboncoin_listing_id="3278047139", ebay_listing_id="820179286165"
    )

    _, background_tasks = sell(db, sold_copy, sale_source)

    db.refresh(kept_copy)
    kept_copy_state = article_to_dict(kept_copy)
    assert kept_copy_state["is_sold"] is False
    assert kept_copy_state["published_on_vinted"] is True
    assert kept_copy_state["published_on_leboncoin"] is True
    assert kept_copy_state["published_on_ebay"] is True
    assert kept_copy_state["pending_vinted_unlist"] is False
    assert kept_copy_state["pending_leboncoin_unlist"] is False
    assert all(article_id == sold_copy.id for article_id, _ in ebay_removals_scheduled(background_tasks))
