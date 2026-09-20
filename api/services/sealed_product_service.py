"""
Persistance pour :class:`models.sealed_product.SealedProduct`.

Couche DB pure — la résolution Cardmarket (réseau) vit dans
:mod:`services.cardmarket_product_resolve_service` pour garder ce module transactionnel.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from models.sealed_product import SealedProduct


def list_sealed_for_user(
    db: Session,
    user_id: int,
    *,
    search: str | None = None,
    language: str | None = None,
    product_type: str | None = None,
    listed_state: str | None = None,
) -> list[SealedProduct]:
    """
    Liste les produits scellés de l'utilisateur, du plus récent au plus ancien.

    ``listed_state`` : ``"any"`` (défaut), ``"with_article"``, ``"without_article"``.
    """
    q = db.query(SealedProduct).filter(SealedProduct.user_id == user_id)
    if search:
        like = f"%{search.strip()}%"
        q = q.filter(
            or_(
                SealedProduct.name.ilike(like),
                SealedProduct.set_name.ilike(like),
            )
        )
    if language:
        q = q.filter(SealedProduct.language == language.strip().lower())
    if product_type:
        q = q.filter(SealedProduct.product_type == product_type.strip().lower())
    if listed_state == "with_article":
        q = q.filter(SealedProduct.article_id.is_not(None))
    elif listed_state == "without_article":
        q = q.filter(SealedProduct.article_id.is_(None))
    return q.order_by(SealedProduct.created_at.desc()).all()


def get_sealed_product(
    db: Session,
    sealed_id: int,
    user_id: int | None = None,
) -> SealedProduct | None:
    """Récupère un produit scellé (avec son article lié) par identifiant."""
    q = db.query(SealedProduct).options(joinedload(SealedProduct.article)).filter(SealedProduct.id == sealed_id)
    if user_id is not None:
        q = q.filter(SealedProduct.user_id == user_id)
    return q.first()


def find_by_cardmarket_id_product(db: Session, user_id: int, id_product: int) -> SealedProduct | None:
    """Ligne existante pour ce produit Cardmarket, afin d'incrémenter la quantité à l'ajout catalogue."""
    return (
        db.query(SealedProduct)
        .filter(SealedProduct.user_id == user_id, SealedProduct.cardmarket_id_product == id_product)
        .first()
    )


def _gain_fields(
    market_price_eur: Decimal | None,
    purchase_price_eur: Decimal | None,
    quantity: int,
) -> dict[str, Any]:
    """Calcule les champs de gain (valeur ligne, gain absolu et pourcentage) pour la fiche."""
    line_market = float(market_price_eur) * quantity if market_price_eur is not None else None
    line_purchase = float(purchase_price_eur) * quantity if purchase_price_eur is not None else None
    gain_eur: float | None = None
    gain_percent: float | None = None
    if market_price_eur is not None and purchase_price_eur is not None:
        gain_eur = round((float(market_price_eur) - float(purchase_price_eur)) * quantity, 2)
        if float(purchase_price_eur) > 0:
            gain_percent = round((float(market_price_eur) / float(purchase_price_eur) - 1.0) * 100.0, 1)
    return {
        "line_market_eur": round(line_market, 2) if line_market is not None else None,
        "line_purchase_eur": round(line_purchase, 2) if line_purchase is not None else None,
        "gain_eur": gain_eur,
        "gain_percent": gain_percent,
    }


def sealed_product_to_dict(product: SealedProduct) -> dict[str, Any]:
    """Forme JSON consommée par le front (snake_case), gain inclus."""
    quantity = int(product.quantity)
    return {
        "id": product.id,
        "name": product.name,
        "product_type": product.product_type,
        "set_name": product.set_name,
        "language": product.language,
        "image_url": product.image_url,
        "quantity": quantity,
        "purchase_price_eur": float(product.purchase_price_eur) if product.purchase_price_eur is not None else None,
        "notes": product.notes,
        "article_id": product.article_id,
        "cardmarket_id_product": product.cardmarket_id_product,
        "cardmarket_url": product.cardmarket_url,
        "market_price_eur": float(product.market_price_eur) if product.market_price_eur is not None else None,
        "market_price_updated_at": (
            product.market_price_updated_at.isoformat() if product.market_price_updated_at is not None else None
        ),
        **_gain_fields(product.market_price_eur, product.purchase_price_eur, quantity),
        "created_at": product.created_at.isoformat(),
        "updated_at": product.updated_at.isoformat(),
    }


def apply_market_price(
    product: SealedProduct,
    *,
    cardmarket_id_product: int | None,
    market_price_eur: float | None,
) -> None:
    """
    Écrit le mapping / prix Cardmarket sur une ligne (sans commit).

    L'``idProduct`` est stable : on ne fait que le renseigner, jamais l'effacer ;
    le prix n'est réécrit que lorsqu'une nouvelle valeur existe (un raté transitoire
    du guide ne doit pas écraser un prix connu).
    """
    if cardmarket_id_product is not None:
        product.cardmarket_id_product = cardmarket_id_product
    if market_price_eur is not None:
        product.market_price_eur = Decimal(str(round(market_price_eur, 2)))
        product.market_price_updated_at = dt.datetime.now(dt.UTC)


def create_sealed_product(
    db: Session,
    user_id: int,
    *,
    name: str,
    product_type: str,
    set_name: str | None,
    language: str,
    quantity: int,
    purchase_price_eur: float | None,
    notes: str | None,
    image_url: str | None,
    cardmarket_id_product: int | None,
    cardmarket_url: str | None,
    market_price_eur: float | None,
) -> SealedProduct:
    """Crée et persiste un produit scellé, prix marché appliqué s'il est fourni."""
    product = SealedProduct(
        user_id=user_id,
        name=name.strip(),
        product_type=product_type,
        set_name=(set_name.strip() if set_name else None) or None,
        language=language.strip().lower(),
        quantity=quantity,
        purchase_price_eur=(Decimal(str(round(purchase_price_eur, 2))) if purchase_price_eur is not None else None),
        notes=(notes.strip() if notes else None) or None,
        image_url=(image_url.strip() if image_url else None) or None,
        cardmarket_url=(cardmarket_url.strip() if cardmarket_url else None) or None,
    )
    apply_market_price(
        product,
        cardmarket_id_product=cardmarket_id_product,
        market_price_eur=market_price_eur,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def update_sealed_product(
    db: Session,
    product: SealedProduct,
    *,
    name: str | None = None,
    product_type: str | None = None,
    set_name: str | None = None,
    language: str | None = None,
    quantity: int | None = None,
    purchase_price_eur: float | None = None,
    notes: str | None = None,
    image_url: str | None = None,
    cardmarket_id_product: int | None = None,
    cardmarket_url: str | None = None,
    market_price_eur: float | None = None,
) -> SealedProduct:
    """Applique les champs fournis (patch partiel) puis commit."""
    if name is not None:
        product.name = name.strip() or product.name
    if product_type is not None:
        product.product_type = product_type
    if set_name is not None:
        product.set_name = set_name.strip() or None
    if language is not None:
        lang = language.strip().lower()
        if lang:
            product.language = lang
    if quantity is not None:
        product.quantity = max(1, int(quantity))
    if purchase_price_eur is not None:
        product.purchase_price_eur = Decimal(str(round(purchase_price_eur, 2)))
    if notes is not None:
        product.notes = notes.strip() or None
    if image_url is not None:
        product.image_url = image_url.strip() or None
    if cardmarket_url is not None:
        product.cardmarket_url = cardmarket_url.strip() or None
    apply_market_price(
        product,
        cardmarket_id_product=cardmarket_id_product,
        market_price_eur=market_price_eur,
    )
    db.commit()
    db.refresh(product)
    return product


def delete_sealed_product(db: Session, user_id: int, sealed_id: int) -> bool:
    """Supprime un produit scellé de l'utilisateur ; ``False`` s'il est introuvable."""
    row = db.query(SealedProduct).filter(
        SealedProduct.id == sealed_id, SealedProduct.user_id == user_id
    ).first()
    if row is None:
        return False
    db.delete(row)
    db.commit()
    return True


def aggregate_sealed_stats(rows: list[SealedProduct]) -> dict[str, Any]:
    """Compteurs d'en-tête pour l'onglet Produits (quantité, valeur marché, gain)."""
    if not rows:
        return {
            "unique_products": 0,
            "total_quantity": 0,
            "estimated_market_eur": 0.0,
            "purchase_value_eur": 0.0,
            "gain_eur": 0.0,
            "gain_percent": None,
            "priced_products": 0,
            "with_article": 0,
            "by_type": {},
        }
    total_quantity = 0
    estimated_market = Decimal("0")
    purchase_value = Decimal("0")
    gain_basis_purchase = Decimal("0")
    gain_eur = Decimal("0")
    priced_products = 0
    with_article = 0
    by_type: dict[str, int] = {}
    for r in rows:
        qty = int(r.quantity)
        total_quantity += qty
        by_type[r.product_type] = by_type.get(r.product_type, 0) + 1
        if r.article_id is not None:
            with_article += 1
        if r.market_price_eur is not None:
            estimated_market += Decimal(r.market_price_eur) * qty
            priced_products += 1
        if r.purchase_price_eur is not None:
            purchase_value += Decimal(r.purchase_price_eur) * qty
        if r.market_price_eur is not None and r.purchase_price_eur is not None:
            gain_eur += (Decimal(r.market_price_eur) - Decimal(r.purchase_price_eur)) * qty
            gain_basis_purchase += Decimal(r.purchase_price_eur) * qty
    gain_percent = (
        round(float(gain_eur) / float(gain_basis_purchase) * 100.0, 1) if gain_basis_purchase > 0 else None
    )
    return {
        "unique_products": len(rows),
        "total_quantity": total_quantity,
        "estimated_market_eur": float(estimated_market),
        "purchase_value_eur": float(purchase_value),
        "gain_eur": round(float(gain_eur), 2),
        "gain_percent": gain_percent,
        "priced_products": priced_products,
        "with_article": with_article,
        "by_type": by_type,
    }
