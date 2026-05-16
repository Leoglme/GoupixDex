"""
In-process broker for ``/ws/scan-stream`` — fan-out scan events to every
WebSocket currently opened by the same authenticated user.

The hub is intentionally tiny:

* one ``dict[user_id, set[WebSocket]]`` guarded by an :class:`asyncio.Lock`
* one ``deque`` per user holding the last N events so a freshly-opened socket
  (e.g. desktop tab reopened after sleep) can replay missed updates

State is process-local. With a single Uvicorn worker — the production setup —
this is enough. Moving to N workers would require Redis Pub/Sub; that's
out of scope for the MVP.
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from typing import Any

from fastapi import WebSocket
from starlette.websockets import WebSocketState

logger = logging.getLogger(__name__)

#: Max events kept in memory per user for backfill on reconnect.
_HISTORY_PER_USER = 50


class ScanStreamHub:
    """User-scoped pub/sub for scan events (WebSocket fan-out + tiny replay buffer)."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._sockets: dict[int, set[WebSocket]] = {}
        self._history: dict[int, deque[dict[str, Any]]] = {}

    async def connect(self, user_id: int, ws: WebSocket) -> list[dict[str, Any]]:
        """Register the socket and return the backlog the client should replay."""
        await ws.accept()
        async with self._lock:
            self._sockets.setdefault(user_id, set()).add(ws)
            history = list(self._history.get(user_id, deque()))
        return history

    async def disconnect(self, user_id: int, ws: WebSocket) -> None:
        async with self._lock:
            bucket = self._sockets.get(user_id)
            if bucket is None:
                return
            bucket.discard(ws)
            if not bucket:
                self._sockets.pop(user_id, None)

    async def publish(self, user_id: int, payload: dict[str, Any]) -> None:
        """Record the event in the user's backlog and push it to every open socket."""
        async with self._lock:
            buf = self._history.setdefault(user_id, deque(maxlen=_HISTORY_PER_USER))
            buf.append(payload)
            sockets = list(self._sockets.get(user_id, set()))

        if not sockets:
            return

        # Best-effort delivery: drop the socket if it errors out so a dead tab
        # doesn't keep blocking events for the live ones.
        dead: list[WebSocket] = []
        for ws in sockets:
            if ws.application_state != WebSocketState.CONNECTED:
                dead.append(ws)
                continue
            try:
                await ws.send_json(payload)
            except Exception:
                logger.debug("scan-stream socket send failed; dropping", exc_info=True)
                dead.append(ws)

        if dead:
            async with self._lock:
                bucket = self._sockets.get(user_id)
                if bucket is not None:
                    for ws in dead:
                        bucket.discard(ws)
                    if not bucket:
                        self._sockets.pop(user_id, None)

    def history_snapshot(self, user_id: int, limit: int | None = None) -> list[dict[str, Any]]:
        """Synchronous read used by the ``GET /scan-stream/recent`` route."""
        buf = self._history.get(user_id)
        if not buf:
            return []
        items = list(buf)
        if limit is not None and limit > 0:
            items = items[-limit:]
        return items


_HUB = ScanStreamHub()


def get_scan_stream_hub() -> ScanStreamHub:
    """Process-wide singleton (FastAPI DI returns the same instance everywhere)."""
    return _HUB
