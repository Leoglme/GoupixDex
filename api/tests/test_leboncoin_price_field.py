import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from services.leboncoin_service import (
    LeboncoinService,
    format_leboncoin_price,
    parse_leboncoin_price,
)


class FakePriceTab:
    """Onglet dont le champ prix affiche une valeur, et que Leboncoin peut réécrire avec son prix suggéré."""

    def __init__(
        self, shown_price: str | None, *, keeps_suggested_price: bool = False
    ) -> None:
        self.shown_price = shown_price
        self.keeps_suggested_price = keeps_suggested_price
        self.typed_prices: list[str] = []

    async def evaluate(self, script: str, **_options: object) -> Any:
        if script.startswith("!!document.querySelector"):
            return self.shown_price is not None
        return self.shown_price

    async def sleep(self, _seconds: float) -> None:
        return None


def use_price_tab(monkeypatch: pytest.MonkeyPatch, tab: FakePriceTab) -> None:
    async def type_price(
        _cls: type, _tab: FakePriceTab, _selector: str, value: str
    ) -> bool:
        tab.typed_prices.append(value)
        if not tab.keeps_suggested_price:
            tab.shown_price = value
        return True

    monkeypatch.setattr(LeboncoinService, "_set_input_value", classmethod(type_price))


def test_price_is_typed_the_way_leboncoin_expects_it() -> None:
    assert format_leboncoin_price(3.0) == "3"
    assert format_leboncoin_price(2.5) == "2,50"


def test_shown_price_is_read_with_a_comma_or_a_currency_sign() -> None:
    assert parse_leboncoin_price("2,50") == 2.5
    assert parse_leboncoin_price("5 €") == 5.0
    assert parse_leboncoin_price("") is None


def test_suggested_price_is_replaced_by_the_article_price(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tab = FakePriceTab("5")
    use_price_tab(monkeypatch, tab)

    assert asyncio.run(LeboncoinService._fill_price(tab, 2.5)) is True
    assert tab.typed_prices == ["2,50"]


def test_price_that_does_not_hold_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    tab = FakePriceTab("5", keeps_suggested_price=True)
    use_price_tab(monkeypatch, tab)

    assert asyncio.run(LeboncoinService._fill_price(tab, 2.5)) is False
    assert len(tab.typed_prices) == 3


def test_page_without_price_field_is_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    tab = FakePriceTab(None)
    use_price_tab(monkeypatch, tab)

    assert asyncio.run(LeboncoinService._fill_price(tab, 2.5)) is None
    assert tab.typed_prices == []


def test_ad_is_not_deposited_when_the_price_could_not_be_typed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    submitted: list[bool] = []

    async def do_nothing(*_args: object, **_kwargs: object) -> None:
        return None

    async def continue_clicked(_cls: type, _tab: object) -> bool:
        return True

    async def late_steps_without_price(
        _cls: type, _tab: object, **_kwargs: object
    ) -> bool:
        return False

    async def no_price_field(_cls: type, _tab: object, _price_eur: float) -> None:
        return None

    async def submit(_cls: type, _progress: object = None) -> dict[str, Any]:
        submitted.append(True)
        return {"published": True}

    monkeypatch.setattr(LeboncoinService, "_tab", SimpleNamespace(sleep=do_nothing))
    monkeypatch.setattr(
        LeboncoinService, "_wizard_step_title_and_category", classmethod(do_nothing)
    )
    monkeypatch.setattr(LeboncoinService, "upload_photos", classmethod(do_nothing))
    monkeypatch.setattr(
        LeboncoinService, "_wizard_fill_structured_attributes", classmethod(do_nothing)
    )
    monkeypatch.setattr(
        LeboncoinService, "_click_continue", classmethod(continue_clicked)
    )
    monkeypatch.setattr(
        LeboncoinService,
        "_wizard_fill_late_steps",
        classmethod(late_steps_without_price),
    )
    monkeypatch.setattr(LeboncoinService, "_fill_price", classmethod(no_price_field))
    monkeypatch.setattr(LeboncoinService, "submit_and_wait", classmethod(submit))

    with pytest.raises(RuntimeError, match="2,50 € n'a pas pu être saisi"):
        asyncio.run(
            LeboncoinService.run_deposit_wizard(
                title="Charcadet",
                description="Carte",
                price_eur=2.5,
                postal_code="35230",
                address_line1="1 rue",
                city="Saint-Erblon",
                photo_basenames=[],
                listing_fields=SimpleNamespace(),
            )
        )
    assert submitted == []
