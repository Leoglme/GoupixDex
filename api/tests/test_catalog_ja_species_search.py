"""Recherche du catalogue japonais par nom latin : TCGdex n'a que des noms japonais, la recherche passe par le n° Pokédex."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from services import catalog_browse_service as service
from services.card_image_fallback_service import CardImageUrls


class _FakeTcgdex:
    """Sulfura (n° 146) dans le set français xy10, et deux cartes japonaises : M6a-105 sans scan, SV2a-146 illustrée."""

    _base = "https://api.tcgdex.net/v2"

    def get_card(self, locale: str, card_id: str) -> dict[str, Any]:
        return {"id": card_id, "dexId": [146]}

    def get_set(self, locale: str, set_id: str) -> dict[str, Any]:
        return {"id": set_id, "cards": []}


@pytest.fixture
def card_requests(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[tuple[str, dict[str, str]]]]:
    """TCGdex, PokéAPI et scans de repli simulés ; renvoie les recherches de cartes envoyées à TCGdex."""
    requests: list[tuple[str, dict[str, str]]] = []

    def fake_card_rows(locale: str, params: dict[str, str]) -> list[dict[str, Any]]:
        requests.append((locale, params))
        if locale == "fr":
            return [{"id": "xy10-9", "localId": "9", "name": "Sulfura"}]
        if locale == "ja":
            return [
                {"id": "M6a-105", "localId": "105", "name": "ファイヤー"},
                {"id": "SV2a-146", "localId": "146", "name": "ファイヤー", "image": "https://assets.tcgdex.net/ja/SV/SV2a/146"},
            ]
        return []

    monkeypatch.setattr(service, "_tcgdex_card_rows", fake_card_rows)
    monkeypatch.setattr(service, "_client", _FakeTcgdex)
    monkeypatch.setattr(service, "fetch_species_names_by_dex", lambda dex: ("Sulfura", "Moltres", "ファイヤー"))
    monkeypatch.setattr(
        service,
        "fallback_card_images",
        lambda locale, detail: (
            {"105": CardImageUrls(low="https://cdn.example/M6a-105.jpg", high="https://cdn.example/M6a-105-hd.jpg")}
            if detail["id"] == "M6a"
            else {}
        ),
    )
    monkeypatch.setattr(service, "list_sets_for_ui", lambda *args, **kwargs: [])
    monkeypatch.setattr(service, "latin_display_name_for_ja_set", lambda set_id: None)
    service._cache._store.clear()
    yield requests
    service._cache._store.clear()


def test_a_french_name_searched_in_japanese_finds_the_cards_of_its_species(
    card_requests: list[tuple[str, dict[str, str]]],
) -> None:
    cards = service.search_cards_for_ui("ja", "Sulfura")

    assert [(card["id"], card["display_name"]) for card in cards] == [("M6a-105", "Sulfura"), ("SV2a-146", "Sulfura")]
    assert cards[0]["image_low"] == "https://cdn.example/M6a-105.jpg"
    assert ("ja", {"dexId": "146", "pagination:page": "1", "pagination:itemsPerPage": "60"}) in card_requests


def test_a_number_after_the_name_narrows_the_japanese_cards(card_requests: list[tuple[str, dict[str, str]]]) -> None:
    service.search_cards_for_ui("ja", "Sulfura 105")

    japanese_request = next(params for locale, params in card_requests if locale == "ja")
    assert japanese_request["localId"] == "like:105"


def test_a_japanese_name_is_searched_as_typed(card_requests: list[tuple[str, dict[str, str]]]) -> None:
    service.search_cards_for_ui("ja", "ファイヤー")

    assert card_requests[0] == ("ja", {"pagination:page": "1", "pagination:itemsPerPage": "40", "name": "like:ファイヤー"})
