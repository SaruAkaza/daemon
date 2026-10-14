from __future__ import annotations

import json
import os
from pathlib import Path
import threading
from typing import Any

from scripts.agents.canonical_json import canonical_json_bytes, sha256_bytes

GENESIS_PREV_HASH = "0" * 64


class IntegrityError(RuntimeError):
    """Raised when an append-only log has been tampered with or corrupted."""
    pass


class HashChainLogger:
    """Manages append-only JSONL logs protected by a SHA-256 integrity hash chain."""

    def __init__(self, log_path: Path | str) -> None:
        self.log_path = Path(log_path).resolve()
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.verify_on_startup()

    def verify_on_startup(self) -> None:
        """Verifies full log integrity on startup fail-closed."""
        with self._lock:
            if self.log_path.is_file() and self.log_path.stat().st_size > 0:
                valid, line_no, err = self.verify_integrity()
                if not valid:
                    raise IntegrityError(
                        f"Log integrity check failed for '{self.log_path.name}' at line {line_no}: {err}"
                    )

    def _get_last_entry_hash(self) -> str:
        if not self.log_path.is_file():
            return GENESIS_PREV_HASH
        with open(self.log_path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
        if not lines:
            return GENESIS_PREV_HASH
        last_obj = json.loads(lines[-1])
        return str(last_obj.get("entryHash", GENESIS_PREV_HASH))

    def append_entry(self, record: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            if self.log_path.is_file() and self.log_path.stat().st_size > 0:
                valid, line_no, err = self.verify_integrity()
                if not valid:
                    raise IntegrityError(
                        f"Refusing to append to corrupted hash chain '{self.log_path.name}' at line {line_no}: {err}"
                    )
            prev_hash = self._get_last_entry_hash()
            rec = dict(record)
            rec["prevHash"] = prev_hash
            rec.pop("entryHash", None)
            entry_hash = sha256_bytes(canonical_json_bytes(rec))
            rec["entryHash"] = entry_hash

            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, separators=(",", ":"), ensure_ascii=False) + "\n")
                f.flush()
                try:
                    os.fsync(f.fileno())
                except OSError:
                    pass

            return rec

    def verify_integrity(self) -> tuple[bool, int, str]:
        with self._lock:
            if not self.log_path.is_file():
                return True, 0, ""

            with open(self.log_path, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]

            expected_prev = GENESIS_PREV_HASH
            for idx, line in enumerate(lines, 1):
                try:
                    entry = json.loads(line)
                except Exception as e:
                    return False, idx, f"Invalid JSON on line {idx}: {e}"

                if not isinstance(entry, dict):
                    return False, idx, f"Non-object entry on line {idx}"

                stored_prev = entry.get("prevHash")
                if stored_prev != expected_prev:
                    return False, idx, f"prevHash mismatch on line {idx}: expected {expected_prev}, got {stored_prev}"

                stored_hash = entry.get("entryHash")
                entry_copy = dict(entry)
                entry_copy.pop("entryHash", None)
                computed_hash = sha256_bytes(canonical_json_bytes(entry_copy))

                if computed_hash != stored_hash:
                    return False, idx, f"Hash mismatch on line {idx}: computed {computed_hash} != stored {stored_hash}"

                expected_prev = stored_hash

            return True, len(lines), ""

    def read_all_entries(self) -> list[dict[str, Any]]:
        valid, line_no, err = self.verify_integrity()
        if not valid:
            raise IntegrityError(f"Hash chain integrity verification failed at line {line_no}: {err}")

        if not self.log_path.is_file():
            return []

        entries = []
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                line_str = line.strip()
                if line_str:
                    entries.append(json.loads(line_str))
        return entries
