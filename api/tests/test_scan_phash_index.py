"""Complément nocturne de l'index de scan : seules les cartes absentes de l'index livré sont calculées."""

from __future__ import annotations

import base64
import datetime as dt
import io
from collections import Counter
from collections.abc import Iterator
from typing import Any

import pytest
from PIL import Image, ImageDraw
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import models  # noqa: F401 — enregistre tous les mappers (relations croisées entre modèles)
from models.base import Base
from models.scan_phash_card import ScanPhashCard
from services import scan_phash_index_service as service
from services.card_image_fallback_service import CardImageUrls

_HASHES = bytes(range(64))


@pytest.fixture
def db() -> Iterator[Session]:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


class _FakeTcgdex:
    """TCGdex réduit au set japonais M6a : deux cartes connues de l'index livré, trois nouvelles."""

    def get_series(self, locale: str, series_id: str) -> dict[str, Any]:
        return {"sets": []}

    def list_sets(self, locale: str, page: int = 1, per_page: int = 50) -> list[dict[str, Any]]:
        if locale != "ja":
            return []
        return [{"id": "M6a", "cardCount": {"total": 5}}]

    def get_set(self, locale: str, set_id: str) -> dict[str, Any]:
        return {
            "id": set_id,
            "serie": {"id": "M"},
            "cards": [
                {"id": "M6a-001", "localId": "001", "name": "タマタマ"},
                {"id": "M6a-002", "localId": "002", "name": "アローラ ナッシー"},
                {"id": "M6a-150", "localId": "150", "name": "ゲンガー"},
                {"id": "M6a-151", "localId": "151", "name": "ダークライ＆クレセリアLEGEND"},
                {"id": "M6a-R", "localId": "R", "name": "ミュウ"},
            ],
        }


@pytest.fixture
def fake_sources(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Index livré, TCGdex, scans de repli et téléchargements simulés ; renvoie les URL téléchargées."""
    downloaded: list[str] = []
    shipped = service._ShippedIndex(
        keys=frozenset({"ja/M6a-001", "ja/M6a-002"}),
        cards_per_set=Counter({("ja", "M6a"): 2}),
    )
    monkeypatch.setattr(service, "_load_shipped_index", lambda url: shipped)
    monkeypatch.setattr(service, "TcgdexClientService", _FakeTcgdex)
    monkeypatch.setattr(
        service,
        "fallback_card_images",
        lambda locale, detail: {
            "150": CardImageUrls(low="https://cdn.example/M6a-150.jpg", high="https://cdn.example/M6a-150-hd.jpg"),
            "R": CardImageUrls(low="https://cdn.example/M6a-R.jpg", high="https://cdn.example/M6a-R-hd.jpg"),
        },
    )

    def fake_hash_image(http: Any, url: str | None) -> bytes | None:
        if url is None:
            return None
        downloaded.append(url)
        return None if url.endswith("M6a-R.jpg") else _HASHES

    monkeypatch.setattr(service, "_hash_image_at", fake_hash_image)
    service._delta_cache.clear()
    return downloaded


def test_only_cards_missing_from_the_shipped_index_are_computed(db: Session, fake_sources: list[str]) -> None:
    report = service.refresh_scan_phash_cards(db)

    rows = {row.tcgdex_card_id: row for row in db.query(ScanPhashCard).all()}
    assert set(rows) == {"M6a-150", "M6a-151", "M6a-R"}
    assert rows["M6a-150"].hashes == _HASHES
    assert rows["M6a-150"].image_url == "https://cdn.example/M6a-150.jpg"
    assert rows["M6a-151"].hashes is None
    assert rows["M6a-R"].hashes is None
    assert (report.cards_hashed, report.cards_without_image) == (1, 2)


def test_the_scanner_receives_only_the_computed_cards(db: Session, fake_sources: list[str]) -> None:
    service.refresh_scan_phash_cards(db)

    payload = service.scan_phash_delta_payload(db)

    assert payload["count"] == 1
    assert payload["cards"] == [
        [
            "M6a-150",
            "ja",
            "ゲンガー",
            "M6a",
            "150",
            base64.b64encode(_HASHES).decode("ascii"),
            "https://cdn.example/M6a-150.jpg",
        ]
    ]


def test_a_second_run_downloads_nothing_until_missing_images_are_due(db: Session, fake_sources: list[str]) -> None:
    service.refresh_scan_phash_cards(db)
    fake_sources.clear()

    service.refresh_scan_phash_cards(db)
    assert fake_sources == []

    for row in db.query(ScanPhashCard).filter(ScanPhashCard.hashes.is_(None)).all():
        row.checked_at = dt.datetime.now(dt.UTC) - dt.timedelta(days=4)
    db.commit()
    service.refresh_scan_phash_cards(db)
    assert fake_sources == ["https://cdn.example/M6a-R.jpg"]


def _card_picture(width: int, height: int, *, art_left: float) -> bytes:
    """Fausse carte : fond clair, illustration sombre placée à ``art_left``, bandeau de texte."""
    image = Image.new("RGB", (width, height), (235, 220, 120))
    draw = ImageDraw.Draw(image)
    draw.ellipse((width * art_left, height * 0.14, width * (art_left + 0.4), height * 0.45), fill=(40, 60, 160))
    draw.rectangle((width * 0.1, height * 0.6, width * 0.9, height * 0.66), fill=(30, 30, 30))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _differing_bits(a: bytes, b: bytes) -> int:
    return sum(bin(x ^ y).count("1") for x, y in zip(a, b, strict=True))


def test_the_same_card_at_another_resolution_stays_far_closer_than_another_card() -> None:
    card = service.compute_card_phash(_card_picture(245, 342, art_left=0.15))
    same_card_scanned_larger = service.compute_card_phash(_card_picture(734, 1024, art_left=0.15))
    other_card = service.compute_card_phash(_card_picture(245, 342, art_left=0.45))

    assert len(card) == 64
    assert _differing_bits(card, same_card_scanned_larger) * 3 < _differing_bits(card, other_card)
