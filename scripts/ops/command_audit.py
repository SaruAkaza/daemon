from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.ops.hash_chain import HashChainLogger
from scripts.ops.runtime_locator import get_ops_stores_dir

SENSITIVE_KEYS = {"token", "session", "cookie", "password", "secret", "authorization"}


def scrub_sensitive_data(obj: Any) -> Any:
    """Recursively scrub any sensitive authentication values from audit payload."""
    if isinstance(obj, dict):
        cleaned = {}
        for k, v in obj.items():
            if any(s in k.lower() for s in SENSITIVE_KEYS):
                cleaned[k] = "[REDACTED]"
            else:
                cleaned[k] = scrub_sensitive_data(v)
        return cleaned
    elif isinstance(obj, list):
        return [scrub_sensitive_data(item) for item in obj]
    return obj


class CommandAuditLog:
    """Append-only audit log for operational commands protected by SHA-256 hash chaining."""

    def __init__(self, stores_dir: Path | str | None = None) -> None:
        self.stores_dir = Path(stores_dir).resolve() if stores_dir else get_ops_stores_dir()
        self.stores_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.stores_dir / "command_audit.jsonl"
        self.logger = HashChainLogger(self.log_file)

    def log_action(self, entry: dict[str, Any]) -> dict[str, Any]:
        rec = dict(entry)
        rec.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        cleaned_rec = scrub_sensitive_data(rec)
        return self.logger.append_entry(cleaned_rec)

    def verify_audit_chain(self) -> bool:
        valid, _, _ = self.logger.verify_integrity()
        return valid

    def read_all_actions(self) -> list[dict[str, Any]]:
        return self.logger.read_all_entries()
