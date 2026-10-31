"""Complément nocturne de l'index visuel du scanner : embeddings des cartes que ``embed-v3`` ne connaît pas."""

from __future__ import annotations

import base64
import datetime as dt
import io
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import models  # noqa: F401 — enregistre tous les mappers (relations croisées entre modèles)
from core.database import get_db
from models.base import Base
from models.scan_embed_card import ScanEmbedCard
from routes import scan_index_route
from services import scan_embed_index_service as service
from services import scan_index_cards_service as cards_service
from services.card_image_fallback_service import CardImageUrls

_EMBEDDING = bytes(range(256)) * 2 + bytes(4)
_MODEL_PATH = Path(__file__).resolve().parents[2] / "web" / "public" / "scan-model" / "mobileclip-s0-vision-fp16.onnx"


@pytest.fixture
def db() -> Iterator[Session]:
    """Base SQLite en mémoire, partagée avec le fil où tourne l'API de test."""
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


class _FakeTcgdex:
    """TCGdex réduit au set japonais SV11W : la Trioxhydre ex simple est dans l'index livré, pas ses deux secrètes."""

    def get_series(self, locale: str, series_id: str) -> dict[str, Any]:
        return {"sets": []}

    def list_sets(self, locale: str, page: int = 1, per_page: int = 50) -> list[dict[str, Any]]:
        return [{"id": "SV11W", "cardCount": {"total": 3}}] if locale == "ja" else []

    def get_set(self, locale: str, set_id: str) -> dict[str, Any]:
        return {
            "id": set_id,
            "serie": {"id": "SV"},
            "cards": [
                {"id": "SV11W-062", "localId": "062", "name": "サザンドラex"},
                {"id": "SV11W-163", "localId": "163", "name": "サザンドラex"},
                {"id": "SV11W-171", "localId": "171", "name": "サザンドラex"},
            ],
        }


class _FakeEmbedder:
    """Modèle simulé : un embedding fixe pour chaque image lisible."""

    def embed_images(self, images: list[bytes | None]) -> list[bytes | None]:
        return [_EMBEDDING if image is not None else None for image in images]


