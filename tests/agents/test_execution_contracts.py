from __future__ import annotations

import copy
import pytest
from pathlib import Path

from scripts.agents.contracts import (
    ContractValidationError,
    load_schema,
    validate_payload,
)
from scripts.agents.orchestrator_state import OrchestratorSelection
from scripts.agents.execution_request_builder import (
    ExecutionRequestBuilder,
    ExecutionRequestBuilderError,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def valid_job_payload():
    return {
        "schemaVersion": "1.0",
        "jobId": "JOB-TREVAS-001",
        "kind": "book_ingestion",
        "bookId": "trevas-3-0",
        "status": "in_progress",
        "createdAt": "2026-09-08T10:00:00-03:00",
        "updatedAt": "2026-09-08T10:00:00-03:00",
        "requestedBy": "human",
        "currentStage": "extraction",
        "stages": {
            "source": "pass",
            "extraction": "ready",
            "editorial": "waiting",
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
                "event": "job_created",
                "stage": "source",
                "message": "Job initiated for Trevas 3.0",
            }
        ],
    }


@pytest.fixture
def valid_context_pack_payload():
    return {
        "schemaVersion": "1.0",
        "contextPackId": "CTX-TREVAS-EXTRACTION-001",
        "jobId": "JOB-TREVAS-001",
        "agent": "extraction-agent",
        "stage": "extraction",
        "mandatory": [
            "docs/architecture/constitution.md",
            "docs/reference/cataloging-rules.md",
        ],
        "domain": [
            "docs/context/domain/taxonomy.md",
        ],
        "bookContext": [
            "coordination/books/trevas.md",
        ],
        "jobContext": [
            "coordination/queue/codex.json",
        ],
        "handoffContext": [],
        "task": {
            "type": "extract_raw_text",
            "scope": {
                "bookId": "trevas-3-0",
                "pages": [1, 2, 3],
            },
            "parameters": {
                "strictCoverage": True,
            },
        },
        "outputContract": "schemas/agent-handoff.schema.json",
    }


@pytest.fixture
def valid_execution_request_payload(valid_context_pack_payload):
    return {
        "schemaVersion": "2.0",
        "requestId": "REQ-TREVAS-001-EXTRACTION-01",
        "jobId": "JOB-TREVAS-001",
        "bookId": "trevas-3-0",
        "targetStage": "extraction",
        "assignedAgent": "extraction-agent",
        "allowedWriteScope": [
            "data/text/trevas-3-0.txt",
            "data/handoffs/handoff-extraction.json",
        ],
        "executionProfile": "default-high",
        "contextPack": copy.deepcopy(valid_context_pack_payload),
        "taskInstruction": "Extract and clean pages 1 to 3 from Trevas 3.0 source text.",
        "outputSchemaName": "agent-handoff.schema.json",
        "timeoutSeconds": 300,
        "metadata": {
            "requestedBy": "orchestrator",
            "timestamp": "2026-09-08T10:05:00-03:00",
        },
    }


@pytest.fixture
def valid_execution_result_payload():
    return {
        "schemaVersion": "2.0",
        "executionId": "EXEC-REQ-TREVAS-001-EXTRACTION-01-01",
        "requestId": "REQ-TREVAS-001-EXTRACTION-01",
        "agent": "extraction-agent",
        "stage": "extraction",
        "status": "SUCCESS",
        "proposedArtifacts": {
            "data/text/trevas-3-0.txt": "Clean text content of pages 1 to 3...",
            "data/handoffs/handoff-extraction.json": '{"status": "pass"}',
        },
        "evidence": [
            {
                "book": "trevas-3-0",
                "page": 1,
                "section": "Introducao",
                "snippet": "Texto original da introducao...",
            }
        ],
        "uncertainties": [
            {
                "type": "OCR_AMBIGUITY",
                "description": "Caractere ilegivel na pagina 2, linha 14.",
                "sourceRef": "trevas-3-0:page2:L14",
                "suggestedResolution": "Conferir na edicao fisica 3a edicao.",
            }
        ],
        "rawResponse": "Response raw text from inference engine",
        "metadata": {
            "durationMs": 4500,
            "provider": "antigravity",
            "model": "gemini-3.7-high",
        },
    }


# ===========================================================================
# 1. ExecutionRequest Schema Tests
# ===========================================================================


def test_load_execution_request_schema():
    schema = load_schema("execution-request.schema.json")
    assert schema["type"] == "object"
    assert "requestId" in schema["required"]
    assert "targetStage" in schema["required"]
    assert "assignedAgent" in schema["required"]
    assert "allowedWriteScope" in schema["required"]
    assert "executionProfile" in schema["required"]
    assert "contextPack" in schema["required"]
    assert "taskInstruction" in schema["required"]
    assert "outputSchemaName" in schema["required"]
    assert schema["additionalProperties"] is False


def test_execution_request_schema_valid(valid_execution_request_payload):
    validate_payload("execution-request.schema.json", valid_execution_request_payload)
    validate_payload("execution-request", valid_execution_request_payload)


