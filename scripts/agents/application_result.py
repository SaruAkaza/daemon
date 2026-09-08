from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from scripts.agents.change_set_applier import AppliedOperationRecord
from scripts.agents.transaction_journal import TransactionJournal


@dataclass(frozen=True)
class ApplicationResult:
    """Formal outcome of applying a ChangeSet to the repository filesystem."""
    change_set_id: str
    request_id: str
    status: str  # "APPLIED", "NOT_APPLIED", "ROLLED_BACK", "ROLLBACK_FAILED", "HUMAN_REVIEW", "BLOCKED"
    applied_operations: tuple[AppliedOperationRecord, ...]
    blocked_operations: tuple[dict[str, Any], ...]
    failure_code: str | None
    reasons: tuple[str, ...]
    applied_at: str | None
    duration_ms: float
    journal: TransactionJournal | None
    metadata: dict[str, Any]
    schema_version: str = "2.1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "changeSetId": self.change_set_id,
            "requestId": self.request_id,
            "status": self.status,
            "appliedOperations": [
                {
                    "operationId": op.operation_id,
                    "targetPath": op.target_path,
                    "type": op.type,
                    "postApplySha256": op.post_apply_sha256,
                    "appliedAt": op.applied_at,
                    "previousSha256": getattr(op, "previous_sha256", None),
                    "bytesWritten": getattr(op, "bytes_written", 0),
                }
                for op in self.applied_operations
            ],
            "blockedOperations": list(self.blocked_operations),
            "failureCode": self.failure_code,
            "reasons": list(self.reasons),
            "appliedAt": self.applied_at,
            "durationMs": self.duration_ms,
            "journal": self.journal.to_dict() if self.journal else None,
            "metadata": self.metadata,
        }
