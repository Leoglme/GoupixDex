"""
Persistence helpers for :class:`models.collection_card.CollectionCard`.

Pure DB layer — HTTP / TCGdex fetches live in
:mod:`services.collection_card_lookup_service` to keep transactional code thin.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from models.collection_card import CollectionCard


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
    q = db.query(CollectionCard).filter(CollectionCard.user_id == user_id)
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
    """JSON shape used by the front-end (snake_case)."""
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
        "quantity": int(card.quantity),
        "notes": card.notes,
        "article_id": card.article_id,
        "created_at": card.created_at.isoformat(),
        "updated_at": card.updated_at.isoformat(),
    }


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
    db.commit()
    db.refresh(card)
    return card


def aggregate_collection_stats(rows: list[CollectionCard]) -> dict[str, Any]:
    """High-level counters for the dashboard header (unique cards, quantity, sets)."""
    if not rows:
        return {
            "unique_cards": 0,
            "total_quantity": 0,
            "unique_sets": 0,
            "languages": {},
            "with_article": 0,
        }
    languages: dict[str, int] = {}
    sets: set[str] = set()
    total_quantity = 0
    with_article = 0
    for r in rows:
        languages[r.language] = languages.get(r.language, 0) + int(r.quantity)
        if r.tcgdex_set_id:
            sets.add(r.tcgdex_set_id)
        total_quantity += int(r.quantity)
        if r.article_id is not None:
            with_article += 1
    return {
        "unique_cards": len(rows),
        "total_quantity": total_quantity,
        "unique_sets": len(sets),
        "languages": languages,
        "with_article": with_article,
    }