@pytest.fixture
def fake_sources(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Index livré, TCGdex, scans de repli, téléchargements et modèle simulés ; renvoie les URL téléchargées."""
    downloaded: list[str] = []
    shipped = cards_service.ShippedIndex(names={"ja/SV11W-062": "サザンドラex"})
    monkeypatch.setattr(service, "load_shipped_index", lambda url, min_cards: shipped)
    monkeypatch.setattr(service, "TcgdexClientService", _FakeTcgdex)
    monkeypatch.setattr(
        cards_service,
        "fallback_card_images",
        lambda locale, detail: {
            local_id: CardImageUrls(low=f"https://cdn.example/SV11W-{local_id}.jpg", high=f"https://cdn.example/SV11W-{local_id}-hd.jpg")
            for local_id in ("062", "163", "171")
        },
    )

    def fake_download(http: Any, url: str | None) -> bytes | None:
        if url is None:
            return None
        downloaded.append(url)
        return None if url.endswith("171.jpg") else b"image"

    monkeypatch.setattr(service, "download_image", fake_download)
    monkeypatch.setattr(service, "_load_card_embedder", _FakeEmbedder)
    service._delta_cache.clear()
    return downloaded


def test_only_cards_missing_from_the_shipped_visual_index_are_computed(db: Session, fake_sources: list[str]) -> None:
    report = service.refresh_scan_embed_cards(db)

    rows = {row.tcgdex_card_id: row for row in db.query(ScanEmbedCard).all()}
    assert set(rows) == {"SV11W-163", "SV11W-171"}
    assert rows["SV11W-163"].embedding == _EMBEDDING
    assert rows["SV11W-163"].image_url == "https://cdn.example/SV11W-163.jpg"
    assert rows["SV11W-171"].embedding is None
    assert (report.cards_computed, report.cards_without_image) == (1, 1)


def test_the_model_is_not_downloaded_when_no_card_is_missing(
    db: Session, fake_sources: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    service.refresh_scan_embed_cards(db)
    fake_sources.clear()

    def model_must_not_load() -> _FakeEmbedder:
        raise AssertionError("modèle téléchargé sans carte à calculer")

    monkeypatch.setattr(service, "_load_card_embedder", model_must_not_load)
    service.refresh_scan_embed_cards(db)

    assert fake_sources == []


@pytest.fixture
def client(db: Session) -> TestClient:
    """API réduite aux compléments d'index de scan."""
    app = FastAPI()
    app.include_router(scan_index_route.router)
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def test_the_scanner_downloads_the_computed_embeddings_again_only_once_they_change(
    db: Session, fake_sources: list[str], client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    service.refresh_scan_embed_cards(db)

    response = client.get("/scan-index/embed-delta", headers={"Accept-Encoding": "gzip"})
    payload = response.json()
    etag = response.headers["etag"]

    assert response.headers["content-encoding"] == "gzip"
    assert (payload["version"], payload["dim"], payload["count"]) == (3, 512, 1)
    assert payload["cards"] == [
        ["SV11W-163", "ja", "サザンドラex", "SV11W", "163", base64.b64encode(_EMBEDDING).decode("ascii")]
    ]
    assert client.get("/scan-index/embed-delta", headers={"If-None-Match": etag}).status_code == 304

    monkeypatch.setattr(service, "download_image", lambda http, url: b"image")
    for row in db.query(ScanEmbedCard).filter(ScanEmbedCard.embedding.is_(None)).all():
        row.checked_at = dt.datetime.now(dt.UTC) - dt.timedelta(days=4)
    db.commit()
    service.refresh_scan_embed_cards(db)

    refreshed = client.get("/scan-index/embed-delta", headers={"If-None-Match": etag})
    assert refreshed.status_code == 200
    assert refreshed.json()["count"] == 2


def _decoded(row: bytes) -> np.ndarray:
    scale = np.frombuffer(row[512:], dtype="<f4")[0]
    return np.frombuffer(row[:512], dtype=np.int8).astype(np.float32) * scale


def test_a_quantised_embedding_keeps_the_similarity_of_the_original() -> None:
    rng = np.random.default_rng(7)
    card = rng.normal(size=512)
    same_card_photographed = card + rng.normal(scale=0.4, size=512)

    quantised = service.quantised_embedding(card)
    original_similarity = float(card @ same_card_photographed) / (np.linalg.norm(card) * np.linalg.norm(same_card_photographed))
    decoded_similarity = float(_decoded(quantised) @ _decoded(service.quantised_embedding(same_card_photographed)))

    assert len(quantised) == 516
    assert abs(float(np.linalg.norm(_decoded(quantised))) - 1.0) < 0.01
    assert abs(decoded_similarity - original_similarity) < 0.01


def _card_picture(width: int, height: int, *, art_color: tuple[int, int, int]) -> bytes:
    """Fausse carte : cadre jaune, illustration ronde de la couleur donnée, bandeau de texte."""
    image = Image.new("RGB", (width, height), (235, 220, 120))
    draw = ImageDraw.Draw(image)
    draw.ellipse((width * 0.15, height * 0.14, width * 0.85, height * 0.45), fill=art_color)
    draw.rectangle((width * 0.1, height * 0.6, width * 0.9, height * 0.66), fill=(30, 30, 30))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.mark.skipif(not _MODEL_PATH.exists(), reason="modèle du scanner absent")
def test_the_scanner_model_places_the_same_card_closer_than_another_card() -> None:
    pytest.importorskip("onnxruntime")
    embedder = service._MobileClipEmbedder(_MODEL_PATH.read_bytes())

    card, same_card_larger, other_card, unreadable = embedder.embed_images(
        [
            _card_picture(245, 342, art_color=(40, 60, 160)),
            _card_picture(734, 1024, art_color=(40, 60, 160)),
            _card_picture(245, 342, art_color=(200, 40, 40)),
            b"not an image",
        ]
    )

    assert card is not None and same_card_larger is not None and other_card is not None
    assert unreadable is None
    assert float(_decoded(card) @ _decoded(same_card_larger)) > float(_decoded(card) @ _decoded(other_card))
