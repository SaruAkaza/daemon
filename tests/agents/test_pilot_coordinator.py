from __future__ import annotations

import json
from pathlib import Path
import pytest

from scripts.agents.bundle_importer import ResultBundleEnvelope
from scripts.agents.canonical_json import sha256_bytes
from scripts.agents.pilot_audit_store import PilotAuditStore
from scripts.agents.pilot_coordinator import PilotCoordinator, PilotCoordinatorError


@pytest.fixture
def coordinator_env(tmp_path: Path):
    runtime_root = tmp_path / ".daemon_runtime"
    audit_store = PilotAuditStore(runtime_root / "audit" / "pilot")
    coordinator = PilotCoordinator(audit_store=audit_store, runtime_root=runtime_root)
    return coordinator, runtime_root, audit_store


def test_initialize_attempt_success(coordinator_env):
    coord, _, audit_store = coordinator_env
    attempt_meta = coord.initialize_attempt("JOB-ANIM-001", "animalidade", "EXTRACTION", attempt_num=1)

    assert attempt_meta["attemptNumber"] == 1
    assert attempt_meta["state"] == "READY_TO_EXPORT"

    history = audit_store.get_audit_history("animalidade")
    assert len(history) == 1
    assert history[0]["toState"] == "READY_TO_EXPORT"


def test_no_retry_overwrite(coordinator_env):
    coord, _, _ = coordinator_env
    coord.initialize_attempt("JOB-ANIM-001", "animalidade", "EXTRACTION", attempt_num=1)

    with pytest.raises(PilotCoordinatorError):
        # Attempting to re-initialize attempt 1 must fail closed
        coord.initialize_attempt("JOB-ANIM-001", "animalidade", "EXTRACTION", attempt_num=1)


def test_process_imported_bundle_and_human_decision(coordinator_env, tmp_path: Path):
    coord, runtime_root, audit_store = coordinator_env
    coord.initialize_attempt("JOB-ANIM-001", "animalidade", "EXTRACTION", attempt_num=1)

    # Export transition
    coord.record_export("animalidade", attempt_num=1, bundle_id="EB-ANIM-EXTRACTION-att1-12345678")

    # Create dummy incoming result bundle
    bdir = tmp_path / "incoming" / "RB-ANIM-EXTRACTION-att1-12345678"
    bdir.mkdir(parents=True)
    art_dir = bdir / "artifacts"
    art_dir.mkdir()
    art_file = art_dir / "extracted.txt"
    art_file.write_text("Extracted text", encoding="utf-8")
    art_hash = sha256_bytes(art_file.read_bytes())

    exec_res = {
        "schemaVersion": "2.0",
        "resultId": "RES-01",
        "requestId": "REQ-01",
        "verdict": "ACCEPT",
        "artifacts": [{"path": "artifacts/extracted.txt"}],
    }
    (bdir / "execution-result.json").write_text(json.dumps(exec_res), encoding="utf-8")

    manifest = {
        "resultBundleId": "RB-ANIM-EXTRACTION-att1-12345678",
        "executionBundleId": "EB-ANIM-EXTRACTION-att1-12345678",
        "requestId": "REQ-01",
        "bookId": "animalidade",
        "attemptNumber": 1,
        "inputManifestSha256": "a" * 64,
        "resultManifestSha256": "placeholder",
        "executionResultPath": "execution-result.json",
        "resultManifestPath": "result-manifest.json",
        "artifacts": [
            {
                "path": "artifacts/extracted.txt",
                "sha256": art_hash,
                "sizeBytes": art_file.stat().st_size,
            }
        ],
        "completedAt": "2026-09-08T12:00:00Z",
    }
    (bdir / "result-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    envelope = ResultBundleEnvelope(
        bundle_id="RB-ANIM-EXTRACTION-att1-12345678",
        bundle_dir=bdir,
        result_manifest_path=bdir / "result-manifest.json",
        execution_result_path=bdir / "execution-result.json",
        artifacts_dir=art_dir,
    )

    proc_res = coord.process_imported_bundle(
        envelope,
        expected_request_id="REQ-01",
        expected_bundle_id="RB-ANIM-EXTRACTION-att1-12345678",
        expected_input_manifest_hash="a" * 64,
    )

    assert proc_res["status"] == "NEEDS_HUMAN_REVIEW"
    review_req = proc_res["reviewRequest"]

    # Submit decision
    decision = {
        "decisionId": "DEC-01",
        "requestId": "REQ-01",
        "resultBundleId": "RB-ANIM-EXTRACTION-att1-12345678",
        "reviewedResultManifestSha256": proc_res["resultManifestSha256"],
        "decision": "APPROVE",
        "reviewer": "human-reviewer",
        "reviewNotes": "All verified.",
        "decidedAt": "2026-09-08T14:00:00Z",
    }

    dec_outcome = coord.submit_human_decision(
        book_id="animalidade",
        decision=decision,
        review_request=review_req,
        current_result_manifest_hash=proc_res["resultManifestSha256"],
    )

    assert dec_outcome["status"] == "APPROVED"


