"""Publication Vinted : une annonce créée sans confirmation est retrouvée sur le dressing, jamais publiée deux fois."""

from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any

import pytest

from models.article import Article
from models.user import User
from services import vinted_publish_service
from services.vinted_progress_session_service import VintedProgressSessionService
from services.vinted_service import VintedPublishNotConfirmedError, VintedService

TITLE = "Monaflèmit ex / Slaking ex mc 583 - Starter Decks 100 Battle Collection - Pokémon Français"
LISTING_ID = 10612624528


def _wardrobe_row(item_id: int, title: str = TITLE, price: str = "1.5") -> dict[str, Any]:
    return {"id": item_id, "title": title, "price": price, "is_closed": False, "is_draft": False}


class FakeVintedSellPage:
    """Dressing et formulaire Vinted simulés : le dressing change une fois « Ajouter » cliqué."""

    def __init__(
        self,
        monkeypatch: pytest.MonkeyPatch,
        *,
        wardrobe_before_publish: list[dict[str, Any]],
        wardrobe_after_publish: list[dict[str, Any]],
        is_publish_confirmed: bool,
        vinted_messages: list[str] | None = None,
    ) -> None:
        self.is_sell_page_opened = False
        self.is_publish_clicked = False

        async def member_id() -> int:
            return 198987080

        async def wardrobe_rows(_tab: object, _member_id: int) -> list[dict[str, Any]]:
            return wardrobe_after_publish if self.is_publish_clicked else wardrobe_before_publish

        async def open_sell_page() -> None:
            self.is_sell_page_opened = True

        async def fill_form(*_args: Any, **_kwargs: Any) -> None:
            return None

        async def click_publish(**_kwargs: Any) -> None:
            self.is_publish_clicked = True
            if not is_publish_confirmed:
                raise VintedPublishNotConfirmedError(vinted_messages or [])

        async def ready_images(*_args: Any) -> list[str]:
            return ["listing_121.jpg"]

        async def no_wait(_milliseconds: int) -> None:
            return None

        monkeypatch.setattr(VintedService, "_require_tab", lambda: object())
        monkeypatch.setattr(VintedService, "fetch_logged_in_vinted_user_numeric_id", member_id)
        monkeypatch.setattr(VintedService, "_fetch_member_wardrobe_rows", wardrobe_rows)
        monkeypatch.setattr(VintedService, "open_sell_item_page", open_sell_page)
        monkeypatch.setattr(VintedService, "fill_item_details", fill_form)
        monkeypatch.setattr(VintedService, "publish", click_publish)
        monkeypatch.setattr(vinted_publish_service, "_materialize_listing_images", ready_images)
        monkeypatch.setattr(vinted_publish_service.TimerService, "wait", no_wait)


def list_on_vinted(
    *, other_articles_listing_ids: frozenset[int] = frozenset(), may_reuse_wardrobe_listing: bool = True
) -> dict[str, Any]:
    article = Article(
        id=121,
        user_id=1,
        title=TITLE,
        description="Carte japonaise.",
        purchase_price=Decimal("0.10"),
        sell_price=Decimal("1.50"),
    )
    return asyncio.run(
        vinted_publish_service.run_single_vinted_listing(
            article,
            User(id=1, email="leo@example.test"),
            ["https://example.test/front.jpg"],
            None,
            other_articles_listing_ids=other_articles_listing_ids,
            may_reuse_wardrobe_listing=may_reuse_wardrobe_listing,
        )
    )


def test_a_listing_already_on_the_wardrobe_is_not_listed_twice(monkeypatch: pytest.MonkeyPatch) -> None:
    vinted = FakeVintedSellPage(
        monkeypatch,
        wardrobe_before_publish=[_wardrobe_row(LISTING_ID)],
        wardrobe_after_publish=[],
        is_publish_confirmed=True,
    )

    listing = list_on_vinted()

    assert listing["published"] is True
    assert listing["detail"] == "already_listed"
    assert listing["vinted_id"] == LISTING_ID
    assert vinted.is_sell_page_opened is False


def test_the_listing_of_another_article_is_never_taken_over(monkeypatch: pytest.MonkeyPatch) -> None:
    vinted = FakeVintedSellPage(
        monkeypatch,
        wardrobe_before_publish=[_wardrobe_row(555)],
        wardrobe_after_publish=[_wardrobe_row(LISTING_ID), _wardrobe_row(555)],
        is_publish_confirmed=True,
    )

    listing = list_on_vinted(other_articles_listing_ids=frozenset({555}))

    assert vinted.is_publish_clicked is True
    assert listing["vinted_id"] == LISTING_ID


