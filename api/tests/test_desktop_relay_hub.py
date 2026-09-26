import asyncio

import pytest

from services.desktop_relay_hub import (
    CONNECTION_REPLACED,
    DesktopAgentOfflineError,
    DesktopRelayHub,
    UnknownRelayClientError,
)

USER_ID = 1
OTHER_USER_ID = 2
CLIENT_ID = "ipad-client-0001"
VINTED_HEALTH = {"worker": "vinted", "method": "GET", "path": "/health"}


def drain(queue: asyncio.Queue) -> list[dict]:
    events = []
    while not queue.empty():
        events.append(queue.get_nowait())
    return events


def test_request_needs_a_connected_desktop() -> None:
    hub = DesktopRelayHub()
    hub.attach_client(USER_ID, CLIENT_ID)
    with pytest.raises(DesktopAgentOfflineError):
        hub.submit_request(USER_ID, CLIENT_ID, VINTED_HEALTH)


def test_request_round_trip_reaches_the_asking_client() -> None:
    hub = DesktopRelayHub()
    agent = hub.attach_agent(USER_ID, "0.1.0")
    client = hub.attach_client(USER_ID, CLIENT_ID)

    request_id = hub.submit_request(USER_ID, CLIENT_ID, VINTED_HEALTH)
    forwarded = drain(agent.queue)
    assert forwarded == [{"type": "request", "id": request_id, **VINTED_HEALTH}]

    assert hub.complete_request(USER_ID, request_id, {"status": 200, "data": {"status": "ok"}})
    assert drain(client.queue) == [{"type": "response", "id": request_id, "status": 200, "data": {"status": "ok"}}]
    assert not hub.complete_request(USER_ID, request_id, {"status": 200})


def test_another_user_cannot_use_or_answer_the_relay() -> None:
    hub = DesktopRelayHub()
    hub.attach_agent(USER_ID, None)
    hub.attach_client(USER_ID, CLIENT_ID)
    request_id = hub.submit_request(USER_ID, CLIENT_ID, VINTED_HEALTH)

    with pytest.raises(DesktopAgentOfflineError):
        hub.submit_request(OTHER_USER_ID, CLIENT_ID, VINTED_HEALTH)
    hub.attach_agent(OTHER_USER_ID, None)
    with pytest.raises(UnknownRelayClientError):
        hub.submit_request(OTHER_USER_ID, CLIENT_ID, VINTED_HEALTH)
    assert not hub.complete_request(OTHER_USER_ID, request_id, {"status": 200})


def test_desktop_disconnect_fails_pending_work_and_reports_offline() -> None:
    hub = DesktopRelayHub()
    agent = hub.attach_agent(USER_ID, None)
    client = hub.attach_client(USER_ID, CLIENT_ID)
    request_id = hub.submit_request(USER_ID, CLIENT_ID, VINTED_HEALTH)
    stream_id = hub.open_stream(USER_ID, CLIENT_ID, {"worker": "amazon", "kind": "ws", "path": "/ws/progress"})

    hub.detach_agent(USER_ID, agent)

    events = drain(client.queue)
    assert {"type": "response", "id": request_id, "status": 503, "error": "desktop_disconnected"} in events
    assert {"type": "stream-end", "id": stream_id, "error": "desktop_disconnected"} in events
    assert events[-1] == {"type": "agent-status", "online": False}
    assert hub.agent_status(USER_ID) == {"online": False}


def test_newer_desktop_connection_replaces_the_previous_one() -> None:
    hub = DesktopRelayHub()
    first = hub.attach_agent(USER_ID, "0.1.0")
    second = hub.attach_agent(USER_ID, "0.1.1")

    assert drain(first.queue) == [CONNECTION_REPLACED]
    hub.detach_agent(USER_ID, first)
    assert hub.agent_status(USER_ID)["app_version"] == "0.1.1"
    hub.detach_agent(USER_ID, second)
    assert hub.agent_status(USER_ID) == {"online": False}


def test_reconnecting_client_keeps_buffered_events() -> None:
    hub = DesktopRelayHub()
    hub.attach_agent(USER_ID, None)
    first = hub.attach_client(USER_ID, CLIENT_ID)
    first_queue = first.queue
    request_id = hub.submit_request(USER_ID, CLIENT_ID, VINTED_HEALTH)
    hub.detach_client(CLIENT_ID, first_queue)
    hub.complete_request(USER_ID, request_id, {"status": 200})

    reconnected = hub.attach_client(USER_ID, CLIENT_ID)

    assert drain(first_queue) == [CONNECTION_REPLACED]
    assert drain(reconnected.queue) == [{"type": "response", "id": request_id, "status": 200}]


def test_client_close_stops_the_desktop_stream() -> None:
    hub = DesktopRelayHub()
    agent = hub.attach_agent(USER_ID, None)
    hub.attach_client(USER_ID, CLIENT_ID)
    stream_id = hub.open_stream(USER_ID, CLIENT_ID, {"worker": "vinted", "kind": "sse", "path": "/articles/1/listing-progress"})
    drain(agent.queue)

    assert hub.close_stream(USER_ID, CLIENT_ID, stream_id)
    assert drain(agent.queue) == [{"type": "stream-close", "id": stream_id}]
    assert not hub.push_stream_events(USER_ID, stream_id, [{"data": "{}"}])
