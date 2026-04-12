"""Sessions de progression Vinted (SSE) — état en mémoire par worker."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

logger = logging.getLogger(__name__)


class VintedProgressSession:
    """Journal d'événements + signalement de fin pour une publication Vinted."""

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
        """Rejoue l'historique puis attend les entrées suivantes jusqu'à ``done``."""
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


_sessions: dict[int, VintedProgressSession] = {}


def register(article_id: int) -> None:
    if article_id in _sessions:
        logger.warning("Vinted progress: replacing existing session article_id=%s", article_id)
    _sessions[article_id] = VintedProgressSession()


def get_session(article_id: int) -> VintedProgressSession | None:
    return _sessions.get(article_id)


async def emit(article_id: int, event: dict[str, Any]) -> None:
    s = _sessions.get(article_id)
    if s is None:
        return
    await s.emit(event)


async def finish(article_id: int, vinted: dict[str, Any]) -> None:
    s = _sessions.get(article_id)
    if s is None:
        return
    await s.finish(vinted)


async def event_stream(article_id: int) -> AsyncIterator[dict[str, Any]]:
    s = _sessions.get(article_id)
    if s is None:
        yield {"type": "error", "message": "Aucune session de publication pour cet article."}
        return
    async for ev in s.iter_events():
        yield ev


def cleanup_later(article_id: int, delay_sec: float = 300.0) -> None:
    """Libère la session après quelques minutes (évite fuites en dev)."""

    async def _run() -> None:
        await asyncio.sleep(delay_sec)
        _sessions.pop(article_id, None)

    try:
        asyncio.get_running_loop().create_task(_run())
    except RuntimeError:
        pass
