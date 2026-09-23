"""
Persistence helpers for :class:`models.collection_card.CollectionCard`.

Pure DB layer — HTTP / TCGdex fetches live in
:mod:`services.collection_card_lookup_service` to keep transactional code thin.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from models.collection_card import CollectionCard
from services.cardmarket_local_price_service import resolve_market_price_eur
from services.collection_gain import gain_fields


def list_collection_for_user(
    db: Session,
    user_id: int,
    *,
    search: str | None = None,
    language: str | None = None,
    set_id: str | None = None,
    listed_state: str | None = None,
) -> list[CollectionCard]:
    """
    List the user's collection, newest first.

    ``listed_state`` filter values: ``"any"`` (default), ``"with_article"``, ``"without_article"``.
    """
    q = db.query(CollectionCard).filter(
        CollectionCard.user_id == user_id,
        CollectionCard.is_placeholder.is_(False),
    )
    if search:
        like = f"%{search.strip()}%"
        q = q.filter(
            or_(
                CollectionCard.display_name.ilike(like),
                CollectionCard.card_name_en.ilike(like),
                CollectionCard.card_name_fr.ilike(like),
                CollectionCard.set_name.ilike(like),
                CollectionCard.set_code.ilike(like),
                CollectionCard.card_number.ilike(like),
            )
        )
    if language:
        q = q.filter(CollectionCard.language == language.strip().lower())
    if set_id:
        q = q.filter(CollectionCard.tcgdex_set_id == set_id.strip())
    if listed_state == "with_article":
        q = q.filter(CollectionCard.article_id.is_not(None))
    elif listed_state == "without_article":
        q = q.filter(CollectionCard.article_id.is_(None))
    return q.order_by(CollectionCard.created_at.desc()).all()


def get_collection_card(
    db: Session,
    card_id: int,
    user_id: int | None = None,
) -> CollectionCard | None:
    q = db.query(CollectionCard).options(joinedload(CollectionCard.article)).filter(CollectionCard.id == card_id)
    if user_id is not None:
        q = q.filter(CollectionCard.user_id == user_id)
    return q.first()


def collection_card_to_dict(card: CollectionCard) -> dict[str, Any]:
    """JSON shape used by the front-end (snake_case), plus-value incluse."""
    quantity = int(card.quantity)
    return {
        "id": card.id,
        "tcgdex_card_id": card.tcgdex_card_id,
        "tcgdex_set_id": card.tcgdex_set_id,
        "set_code": card.set_code,
        "set_name": card.set_name,
        "card_number": card.card_number,
        "card_name_en": card.card_name_en,
        "card_name_fr": card.card_name_fr,
        "card_name_ja": card.card_name_ja,
        "display_name": card.display_name,
        "rarity": card.rarity,
        "language": card.language,
        "image_url": card.image_url,
        "quantity": quantity,
        "is_placeholder": bool(card.is_placeholder),
        "purchase_price_eur": float(card.purchase_price_eur) if card.purchase_price_eur is not None else None,
        "notes": card.notes,
        "article_id": card.article_id,
        "cardmarket_id_product": card.cardmarket_id_product,
        "market_price_eur": float(card.market_price_eur) if card.market_price_eur is not None else None,
        "market_price_overridden": bool(card.market_price_overridden),
        "market_price_updated_at": (
            card.market_price_updated_at.isoformat() if card.market_price_updated_at is not None else None
        ),
        **gain_fields(card.market_price_eur, card.purchase_price_eur, quantity),
        "created_at": card.created_at.isoformat(),
        "updated_at": card.updated_at.isoformat(),
    }


def apply_market_price(
    card: CollectionCard,
    *,
    cardmarket_id_product: int | None,
    market_price_eur: float | None,
) -> None:
    """
    Write the harvested Cardmarket mapping / price onto a row (no commit).

    The ``idProduct`` is stable so it is only ever filled, never cleared; the
    price is refreshed whenever a new value is available and left untouched
    otherwise (a transient TCGdex miss must not erase a known price).
    """
    if cardmarket_id_product is not None:
        card.cardmarket_id_product = cardmarket_id_product
    if market_price_eur is not None:
        card.market_price_eur = Decimal(str(round(market_price_eur, 2)))
        card.market_price_updated_at = dt.datetime.now(dt.UTC)


def find_existing_for_user(
    db: Session,
    user_id: int,
    *,
    tcgdex_card_id: str,
    language: str,
) -> CollectionCard | None:
    """Return the row matching the (card, language) pair so add can increment."""
    return (
        db.query(CollectionCard)
        .filter(
            CollectionCard.user_id == user_id,
            CollectionCard.tcgdex_card_id == tcgdex_card_id,
            CollectionCard.language == language,
        )
        .first()
    )


def owned_quantity(db: Session, user_id: int, tcgdex_card_id: str, language: str | None = None) -> int:
    """
    Exemplaires possédés d'une carte TCGdex (toutes lignes confondues, cartes en vente comprises),
    limités à une langue physique si elle est fournie — même règle que l'index « possédé » du catalogue.
    """
    q = db.query(CollectionCard.quantity).filter(
        CollectionCard.user_id == user_id,
        CollectionCard.tcgdex_card_id == tcgdex_card_id,
        CollectionCard.is_placeholder.is_(False),
    )
    if language:
        q = q.filter(CollectionCard.language == language.strip().lower())
    return sum(int(quantity) for (quantity,) in q.all())


def delete_collection_card(db: Session, user_id: int, card_id: int) -> bool:
    row = db.query(CollectionCard).filter(
        CollectionCard.id == card_id, CollectionCard.user_id == user_id
    ).first()
    if row is None:
        return False
    db.delete(row)
    db.commit()
    return True


def update_collection_card(
    db: Session,
    card: CollectionCard,
    *,
    quantity: int | None = None,
    language: str | None = None,
    notes: str | None = None,
    purchase_price_eur: float | None = None,
    market_price_eur: float | None = None,
    reset_market_price: bool = False,
) -> CollectionCard:
    """Apply optional patch fields and commit."""
    if quantity is not None:
        card.quantity = max(1, int(quantity))
    if language is not None:
        lang = language.strip().lower()
        if lang:
            card.language = lang
    if notes is not None:
        card.notes = notes.strip() or None
    if purchase_price_eur is not None:
        card.purchase_price_eur = Decimal(str(round(float(purchase_price_eur), 2)))
    if reset_market_price:
        card.market_price_overridden = False
        auto_price = resolve_market_price_eur(card.cardmarket_id_product, None)
        if auto_price is not None:
            card.market_price_eur = Decimal(str(round(float(auto_price), 2)))
    elif market_price_eur is not None:
        card.market_price_eur = Decimal(str(round(float(market_price_eur), 2)))
        card.market_price_overridden = True
    db.commit()
    db.refresh(card)
    return card


def aggregate_collection_stats(rows: list[CollectionCard]) -> dict[str, Any]:
    """High-level counters for the dashboard header (unique cards, quantity, sets, plus-value)."""
    if not rows:
        return {
            "unique_cards": 0,
            "total_quantity": 0,
            "unique_sets": 0,
            "languages": {},
            "with_article": 0,
            "estimated_value_eur": 0.0,
            "priced_cards": 0,
            "purchase_value_eur": 0.0,
            "gain_eur": 0.0,
            "gain_percent": None,
            "invested_cards": 0,
        }
    languages: dict[str, int] = {}
    sets: set[str] = set()
    total_quantity = 0
    with_article = 0
    estimated_value = Decimal("0")
    priced_cards = 0
    purchase_value = Decimal("0")
    gain_basis_purchase = Decimal("0")
    gain_eur = Decimal("0")
    invested_cards = 0
    for r in rows:
        qty = int(r.quantity)
        languages[r.language] = languages.get(r.language, 0) + qty
        if r.tcgdex_set_id:
            sets.add(r.tcgdex_set_id)
        total_quantity += qty
        if r.article_id is not None:
            with_article += 1
        if r.market_price_eur is not None:
            estimated_value += Decimal(r.market_price_eur) * qty
            priced_cards += 1
        if r.purchase_price_eur is not None:
            purchase_value += Decimal(r.purchase_price_eur) * qty
            invested_cards += 1
        if r.market_price_eur is not None and r.purchase_price_eur is not None:
            gain_eur += (Decimal(r.market_price_eur) - Decimal(r.purchase_price_eur)) * qty
            gain_basis_purchase += Decimal(r.purchase_price_eur) * qty
    gain_percent = (
        round(float(gain_eur) / float(gain_basis_purchase) * 100.0, 1) if gain_basis_purchase > 0 else None
    )
    return {
        "unique_cards": len(rows),
        "total_quantity": total_quantity,
        "unique_sets": len(sets),
        "languages": languages,
        "with_article": with_article,
        "estimated_value_eur": float(estimated_value),
        "priced_cards": priced_cards,
        "purchase_value_eur": float(purchase_value),
        "gain_eur": round(float(gain_eur), 2),
        "gain_percent": gain_percent,
        "invested_cards": invested_cards,
    }
