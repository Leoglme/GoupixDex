"""
In-process broker for ``/ws/scan-stream`` — fan-out scan events to every
WebSocket currently opened by the same authenticated user.

The hub is intentionally tiny:

* one ``dict[user_id, set[WebSocket]]`` guarded by an :class:`asyncio.Lock`
* one ``deque`` per user holding the last N events so a freshly-opened socket
  (e.g. desktop tab reopened after sleep) can replay missed updates.
  A scan lifecycle publishes several events with the same ``event_id``
  (queued → ocr_running → … → added); the history keeps **one entry per
  event_id** (the latest state) so the backlog and ``GET /scan-stream/recent``
  stay small even with base64 previews attached.

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
        #: Per-user lock serialising ``send_json`` calls: Starlette does not
        #: allow concurrent sends on one socket (backlog replay vs live publish).
        self._send_locks: dict[int, asyncio.Lock] = {}

    async def _send_lock_for(self, user_id: int) -> asyncio.Lock:
        async with self._lock:
            return self._send_locks.setdefault(user_id, asyncio.Lock())

    async def connect(self, user_id: int, ws: WebSocket) -> None:
        """Accept the socket, register it, and replay the user's backlog on it."""
        await ws.accept()
        async with self._lock:
            self._sockets.setdefault(user_id, set()).add(ws)
            backlog = list(self._history.get(user_id, deque()))
            send_lock = self._send_locks.setdefault(user_id, asyncio.Lock())

        async with send_lock:
            for past in backlog:
                await ws.send_json(past)

    async def disconnect(self, user_id: int, ws: WebSocket) -> None:
        async with self._lock:
            bucket = self._sockets.get(user_id)
            if bucket is None:
                return
            bucket.discard(ws)
            if not bucket:
                self._sockets.pop(user_id, None)
                self._send_locks.pop(user_id, None)

    async def publish(self, user_id: int, payload: dict[str, Any], *, transient: bool = False) -> None:
        """
        Record the event in the user's backlog and push it to every open socket.

        ``transient=True`` skips the backlog entirely (live feedback only, e.g.
        a frame dropped by the pre-OCR gate — useless after the fact).
        """
        async with self._lock:
            if not transient:
                buf = self._history.setdefault(user_id, deque(maxlen=_HISTORY_PER_USER))
                event_id = str(payload.get("event_id"))
                # One history slot per scan: replace the previous state in place.
                for index, item in enumerate(buf):
                    if str(item.get("event_id")) == event_id:
                        buf[index] = payload
                        break
                else:
                    buf.append(payload)
            sockets = list(self._sockets.get(user_id, set()))
            send_lock = self._send_locks.setdefault(user_id, asyncio.Lock())

        if not sockets:
            return

        # Best-effort delivery: drop the socket if it errors out so a dead tab
        # doesn't keep blocking events for the live ones.
        dead: list[WebSocket] = []
        async with send_lock:
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
                        self._send_locks.pop(user_id, None)

    def history_snapshot(self, user_id: int, limit: int | None = None) -> list[dict[str, Any]]:
        """Synchronous read used by the ``GET /scan-stream/recent`` route."""
        buf = self._history.get(user_id)
        if not buf:
            return []
        items = list(buf)
        if limit is not None and limit > 0:
            items = items[-limit:]
        return items

    def dismiss_event(self, user_id: int, event_id: str) -> bool:
        """Remove one event from the in-memory backlog (UI dismiss)."""
        buf = self._history.get(user_id)
        if not buf:
            return False
        kept = [item for item in buf if str(item.get("event_id")) != event_id]
        if len(kept) == len(buf):
            return False
        self._history[user_id] = deque(kept, maxlen=_HISTORY_PER_USER)
        return True

    def clear_events(
        self,
        user_id: int,
        *,
        statuses: set[str] | None = None,
    ) -> int:
        """
        Drop events from the backlog, optionally filtered by terminal ``status``.

        When ``statuses`` is ``None``, clears the entire history for the user.
        """
        buf = self._history.get(user_id)
        if not buf:
            return 0
        if statuses is None:
            removed = len(buf)
            self._history.pop(user_id, None)
            return removed
        kept = [item for item in buf if str(item.get("status")) not in statuses]
        removed = len(buf) - len(kept)
        if removed:
            self._history[user_id] = deque(kept, maxlen=_HISTORY_PER_USER)
        return removed


_HUB = ScanStreamHub()


def get_scan_stream_hub() -> ScanStreamHub:
    """Process-wide singleton (FastAPI DI returns the same instance everywhere)."""
    return _HUB
