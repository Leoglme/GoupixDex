"""Prix d'achat repris des commandes Cardmarket : au scan d'une carte, et à l'import d'une commande."""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import models  # noqa: F401 — enregistre tous les mappers (relations croisées entre modèles)
from models.article import Article
from models.base import Base
from models.cardmarket_order import CardmarketOrder
from models.cardmarket_order_line import CardmarketOrderLine
from models.collection_card import CollectionCard
from services import cardmarket_order_service, scan_stream_service


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch) -> Iterator[Session]:
    """Base SQLite en mémoire, partagée avec les sessions que le service de scan ouvre lui-même."""
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    monkeypatch.setattr(scan_stream_service, "SessionLocal", sessionmaker(bind=engine))
    with Session(engine) as session:
        yield session


def _order_line(
    db: Session,
    *,
    unit_price: str,
    paid_on: dt.date,
    set_code: str = "sv2a",
    card_number: str = "173",
    language_code: str = "JP",
    quantity: int = 1,
) -> CardmarketOrderLine:
    order = CardmarketOrder(
        user_id=1,
        external_order_id=f"order-{paid_on.isoformat()}-{unit_price}",
        paid_at=dt.datetime.combine(paid_on, dt.time(12), tzinfo=dt.UTC),
        items_subtotal=Decimal(unit_price),
        shipping_fee=Decimal("1.25"),
        order_total=Decimal(unit_price) + Decimal("1.25"),
    )
    db.add(order)
    db.flush()
    line = CardmarketOrderLine(
        order_id=order.id,
        line_index=0,
        quantity=quantity,
        raw_label="Pikachu",
        pokemon_key="pikachu",
        card_number=card_number,
        language_code=language_code,
        condition_label="NM",
        set_code=set_code,
        variant_token="AR",
        unit_price_eur=Decimal(unit_price),
    )
    db.add(line)
    db.commit()
    return line


def _pikachu_meta() -> dict[str, Any]:
    """Fiche TCGdex de la Pikachu AR japonaise de « Pokémon Card 151 » (SV2a-173)."""
    return {
        "tcgdex_card_id": "SV2a-173",
        "tcgdex_set_id": "SV2a",
        "set_code": "SV2A",
        "set_name": "Pokémon Card 151",
        "card_number": "173",
        "card_name_en": "Pikachu",
        "card_name_fr": "Pikachu",
        "card_name_ja": "ピカチュウ",
        "display_name": "Pikachu",
        "rarity": "Illustration rare",
        "dex_id": 25,
        "language": "ja",
        "image_url": None,
        "cardmarket_id_product": None,
        "market_price_eur": 12.0,
    }


def _owned_card(db: Session, **overrides: Any) -> CollectionCard:
    fields: dict[str, Any] = {
        "user_id": 1,
        "tcgdex_card_id": "SV2a-173",
        "tcgdex_set_id": "SV2a",
        "set_code": "SV2A",
        "card_number": "173",
        "display_name": "Pikachu",
        "language": "ja",
        "quantity": 1,
        **overrides,
    }
    card = CollectionCard(**fields)
    db.add(card)
    db.commit()
    db.refresh(card)
    return card


def test_a_scanned_card_takes_the_price_of_its_latest_cardmarket_purchase(db: Session) -> None:
    _order_line(db, unit_price="9.00", paid_on=dt.date(2026, 9, 1))
    _order_line(db, unit_price="11.50", paid_on=dt.date(2026, 10, 20))
    db.close()

    card_json, _, _ = scan_stream_service._add_and_place_in_awaiting_binder(1, _pikachu_meta())

    assert card_json["purchase_price_eur"] == 11.5


def test_a_purchase_already_listed_for_sale_is_skipped(db: Session) -> None:
    _order_line(db, unit_price="9.00", paid_on=dt.date(2026, 9, 1))
    latest = _order_line(db, unit_price="11.50", paid_on=dt.date(2026, 10, 20))
    db.add(Article(user_id=1, title="Pikachu", description="", purchase_price=Decimal("11.50"), order_line_id=latest.id))
    db.commit()
    card = _owned_card(db)

    assert cardmarket_order_service.fill_purchase_price_from_orders(db, card) is True
    assert card.purchase_price_eur == Decimal("9.00")


@pytest.mark.parametrize(
    ("set_code", "card_number", "language_code"),
    [("sv2a", "173", "FR"), ("sv4a", "173", "JP"), ("sv2a", "174", "JP")],
)
def test_a_purchase_of_another_print_gives_no_price(
    db: Session, set_code: str, card_number: str, language_code: str
) -> None:
    _order_line(
        db,
        unit_price="11.50",
        paid_on=dt.date(2026, 10, 20),
        set_code=set_code,
        card_number=card_number,
        language_code=language_code,
    )
    card = _owned_card(db)

    assert cardmarket_order_service.fill_purchase_price_from_orders(db, card) is False
    assert card.purchase_price_eur is None


def test_an_international_card_matches_its_official_set_code_and_unpadded_number(db: Session) -> None:
    _order_line(
        db, unit_price="0.50", paid_on=dt.date(2026, 10, 20), set_code="mew", card_number="074", language_code="FR"
    )
    card = _owned_card(db, tcgdex_card_id="sv03.5-074", tcgdex_set_id="sv03.5", set_code="MEW", card_number="74")
    card.language = "fr"

    assert cardmarket_order_service.fill_purchase_price_from_orders(db, card) is True
    assert card.purchase_price_eur == Decimal("0.50")


@pytest.mark.parametrize("overrides", [{"purchase_price_eur": Decimal("4.00")}, {"is_placeholder": True, "quantity": 0}])
def test_a_card_with_a_price_or_not_owned_keeps_its_price(db: Session, overrides: dict[str, Any]) -> None:
    _order_line(db, unit_price="11.50", paid_on=dt.date(2026, 10, 20))
    card = _owned_card(db, **overrides)
    price_before = card.purchase_price_eur

    assert cardmarket_order_service.fill_purchase_price_from_orders(db, card) is False
    assert card.purchase_price_eur == price_before


def test_importing_an_order_prices_the_cards_scanned_before(db: Session) -> None:
    scanned = _owned_card(db)
    article = Article(user_id=1, title="Pikachu", description="", purchase_price=Decimal("10.00"))
    db.add(article)
    db.commit()
    for_sale = _owned_card(db, article_id=article.id)
    already_priced = _owned_card(db, purchase_price_eur=Decimal("4.00"))
    _order_line(db, unit_price="11.50", paid_on=dt.date(2026, 10, 20), quantity=3)

    filled = cardmarket_order_service.fill_collection_purchase_prices_from_orders(db, 1)

    for card in (scanned, for_sale, already_priced):
        db.refresh(card)
    assert filled == 1
    assert scanned.purchase_price_eur == Decimal("11.50")
    assert for_sale.purchase_price_eur is None
    assert already_priced.purchase_price_eur == Decimal("4.00")
