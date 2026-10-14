from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from scripts.agents.contracts import validate_payload
from scripts.agents.legacy_comparator import LegacyComparisonResult


AUTOMATED_AGENT_IDENTIFIERS = {
    "model",
    "llm",
    "extraction-agent",
    "source-agent",
    "editorial-agent",
    "entities-agent",
    "relations-agent",
    "qa-agent",
    "frontend-agent",
    "gemini",
    "antigravity",
    "claude",
    "gpt",
}


class PilotReviewEngine:
    """Manages formal human review requests and cryptographically validates review decisions."""

    def create_review_request(
        self,
        job_id: str,
        attempt: int,
        request_id: str,
        bundle_id: str,
        result_manifest_hash: str,
        comparison: LegacyComparisonResult,
    ) -> dict[str, Any]:
        """Builds and validates a schema-compliant PilotReviewRequest."""
        discrepancies_data = [
            {
                "entityId": d.entity_id,
                "fieldPath": d.field_path,
                "extractedValue": d.extracted_value,
                "legacyValue": d.legacy_value,
                "sourceCitation": d.source_citation,
            }
            for d in comparison.discrepancies
        ]

        payload = {
            "jobId": job_id,
            "attemptNumber": attempt,
            "requestId": request_id,
            "resultBundleId": bundle_id,
            "resultManifestSha256": result_manifest_hash,
            "legacyComparison": {
                "verdict": comparison.verdict,
                "equivalentCount": comparison.equivalent_count,
                "structuralDiffCount": comparison.structural_diff_count,
                "semanticDiffCount": comparison.semantic_diff_count,
                "newEntitiesCount": comparison.new_entities_count,
                "discrepancies": discrepancies_data,
            },
            "status": "PENDING",
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }

        validate_payload("pilot-review-request.schema.json", payload)
        return payload

    def validate_review_decision(
        self,
        decision: dict[str, Any],
        request: dict[str, Any],
        current_result_manifest_hash: str,
    ) -> tuple[bool, str]:
        """Validates a PilotReviewDecision against request, schemas, and cryptographic manifest hash."""
        try:
            validate_payload("pilot-review-decision.schema.json", decision)
        except Exception as e:
            return False, f"ERR_REVIEW_DECISION_INVALID: Schema validation failed: {e}"

        reviewer = decision.get("reviewer", "").strip().lower()
        if reviewer in AUTOMATED_AGENT_IDENTIFIERS or any(agt in reviewer for agt in ("-agent", "llm", "gemini")):
            return False, f"ERR_REVIEW_AUTHORITY_VIOLATION: Reviewer '{decision.get('reviewer')}' is an automated agent. Model cannot self-approve."

        if decision.get("requestId") != request.get("requestId"):
            return (
                False,
                f"ERR_REVIEW_ID_MISMATCH: Decision requestId '{decision.get('requestId')}' != request '{request.get('requestId')}'",
            )

        if decision.get("resultBundleId") != request.get("resultBundleId"):
            return (
                False,
                f"ERR_REVIEW_ID_MISMATCH: Decision resultBundleId '{decision.get('resultBundleId')}' != request '{request.get('resultBundleId')}'",
            )

        reviewed_hash = decision.get("reviewedResultManifestSha256")
        if reviewed_hash != current_result_manifest_hash:
            return (
                False,
                f"ERR_REVIEW_HASH_MISMATCH: Decision reviewed manifest hash '{reviewed_hash}' != actual current '{current_result_manifest_hash}'",
            )

        dec_value = decision.get("decision")
        if dec_value == "REJECT":
            notes = decision.get("reviewNotes", "")
            return False, f"ERR_REVIEW_REJECTED: {notes}"
        elif dec_value == "APPROVE":
            return True, "APPROVED"

        return False, f"ERR_REVIEW_INVALID: Unknown decision value '{dec_value}'"
