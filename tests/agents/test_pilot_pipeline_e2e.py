from __future__ import annotations

import json
import os
import stat
import subprocess
from pathlib import Path
import pytest

from scripts.agents.bundle_exporter import ExecutionBundleExporter
from scripts.agents.bundle_importer import ResultBundleEnvelope
from scripts.agents.canonical_json import sha256_bytes, sha256_file
from scripts.agents.pilot_audit_store import PilotAuditStore
from scripts.agents.pilot_coordinator import PilotCoordinator
from scripts.agents.pilot_persistence_adapter import PilotPersistenceAdapter
from scripts.agents.pilot_qa_validator import PilotQAValidator
from scripts.agents.preview_projector import LocalPreviewProjector
from scripts.agents.restricted_workspace import RestrictedPilotWorkspace


@pytest.fixture
def hermetic_pipeline_env(tmp_path: Path):
    runtime_root = tmp_path / ".daemon_runtime"
    audit_store = PilotAuditStore(runtime_root / "audit" / "pilot")
    coordinator = PilotCoordinator(audit_store=audit_store, runtime_root=runtime_root)
    workspace_root = RestrictedPilotWorkspace.get_workspace_path(runtime_root, "animalidade")
    RestrictedPilotWorkspace.initialize_layout(workspace_root)
    preview_root = runtime_root / "preview"
    staging_root = runtime_root / "staging"
    return {
        "tmp_path": tmp_path,
        "runtime_root": runtime_root,
        "audit_store": audit_store,
        "coordinator": coordinator,
        "workspace_root": workspace_root,
        "preview_root": preview_root,
        "staging_root": staging_root,
    }