def test_execution_request_schema_missing_required(valid_execution_request_payload):
    for req_prop in [
        "schemaVersion",
        "requestId",
        "jobId",
        "bookId",
        "targetStage",
        "assignedAgent",
        "allowedWriteScope",
        "executionProfile",
        "contextPack",
        "taskInstruction",
        "outputSchemaName",
    ]:
        bad_payload = copy.deepcopy(valid_execution_request_payload)
        del bad_payload[req_prop]
        with pytest.raises(ContractValidationError):
            validate_payload("execution-request.schema.json", bad_payload)


def test_execution_request_schema_invalid_stage(valid_execution_request_payload):
    bad = copy.deepcopy(valid_execution_request_payload)
    bad["targetStage"] = "invalid_stage_xyz"
    with pytest.raises(ContractValidationError):
        validate_payload("execution-request.schema.json", bad)


def test_execution_request_schema_invalid_agent(valid_execution_request_payload):
    bad = copy.deepcopy(valid_execution_request_payload)
    bad["assignedAgent"] = "rogue_agent_xyz"
    with pytest.raises(ContractValidationError):
        validate_payload("execution-request.schema.json", bad)


def test_execution_request_schema_disallows_additional_properties(valid_execution_request_payload):
    bad = copy.deepcopy(valid_execution_request_payload)
    bad["unexpectedField"] = "should fail"
    with pytest.raises(ContractValidationError):
        validate_payload("execution-request.schema.json", bad)


# ===========================================================================
# 2. ExecutionResult Schema Tests
# ===========================================================================


def test_load_execution_result_schema():
    schema = load_schema("execution-result.schema.json")
    assert schema["type"] == "object"
    assert "executionId" in schema["required"]
    assert "requestId" in schema["required"]
    assert "agent" in schema["required"]
    assert "stage" in schema["required"]
    assert "status" in schema["required"]
    assert "proposedArtifacts" in schema["required"]
    assert "evidence" in schema["required"]
    assert "uncertainties" in schema["required"]
    assert schema["additionalProperties"] is False


def test_execution_result_schema_valid(valid_execution_result_payload):
    validate_payload("execution-result.schema.json", valid_execution_result_payload)
    validate_payload("execution-result", valid_execution_result_payload)


@pytest.mark.parametrize(
    "status",
    ["SUCCESS", "VALIDATION_FAILED", "REPAIR_FAILED", "TIMEOUT", "ERROR"],
)
def test_execution_result_status_enum_valid(valid_execution_result_payload, status):
    payload = copy.deepcopy(valid_execution_result_payload)
    payload["status"] = status
    validate_payload("execution-result.schema.json", payload)


def test_execution_result_status_invalid(valid_execution_result_payload):
    payload = copy.deepcopy(valid_execution_result_payload)
    payload["status"] = "PARTIAL_SUCCESS"
    with pytest.raises(ContractValidationError):
        validate_payload("execution-result.schema.json", payload)


def test_execution_result_missing_required(valid_execution_result_payload):
    for req_prop in [
        "schemaVersion",
        "executionId",
        "requestId",
        "agent",
        "stage",
        "status",
        "proposedArtifacts",
        "evidence",
        "uncertainties",
    ]:
        bad_payload = copy.deepcopy(valid_execution_result_payload)
        del bad_payload[req_prop]
        with pytest.raises(ContractValidationError):
            validate_payload("execution-result.schema.json", bad_payload)


def test_execution_result_disallows_additional_properties(valid_execution_result_payload):
    bad = copy.deepcopy(valid_execution_result_payload)
    bad["rogueKey"] = 123
    with pytest.raises(ContractValidationError):
        validate_payload("execution-result.schema.json", bad)


# ===========================================================================
# 3. ExecutionRequestBuilder Unit Tests
# ===========================================================================


def test_builder_builds_valid_request(valid_job_payload, valid_context_pack_payload):
    selection = OrchestratorSelection(
        action="RUN_STAGE",
        code="ALLOW",
        stage="extraction",
        agent="extraction-agent",
        reasons=("Stage extraction is ready to run.",),
    )
    request = ExecutionRequestBuilder.build_request(
        job=valid_job_payload,
        selection=selection,
        context_pack=valid_context_pack_payload,
        execution_profile="default-high",
        allowed_write_scope=["data/text/trevas-3-0.txt"],
        task_instruction="Extract text from pages 1-3",
        output_schema_name="agent-handoff.schema.json",
        timeout_seconds=120,
        metadata={"test": True},
    )

    assert request["schemaVersion"] == "2.0"
    assert request["requestId"] == "REQ-JOB-TREVAS-001-EXTRACTION"
    assert request["jobId"] == "JOB-TREVAS-001"
    assert request["bookId"] == "trevas-3-0"
    assert request["targetStage"] == "extraction"
    assert request["assignedAgent"] == "extraction-agent"
    assert request["executionProfile"] == "default-high"
    assert request["allowedWriteScope"] == ["data/text/trevas-3-0.txt"]
    assert request["taskInstruction"] == "Extract text from pages 1-3"
    assert request["outputSchemaName"] == "agent-handoff.schema.json"
    assert request["timeoutSeconds"] == 120
    assert request["metadata"] == {"test": True}

    # Validate output with schema
    validate_payload("execution-request.schema.json", request)


