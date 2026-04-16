"""Sessions SSE pour publication Vinted groupée (un navigateur, plusieurs annonces)."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

logger = logging.getLogger(__name__)


class VintedBatchSession:
    """Journal + progression + fin pour un job batch (clé ``job_id`` UUID)."""

    def __init__(self) -> None:
        self._logs: list[dict[str, Any]] = []
        self._condition = asyncio.Condition()
        self._done = False

    async def emit(self, event: dict[str, Any]) -> None:
        async with self._condition:
            self._logs.append(event)
            self._condition.notify_all()

    async def finish(self, payload: dict[str, Any]) -> None:
        async with self._condition:
            self._logs.append({"type": "done", **payload})
            self._done = True
            self._condition.notify_all()

    async def iter_events(self) -> AsyncIterator[dict[str, Any]]:
        i = 0
        while True:
            async with self._condition:
                while i >= len(self._logs) and not self._done:
                    try:
                        await asyncio.wait_for(self._condition.wait(), timeout=3600.0)
                    except asyncio.TimeoutError:
                        yield {"type": "error", "message": "Délai dépassé (1 h)"}
                        return
                while i < len(self._logs):
                    ev = self._logs[i]
                    i += 1
                    yield ev
                    if ev.get("type") == "done":
                        return
                if self._done and i >= len(self._logs):
                    return


_sessions: dict[str, VintedBatchSession] = {}
_active_job_by_user: dict[int, str] = {}
_job_owner: dict[str, int] = {}


def try_register_job(job_id: str, user_id: int) -> bool:
    """Enregistre un job ; False si l'utilisateur a déjà un lot en cours."""
    if user_id in _active_job_by_user:
        return False
    _sessions[job_id] = VintedBatchSession()
    _active_job_by_user[user_id] = job_id
    _job_owner[job_id] = user_id
    return True


def get_job_user_id(job_id: str) -> int | None:
    return _job_owner.get(job_id)


def clear_active_job_for_user(user_id: int) -> None:
    """Libère le pointeur « job actif » pour l'utilisateur (la session SSE reste jusqu'à cleanup)."""
    _active_job_by_user.pop(user_id, None)


def get_active_job_id(user_id: int) -> str | None:
    return _active_job_by_user.get(user_id)


def get_session(job_id: str) -> VintedBatchSession | None:
    return _sessions.get(job_id)


async def emit_event(job_id: str, event: dict[str, Any]) -> None:
    s = _sessions.get(job_id)
    if s is None:
        return
    await s.emit(event)


async def finish_job(job_id: str, payload: dict[str, Any]) -> None:
    s = _sessions.get(job_id)
    if s is None:
        return
    await s.finish(payload)


async def event_stream(job_id: str) -> AsyncIterator[dict[str, Any]]:
    s = _sessions.get(job_id)
    if s is None:
        yield {"type": "error", "message": "Job introuvable ou expiré."}
        return
    async for ev in s.iter_events():
        yield ev


def cleanup_later(job_id: str, delay_sec: float = 600.0) -> None:
    async def _run() -> None:
        await asyncio.sleep(delay_sec)
        _sessions.pop(job_id, None)
        _job_owner.pop(job_id, None)

    try:
        asyncio.get_running_loop().create_task(_run())
    except RuntimeError:
        pass