def test_process_imported_bundle_semantic_difference_surfaces_in_review_request(tmp_path: Path):
    audit_store = PilotAuditStore(tmp_path / "audit" / "pilot")
    coord = PilotCoordinator(audit_store=audit_store, runtime_root=tmp_path)

    coord.initialize_attempt("JOB-01", "animalidade", "EXTRACTION", attempt_num=1)
    coord.record_export("animalidade", attempt_num=1, bundle_id="EB-01")

    bdir = tmp_path / "incoming" / "RB-DIFF-01"
    bdir.mkdir(parents=True)
    art_dir = bdir / "artifacts"
    art_dir.mkdir()

    # Extracted entity with attr = 12
    extracted_entity = {"id": "creature-lobo", "name": "Lobo", "attributes": {"FR": 12}}
    ent_bytes = json.dumps(extracted_entity).encode("utf-8")
    (art_dir / "creature.json").write_bytes(ent_bytes)
    ent_hash = sha256_bytes(ent_bytes)

    exec_res = {
        "schemaVersion": "2.0",
        "resultId": "RES-01",
        "requestId": "REQ-DIFF-01",
        "verdict": "ACCEPT",
        "artifacts": [{"path": "artifacts/creature.json"}],
    }
    (bdir / "execution-result.json").write_text(json.dumps(exec_res), encoding="utf-8")

    manifest = {
        "resultBundleId": "RB-DIFF-01",
        "executionBundleId": "EB-01",
        "requestId": "REQ-DIFF-01",
        "bookId": "animalidade",
        "attemptNumber": 1,
        "inputManifestSha256": "a" * 64,
        "resultManifestSha256": "placeholder",
        "executionResultPath": "execution-result.json",
        "resultManifestPath": "result-manifest.json",
        "artifacts": [
            {
                "path": "artifacts/creature.json",
                "sha256": ent_hash,
                "sizeBytes": len(ent_bytes),
            }
        ],
        "completedAt": "2026-09-08T12:00:00Z",
    }
    (bdir / "result-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    envelope = ResultBundleEnvelope(
        bundle_id="RB-DIFF-01",
        bundle_dir=bdir,
        result_manifest_path=bdir / "result-manifest.json",
        execution_result_path=bdir / "execution-result.json",
        artifacts_dir=art_dir,
    )

    # Legacy record has FR = 10 (genuine difference!)
    legacy_entities = [{"id": "creature-lobo", "name": "Lobo", "attributes": {"FR": 10}}]

    proc_res = coord.process_imported_bundle(
        envelope,
        expected_request_id="REQ-DIFF-01",
        expected_bundle_id="RB-DIFF-01",
        expected_input_manifest_hash="a" * 64,
        expected_execution_bundle_id="EB-01",
        legacy_entities=legacy_entities,
    )

    assert proc_res["status"] == "NEEDS_HUMAN_REVIEW"
    review_req = proc_res["reviewRequest"]
    comp = review_req["legacyComparison"]

    assert comp["verdict"] == "SEMANTIC_DIFFERENCE"
    assert comp["semanticDiffCount"] == 1
    assert len(comp["discrepancies"]) == 1
    disc = comp["discrepancies"][0]
    assert disc["entityId"] == "creature-lobo"
    assert "FR" in disc["fieldPath"]
    assert disc["extractedValue"] == 12
    assert disc["legacyValue"] == 10


def test_submit_invalid_human_decision_does_not_persist_to_audit_store(tmp_path: Path):
    runtime_root = tmp_path / ".daemon_runtime"
    coord = PilotCoordinator(runtime_root=runtime_root)

    review_req = {
        "requestId": "REQ-01",
        "resultBundleId": "RB-01",
        "resultManifestSha256": "b" * 64,
    }

    # Invalid decision: reviewer is an automated agent (model cannot self-approve)
    bad_decision = {
        "decisionId": "DEC-INVALID-01",
        "requestId": "REQ-01",
        "resultBundleId": "RB-01",
        "reviewedResultManifestSha256": "b" * 64,
        "decision": "APPROVE",
        "reviewer": "pilot-agent",
        "reviewNotes": "Self approved.",
        "decidedAt": "2026-09-08T14:00:00Z",
    }

    outcome = coord.submit_human_decision(
        book_id="animalidade",
        decision=bad_decision,
        review_request=review_req,
        current_result_manifest_hash="b" * 64,
    )

    assert outcome["status"] == "VALIDATION_FAILED"
    assert "ERR_REVIEW_AUTHORITY_VIOLATION" in outcome["error"]

    # Verify that DEC-INVALID-01 was NOT written to the audit store
    audit_dec_dir = runtime_root / "audit" / "pilot" / "animalidade" / "decisions"
    if audit_dec_dir.exists():
        assert not (audit_dec_dir / "DEC-INVALID-01.json").exists()


