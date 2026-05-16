"""Article persistence and serialization helpers."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session, joinedload

from core.database import SessionLocal
from models.article import Article
from models.cardmarket_order_line import CardmarketOrderLine
from schemas.articles import ArticleUpdate


def list_articles_for_user(db: Session, user_id: int) -> list[Article]:
    return (
        db.query(Article)
        .options(
            joinedload(Article.images),
            joinedload(Article.order_line).joinedload(CardmarketOrderLine.order),
        )
        .filter(Article.user_id == user_id)
        .order_by(Article.created_at.desc())
        .all()
    )


def get_article(db: Session, article_id: int, user_id: int | None = None) -> Article | None:
    q = (
        db.query(Article)
        .options(
            joinedload(Article.images),
            joinedload(Article.order_line).joinedload(CardmarketOrderLine.order),
        )
        .filter(Article.id == article_id)
    )
    if user_id is not None:
        q = q.filter(Article.user_id == user_id)
    return q.first()


def article_to_dict(article: Article) -> dict[str, Any]:
    """Serialize article and nested images for JSON responses."""
    order_ctx: dict[str, Any] | None = None
    if article.order_line_id and article.order_line is not None:
        ln = article.order_line
        ord_row = ln.order
        if ord_row is not None:
            order_ctx = {
                "order_line_id": ln.id,
                "order_id": ord_row.id,
                "external_order_id": ord_row.external_order_id,
                "paid_at": ord_row.paid_at.isoformat() if ord_row.paid_at else None,
                "unit_price_eur": float(ln.unit_price_eur),
                "seller_username": ord_row.seller_username,
                "seller_country_code": ord_row.seller_country_code,
            }
    return {
        "id": article.id,
        "user_id": article.user_id,
        "title": article.title,
        "description": article.description,
        "pokemon_name": article.pokemon_name,
        "set_code": article.set_code,
        "card_number": article.card_number,
        "condition": article.condition,
        "is_graded": bool(article.is_graded),
        "graded_grader_value_id": article.graded_grader_value_id,
        "graded_grade_value_id": article.graded_grade_value_id,
        "graded_cert_number": article.graded_cert_number,
        "purchase_price": float(article.purchase_price),
        "sell_price": float(article.sell_price) if article.sell_price is not None else None,
        "sold_price": float(article.sold_price) if article.sold_price is not None else None,
        "sale_source": article.sale_source,
        "is_sold": article.is_sold,
        "published_on_vinted": bool(article.published_on_vinted),
        "vinted_published_at": article.vinted_published_at.isoformat()
        if article.vinted_published_at
        else None,
        "published_on_ebay": bool(article.published_on_ebay),
        "ebay_listing_id": article.ebay_listing_id,
        "ebay_inventory_sku": article.ebay_inventory_sku,
        "ebay_published_at": article.ebay_published_at.isoformat()
        if article.ebay_published_at
        else None,
        "vinted_id": int(article.vinted_id) if article.vinted_id is not None else None,
        "cross_ebay_removal_failed": bool(article.cross_ebay_removal_failed),
        "cross_vinted_removal_failed": bool(article.cross_vinted_removal_failed),
        "cross_ebay_removal_error": article.cross_ebay_removal_error,
        "cross_vinted_removal_error": article.cross_vinted_removal_error,
        "pending_vinted_unlist": bool(
            article.is_sold
            and (article.sale_source or "").lower() == "ebay"
            and article.published_on_vinted
        ),
        "created_at": article.created_at.isoformat(),
        "sold_at": article.sold_at.isoformat() if article.sold_at else None,
        "order_line_id": article.order_line_id,
        "order_context": order_ctx,
        "images": [{"id": img.id, "image_url": img.image_url, "created_at": img.created_at.isoformat()} for img in article.images],
    }


def mark_article_published_on_vinted(
    article_id: int, user_id: int, *, vinted_id: int | None = None
) -> bool:
    """
    Mark the article as published on Vinted (short DB session, suitable for long-running tasks).
    Optionally persist ``vinted_id`` (identifiant URL Vinted).
    """
    db = SessionLocal()
    try:
        article = get_article(db, article_id, user_id)
        if article is None:
            return False
        article.published_on_vinted = True
        article.vinted_published_at = dt.datetime.now(dt.UTC)
        if vinted_id is not None and vinted_id > 0:
            article.vinted_id = int(vinted_id)
        db.commit()
        return True
    finally:
        db.close()


def mark_article_published_on_ebay(
    article_id: int, user_id: int, listing_id: str, inventory_sku: str | None = None
) -> bool:
    db = SessionLocal()
    try:
        article = get_article(db, article_id, user_id)
        if article is None:
            return False
        article.published_on_ebay = True
        article.ebay_listing_id = listing_id[:64]
        if inventory_sku:
            article.ebay_inventory_sku = inventory_sku.strip()[:50]
        article.ebay_published_at = dt.datetime.now(dt.UTC)
        db.commit()
        return True
    finally:
        db.close()


def delete_articles_by_ids(db: Session, user_id: int, ids: list[int]) -> int:
    """
    Supprime les articles dont l'id est dans ``ids`` et ``user_id`` correspond.
    Returns the number of deleted rows.
    """
    if not ids:
        return 0
    q = db.query(Article).filter(Article.user_id == user_id, Article.id.in_(ids))
    deleted = q.delete(synchronize_session=False)
    db.commit()
    return int(deleted)


def update_article_from_body(article: Article, body: ArticleUpdate) -> None:
    """Apply a partial update from ``ArticleUpdate`` (only set fields are changed)."""
    data = body.model_dump(exclude_unset=True)
    data.pop("order_line_id", None)
    if "is_graded" in data:
        article.is_graded = bool(data["is_graded"])
        if not article.is_graded:
            article.graded_grader_value_id = None
            article.graded_grade_value_id = None
            article.graded_cert_number = None
    if "title" in data and data["title"] is not None:
        article.title = data["title"]
    if "description" in data and data["description"] is not None:
        article.description = data["description"]
    if "pokemon_name" in data:
        article.pokemon_name = data["pokemon_name"]
    if "set_code" in data:
        article.set_code = data["set_code"]
    if "card_number" in data:
        article.card_number = data["card_number"]
    if "condition" in data and data["condition"] is not None:
        article.condition = data["condition"]
    if "purchase_price" in data and data["purchase_price"] is not None:
        article.purchase_price = data["purchase_price"]
    if "sell_price" in data:
        article.sell_price = data["sell_price"]
    if "graded_grader_value_id" in data:
        gid = data["graded_grader_value_id"]
        article.graded_grader_value_id = (gid.strip() if isinstance(gid, str) else None) or None
    if "graded_grade_value_id" in data:
        tid = data["graded_grade_value_id"]
        article.graded_grade_value_id = (tid.strip() if isinstance(tid, str) else None) or None
    if "graded_cert_number" in data:
        cert = data["graded_cert_number"]
        if cert is None:
            article.graded_cert_number = None
        else:
            c = str(cert).strip()[:30]
            article.graded_cert_number = c or None
    if data.get("clear_vinted_publication") is True:
        article.published_on_vinted = False
        article.vinted_published_at = None
        article.vinted_id = None
    if data.get("clear_ebay_publication") is True:
        article.published_on_ebay = False
        article.ebay_listing_id = None
        article.ebay_inventory_sku = None
        article.ebay_published_at = None
