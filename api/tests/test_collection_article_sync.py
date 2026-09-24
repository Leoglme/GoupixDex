"""Synchro « Ma Collection » ↔ articles en vente : une carte vendue quitte la collection."""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import models  # noqa: F401 — enregistre tous les mappers (relations croisées entre modèles)
from models.article import Article
from models.base import Base
from models.collection_card import CollectionCard
from services import collection_article_sync_service as sync


@pytest.fixture
def db() -> Iterator[Session]:
    """Base SQLite en mémoire avec le schéma complet."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _for_sale_article(db: Session, *, purchase_price: str = "2.50") -> Article:
    article = Article(
        user_id=1,
        title="Porygon-Z sv4m 077/066 - Future Flash - Pokémon Japonais",
        description="",
        purchase_price=Decimal(purchase_price),
        set_code="SV4M",
        card_number="077/066",
        pokemon_name="Porygon-Z",
    )
    db.add(article)
    db.commit()
    db.refresh(article)
    return article


def _linked_card(db: Session, article: Article, *, quantity: int = 1) -> CollectionCard:
    card = CollectionCard(
        user_id=1,
        tcgdex_card_id="SV4M-077",
        tcgdex_set_id="SV4M",
        card_number="077",
        display_name="Porygon-Z",
        language="ja",
        quantity=quantity,
        purchase_price_eur=Decimal("2.50"),
        article_id=article.id,
    )
    db.add(card)
    db.commit()
    db.refresh(card)
    return card


def test_sold_card_leaves_the_collection(db: Session) -> None:
    article = _for_sale_article(db)
    card = _linked_card(db, article)
    assert sync.remove_collection_card_for_sold_article(db, article) is True
    assert db.get(CollectionCard, card.id) is None


def test_selling_one_of_several_copies_keeps_the_others(db: Session) -> None:
    article = _for_sale_article(db)
    card = _linked_card(db, article, quantity=2)
    assert sync.remove_collection_card_for_sold_article(db, article) is True
    db.refresh(card)
    assert card.quantity == 1
    assert card.article_id is None


def test_selling_an_article_without_collection_card_changes_nothing(db: Session) -> None:
    article = _for_sale_article(db)
    assert sync.remove_collection_card_for_sold_article(db, article) is False


def test_purchase_price_follows_the_article_and_the_card(db: Session) -> None:
    article = _for_sale_article(db)
    card = _linked_card(db, article)
    article.purchase_price = Decimal("4.00")
    db.commit()
    sync.sync_purchase_price_to_collection(db, article)
    db.refresh(card)
    assert card.purchase_price_eur == Decimal("4.00")

    card.purchase_price_eur = Decimal("3.10")
    db.commit()
    sync.sync_purchase_price_to_article(db, card)
    db.refresh(article)
    assert article.purchase_price == Decimal("3.10")


def test_sealed_product_article_never_becomes_a_collection_card(db: Session) -> None:
    article = Article(
        user_id=1, title="ETB Flammes Fantasmagoriques", description="", purchase_price=Decimal(58), set_code="", card_number=""
    )
    db.add(article)
    db.commit()
    assert sync.ensure_collection_card_for_article(db, article) is None


def test_physical_language_trusts_the_resolved_set_over_the_title() -> None:
    assert sync._physical_language(Article(title="Cizayox / Scizor Sv3 116/108 AR - PSA 9"), "SV3-116") == "ja"
    assert sync._physical_language(Article(title="Rotom V (LOR 176) - Pokémon English"), "swsh11-176") == "en"
    assert sync._physical_language(Article(title="Mega Nanméouïe ex ASC - Pokémon Français"), "me02.5-253") == "fr"


def test_title_name_candidates_read_french_and_english_names() -> None:
    plumeline = Article(
        title="Plumeline / Oricorio ex PFL 110/094 - ME02: Flammes Fantasmagoriques  - Pokémon Japonais", set_code="PFL"
    )
    assert sync._title_name_candidates(plumeline) == ["Plumeline", "Oricorio ex"]
    rotom = Article(title="Rotom V (LOR 176) Origine Perdue - Motisma V 176/196 NM - Pokémon English", set_code="LOR")
    assert sync._title_name_candidates(rotom) == ["Rotom V", "Motisma V"]


def test_needs_refresh_flags_unresolved_mislabelled_and_japanese_named_cards() -> None:
    article = Article(title="PSA 9 - Alisma / Geeta Sv3 137/108", pokemon_name="Alisma")
    unresolved = CollectionCard(tcgdex_card_id="manual-article-38", language="fr", display_name="Alisma")
    wrong_language = CollectionCard(tcgdex_card_id="SV3-137", language="fr", display_name="Alisma")
    japanese_name = CollectionCard(tcgdex_card_id="SV3-137", language="ja", display_name="オモダカ")
    correct = CollectionCard(tcgdex_card_id="SV3-137", language="ja", display_name="Alisma")
    assert sync.needs_refresh(unresolved, article)
    assert sync.needs_refresh(wrong_language, article)
    assert sync.needs_refresh(japanese_name, article)
    assert not sync.needs_refresh(correct, article)
