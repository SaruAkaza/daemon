from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Iterator
import urllib.parse

from scripts.agents.canonical_json import canonical_json_bytes
from scripts.ops.command_processor import CommandProcessor, RiskValidationError
from scripts.ops.command_store import CommandConflictError
from scripts.ops.event_broadcaster import EventBroadcaster
from scripts.ops.token_manager import TokenManager

MAX_PAYLOAD_SIZE = 64 * 1024  # 64 KB limit
LOOPBACK_ADDRESSES = {"127.0.0.1", "::1", "localhost"}


class OpsRequestHandler:
    """Secure request handler for Daemon Tools operational control plane."""

    def __init__(
        self,
        token_manager: TokenManager,
        command_processor: CommandProcessor,
        broadcaster: EventBroadcaster,
        allowed_hosts: set[str] | None = None,
    ) -> None:
        self.token_manager = token_manager
        self.command_processor = command_processor
        self.broadcaster = broadcaster
        self.allowed_hosts = {h.lower() for h in allowed_hosts} if allowed_hosts is not None else {"127.0.0.1", "localhost"}

    def handle_request(
        self,
        method: str,
        path: str,
        headers: dict[str, str],
        client_address: tuple[str, int],
        body: bytes,
    ) -> tuple[int, dict[str, str], bytes | Iterator[bytes]]:
        # Normalize header keys to lowercase
        norm_headers = {k.lower(): v for k, v in headers.items()}

        # 1. Loopback check
        client_ip = client_address[0]
        if client_ip not in LOOPBACK_ADDRESSES:
            return 403, {"Content-Type": "application/json; charset=utf-8"}, b'{"error":"Forbidden: non-loopback access denied"}'

        # 2. Host header verification (DNS rebinding prevention)
        host_hdr = norm_headers.get("host", "").split(":")[0].strip().lower()
        if not host_hdr or host_hdr not in self.allowed_hosts:
            return 403, {"Content-Type": "application/json; charset=utf-8"}, b'{"error":"Forbidden: invalid Host header"}'

        # 3. Origin header verification (if present)
        origin_hdr = norm_headers.get("origin")
        if origin_hdr:
            parsed = urllib.parse.urlparse(origin_hdr)
            origin_host = (parsed.hostname or "").lower()
            if origin_host not in self.allowed_hosts:
                return 403, {"Content-Type": "application/json; charset=utf-8"}, b'{"error":"Forbidden: invalid Origin header"}'

        # 4. Request body size check
        if len(body) > MAX_PAYLOAD_SIZE:
            return 413, {"Content-Type": "application/json; charset=utf-8"}, b'{"error":"Payload Too Large: maximum body size is 64KB"}'

        # 5. Authentication check (same-origin session cookie or Bearer token)
        cookie_hdr = norm_headers.get("cookie")
        auth_hdr = norm_headers.get("authorization")
        if not self.token_manager.validate_session(cookie_hdr, auth_hdr):
            return 401, {"Content-Type": "application/json; charset=utf-8"}, b'{"error":"Unauthorized: valid session cookie or Bearer token required"}'

        # 6. Route dispatching
        clean_path = urllib.parse.urlparse(path).path.rstrip("/")
        if clean_path == "/api/ops/snapshot" and method == "GET":
            return self._handle_snapshot()
        elif clean_path == "/api/ops/commands" and method == "GET":
            return self._handle_get_commands()
        elif clean_path == "/api/ops/commands" and method == "POST":
            return self._handle_post_command(body)
        elif clean_path == "/api/ops/reviews" and method == "GET":
            return self._handle_get_reviews()
        elif clean_path == "/api/ops/events" and method == "GET":
            return self._handle_events(norm_headers)
        else:
            return 404, {"Content-Type": "application/json; charset=utf-8"}, b'{"error":"Not Found"}'

    def _handle_snapshot(self) -> tuple[int, dict[str, str], bytes]:
        ctrl_state = self.command_processor.command_store.get_control_state()
        cmds = self.command_processor.command_store.list_commands()
        reviews = (
            self.command_processor.review_store.list_reviews()
            if self.command_processor.review_store
            else []
        )
        snapshot = {
            "controlState": ctrl_state,
            "commands": cmds,
            "reviews": reviews,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return 200, {"Content-Type": "application/json; charset=utf-8"}, canonical_json_bytes(snapshot)

    def _handle_get_commands(self) -> tuple[int, dict[str, str], bytes]:
        cmds = self.command_processor.command_store.list_commands()
        return 200, {"Content-Type": "application/json; charset=utf-8"}, canonical_json_bytes({"commands": cmds})

    def _handle_get_reviews(self) -> tuple[int, dict[str, str], bytes]:
        reviews = (
            self.command_processor.review_store.list_reviews()
            if self.command_processor.review_store
            else []
        )
        return 200, {"Content-Type": "application/json; charset=utf-8"}, canonical_json_bytes({"reviews": reviews})

    def _handle_post_command(self, body: bytes) -> tuple[int, dict[str, str], bytes]:
        try:
            cmd_data = json.loads(body.decode("utf-8"))
            if not isinstance(cmd_data, dict):
                return 400, {"Content-Type": "application/json; charset=utf-8"}, b'{"error":"Command payload must be a JSON object"}'
        except Exception as e:
            return 400, {"Content-Type": "application/json; charset=utf-8"}, canonical_json_bytes({"error": f"Invalid JSON: {e}"})

        try:
            record, status_code = self.command_processor.submit_command(cmd_data)
            self.broadcaster.publish_event("command_updated", record)
            return status_code, {"Content-Type": "application/json; charset=utf-8"}, canonical_json_bytes(record)
        except CommandConflictError as e:
            return 409, {"Content-Type": "application/json; charset=utf-8"}, canonical_json_bytes({"error": str(e)})
        except (RiskValidationError, ValueError) as e:
            return 400, {"Content-Type": "application/json; charset=utf-8"}, canonical_json_bytes({"error": str(e)})
        except Exception as e:
            return 500, {"Content-Type": "application/json; charset=utf-8"}, canonical_json_bytes({"error": f"Internal server error: {e}"})

    def _handle_events(self, headers: dict[str, str]) -> tuple[int, dict[str, str], bytes]:
        last_id_str = headers.get("last-event-id", "0")
        try:
            last_id = int(last_id_str)
        except ValueError:
            last_id = 0

        events, needs_snapshot = self.broadcaster.get_events_since(last_id)
        frames: list[str] = []
        if needs_snapshot:
            frames.append(self.broadcaster.format_sse_message(0, "snapshot_required", {"needsSnapshot": True}))

        for ev in events:
            frames.append(self.broadcaster.format_sse_message(ev["id"], ev["type"], ev["data"]))

        if not frames:
            frames.append(self.broadcaster.format_keepalive())

        resp_body = "".join(frames).encode("utf-8")
        return 200, {
            "Content-Type": "text/event-stream; charset=utf-8",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }, resp_body
