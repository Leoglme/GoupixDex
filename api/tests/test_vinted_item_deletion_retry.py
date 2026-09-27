import asyncio

import pytest

from services.vinted_service import VintedService

ITEM_ID = 8737862700
ITEM_PAGE_URL = f"https://www.vinted.fr/items/{ITEM_ID}"


class FakeTab:
    def __init__(self) -> None:
        self.opened_urls: list[str] = []

    async def get(self, url: str) -> None:
        self.opened_urls.append(url)

    async def evaluate(self, _expression: str, **_options: object) -> str:
        return "https://www.vinted.fr/member/198987080"


def fake_item_page(monkeypatch: pytest.MonkeyPatch, confirmation_selectors: list[str | None]) -> None:
    async def open_confirmation(_tab: object, _item_id: int) -> str | None:
        return confirmation_selectors.pop(0)

    async def click(_tab: object, _selector: str) -> bool:
        return True

    async def listing_left_wardrobe(_tab: object, _member_id: int, _item_id: int) -> None:
        return None

    async def skip_pause(_seconds: float) -> None:
        return None

    monkeypatch.setattr(VintedService, "_open_item_delete_confirmation", open_confirmation)
    monkeypatch.setattr(VintedService, "_click_in_page", click)
    monkeypatch.setattr(VintedService, "_ensure_listing_left_wardrobe", listing_left_wardrobe)
    monkeypatch.setattr("services.vinted_service.asyncio.sleep", skip_pause)


def test_item_page_that_ignored_every_click_is_reloaded_once(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_item_page(monkeypatch, [None, '[data-testid="item-delete-confirmation-button"]'])
    tab = FakeTab()

    asyncio.run(VintedService.delete_vinted_item_listing(tab, ITEM_ID))

    assert tab.opened_urls == [ITEM_PAGE_URL, ITEM_PAGE_URL]


def test_deletion_confirmed_on_the_first_load_does_not_reload(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_item_page(monkeypatch, ['[data-testid="item-delete-confirmation-button"]'])
    tab = FakeTab()

    asyncio.run(VintedService.delete_vinted_item_listing(tab, ITEM_ID))

    assert tab.opened_urls == [ITEM_PAGE_URL]


def test_deletion_fails_when_the_dialog_never_opens(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_item_page(monkeypatch, [None, None])
    tab = FakeTab()

    with pytest.raises(RuntimeError, match="Confirmation de suppression introuvable"):
        asyncio.run(VintedService.delete_vinted_item_listing(tab, ITEM_ID))
    assert tab.opened_urls == [ITEM_PAGE_URL, ITEM_PAGE_URL]
