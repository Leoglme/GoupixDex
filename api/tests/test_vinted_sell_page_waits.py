import asyncio
from typing import Any

import pytest

from services import vinted_service
from services.vinted_service import VintedService


class FakePhotoInput:
    def __init__(self) -> None:
        self.sent_files: list[str] = []

    async def send_file(self, *paths: str) -> None:
        self.sent_files.extend(paths)


class FakeSellTab:
    def __init__(self, evaluate_results: list[Any]) -> None:
        self.evaluate_results = evaluate_results
        self.evaluated_scripts: list[str] = []
        self.photo_input = FakePhotoInput()
        self.queried_selectors: list[str] = []

    async def select(self, _selector: str, timeout: float = 0.0) -> FakePhotoInput:
        return self.photo_input

    async def evaluate(self, script: str, **_options: object) -> Any:
        self.evaluated_scripts.append(script)
        return self.evaluate_results.pop(0) if self.evaluate_results else 0

    async def query_selector(self, selector: str) -> None:
        self.queried_selectors.append(selector)
        return None


def use_tab(monkeypatch: pytest.MonkeyPatch, tab: FakeSellTab) -> None:
    async def skip_pause(_seconds: float) -> None:
        return None

    monkeypatch.setattr(VintedService, "_require_tab", lambda: tab)
    monkeypatch.setattr(vinted_service.asyncio, "sleep", skip_pause)


def test_photo_upload_is_confirmed_as_soon_as_every_photo_is_counted(monkeypatch: pytest.MonkeyPatch) -> None:
    tab = FakeSellTab([0, 1, 2])
    use_tab(monkeypatch, tab)

    asyncio.run(VintedService.add_photos_to_item(["front.jpeg", "back.jpeg"]))

    assert len(tab.photo_input.sent_files) == 2
    assert len(tab.evaluated_scripts) == 3


def test_unconfirmed_photo_upload_gives_up_after_ten_seconds(monkeypatch: pytest.MonkeyPatch) -> None:
    tab = FakeSellTab([])
    use_tab(monkeypatch, tab)

    with pytest.raises(RuntimeError, match="Timeout waiting for photo thumbnails"):
        asyncio.run(VintedService.add_photos_to_item(["front.jpeg"]))
    assert len(tab.evaluated_scripts) == 40


def test_cookie_banner_is_not_awaited_once_consent_is_stored() -> None:
    tab = FakeSellTab([True])

    asyncio.run(VintedService._accept_onetrust_cookies(tab, total_timeout_sec=15.0))

    assert tab.queried_selectors == []
