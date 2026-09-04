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
DEFAULT_JOBS_DIR = (ROOT / "coordination" / "jobs").resolve()


class JobStoreError(RuntimeError):
    """Base exception for JobStore operational and storage errors."""
    pass


class JobAlreadyExistsError(JobStoreError):
    """Raised when attempting to create a job with an ID that already exists."""
    pass


class JobNotFoundError(JobStoreError):
    """Raised when an operation references a job ID that does not exist."""
    pass


class JobStore:
    """Persistent storage and lifecycle management for Agent Jobs."""

    def __init__(self, root: Path | str | None = None) -> None:
        if root is None:
            self.root = DEFAULT_JOBS_DIR
        else:
            self.root = Path(root).resolve()

        self.root.mkdir(parents=True, exist_ok=True)

    def _job_path(self, job_id: str) -> Path:
        """Resolve job_id to a safe Path within the jobs directory.

        Raises:
            JobStoreError: If path traversal is attempted or job_id is invalid.
        """
        if not isinstance(job_id, str) or not job_id.strip():
            raise JobStoreError("job_id must be a non-empty string.")

        if ".." in job_id or "/" in job_id or "\\" in job_id:
            raise JobStoreError(f"Invalid job_id or path traversal attempt: {job_id}")

        filename = f"{job_id}.json"
        target = (self.root / filename).resolve()

        try:
            target.relative_to(self.root.resolve())
        except ValueError:
            raise JobStoreError(f"Path traversal detected for job_id: {job_id}")

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
            raise JobStoreError(f"Failed to persist job file at {target_path}: {e}") from e

    def create(self, job_data: dict[str, Any]) -> dict[str, Any]:
        """Validate and create a new persistent Job.

        Raises:
            ContractValidationError: If job_data fails schema validation or is not a dict.
            JobAlreadyExistsError: If a job with this ID already exists.
            JobStoreError: If I/O or filesystem persistence fails.
        """
        validate_payload("agent-job", job_data)

        job_id = job_data["jobId"]
        target_path = self._job_path(job_id)
        if target_path.exists():
            raise JobAlreadyExistsError(f"Job '{job_id}' already exists at {target_path}")

        safe_copy = copy.deepcopy(job_data)
        self._atomic_write(target_path, safe_copy)
        return copy.deepcopy(safe_copy)

    def load(self, job_id: str) -> dict[str, Any]:
        """Load and revalidate a persisted Job from disk.

        Raises:
            JobNotFoundError: If the job file does not exist.
            ContractValidationError: If stored JSON is malformed or violates schema.
            JobStoreError: If path is unsafe or I/O fails.
        """
        target_path = self._job_path(job_id)
        if not target_path.is_file():
            raise JobNotFoundError(f"Job '{job_id}' not found at {target_path}")

        data = load_json(target_path)
        validate_payload("agent-job", data)

        return copy.deepcopy(data)

    def update(self, job_data: dict[str, Any]) -> dict[str, Any]:
        """Validate and update an existing persistent Job (no upsert).

        Raises:
            ContractValidationError: If job_data fails schema validation or is not a dict.
            JobNotFoundError: If the job does not already exist.
            JobStoreError: If I/O or filesystem persistence fails.
        """
        validate_payload("agent-job", job_data)

        job_id = job_data["jobId"]
        target_path = self._job_path(job_id)
        if not target_path.is_file():
            raise JobNotFoundError(f"Cannot update non-existent job '{job_id}' at {target_path}")

        safe_copy = copy.deepcopy(job_data)
        self._atomic_write(target_path, safe_copy)
        return copy.deepcopy(safe_copy)

    def list_job_ids(self) -> list[str]:
        """Return a sorted list of all persisted job IDs."""
        if not self.root.is_dir():
            return []

        job_ids = []
        for path in self.root.iterdir():
            if path.is_file() and path.suffix == ".json" and not path.name.endswith(".tmp"):
                job_ids.append(path.stem)

        return sorted(job_ids)
