import asyncio
import json
from types import SimpleNamespace
from typing import Any, Self

import pytest

from services import (
    desktop_leboncoin_runner_service,
    leboncoin_publish_service,
    leboncoin_service,
)
from services.desktop_leboncoin_runner_service import DesktopLeboncoinRunnerService
from services.desktop_stubs_service import DesktopStubsService
from services.leboncoin_service import LeboncoinService

CHARCADET_LISTING_ID = "3278016312"
OTHER_COPY_LISTING_ID = "3278016001"


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now


class FakeMyAdsTab:
    """Onglet « Mes annonces » où l'annonce déposée apparaît après quelques relevés."""

    def __init__(self, clock: FakeClock, listing_ids_by_poll: list[list[str]]) -> None:
        self.clock = clock
        self.listing_ids_by_poll = listing_ids_by_poll
        self.opened_urls: list[str] = []

    async def get(self, url: str) -> "FakeMyAdsTab":
        self.opened_urls.append(url)
        return self

    async def sleep(self, seconds: float) -> None:
        self.clock.now += seconds

    async def evaluate(self, _script: str, **_options: object) -> Any:
        return json.dumps(self.listing_ids_by_poll.pop(0) if self.listing_ids_by_poll else [])


def use_my_ads_tab(
    monkeypatch: pytest.MonkeyPatch, listing_ids_by_poll: list[list[str]]
) -> FakeMyAdsTab:
    clock = FakeClock()
    tab = FakeMyAdsTab(clock, listing_ids_by_poll)
    monkeypatch.setattr(leboncoin_service.time, "monotonic", clock.monotonic)
    monkeypatch.setattr(LeboncoinService, "_tab", tab)
    return tab


def test_deposited_ad_is_found_once_leboncoin_lists_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tab = use_my_ads_tab(monkeypatch, [[]] * 10 + [[CHARCADET_LISTING_ID]])

    listing_id = asyncio.run(
        LeboncoinService.find_listing_id_in_my_ads(
            "Charbambin / Charcadet m2 083/080 AR",
            listing_ids_before_deposit=frozenset(),
        )
    )

    assert listing_id == CHARCADET_LISTING_ID
    assert tab.opened_urls == [
        leboncoin_service.MY_ADS_URL,
        leboncoin_service.MY_ADS_URL,
    ]


def test_other_copy_ad_already_listed_is_never_taken_for_the_deposited_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_my_ads_tab(
        monkeypatch,
        [[OTHER_COPY_LISTING_ID]] * 10 + [[OTHER_COPY_LISTING_ID, CHARCADET_LISTING_ID]],
    )

    listing_id = asyncio.run(
        LeboncoinService.find_listing_id_in_my_ads(
            "Charbambin / Charcadet m2 083/080 AR",
            listing_ids_before_deposit=frozenset({OTHER_COPY_LISTING_ID}),
        )
    )

    assert listing_id == CHARCADET_LISTING_ID


def test_ads_with_the_title_are_read_before_the_deposit(monkeypatch: pytest.MonkeyPatch) -> None:
    tab = use_my_ads_tab(monkeypatch, [[OTHER_COPY_LISTING_ID]])

    async def list_loaded(_tab: object) -> dict[str, int]:
        return {"shown": 1, "online": 1}

    monkeypatch.setattr(LeboncoinService, "_wait_for_my_ads_list", list_loaded)

    listing_ids = asyncio.run(LeboncoinService.read_listing_ids_with_title_in_my_ads("Charcadet"))

    assert listing_ids == frozenset({OTHER_COPY_LISTING_ID})
    assert tab.opened_urls == [leboncoin_service.MY_ADS_URL]


def test_unreadable_my_ads_before_the_deposit_gives_no_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    use_my_ads_tab(monkeypatch, [])

    async def session_expired(_tab: object) -> dict[str, int]:
        raise RuntimeError("Session Leboncoin expirée")

    monkeypatch.setattr(LeboncoinService, "_wait_for_my_ads_list", session_expired)

    assert asyncio.run(LeboncoinService.read_listing_ids_with_title_in_my_ads("Charcadet")) is None


def test_lookup_gives_up_when_the_ad_is_still_not_listed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_my_ads_tab(monkeypatch, [])

    assert (
        asyncio.run(
            LeboncoinService.find_listing_id_in_my_ads(
                "Charcadet", listing_ids_before_deposit=frozenset(), timeout_sec=20.0
            )
        )
        is None
    )


class FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self.payload


