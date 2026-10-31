"""Libellés latins des cartes japonaises : aucune écriture japonaise ne doit atteindre l'écran."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import models  # noqa: F401 — enregistre tous les mappers (relations croisées entre modèles)
from models.base import Base
from models.collection_card import CollectionCard
from services import japanese_latin_labels_service as labels
from services.catalog_prefill_service import _pick_display_pokemon_name


@pytest.fixture
def sources(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    """M6a : Moltres connu de Limitless (105), Alolan Exeggutor de TCGplayer (104), Mew de son n° Pokédex (151)."""
    dex_lookups = {"count": 0}

    def fake_dex_id(card_id: str) -> int | None:
        dex_lookups["count"] += 1
        return 151 if card_id == "M6a-151" else None

    limitless_names = {"M6a": {"105": "Moltres"}}
    tcgplayer_names = {"M6a": {"104": "Alolan Exeggutor"}}
    set_names = {"M6a": "30th Celebration"}
    monkeypatch.setattr(labels, "limitless_en_card_names_for_set", lambda set_id: limitless_names.get(set_id, {}))
    monkeypatch.setattr(labels, "tcgplayer_japanese_card_names", lambda set_id: tcgplayer_names.get(set_id, {}))
    monkeypatch.setattr(labels, "japanese_card_english_name", lambda name, dex: "Mew" if dex == 151 else None)
    monkeypatch.setattr(labels, "_japanese_card_dex_id", fake_dex_id)
    monkeypatch.setattr(labels, "latin_display_name_for_ja_set", set_names.get)
    return dex_lookups


def test_every_japanese_card_of_a_set_gets_a_latin_label(sources: dict[str, int]) -> None:
    cards: list[dict[str, Any]] = [
        {"id": "M6a-104", "localId": "104", "name": "アローラ ナッシー"},
        {"id": "M6a-105", "localId": "105", "name": "ファイヤー"},
        {"id": "M6a-151", "localId": "151", "name": "ミュウ"},
        {"id": "M6a-160", "localId": "160", "name": "トレーナーズポスト"},
        {"id": "M6a-153", "localId": "153", "name": "N"},
    ]

    labels.attach_latin_card_labels(cards)

    assert [card.get("display_name") for card in cards] == ["Alolan Exeggutor", "Moltres", "Mew", "Carte 160", None]
    assert sources["count"] == 2


def test_a_japanese_series_takes_its_latin_name_or_its_code() -> None:
    assert labels.latin_series_name("S", "剣と盾") == "Sword & Shield"
    assert labels.latin_series_name("L", "LEGEND") == "LEGEND"
    assert labels.latin_series_name("N", "ポケモンカードゲーム ネクスト") == "N"


def test_a_japanese_set_name_takes_the_limitless_name_or_the_code(sources: dict[str, int]) -> None:
    assert labels.latin_set_name("M6a", "30th CELEBRATION") == "30th CELEBRATION"
    assert labels.latin_set_name("M6a", "30周年セレブレーション") == "30th Celebration"
    assert labels.latin_set_name("M9", "ニンジャスピナー") == "M9"


def test_the_listing_form_never_prefills_a_japanese_pokemon_name() -> None:
    assert _pick_display_pokemon_name("ja", "Moltres", "Sulfura", "ファイヤー") == "Sulfura"
    assert _pick_display_pokemon_name("ja", "", "", "ファイヤー") == "Pokémon"


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch) -> Iterator[Session]:
    """Base SQLite en mémoire, partagée avec la session que la réparation ouvre elle-même."""
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    monkeypatch.setattr(labels, "SessionLocal", sessionmaker(bind=engine))
    with Session(engine) as session:
        yield session


def _saved_card(db: Session, card_id: str, set_name: str, display_name: str, language: str = "ja") -> CollectionCard:
    set_id, local_id = card_id.rsplit("-", 1)
    card = CollectionCard(
        user_id=1,
        tcgdex_card_id=card_id,
        tcgdex_set_id=set_id,
        set_name=set_name,
        card_number=local_id,
        display_name=display_name,
        language=language,
    )
    db.add(card)
    db.commit()
    return card


def test_saved_japanese_cards_are_relabelled_at_startup(db: Session, sources: dict[str, int]) -> None:
    trainer = _saved_card(db, "M6a-105", "30周年セレブレーション", "ファイヤー")
    pokemon = _saved_card(db, "M6a-151", "30th Celebration", "Mew")
    learned_since = _saved_card(db, "M6a-104", "30th Celebration", "Carte 104")
    french = _saved_card(db, "sv03.5-151", "151", "Mew", language="fr")

    assert labels.relabel_japanese_collection_cards() == 2

    db.expire_all()
    assert (trainer.set_name, trainer.display_name) == ("30th Celebration", "Moltres")
    assert (pokemon.set_name, pokemon.display_name) == ("30th Celebration", "Mew")
    assert learned_since.display_name == "Alolan Exeggutor"
    assert french.display_name == "Mew"
