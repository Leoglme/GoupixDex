"""
``/sealed`` — les produits scellés de la collection (ETB, coffrets, displays…).

Stockage complet (contrairement aux cartes) : prix d'achat + prix marché Cardmarket.
La mise en vente réutilise :class:`models.article.Article` via ``attach-article``.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from core.database import get_db
from core.deps import get_current_user
from models.margin_settings import MarginSettings
from models.user import User
from schemas.sealed import (
    CardmarketResolveBody,
    SealedCatalogAddBody,
    SealedCatalogPriceHistoryBody,
    SealedProductCreateBody,
    SealedProductPrepareSaleBody,
    SealedProductUpdateBody,
    SealedQuoteBody,
)
from services import sealed_price_history_service, sealed_product_service
from services.cardmarket_local_price_service import resolve_market_price_eur
from services.cardmarket_product_resolve_service import resolve_cardmarket_product

router = APIRouter(prefix="/sealed", tags=["sealed"])

_LANGUAGE_LABELS = {"fr": "Français", "en": "Anglais", "ja": "Japonais"}


def _price_for_new_product(body: SealedProductCreateBody) -> float | None:
    """Prix marché à l'ajout : valeur saisie sinon guide Cardmarket local via l'``idProduct``."""
    if body.market_price_eur is not None:
        return body.market_price_eur
    if body.cardmarket_id_product is not None:
        return resolve_market_price_eur(body.cardmarket_id_product, None)
    return None


def _margin_percent(db: Session, user_id: int) -> int:
    """Marge de vente configurée par l'utilisateur (20 % par défaut)."""
    row = db.query(MarginSettings).filter(MarginSettings.user_id == user_id).first()
    return row.margin_percent if row is not None else 20


