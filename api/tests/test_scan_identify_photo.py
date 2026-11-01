"""Recours du scanner : lire le code et le numéro imprimés d'une carte que ses empreintes ne départagent pas."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.deps import get_current_user
from models.user import User
from routes import scan_stream_route
from services import scan_stream_service

_OCR_OF_TRIOXHYDRE_SR: dict[str, Any] = {
    "pokemon_name": "サザンドラ",
    "pokemon_name_english": None,
    "set_code": "SV11W",
    "card_number": "163/086",
    "card_number_denominator": "086",
}


@pytest.fixture
def client() -> TestClient:
    """API réduite au flux de scan, connectée en tant que Léo."""
    app = FastAPI()
    app.include_router(scan_stream_route.router)
    app.dependency_overrides[get_current_user] = lambda: User(id=1, email="leo@example.test")
    return TestClient(app)


@pytest.fixture
def read_trioxhydre(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Groq lit la Trioxhydre ex SR ; renvoie les appels faits au résolveur TCGdex."""
    resolver_calls: list[dict[str, Any]] = []

    def fake_resolve(**kwargs: Any) -> str | None:
        resolver_calls.append(kwargs)
        return "SV11W-163" if kwargs["ocr_set_code"] == "SV11W" else None

    monkeypatch.setattr(scan_stream_service, "extract_card_from_bytes", lambda data, filename, **_: _OCR_OF_TRIOXHYDRE_SR)
    monkeypatch.setattr(scan_stream_service, "resolve_tcgdex_card_id_from_ocr", fake_resolve)
    monkeypatch.setattr(
        scan_stream_service,
        "scanned_card_meta",
        lambda card_id, language: {"display_name": "Trioxhydre ex", "tcgdex_set_id": "SV11W"},
    )
    return resolver_calls


def _post_photo(client: TestClient, language: str = "ja") -> Any:
    return client.post(
        "/scan-stream/identify-photo",
        files={"file": ("carte.jpg", b"jpeg", "image/jpeg")},
        data={"language": language},
    )


def test_the_card_read_from_its_printed_code_comes_back_without_being_added(
    client: TestClient, read_trioxhydre: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(scan_stream_service, "submit_scan", lambda **_: pytest.fail("la carte ne doit pas être ajoutée"))

    response = _post_photo(client)

    assert response.status_code == 200
    assert response.json() == {
        "card": {
            "tcgdexCardId": "SV11W-163",
            "language": "ja",
            "name": "Trioxhydre ex",
            "setId": "SV11W",
            "localId": "163",
        }
    }
    assert read_trioxhydre[0]["ocr_card_number"] == "163/086"
    assert read_trioxhydre[0]["physical_language"] == "ja"


def test_a_text_that_matches_no_card_returns_no_card(
    client: TestClient, read_trioxhydre: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        scan_stream_service,
        "extract_card_from_bytes",
        lambda data, filename, **_: {**_OCR_OF_TRIOXHYDRE_SR, "set_code": None, "card_number": None},
    )

    response = _post_photo(client)

    assert response.status_code == 200
    assert response.json() == {"card": None}


def test_an_unavailable_reading_is_reported_to_the_phone(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def groq_down(data: bytes, filename: str, **_: Any) -> dict[str, Any]:
        raise RuntimeError("Groq 429 TPM")

    monkeypatch.setattr(scan_stream_service, "extract_card_from_bytes", groq_down)

    response = _post_photo(client)

    assert response.status_code == 502
    assert response.json()["detail"] == "Lecture de la carte indisponible."
