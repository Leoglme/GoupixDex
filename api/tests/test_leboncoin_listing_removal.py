import asyncio
import json
from typing import Any

import pytest

from app_types.leboncoin import LeboncoinListingRemovalOutcome
from services import desktop_leboncoin_runner_service as runner_module
from services.desktop_leboncoin_runner_service import DesktopLeboncoinRunnerService
from services.leboncoin_service import LeboncoinService

USER_ID = 1
REMOTE_BASE = "https://api.example.test"


def article_payload(article_id: int, **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": article_id,
        "user_id": USER_ID,
        "title": "Charbambin / Charcadet m2 083/080 AR",
        "description": "",
        "pokemon_name": "Charbambin",
        "set_code": "m2",
        "card_number": "083/080",
        "purchase_price": 1.0,
        "sell_price": 3.0,
        "published_on_leboncoin": True,
        "leboncoin_listing_id": "3278016312",
    }
    payload.update(overrides)
    return payload


class FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


class FakeAsyncClient:
    articles: dict[int, dict[str, Any]] = {}

    def __init__(self, **_options: object) -> None:
        pass

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None

    async def get(self, url: str, **_options: object) -> FakeResponse:
        return FakeResponse(self.articles[int(url.rsplit("/", 1)[-1])])


class FakeLeboncoin:
    def __init__(self, monkeypatch: pytest.MonkeyPatch, deletion_errors: dict[str, str] | None = None) -> None:
        self.browser_opened = 0
        self.browser_closed = 0
        self.deleted: list[tuple[str | None, str]] = []
        self.reports: list[tuple[str, dict[str, Any]]] = []
        errors = deletion_errors or {}

        async def init_browser() -> None:
            self.browser_opened += 1

        async def init_page(_url: str = "") -> None:
            return None

        def close_browser() -> None:
            self.browser_closed += 1

        async def delete_listing(listing_id: str | None, title: str) -> bool:
            if listing_id in errors:
                raise RuntimeError(errors[listing_id])
            self.deleted.append((listing_id, title))
            return True

        async def post_confirmation(url: str, _headers: dict[str, str], payload: dict[str, Any]) -> None:
            self.reports.append((url.removeprefix(REMOTE_BASE), payload))

        monkeypatch.setattr(LeboncoinService, "init_browser", init_browser)
        monkeypatch.setattr(LeboncoinService, "init_page", init_page)
        monkeypatch.setattr(LeboncoinService, "close_browser", close_browser)
        monkeypatch.setattr(LeboncoinService, "delete_listing", delete_listing)
        monkeypatch.setattr(runner_module, "post_confirmation_to_api", post_confirmation)
        monkeypatch.setattr(runner_module.httpx, "AsyncClient", FakeAsyncClient)


def run_removal(article_ids: list[int]) -> list[LeboncoinListingRemovalOutcome]:
    return asyncio.run(
        DesktopLeboncoinRunnerService.run_leboncoin_listings_removal(article_ids, USER_ID, "token", REMOTE_BASE)
    )


def test_removed_listing_is_confirmed_to_goupixdex(monkeypatch: pytest.MonkeyPatch) -> None:
    leboncoin = FakeLeboncoin(monkeypatch)
    FakeAsyncClient.articles = {80: article_payload(80)}

    run_removal([80])

    assert leboncoin.deleted == [("3278016312", "Charbambin / Charcadet m2 083/080 AR")]
    assert leboncoin.reports == [("/articles/80/confirm-leboncoin-unlist", {})]


def test_failed_removal_is_recorded_on_the_article_and_the_next_one_still_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    leboncoin = FakeLeboncoin(monkeypatch, {"111": "Leboncoin a refusé la suppression : erreur technique"})
    FakeAsyncClient.articles = {
        71: article_payload(71, leboncoin_listing_id="111"),
        80: article_payload(80, leboncoin_listing_id="222"),
    }

    outcomes = run_removal([71, 80])

    assert outcomes == [
        {"article_id": 71, "delisted": False, "detail": "Leboncoin a refusé la suppression : erreur technique"},
        {"article_id": 80, "delisted": True, "detail": None},
    ]
    assert leboncoin.reports == [
        (
            "/articles/71/fail-leboncoin-cross-removal",
            {"detail": "Leboncoin a refusé la suppression : erreur technique"},
        ),
        ("/articles/80/confirm-leboncoin-unlist", {}),
    ]
    assert (leboncoin.browser_opened, leboncoin.browser_closed) == (1, 1)


