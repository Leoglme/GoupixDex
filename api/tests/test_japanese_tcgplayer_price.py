from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from services import card_image_fallback_service as fallback
from services import pricing_service

INFERNO_X_GROUP = (85, 24459)


def use_inferno_x_export(monkeypatch: pytest.MonkeyPatch) -> None:
    exports: dict[str, list[dict[str, Any]]] = {
        "85/24459/products": [
            {
                "productId": 655861,
                "name": "Charcadet - 083/080 (Master Ball)",
                "extendedData": [{"name": "Number", "value": "083/080"}],
            },
            {
                "productId": 655862,
                "name": "Charcadet - 083/080",
                "extendedData": [{"name": "Number", "value": "083/080"}],
            },
            {
                "productId": 655900,
                "name": "Armarouge - 084/080",
                "extendedData": [{"name": "Number", "value": "084/080"}],
            },
        ],
        "85/24459/prices": [
            {
                "productId": 655861,
                "marketPrice": 9.5,
                "midPrice": 10.0,
                "lowPrice": 8.0,
                "subTypeName": "Holofoil",
            },
            {
                "productId": 655862,
                "marketPrice": 1.67,
                "midPrice": 1.93,
                "lowPrice": 1.0,
                "subTypeName": "Holofoil",
            },
            {
                "productId": 655900,
                "marketPrice": 3.2,
                "midPrice": 3.5,
                "lowPrice": 2.9,
                "subTypeName": "Holofoil",
            },
        ],
    }
    monkeypatch.setattr(
        fallback, "_tcgplayer_group", lambda _locale, _set_id: INFERNO_X_GROUP
    )
    monkeypatch.setattr(fallback, "_tcgplayer_json", lambda path: exports.get(path, []))


def price_japanese_card(
    monkeypatch: pytest.MonkeyPatch, language: str
) -> dict[str, Any] | None:
    def pokewallet_is_not_called(*_args: object) -> float | None:
        raise AssertionError("PokéWallet ne doit pas être appelé")

    monkeypatch.setattr(
        pricing_service,
        "fetch_tcgdex_pricing_snapshot",
        lambda _card_id, _language: ({"idProduct": 850001}, None),
    )
    monkeypatch.setattr(
        pricing_service, "resolve_market_price_eur", lambda _id_product, _block: 2.06
    )
    monkeypatch.setattr(
        pricing_service,
        "_pokewallet_tcgplayer_usd_only",
        pokewallet_is_not_called if language == "ja" else lambda *_args: None,
    )
    return pricing_service._fetch_prices_via_cardmarket_local(
        "M2", "083", "Charcadet", tcgdex_card_id="M2-083", language=language
    )


def test_japanese_card_prices_come_from_its_normal_print(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_inferno_x_export(monkeypatch)

    rows = fallback.tcgplayer_japanese_card_prices("M2", "083")

    assert [row["productId"] for row in rows] == [655862]


def test_card_missing_from_tcgplayer_has_no_prices(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_inferno_x_export(monkeypatch)

    assert fallback.tcgplayer_japanese_card_prices("M2", "099") == []


def test_japanese_card_gets_its_tcgplayer_price_from_tcgcsv(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_inferno_x_export(monkeypatch)

    prices = price_japanese_card(monkeypatch, "ja")

    assert prices is not None
    assert prices["tcgplayer_usd"] == 1.67
    assert prices["cardmarket_eur"] == 2.06


def test_card_of_another_language_is_not_priced_from_the_japanese_export(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_inferno_x_export(monkeypatch)

    prices = price_japanese_card(monkeypatch, "en")

    assert prices is not None
    assert prices["tcgplayer_usd"] is None


class FakeTcgcsvResponse:
    status_code = 200

    def __init__(self, results: list[dict[str, Any]]) -> None:
        self.results = results

    def json(self) -> dict[str, Any]:
        return {"results": self.results}


def test_export_that_did_not_answer_is_fetched_again_a_few_minutes_later(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = SimpleNamespace(now=1000.0)
    answers: list[Exception | FakeTcgcsvResponse] = [
        httpx.ConnectError("TCGCSV injoignable"),
        FakeTcgcsvResponse([{"productId": 655862, "marketPrice": 1.67}]),
    ]

    def get(_url: str, timeout: float) -> FakeTcgcsvResponse:
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(fallback, "time", SimpleNamespace(monotonic=lambda: clock.now))
    monkeypatch.setattr(fallback, "_cache", fallback._TtlCache())
    monkeypatch.setattr(fallback._http, "get", get)

    assert fallback._tcgplayer_json("85/24459/prices") == []
    clock.now += 301.0
    assert fallback._tcgplayer_json("85/24459/prices") == [
        {"productId": 655862, "marketPrice": 1.67}
    ]
