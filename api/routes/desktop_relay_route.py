"""
Desktop relay: lets a web client (iPad, phone) run the desktop-only actions on the
user's own PC, where the GoupixDex desktop app drives the local workers.

Both long-lived channels are SSE (WebSocket upgrades are not proxied by the
production nginx); everything else is plain JSON POST.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Iterable
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

from core.database import SessionLocal
from core.deps import get_bearer_or_query_token, get_current_user, get_current_user_from_token_str
from models.user import User
from schemas.desktop_relay import (
    DesktopRelayRequestIn,
    DesktopRelayResponseIn,
    DesktopRelayStreamEndIn,
    DesktopRelayStreamEventsIn,
    DesktopRelayStreamIn,
)
from services.desktop_relay_hub import (
    CONNECTION_REPLACED,
    DesktopAgentOfflineError,
    UnknownRelayClientError,
    get_desktop_relay_hub,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/desktop-relay", tags=["desktop-relay"])

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}

#: Comment line sent on idle streams so nginx and the browser keep them open.
_HEARTBEAT_INTERVAL_S = 15.0


def _approved_user_id_from_token(raw_token: str) -> int:
    """Resolve the token owner with a short-lived session: SSE streams must not pin a pooled connection."""
    db = SessionLocal()
    try:
        user = get_current_user_from_token_str(raw_token=raw_token, db=db)
        if str(user.status or "") != "approved":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access revoked")
        return int(user.id)
    finally:
        db.close()


def _format_sse(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event, default=str)}\n\n"


async def _iter_sse(
    queue: asyncio.Queue[dict[str, Any]],
    first_events: Iterable[dict[str, Any]] = (),
) -> AsyncIterator[str]:
    yield "retry: 3000\n\n"
    for event in first_events:
        yield _format_sse(event)
    while True:
        try:
            event = await asyncio.wait_for(queue.get(), timeout=_HEARTBEAT_INTERVAL_S)
        except asyncio.TimeoutError:
            yield ": ping\n\n"
            continue
        yield _format_sse(event)
        if event is CONNECTION_REPLACED:
            return


@router.get("/status")
async def desktop_relay_status(user: Annotated[User, Depends(get_current_user)]) -> dict[str, Any]:
    """Whether the user's desktop app is connected and can run desktop-only actions."""
    return get_desktop_relay_hub().agent_status(int(user.id))


@router.get("/agent/stream")
async def desktop_agent_stream(
    raw_token: Annotated[str, Depends(get_bearer_or_query_token)],
    app_version: Annotated[str | None, Query(max_length=40)] = None,
) -> StreamingResponse:
    """SSE opened by the desktop app: the commands sent from the user's other devices arrive here."""
    user_id = await run_in_threadpool(_approved_user_id_from_token, raw_token)
    hub = get_desktop_relay_hub()

    async def generate() -> AsyncIterator[str]:
        agent = hub.attach_agent(user_id, app_version)
        logger.info("desktop-relay: desktop app connected (user=%s, version=%s)", user_id, app_version)
        try:
            async for chunk in _iter_sse(agent.queue):
                yield chunk
        finally:
            hub.detach_agent(user_id, agent)
            logger.info("desktop-relay: desktop app disconnected (user=%s)", user_id)

    return StreamingResponse(generate(), media_type="text/event-stream", headers=_SSE_HEADERS)


@router.post("/agent/responses")
async def desktop_agent_response(
    payload: DesktopRelayResponseIn,
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, bool]:
    """Response of a worker HTTP call run by the desktop app."""
    response = payload.model_dump(exclude={"request_id"})
    delivered = get_desktop_relay_hub().complete_request(int(user.id), payload.request_id, response)
    return {"delivered": delivered}


@router.post("/agent/stream-events")
async def desktop_agent_stream_events(
    payload: DesktopRelayStreamEventsIn,
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, bool]:
    """Worker progress events read by the desktop app; ``delivered: false`` means the web client left."""
    events = [event.model_dump(exclude_none=True) for event in payload.events]
    delivered = get_desktop_relay_hub().push_stream_events(int(user.id), payload.stream_id, events)
    return {"delivered": delivered}


@router.post("/agent/stream-end")
async def desktop_agent_stream_end(
    payload: DesktopRelayStreamEndIn,
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, bool]:
    """The worker progress stream closed on the desktop side."""
    delivered = get_desktop_relay_hub().end_stream(int(user.id), payload.stream_id, payload.error)
    return {"delivered": delivered}


@router.get("/client/stream")
async def desktop_relay_client_stream(
    raw_token: Annotated[str, Depends(get_bearer_or_query_token)],
    client_id: Annotated[str, Query(min_length=8, max_length=64)],
) -> StreamingResponse:
    """SSE opened by a web client: responses, stream events and desktop presence changes."""
    user_id = await run_in_threadpool(_approved_user_id_from_token, raw_token)
    hub = get_desktop_relay_hub()

    async def generate() -> AsyncIterator[str]:
        client = hub.attach_client(user_id, client_id)
        queue = client.queue
        try:
            async for chunk in _iter_sse(queue, first_events=[{"type": "agent-status", **hub.agent_status(user_id)}]):
                yield chunk
        finally:
            hub.detach_client(client_id, queue)

    return StreamingResponse(generate(), media_type="text/event-stream", headers=_SSE_HEADERS)


@router.post("/requests", status_code=status.HTTP_202_ACCEPTED)
async def desktop_relay_request(
    payload: DesktopRelayRequestIn,
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, str]:
    """Send one worker HTTP call to the desktop app; the response arrives on the client stream."""
    command = payload.model_dump(exclude={"client_id"})
    try:
        request_id = get_desktop_relay_hub().submit_request(int(user.id), payload.client_id, command)
    except DesktopAgentOfflineError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="desktop_offline") from None
    except UnknownRelayClientError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="relay_client_unknown") from None
    return {"request_id": request_id}


@router.post("/streams", status_code=status.HTTP_202_ACCEPTED)
async def desktop_relay_open_stream(
    payload: DesktopRelayStreamIn,
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, str]:
    """Ask the desktop app to follow a worker progress stream; its events arrive on the client stream."""
    command = payload.model_dump(exclude={"client_id"})
    try:
        stream_id = get_desktop_relay_hub().open_stream(int(user.id), payload.client_id, command)
    except DesktopAgentOfflineError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="desktop_offline") from None
    except UnknownRelayClientError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="relay_client_unknown") from None
    return {"stream_id": stream_id}


@router.delete("/streams/{stream_id}", status_code=status.HTTP_204_NO_CONTENT)
async def desktop_relay_close_stream(
    stream_id: str,
    client_id: Annotated[str, Query(min_length=8, max_length=64)],
    user: Annotated[User, Depends(get_current_user)],
) -> Response:
    """Stop following a worker stream (the desktop app closes it)."""
    get_desktop_relay_hub().close_stream(int(user.id), client_id, stream_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
