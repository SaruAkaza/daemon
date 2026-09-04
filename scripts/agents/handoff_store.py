from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

from scripts.agents.contracts import (
    ContractValidationError,
    load_json,
    validate_payload,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_HANDOFFS_DIR = (ROOT / "coordination" / "handoffs").resolve()


class HandoffStoreError(RuntimeError):
    """Base exception for HandoffStore operational and storage errors."""
    pass


class HandoffAlreadyExistsError(HandoffStoreError):
    """Raised when attempting to create a handoff with an ID that already exists."""
    pass


class HandoffNotFoundError(HandoffStoreError):
    """Raised when an operation references a handoff ID that does not exist."""
    pass


class HandoffStore:
    """Persistent storage for immutable Agent Handoff records."""

    def __init__(self, root: Path | str | None = None) -> None:
        if root is None:
            self.root = DEFAULT_HANDOFFS_DIR
        else:
            self.root = Path(root).resolve()

        self.root.mkdir(parents=True, exist_ok=True)

    def _handoff_path(self, handoff_id: str) -> Path:
        """Resolve handoff_id to a safe Path within the handoffs directory.

        Raises:
            HandoffStoreError: If path traversal is attempted or handoff_id is invalid.
        """
        if not isinstance(handoff_id, str) or not handoff_id.strip():
            raise HandoffStoreError("handoff_id must be a non-empty string.")

        if ".." in handoff_id or "/" in handoff_id or "\\" in handoff_id or ":" in handoff_id:
            raise HandoffStoreError(f"Invalid handoff_id or path traversal attempt: {handoff_id}")

        filename = f"{handoff_id}.json"
        target = (self.root / filename).resolve()

        try:
            target.relative_to(self.root.resolve())
        except ValueError:
            raise HandoffStoreError(f"Path traversal detected for handoff_id: {handoff_id}")

        return target

    def _atomic_write(self, target_path: Path, data: dict[str, Any]) -> None:
        """Serialize data to JSON and write atomically to disk."""
        tmp_path = target_path.with_name(f"{target_path.name}.{os.getpid()}.tmp")
        raw = json.dumps(data, indent=2, ensure_ascii=False) + "\n"

        try:
            tmp_path.write_text(raw, encoding="utf-8")
            os.replace(tmp_path, target_path)
        except Exception as e:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass
            raise HandoffStoreError(f"Failed to persist handoff file at {target_path}: {e}") from e

    def create(self, payload: dict[str, Any]) -> Path:
        """Validate and persist an immutable Agent Handoff record.

        Raises:
            ContractValidationError: If payload fails schema validation or is not a dict.
            HandoffAlreadyExistsError: If a handoff with this ID already exists.
            HandoffStoreError: If I/O or filesystem persistence fails.
        """
        validate_payload("agent-handoff", payload)

        handoff_id = payload["handoffId"]
        target_path = self._handoff_path(handoff_id)
        if target_path.exists():
            raise HandoffAlreadyExistsError(
                f"Handoff '{handoff_id}' already exists at {target_path}"
            )

        safe_copy = copy.deepcopy(payload)
        self._atomic_write(target_path, safe_copy)
        return target_path

    def load(self, handoff_id: str) -> dict[str, Any]:
        """Load and revalidate a persisted Agent Handoff record from disk.

        Raises:
            HandoffNotFoundError: If the handoff file does not exist.
            ContractValidationError: If stored JSON is malformed or violates schema.
            HandoffStoreError: If path is unsafe or I/O fails.
        """
        target_path = self._handoff_path(handoff_id)
        if not target_path.is_file():
            raise HandoffNotFoundError(f"Handoff '{handoff_id}' not found at {target_path}")

        data = load_json(target_path)
        validate_payload("agent-handoff", data)

        return copy.deepcopy(data)

    def list_handoff_ids(self) -> list[str]:
        """Return a sorted list of all persisted handoff IDs."""
        if not self.root.is_dir():
            return []

        handoff_ids = []
        for path in self.root.iterdir():
            if path.is_file() and path.suffix == ".json" and not path.name.endswith(".tmp"):
                handoff_ids.append(path.stem)

        return sorted(handoff_ids)
