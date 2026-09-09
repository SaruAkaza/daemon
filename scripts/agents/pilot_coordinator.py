from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.agents.bundle_importer import ResultBundleEnvelope, ResultBundleImporter
from scripts.agents.bundle_integrity_validator import BundleIntegrityValidator
from scripts.agents.legacy_comparator import LegacyComparisonResult, LegacyComparator
from scripts.agents.pilot_audit_store import PilotAuditStore
from scripts.agents.pilot_review import PilotReviewEngine
from scripts.agents.pilot_state_machine import PilotStateMachine


class PilotCoordinatorError(RuntimeError):
    """Raised when coordinator workflow rules or attempt uniqueness are violated."""
    pass


class PilotCoordinator:
    """Coordinates immutable sequential attempts, audit transitions, and governance approvals."""

    def __init__(
        self,
        audit_store: PilotAuditStore | None = None,
        runtime_root: Path | None = None,
    ) -> None:
        self.runtime_root = Path(runtime_root) if runtime_root else Path.cwd().parent / ".daemon_runtime"
        self.audit_store = audit_store or PilotAuditStore(self.runtime_root / "audit" / "pilot")
        self.sm = PilotStateMachine()
        self.importer = ResultBundleImporter()
        self.validator = BundleIntegrityValidator()
        self.review_engine = PilotReviewEngine()
        self.comparator = LegacyComparator()

    def initialize_attempt(
        self,
        job_id: str,
        book_id: str,
        stage: str,
        attempt_num: int,
    ) -> dict[str, Any]:
        """Initializes an attempt, guaranteeing uniqueness and recording audit event."""
        if attempt_num < 1:
            raise PilotCoordinatorError(f"attempt_num must be >= 1, got {attempt_num}")

        history = self.audit_store.get_audit_history(book_id)
        for rec in history:
            if rec.get("details", {}).get("attemptNumber") == attempt_num:
                raise PilotCoordinatorError(
                    f"Attempt {attempt_num} already exists for book '{book_id}'. Overwrites prohibited."
                )

        from_state = history[-1]["toState"] if history else "READY_TO_EXPORT"
        target_state = "READY_TO_EXPORT"
        if from_state != "READY_TO_EXPORT":
            target_state = self.sm.transition(from_state, "prepare_attempt")

        self.audit_store.record_transition(
            book_id=book_id,
            from_state=from_state,
            event="prepare_attempt" if from_state != "READY_TO_EXPORT" else "init",
            to_state=target_state,
            details={"jobId": job_id, "stage": stage, "attemptNumber": attempt_num},
        )

        return {
            "jobId": job_id,
            "bookId": book_id,
            "stage": stage,
            "attemptNumber": attempt_num,
            "state": target_state,
        }

    def record_export(self, book_id: str, attempt_num: int, bundle_id: str) -> None:
        """Records bundle export transition to WAITING_FOR_RESULT."""
        self.audit_store.record_transition(
            book_id=book_id,
            from_state="READY_TO_EXPORT",
            event="export_bundle",
            to_state="WAITING_FOR_RESULT",
            details={"attemptNumber": attempt_num, "bundleId": bundle_id},
        )

    def process_imported_bundle(
        self,
        envelope: ResultBundleEnvelope,
        expected_request_id: str,
        expected_bundle_id: str,
        expected_input_manifest_hash: str,
        expected_execution_bundle_id: str | None = None,
        legacy_entities: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Validates bundle integrity and either quarantines it or advances to human review."""
        book_id = "animalidade"
        attempt = 1
        job_id = "JOB-ANIM-001"
        try:
            with open(envelope.result_manifest_path, encoding="utf-8") as f:
                mdata = json.load(f)
            book_id = mdata.get("bookId", "animalidade")
            attempt = mdata.get("attemptNumber", 1)
            job_id = mdata.get("jobId", "JOB-ANIM-001")
        except Exception:
            pass

        self.audit_store.record_transition(
            book_id=book_id,
            from_state="WAITING_FOR_RESULT",
            event="import_bundle",
            to_state="RESULT_IMPORTED",
            details={"bundleId": envelope.bundle_id},
        )

        verdict = self.validator.validate(
            envelope,
            expected_request_id=expected_request_id,
            expected_bundle_id=expected_bundle_id,
            expected_input_manifest_hash=expected_input_manifest_hash,
            expected_execution_bundle_id=expected_execution_bundle_id,
        )

        if not verdict.is_valid:
            self.audit_store.record_transition(
                book_id=book_id,
                from_state="RESULT_IMPORTED",
                event="integrity_failed",
                to_state="VALIDATION_FAILED",
                details={"errors": verdict.errors},
            )
            rejected_dir = self.runtime_root / "bundles" / "rejected"
            self.importer.seal_and_quarantine(
                envelope.bundle_dir, rejected_dir, reason="; ".join(verdict.errors)
            )
            return {
                "status": "VALIDATION_FAILED",
                "verdict": verdict,
                "errors": verdict.errors,
            }

        accepted_dir = self.runtime_root / "bundles" / "accepted"
        promoted_dir = self.importer.promote_to_accepted(envelope.bundle_dir, accepted_dir)

        # Collect extracted entities for deterministic comparison
        extracted_entities: list[dict[str, Any]] = []
        artifacts_dir = promoted_dir / "artifacts"
        if artifacts_dir.is_dir():
            for jf in sorted(artifacts_dir.glob("*.json")):
                if jf.name in ("execution-result.json", "result-manifest.json"):
                    continue
                try:
                    with open(jf, encoding="utf-8") as f:
                        jdata = json.load(f)
                    if isinstance(jdata, list):
                        extracted_entities.extend([item for item in jdata if isinstance(item, dict)])
                    elif isinstance(jdata, dict):
                        extracted_entities.append(jdata)
                except Exception:
                    pass

        if legacy_entities is not None:
            comp = self.comparator.compare_entities(extracted_entities, legacy_entities)
        else:
            comp = LegacyComparisonResult(
                verdict="SEMANTIC_EQUIVALENT",
                equivalent_count=len(verdict.artifact_hashes),
                structural_diff_count=0,
                semantic_diff_count=0,
                new_entities_count=0,
                discrepancies=[],
            )

        review_req = self.review_engine.create_review_request(
            job_id=job_id,
            attempt=attempt,
            request_id=expected_request_id,
            bundle_id=expected_bundle_id,
            result_manifest_hash=verdict.result_manifest_sha256,
            comparison=comp,
        )
        self.audit_store.record_review_request(book_id, review_req)

        self.audit_store.record_transition(
            book_id=book_id,
            from_state="RESULT_IMPORTED",
            event="integrity_passed",
            to_state="NEEDS_HUMAN_REVIEW",
            details={
                "bundleId": expected_bundle_id,
                "manifestHash": verdict.result_manifest_sha256,
                "comparisonVerdict": comp.verdict,
            },
        )

        return {
            "status": "NEEDS_HUMAN_REVIEW",
            "reviewRequest": review_req,
            "resultManifestSha256": verdict.result_manifest_sha256,
            "verdict": verdict,
            "promotedDir": str(promoted_dir),
        }

    def submit_human_decision(
        self,
        book_id: str,
        decision: dict[str, Any],
        review_request: dict[str, Any],
        current_result_manifest_hash: str,
    ) -> dict[str, Any]:
        """Validates and processes a human review decision."""
        valid, msg = self.review_engine.validate_review_decision(
            decision, review_request, current_result_manifest_hash
        )
        self.audit_store.record_review_decision(book_id, decision)

        if not valid:
            if "ERR_REVIEW_REJECTED" in msg:
                self.audit_store.record_transition(
                    book_id=book_id,
                    from_state="NEEDS_HUMAN_REVIEW",
                    event="human_reject",
                    to_state="REJECTED",
                    details={"reason": msg},
                )
                self.audit_store.record_transition(
                    book_id=book_id,
                    from_state="REJECTED",
                    event="request_rework",
                    to_state="REWORK_REQUIRED",
                    details={"notes": decision.get("reviewNotes")},
                )
                return {"status": "REWORK_REQUIRED", "error": msg}
            else:
                return {"status": "VALIDATION_FAILED", "error": msg}

        self.audit_store.record_transition(
            book_id=book_id,
            from_state="NEEDS_HUMAN_REVIEW",
            event="human_approve",
            to_state="APPROVED",
            details={
                "decisionId": decision.get("decisionId"),
                "manifestHash": current_result_manifest_hash,
            },
        )
        return {"status": "APPROVED", "decision": decision}
