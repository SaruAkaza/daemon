from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import json
import threading
from typing import Any

import queue

from scripts.ops.command_audit import scrub_sensitive_data


class EventBroadcaster:
    """Thread-safe Server-Sent Events (SSE) broadcaster with ring buffer replay and snapshot fallback."""

    def __init__(self, buffer_size: int = 100) -> None:
        self.buffer_size = buffer_size
        self._buffer: deque[dict[str, Any]] = deque(maxlen=buffer_size)
        self._current_id = 0
        self._lock = threading.RLock()
        self._subscribers: list[queue.Queue[dict[str, Any]]] = []

    def subscribe(self) -> queue.Queue[dict[str, Any]]:
        q: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=200)
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: queue.Queue[dict[str, Any]]) -> None:
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    def publish_event(self, event_type: str, data: dict[str, Any]) -> int:
        """Publish a new event into the circular buffer with a strictly monotonic ID."""
        with self._lock:
            self._current_id += 1
            event_id = self._current_id
            cleaned_data = scrub_sensitive_data(data)
            entry = {
                "id": event_id,
                "type": event_type,
                "data": cleaned_data,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            self._buffer.append(entry)
            for q in list(self._subscribers):
                try:
                    q.put_nowait(entry)
                except queue.Full:
                    pass
            return event_id

    def get_events_since(self, last_event_id: int) -> tuple[list[dict[str, Any]], bool]:
        """Replay events occurring after `last_event_id`.
        
        Returns:
            (events, needs_snapshot)
            needs_snapshot is True if last_event_id was evicted from the ring buffer
            or if the client event ID is newer than server state (e.g. server restarted).
        """
        with self._lock:
            if not self._buffer:
                if last_event_id > 0:
                    return [], True
                return [], False

            oldest_id = self._buffer[0]["id"]
            newest_id = self._buffer[-1]["id"]

            # If client's last_event_id is higher than our latest event,
            # the server likely restarted and reset its sequence.
            if last_event_id > newest_id:
                return [], True

            # If client missed events that have already been evicted from the ring buffer
            # (e.g. oldest retained is 6, client was at 4 -> event 5 is lost)
            if last_event_id < oldest_id - 1:
                return [], True

            events = [e for e in self._buffer if e["id"] > last_event_id]
            return events, False

    def format_sse_message(self, event_id: int, event_type: str, data: dict[str, Any]) -> str:
        """Format an event according to the W3C Server-Sent Events wire standard."""
        cleaned_data = scrub_sensitive_data(data)
        payload_str = json.dumps(cleaned_data, separators=(",", ":"))
        return f"id: {event_id}\nevent: {event_type}\ndata: {payload_str}\n\n"

    def format_keepalive(self) -> str:
        """Format SSE keepalive comment frame to prevent proxy/browser timeouts."""
        return ": keepalive\n\n"