def test_article_without_leboncoin_listing_never_opens_chrome(monkeypatch: pytest.MonkeyPatch) -> None:
    leboncoin = FakeLeboncoin(monkeypatch)
    FakeAsyncClient.articles = {80: article_payload(80, published_on_leboncoin=False)}

    outcomes = run_removal([80])

    assert outcomes == [{"article_id": 80, "delisted": True, "detail": "Déjà retirée de Leboncoin."}]
    assert leboncoin.browser_opened == 0
    assert leboncoin.reports == []


class FakeMyAdsTab:
    def __init__(self, list_states: list[dict[str, int]], match_counts: list[int]) -> None:
        self.list_states = list_states
        self.match_counts = match_counts
        self.scroll_count = 0

    async def evaluate(self, expression: str, **_options: object) -> object:
        if "scrollTo" in expression:
            self.scroll_count += 1
            return True
        match_count = self.match_counts.pop(0)
        return json.dumps({"matchCount": match_count, "isMarked": match_count == 1})

    async def sleep(self, _seconds: float) -> None:
        return None


def fake_my_ads_list(monkeypatch: pytest.MonkeyPatch, tab: FakeMyAdsTab) -> None:
    async def wait_for_list(_tab: object) -> dict[str, int]:
        return tab.list_states.pop(0)

    monkeypatch.setattr(LeboncoinService, "_wait_for_my_ads_list", wait_for_list)


def test_listing_missing_from_a_fully_loaded_list_is_reported_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    tab = FakeMyAdsTab([{"shown": 12, "online": 12}], [0])
    fake_my_ads_list(monkeypatch, tab)

    is_found = asyncio.run(LeboncoinService._find_listing_delete_trigger(tab, "3278016312", "Titre"))  # type: ignore[arg-type]

    assert is_found is False
    assert tab.scroll_count == 0


def test_listing_is_searched_in_the_next_loaded_ads(monkeypatch: pytest.MonkeyPatch) -> None:
    tab = FakeMyAdsTab([{"shown": 30, "online": 45}, {"shown": 45, "online": 45}], [0, 1])
    fake_my_ads_list(monkeypatch, tab)

    is_found = asyncio.run(LeboncoinService._find_listing_delete_trigger(tab, "3278016312", "Titre"))  # type: ignore[arg-type]

    assert is_found is True
    assert tab.scroll_count == 1


def test_listing_is_never_reported_absent_when_the_list_stops_loading(monkeypatch: pytest.MonkeyPatch) -> None:
    tab = FakeMyAdsTab([{"shown": 30, "online": 45}, {"shown": 30, "online": 45}], [0, 0])
    fake_my_ads_list(monkeypatch, tab)

    with pytest.raises(RuntimeError, match="n’a pas chargé toutes vos annonces"):
        asyncio.run(LeboncoinService._find_listing_delete_trigger(tab, "3278016312", "Titre"))  # type: ignore[arg-type]


def test_unreadable_my_ads_page_is_never_reported_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    tab = FakeMyAdsTab([{"shown": 12, "online": 12}], [])

    async def javascript_error(_expression: str, **_options: object) -> object:
        return {"exception": "TypeError"}

    tab.evaluate = javascript_error  # type: ignore[method-assign]
    fake_my_ads_list(monkeypatch, tab)

    with pytest.raises(RuntimeError, match="Lecture de « Mes annonces » impossible"):
        asyncio.run(LeboncoinService._find_listing_delete_trigger(tab, "3278016312", "Titre"))  # type: ignore[arg-type]


def test_two_listings_with_the_same_title_are_never_deleted(monkeypatch: pytest.MonkeyPatch) -> None:
    tab = FakeMyAdsTab([{"shown": 12, "online": 12}], [2])
    fake_my_ads_list(monkeypatch, tab)

    with pytest.raises(RuntimeError, match="2 annonces Leboncoin portent ce titre"):
        asyncio.run(LeboncoinService._find_listing_delete_trigger(tab, None, "Titre"))  # type: ignore[arg-type]


class FakeDeleteDialogTab:
    def __init__(self, outcomes: list[str]) -> None:
        self.outcomes = outcomes

    async def evaluate(self, _expression: str, **_options: object) -> str:
        return self.outcomes.pop(0)

    async def sleep(self, _seconds: float) -> None:
        return None


