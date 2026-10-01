"""Fiche d'une carte scannée : exemplaires possédés, ajout confirmé puis annulable, ordre de la collection."""

from __future__ import annotations

import asyncio
import datetime as dt
from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import models  # noqa: F401 — enregistre tous les mappers (relations croisées entre modèles)
from models.base import Base
from models.binder import Binder, BinderItem
from models.collection_card import CollectionCard
from services import collection_card_service, scan_stream_service
from services.scan_stream_hub import get_scan_stream_hub


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch) -> Iterator[Session]:
    """Base SQLite en mémoire, partagée avec les sessions que le service de scan ouvre lui-même (y compris hors thread)."""
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
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


def _added_scan_event(event_id: str, card: CollectionCard) -> dict[str, Any]:
    return {
        "event_id": event_id,
        "user_id": 1,
        "status": "added",
        "physical_language": card.language,
        "direction": "in",
        "tcgdex_card_id": card.tcgdex_card_id,
        "collection_card": {"id": card.id, "quantity": card.quantity},
    }


def test_adding_an_owned_card_moves_it_to_the_top_of_the_collection(db: Session) -> None:
    owned_card = _collection_card(db, language="fr", quantity=1)
    owned_card.last_added_at = dt.datetime(2026, 9, 1, tzinfo=dt.UTC)
    _collection_card(db, language="fr", quantity=1, tcgdex_card_id="sv10-112")
    db.commit()
    db.close()

    scan_stream_service._add_or_increment(1, _card_meta(), notes=None)

    rows = collection_card_service.list_collection_for_user(db, 1)
    assert rows[0].tcgdex_card_id == "me02-107"
    assert rows[0].quantity == 2


def test_undoing_a_new_card_removes_it_from_the_collection(db: Session) -> None:
    card_id = _collection_card(db, language="fr", quantity=1).id

    card_json, left_collection, remaining = scan_stream_service._remove_added_copy(1, card_id)

    assert card_json is not None
    assert left_collection is True
    assert remaining == 0
    db.expire_all()
    assert db.get(CollectionCard, card_id) is None


def test_undoing_one_of_several_copies_keeps_the_others(db: Session) -> None:
    card = _collection_card(db, language="fr", quantity=3)

    card_json, left_collection, remaining = scan_stream_service._remove_added_copy(1, card.id)

    assert card_json is not None
    assert card_json["quantity"] == 2
    assert left_collection is False
    assert remaining == 2


def test_undoing_a_card_placed_in_a_binder_restores_its_empty_slot(db: Session) -> None:
    card = _collection_card(db, language="ja", quantity=1)
    binder = Binder(id=1, user_id=1, name="151 AR")
    db.add(binder)
    db.flush()
    db.add(BinderItem(binder_id=binder.id, collection_card_id=card.id, position=3))
    db.commit()

    scan_stream_service._remove_added_copy(1, card.id)

    db.expire_all()
    slot_card = db.get(CollectionCard, card.id)
    assert slot_card is not None
    assert slot_card.is_placeholder is True
    assert slot_card.quantity == 0


def test_undoing_a_scan_removes_it_from_the_feed_once(db: Session) -> None:
    card = _collection_card(db, language="fr", quantity=2)
    hub = get_scan_stream_hub()
    hub.clear_events(1)
    asyncio.run(hub.publish(1, _added_scan_event("sheet-undo-test-01", card)))

    cancelled_event = asyncio.run(scan_stream_service.undo_added_scan(user_id=1, event_id="sheet-undo-test-01"))

    assert cancelled_event["status"] == "cancelled"
    assert cancelled_event["remaining_quantity"] == 1
    assert hub.find_event(1, "sheet-undo-test-01") is None
    with pytest.raises(LookupError):
        asyncio.run(scan_stream_service.undo_added_scan(user_id=1, event_id="sheet-undo-test-01"))


def test_only_an_added_scan_can_be_undone(db: Session) -> None:
    card = _collection_card(db, language="fr", quantity=1)
    hub = get_scan_stream_hub()
    hub.clear_events(1)
    asyncio.run(hub.publish(1, {**_added_scan_event("sheet-undo-test-02", card), "status": "removed"}))

    with pytest.raises(ValueError):
        asyncio.run(scan_stream_service.undo_added_scan(user_id=1, event_id="sheet-undo-test-02"))
    hub.clear_events(1)
