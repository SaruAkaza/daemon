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
from scripts.agents.execution_validator import ExecutionResultValidator
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

    # Step 6: Persist through Coordinator into RestrictedPilotWorkspace
    persist_res = coord.apply_persistence(
        book_id=book_id,
        workspace_root=ws_root,
        staging_root=staging_root,
        execution_request=req_payload,
        execution_result=exec_result_payload,
        review_decision=decision_payload,
    )
    assert persist_res["status"] == "PERSISTED"
    assert (ws_root / "data" / "text" / "animalidade.txt").exists()
    assert (ws_root / "data" / "entities" / "creature_npc.json").exists()

    # Step 7: Dataset QA Gates orchestrated by Coordinator
    qa_res = coord.run_qa_validation(book_id=book_id, workspace_root=ws_root, expected_pages=1)
    assert qa_res["status"] == "QA_PASS"
    assert qa_res["verdict"].passed is True

    # Step 8: Local Preview Projection orchestrated by Coordinator
    preview_res = coord.project_preview(
        book_id=book_id,
        workspace_root=ws_root,
        preview_root=preview_root,
        rights_status="UNKNOWN",
        publication_mode="NOT_PUBLIC",
    )
    assert preview_res["status"] == "PREVIEW_READY"
    projected_path = Path(preview_res["path"])
    assert (projected_path / "index.json").exists()

    pilot_complete_res = coord.complete_pilot(book_id=book_id)
    assert pilot_complete_res["status"] == "PILOT_VALIDATED"

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


