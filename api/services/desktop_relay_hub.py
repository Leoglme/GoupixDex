"""
In-process relay between the web app on another device (iPad, phone) and the
user's desktop app (GoupixDex Windows), which alone can drive the local workers
(Vinted, Amazon, Cardmarket, Leboncoin through Chrome).

* The desktop app holds one SSE stream (``GET /desktop-relay/agent/stream``):
  it receives the commands, runs them against its local workers and posts the
  results back (``POST /desktop-relay/agent/...``).
* Each web client holds its own SSE stream (``GET /desktop-relay/client/stream``)
  where the responses, stream events and desktop presence changes land.

Every method is synchronous (no ``await``), so each call is atomic on the event
loop. State is process-local, like ``ScanStreamHub``: enough for the single
Uvicorn worker used in production.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

#: Events buffered per web client; the oldest are dropped beyond this.
_CLIENT_QUEUE_MAX = 500

_DISCONNECTED_CLIENT_TTL_S = 120.0

#: Pending requests / streams older than this are forgotten (longest worker call: ~30 min).
_PENDING_TTL_S = 40 * 60.0

#: Queue marker telling an SSE generator that a newer connection replaced it.
CONNECTION_REPLACED: dict[str, Any] = {"type": "connection-replaced"}


class DesktopAgentOfflineError(Exception):
    """No desktop app is connected for this user."""


class UnknownRelayClientError(Exception):
    """The web client id is unknown or belongs to another user."""


@dataclass
class DesktopAgentConnection:
    """One SSE connection opened by the desktop app."""

    queue: asyncio.Queue[dict[str, Any]]
    connected_at: float
    app_version: str | None


@dataclass
class RelayClientConnection:
    """One web client (browser tab), kept alive across short reconnections."""

    user_id: int
    queue: asyncio.Queue[dict[str, Any]]
    is_connected: bool = True
    disconnected_at: float | None = None


@dataclass
class _PendingRelayEntry:
    user_id: int
    client_id: str
    created_at: float


class DesktopRelayHub:
    """Routes commands from a user's web clients to their desktop app, and results back."""

    def __init__(self) -> None:
        self._agents: dict[int, DesktopAgentConnection] = {}
        self._clients: dict[str, RelayClientConnection] = {}
        self._requests: dict[str, _PendingRelayEntry] = {}
        self._streams: dict[str, _PendingRelayEntry] = {}

    def attach_agent(self, user_id: int, app_version: str | None) -> DesktopAgentConnection:
        """Register the desktop app of ``user_id``; a previous connection of the same user is replaced."""
        agent = DesktopAgentConnection(queue=asyncio.Queue(), connected_at=time.time(), app_version=app_version)
        previous = self._agents.get(user_id)
        self._agents[user_id] = agent
        if previous is not None:
            previous.queue.put_nowait(CONNECTION_REPLACED)
        self._notify_agent_status(user_id)
        return agent

    def detach_agent(self, user_id: int, agent: DesktopAgentConnection) -> None:
        """Forget the desktop app connection and fail everything still waiting on it."""
        if self._agents.get(user_id) is not agent:
            return
        del self._agents[user_id]

        for request_id, entry in list(self._requests.items()):
            if entry.user_id == user_id:
                del self._requests[request_id]
                self._push_to_client(
                    entry.client_id,
                    {"type": "response", "id": request_id, "status": 503, "error": "desktop_disconnected"},
                )
        for stream_id, entry in list(self._streams.items()):
            if entry.user_id == user_id:
                del self._streams[stream_id]
                self._push_to_client(entry.client_id, {"type": "stream-end", "id": stream_id, "error": "desktop_disconnected"})

        self._notify_agent_status(user_id)

    def agent_status(self, user_id: int) -> dict[str, Any]:
        """Presence of the desktop app, as sent to web clients."""
        agent = self._agents.get(user_id)
        if agent is None:
            return {"online": False}
        return {"online": True, "connected_at": agent.connected_at, "app_version": agent.app_version}

    def attach_client(self, user_id: int, client_id: str) -> RelayClientConnection:
        """Register a web client SSE connection; reconnecting with the same id keeps its buffered events."""
        self._forget_stale_entries()
        existing = self._clients.get(client_id)
        if existing is not None and existing.user_id == user_id:
            # Hand the buffered events to the new connection, then stop the old generator.
            fresh_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=_CLIENT_QUEUE_MAX)
            while not existing.queue.empty():
                fresh_queue.put_nowait(existing.queue.get_nowait())
            existing.queue.put_nowait(CONNECTION_REPLACED)
            existing.queue = fresh_queue
            existing.is_connected = True
            existing.disconnected_at = None
            return existing

        client = RelayClientConnection(user_id=user_id, queue=asyncio.Queue(maxsize=_CLIENT_QUEUE_MAX))
        self._clients[client_id] = client
        return client

    def detach_client(self, client_id: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
        """Mark the web client disconnected when ``queue`` still belongs to its current connection."""
        client = self._clients.get(client_id)
        if client is None or client.queue is not queue:
            return
        client.is_connected = False
        client.disconnected_at = time.time()

    def submit_request(self, user_id: int, client_id: str, command: dict[str, Any]) -> str:
        """Forward one worker HTTP call to the desktop app; the response comes back on the client stream."""
        agent = self._require_agent(user_id)
        self._require_client(user_id, client_id)
        request_id = uuid.uuid4().hex
        self._requests[request_id] = _PendingRelayEntry(user_id=user_id, client_id=client_id, created_at=time.time())
        agent.queue.put_nowait({"type": "request", "id": request_id, **command})
        return request_id

    def complete_request(self, user_id: int, request_id: str, response: dict[str, Any]) -> bool:
        """Deliver the desktop app response to the web client that asked for it."""
        entry = self._requests.get(request_id)
        if entry is None or entry.user_id != user_id:
            return False
        del self._requests[request_id]
        self._push_to_client(entry.client_id, {"type": "response", "id": request_id, **response})
        return True

    def open_stream(self, user_id: int, client_id: str, command: dict[str, Any]) -> str:
        """Ask the desktop app to open a worker progress stream (SSE or WebSocket) for the web client."""
        agent = self._require_agent(user_id)
        self._require_client(user_id, client_id)
        stream_id = uuid.uuid4().hex
        self._streams[stream_id] = _PendingRelayEntry(user_id=user_id, client_id=client_id, created_at=time.time())
        agent.queue.put_nowait({"type": "stream-open", "id": stream_id, **command})
        return stream_id

    def push_stream_events(self, user_id: int, stream_id: str, events: list[dict[str, Any]]) -> bool:
        """Forward the worker events read by the desktop app to the web client."""
        entry = self._streams.get(stream_id)
        if entry is None or entry.user_id != user_id:
            return False
        self._push_to_client(entry.client_id, {"type": "stream-events", "id": stream_id, "events": events})
        return True

    def end_stream(self, user_id: int, stream_id: str, error: str | None) -> bool:
        """Tell the web client that the worker stream is over."""
        entry = self._streams.get(stream_id)
        if entry is None or entry.user_id != user_id:
            return False
        del self._streams[stream_id]
        self._push_to_client(entry.client_id, {"type": "stream-end", "id": stream_id, "error": error})
        return True

    def close_stream(self, user_id: int, client_id: str, stream_id: str) -> bool:
        """Stop a stream on the web client's request: the desktop app closes the worker connection."""
        entry = self._streams.get(stream_id)
        if entry is None or entry.user_id != user_id or entry.client_id != client_id:
            return False
        del self._streams[stream_id]
        agent = self._agents.get(user_id)
        if agent is not None:
            agent.queue.put_nowait({"type": "stream-close", "id": stream_id})
        return True

    def _require_agent(self, user_id: int) -> DesktopAgentConnection:
        agent = self._agents.get(user_id)
        if agent is None:
            raise DesktopAgentOfflineError
        return agent

    def _require_client(self, user_id: int, client_id: str) -> None:
        client = self._clients.get(client_id)
        if client is None or client.user_id != user_id:
            raise UnknownRelayClientError

    def _push_to_client(self, client_id: str, event: dict[str, Any]) -> None:
        client = self._clients.get(client_id)
        if client is None:
            return
        if client.queue.full():
            with suppress(asyncio.QueueEmpty):
                client.queue.get_nowait()
            logger.warning("desktop-relay: client %s queue full, oldest event dropped", client_id)
        client.queue.put_nowait(event)

    def _notify_agent_status(self, user_id: int) -> None:
        status = self.agent_status(user_id)
        for client_id, client in self._clients.items():
            if client.user_id == user_id:
                self._push_to_client(client_id, {"type": "agent-status", **status})

    def _forget_stale_entries(self) -> None:
        now = time.time()
        stale_client_ids = [
            client_id
            for client_id, client in self._clients.items()
            if not client.is_connected
            and client.disconnected_at is not None
            and now - client.disconnected_at > _DISCONNECTED_CLIENT_TTL_S
        ]
        for client_id in stale_client_ids:
            del self._clients[client_id]

        for request_id, entry in list(self._requests.items()):
            if entry.client_id in stale_client_ids or now - entry.created_at > _PENDING_TTL_S:
                del self._requests[request_id]
        for stream_id, entry in list(self._streams.items()):
            if entry.client_id in stale_client_ids or now - entry.created_at > _PENDING_TTL_S:
                self.close_stream(entry.user_id, entry.client_id, stream_id)


_hub: DesktopRelayHub | None = None


def get_desktop_relay_hub() -> DesktopRelayHub:
    """Process-wide relay hub."""
    global _hub
    if _hub is None:
        _hub = DesktopRelayHub()
    return _hub
