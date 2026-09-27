import asyncio

import httpx
import pytest

from services import desktop_api_confirmation_service as confirmation

URL = "https://api.example.test/articles/94/confirm-vinted-unlist"


def fake_api(monkeypatch: pytest.MonkeyPatch, answers: list[int | Exception]) -> list[httpx.Request]:
    calls: list[httpx.Request] = []
    real_async_client = httpx.AsyncClient

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return httpx.Response(answer, json={})

    async def skip_pause(_seconds: float) -> None:
        return None

    monkeypatch.setattr(
        confirmation.httpx,
        "AsyncClient",
        lambda **kwargs: real_async_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    monkeypatch.setattr(confirmation.asyncio, "sleep", skip_pause)
    return calls


def test_confirmation_survives_an_api_redeploy(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = fake_api(monkeypatch, [502, httpx.ConnectError("refused"), 502, 200])

    asyncio.run(confirmation.post_confirmation_to_api(URL, {}, {"hide_when_off_all_platforms": True}))

    assert len(calls) == 4


def test_refused_confirmation_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = fake_api(monkeypatch, [404])

    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(confirmation.post_confirmation_to_api(URL, {}, {}))
    assert len(calls) == 1


def test_confirmation_gives_up_when_the_api_stays_down(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = fake_api(monkeypatch, [502] * 6)

    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(confirmation.post_confirmation_to_api(URL, {}, {}))
    assert len(calls) == 6
