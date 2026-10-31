"""Set dont TCGdex mélange les images (M1S) : les cartes de collection montrent l'image Limitless de leur numéro."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import models  # noqa: F401
from models.base import Base
from models.collection_card import CollectionCard
from services import catalog_external_cards_service, collection_card_image_repair_service
from services.card_image_fallback_service import CardImageUrls
from services.catalog_external_cards_service import ExternalCard, limitless_image_of_shuffled_set


def _limitless_card(set_id: str, local_id: str) -> ExternalCard:
    return ExternalCard(
        local_id=local_id,
        name_ja=None,
        name_en=None,
        rarity=None,
        images=CardImageUrls(
            low=f"https://limitless.example/{set_id}_{local_id}_SM.png",
            high=f"https://limitless.example/{set_id}_{local_id}_LG.png",
        ),
        source="limitless",
    )


@pytest.fixture(autouse=True)
def limitless(monkeypatch: pytest.MonkeyPatch) -> None:
    """Limitless simulé : chaque numéro a son scan."""
    monkeypatch.setattr(catalog_external_cards_service, "external_card", _limitless_card)


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch) -> Iterator[Session]:
    """Base SQLite en mémoire, partagée avec la session que la réparation ouvre elle-même."""
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    monkeypatch.setattr(collection_card_image_repair_service, "SessionLocal", sessionmaker(bind=engine))
    with Session(engine) as session:
        yield session


def _collection_card(db: Session, tcgdex_card_id: str, language: str) -> CollectionCard:
    set_id, local_id = tcgdex_card_id.split("-")
    card = CollectionCard(
        user_id=1,
        tcgdex_card_id=tcgdex_card_id,
        tcgdex_set_id=set_id,
        card_number=local_id,
        display_name="Galvaran",
        language=language,
        image_url=f"https://assets.tcgdex.net/{language}/M/{set_id}/{local_id}/low.webp",
    )
    db.add(card)
    db.commit()
    db.refresh(card)
    return card


def test_a_card_of_a_set_with_shuffled_tcgdex_images_gets_its_limitless_image() -> None:
    image = limitless_image_of_shuffled_set("ja", "M1S", "070")

    assert image is not None
    assert image.low == "https://limitless.example/M1S_070_SM.png"


def test_cards_of_other_sets_or_languages_keep_their_tcgdex_image() -> None:
    assert limitless_image_of_shuffled_set("ja", "M2", "070") is None
    assert limitless_image_of_shuffled_set("fr", "M1S", "070") is None


def test_collection_cards_saved_with_a_shuffled_tcgdex_image_are_repaired_once(db: Session) -> None:
    shuffled_card = _collection_card(db, "M1S-070", "ja")
    other_set_card = _collection_card(db, "M2-070", "ja")

    first_run_replaced = collection_card_image_repair_service.replace_shuffled_tcgdex_images()
    second_run_replaced = collection_card_image_repair_service.replace_shuffled_tcgdex_images()

    db.expire_all()
    repaired_card = db.get(CollectionCard, shuffled_card.id)
    untouched_card = db.get(CollectionCard, other_set_card.id)
    assert repaired_card is not None and untouched_card is not None
    assert (first_run_replaced, second_run_replaced) == (1, 0)
    assert repaired_card.image_url == "https://limitless.example/M1S_070_SM.png"
    assert untouched_card.image_url == "https://assets.tcgdex.net/ja/M/M2/070/low.webp"
