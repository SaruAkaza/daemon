from pathlib import Path
import pytest

from scripts.agents.contracts import validate_payload
from scripts.agents.orchestrator_state import OrchestratorSelection
from scripts.agents.prepare_pilot_job import (
    PilotJobPreparer,
    SourceCustodyReport,
    PilotReadinessStatus,
)



def test_verify_source_custody_existing_source():
    repo_root = Path(__file__).resolve().parents[2]
    preparer = PilotJobPreparer(repo_root=repo_root)

    report = preparer.verify_source_custody("animalidade")
    assert isinstance(report, SourceCustodyReport)
    assert report.book_id == "animalidade"
    assert report.exists is True
    assert report.status == "VERIFIED"
    assert len(report.sha256) == 64
    assert report.size_bytes > 0
    assert report.source_format == "docx"
    assert "animalidade.docx" in report.source_path.replace("\\", "/")


def test_verify_source_custody_missing_source(tmp_path: Path):
    empty_repo = tmp_path / "empty_repo"
    empty_repo.mkdir()
    preparer = PilotJobPreparer(repo_root=empty_repo)

    report = preparer.verify_source_custody("nonexistent_book")
    assert isinstance(report, SourceCustodyReport)
    assert report.book_id == "nonexistent_book"
    assert report.exists is False
    assert report.status == "MISSING"
    assert report.sha256 is None or report.sha256 == ""


def test_prepare_pilot_environment_success(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    runtime_base = tmp_path / ".daemon_runtime"
    preparer = PilotJobPreparer(repo_root=repo_root)

    status = preparer.prepare_pilot_environment("animalidade", runtime_base=runtime_base)
    assert isinstance(status, PilotReadinessStatus)
    assert status.ready is True
    assert status.book_id == "animalidade"
    assert status.workspace_ready is True
    assert status.schemas_ready is True
    assert status.coordinator_ready is True
    assert status.audit_store_ready is True
    assert status.errors == []

    # Verify directory structure
    assert (runtime_base / "workspaces" / "pilot" / "animalidade" / "repository" / "data" / "pilot").is_dir()
    assert (runtime_base / "bundles" / "outgoing").is_dir()
    assert (runtime_base / "bundles" / "incoming").is_dir()
    assert (runtime_base / "bundles" / "accepted").is_dir()
    assert (runtime_base / "bundles" / "rejected").is_dir()
    assert (runtime_base / "preview" / "animalidade").is_dir()
    assert (runtime_base / "audit" / "pilot" / "animalidade").is_dir()


def test_prepare_pilot_environment_missing_schemas(tmp_path: Path):
    empty_repo = tmp_path / "empty_repo"
    empty_repo.mkdir()
    runtime_base = tmp_path / ".daemon_runtime"
    preparer = PilotJobPreparer(repo_root=empty_repo)

    status = preparer.prepare_pilot_environment("animalidade", runtime_base=runtime_base)
    assert status.ready is False
    assert status.schemas_ready is False
    assert len(status.errors) > 0


def test_emit_infrastructure_verified_checkpoint():
    preparer = PilotJobPreparer()
    checkpoint = preparer.emit_infrastructure_verified_checkpoint()
    assert checkpoint == "INFRASTRUCTURE_VERIFIED"


def test_preparer_never_touches_main_worktree(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    preparer = PilotJobPreparer(repo_root=repo_root)

    # Custody verification
    rep = preparer.verify_source_custody("animalidade")
    assert rep.exists is True

    # Preparation in isolated tmp runtime
    runtime_base = tmp_path / ".daemon_runtime"
    status = preparer.prepare_pilot_environment("animalidade", runtime_base=runtime_base)
    assert status.ready is True

    # Ensure no pilot artifacts leaked into repo data
    assert not (repo_root / "data" / "pilot" / "animalidade").exists()
    assert not (repo_root / "data" / "entities" / "pilot").exists()


def test_prepare_pilot_job_relations_stage_binds_collection_schema_and_v2():
    repo_root = Path(__file__).resolve().parents[2]
    preparer = PilotJobPreparer(repo_root=repo_root)

    # 1. Verify stage configuration defaults
    config = preparer.get_stage_configuration("relations")
    assert config["outputSchemaName"] == "relation-collection.schema.json"
    assert config["allowedWriteScope"] == [
        "data/entities/relations.json",
        "data/entities/unresolved-relations.json",
    ]
    assert config["relationOntologyVersion"] == "relations-v2"

    # 2. Verify building request produces schema-compliant execution-request with exact bindings
    job = {
        "schemaVersion": "1.0",
        "jobId": "JOB-ANIMALIDADE-REL-001",
        "kind": "book_ingestion",
        "bookId": "animalidade",
        "status": "in_progress",
        "createdAt": "2026-09-10T10:00:00-03:00",
        "updatedAt": "2026-09-10T10:00:00-03:00",
        "requestedBy": "human",
        "currentStage": "relations",
        "stages": {
            "source": "pass",
            "extraction": "pass",
            "editorial": "pass",
            "entities": "pass",
            "relations": "ready",
            "frontend": "waiting",
            "qa": "waiting",
            "release": "waiting",
        },
        "humanReviewRequired": False,
        "blockingReasons": [],
        "artifacts": [],
        "history": [
            {
                "timestamp": "2026-09-10T10:00:00-03:00",
                "event": "stage_ready",
                "stage": "relations",
                "message": "Relations stage ready",
            }
        ],
    }
    selection = OrchestratorSelection(
        action="RUN_STAGE",
        code="ALLOW",
        stage="relations",
        agent="relations-agent",
        reasons=("Relations stage ready.",),
    )
    context_pack = {
        "schemaVersion": "1.0",
        "contextPackId": "CTX-ANIMALIDADE-RELATIONS-001",
        "jobId": "JOB-ANIMALIDADE-REL-001",
        "agent": "relations-agent",
        "stage": "relations",
        "mandatory": ["docs/architecture/constitution.md"],
        "domain": ["docs/context/domain/taxonomy.md"],
        "bookContext": ["coordination/books/animalidade.md"],
        "jobContext": [],
        "handoffContext": [],
        "task": {
            "type": "catalog_relations",
            "scope": {
                "bookId": "animalidade",
            },
        },
        "outputContract": "schemas/relation-collection.schema.json",
        "relationOntologyVersion": "relations-v2",
    }

    req = preparer.build_relations_stage_request(job, selection, context_pack)
    assert req["targetStage"] == "relations"
    assert req["assignedAgent"] == "relations-agent"
    assert req["outputSchemaName"] == "relation-collection.schema.json"
    assert req["allowedWriteScope"] == [
        "data/entities/relations.json",
        "data/entities/unresolved-relations.json",
    ]
    assert req["relationOntologyVersion"] == "relations-v2"
    validate_payload("execution-request.schema.json", req)


