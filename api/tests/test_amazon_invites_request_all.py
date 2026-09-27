from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import pytest
from fastapi.testclient import TestClient

import desktop_amazon_server as worker

USER_ID = 7
ACTIVE_ACCOUNT_ID = 1
NOT_CONNECTED_ACCOUNT_ID = 3
ALREADY_REQUESTED_ASIN = "B0ALREADY1"
BROKEN_PAGE_ASIN = "B0BROKEN01"


@dataclass
class RecordedWorkerCalls:
    bound_account_ids: list[int | None] = field(default_factory=list)
    progress_events: list[dict[str, Any]] = field(default_factory=list)


class FakeBrowserScraper:
    def request_invitation_via_browser(self, asin: str) -> dict[str, Any]:
        if asin == ALREADY_REQUESTED_ASIN:
            return {
                "success": False,
                "message": "Invitation already recorded or status changed.",
                "item": {"asin": asin, "title": "Coffret", "invitation_status": "requested"},
            }
        if asin == BROKEN_PAGE_ASIN:
            return {"success": False, "message": "Invitation button not found.", "item": None}
        return {
            "success": True,
            "message": "Invitation requested.",
            "item": {"asin": asin, "title": f"Produit {asin}", "invitation_status": "requested"},
        }


@pytest.fixture
def worker_calls(monkeypatch: pytest.MonkeyPatch) -> Iterator[RecordedWorkerCalls]:
    calls = RecordedWorkerCalls()

    async def fake_close_chromium() -> None:
        return None

    async def fake_ensure_signed_in(
        _user_id: int, account_id: int, _raw_token: str, _remote: str, _scraper: Any
    ) -> None:
        if account_id == NOT_CONNECTED_ACCOUNT_ID:
            raise RuntimeError("Connexion automatique échouée.")

    async def fake_broadcast(payload: dict[str, Any]) -> None:
        calls.progress_events.append(payload)

    monkeypatch.setattr(worker, "_close_all_amazon_chromium", fake_close_chromium)
    monkeypatch.setattr(
        worker, "bind_amazon_profile_for", lambda _user_id, account_id: calls.bound_account_ids.append(account_id)
    )
    monkeypatch.setattr(worker, "_reset_amazon_scraper", lambda: None)
    monkeypatch.setattr(worker, "_browser_scraper", FakeBrowserScraper)
    monkeypatch.setattr(worker, "_ensure_account_signed_in", fake_ensure_signed_in)
    monkeypatch.setattr(worker, "_broadcast_amazon_progress", fake_broadcast)
    monkeypatch.setattr(worker, "_invites_cache", {})
    worker.app.dependency_overrides[worker.get_user_id_introspected] = lambda: USER_ID
    worker.app.dependency_overrides[worker.bind_active_amazon_profile] = lambda: ACTIVE_ACCOUNT_ID
    worker.app.dependency_overrides[worker.get_bearer_or_query_token] = lambda: "token"
    worker.app.dependency_overrides[worker.get_remote_base_flexible] = lambda: "http://remote"
    yield calls
    worker.app.dependency_overrides.clear()


def test_request_all_goes_through_every_account_even_when_one_cannot_sign_in(
    worker_calls: RecordedWorkerCalls,
) -> None:
    worker._invites_cache[worker._invites_cache_key(USER_ID, 1)] = [
        {"id": "B0NEWINV01", "asin": "B0NEWINV01", "title": "Mini-boîte", "status": "not_requested"},
    ]

    response = TestClient(worker.app).post(
        "/amazon/invites/request-all",
        json={
            "accounts": [
                {"account_id": 1, "asins": ["B0NEWINV01", ALREADY_REQUESTED_ASIN]},
                {"account_id": NOT_CONNECTED_ACCOUNT_ID, "asins": ["B0NEWINV02"]},
                {"account_id": 2, "asins": ["B0NEWINV03", BROKEN_PAGE_ASIN]},
            ]
        },
    )

    assert response.status_code == 200
    body = response.json()
    outcomes = {
        account_id: [outcome["outcome"] for outcome in account_outcomes]
        for account_id, account_outcomes in body["outcomes_by_account"].items()
    }
    assert outcomes == {"1": ["requested", "already_done"], "3": [], "2": ["requested", "failed"]}
    assert list(body["errors"]) == ["3"]
    assert (body["requested_count"], body["already_done_count"], body["failed_count"]) == (2, 1, 1)
    assert worker_calls.bound_account_ids == [1, NOT_CONNECTED_ACCOUNT_ID, 2, ACTIVE_ACCOUNT_ID]
    assert worker._invites_cache[worker._invites_cache_key(USER_ID, 1)][0]["status"] == "requested"
    last_event = worker_calls.progress_events[-1]
    assert (last_event["status"], last_event["current_page"], last_event["total_pages"]) == ("completed", 5, 5)


def test_request_all_rejects_an_invalid_asin(worker_calls: RecordedWorkerCalls) -> None:
    response = TestClient(worker.app).post(
        "/amazon/invites/request-all",
        json={"accounts": [{"account_id": 1, "asins": ["pas-un-asin"]}]},
    )

    assert response.status_code == 422
    assert worker_calls.bound_account_ids == []