def test_full_pilot_pipeline_hermetic_success(hermetic_pipeline_env: dict):
    env = hermetic_pipeline_env
    coord: PilotCoordinator = env["coordinator"]
    ws_root: Path = env["workspace_root"]
    runtime_root: Path = env["runtime_root"]
    preview_root: Path = env["preview_root"]
    staging_root: Path = env["staging_root"]
    audit_store: PilotAuditStore = env["audit_store"]

    book_id = "animalidade"
    job_id = "JOB-ANIM-001"
    request_id = "REQ-ANIM-001-EXTRACTION-01"

    # Step 1: Initialize attempt
    attempt_meta = coord.initialize_attempt(job_id, book_id, "EXTRACTION", attempt_num=1)
    assert attempt_meta["state"] == "READY_TO_EXPORT"

    # Step 2: Export bundle
    req_payload = {
        "schemaVersion": "2.0",
        "requestId": request_id,
        "jobId": job_id,
        "bookId": book_id,
        "targetStage": "extraction",
        "assignedAgent": "extraction-agent",
        "allowedWriteScope": ["data/text/animalidade.txt", "data/entities/creature_npc.json"],
        "executionProfile": "manual-antigravity",
        "contextPack": {
            "schemaVersion": "1.0",
            "contextPackId": f"CTX-{request_id}",
            "jobId": job_id,
            "agent": "extraction-agent",
            "stage": "extraction",
            "mandatory": ["docs/architecture/constitution.md"],
            "domain": ["docs/context/domain/taxonomy.md"],
            "bookContext": ["coordination/books/animalidade.md"],
            "jobContext": ["coordination/queue/codex.json"],
            "handoffContext": [],
            "task": {
                "type": "extract_pilot",
                "sourceType": "docx",
                "sourcePath": "Livros/word/feito/animalidade.docx",
            },
            "outputContract": "schemas/entity.schema.json",
        },
        "taskInstruction": "Extract pilot data",
        "outputSchemaName": "entity.schema.json",
    }
    exporter = ExecutionBundleExporter()
    outgoing_dir = runtime_root / "bundles" / "outgoing"
    exported_bundle_dir = exporter.export_bundle(req_payload, attempt=1, output_base_dir=outgoing_dir)
    coord.record_export(book_id, attempt_num=1, bundle_id=exported_bundle_dir.name)

    with open(exported_bundle_dir / "execution-bundle.json", encoding="utf-8") as f:
        eb_envelope = json.load(f)
    input_manifest_hash = eb_envelope["inputManifestSha256"]

    # Step 3: Simulate operator returning valid ResultBundle
    incoming_bundle_id = f"RB-ANIM-EXTRACTION-att1-{eb_envelope['executionBundleId'].split('-')[-1]}"
    incoming_dir = runtime_root / "bundles" / "incoming" / incoming_bundle_id
    incoming_dir.mkdir(parents=True)
    artifacts_dir = incoming_dir / "artifacts"
    artifacts_dir.mkdir()

    # Candidate files
    text_bytes = b"Texto extraido de animalidade\n"
    (artifacts_dir / "animalidade.txt").write_bytes(text_bytes)
    text_hash = sha256_bytes(text_bytes)
    text_content = text_bytes.decode("utf-8")

    entity_data = {
        "id": "creature-lobo",
        "name": "Lobo",
        "category": "creature_npc",
        "source": "animalidade",
        "page": 1,
        "entries": ["Lobo selvagem."],
    }
    entity_str = json.dumps(entity_data)
    entity_bytes = entity_str.encode("utf-8")
    (artifacts_dir / "creature_npc.json").write_bytes(entity_bytes)
    entity_hash = sha256_bytes(entity_bytes)

    exec_result_payload = {
        "schemaVersion": "2.0",
        "executionId": f"EXEC-{request_id}-01",
        "requestId": request_id,
        "agent": "extraction-agent",
        "stage": "extraction",
        "status": "SUCCESS",
        "proposedArtifacts": {
            "data/text/animalidade.txt": text_content,
            "data/entities/creature_npc.json": entity_str,
        },
        "evidence": [{"book": "animalidade", "page": 1}],
        "uncertainties": [],
    }
    (incoming_dir / "execution-result.json").write_text(json.dumps(exec_result_payload), encoding="utf-8")

    result_manifest_payload = {
        "resultBundleId": incoming_bundle_id,
        "executionBundleId": eb_envelope["executionBundleId"],
        "requestId": request_id,
        "bookId": book_id,
        "attemptNumber": 1,
        "inputManifestSha256": input_manifest_hash,
        "resultManifestSha256": "placeholder",
        "executionResultPath": "execution-result.json",
        "resultManifestPath": "result-manifest.json",
        "artifacts": [
            {
                "path": "artifacts/animalidade.txt",
                "sha256": text_hash,
                "sizeBytes": len(text_bytes),
            },
            {
                "path": "artifacts/creature_npc.json",
                "sha256": entity_hash,
                "sizeBytes": len(entity_bytes),
            },
        ],
        "completedAt": "2026-09-08T14:00:00Z",
    }
    (incoming_dir / "result-manifest.json").write_text(json.dumps(result_manifest_payload), encoding="utf-8")

    envelope = ResultBundleEnvelope(
        bundle_id=incoming_bundle_id,
        bundle_dir=incoming_dir,
        result_manifest_path=incoming_dir / "result-manifest.json",
        execution_result_path=incoming_dir / "execution-result.json",
        artifacts_dir=artifacts_dir,
    )

    # Step 4: Coordinator processes imported bundle -> advances to NEEDS_HUMAN_REVIEW
    import_res = coord.process_imported_bundle(
        envelope=envelope,
        expected_request_id=request_id,
        expected_bundle_id=incoming_bundle_id,
        expected_input_manifest_hash=input_manifest_hash,
    )
    assert import_res.get("errors") is None or import_res.get("errors") == []
    assert import_res["status"] == "NEEDS_HUMAN_REVIEW"
    review_req = import_res["reviewRequest"]
    res_manifest_hash = import_res["resultManifestSha256"]

    # Step 5: Submit human decision APPROVE
    decision_payload = {
        "decisionId": "DEC-ANIM-001",
        "requestId": request_id,
        "resultBundleId": incoming_bundle_id,
        "reviewedResultManifestSha256": res_manifest_hash,
        "decision": "APPROVE",
        "reviewer": "human-editor-carol",
        "reviewNotes": "Integrity confirmed and approved for isolated persistence.",
        "decidedAt": "2026-09-08T14:30:00Z",
    }
    dec_outcome = coord.submit_human_decision(
        book_id=book_id,
        decision=decision_payload,
        review_request=review_req,
        current_result_manifest_hash=res_manifest_hash,
    )
    assert dec_outcome["status"] == "APPROVED"

    # Step 6: Persist through V2.1 Application Adapter into RestrictedPilotWorkspace
    adapter = PilotPersistenceAdapter()
    app_result = adapter.apply_pilot_artifacts(
        workspace_root=ws_root,
        staging_root=staging_root,
        execution_request=req_payload,
        execution_result=exec_result_payload,
        review_decision=decision_payload,
    )
    assert app_result.status == "APPLIED"
    assert (ws_root / "data" / "text" / "animalidade.txt").exists()
    assert (ws_root / "data" / "entities" / "creature_npc.json").exists()

    coord.audit_store.record_transition(
        book_id=book_id,
        from_state="APPROVED",
        event="apply_persistence",
        to_state="PERSISTED",
        details={"changeSetId": app_result.change_set_id},
    )

    # Step 7: Dataset QA Gates against isolated workspace
    qa_validator = PilotQAValidator()
    qa_verdict = qa_validator.validate_dataset(ws_root, book_id=book_id, expected_pages=1)
    assert qa_verdict.passed is True

    coord.audit_store.record_transition(
        book_id=book_id,
        from_state="PERSISTED",
        event="qa_gates_passed",
        to_state="QA_PASS",
    )

    # Step 8: Local Preview Projection
    projector = LocalPreviewProjector()
    projected_path = projector.project_local_preview(
        workspace_root=ws_root,
        preview_root=preview_root,
        book_id=book_id,
        rights_status="UNKNOWN",
        publication_mode="NOT_PUBLIC",
    )
    assert (projected_path / "index.json").exists()

    coord.audit_store.record_transition(
        book_id=book_id,
        from_state="QA_PASS",
        event="project_preview",
        to_state="PREVIEW_READY",
        details={"path": str(projected_path)},
    )
    coord.audit_store.record_transition(
        book_id=book_id,
        from_state="PREVIEW_READY",
        event="validate_navigation",
        to_state="PILOT_VALIDATED",
    )

    # Clean up permissions so tmp_path can be removed cleanly
    for root, _, files in os.walk(env["runtime_root"]):
        for fname in files:
            try:
                os.chmod(Path(root) / fname, stat.S_IWRITE | stat.S_IREAD)
            except Exception:
                pass


