import asyncio
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from models.article import Article
from services import ebay_listing_delete_service as ebay_delete

SKU = "gpx884783fab78cef"
OFFER_ID = "171190907011"
GET_OFFERS = "GET /sell/inventory/v1/offer"
WITHDRAW = f"POST /sell/inventory/v1/offer/{OFFER_ID}/withdraw"
DELETE_OFFER = f"DELETE /sell/inventory/v1/offer/{OFFER_ID}"
DELETE_INVENTORY_ITEM = f"DELETE /sell/inventory/v1/inventory_item/{SKU}"


def fake_ebay(monkeypatch: pytest.MonkeyPatch, answers: dict[str, int | Exception]) -> list[str]:
    calls: list[str] = []
    real_async_client = httpx.AsyncClient

    def handler(request: httpx.Request) -> httpx.Response:
        call = f"{request.method} {request.url.path}"
        calls.append(call)
        answer = answers[call]
        if isinstance(answer, Exception):
            raise answer
        if call == GET_OFFERS and answer == 200:
            return httpx.Response(200, json={"offers": [{"offerId": OFFER_ID, "status": "PUBLISHED"}]})
        return httpx.Response(answer)

    async def fake_access_token(*_args: Any, **_kwargs: Any) -> str:
        return "ebay-token"

    monkeypatch.setattr(
        ebay_delete.httpx,
        "AsyncClient",
        lambda **kwargs: real_async_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    monkeypatch.setattr(ebay_delete, "ensure_ebay_access_token", fake_access_token)
    return calls


def remove_spiritomb_listing() -> tuple[bool, str | None]:
    article = Article(
        id=88,
        title="Spiritomb m1l 071/063 AR - Mega Brave - Pokémon Japonais",
        published_on_ebay=True,
        ebay_listing_id="358576456267",
        ebay_inventory_sku=SKU,
    )
    settings = SimpleNamespace(ebay_client_id="client-id", ebay_use_sandbox=False)
    return asyncio.run(
        ebay_delete.delete_ebay_listing_for_article(SimpleNamespace(), article, SimpleNamespace(), app=settings)
    )


def test_ended_listing_counts_as_removed_when_ebay_fails_to_delete_the_offer(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = fake_ebay(monkeypatch, {GET_OFFERS: 200, WITHDRAW: 200, DELETE_OFFER: 500, DELETE_INVENTORY_ITEM: 204})

    assert remove_spiritomb_listing() == (True, None)
    assert calls == [GET_OFFERS, WITHDRAW, DELETE_OFFER, DELETE_INVENTORY_ITEM]


def test_offer_already_gone_on_ebay_counts_as_removed(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = fake_ebay(monkeypatch, {GET_OFFERS: 404, DELETE_INVENTORY_ITEM: 404})

    assert remove_spiritomb_listing() == (True, None)
    assert calls == [GET_OFFERS, DELETE_INVENTORY_ITEM]


def test_listing_still_live_when_ebay_refuses_to_end_it(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = fake_ebay(monkeypatch, {GET_OFFERS: 200, WITHDRAW: 500, DELETE_OFFER: 500})

    is_removed, error = remove_spiritomb_listing()

    assert not is_removed
    assert error is not None
    assert DELETE_INVENTORY_ITEM not in calls


def test_unreachable_ebay_is_reported_without_raising(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_ebay(monkeypatch, {GET_OFFERS: httpx.ConnectError("refused")})

    is_removed, error = remove_spiritomb_listing()

    assert not is_removed
    assert error == "eBay ne répond pas pour le moment : réessayez dans quelques minutes."
