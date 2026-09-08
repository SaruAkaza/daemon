from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from scripts.agents.application_runtime import ApplicationRuntimeConfig
from scripts.agents.change_set import ChangeSet
from scripts.agents.filesystem_primitives import FileSystemPrimitives
from scripts.agents.patch_applier import PatchApplier
from scripts.agents.precondition_validator import PreconditionValidator
from scripts.agents.staging_manager import StagingManager
from scripts.agents.transaction_journal import (
    JournalOperationEntry,
    TransactionJournal,
)


@dataclass(frozen=True)
class AppliedOperationRecord:
    operation_id: str
    target_path: str
    type: str
    post_apply_sha256: str
    applied_at: str


@dataclass(frozen=True)
class ChangeSetApplicationOutcome:
    status: str  # "APPLIED", "ROLLED_BACK", "ROLLBACK_FAILED", "NOT_APPLIED"
    journal: TransactionJournal
    applied_records: tuple[AppliedOperationRecord, ...]
    failure_code: str | None
    reasons: tuple[str, ...]


class ChangeSetApplier:
    """Orchestrates 6-phase application with transaction journaling and compensating rollback."""

    def __init__(
        self,
        config: ApplicationRuntimeConfig,
        precondition_validator: PreconditionValidator,
        patch_applier: PatchApplier,
        staging_manager: StagingManager,
        primitives: type[FileSystemPrimitives] = FileSystemPrimitives,
    ) -> None:
        self.config = config
        self.precondition_validator = precondition_validator
        self.patch_applier = patch_applier
        self.staging_manager = staging_manager
        self.primitives = primitives

    def apply(
        self,
        change_set: ChangeSet,
        allowed_write_scope: Sequence[str],
    ) -> ChangeSetApplicationOutcome:
        started_at = datetime.now(timezone.utc).isoformat()

        # Build initial journal operations
        journal_ops = tuple(
            JournalOperationEntry(
                operation_id=op.operation_id,
                type=op.type,
                target_path=op.target_path,
                original_exists=(op.type == "UPDATE"),
                expected_base_sha256=op.expected_base_sha256,
                candidate_sha256="",
                applied_status="NOT_APPLIED",
            )
            for op in change_set.operations
        )

        initial_journal = TransactionJournal(
            change_set_id=change_set.change_set_id,
            request_id=change_set.request_id,
            started_at=started_at,
            staging_dir="",
            operations=journal_ops,
            filesystem_state="CLEAN",
        )

        # ---------------------------------------------------------
        # Phase 1: Precondition validation (initial)
        # ---------------------------------------------------------
        pre_res = self.precondition_validator.validate_initial(
            change_set, list(allowed_write_scope)
        )
        if not pre_res.valid:
            ended_at = datetime.now(timezone.utc).isoformat()
            journal = initial_journal.with_state(
                filesystem_state="CLEAN",
                ended_at=ended_at,
            )
            return ChangeSetApplicationOutcome(
                status="NOT_APPLIED",
                journal=journal,
                applied_records=(),
                failure_code=pre_res.code,
                reasons=pre_res.reasons,
            )

        # ---------------------------------------------------------
        # Phase 2: Candidate construction in memory
        # ---------------------------------------------------------
        try:
            candidates = self.patch_applier.construct_candidates(change_set)
        except Exception as exc:
            ended_at = datetime.now(timezone.utc).isoformat()
            journal = initial_journal.with_state(
                filesystem_state="CLEAN",
                ended_at=ended_at,
            )
            return ChangeSetApplicationOutcome(
                status="NOT_APPLIED",
                journal=journal,
                applied_records=(),
                failure_code="ERR_PATCH_INVALID",
                reasons=(f"Candidate construction failed: {exc}",),
            )

        # Update candidate_sha256 in journal operations
        cand_map = {c.operation_id: c for c in candidates}
        journal_ops_with_cand = tuple(
            JournalOperationEntry(
                operation_id=op.operation_id,
                type=op.type,
                target_path=op.target_path,
                original_exists=op.original_exists,
                expected_base_sha256=op.expected_base_sha256,
                candidate_sha256=cand_map[op.operation_id].candidate_sha256 if op.operation_id in cand_map else "",
                applied_status="NOT_APPLIED",
            )
            for op in initial_journal.operations
        )

        # ---------------------------------------------------------
        # Phase 3: Same-volume Isolated Staging
        # ---------------------------------------------------------
        try:
            staging_dir = self.staging_manager.prepare_staging(change_set.change_set_id)
            staged_paths = self.staging_manager.stage_candidates(staging_dir, candidates)
        except Exception as exc:
            ended_at = datetime.now(timezone.utc).isoformat()
            journal = initial_journal.with_state(
                filesystem_state="CLEAN",
                ended_at=ended_at,
            )
            err_code = "ERR_CROSS_VOLUME_STAGING" if "ERR_CROSS_VOLUME_STAGING" in str(exc) else "ERR_RESOURCE_BOUND_EXCEEDED"
            return ChangeSetApplicationOutcome(
                status="NOT_APPLIED",
                journal=journal,
                applied_records=(),
                failure_code=err_code,
                reasons=(str(exc),),
            )

        journal = TransactionJournal(
            change_set_id=change_set.change_set_id,
            request_id=change_set.request_id,
            started_at=started_at,
            staging_dir=str(staging_dir),
            operations=journal_ops_with_cand,
            filesystem_state="IN_FLIGHT",
        )

        # ---------------------------------------------------------
        # Phase 4: TOCTOU Revalidation immediately pre-mutation
        # ---------------------------------------------------------
        toctou_res = self.precondition_validator.validate_toctou_pre_mutation(
            change_set, list(allowed_write_scope)
        )
        if not toctou_res.valid:
            self.staging_manager.cleanup_staging(staging_dir)
            ended_at = datetime.now(timezone.utc).isoformat()
            journal = journal.with_state(
                filesystem_state="CLEAN",
                ended_at=ended_at,
            )
            return ChangeSetApplicationOutcome(
                status="NOT_APPLIED",
                journal=journal,
                applied_records=(),
                failure_code=toctou_res.code,
                reasons=toctou_res.reasons,
            )

        # ---------------------------------------------------------
        # Phase 5: Atomic Individual Mutation with Snapshots
        # ---------------------------------------------------------
        applied_records: list[AppliedOperationRecord] = []
        for op in change_set.operations:
            staged_file = staged_paths[op.operation_id]
            target_path = self.config.repository_root / op.target_path
            backup_path: str | None = None

            try:
                if op.type == "UPDATE":
                    backup = self.staging_manager.create_backup(
                        staging_dir, op.target_path, self.config.repository_root
                    )
                    backup_path = str(backup)
                    post_sha = self.primitives.atomic_replace(target_path, staged_file)
                elif op.type == "CREATE":
                    post_sha = self.primitives.exclusive_create(target_path, staged_file)
                else:
                    raise ValueError(f"ERR_FORBIDDEN_OPERATION_TYPE: {op.type}")

                applied_time = datetime.now(timezone.utc).isoformat()
                applied_rec = AppliedOperationRecord(
                    operation_id=op.operation_id,
                    target_path=op.target_path,
                    type=op.type,
                    post_apply_sha256=post_sha,
                    applied_at=applied_time,
                )
                applied_records.append(applied_rec)

                # Update journal entry
                entry = next(e for e in journal.operations if e.operation_id == op.operation_id)
                new_entry = JournalOperationEntry(
                    operation_id=entry.operation_id,
                    type=entry.type,
                    target_path=entry.target_path,
                    original_exists=entry.original_exists,
                    expected_base_sha256=entry.expected_base_sha256,
                    candidate_sha256=entry.candidate_sha256,
                    applied_status="APPLIED",
                    observed_post_apply_sha256=post_sha,
                    backup_path=backup_path,
                    applied_at=applied_time,
                )
                journal = journal.with_updated_operation(new_entry)

            except Exception as exc:
                # ---------------------------------------------------------
                # Phase 6: Compensating Rollback Engine
                # ---------------------------------------------------------
                return self._execute_rollback(
                    change_set=change_set,
                    journal=journal,
                    applied_records=applied_records,
                    staging_dir=staging_dir,
                    triggering_error=exc,
                )

        # All operations applied successfully!
        ended_at = datetime.now(timezone.utc).isoformat()
        journal = journal.with_state(
            filesystem_state="CLEAN",
            ended_at=ended_at,
        )
        self.staging_manager.cleanup_staging(staging_dir)

        return ChangeSetApplicationOutcome(
            status="APPLIED",
            journal=journal,
            applied_records=tuple(applied_records),
            failure_code=None,
            reasons=(),
        )

    def _execute_rollback(
        self,
        change_set: ChangeSet,
        journal: TransactionJournal,
        applied_records: list[AppliedOperationRecord],
        staging_dir: Path,
        triggering_error: Exception,
    ) -> ChangeSetApplicationOutcome:
        rollback_failed = False
        reasons: list[str] = [f"Mutation failed: {triggering_error}"]

        # Reverse order compensation strictly on APPLIED operations
        for rec in reversed(applied_records):
            entry = next(e for e in journal.operations if e.operation_id == rec.operation_id)
            target = self.config.repository_root / rec.target_path
            now_iso = datetime.now(timezone.utc).isoformat()

            if rec.type == "CREATE":
                ok = self.primitives.compensating_remove(target, rec.post_apply_sha256)
                if ok:
                    updated = JournalOperationEntry(
                        operation_id=entry.operation_id,
                        type=entry.type,
                        target_path=entry.target_path,
                        original_exists=entry.original_exists,
                        expected_base_sha256=entry.expected_base_sha256,
                        candidate_sha256=entry.candidate_sha256,
                        applied_status="REVERTED",
                        observed_post_apply_sha256=entry.observed_post_apply_sha256,
                        backup_path=entry.backup_path,
                        applied_at=entry.applied_at,
                        reverted_at=now_iso,
                        rollback_attempted=True,
                        rollback_result="SUCCESS",
                    )
                else:
                    updated = JournalOperationEntry(
                        operation_id=entry.operation_id,
                        type=entry.type,
                        target_path=entry.target_path,
                        original_exists=entry.original_exists,
                        expected_base_sha256=entry.expected_base_sha256,
                        candidate_sha256=entry.candidate_sha256,
                        applied_status="REVERT_FAILED",
                        observed_post_apply_sha256=entry.observed_post_apply_sha256,
                        backup_path=entry.backup_path,
                        applied_at=entry.applied_at,
                        rollback_attempted=True,
                        rollback_result="SKIPPED_EXTERNAL_MUTATION",
                        error_message="Hash mismatch or missing file during compensating remove",
                    )
                    rollback_failed = True
                    reasons.append(f"Compensating remove failed for '{rec.target_path}'")
                journal = journal.with_updated_operation(updated)

            elif rec.type == "UPDATE":
                backup_file = Path(entry.backup_path) if entry.backup_path else Path("")
                ok = self.primitives.compensating_restore(target, backup_file, rec.post_apply_sha256)
                if ok:
                    updated = JournalOperationEntry(
                        operation_id=entry.operation_id,
                        type=entry.type,
                        target_path=entry.target_path,
                        original_exists=entry.original_exists,
                        expected_base_sha256=entry.expected_base_sha256,
                        candidate_sha256=entry.candidate_sha256,
                        applied_status="REVERTED",
                        observed_post_apply_sha256=entry.observed_post_apply_sha256,
                        backup_path=entry.backup_path,
                        applied_at=entry.applied_at,
                        reverted_at=now_iso,
                        rollback_attempted=True,
                        rollback_result="SUCCESS",
                    )
                else:
                    updated = JournalOperationEntry(
                        operation_id=entry.operation_id,
                        type=entry.type,
                        target_path=entry.target_path,
                        original_exists=entry.original_exists,
                        expected_base_sha256=entry.expected_base_sha256,
                        candidate_sha256=entry.candidate_sha256,
                        applied_status="REVERT_FAILED",
                        observed_post_apply_sha256=entry.observed_post_apply_sha256,
                        backup_path=entry.backup_path,
                        applied_at=entry.applied_at,
                        rollback_attempted=True,
                        rollback_result="SKIPPED_EXTERNAL_MUTATION",
                        error_message="Hash mismatch or missing backup during compensating restore",
                    )
                    rollback_failed = True
                    reasons.append(f"Compensating restore failed for '{rec.target_path}'")
                journal = journal.with_updated_operation(updated)

        ended_at = datetime.now(timezone.utc).isoformat()

        if rollback_failed:
            journal = journal.with_state(
                filesystem_state="ROLLBACK_FAILED",
                rollback_attempted=True,
                rollback_succeeded=False,
                ended_at=ended_at,
            )
            self.staging_manager.preserve_for_audit(staging_dir, journal)
            return ChangeSetApplicationOutcome(
                status="ROLLBACK_FAILED",
                journal=journal,
                applied_records=tuple(applied_records),
                failure_code="ERR_CRITICAL_ROLLBACK_FAILED",
                reasons=tuple(reasons),
            )
        else:
            journal = journal.with_state(
                filesystem_state="REVERTED",
                rollback_attempted=True,
                rollback_succeeded=True,
                ended_at=ended_at,
            )
            self.staging_manager.cleanup_staging(staging_dir)
            return ChangeSetApplicationOutcome(
                status="ROLLED_BACK",
                journal=journal,
                applied_records=tuple(applied_records),
                failure_code="ERR_ATOMIC_COMMIT_FAILED",
                reasons=tuple(reasons),
            )
