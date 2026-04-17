"""SSE sessions for grouped Vinted publish (one browser, several listings)."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any, ClassVar


class _VintedBatchChannel:
    """Log + progress + completion for a batch job (``job_id`` UUID key)."""

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


class VintedBatchSessionService:
    """Registry of batch jobs + SSE stream per ``job_id``."""

    _sessions: ClassVar[dict[str, _VintedBatchChannel]] = {}
    _active_job_by_user: ClassVar[dict[int, str]] = {}
    _job_owner: ClassVar[dict[str, int]] = {}

    @classmethod
    def try_register_job(cls, job_id: str, user_id: int) -> bool:
        """Register a job; False if the user already has a batch in progress."""
        if user_id in cls._active_job_by_user:
            return False
        cls._sessions[job_id] = _VintedBatchChannel()
        cls._active_job_by_user[user_id] = job_id
        cls._job_owner[job_id] = user_id
        return True

    @classmethod
    def get_job_user_id(cls, job_id: str) -> int | None:
        return cls._job_owner.get(job_id)

    @classmethod
    def clear_active_job_for_user(cls, user_id: int) -> None:
        """Clear the active-job pointer for the user (SSE session remains until cleanup)."""
        cls._active_job_by_user.pop(user_id, None)

    @classmethod
    def get_active_job_id(cls, user_id: int) -> str | None:
        return cls._active_job_by_user.get(user_id)

    @classmethod
    def get_session(cls, job_id: str) -> _VintedBatchChannel | None:
        return cls._sessions.get(job_id)

    @classmethod
    async def emit_event(cls, job_id: str, event: dict[str, Any]) -> None:
        s = cls._sessions.get(job_id)
        if s is None:
            return
        await s.emit(event)

    @classmethod
    async def finish_job(cls, job_id: str, payload: dict[str, Any]) -> None:
        s = cls._sessions.get(job_id)
        if s is None:
            return
        await s.finish(payload)

    @classmethod
    async def event_stream(cls, job_id: str) -> AsyncIterator[dict[str, Any]]:
        s = cls._sessions.get(job_id)
        if s is None:
            yield {"type": "error", "message": "Job introuvable ou expiré."}
            return
        async for ev in s.iter_events():
            yield ev

    @classmethod
    def cleanup_later(cls, job_id: str, delay_sec: float = 600.0) -> None:
        async def _run() -> None:
            await asyncio.sleep(delay_sec)
            cls._sessions.pop(job_id, None)
            cls._job_owner.pop(job_id, None)

        try:
            asyncio.get_running_loop().create_task(_run())
        except RuntimeError:
            pass
