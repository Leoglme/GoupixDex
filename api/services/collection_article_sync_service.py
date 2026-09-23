"""
Garde « Ma Collection » alignée sur les articles en vente.

Principe métier : une carte mise en vente est **possédée**, donc présente dans la
collection ; une fois **vendue**, elle en disparaît. Un article (fiche de vente) n'a
pas d'identité TCGdex — on la résout depuis son set/numéro pour construire une vraie
carte de collection (image, noms, cote), avec repli minimal (photo de l'article) si
TCGdex ne répond pas.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from models.article import Article
from models.collection_card import CollectionCard
from services.cardmarket_local_price_service import resolve_market_price_eur
from services.collection_card_lookup_service import fetch_card_for_collection
from services.tcgdex_lookup_service import resolve_tcgdex_card_id_from_ocr

#: Langue par défaut d'une carte créée depuis un article (les articles n'en portent pas).
_DEFAULT_LANGUAGE = "fr"


def linked_collection_card(db: Session, article: Article) -> CollectionCard | None:
    """Carte de collection déjà reliée à cet article, le cas échéant."""
    return (
        db.query(CollectionCard)
        .filter(CollectionCard.user_id == article.user_id, CollectionCard.article_id == article.id)
        .first()
    )


def _resolved_card_payload(article: Article) -> dict[str, Any] | None:
    """Résout la carte TCGdex depuis le set/numéro de l'article ; ``None`` si irrésolvable."""
    if not article.set_code or not article.card_number:
        return None
    try:
        tcgdex_card_id = resolve_tcgdex_card_id_from_ocr(
            ocr_set_code=article.set_code,
            ocr_card_number=article.card_number,
            ocr_pokemon_name=article.pokemon_name,
        )
    except (RuntimeError, ValueError):
        return None
    if not tcgdex_card_id:
        return None
    try:
        return fetch_card_for_collection(tcgdex_card_id=tcgdex_card_id, physical_language=_DEFAULT_LANGUAGE)
    except (RuntimeError, ValueError):
        return None


def _new_collection_card_from_article(article: Article) -> CollectionCard:
    """
    Construit (sans persister) une carte de collection pour un article en vente.

    Résout d'abord la fiche TCGdex complète ; à défaut, retombe sur une carte minimale
    portant la photo uploadée de l'article et son set/numéro.
    """
    purchase_price = Decimal(str(round(float(article.purchase_price), 2)))
    payload = _resolved_card_payload(article)
    if payload is not None:
        market_price = payload.get("market_price_eur")
        return CollectionCard(
            user_id=article.user_id,
            tcgdex_card_id=str(payload["tcgdex_card_id"]),
            tcgdex_set_id=str(payload["tcgdex_set_id"]),
            set_code=payload.get("set_code"),
            set_name=payload.get("set_name"),
            card_number=str(payload["card_number"]),
            card_name_en=payload.get("card_name_en"),
            card_name_fr=payload.get("card_name_fr"),
            card_name_ja=payload.get("card_name_ja"),
            display_name=str(payload["display_name"]),
            rarity=payload.get("rarity"),
            language=str(payload.get("language") or _DEFAULT_LANGUAGE),
            image_url=payload.get("image_url"),
            quantity=1,
            purchase_price_eur=purchase_price,
            cardmarket_id_product=payload.get("cardmarket_id_product"),
            market_price_eur=(Decimal(str(round(float(market_price), 2))) if market_price is not None else None),
            article_id=article.id,
        )

    # Repli minimal : TCGdex n'a pas résolu la carte — on garde la photo de l'article.
    market_price = article.market_cardmarket_eur
    if market_price is None and article.cardmarket_id_product is not None:
        resolved = resolve_market_price_eur(article.cardmarket_id_product, None)
        market_price = Decimal(str(round(float(resolved), 2))) if resolved is not None else None
    display_name = (article.pokemon_name or article.title or "Carte").strip()
    return CollectionCard(
        user_id=article.user_id,
        tcgdex_card_id=f"manual-article-{article.id}",
        tcgdex_set_id=(article.set_code or "manual"),
        set_code=article.set_code,
        set_name=None,
        card_number=(article.card_number or "?"),
        card_name_fr=(article.pokemon_name or None),
        display_name=display_name,
        language=_DEFAULT_LANGUAGE,
        image_url=(article.images[0].image_url if article.images else None),
        quantity=1,
        purchase_price_eur=purchase_price,
        cardmarket_id_product=article.cardmarket_id_product,
        market_price_eur=market_price,
        article_id=article.id,
    )


def ensure_collection_card_for_article(db: Session, article: Article) -> CollectionCard | None:
    """
    Garantit qu'un article en vente possède sa carte de collection reliée (idempotent).

    Ne fait rien pour un article vendu (la carte a alors quitté la collection), déjà relié, ou
    sans set + numéro (produit scellé, saisie incomplète). Retourne la carte reliée (existante ou
    créée), ou ``None`` si rien n'est fait.
    """
    if article.is_sold:
        return None
    if not (article.set_code and article.set_code.strip()) or not (article.card_number and article.card_number.strip()):
        return None
    existing = linked_collection_card(db, article)
    if existing is not None:
        return existing
    card = _new_collection_card_from_article(article)
    db.add(card)
    db.commit()
    db.refresh(card)
    return card


def attach_collection_card(db: Session, *, user_id: int, collection_card_id: int, article: Article) -> bool:
    """Relie une carte de collection existante à cet article (vente depuis la collection) ; ``True`` si reliée."""
    card = (
        db.query(CollectionCard)
        .filter(CollectionCard.id == collection_card_id, CollectionCard.user_id == user_id)
        .first()
    )
    if card is None:
        return False
    card.article_id = article.id
    db.commit()
    return True


def remove_collection_card_for_sold_article(db: Session, article: Article) -> bool:
    """Retire de la collection la carte reliée à un article vendu ; ``True`` si une carte a été supprimée."""
    card = linked_collection_card(db, article)
    if card is None:
        return False
    db.delete(card)
    db.commit()
    return True
