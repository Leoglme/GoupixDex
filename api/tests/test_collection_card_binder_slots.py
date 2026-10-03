"""Ranger une carte de la collection dans la pochette vide de son Pokémon, depuis sa fiche."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import models  # noqa: F401 — enregistre tous les mappers (relations croisées entre modèles)
from models.base import Base
from models.binder import Binder, BinderItem
from models.collection_card import CollectionCard
from services import binder_service, collection_card_lookup_service


@pytest.fixture
def db() -> Iterator[Session]:
    """Base SQLite en mémoire."""
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(autouse=True)
def read_pokedex_card_ids(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """TCGdex simulé : chaque carte lue est un Pikachu (n° 25) ; la liste garde les cartes lues."""
    card_ids: list[str] = []

    def fake_fetch_card_pokedex_number(*, tcgdex_card_id: str, physical_language: str) -> int:
        card_ids.append(tcgdex_card_id)
        return 25

    monkeypatch.setattr(binder_service, "fetch_card_pokedex_number", fake_fetch_card_pokedex_number)
    return card_ids


def _japanese_card(
    db: Session,
    tcgdex_card_id: str,
    *,
    quantity: int = 1,
    is_placeholder: bool = False,
) -> CollectionCard:
    card = CollectionCard(
        user_id=1,
        tcgdex_card_id=tcgdex_card_id,
        tcgdex_set_id=tcgdex_card_id.split("-")[0],
        card_number=tcgdex_card_id.split("-")[1],
        display_name="Pikachu",
        language="ja",
        quantity=quantity,
        is_placeholder=is_placeholder,
        rarity="Illustration rare",
    )
    db.add(card)
    db.commit()
    db.refresh(card)
    return card


def _kanto_binder(db: Session, *, pokedex_region: str | None = "kanto") -> Binder:
    """Classeur 151-AR : Bulbizarre AR japonaise en pochette 0, pochette 4 réservée à Pikachu (n° 25)."""
    db.add(Binder(id=1, user_id=1, name="151-AR", pokedex_region=pokedex_region, pokedex_slots={"0": 1, "4": 25}))
    db.flush()
    bulbasaur = _japanese_card(db, "SV2a-166")
    _put_in_binder(db, bulbasaur, 0)
    binder = binder_service.get_binder_with_cards(db, 1, 1)
    assert binder is not None
    return binder


def _put_in_binder(db: Session, card: CollectionCard, position: int) -> None:
    db.add(BinderItem(binder_id=1, collection_card_id=card.id, position=position))
    db.commit()


def test_an_owned_card_is_offered_the_empty_pocket_of_its_pokemon(db: Session) -> None:
    _kanto_binder(db)
    pikachu = _japanese_card(db, "SV2a-173")

    slots = binder_service.fillable_binder_slots_for_collection_card(db, 1, pikachu)

    assert slots == [{"binder_id": 1, "binder_name": "151-AR", "kind": "pokedex_slot", "position": 4}]


def test_a_wanted_card_of_a_binder_is_offered_no_pocket(db: Session) -> None:
    _kanto_binder(db)
    wanted_pikachu = _japanese_card(db, "SV2a-173", quantity=0, is_placeholder=True)

    assert binder_service.fillable_binder_slots_for_collection_card(db, 1, wanted_pikachu) == []


def test_tcgdex_is_not_read_without_a_pokedex_binder(db: Session, read_pokedex_card_ids: list[str]) -> None:
    _kanto_binder(db, pokedex_region=None)
    pikachu = _japanese_card(db, "SV2a-173")

    assert binder_service.fillable_binder_slots_for_collection_card(db, 1, pikachu) == []
    assert read_pokedex_card_ids == []


def test_placing_a_card_puts_it_in_the_empty_pocket_of_its_pokemon(db: Session) -> None:
    binder = _kanto_binder(db)
    pikachu = _japanese_card(db, "SV2a-173")

    binder_placement = binder_service.place_collection_card_in_free_slot(db, binder, pikachu)

    assert binder_placement == {"binder_id": 1, "binder_name": "151-AR", "kind": "pokedex_slot", "position": 4}
    assert db.query(BinderItem).filter(BinderItem.collection_card_id == pikachu.id).one().position == 4


def test_placing_a_card_in_a_binder_without_room_for_it_fails(db: Session) -> None:
    binder = _kanto_binder(db)
    _put_in_binder(db, _japanese_card(db, "SV4a-205"), 4)
    pikachu = _japanese_card(db, "SV2a-173")
    binder = binder_service.get_binder_with_cards(db, 1, 1)
    assert binder is not None

    with pytest.raises(ValueError, match="pas de place"):
        binder_service.place_collection_card_in_free_slot(db, binder, pikachu)


class _TcgdexWithSharedJapaneseId:
    """Même id ``sv10-112`` : Sulfura ex (n° 146) en japonais, Abo (n° 23) dans les autres langues."""

    def __init__(self) -> None:
        self.read_locales: list[str] = []

    def get_card(self, locale: str, _card_id: str) -> dict[str, Any]:
        self.read_locales.append(locale)
        return {"dexId": [146] if locale == "ja" else [23]}


class _TcgdexWithoutTheCard:
    def __init__(self) -> None:
        self.read_count = 0

    def get_card(self, _locale: str, card_id: str) -> dict[str, Any]:
        self.read_count += 1
        raise ValueError(f"no card {card_id}")


def test_a_japanese_card_reads_its_pokedex_number_in_japanese_only_once(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(collection_card_lookup_service, "_pokedex_number_cache", {})
    tcgdex = _TcgdexWithSharedJapaneseId()

    pokedex_numbers = [
        collection_card_lookup_service.fetch_card_pokedex_number(
            tcgdex_card_id="sv10-112", physical_language="ja", tcgdex=tcgdex
        )
        for _ in range(2)
    ]

    assert pokedex_numbers == [146, 146]
    assert tcgdex.read_locales == ["ja"]


def test_a_card_missing_from_tcgdex_is_read_again_next_time(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(collection_card_lookup_service, "_pokedex_number_cache", {})
    tcgdex = _TcgdexWithoutTheCard()

    for _ in range(2):
        pokedex_number = collection_card_lookup_service.fetch_card_pokedex_number(
            tcgdex_card_id="S10b-075", physical_language="ja", tcgdex=tcgdex
        )
        assert pokedex_number is None

    assert tcgdex.read_count == 2