def test_synthetic_pilot_relations_stage_v2_e2e(hermetic_pipeline_env: dict):
    env = hermetic_pipeline_env
    coord: PilotCoordinator = env["coordinator"]
    ws_root: Path = env["workspace_root"]
    runtime_root: Path = env["runtime_root"]
    preview_root: Path = env["preview_root"]
    staging_root: Path = env["staging_root"]

    book_id = "animalidade"
    job_id = "JOB-ANIM-REL-001"
    request_id = "REQ-ANIM-001-RELATIONS-01"

    # Step 1: Setup workspace with synthetic entities
    entities_dir = ws_root / "data" / "entities"
    entities_dir.mkdir(parents=True, exist_ok=True)

    creature_entities = [
        {
            "id": "creature-sintetico",
            "name": "Criatura Sintetica",
            "category": "creature_npc",
            "source": book_id,
            "page": 1,
            "entries": ["Entidade sintetica para teste hermetico de criatura."],
        }
    ]
    (entities_dir / "creature_npc.json").write_text(
        json.dumps(creature_entities), encoding="utf-8"
    )

    option_entities = [
        {
            "id": "poder-sintetico-1",
            "name": "Poder Sintetico 1",
            "category": "character_option",
            "subtype": "poder",
            "source": book_id,
            "page": 1,
            "entries": ["Entidade sintetica de opcao de poder efetivo."],
        },
        {
            "id": "poder-sintetico-2",
            "name": "Poder Sintetico 2",
            "category": "character_option",
            "subtype": "poder",
            "source": book_id,
            "page": 1,
            "entries": ["Entidade sintetica de opcao selecionavel de poder."],
        },
        {
            "id": "fraqueza-sintetica",
            "name": "Fraqueza Sintetica",
            "category": "character_option",
            "subtype": "aprimoramento",
            "source": book_id,
            "page": 1,
            "entries": ["Entidade sintetica de fraqueza efetiva."],
        },
    ]
    (entities_dir / "character_option.json").write_text(
        json.dumps(option_entities), encoding="utf-8"
    )

    # Step 2: Build Relations Stage ExecutionRequest V2 and export bundle
    attempt_meta = coord.initialize_attempt(job_id, book_id, "RELATIONS", attempt_num=1)
    assert attempt_meta["state"] == "READY_TO_EXPORT"

    req_payload = {
        "schemaVersion": "2.0",
        "requestId": request_id,
        "jobId": job_id,
        "bookId": book_id,
        "targetStage": "relations",
        "assignedAgent": "relations-agent",
        "allowedWriteScope": [
            "data/entities/relations.json",
            "data/entities/unresolved-relations.json",
        ],
        "executionProfile": "manual-antigravity",
        "relationOntologyVersion": "relations-v2",
        "outputSchemaName": "relation-collection.schema.json",
        "taskInstruction": "Catalog synthetic relations under relations-v2 ontology",
        "contextPack": {
            "schemaVersion": "1.0",
            "contextPackId": f"CTX-{request_id}",
            "jobId": job_id,
            "agent": "relations-agent",
            "stage": "relations",
            "mandatory": ["docs/architecture/constitution.md"],
            "domain": ["docs/context/domain/taxonomy.md"],
            "bookContext": ["coordination/books/animalidade.md"],
            "jobContext": [],
            "handoffContext": [],
            "task": {
                "type": "catalog_relations",
                "scope": {"bookId": book_id},
            },
            "outputContract": "schemas/relation-collection.schema.json",
            "relationOntologyVersion": "relations-v2",
        },
    }
    exporter = ExecutionBundleExporter()
    outgoing_dir = runtime_root / "bundles" / "outgoing"
    exported_bundle_dir = exporter.export_bundle(
        req_payload, attempt=1, output_base_dir=outgoing_dir
    )
    coord.record_export(book_id, attempt_num=1, bundle_id=exported_bundle_dir.name)

    with open(exported_bundle_dir / "execution-bundle.json", encoding="utf-8") as f:
        eb_envelope = json.load(f)
    input_manifest_hash = eb_envelope["inputManifestSha256"]

    # Step 3: Construct ResultBundle with proposed artifacts
    incoming_bundle_id = (
        f"RB-ANIM-RELATIONS-att1-{eb_envelope['executionBundleId'].split('-')[-1]}"
    )
    incoming_dir = runtime_root / "bundles" / "incoming" / incoming_bundle_id
    incoming_dir.mkdir(parents=True)
    artifacts_dir = incoming_dir / "artifacts"
    artifacts_dir.mkdir()

    canonical_relations = [
        {
            "schemaVersion": "1.0",
            "id": "rel-sintetico-has-power-001",
            "type": "HAS_POWER",
            "sourceEntityId": "creature-sintetico",
            "targetEntityId": "poder-sintetico-1",
            "source": book_id,
            "page": 1,
            "confidence": 1.0,
        },
        {
            "schemaVersion": "1.0",
            "id": "rel-sintetico-can-choose-power-001",
            "type": "CAN_CHOOSE_POWER",
            "sourceEntityId": "creature-sintetico",
            "targetEntityId": "poder-sintetico-2",
            "source": book_id,
            "page": 1,
            "confidence": 1.0,
        },
        {
            "schemaVersion": "1.0",
            "id": "rel-sintetico-has-weakness-001",
            "type": "HAS_WEAKNESS",
            "sourceEntityId": "creature-sintetico",
            "targetEntityId": "fraqueza-sintetica",
            "source": book_id,
            "page": 1,
            "confidence": 1.0,
        },
    ]
    relations_str = json.dumps(canonical_relations)
    relations_bytes = relations_str.encode("utf-8")
    (artifacts_dir / "relations.json").write_bytes(relations_bytes)
    relations_hash = sha256_bytes(relations_bytes)

    unresolved_relations = [
        {
            "sourceEntityId": "creature-sintetico",
            "candidateRelationType": "CAN_CHOOSE_POWER",
            "rawReferenceText": "Menção a poder externo não catalogado",
            "sourcePage": 1,
            "sourceParagraph": 1,
            "reason": "Target entity not present in local book scope",
            "status": "UNRESOLVED_PENDING_CROSS_BOOK_LINK",
            "candidateTargetEntityId": "external-missing-power",
        }
    ]
    unresolved_str = json.dumps(unresolved_relations)
    unresolved_bytes = unresolved_str.encode("utf-8")
    (artifacts_dir / "unresolved-relations.json").write_bytes(unresolved_bytes)
    unresolved_hash = sha256_bytes(unresolved_bytes)

    exec_result_payload = {
        "schemaVersion": "2.0",
        "executionId": f"EXEC-{request_id}-01",
        "requestId": request_id,
        "agent": "relations-agent",
        "stage": "relations",
        "status": "SUCCESS",
        "proposedArtifacts": {
            "data/entities/relations.json": relations_str,
            "data/entities/unresolved-relations.json": unresolved_str,
        },
        "evidence": [{"book": book_id, "page": 1}],
        "uncertainties": [],
    }
    (incoming_dir / "execution-result.json").write_text(
        json.dumps(exec_result_payload), encoding="utf-8"
    )

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
                "path": "artifacts/relations.json",
                "sha256": relations_hash,
                "sizeBytes": len(relations_bytes),
            },
            {
                "path": "artifacts/unresolved-relations.json",
                "sha256": unresolved_hash,
                "sizeBytes": len(unresolved_bytes),
            },
        ],
        "completedAt": "2026-09-10T10:00:00Z",
    }
    (incoming_dir / "result-manifest.json").write_text(
        json.dumps(result_manifest_payload), encoding="utf-8"
    )

    envelope = ResultBundleEnvelope(
        bundle_id=incoming_bundle_id,
        bundle_dir=incoming_dir,
        result_manifest_path=incoming_dir / "result-manifest.json",
        execution_result_path=incoming_dir / "execution-result.json",
        artifacts_dir=artifacts_dir,
    )

    # Step 4: Validate execution result using ExecutionResultValidator
    validator = ExecutionResultValidator()
    verdict = validator.validate(exec_result_payload, req_payload)
    assert verdict.verdict == "ACCEPT", f"Failed with {verdict.code}: {verdict.reasons}"
    assert verdict.code == "ALLOW"

    # Step 5: Import bundle and run QA gate validation
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

    # Submit human decision APPROVE
    decision_payload = {
        "decisionId": "DEC-ANIM-REL-001",
        "requestId": request_id,
        "resultBundleId": incoming_bundle_id,
        "reviewedResultManifestSha256": res_manifest_hash,
        "decision": "APPROVE",
        "reviewer": "human-editor-carol",
        "reviewNotes": "Relations V2 synthetic integrity approved.",
        "decidedAt": "2026-09-10T10:15:00Z",
    }
    dec_outcome = coord.submit_human_decision(
        book_id=book_id,
        decision=decision_payload,
        review_request=review_req,
        current_result_manifest_hash=res_manifest_hash,
    )
    assert dec_outcome["status"] == "APPROVED"

    # Persist through Coordinator into RestrictedPilotWorkspace
    persist_res = coord.apply_persistence(
        book_id=book_id,
        workspace_root=ws_root,
        staging_root=staging_root,
        execution_request=req_payload,
        execution_result=exec_result_payload,
        review_decision=decision_payload,
    )
    assert persist_res["status"] == "PERSISTED"
    assert (ws_root / "data" / "entities" / "relations.json").exists()
    assert (ws_root / "data" / "entities" / "unresolved-relations.json").exists()

    # QA gate validation
    qa_res = coord.run_qa_validation(book_id=book_id, workspace_root=ws_root, expected_pages=1)
    assert qa_res["status"] == "QA_PASS"
    qa_result = qa_res["verdict"]
    assert qa_result.passed is True
    assert qa_result.relation_count == 3

    # Step 6: Confirm preview projection
    preview_res = coord.project_preview(
        book_id=book_id,
        workspace_root=ws_root,
        preview_root=preview_root,
        rights_status="UNKNOWN",
        publication_mode="NOT_PUBLIC",
    )
    assert preview_res["status"] == "PREVIEW_READY"
    projected_path = Path(preview_res["path"])
    assert (projected_path / "index.json").exists()

    with open(projected_path / "index.json", encoding="utf-8") as pf:
        preview_data = json.load(pf)
    assert len(preview_data.get("relations", [])) == 3
    rel_types = {r["type"] for r in preview_data["relations"]}
    assert rel_types == {"HAS_POWER", "CAN_CHOOSE_POWER", "HAS_WEAKNESS"}

    pilot_complete_res = coord.complete_pilot(book_id=book_id)
    assert pilot_complete_res["status"] == "PILOT_VALIDATED"

    # Cleanup permissions
    for root, _, files in os.walk(env["runtime_root"]):
        for fname in files:
            try:
                os.chmod(Path(root) / fname, stat.S_IWRITE | stat.S_IREAD)
            except Exception:
                pass


