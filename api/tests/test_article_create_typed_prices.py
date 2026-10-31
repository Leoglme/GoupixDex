"""Mise en ligne d'une carte de la collection : les prix tapés au clavier français (« 0,1 », « 1,50 ») sont acceptés."""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import models  # noqa: F401
from core.database import get_db
from core.deps import get_current_user
from models.article import Article
from models.base import Base
from models.collection_card import CollectionCard
from models.user import User
from routes import articles

USER_ID = 1


@pytest.fixture
def db() -> Iterator[Session]:
    """Base SQLite en mémoire, partagée avec le fil où tourne l'API de test."""
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def client(db: Session, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """API réduite aux routes des articles, connectée en tant que Léo, sans relevé des prix Cardmarket."""
    monkeypatch.setattr(articles, "refresh_article_market_reference", lambda article: None)
    app = FastAPI()
    app.include_router(articles.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: User(id=USER_ID, email="leo@example.test")
    return TestClient(app)


@pytest.fixture
def collection_card(db: Session) -> CollectionCard:
    """Carte de la collection mise en ligne, sans prix d'achat noté."""
    card = CollectionCard(
        user_id=USER_ID,
        tcgdex_card_id="SV4M-077",
        tcgdex_set_id="SV4M",
        card_number="077",
        display_name="Porygon-Z",
        language="ja",
    )
    db.add(card)
    db.commit()
    db.refresh(card)
    return card


def _create_article(
    client: TestClient, collection_card: CollectionCard, *, purchase_price: str, sell_price: str
) -> Response:
    """Envoie la fiche comme l'assistant de mise en ligne d'une carte, sans les photos (elles partiraient sur Supabase)."""
    return client.post(
        "/articles",
        data={
            "title": "Porygon-Z SV4M 077 - Pokémon Japonais",
            "description": "Carte Pokémon japonaise en excellent état.",
            "purchase_price": purchase_price,
            "condition": "Near Mint",
            "is_graded": "false",
            "pokemon_name": "Porygon-Z",
            "set_code": "SV4M",
            "card_number": "077",
            "sell_price": sell_price,
            "publish_to_vinted": "false",
            "publish_to_ebay": "false",
            "is_sold": "false",
            "collection_card_id": str(collection_card.id),
        },
    )


def test_prices_typed_with_a_comma_are_saved(client: TestClient, db: Session, collection_card: CollectionCard) -> None:
    response = _create_article(client, collection_card, purchase_price="0,1", sell_price="1,50")

    assert response.status_code == 201
    article = db.get(Article, response.json()["article"]["id"])
    assert article is not None
    assert article.purchase_price == Decimal("0.10")
    assert article.sell_price == Decimal("1.50")
    assert collection_card.article_id == article.id
    assert collection_card.purchase_price_eur == Decimal("0.10")


def test_prices_typed_with_a_dot_or_spaces_are_saved(
    client: TestClient, db: Session, collection_card: CollectionCard
) -> None:
    response = _create_article(client, collection_card, purchase_price="12.5", sell_price="1 234,50")

    assert response.status_code == 201
    article = db.get(Article, response.json()["article"]["id"])
    assert article is not None
    assert article.purchase_price == Decimal("12.50")
    assert article.sell_price == Decimal("1234.50")


@pytest.mark.parametrize("typed_price", ["abc", "1.234,50", "NaN"])
def test_an_unreadable_price_is_refused_with_a_message_naming_the_field(
    client: TestClient, db: Session, collection_card: CollectionCard, typed_price: str
) -> None:
    response = _create_article(client, collection_card, purchase_price=typed_price, sell_price="1,50")

    assert response.status_code == 400
    assert response.json()["detail"] == f"Prix d'achat invalide : « {typed_price} »."
    assert db.query(Article).count() == 0
