"""Retrait par le PC de l'annonce Vinted d'un article vendu ailleurs, sans jamais toucher celle d'un autre exemplaire."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from services import desktop_vinted_runner_service as runner_module
from services.desktop_vinted_runner_service import DesktopVintedRunnerService
from services.vinted_service import VintedService

USER_ID = 1
REMOTE_BASE = "https://api.example.test"
TITLE = "Piafabec / Spearow m1l 074/063 AR - Mega Brave - Pokémon Japonais"
SOLD_COPY_ID = 89
OTHER_COPY_ID = 75
SOLD_COPY_LISTING_ID = 10571219638
OTHER_COPY_LISTING_ID = 10571213032


def article_payload(article_id: int, **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": article_id,
        "user_id": USER_ID,
        "title": TITLE,
        "description": "",
        "purchase_price": 1.0,
        "sell_price": 2.5,
        "is_sold": False,
        "sale_source": None,
        "published_on_vinted": True,
        "vinted_id": None,
        "pending_vinted_unlist": False,
    }
    payload.update(overrides)
    return payload


def sold_on_ebay(article_id: int, **overrides: Any) -> dict[str, Any]:
    return article_payload(article_id, is_sold=True, sale_source="ebay", pending_vinted_unlist=True, **overrides)


class FakeResponse:
    def __init__(self, payload: Any) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> Any:
        return self._payload


class FakeApiClient:
    articles: dict[int, dict[str, Any]] = {}
    requested_paths: list[str] = []

    def __init__(self, **_options: object) -> None:
        pass

    async def __aenter__(self) -> "FakeApiClient":
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None

    async def get(self, url: str, **_options: object) -> FakeResponse:
        path = url.removeprefix(REMOTE_BASE)
        self.requested_paths.append(path)
        if path == "/articles":
            return FakeResponse(list(self.articles.values()))
        if path == "/users/me/vinted-decrypted":
            return FakeResponse({"vinted_email": "leo@example.test", "vinted_password": "secret"})
        if path == "/users/me":
            return FakeResponse({"id": USER_ID, "email": "leo@example.test"})
        return FakeResponse(self.articles[int(path.rsplit("/", 1)[-1])])


class FakeVinted:
    def __init__(self, monkeypatch: pytest.MonkeyPatch, articles: list[dict[str, Any]], live_listing_id: int | None):
        self.browser_opened = 0
        self.lookups: list[dict[str, Any]] = []
        self.deleted: list[int] = []
        self.reports: list[tuple[str, dict[str, Any]]] = []
        FakeApiClient.articles = {article["id"]: article for article in articles}
        FakeApiClient.requested_paths = []

        async def ensure_browser_session() -> bool:
            self.browser_opened += 1
            return True

        async def ensure_sign_in(_email: str, _password: str, **_options: object) -> None:
            return None

        async def find_live_member_listing(_tab: object, **criteria: Any) -> int | None:
            self.lookups.append(criteria)
            return live_listing_id

        async def delete_listing(_tab: object, item_id: int) -> None:
            self.deleted.append(item_id)

        async def shutdown_browser() -> None:
            return None

        async def post_confirmation(url: str, _headers: dict[str, str], payload: dict[str, Any]) -> None:
            self.reports.append((url.removeprefix(REMOTE_BASE), payload))

        monkeypatch.setattr(VintedService, "ensure_browser_session", ensure_browser_session)
        monkeypatch.setattr(VintedService, "ensure_sign_in", ensure_sign_in)
        monkeypatch.setattr(VintedService, "_require_tab", lambda: object())
        monkeypatch.setattr(VintedService, "find_live_member_listing", find_live_member_listing)
        monkeypatch.setattr(VintedService, "delete_vinted_item_listing", delete_listing)
        monkeypatch.setattr(VintedService, "shutdown_browser", shutdown_browser)
        monkeypatch.setattr(runner_module, "post_confirmation_to_api", post_confirmation)
        monkeypatch.setattr(runner_module.httpx, "AsyncClient", FakeApiClient)


def remove_after_ebay_sale(article_id: int) -> None:
    asyncio.run(
        DesktopVintedRunnerService.run_vinted_unlist_after_ebay_sale(article_id, USER_ID, "token", REMOTE_BASE)
    )


def test_listing_with_its_vinted_id_is_deleted_without_reading_the_other_articles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vinted = FakeVinted(
        monkeypatch, [sold_on_ebay(SOLD_COPY_ID, vinted_id=SOLD_COPY_LISTING_ID)], live_listing_id=SOLD_COPY_LISTING_ID
    )

    remove_after_ebay_sale(SOLD_COPY_ID)

    assert vinted.lookups[0]["vinted_id"] == SOLD_COPY_LISTING_ID
    assert vinted.deleted == [SOLD_COPY_LISTING_ID]
    assert vinted.reports == [
        (f"/articles/{SOLD_COPY_ID}/confirm-vinted-unlist", {"hide_when_off_all_platforms": True})
    ]
    assert "/articles" not in FakeApiClient.requested_paths


def test_listing_without_vinted_id_is_searched_without_the_other_copy_listing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vinted = FakeVinted(
        monkeypatch,
        [sold_on_ebay(SOLD_COPY_ID), article_payload(OTHER_COPY_ID, vinted_id=OTHER_COPY_LISTING_ID)],
        live_listing_id=SOLD_COPY_LISTING_ID,
    )

    remove_after_ebay_sale(SOLD_COPY_ID)

    assert vinted.lookups[0]["vinted_id"] is None
    assert vinted.lookups[0]["other_articles_listing_ids"] == frozenset({OTHER_COPY_LISTING_ID})
    assert vinted.deleted == [SOLD_COPY_LISTING_ID]


def test_other_copy_on_sale_without_vinted_id_blocks_the_removal_before_chrome(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vinted = FakeVinted(
        monkeypatch, [sold_on_ebay(SOLD_COPY_ID), article_payload(OTHER_COPY_ID)], live_listing_id=SOLD_COPY_LISTING_ID
    )

    remove_after_ebay_sale(SOLD_COPY_ID)

    assert vinted.browser_opened == 0
    assert vinted.deleted == []
    assert vinted.reports == [
        (
            f"/articles/{SOLD_COPY_ID}/fail-vinted-cross-removal",
            {
                "detail": f"L’article #{OTHER_COPY_ID}, encore en vente, porte le même titre sur Vinted : "
                "supprimez la bonne annonce depuis Vinted."
            },
        )
    ]


def test_other_copy_already_sold_does_not_block_the_removal(monkeypatch: pytest.MonkeyPatch) -> None:
    vinted = FakeVinted(
        monkeypatch,
        [sold_on_ebay(SOLD_COPY_ID), article_payload(OTHER_COPY_ID, is_sold=True, sale_source="vinted")],
        live_listing_id=SOLD_COPY_LISTING_ID,
    )

    remove_after_ebay_sale(SOLD_COPY_ID)

    assert vinted.deleted == [SOLD_COPY_LISTING_ID]
