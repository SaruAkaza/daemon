from __future__ import annotations

import pytest

from scripts.agents.legacy_comparator import LegacyComparisonResult, LegacyDiscrepancy
from scripts.agents.pilot_review import PilotReviewEngine


@pytest.fixture
def sample_comparison() -> LegacyComparisonResult:
    return LegacyComparisonResult(
        verdict="SEMANTIC_EQUIVALENT",
        equivalent_count=1,
        structural_diff_count=0,
        semantic_diff_count=0,
        new_entities_count=0,
        discrepancies=[],
    )


@pytest.fixture
def sample_request(sample_comparison: LegacyComparisonResult) -> dict:
    engine = PilotReviewEngine()
    return engine.create_review_request(
        job_id="JOB-ANIM-001",
        attempt=1,
        request_id="REQ-ANIM-01",
        bundle_id="RB-ANIM-EXTRACTION-att1-12345678",
        result_manifest_hash="a" * 64,
        comparison=sample_comparison,
    )


def test_create_review_request_valid(sample_request: dict):
    assert sample_request["jobId"] == "JOB-ANIM-001"
    assert sample_request["attemptNumber"] == 1
    assert sample_request["requestId"] == "REQ-ANIM-01"
    assert sample_request["resultBundleId"] == "RB-ANIM-EXTRACTION-att1-12345678"
    assert sample_request["resultManifestSha256"] == "a" * 64
    assert sample_request["status"] == "PENDING"
    assert sample_request["legacyComparison"]["verdict"] == "SEMANTIC_EQUIVALENT"


def test_validate_review_decision_approved_success(sample_request: dict):
    engine = PilotReviewEngine()
    decision = {
        "decisionId": "DEC-ANIM-001",
        "requestId": "REQ-ANIM-01",
        "resultBundleId": "RB-ANIM-EXTRACTION-att1-12345678",
        "reviewedResultManifestSha256": "a" * 64,
        "decision": "APPROVE",
        "reviewer": "human-editor-alice",
        "reviewNotes": "All entities verified against source text.",
        "decidedAt": "2026-09-08T14:00:00Z",
    }

    valid, msg = engine.validate_review_decision(decision, sample_request, "a" * 64)
    assert valid is True
    assert msg == "APPROVED"


def test_validate_review_decision_hash_mismatch(sample_request: dict):
    engine = PilotReviewEngine()
    decision = {
        "decisionId": "DEC-ANIM-001",
        "requestId": "REQ-ANIM-01",
        "resultBundleId": "RB-ANIM-EXTRACTION-att1-12345678",
        "reviewedResultManifestSha256": "a" * 64,
        "decision": "APPROVE",
        "reviewer": "human-editor-alice",
        "reviewNotes": "Looks good.",
        "decidedAt": "2026-09-08T14:00:00Z",
    }

    # Manifest hash altered after review
    valid, msg = engine.validate_review_decision(decision, sample_request, "f" * 64)
    assert valid is False
    assert "ERR_REVIEW_HASH_MISMATCH" in msg


def test_validate_review_decision_rejected(sample_request: dict):
    engine = PilotReviewEngine()
    decision = {
        "decisionId": "DEC-ANIM-001",
        "requestId": "REQ-ANIM-01",
        "resultBundleId": "RB-ANIM-EXTRACTION-att1-12345678",
        "reviewedResultManifestSha256": "a" * 64,
        "decision": "REJECT",
        "reviewer": "human-editor-alice",
        "reviewNotes": "Missing 2 paragraphs from page 4.",
        "decidedAt": "2026-09-08T14:00:00Z",
    }

    valid, msg = engine.validate_review_decision(decision, sample_request, "a" * 64)
    assert valid is False
    assert "ERR_REVIEW_REJECTED" in msg


def test_validate_review_decision_blocked_agent_authority(sample_request: dict):
    engine = PilotReviewEngine()
    decision = {
        "decisionId": "DEC-ANIM-001",
        "requestId": "REQ-ANIM-01",
        "resultBundleId": "RB-ANIM-EXTRACTION-att1-12345678",
        "reviewedResultManifestSha256": "a" * 64,
        "decision": "APPROVE",
        "reviewer": "extraction-agent",
        "reviewNotes": "Self approved by agent.",
        "decidedAt": "2026-09-08T14:00:00Z",
    }

    valid, msg = engine.validate_review_decision(decision, sample_request, "a" * 64)
    assert valid is False
    assert "ERR_REVIEW_AUTHORITY_VIOLATION" in msg