def test_another_copy_listed_without_id_disables_the_wardrobe_shortcut(monkeypatch: pytest.MonkeyPatch) -> None:
    vinted = FakeVintedSellPage(
        monkeypatch,
        wardrobe_before_publish=[_wardrobe_row(555)],
        wardrobe_after_publish=[_wardrobe_row(LISTING_ID), _wardrobe_row(555)],
        is_publish_confirmed=True,
    )

    list_on_vinted(may_reuse_wardrobe_listing=False)

    assert vinted.is_publish_clicked is True


def test_an_unconfirmed_publish_found_on_the_wardrobe_counts_as_published(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeVintedSellPage(
        monkeypatch,
        wardrobe_before_publish=[],
        wardrobe_after_publish=[_wardrobe_row(LISTING_ID)],
        is_publish_confirmed=False,
    )

    listing = list_on_vinted()

    assert listing["published"] is True
    assert listing["vinted_id"] == LISTING_ID


def test_an_unconfirmed_publish_missing_from_the_wardrobe_fails_with_the_message_vinted_showed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeVintedSellPage(
        monkeypatch,
        wardrobe_before_publish=[],
        wardrobe_after_publish=[],
        is_publish_confirmed=False,
        vinted_messages=["Le prix doit être d’au moins 1,00 €"],
    )

    with pytest.raises(VintedPublishNotConfirmedError, match="Le prix doit être d’au moins 1,00 €"):
        list_on_vinted()


class FakeVintedTab:
    """Onglet nodriver dont ``target.url`` reste figée sur le formulaire alors que la page a changé d'adresse."""

    def __init__(self, url_after_publish: str) -> None:
        self.target = type("Target", (), {"url": "https://www.vinted.fr/items/new"})()
        self.page_url = "https://www.vinted.fr/items/new"
        self.url_after_publish = url_after_publish

    async def select(self, _selector: str, timeout: int = 0) -> Any:
        tab = self

        class UploadButton:
            async def click(self) -> None:
                tab.page_url = tab.url_after_publish

        return UploadButton()

    async def evaluate(self, script: str, **_kwargs: Any) -> Any:
        return self.page_url if script == "location.href" else None


@pytest.mark.parametrize(
    "url_after_publish",
    [
        "https://www.vinted.fr/items/10612624528-monaflemit-ex-slaking-ex-mc-583",
        "https://www.vinted.fr/member/198987080",
    ],
)
def test_publish_is_confirmed_by_the_page_address_read_in_the_page(
    monkeypatch: pytest.MonkeyPatch, url_after_publish: str
) -> None:
    async def no_scroll(_selector: str) -> None:
        return None

    async def no_screenshot(_tab: object) -> None:
        return None

    monkeypatch.setattr(VintedService, "_require_tab", lambda: FakeVintedTab(url_after_publish))
    monkeypatch.setattr(VintedService, "_scroll_selector_into_view", no_scroll)
    monkeypatch.setattr(VintedService, "_tab_screenshot_data_url", no_screenshot)

    asyncio.run(VintedService.publish())


@pytest.fixture
def progress_sessions(monkeypatch: pytest.MonkeyPatch) -> None:
    """Registre des sessions de publication vidé pour chaque test."""
    monkeypatch.setattr(VintedProgressSessionService, "_sessions", {})


@pytest.mark.usefixtures("progress_sessions")
def test_a_retry_after_a_finished_publish_does_not_replay_the_old_result() -> None:
    async def retry_after_failure() -> list[dict[str, Any]]:
        VintedProgressSessionService.register(121)
        await VintedProgressSessionService.finish(121, {"vinted": {"published": False}})
        VintedProgressSessionService.register(121)
        await VintedProgressSessionService.emit(121, {"type": "log", "message": "Opening the sell page…"})
        await VintedProgressSessionService.finish(121, {"vinted": {"published": True}})
        return [event async for event in VintedProgressSessionService.event_stream(121)]

    events = asyncio.run(retry_after_failure())

    assert events == [
        {"type": "log", "message": "Opening the sell page…"},
        {"type": "done", "vinted": {"published": True}},
    ]


@pytest.mark.usefixtures("progress_sessions")
def test_a_running_publish_keeps_its_session_for_the_second_marketplace() -> None:
    VintedProgressSessionService.register(121)
    running_session = VintedProgressSessionService.get_session(121)

    VintedProgressSessionService.register(121)

    assert VintedProgressSessionService.get_session(121) is running_session


@pytest.mark.usefixtures("progress_sessions")
def test_cleaning_up_the_old_attempt_keeps_the_retry_session() -> None:
    async def retry_then_cleanup() -> bool:
        VintedProgressSessionService.register(121)
        await VintedProgressSessionService.finish(121, {"vinted": {"published": False}})
        VintedProgressSessionService.cleanup_later(121, delay_sec=0.0)
        VintedProgressSessionService.register(121)
        retry_session = VintedProgressSessionService.get_session(121)
        await asyncio.sleep(0.01)
        return VintedProgressSessionService.get_session(121) is retry_session

    assert asyncio.run(retry_then_cleanup()) is True
