"""
``/collection`` — the user's personal Pokémon card binder.

Lean storage: card identity + language + quantity. Pricing / condition stay on
:class:`models.article.Article` and are created on demand via
``POST /collection/{id}/prepare-article-prefill``.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from core.database import get_db
from core.deps import get_current_user
from models.collection_card import CollectionCard
from models.margin_settings import MarginSettings
from models.user import User
from schemas.collection import (
    CollectionCardAddBody,
    CollectionCardPrepareSaleBody,
    CollectionCardUpdateBody,
)
from services import collection_card_service, pricing_service
from services.collection_card_lookup_service import fetch_card_for_collection
from services.scan_service import build_title_and_description
from services.tcgdex_client_service import TcgdexClientService, tcgdx_image_url_high

router = APIRouter(prefix="/collection", tags=["collection"])


def _margin_percent(db: Session, user_id: int) -> int:
    row = db.query(MarginSettings).filter(MarginSettings.user_id == user_id).first()
    return row.margin_percent if row is not None else 20


@router.get("")
def list_collection(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    search: str | None = Query(None, max_length=120),
    language: str | None = Query(None, min_length=2, max_length=8),
    set_id: str | None = Query(None, max_length=64),
    listed: str | None = Query(None, pattern="^(any|with_article|without_article)$"),
) -> dict[str, Any]:
    """Paginated-style list (front filters in JS for now) + aggregated stats header."""
    rows = collection_card_service.list_collection_for_user(
        db,
        user.id,
        search=search,
        language=language,
        set_id=set_id,
        listed_state=listed,
    )
    return {
        "items": [collection_card_service.collection_card_to_dict(r) for r in rows],
        "stats": collection_card_service.aggregate_collection_stats(rows),
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def add_to_collection(
    body: CollectionCardAddBody,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """
    Add a TCGdex card to ``Ma Collection``.

    If the same ``(tcgdex_card_id, language)`` already exists, the existing row's
    ``quantity`` is incremented (idempotent quick-add UX).
    """
    try:
        meta = fetch_card_for_collection(
            tcgdex_card_id=body.tcgdex_card_id,
            physical_language=body.language,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    existing = collection_card_service.find_existing_for_user(
        db,
        user.id,
        tcgdex_card_id=meta["tcgdex_card_id"],
        language=meta["language"],
    )
    if existing is not None:
        existing.quantity = int(existing.quantity) + int(body.quantity)
        if body.notes:
            existing.notes = body.notes.strip() or existing.notes
        db.commit()
        db.refresh(existing)
        return {"created": False, "card": collection_card_service.collection_card_to_dict(existing)}

    row = CollectionCard(
        user_id=user.id,
        tcgdex_card_id=meta["tcgdex_card_id"],
        tcgdex_set_id=meta["tcgdex_set_id"],
        set_code=meta["set_code"],
        set_name=meta["set_name"],
        card_number=meta["card_number"],
        card_name_en=meta["card_name_en"],
        card_name_fr=meta["card_name_fr"],
        card_name_ja=meta["card_name_ja"],
        display_name=meta["display_name"],
        rarity=meta["rarity"],
        language=meta["language"],
        image_url=meta["image_url"],
        quantity=int(body.quantity),
        notes=(body.notes.strip() if body.notes else None),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"created": True, "card": collection_card_service.collection_card_to_dict(row)}


@router.get("/{card_id}")
def get_collection_card(
    card_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    row = collection_card_service.get_collection_card(db, card_id, user.id)
    if row is None:
        raise HTTPException(status_code=404, detail="Carte de collection introuvable.")
    return collection_card_service.collection_card_to_dict(row)


@router.patch("/{card_id}")
def patch_collection_card(
    card_id: int,
    body: CollectionCardUpdateBody,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    row = collection_card_service.get_collection_card(db, card_id, user.id)
    if row is None:
        raise HTTPException(status_code=404, detail="Carte de collection introuvable.")
    row = collection_card_service.update_collection_card(
        db,
        row,
        quantity=body.quantity,
        language=body.language,
        notes=body.notes,
    )
    return collection_card_service.collection_card_to_dict(row)


@router.delete("/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_collection_card(
    card_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    ok = collection_card_service.delete_collection_card(db, user.id, card_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Carte de collection introuvable.")


@router.post("/{card_id}/prepare-article-prefill")
def prepare_article_prefill(
    card_id: int,
    body: CollectionCardPrepareSaleBody,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """
    Build the payload consumed by ``ArticleForm.applyCatalogPrefill`` from a
    collection card. Uses the cached metadata (no TCGdex call) and optionally
    refreshes pricing via :mod:`services.pricing_service`.
    """
    row = collection_card_service.get_collection_card(db, card_id, user.id)
    if row is None:
        raise HTTPException(status_code=404, detail="Carte de collection introuvable.")

    margin = _margin_percent(db, user.id)
    pricing: dict[str, Any] = {
        "cardmarket_eur": None,
        "tcgplayer_usd": None,
        "average_price_eur": None,
        "error": None,
    }
    suggested: float | None = None
    if body.refresh_pricing and row.set_code and row.card_number:
        prices = pricing_service.fetch_card_prices(
            row.set_code,
            row.card_number,
            row.card_name_en or row.display_name,
        )
        avg = prices.get("average_price")
        pricing = {
            "cardmarket_eur": prices.get("cardmarket_eur"),
            "tcgplayer_usd": prices.get("tcgplayer_usd"),
            "average_price_eur": round(float(avg), 2) if isinstance(avg, (int, float)) else None,
            "error": prices.get("error"),
        }
        if isinstance(avg, (int, float)):
            suggested = round(float(avg) * (1.0 + margin / 100.0), 2)

    ocr_like = {
        "set_code": row.set_code or "",
        "card_number": row.card_number,
        "pokemon_name": row.display_name,
        "pokemon_name_english": row.card_name_en or "",
        "pokemon_name_french": row.card_name_fr or "",
        "set_name_english": row.set_name or "",
        "rarity_english": row.rarity or "",
    }
    card_info: dict[str, Any] = {
        "set_name": row.set_name or "",
        "set_code": row.set_code or "",
        "card_number": row.card_number,
        "rarity": row.rarity or "",
    }
    title, description = build_title_and_description(ocr_like, card_info)
    if row.card_name_ja and row.card_name_ja not in {row.card_name_en, row.card_name_fr}:
        description = f"{description}\nNom (JPN) : {row.card_name_ja}"

    image_url_high: str | None = None
    if row.image_url:
        base = row.image_url
        if base.endswith("/low.webp"):
            base = base[: -len("/low.webp")]
        image_url_high = tcgdx_image_url_high(base)

    return {
        "tcgdx_card_id": row.tcgdex_card_id,
        "display_pokemon_name": row.display_name,
        "tcgdex": {
            "names": {"en": row.card_name_en, "fr": row.card_name_fr, "ja": row.card_name_ja},
            "set_id": row.tcgdex_set_id,
            "local_id": row.card_number,
        },
        "pokewallet": {
            "set_code": row.set_code or "",
            "card_number": row.card_number,
        },
        "listing_preview": {
            "title": title,
            "description": description,
            "suggested_price": suggested,
        },
        "pricing": pricing,
        "image_url_high": image_url_high,
        "margin_percent_used": margin,
        "collection_card_id": row.id,
        "physical_language": row.language,
        "error": None,
    }


@router.post("/{card_id}/attach-article", status_code=status.HTTP_200_OK)
def attach_article_to_collection_card(
    card_id: int,
    article_id: Annotated[int, Query(ge=1)],
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Link an already-created article back to this collection entry."""
    from models.article import Article

    row = collection_card_service.get_collection_card(db, card_id, user.id)
    if row is None:
        raise HTTPException(status_code=404, detail="Carte de collection introuvable.")
    article = db.query(Article).filter(Article.id == article_id, Article.user_id == user.id).first()
    if article is None:
        raise HTTPException(status_code=400, detail="Article introuvable ou non autorisé.")
    row.article_id = article.id
    db.commit()
    db.refresh(row)
    return collection_card_service.collection_card_to_dict(row)
