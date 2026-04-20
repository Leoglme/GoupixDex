"""Vinted publish progress sessions (SSE) — in-memory per worker."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any, ClassVar


class _VintedProgressChannel:
    """Event log + completion signal for one Vinted listing publish."""

    def __init__(self) -> None:
        self._logs: list[dict[str, Any]] = []
        self._condition = asyncio.Condition()
        self._done = False

    async def emit(self, event: dict[str, Any]) -> None:
        async with self._condition:
            self._logs.append(event)
            self._condition.notify_all()

    async def finish(self, payload: dict[str, Any]) -> None:
        """``payload``: keys such as ``vinted`` / ``ebay`` merged into the ``done`` event."""
        async with self._condition:
            done_ev = {"type": "done", **payload}
            self._logs.append(done_ev)
            self._done = True
            self._condition.notify_all()

    async def iter_events(self) -> AsyncIterator[dict[str, Any]]:
        """Replay history then wait for further entries until ``done``."""
        i = 0
        while True:
            async with self._condition:
                while i >= len(self._logs) and not self._done:
                    try:
                        await asyncio.wait_for(self._condition.wait(), timeout=600.0)
                    except asyncio.TimeoutError:
                        yield {"type": "error", "message": "Timed out (10 min)"}
                        return
                while i < len(self._logs):
                    ev = self._logs[i]
                    i += 1
                    yield ev
                    if ev.get("type") == "done":
                        return
                if self._done and i >= len(self._logs):
                    return


class VintedProgressSessionService:
    """Registry of SSE sessions keyed by ``article_id``."""

    _sessions: ClassVar[dict[int, _VintedProgressChannel]] = {}

    @classmethod
    def register(cls, article_id: int) -> None:
        """Create a session if missing (Vinted + eBay may share the same SSE stream)."""
        if article_id not in cls._sessions:
            cls._sessions[article_id] = _VintedProgressChannel()

    @classmethod
    def get_session(cls, article_id: int) -> _VintedProgressChannel | None:
        return cls._sessions.get(article_id)

    @classmethod
    async def emit(cls, article_id: int, event: dict[str, Any]) -> None:
        s = cls._sessions.get(article_id)
        if s is None:
            return
        await s.emit(event)

    @classmethod
    async def finish(cls, article_id: int, payload: dict[str, Any]) -> None:
        s = cls._sessions.get(article_id)
        if s is None:
            return
        await s.finish(payload)

    @classmethod
    async def event_stream(cls, article_id: int) -> AsyncIterator[dict[str, Any]]:
        # Petit filet de sécurité : si une route a enregistré la session via
        # `BackgroundTasks` (donc après le retour HTTP) ou si le front ouvre le
        # SSE très vite après un POST 202, on laisse jusqu'à ~1,5 s pour que
        # `register()` soit appelé. Au-delà on considère qu'il n'y a vraiment
        # pas de publication en cours pour cet article.
        s = cls._sessions.get(article_id)
        if s is None:
            for _ in range(15):
                await asyncio.sleep(0.1)
                s = cls._sessions.get(article_id)
                if s is not None:
                    break
        if s is None:
            yield {"type": "error", "message": "Aucune session de publication pour cet article."}
            return
        async for ev in s.iter_events():
            yield ev

    @classmethod
    def cleanup_later(cls, article_id: int, delay_sec: float = 300.0) -> None:
        """Drop the session after a few minutes (avoids leaks in dev)."""

        async def _run() -> None:
            await asyncio.sleep(delay_sec)
            cls._sessions.pop(article_id, None)

        try:
            asyncio.get_running_loop().create_task(_run())
        except RuntimeError:
            pass