@router.get("")
def list_sealed(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    search: str | None = Query(None, max_length=120),
    language: str | None = Query(None, min_length=2, max_length=8),
    product_type: str | None = Query(None, max_length=32),
    listed: str | None = Query(None, pattern="^(any|with_article|without_article)$"),
) -> dict[str, Any]:
    """Liste les produits scellés + stats d'en-tête (valeur marché, gain)."""
    rows = sealed_product_service.list_sealed_for_user(
        db,
        user.id,
        search=search,
        language=language,
        product_type=product_type,
        listed_state=listed,
    )
    return {
        "items": [sealed_product_service.sealed_product_to_dict(r) for r in rows],
        "stats": sealed_product_service.aggregate_sealed_stats(rows),
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def add_sealed_product(
    body: SealedProductCreateBody,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Ajoute un produit scellé (prix marché résolu depuis le guide si un ``idProduct`` est fourni)."""
    product = sealed_product_service.create_sealed_product(
        db,
        user.id,
        name=body.name,
        product_type=body.product_type,
        set_name=body.set_name,
        language=body.language,
        quantity=body.quantity,
        purchase_price_eur=body.purchase_price_eur,
        notes=body.notes,
        image_url=body.image_url,
        cardmarket_id_product=body.cardmarket_id_product,
        cardmarket_url=body.cardmarket_url,
        market_price_eur=_price_for_new_product(body),
    )
    if product.market_price_eur is not None:
        sealed_price_history_service.record_snapshot(db, product.id, float(product.market_price_eur))
        db.commit()
    return {"created": True, "product": sealed_product_service.sealed_product_to_dict(product)}


@router.post("/catalog-add", status_code=status.HTTP_201_CREATED)
def add_from_catalog(
    body: SealedCatalogAddBody,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """
    Ajoute un produit choisi dans le catalogue Cardmarket (parcours par extension).

    Idempotent : recliquer le même produit incrémente la quantité (comme les cartes).
    Prix marché résolu depuis le guide local via l'``idProduct``.
    """
    market_price: float | None = None
    if body.cardmarket_id_product is not None:
        market_price = resolve_market_price_eur(body.cardmarket_id_product, None)
    if market_price is None:
        market_price = body.market_price_eur
    existing = (
        sealed_product_service.find_by_cardmarket_id_product(db, user.id, body.cardmarket_id_product)
        if body.cardmarket_id_product is not None
        else None
    )
    if existing is not None:
        product = sealed_product_service.update_sealed_product(
            db,
            existing,
            quantity=int(existing.quantity) + body.quantity,
            image_url=body.image_url or existing.image_url,
            market_price_eur=market_price,
        )
        created = False
    else:
        product = sealed_product_service.create_sealed_product(
            db,
            user.id,
            name=body.name,
            product_type=body.product_type,
            set_name=body.set_name,
            language=body.language,
            quantity=body.quantity,
            purchase_price_eur=None,
            notes=None,
            image_url=body.image_url,
            cardmarket_id_product=body.cardmarket_id_product,
            cardmarket_url=None,
            market_price_eur=market_price,
        )
        created = True
    if product.market_price_eur is not None:
        sealed_price_history_service.record_snapshot(db, product.id, float(product.market_price_eur))
        db.commit()
    return {"created": created, "product": sealed_product_service.sealed_product_to_dict(product)}


@router.post("/quote")
def quote_prices(
    body: SealedQuoteBody,
    _user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Prix marché en lot pour des ``idProduct`` du catalogue (guide local, sans quota)."""
    prices: dict[str, float | None] = {}
    for id_product in dict.fromkeys(body.cardmarket_id_products):
        prices[str(id_product)] = resolve_market_price_eur(id_product, None)
    return {"prices": prices}


@router.post("/catalog-price-history")
def catalog_price_history(
    body: SealedCatalogPriceHistoryBody,
    _user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Courbe approximative d'un produit du catalogue (amorce guide par ``idProduct``, avant l'ajout)."""
    return sealed_price_history_service.catalog_price_history(body.cardmarket_id_product)


@router.post("/resolve-cardmarket")
def resolve_cardmarket(
    body: CardmarketResolveBody,
    _user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Pré-remplit un scellé depuis une URL Cardmarket (best-effort : ``idProduct`` + nom + image + prix)."""
    return resolve_cardmarket_product(body.url)


@router.get("/{sealed_id}")
def get_sealed_product(
    sealed_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    row = sealed_product_service.get_sealed_product(db, sealed_id, user.id)
    if row is None:
        raise HTTPException(status_code=404, detail="Produit scellé introuvable.")
    return sealed_product_service.sealed_product_to_dict(row)


@router.get("/{sealed_id}/price-history")
def get_price_history(
    sealed_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Courbe d'évolution du prix marché du produit (historique réel + amorce approximative)."""
    row = sealed_product_service.get_sealed_product(db, sealed_id, user.id)
    if row is None:
        raise HTTPException(status_code=404, detail="Produit scellé introuvable.")
    return sealed_price_history_service.price_history(db, row)


@router.patch("/{sealed_id}")
def patch_sealed_product(
    sealed_id: int,
    body: SealedProductUpdateBody,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    row = sealed_product_service.get_sealed_product(db, sealed_id, user.id)
    if row is None:
        raise HTTPException(status_code=404, detail="Produit scellé introuvable.")
    row = sealed_product_service.update_sealed_product(
        db,
        row,
        name=body.name,
        product_type=body.product_type,
        set_name=body.set_name,
        language=body.language,
        quantity=body.quantity,
        purchase_price_eur=body.purchase_price_eur,
        notes=body.notes,
        image_url=body.image_url,
        cardmarket_id_product=body.cardmarket_id_product,
        cardmarket_url=body.cardmarket_url,
        market_price_eur=body.market_price_eur,
    )
    return sealed_product_service.sealed_product_to_dict(row)


@router.delete("/{sealed_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sealed_product(
    sealed_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    ok = sealed_product_service.delete_sealed_product(db, user.id, sealed_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Produit scellé introuvable.")


@router.post("/{sealed_id}/prepare-article-prefill")
def prepare_article_prefill(
    sealed_id: int,
    body: SealedProductPrepareSaleBody,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """
    Construit le payload consommé par ``ArticleForm.applyCatalogPrefill`` depuis un
    produit scellé (titre, description, image, prix suggéré). Rafraîchit le prix
    marché depuis le guide si un ``idProduct`` est connu.
    """
    row = sealed_product_service.get_sealed_product(db, sealed_id, user.id)
    if row is None:
        raise HTTPException(status_code=404, detail="Produit scellé introuvable.")

    if body.refresh_pricing and row.cardmarket_id_product is not None:
        refreshed = resolve_market_price_eur(row.cardmarket_id_product, None)
        if refreshed is not None:
            sealed_product_service.apply_market_price(
                row,
                cardmarket_id_product=row.cardmarket_id_product,
                market_price_eur=refreshed,
            )
            db.commit()
            db.refresh(row)

    margin = _margin_percent(db, user.id)
    market = float(row.market_price_eur) if row.market_price_eur is not None else None
    suggested = round(market * (1.0 + margin / 100.0), 2) if market is not None else None

    description_lines = [row.name]
    if row.set_name:
        description_lines.append(row.set_name)
    description_lines.append("Produit scellé, neuf et jamais ouvert.")
    description_lines.append(f"Langue : {_LANGUAGE_LABELS.get(row.language, row.language.upper())}")
    if row.notes:
        description_lines.append(row.notes)
    description = "\n".join(description_lines)

    return {
        "tcgdx_card_id": "",
        "display_pokemon_name": row.name,
        "tcgdex": {"names": {"en": row.name, "fr": row.name, "ja": None}, "set_id": "", "local_id": ""},
        "pokewallet": {"set_code": "", "card_number": ""},
        "listing_preview": {"title": row.name, "description": description, "suggested_price": suggested},
        "pricing": {
            "cardmarket_eur": market,
            "tcgplayer_usd": None,
            "average_price_eur": market,
            "error": None if market is not None else "Aucun prix marché connu pour ce produit.",
        },
        "image_url_high": row.image_url,
        "margin_percent_used": margin,
        "sealed_product_id": row.id,
        "physical_language": row.language,
        "error": None,
    }


@router.post("/{sealed_id}/attach-article", status_code=status.HTTP_200_OK)
def attach_article_to_sealed_product(
    sealed_id: int,
    article_id: Annotated[int, Query(ge=1)],
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Relie un article déjà créé à ce produit scellé (mise en vente Vinted, etc.)."""
    from models.article import Article

    row = sealed_product_service.get_sealed_product(db, sealed_id, user.id)
    if row is None:
        raise HTTPException(status_code=404, detail="Produit scellé introuvable.")
    article = db.query(Article).filter(Article.id == article_id, Article.user_id == user.id).first()
    if article is None:
        raise HTTPException(status_code=400, detail="Article introuvable ou non autorisé.")
    row.article_id = article.id
    db.commit()
    db.refresh(row)
    return sealed_product_service.sealed_product_to_dict(row)