def test_pilot_pipeline_integrity_tamper_rejection(hermetic_pipeline_env: dict):
    env = hermetic_pipeline_env
    coord: PilotCoordinator = env["coordinator"]
    runtime_root: Path = env["runtime_root"]

    coord.initialize_attempt("JOB-01", "animalidade", "EXTRACTION", attempt_num=1)
    coord.record_export("animalidade", attempt_num=1, bundle_id="EB-ANIM-01")

    # Tampered incoming bundle
    bdir = runtime_root / "bundles" / "incoming" / "RB-ANIM-01"
    bdir.mkdir(parents=True)
    art_dir = bdir / "artifacts"
    art_dir.mkdir()
    (art_dir / "text.txt").write_text("tampered bytes", encoding="utf-8")

    (bdir / "execution-result.json").write_text(
        json.dumps({"schemaVersion": "2.0", "resultId": "R1", "requestId": "REQ-01", "verdict": "ACCEPT", "artifacts": [{"path": "artifacts/text.txt"}]}),
        encoding="utf-8",
    )
    (bdir / "result-manifest.json").write_text(
        json.dumps({
            "resultBundleId": "RB-ANIM-01",
            "executionBundleId": "EB-ANIM-01",
            "requestId": "REQ-01",
            "bookId": "animalidade",
            "attemptNumber": 1,
            "inputManifestSha256": "0" * 64,
            "resultManifestSha256": "0" * 64,
            "executionResultPath": "execution-result.json",
            "resultManifestPath": "result-manifest.json",
            "artifacts": [{"path": "artifacts/text.txt", "sha256": "f" * 64, "sizeBytes": 10}],
            "completedAt": "2026-09-08T12:00:00Z",
        }),
        encoding="utf-8",
    )

    envelope = ResultBundleEnvelope(
        bundle_id="RB-ANIM-01",
        bundle_dir=bdir,
        result_manifest_path=bdir / "result-manifest.json",
        execution_result_path=bdir / "execution-result.json",
        artifacts_dir=art_dir,
    )

    res = coord.process_imported_bundle(
        envelope,
        expected_request_id="REQ-01",
        expected_bundle_id="RB-ANIM-01",
        expected_input_manifest_hash="0" * 64,
    )

    assert res["status"] == "VALIDATION_FAILED"
    assert (runtime_root / "bundles" / "rejected" / "RB-ANIM-01").exists()

    for root, _, files in os.walk(env["runtime_root"]):
        for fname in files:
            try:
                os.chmod(Path(root) / fname, stat.S_IWRITE | stat.S_IREAD)
            except Exception:
                pass


def test_pilot_pipeline_human_rejection_and_rework(hermetic_pipeline_env: dict):
    env = hermetic_pipeline_env
    coord: PilotCoordinator = env["coordinator"]

    coord.initialize_attempt("JOB-01", "animalidade", "EXTRACTION", attempt_num=1)
    coord.audit_store.record_transition("animalidade", "READY_TO_EXPORT", "export_bundle", "WAITING_FOR_RESULT")
    coord.audit_store.record_transition("animalidade", "WAITING_FOR_RESULT", "import_bundle", "RESULT_IMPORTED")
    coord.audit_store.record_transition("animalidade", "RESULT_IMPORTED", "integrity_passed", "NEEDS_HUMAN_REVIEW")

    req = {"requestId": "REQ-01", "resultBundleId": "RB-01"}
    decision = {
        "decisionId": "DEC-01",
        "requestId": "REQ-01",
        "resultBundleId": "RB-01",
        "reviewedResultManifestSha256": "0" * 64,
        "decision": "REJECT",
        "reviewer": "human-reviewer",
        "reviewNotes": "Missing sections",
        "decidedAt": "2026-09-08T12:00:00Z",
    }

    outcome = coord.submit_human_decision(
        book_id="animalidade",
        decision=decision,
        review_request=req,
        current_result_manifest_hash="0" * 64,
    )
    assert outcome["status"] == "REWORK_REQUIRED"

    # Attempt 2 creation succeeds from REWORK_REQUIRED
    attempt2 = coord.initialize_attempt("JOB-01", "animalidade", "EXTRACTION", attempt_num=2)
    assert attempt2["attemptNumber"] == 2
    assert attempt2["state"] == "READY_TO_EXPORT"


def test_main_worktree_remains_strictly_clean_after_persistence():
    # Verify main repository worktree has no uncommitted changes under data/ or docs/assets/data
    status_output = subprocess.check_output(["git", "status", "--short"], text=True)
    # Filter only data/ or docs/assets/data
    tainted = [line for line in status_output.splitlines() if "data/" in line or "docs/assets/data" in line]
    assert len(tainted) == 0, f"Working tree contaminated: {tainted}"
