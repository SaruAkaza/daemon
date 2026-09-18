import json
import pytest

from scripts.ops.event_broadcaster import EventBroadcaster


def test_monotonic_event_ids_across_publishes():
    broadcaster = EventBroadcaster(buffer_size=100)
    id1 = broadcaster.publish_event("review_created", {"reviewId": "REV-01"})
    id2 = broadcaster.publish_event("command_submitted", {"commandId": "CMD-01"})
    id3 = broadcaster.publish_event("stage_completed", {"bookId": "trevas-3ed"})

    assert id1 == 1
    assert id2 == 2
    assert id3 == 3


def test_replay_via_last_event_id_within_buffer():
    broadcaster = EventBroadcaster(buffer_size=100)
    for i in range(1, 11):
        broadcaster.publish_event("tick", {"count": i})

    # Replay events since id=7 -> should return events 8, 9, 10
    events, needs_snapshot = broadcaster.get_events_since(7)
    assert not needs_snapshot
    assert len(events) == 3
    assert [e["id"] for e in events] == [8, 9, 10]
    assert events[0]["data"]["count"] == 8


def test_snapshot_fallback_when_events_evicted_from_ring_buffer():
    broadcaster = EventBroadcaster(buffer_size=5)
    # Publish 10 events (1..10). Buffer will only retain 6..10.
    for i in range(1, 11):
        broadcaster.publish_event("tick", {"count": i})

    # Client asks for events since 5: oldest is 6, so client was at 5 and has not missed any event
    events, needs_snapshot = broadcaster.get_events_since(5)
    assert not needs_snapshot
    assert [e["id"] for e in events] == [6, 7, 8, 9, 10]

    # Client asks for events since 4: event 5 was dropped, so replay is incomplete
    events, needs_snapshot = broadcaster.get_events_since(4)
    assert needs_snapshot
    assert events == []


def test_snapshot_fallback_on_server_restart():
    broadcaster = EventBroadcaster(buffer_size=100)
    # Server is fresh/restarted (no events published yet)
    # Client reconnects with last_event_id=55 from a previous server session
    events, needs_snapshot = broadcaster.get_events_since(55)
    assert needs_snapshot
    assert events == []

    # If server has published fewer events (e.g. up to 10), client sends 55
    for i in range(1, 11):
        broadcaster.publish_event("tick", {"count": i})
    events, needs_snapshot = broadcaster.get_events_since(55)
    assert needs_snapshot
    assert events == []


def test_format_sse_message():
    broadcaster = EventBroadcaster()
    msg = broadcaster.format_sse_message(42, "command_status", {"status": "SUCCEEDED"})
    expected = "id: 42\nevent: command_status\ndata: {\"status\":\"SUCCEEDED\"}\n\n"
    assert msg == expected


def test_format_keepalive():
    broadcaster = EventBroadcaster()
    msg = broadcaster.format_keepalive()
    assert msg == ": keepalive\n\n"


def test_sensitive_tokens_scrubbed_from_events():
    broadcaster = EventBroadcaster()
    broadcaster.publish_event("auth_event", {
        "operator": "alice",
        "token": "secret-token-value-12345",
        "nested": {"sessionToken": "abc-xyz", "safe": "visible"},
    })

    events, _ = broadcaster.get_events_since(0)
    assert len(events) == 1
    data = events[0]["data"]
    assert data["token"] == "[REDACTED]"
    assert data["nested"]["sessionToken"] == "[REDACTED]"
    assert data["nested"]["safe"] == "visible"

    formatted = broadcaster.format_sse_message(1, "auth_event", data)
    assert "secret-token-value-12345" not in formatted
    assert "[REDACTED]" in formatted
