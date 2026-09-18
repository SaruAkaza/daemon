from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import threading
from typing import Any

from scripts.agents.canonical_json import canonical_json_bytes, sha256_bytes
from scripts.agents.contracts import write_atomic
from scripts.ops.runtime_locator import get_ops_stores_dir


class CommandConflictError(RuntimeError):
    """Raised when a commandId has already been submitted with a different payload."""
    pass


class CommandStore:
    """Durable store for operational commands with strong idempotency and control state."""

    def __init__(self, stores_dir: Path | str | None = None) -> None:
        self.stores_dir = Path(stores_dir).resolve() if stores_dir else get_ops_stores_dir()
        self.stores_dir.mkdir(parents=True, exist_ok=True)
        self.commands_file = self.stores_dir / "commands.json"
        self.control_state_file = self.stores_dir / "control_state.json"
        self._lock = threading.RLock()
        self._ensure_files()
        self._recover_running_commands()

    def _ensure_files(self) -> None:
        if not self.commands_file.exists():
            write_atomic(self.commands_file, canonical_json_bytes({"commands": {}}))
        if not self.control_state_file.exists():
            write_atomic(
                self.control_state_file,
                canonical_json_bytes({
                    "pauseRequests": [],
                    "pausedBooks": [],
                    "priorityOverrides": {},
                    "reprocessIntents": {},
                    "dequeueRequests": [],
                }),
            )

    def _recover_running_commands(self) -> None:
        """Recovers any interrupted RUNNING commands on startup, reclassifying to ACCEPTED."""
        with self._lock:
            commands = self._load_commands()
            dirty = False
            for cid, cmd in commands.items():
                if cmd.get("status") == "RUNNING":
                    cmd["status"] = "ACCEPTED"
                    cmd["recoveredAt"] = datetime.now(timezone.utc).isoformat()
                    cmd["recoveryNote"] = "Execution interrupted by server restart; reset to ACCEPTED"
                    dirty = True
            if dirty:
                self._save_commands(commands)

    def _load_commands(self) -> dict[str, Any]:
        if not self.commands_file.exists():
            return {}
        with open(self.commands_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("commands", {})

    def _save_commands(self, commands: dict[str, Any]) -> None:
        write_atomic(self.commands_file, canonical_json_bytes({"commands": commands}))

    def get_control_state(self) -> dict[str, Any]:
        with self._lock:
            if not self.control_state_file.exists():
                return {"pausedBooks": [], "priorityOverrides": {}, "reprocessIntents": {}}
            with open(self.control_state_file, "r", encoding="utf-8") as f:
                return json.load(f)

    def _save_control_state(self, state: dict[str, Any]) -> None:
        write_atomic(self.control_state_file, canonical_json_bytes(state))

    def set_control_override(self, key: str, value: Any) -> None:
        with self._lock:
            state = self.get_control_state()
            state[key] = value
            self._save_control_state(state)

    def _compute_payload_hash(self, cmd_payload: dict[str, Any]) -> str:
        canonical_dict = {
            "commandType": cmd_payload.get("commandType"),
            "bookId": cmd_payload.get("bookId"),
            "reviewId": cmd_payload.get("reviewId"),
            "payload": cmd_payload.get("payload", {}),
            "reason": cmd_payload.get("reason", ""),
            "operatorId": cmd_payload.get("operatorId"),
            "confirmation": cmd_payload.get("confirmation", {}),
        }
        return sha256_bytes(canonical_json_bytes(canonical_dict))

    def save_command_intent(self, cmd_payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        cid = cmd_payload.get("commandId")
        if not cid:
            raise ValueError("Command requires a non-empty 'commandId'")
        payload_hash = self._compute_payload_hash(cmd_payload)

        with self._lock:
            commands = self._load_commands()
            if cid in commands:
                existing = commands[cid]
                if existing.get("payloadHash") == payload_hash:
                    return existing, True
                else:
                    raise CommandConflictError(
                        f"Command '{cid}' already exists with a different payload (conflict)."
                    )

            record = {
                "commandId": cid,
                "commandType": cmd_payload.get("commandType"),
                "bookId": cmd_payload.get("bookId"),
                "reviewId": cmd_payload.get("reviewId"),
                "payload": cmd_payload.get("payload", {}),
                "reason": cmd_payload.get("reason", ""),
                "operatorId": cmd_payload.get("operatorId"),
                "confirmation": cmd_payload.get("confirmation", {}),
                "payloadHash": payload_hash,
                "status": "ACCEPTED",
                "submittedAt": cmd_payload.get("submittedAt") or datetime.now(timezone.utc).isoformat(),
                "updatedAt": datetime.now(timezone.utc).isoformat(),
                "result": None,
                "error": None,
            }
            commands[cid] = record
            self._save_commands(commands)
            return record, False

    def update_command_status(
        self,
        command_id: str,
        status: str,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            commands = self._load_commands()
            if command_id not in commands:
                raise KeyError(f"Command '{command_id}' not found")
            rec = commands[command_id]
            rec["status"] = status
            rec["updatedAt"] = datetime.now(timezone.utc).isoformat()
            if result is not None:
                rec["result"] = result
            if error is not None:
                rec["error"] = error
            self._save_commands(commands)
            return rec

    def get_command(self, command_id: str) -> dict[str, Any] | None:
        with self._lock:
            commands = self._load_commands()
            return commands.get(command_id)

    def list_commands(self) -> list[dict[str, Any]]:
        with self._lock:
            commands = self._load_commands()
            return list(commands.values())
