"""Article persistence and serialization helpers."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session, joinedload

from models.article import Article
from models.image import Image


def list_articles_for_user(db: Session, user_id: int) -> list[Article]:
    return (
        db.query(Article)
        .options(joinedload(Article.images))
        .filter(Article.user_id == user_id)
        .order_by(Article.created_at.desc())
        .all()
    )


def get_article(db: Session, article_id: int, user_id: int | None = None) -> Article | None:
    q = db.query(Article).options(joinedload(Article.images)).filter(Article.id == article_id)
    if user_id is not None:
        q = q.filter(Article.user_id == user_id)
    return q.first()


def article_to_dict(article: Article) -> dict[str, Any]:
    """Serialize article and nested images for JSON responses."""
    return {
        "id": article.id,
        "user_id": article.user_id,
        "title": article.title,
        "description": article.description,
        "pokemon_name": article.pokemon_name,
        "set_code": article.set_code,
        "card_number": article.card_number,
        "condition": article.condition,
        "purchase_price": float(article.purchase_price),
        "sell_price": float(article.sell_price) if article.sell_price is not None else None,
        "is_sold": article.is_sold,
        "created_at": article.created_at.isoformat(),
        "sold_at": article.sold_at.isoformat() if article.sold_at else None,
        "images": [{"id": img.id, "image_url": img.image_url, "created_at": img.created_at.isoformat()} for img in article.images],
    }


def update_article_fields(
    article: Article,
    *,
    title: str | None = None,
    description: str | None = None,
    pokemon_name: str | None = None,
    set_code: str | None = None,
    card_number: str | None = None,
    condition: str | None = None,
    purchase_price: Decimal | None = None,
    sell_price: Decimal | None = None,
) -> None:
    if title is not None:
        article.title = title
    if description is not None:
        article.description = description
    if pokemon_name is not None:
        article.pokemon_name = pokemon_name
    if set_code is not None:
        article.set_code = set_code
    if card_number is not None:
        article.card_number = card_number
    if condition is not None:
        article.condition = condition
    if purchase_price is not None:
        article.purchase_price = purchase_price
    if sell_price is not None:
        article.sell_price = sell_price