class FakeApiClient:
    def __init__(self, *_args: object, **_kwargs: object) -> None:
        return None

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None

    async def get(self, url: str, headers: dict[str, str]) -> FakeResponse:
        if url.endswith("/settings"):
            return FakeResponse(
                {
                    "sender_postal_code": "35230",
                    "sender_line1": "1 rue",
                    "sender_city": "Saint-Erblon",
                }
            )
        return FakeResponse({"user_id": 1, "images": []})


def record_confirmations(
    monkeypatch: pytest.MonkeyPatch,
    publication: dict[str, Any],
    *,
    is_deposit_signalled: bool,
) -> list[dict[str, Any]]:
    confirmations: list[dict[str, Any]] = []

    async def post_confirmation(
        _url: str, _headers: dict[str, str], payload: dict[str, Any]
    ) -> None:
        confirmations.append(payload)

    async def publish(
        *_args: object, on_deposited: Any, **_kwargs: object
    ) -> dict[str, Any]:
        if is_deposit_signalled:
            await on_deposited()
            confirmations.append({"looked_up": True})
        return publication

    monkeypatch.setattr(
        desktop_leboncoin_runner_service.httpx, "AsyncClient", FakeApiClient
    )
    monkeypatch.setattr(
        DesktopStubsService,
        "article_from_api_dict",
        staticmethod(lambda _article: SimpleNamespace(id=119)),
    )
    monkeypatch.setattr(
        desktop_leboncoin_runner_service, "post_confirmation_to_api", post_confirmation
    )
    monkeypatch.setattr(
        desktop_leboncoin_runner_service, "publish_article_to_leboncoin", publish
    )
    return confirmations


async def publish_charcadet() -> dict[str, Any]:
    async def ignore_progress(_event: dict[str, Any]) -> None:
        return None

    return await DesktopLeboncoinRunnerService._publish_article(
        119, 1, "token", "https://api.example.test", progress=ignore_progress
    )


def test_deposit_is_recorded_before_the_lookup_then_with_the_listing_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    confirmations = record_confirmations(
        monkeypatch,
        {"published": True, "listing_id": CHARCADET_LISTING_ID},
        is_deposit_signalled=True,
    )

    asyncio.run(publish_charcadet())

    assert confirmations == [
        {},
        {"looked_up": True},
        {"listing_id": CHARCADET_LISTING_ID},
    ]


def test_deposit_is_recorded_once_when_the_listing_link_is_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    confirmations = record_confirmations(
        monkeypatch, {"published": True, "listing_id": None}, is_deposit_signalled=True
    )

    asyncio.run(publish_charcadet())

    assert confirmations == [{}, {"looked_up": True}]


def test_listing_id_read_from_the_confirmation_url_is_recorded_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    confirmations = record_confirmations(
        monkeypatch,
        {"published": True, "listing_id": CHARCADET_LISTING_ID},
        is_deposit_signalled=False,
    )

    asyncio.run(publish_charcadet())

    assert confirmations == [{"listing_id": CHARCADET_LISTING_ID}]


def test_failed_lookup_keeps_the_ad_published(monkeypatch: pytest.MonkeyPatch) -> None:
    signalled_deposits: list[bool] = []

    async def signal_deposit() -> None:
        signalled_deposits.append(True)

    async def broken_lookup(_cls: type, _title: str, **_options: object) -> str | None:
        raise RuntimeError("CDP perdu")

    monkeypatch.setattr(
        LeboncoinService, "find_listing_id_in_my_ads", classmethod(broken_lookup)
    )

    listing_id = asyncio.run(
        leboncoin_publish_service._signal_deposit_and_find_listing_id(
            "Charcadet", None, signal_deposit, listing_ids_before_deposit=frozenset()
        )
    )

    assert listing_id is None
    assert signalled_deposits == [True]


def test_listing_link_is_not_searched_without_the_ads_read_before_the_deposit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    signalled_deposits: list[bool] = []
    lookups: list[str] = []

    async def signal_deposit() -> None:
        signalled_deposits.append(True)

    async def lookup(_cls: type, title: str, **_options: object) -> str | None:
        lookups.append(title)
        return OTHER_COPY_LISTING_ID

    monkeypatch.setattr(LeboncoinService, "find_listing_id_in_my_ads", classmethod(lookup))

    listing_id = asyncio.run(
        leboncoin_publish_service._signal_deposit_and_find_listing_id(
            "Charcadet", None, signal_deposit, listing_ids_before_deposit=None
        )
    )

    assert listing_id is None
    assert lookups == []
    assert signalled_deposits == [True]
