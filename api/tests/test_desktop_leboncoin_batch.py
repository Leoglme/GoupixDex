import asyncio
from typing import Any

import pytest

from services.desktop_leboncoin_runner_service import DesktopLeboncoinRunnerService
from services.leboncoin_publish_service import ProgressFn
from services.vinted_batch_session_service import VintedBatchSessionService as batch_hub

USER_ID = 1


def fake_publications(monkeypatch: pytest.MonkeyPatch, results: dict[int, dict[str, Any]]) -> list[int]:
    published_article_ids: list[int] = []

    async def publish_article(
        article_id: int, _user_id: int, _token: str, _remote_base: str, *, progress: ProgressFn
    ) -> dict[str, Any]:
        published_article_ids.append(article_id)
        await progress({"type": "log", "step": "browser", "message": "Ouverture de Chrome (profil Leboncoin)…"})
        return results[article_id]

    monkeypatch.setattr(DesktopLeboncoinRunnerService, "_publish_article", publish_article)
    monkeypatch.setattr(batch_hub, "cleanup_later", lambda job_id, delay_sec=600.0: None)
    return published_article_ids


async def run_batch(job_id: str, article_ids: list[int]) -> list[dict[str, Any]]:
    assert batch_hub.try_register_job(job_id, USER_ID)
    await DesktopLeboncoinRunnerService.run_desktop_leboncoin_batch_job(
        job_id, USER_ID, article_ids, "token", "https://api.example.test"
    )
    return [event async for event in batch_hub.event_stream(job_id)]


def test_batch_publishes_each_article_in_turn_and_keeps_going_after_a_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    published_article_ids = fake_publications(
        monkeypatch,
        {119: {"published": True, "listing_id": "3000000001"}, 71: {"published": False, "detail": "photo refusée"}},
    )

    events = asyncio.run(run_batch("lbc-job-1", [119, 71]))

    assert published_article_ids == [119, 71]
    messages = [event["message"] for event in events if event.get("type") == "log"]
    assert "1/2 — Ouverture de Chrome (profil Leboncoin)…" in messages
    assert "1/2 — Annonce publiée sur Leboncoin." in messages
    assert "2/2 — Échec : photo refusée." in messages
    assert events[-1]["type"] == "done"
    assert events[-1]["leboncoin"] == {"published": False, "count": 2, "published_count": 1}
    assert batch_hub.get_active_job_id(USER_ID) is None


def test_batch_reports_success_when_every_article_is_published(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_publications(monkeypatch, {119: {"published": True}, 80: {"published": True}})

    events = asyncio.run(run_batch("lbc-job-2", [119, 80]))

    assert events[-1]["leboncoin"] == {"published": True, "count": 2, "published_count": 2}
