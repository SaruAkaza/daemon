from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any


@dataclass(frozen=True)
class JournalOperationEntry:
    """Immutable audit record for a single operation in the transaction journal."""
    operation_id: str
    type: str  # "CREATE" | "UPDATE"
    target_path: str
    original_exists: bool
    expected_base_sha256: str | None
    candidate_sha256: str
    applied_status: str  # "NOT_APPLIED", "APPLIED", "REVERTED", "REVERT_FAILED"
    observed_post_apply_sha256: str | None = None
    backup_path: str | None = None
    applied_at: str | None = None
    reverted_at: str | None = None
    rollback_attempted: bool = False
    rollback_result: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "operationId": self.operation_id,
            "type": self.type,
            "targetPath": self.target_path,
            "originalExists": self.original_exists,
            "expectedBaseSha256": self.expected_base_sha256,
            "candidateSha256": self.candidate_sha256,
            "appliedStatus": self.applied_status,
            "observedPostApplySha256": self.observed_post_apply_sha256,
            "backupPath": self.backup_path,
            "appliedAt": self.applied_at,
            "revertedAt": self.reverted_at,
            "rollbackAttempted": self.rollback_attempted,
            "rollbackResult": self.rollback_result,
            "errorMessage": self.error_message,
        }


@dataclass(frozen=True)
class TransactionJournal:
    """Immutable audit journal tracking state across the application lifecycle."""
    change_set_id: str
    request_id: str
    started_at: str
    staging_dir: str
    operations: tuple[JournalOperationEntry, ...]
    rollback_attempted: bool = False
    rollback_succeeded: bool = False
    filesystem_state: str = "CLEAN"  # "CLEAN", "DIRTY", "IN_FLIGHT", "REVERTED", "ROLLBACK_FAILED"
    ended_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "changeSetId": self.change_set_id,
            "requestId": self.request_id,
            "startedAt": self.started_at,
            "endedAt": self.ended_at,
            "stagingDir": self.staging_dir,
            "operations": [op.to_dict() for op in self.operations],
            "rollbackAttempted": self.rollback_attempted,
            "rollbackSucceeded": self.rollback_succeeded,
            "filesystemState": self.filesystem_state,
        }

    def with_updated_operation(self, entry: JournalOperationEntry) -> TransactionJournal:
        """Returns a new TransactionJournal with the matching operation updated."""
        new_ops = tuple(
            entry if op.operation_id == entry.operation_id else op
            for op in self.operations
        )
        return replace(self, operations=new_ops)

    def with_state(
        self,
        filesystem_state: str,
        rollback_attempted: bool | None = None,
        rollback_succeeded: bool | None = None,
        ended_at: str | None = None,
    ) -> TransactionJournal:
        kwargs: dict[str, Any] = {"filesystem_state": filesystem_state}
        if rollback_attempted is not None:
            kwargs["rollback_attempted"] = rollback_attempted
        if rollback_succeeded is not None:
            kwargs["rollback_succeeded"] = rollback_succeeded
        if ended_at is not None:
            kwargs["ended_at"] = ended_at
        return replace(self, **kwargs)