def test_builder_custom_request_id(valid_job_payload, valid_context_pack_payload):
    selection = OrchestratorSelection(
        action="RUN_STAGE",
        code="ALLOW",
        stage="extraction",
        agent="extraction-agent",
    )
    request = ExecutionRequestBuilder.build_request(
        job=valid_job_payload,
        selection=selection,
        context_pack=valid_context_pack_payload,
        execution_profile="default-fast",
        allowed_write_scope=["data/text/trevas-3-0.txt"],
        task_instruction="Extract text",
        output_schema_name="agent-handoff.schema.json",
        request_id="CUSTOM-REQ-999",
    )
    assert request["requestId"] == "CUSTOM-REQ-999"
    validate_payload("execution-request.schema.json", request)


@pytest.mark.parametrize("action", ["WAIT", "BLOCKED", "HUMAN_REVIEW", "READY_FOR_DONE", "NO_ACTION"])
def test_builder_rejects_non_run_stage_selection(valid_job_payload, valid_context_pack_payload, action):
    selection = OrchestratorSelection(
        action=action,
        code="TEST_CODE",
        stage="extraction",
        agent="extraction-agent",
    )
    with pytest.raises(ExecutionRequestBuilderError) as exc_info:
        ExecutionRequestBuilder.build_request(
            job=valid_job_payload,
            selection=selection,
            context_pack=valid_context_pack_payload,
            execution_profile="default-high",
            allowed_write_scope=["data/text/trevas-3-0.txt"],
            task_instruction="Extract text",
            output_schema_name="agent-handoff.schema.json",
        )
    assert "RUN_STAGE" in str(exc_info.value)


def test_builder_rejects_invalid_job_payload(valid_context_pack_payload):
    bad_job = {"invalid": "job"}
    selection = OrchestratorSelection(
        action="RUN_STAGE",
        code="ALLOW",
        stage="extraction",
        agent="extraction-agent",
    )
    with pytest.raises(ExecutionRequestBuilderError) as exc_info:
        ExecutionRequestBuilder.build_request(
            job=bad_job,
            selection=selection,
            context_pack=valid_context_pack_payload,
            execution_profile="default-high",
            allowed_write_scope=["data/text/trevas-3-0.txt"],
            task_instruction="Extract text",
            output_schema_name="agent-handoff.schema.json",
        )
    assert "job" in str(exc_info.value).lower()


def test_builder_rejects_invalid_context_pack(valid_job_payload):
    bad_context_pack = {"invalid": "pack"}
    selection = OrchestratorSelection(
        action="RUN_STAGE",
        code="ALLOW",
        stage="extraction",
        agent="extraction-agent",
    )
    with pytest.raises(ExecutionRequestBuilderError) as exc_info:
        ExecutionRequestBuilder.build_request(
            job=valid_job_payload,
            selection=selection,
            context_pack=bad_context_pack,
            execution_profile="default-high",
            allowed_write_scope=["data/text/trevas-3-0.txt"],
            task_instruction="Extract text",
            output_schema_name="agent-handoff.schema.json",
        )
    assert "context_pack" in str(exc_info.value).lower()


def test_builder_rejects_mismatched_stage(valid_job_payload, valid_context_pack_payload):
    selection = OrchestratorSelection(
        action="RUN_STAGE",
        code="ALLOW",
        stage="editorial",  # Mismatches context_pack (extraction)
        agent="editorial-agent",
    )
    with pytest.raises(ExecutionRequestBuilderError) as exc_info:
        ExecutionRequestBuilder.build_request(
            job=valid_job_payload,
            selection=selection,
            context_pack=valid_context_pack_payload,
            execution_profile="default-high",
            allowed_write_scope=["data/text/trevas-3-0.txt"],
            task_instruction="Editorial task",
            output_schema_name="agent-handoff.schema.json",
        )
    assert "Mismatch" in str(exc_info.value)


def test_builder_does_not_mutate_inputs(valid_job_payload, valid_context_pack_payload):
    job_copy = copy.deepcopy(valid_job_payload)
    context_copy = copy.deepcopy(valid_context_pack_payload)
    write_scope = ["data/text/trevas-3-0.txt"]
    meta = {"key": "val"}

    selection = OrchestratorSelection(
        action="RUN_STAGE",
        code="ALLOW",
        stage="extraction",
        agent="extraction-agent",
    )

    request = ExecutionRequestBuilder.build_request(
        job=valid_job_payload,
        selection=selection,
        context_pack=valid_context_pack_payload,
        execution_profile="default-high",
        allowed_write_scope=write_scope,
        task_instruction="Extract text",
        output_schema_name="agent-handoff.schema.json",
        metadata=meta,
    )

    assert valid_job_payload == job_copy
    assert valid_context_pack_payload == context_copy

    # Check deepcopy of allowed_write_scope and metadata in returned request
    write_scope.append("mutated/path.txt")
    meta["mutated"] = True
    assert "mutated/path.txt" not in request["allowedWriteScope"]
    assert "mutated" not in request["metadata"]
