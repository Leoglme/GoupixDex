"""Fiche d'une carte scannée : exemplaires déjà possédés, ajout ou retrait confirmé, fiche TCGdex gardée en cache."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import models  # noqa: F401 — enregistre tous les mappers (relations croisées entre modèles)
from models.base import Base
from models.collection_card import CollectionCard
from services import scan_stream_service


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch) -> Iterator[Session]:
    """Base SQLite en mémoire, partagée avec les sessions que le service de scan ouvre lui-même."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    monkeypatch.setattr(scan_stream_service, "SessionLocal", sessionmaker(bind=engine))
    with Session(engine) as session:
        yield session


@pytest.fixture(autouse=True)
def empty_card_meta_cache() -> Iterator[None]:
    """Chaque test part d'un cache de fiches TCGdex vide."""
    scan_stream_service._card_meta_cache.clear()
    yield
    scan_stream_service._card_meta_cache.clear()


def _card_meta(tcgdex_card_id: str = "me02-107", language: str = "fr") -> dict[str, Any]:
    return {
        "tcgdex_card_id": tcgdex_card_id,
        "tcgdex_set_id": "me02",
        "set_code": "ME02",
        "set_name": "Flammes Fantasmagoriques",
        "card_number": "107",
        "printed_set_total": 94,
        "card_name_en": "Ambipom",
        "card_name_fr": "Capidextre",
        "card_name_ja": "エテボース",
        "display_name": "Capidextre",
        "rarity": "Illustration Rare",
        "language": language,
        "image_url": "https://assets.tcgdex.net/fr/me/me02/107/low.webp",
        "cardmarket_id_product": 123,
        "market_price_eur": 2.11,
    }


def _collection_card(
    db: Session,
    *,
    language: str,
    quantity: int,
    is_placeholder: bool = False,
    tcgdex_card_id: str = "me02-107",
) -> CollectionCard:
    card = CollectionCard(
        user_id=1,
        tcgdex_card_id=tcgdex_card_id,
        tcgdex_set_id="me02",
        card_number="107",
        display_name="Capidextre",
        language=language,
        quantity=quantity,
        is_placeholder=is_placeholder,
    )
    db.add(card)
    db.commit()
    db.refresh(card)
    return card


def test_preview_counts_english_and_french_copies_of_the_same_print(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(scan_stream_service, "fetch_card_for_collection", lambda **_: _card_meta())
    _collection_card(db, language="fr", quantity=2)
    _collection_card(db, language="en", quantity=1)
    _collection_card(db, language="ja", quantity=4)

    preview = scan_stream_service.build_scanned_card_preview(db, 1, "me02-107", "fr")

    assert preview["owned_quantity"] == 3
    assert preview["market_price_eur"] == 2.11
    assert preview["printed_set_total"] == 94


def test_preview_ignores_empty_binder_placeholders(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scan_stream_service, "fetch_card_for_collection", lambda **_: _card_meta())
    _collection_card(db, language="fr", quantity=0, is_placeholder=True)

    preview = scan_stream_service.build_scanned_card_preview(db, 1, "me02-107", "fr")

    assert preview["owned_quantity"] == 0


def test_card_sheet_is_read_once_from_tcgdex_for_the_preview_and_the_add(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_fetch(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs["tcgdex_card_id"])
        return _card_meta()

    monkeypatch.setattr(scan_stream_service, "fetch_card_for_collection", fake_fetch)

    scan_stream_service.scanned_card_meta("me02-107", "fr")
    scan_stream_service.scanned_card_meta("ME02-107", "fr")

    assert calls == ["me02-107"]


def test_card_sheet_is_read_again_once_stale(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_fetch(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs["tcgdex_card_id"])
        return _card_meta()

    monkeypatch.setattr(scan_stream_service, "fetch_card_for_collection", fake_fetch)
    scan_stream_service.scanned_card_meta("me02-107", "fr")
    cache_key = ("me02-107", "fr")
    cached_at, meta = scan_stream_service._card_meta_cache[cache_key]
    scan_stream_service._card_meta_cache[cache_key] = (cached_at - scan_stream_service._CARD_META_TTL_SEC - 1, meta)

    scan_stream_service.scanned_card_meta("me02-107", "fr")

    assert len(calls) == 2


def test_adding_a_card_fills_its_empty_binder_placeholder(db: Session) -> None:
    placeholder = _collection_card(db, language="fr", quantity=0, is_placeholder=True)
    db.close()

    card_json, created = scan_stream_service._add_or_increment(1, _card_meta(), notes=None)

    assert created is True
    assert card_json["id"] == placeholder.id
    assert card_json["quantity"] == 1
    assert card_json["is_placeholder"] is False


def test_adding_an_owned_card_adds_one_copy(db: Session) -> None:
    _collection_card(db, language="fr", quantity=2)
    db.close()

    card_json, created = scan_stream_service._add_or_increment(1, _card_meta(), notes=None)

    assert created is False
    assert card_json["quantity"] == 3


def test_removing_a_card_never_deletes_an_empty_binder_placeholder(db: Session) -> None:
    placeholder = _collection_card(db, language="fr", quantity=0, is_placeholder=True)

    card_json, deleted, _ = scan_stream_service._decrement_or_delete(1, "me02-107", "fr")

    assert card_json is None
    assert deleted is False
    db.expire_all()
    assert db.get(CollectionCard, placeholder.id) is not None


def test_removing_an_english_card_leaves_the_japanese_card_sharing_its_id(db: Session) -> None:
    japanese_card = _collection_card(db, language="ja", quantity=1, tcgdex_card_id="sv10-112")

    card_json, _, _ = scan_stream_service._decrement_or_delete(1, "sv10-112", "en")

    assert card_json is None
    db.expire_all()
    assert db.get(CollectionCard, japanese_card.id) is not None


def test_removing_a_card_scanned_in_french_takes_the_english_copy(db: Session) -> None:
    english_card = _collection_card(db, language="en", quantity=2)

    card_json, deleted, remaining = scan_stream_service._decrement_or_delete(1, "me02-107", "fr")

    assert card_json is not None
    assert card_json["id"] == english_card.id
    assert deleted is False
    assert remaining == 1
