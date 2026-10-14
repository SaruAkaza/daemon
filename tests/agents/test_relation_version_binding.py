from __future__ import annotations

import copy
from pathlib import Path
import pytest

from scripts.agents.context_loader import ContextLoader
from scripts.agents.context_pack_builder import (
    ContextPackBuilder,
    ContextPackBuilderError,
)
from scripts.agents.contracts import validate_payload
from scripts.agents.execution_request_builder import (
    ExecutionRequestBuilder,
    ExecutionRequestBuilderError,
)
from scripts.agents.orchestrator_state import OrchestratorSelection


def _create_sample_repo(tmp_path: Path) -> dict[str, Path]:
    docs = {
        "constitution.md": tmp_path / "docs" / "architecture" / "constitution.md",
        "project.md": tmp_path / "docs" / "architecture" / "project-context.md",
        "taxonomy.md": tmp_path / "docs" / "context" / "domain" / "taxonomy.md",
        "book_trevas.md": tmp_path / "coordination" / "books" / "trevas.md",
        "output_schema.json": tmp_path / "schemas" / "agent-handoff.schema.json",
    }
    for rel_path, full_path in docs.items():
        full_path.parent.mkdir(parents=True, exist_ok=True)
        if full_path.suffix == ".json":
            full_path.write_text('{"type": "mock_data"}', encoding="utf-8")
        else:
            full_path.write_text(f"# Content of {rel_path}\n", encoding="utf-8")
    return docs


def _sample_layers() -> dict[str, list[str]]:
    return {
        "mandatory": [
            "docs/architecture/constitution.md",
            "docs/architecture/project-context.md",
        ],
        "domain": [
            "docs/context/domain/taxonomy.md",
        ],
        "bookContext": [
            "coordination/books/trevas.md",
        ],
    }


def _relations_job() -> dict:
    return {
        "schemaVersion": "1.0",
        "jobId": "JOB-TREVAS-REL-001",
        "kind": "book_ingestion",
        "bookId": "trevas-3-0",
        "status": "in_progress",
        "createdAt": "2026-09-08T10:00:00-03:00",
        "updatedAt": "2026-09-08T10:00:00-03:00",
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
                "timestamp": "2026-09-08T10:00:00-03:00",
                "event": "stage_ready",
                "stage": "relations",
                "message": "Relations stage ready",
            }
        ],
    }


def _relations_metadata() -> dict:
    return {
        "schemaVersion": "1.0",
        "contextPackId": "CTX-TREVAS-RELATIONS-001",
        "jobId": "JOB-TREVAS-REL-001",
        "agent": "relations-agent",
        "stage": "relations",
        "task": {
            "type": "catalog_relations",
            "scope": {
                "bookId": "trevas-3-0",
            },
        },
        "outputContract": "schemas/agent-handoff.schema.json",
    }


def _editorial_job() -> dict:
    return {
        "schemaVersion": "1.0",
        "jobId": "JOB-TREVAS-EDIT-001",
        "kind": "book_ingestion",
        "bookId": "trevas-3-0",
        "status": "in_progress",
        "createdAt": "2026-09-08T10:00:00-03:00",
        "updatedAt": "2026-09-08T10:00:00-03:00",
        "requestedBy": "human",
        "currentStage": "editorial",
        "stages": {
            "source": "pass",
            "extraction": "pass",
            "editorial": "ready",
            "entities": "waiting",
            "relations": "waiting",
            "frontend": "waiting",
            "qa": "waiting",
            "release": "waiting",
        },
        "humanReviewRequired": False,
        "blockingReasons": [],
        "artifacts": [],
        "history": [
            {
                "timestamp": "2026-09-08T10:00:00-03:00",
                "event": "stage_ready",
                "stage": "editorial",
                "message": "Editorial stage ready",
            }
        ],
    }


def _editorial_metadata() -> dict:
    return {
        "schemaVersion": "1.0",
        "contextPackId": "CTX-TREVAS-EDITORIAL-001",
        "jobId": "JOB-TREVAS-EDIT-001",
        "agent": "editorial-agent",
        "stage": "editorial",
        "task": {
            "type": "classify_editorial_segments",
            "scope": {
                "bookId": "trevas-3-0",
                "pages": [1, 2, 3],
            },
        },
        "outputContract": "schemas/agent-handoff.schema.json",
    }