def test_deletion_survey_means_leboncoin_accepted_the_deletion() -> None:
    tab = FakeDeleteDialogTab(['{"accepted": false, "error": ""}', '{"accepted": true}'])

    asyncio.run(LeboncoinService._wait_for_delete_outcome(tab))  # type: ignore[arg-type]

    assert tab.outcomes == []


def test_deletion_already_in_progress_counts_as_accepted() -> None:
    already_deleting = "Votre annonce est déjà en cours de suppression, cela ne devrait plus tarder."
    tab = FakeDeleteDialogTab([f'{{"accepted": false, "error": "{already_deleting}"}}'])

    asyncio.run(LeboncoinService._wait_for_delete_outcome(tab))  # type: ignore[arg-type]


def test_deletion_error_shown_by_leboncoin_is_raised() -> None:
    technical_error = "Une erreur technique est survenue, veuillez réessayer ultérieurement."
    tab = FakeDeleteDialogTab([f'{{"accepted": false, "error": "{technical_error}"}}'])

    with pytest.raises(RuntimeError, match="Leboncoin a refusé la suppression : Une erreur technique"):
        asyncio.run(LeboncoinService._wait_for_delete_outcome(tab))  # type: ignore[arg-type]


class FakeClockTab:
    def __init__(self) -> None:
        self.now = 0.0

    async def sleep(self, seconds: float) -> None:
        self.now += seconds


def fake_loading_my_ads(monkeypatch: pytest.MonkeyPatch, tab: FakeClockTab, loaded_after_sec: float) -> None:
    async def no_login_gate(_tab: object) -> bool:
        return False

    async def read_list_state(_tab: object) -> dict[str, int]:
        if tab.now < loaded_after_sec:
            return {"shown": 0, "online": 0}
        return {"shown": 12, "online": 12}

    monkeypatch.setattr(LeboncoinService, "_page_shows_login_gate", no_login_gate)
    monkeypatch.setattr(LeboncoinService, "_read_my_ads_list_state", read_list_state)
    monkeypatch.setattr("services.leboncoin_service.time.monotonic", lambda: tab.now)


def test_empty_list_shown_while_my_ads_loads_is_not_taken_as_final(monkeypatch: pytest.MonkeyPatch) -> None:
    tab = FakeClockTab()
    fake_loading_my_ads(monkeypatch, tab, loaded_after_sec=2.0)

    state = asyncio.run(LeboncoinService._wait_for_my_ads_list(tab))  # type: ignore[arg-type]

    assert state == {"shown": 12, "online": 12}


def test_truly_empty_my_ads_is_accepted_once_it_stays_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    tab = FakeClockTab()
    fake_loading_my_ads(monkeypatch, tab, loaded_after_sec=999.0)

    state = asyncio.run(LeboncoinService._wait_for_my_ads_list(tab))  # type: ignore[arg-type]

    assert state == {"shown": 0, "online": 0}
    assert tab.now >= 6.0


class FakeNavigationTab:
    async def get(self, _url: str) -> None:
        return None


def fake_listing_missing_from_my_ads(monkeypatch: pytest.MonkeyPatch, *, is_still_public: bool) -> None:
    async def no_cookie_banner(_tab: object, timeout_sec: float = 0.0) -> None:
        return None

    async def not_in_my_ads(_tab: object, _listing_id: str | None, _title: str) -> bool:
        return False

    async def public_page(_tab: object, _listing_id: str) -> bool:
        return is_still_public

    monkeypatch.setattr(LeboncoinService, "_tab", FakeNavigationTab())
    monkeypatch.setattr(LeboncoinService, "_accept_didomi_cookies", no_cookie_banner)
    monkeypatch.setattr(LeboncoinService, "_find_listing_delete_trigger", not_in_my_ads)
    monkeypatch.setattr(LeboncoinService, "_is_listing_still_public", public_page)


def test_listing_still_public_is_never_reported_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_listing_missing_from_my_ads(monkeypatch, is_still_public=True)

    with pytest.raises(RuntimeError, match="encore en ligne sur Leboncoin"):
        asyncio.run(LeboncoinService.delete_listing("3278016312", "Titre"))


def test_listing_gone_from_my_ads_and_from_leboncoin_is_reported_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_listing_missing_from_my_ads(monkeypatch, is_still_public=False)

    assert asyncio.run(LeboncoinService.delete_listing("3278016312", "Titre")) is False
