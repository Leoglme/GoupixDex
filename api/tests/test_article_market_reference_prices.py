from types import SimpleNamespace
from typing import Any

import pytest

from services import article_market_reference_service as service

ARTICLE: Any = SimpleNamespace(id=71, set_code="ASC", card_number="253/217", pokemon_name="Mega Audino ex")
NO_DB_SESSION: Any = None


def _capture_price_calls(monkeypatch: pytest.MonkeyPatch, linked_card: SimpleNamespace | None) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    def fake_fetch_card_prices(*args: Any, **kwargs: Any) -> dict[str, Any]:
        calls.append({"args": args, "kwargs": kwargs})
        return {"cardmarket_eur": 4.0}

    monkeypatch.setattr(service, "linked_collection_card", lambda db, article: linked_card)
    monkeypatch.setattr(service, "fetch_card_prices", fake_fetch_card_prices)
    return calls


def test_resolved_linked_card_identifies_the_card(monkeypatch: pytest.MonkeyPatch) -> None:
    card = SimpleNamespace(tcgdex_card_id="me01-253", language="fr", card_number="253")
    calls = _capture_price_calls(monkeypatch, card)
    assert service.fetch_article_card_prices(NO_DB_SESSION, ARTICLE) == {"cardmarket_eur": 4.0}
    assert calls[0]["kwargs"] == {"tcgdex_card_id": "me01-253", "language": "fr"}


def test_unresolved_linked_card_falls_back_to_set_and_number(monkeypatch: pytest.MonkeyPatch) -> None:
    card = SimpleNamespace(tcgdex_card_id="manual-article-71", language="fr", card_number="253")
    calls = _capture_price_calls(monkeypatch, card)
    service.fetch_article_card_prices(NO_DB_SESSION, ARTICLE)
    assert calls[0]["kwargs"] == {}
    assert calls[0]["args"] == ("ASC", "253/217", "Mega Audino ex")


def test_linked_card_with_another_number_is_not_trusted(monkeypatch: pytest.MonkeyPatch) -> None:
    card = SimpleNamespace(tcgdex_card_id="me01-199", language="fr", card_number="199")
    calls = _capture_price_calls(monkeypatch, card)
    service.fetch_article_card_prices(NO_DB_SESSION, ARTICLE)
    assert calls[0]["kwargs"] == {}


def test_article_without_linked_card_uses_set_and_number(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _capture_price_calls(monkeypatch, None)
    service.fetch_article_card_prices(NO_DB_SESSION, ARTICLE)
    assert calls[0]["kwargs"] == {}


@pytest.mark.parametrize(
    ("printed", "expected"),
    [("071/063", "71"), ("253", "253"), ("SV001", "sv001"), ("0", "0"), (None, "")],
)
def test_printed_card_number_ignores_denominator_and_leading_zeros(printed: str | None, expected: str) -> None:
    assert service._printed_card_number(printed) == expected