def test_relations_stage_requires_v2_for_new_execution(tmp_path: Path):
    """Verifies building relations stage context pack and execution request with relation_ontology_version='relations-v2' succeeds and sets property."""
    _create_sample_repo(tmp_path)
    loader = ContextLoader(root=tmp_path)
    builder = ContextPackBuilder(loader=loader)

    # Context pack build with relations-v2
    pack = builder.build(
        metadata=_relations_metadata(),
        layers=_sample_layers(),
        relation_ontology_version="relations-v2",
    )
    assert pack["relationOntologyVersion"] == "relations-v2"
    validate_payload("context-pack.schema.json", pack)

    # Execution request build with relations-v2
    job = _relations_job()
    selection = OrchestratorSelection(
        action="RUN_STAGE",
        code="ALLOW",
        stage="relations",
        agent="relations-agent",
        reasons=("Relations stage ready.",),
    )
    request = ExecutionRequestBuilder.build_request(
        job=job,
        selection=selection,
        context_pack=pack,
        execution_profile="default-high",
        allowed_write_scope=["data/entities/relations.json"],
        task_instruction="Catalog relations for Trevas under relations-v2",
        output_schema_name="agent-handoff.schema.json",
        relation_ontology_version="relations-v2",
    )
    assert request["relationOntologyVersion"] == "relations-v2"
    validate_payload("execution-request.schema.json", request)

    # Also verify inheriting relationOntologyVersion from context_pack when relation_ontology_version is None
    request_inherited = ExecutionRequestBuilder.build_request(
        job=job,
        selection=selection,
        context_pack=pack,
        execution_profile="default-high",
        allowed_write_scope=["data/entities/relations.json"],
        task_instruction="Catalog relations for Trevas under relations-v2",
        output_schema_name="agent-handoff.schema.json",
    )
    assert request_inherited["relationOntologyVersion"] == "relations-v2"
    validate_payload("execution-request.schema.json", request_inherited)


def test_relations_stage_rejects_v1_for_new_execution(tmp_path: Path):
    """Verifies attempting to build relations stage request with relation_ontology_version='relations-v1' raises ExecutionRequestBuilderError."""
    _create_sample_repo(tmp_path)
    loader = ContextLoader(root=tmp_path)
    builder = ContextPackBuilder(loader=loader)

    # ContextPackBuilder must reject relations-v1 for relations stage
    with pytest.raises(ContextPackBuilderError) as exc_cp_v1:
        builder.build(
            metadata=_relations_metadata(),
            layers=_sample_layers(),
            relation_ontology_version="relations-v1",
        )
    assert "relations-v2" in str(exc_cp_v1.value)

    # ContextPackBuilder must reject None/missing relation_ontology_version for relations stage
    with pytest.raises(ContextPackBuilderError) as exc_cp_none:
        builder.build(
            metadata=_relations_metadata(),
            layers=_sample_layers(),
        )
    assert "relations-v2" in str(exc_cp_none.value)

    # Prepare a valid context pack first (v2) to test ExecutionRequestBuilder
    pack = builder.build(
        metadata=_relations_metadata(),
        layers=_sample_layers(),
        relation_ontology_version="relations-v2",
    )

    job = _relations_job()
    selection = OrchestratorSelection(
        action="RUN_STAGE",
        code="ALLOW",
        stage="relations",
        agent="relations-agent",
    )

    # ExecutionRequestBuilder rejects explicit relations-v1
    with pytest.raises(ExecutionRequestBuilderError) as exc_req_v1:
        ExecutionRequestBuilder.build_request(
            job=job,
            selection=selection,
            context_pack=pack,
            execution_profile="default-high",
            allowed_write_scope=["data/entities/relations.json"],
            task_instruction="Catalog relations",
            output_schema_name="agent-handoff.schema.json",
            relation_ontology_version="relations-v1",
        )
    assert "reject 'relations-v1'" in str(exc_req_v1.value) or "relations-v2" in str(exc_req_v1.value)

    # ExecutionRequestBuilder rejects when context_pack does not have relations-v2 and no version passed
    pack_without_v2 = copy.deepcopy(pack)
    del pack_without_v2["relationOntologyVersion"]
    with pytest.raises(ExecutionRequestBuilderError) as exc_req_none:
        ExecutionRequestBuilder.build_request(
            job=job,
            selection=selection,
            context_pack=pack_without_v2,
            execution_profile="default-high",
            allowed_write_scope=["data/entities/relations.json"],
            task_instruction="Catalog relations",
            output_schema_name="agent-handoff.schema.json",
        )
    assert "relations-v2" in str(exc_req_none.value)


def test_non_relations_stage_ignores_relation_ontology_version(tmp_path: Path):
    """Verifies editorial/entities/source stage builds successfully without requiring relation_ontology_version."""
    _create_sample_repo(tmp_path)
    loader = ContextLoader(root=tmp_path)
    builder = ContextPackBuilder(loader=loader)

    # Context pack for non-relations stage (editorial) builds without relation_ontology_version
    pack = builder.build(
        metadata=_editorial_metadata(),
        layers=_sample_layers(),
    )
    assert "relationOntologyVersion" not in pack
    validate_payload("context-pack.schema.json", pack)

    # Execution request for non-relations stage builds without relation_ontology_version
    job = _editorial_job()
    selection = OrchestratorSelection(
        action="RUN_STAGE",
        code="ALLOW",
        stage="editorial",
        agent="editorial-agent",
    )
    request = ExecutionRequestBuilder.build_request(
        job=job,
        selection=selection,
        context_pack=pack,
        execution_profile="default-high",
        allowed_write_scope=["data/editorial/segments.json"],
        task_instruction="Classify editorial segments",
        output_schema_name="agent-handoff.schema.json",
    )
    assert "relationOntologyVersion" not in request
    validate_payload("execution-request.schema.json", request)
