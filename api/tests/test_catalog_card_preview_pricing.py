import pytest

from services import catalog_prefill_service, cardmarket_local_price_service, price_history_seed_service

CARDMARKET_BLOCK = {
    "idProduct": 907949,
    "avg": 17.48,
    "low": 4.4,
    "trend": 13.73,
    "avg1": 11.66,
    "avg7": 13.73,
    "avg30": 13.73,
}


class _GuideWithoutProduct:
    def get_card_prices(self, _id_product: int) -> None:
        return None


@pytest.fixture(autouse=True)
def _guide_without_product(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cardmarket_local_price_service, "get_price_api", _GuideWithoutProduct)
    monkeypatch.setattr(price_history_seed_service, "get_price_api", _GuideWithoutProduct)


def test_known_prices_read_the_tcgdex_block_without_searching() -> None:
    prices = catalog_prefill_service._known_prices(CARDMARKET_BLOCK, None)

    assert prices is not None
    assert prices["cardmarket_id_product"] == 907949
    assert prices["cardmarket_eur"] == pytest.approx(13.73)


def test_known_prices_are_unknown_without_block_nor_tcgplayer_price() -> None:
    assert catalog_prefill_service._known_prices(None, None) is None


def test_seed_falls_back_to_the_tcgdex_block_when_the_guide_lacks_the_product() -> None:
    points = price_history_seed_service.synthesized_price_points(907949, CARDMARKET_BLOCK)

    assert [point["price_eur"] for point in points] == [13.73, 13.73, 11.66, 13.73]


def test_seed_is_empty_without_guide_nor_block() -> None:
    assert price_history_seed_service.synthesized_price_points(907949) == []
