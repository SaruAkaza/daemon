from __future__ import annotations

import copy
import json
import pytest
from dataclasses import FrozenInstanceError

from scripts.agents.context_loader import ContextLoader
from scripts.agents.context_materializer import ContextMaterializer
from scripts.agents.contracts import validate_payload
from scripts.agents.execution_adapter import FakeExecutionAdapter, RawExecutionResponse
from scripts.agents.execution_coordinator import (
    ExecutionCoordinator,
    ExecutionCoordinationResult,
)
from scripts.agents.execution_profile import ExecutionProfile
from scripts.agents.execution_validator import ExecutionResultValidator
from scripts.agents.prompt_renderer import PromptRenderer
from scripts.agents.repair_engine import StructuralRepairEngine


@pytest.fixture
def dummy_repo(tmp_path):
    docs = tmp_path / "docs" / "architecture"
    docs.mkdir(parents=True)
    (docs / "constitution.md").write_text("# Constitution\n- Non-invention", encoding="utf-8")

    domain = tmp_path / "docs" / "context" / "domain"
    domain.mkdir(parents=True)
    (domain / "taxonomy.md").write_text("# Taxonomy", encoding="utf-8")

    books = tmp_path / "coordination" / "books"
    books.mkdir(parents=True)
    (books / "trevas.md").write_text("# Trevas Context", encoding="utf-8")

    queue = tmp_path / "coordination" / "queue"
    queue.mkdir(parents=True)
    (queue / "codex.json").write_text('{"job": "active"}', encoding="utf-8")

    schemas = tmp_path / "schemas"
    schemas.mkdir(parents=True)
    (schemas / "agent-handoff.schema.json").write_text('{"title": "Handoff Contract"}', encoding="utf-8")

    return tmp_path


@pytest.fixture
def sample_e2e_request():
    return {
        "schemaVersion": "2.0",
        "requestId": "REQ-JOB-TREVAS-001-EXTRACTION",
        "jobId": "JOB-TREVAS-001",
        "bookId": "trevas-3-0",
        "targetStage": "extraction",
        "assignedAgent": "extraction-agent",
        "allowedWriteScope": [
            "data/text/trevas-3-0.txt",
        ],
        "executionProfile": "offline-test",
        "contextPack": {
            "schemaVersion": "1.0",
            "contextPackId": "CTX-TREVAS-EXTRACTION-001",
            "jobId": "JOB-TREVAS-001",
            "agent": "extraction-agent",
            "stage": "extraction",
            "mandatory": ["docs/architecture/constitution.md"],
            "domain": ["docs/context/domain/taxonomy.md"],
            "bookContext": ["coordination/books/trevas.md"],
            "jobContext": ["coordination/queue/codex.json"],
            "handoffContext": [],
            "task": {
                "type": "extract_raw_text",
                "scope": {"bookId": "trevas-3-0", "pages": [1, 2, 3]},
                "parameters": {"strictCoverage": True},
            },
            "outputContract": "schemas/agent-handoff.schema.json",
        },
        "taskInstruction": "Extract and clean raw text",
        "outputSchemaName": "agent-handoff.schema.json",
        "timeoutSeconds": 120,
    }


@pytest.fixture
def sample_profile():
    return ExecutionProfile(
        profile_id="offline-test",
        provider="fake",
        model="test-fixture",
    )


def test_coordinator_happy_path_e2e(dummy_repo, sample_e2e_request, sample_profile):
    valid_exec_result = {
        "schemaVersion": "2.0",
        "executionId": "EXEC-REQ-JOB-TREVAS-001-EXTRACTION-01",
        "requestId": "REQ-JOB-TREVAS-001-EXTRACTION",
        "agent": "extraction-agent",
        "stage": "extraction",
        "status": "SUCCESS",
        "proposedArtifacts": {
            "data/text/trevas-3-0.txt": "Extracted text content of pages 1 to 3.",
        },
        "evidence": [
            {"book": "trevas-3-0", "page": 1, "section": "Capitulo 1"}
        ],
        "uncertainties": [],
    }
    fake_adapter = FakeExecutionAdapter(
        scripted_responses={
            "REQ-JOB-TREVAS-001-EXTRACTION": RawExecutionResponse(
                content=json.dumps(valid_exec_result),
                status_code="OK",
                duration_seconds=0.5,
            )
        }
    )

    loader = ContextLoader(root=dummy_repo)
    materializer = ContextMaterializer(loader=loader)
    renderer = PromptRenderer()
    repair_engine = StructuralRepairEngine()
    validator = ExecutionResultValidator()

    coordinator = ExecutionCoordinator(
        adapter=fake_adapter,
        materializer=materializer,
        renderer=renderer,
        repair_engine=repair_engine,
        validator=validator,
    )

    result = coordinator.coordinate_execution(sample_e2e_request, sample_profile)

    assert isinstance(result, ExecutionCoordinationResult)
    assert result.verdict.verdict == "ACCEPT"
    assert result.verdict.code == "ALLOW"
    assert result.result["status"] == "SUCCESS"
    assert result.proposed_handoff is not None
    assert result.proposed_handoff["status"] == "pass"
    assert result.proposed_handoff["recommendedNextStage"] == "editorial"
    validate_payload("agent-handoff.schema.json", result.proposed_handoff)

    # Invariant: zero files created on disk
    assert not (dummy_repo / "data" / "text" / "trevas-3-0.txt").exists()


