"""In-memory Vinted wardrobe sync jobs (local worker)."""

from __future__ import annotations

import asyncio
from typing import Any

_lock = asyncio.Lock()
_jobs: dict[str, dict[str, Any]] = {}


class WardrobeJobStoreService:
    """In-memory registry of wardrobe sync jobs."""

    @staticmethod
    async def create_job(job_id: str, user_id: int) -> None:
        async with _lock:
            _jobs[job_id] = {
                "user_id": user_id,
                "status": "pending",
                "result": None,
                "error": None,
                "logs": [],
            }

    @staticmethod
    async def set_running(job_id: str) -> None:
        async with _lock:
            if job_id in _jobs:
                _jobs[job_id]["status"] = "running"

    @staticmethod
    async def set_done(job_id: str, result: dict[str, Any]) -> None:
        async with _lock:
            if job_id in _jobs:
                _jobs[job_id]["status"] = "done"
                _jobs[job_id]["result"] = result
                _jobs[job_id]["error"] = None

    @staticmethod
    async def set_error(job_id: str, message: str) -> None:
        async with _lock:
            if job_id in _jobs:
                _jobs[job_id]["status"] = "error"
                _jobs[job_id]["error"] = message
                _jobs[job_id]["result"] = None

    @staticmethod
    def get_job(job_id: str) -> dict[str, Any] | None:
        row = _jobs.get(job_id)
        return dict(row) if row else None

    @staticmethod
    async def append_log_line(job_id: str, message: str) -> None:
        """Append one line to the job log (SSE stream)."""
        async with _lock:
            row = _jobs.get(job_id)
            if not row:
                return
            logs: list[str] = row.setdefault("logs", [])
            logs.append(message)
