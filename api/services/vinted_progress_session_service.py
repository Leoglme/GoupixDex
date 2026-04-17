"""Vinted publish progress sessions (SSE) — in-memory per worker."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any, ClassVar

logger = logging.getLogger(__name__)


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

    async def finish(self, vinted: dict[str, Any]) -> None:
        async with self._condition:
            payload = {"type": "done", "vinted": vinted}
            self._logs.append(payload)
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
                        yield {"type": "error", "message": "Délai dépassé (10 min)"}
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
        if article_id in cls._sessions:
            logger.warning(
                "Vinted progress: replacing existing session article_id=%s", article_id
            )
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
    async def finish(cls, article_id: int, vinted: dict[str, Any]) -> None:
        s = cls._sessions.get(article_id)
        if s is None:
            return
        await s.finish(vinted)

    @classmethod
    async def event_stream(cls, article_id: int) -> AsyncIterator[dict[str, Any]]:
        s = cls._sessions.get(article_id)
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