def test_coordinator_structural_repair_e2e(dummy_repo, sample_e2e_request, sample_profile):
    valid_exec_result = {
        "schemaVersion": "2.0",
        "executionId": "EXEC-REQ-JOB-TREVAS-001-EXTRACTION-01",
        "requestId": "REQ-JOB-TREVAS-001-EXTRACTION",
        "agent": "extraction-agent",
        "stage": "extraction",
        "status": "SUCCESS",
        "proposedArtifacts": {
            "data/text/trevas-3-0.txt": "Extracted text content.",
        },
        "evidence": [
            {"book": "trevas-3-0", "page": 1}
        ],
        "uncertainties": [],
    }
    fenced_content = f"Here is output:\n```json\n{json.dumps(valid_exec_result)}\n```"
    fake_adapter = FakeExecutionAdapter(
        scripted_responses={
            "REQ-JOB-TREVAS-001-EXTRACTION": RawExecutionResponse(
                content=fenced_content,
                status_code="OK",
                duration_seconds=0.7,
            )
        }
    )

    loader = ContextLoader(root=dummy_repo)
    coordinator = ExecutionCoordinator(
        adapter=fake_adapter,
        materializer=ContextMaterializer(loader=loader),
    )

    result = coordinator.coordinate_execution(sample_e2e_request, sample_profile)
    assert result.verdict.verdict == "ACCEPT"
    assert result.proposed_handoff is not None


def test_coordinator_write_scope_violation_e2e(dummy_repo, sample_e2e_request, sample_profile):
    violating_result = {
        "schemaVersion": "2.0",
        "executionId": "EXEC-REQ-JOB-TREVAS-001-EXTRACTION-01",
        "requestId": "REQ-JOB-TREVAS-001-EXTRACTION",
        "agent": "extraction-agent",
        "stage": "extraction",
        "status": "SUCCESS",
        "proposedArtifacts": {
            "data/text/trevas-3-0.txt": "Extracted text",
            "schemas/unauthorized.json": "{}",
        },
        "evidence": [{"book": "trevas-3-0", "page": 1}],
        "uncertainties": [],
    }
    fake_adapter = FakeExecutionAdapter(
        scripted_responses={
            "REQ-JOB-TREVAS-001-EXTRACTION": RawExecutionResponse(
                content=json.dumps(violating_result),
                status_code="OK",
                duration_seconds=0.4,
            )
        }
    )

    loader = ContextLoader(root=dummy_repo)
    coordinator = ExecutionCoordinator(
        adapter=fake_adapter,
        materializer=ContextMaterializer(loader=loader),
    )

    result = coordinator.coordinate_execution(sample_e2e_request, sample_profile)
    assert result.verdict.verdict == "BLOCKED"
    assert result.verdict.code == "ERR_WRITE_SCOPE_VIOLATION"
    assert result.proposed_handoff is None


def test_coordinator_uncertainties_e2e(dummy_repo, sample_e2e_request, sample_profile):
    uncertain_result = {
        "schemaVersion": "2.0",
        "executionId": "EXEC-REQ-JOB-TREVAS-001-EXTRACTION-01",
        "requestId": "REQ-JOB-TREVAS-001-EXTRACTION",
        "agent": "extraction-agent",
        "stage": "extraction",
        "status": "SUCCESS",
        "proposedArtifacts": {
            "data/text/trevas-3-0.txt": "Extracted text",
        },
        "evidence": [{"book": "trevas-3-0", "page": 1}],
        "uncertainties": [
            {"type": "OCR_ERROR", "description": "Smudged text on page 2"}
        ],
    }
    fake_adapter = FakeExecutionAdapter(
        scripted_responses={
            "REQ-JOB-TREVAS-001-EXTRACTION": RawExecutionResponse(
                content=json.dumps(uncertain_result),
                status_code="OK",
                duration_seconds=0.4,
            )
        }
    )

    loader = ContextLoader(root=dummy_repo)
    coordinator = ExecutionCoordinator(
        adapter=fake_adapter,
        materializer=ContextMaterializer(loader=loader),
    )

    result = coordinator.coordinate_execution(sample_e2e_request, sample_profile)
    assert result.verdict.verdict == "HUMAN_REVIEW"
    assert result.verdict.code == "ERR_SEMANTIC_UNCERTAINTY"
    assert result.proposed_handoff is None


def test_coordinator_immutability(dummy_repo, sample_e2e_request, sample_profile):
    loader = ContextLoader(root=dummy_repo)
    coordinator = ExecutionCoordinator(
        adapter=FakeExecutionAdapter(),
        materializer=ContextMaterializer(loader=loader),
    )
    result = coordinator.coordinate_execution(sample_e2e_request, sample_profile)
    with pytest.raises(FrozenInstanceError):
        result.proposed_handoff = {}  # type: ignore
