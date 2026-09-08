from __future__ import annotations

import json
import pytest

from scripts.agents.contracts import validate_payload
from scripts.agents.execution_adapter import RawExecutionResponse
from scripts.agents.repair_engine import (
    RepairExhaustedError,
    StructuralRepairEngine,
)


@pytest.fixture
def sample_request():
    return {
        "schemaVersion": "2.0",
        "requestId": "REQ-JOB-TREVAS-001-EXTRACTION",
        "jobId": "JOB-TREVAS-001",
        "bookId": "trevas-3-0",
        "targetStage": "extraction",
        "assignedAgent": "extraction-agent",
        "allowedWriteScope": [
            "data/text/trevas-3-0.txt",
            "data/handoffs/handoff-extraction.json",
        ],
        "executionProfile": "offline-test",
        "contextPack": {
            "schemaVersion": "1.0",
            "contextPackId": "CTX-TREVAS-EXTRACTION-001",
            "jobId": "JOB-TREVAS-001",
            "agent": "extraction-agent",
            "stage": "extraction",
            "mandatory": [],
            "domain": [],
            "bookContext": [],
            "jobContext": [],
            "handoffContext": [],
            "task": {"type": "extract_raw_text"},
            "outputContract": "schemas/agent-handoff.schema.json",
        },
        "taskInstruction": "Extract text",
        "outputSchemaName": "agent-handoff.schema.json",
    }


def test_parse_clean_json(sample_request):
    raw_payload = {
        "schemaVersion": "2.0",
        "executionId": "EXEC-REQ-001",
        "requestId": "REQ-JOB-TREVAS-001-EXTRACTION",
        "agent": "extraction-agent",
        "stage": "extraction",
        "status": "SUCCESS",
        "proposedArtifacts": {"data/text/trevas-3-0.txt": "Extracted text"},
        "evidence": [{"book": "trevas-3-0", "page": 1}],
        "uncertainties": [],
    }
    raw = RawExecutionResponse(
        content=json.dumps(raw_payload),
        status_code="OK",
        duration_seconds=1.2,
    )
    engine = StructuralRepairEngine()
    result = engine.parse_and_repair(raw, sample_request)

    assert result["status"] == "SUCCESS"
    assert result["requestId"] == "REQ-JOB-TREVAS-001-EXTRACTION"
    assert result["proposedArtifacts"] == {"data/text/trevas-3-0.txt": "Extracted text"}
    validate_payload("execution-result.schema.json", result)


def test_parse_markdown_fenced_json(sample_request):
    raw_payload = {
        "schemaVersion": "2.0",
        "executionId": "EXEC-REQ-002",
        "requestId": "REQ-JOB-TREVAS-001-EXTRACTION",
        "agent": "extraction-agent",
        "stage": "extraction",
        "status": "SUCCESS",
        "proposedArtifacts": {"data/text/trevas-3-0.txt": "Fenced content"},
        "evidence": [{"book": "trevas-3-0", "page": 2}],
        "uncertainties": [],
    }
    raw = RawExecutionResponse(
        content=f"```json\n{json.dumps(raw_payload, indent=2)}\n```",
        status_code="OK",
        duration_seconds=0.8,
    )
    engine = StructuralRepairEngine()
    result = engine.parse_and_repair(raw, sample_request)

    assert result["status"] == "SUCCESS"
    assert result["proposedArtifacts"]["data/text/trevas-3-0.txt"] == "Fenced content"
    validate_payload("execution-result.schema.json", result)


def test_parse_conversational_wrapped_json(sample_request):
    raw_payload = {
        "schemaVersion": "2.0",
        "executionId": "EXEC-REQ-003",
        "requestId": "REQ-JOB-TREVAS-001-EXTRACTION",
        "agent": "extraction-agent",
        "stage": "extraction",
        "status": "SUCCESS",
        "proposedArtifacts": {"data/text/trevas-3-0.txt": "Cleaned"},
        "evidence": [{"book": "trevas-3-0", "page": 3}],
        "uncertainties": [],
    }
    content = (
        "Here is the final execution output according to schema:\n\n"
        f"```json\n{json.dumps(raw_payload)}\n```\n\n"
        "Let me know if you need anything else!"
    )
    raw = RawExecutionResponse(
        content=content,
        status_code="OK",
        duration_seconds=2.0,
    )
    engine = StructuralRepairEngine()
    result = engine.parse_and_repair(raw, sample_request)

    assert result["status"] == "SUCCESS"
    assert result["evidence"][0]["page"] == 3
    validate_payload("execution-result.schema.json", result)


def test_parse_timeout_status(sample_request):
    raw = RawExecutionResponse(
        content="",
        status_code="TIMEOUT",
        duration_seconds=300.0,
    )
    engine = StructuralRepairEngine()
    result = engine.parse_and_repair(raw, sample_request)

    assert result["status"] == "TIMEOUT"
    assert len(result["uncertainties"]) >= 1
    validate_payload("execution-result.schema.json", result)


def test_parse_error_status(sample_request):
    raw = RawExecutionResponse(
        content="Service 503 Unavailable",
        status_code="ERROR",
        duration_seconds=0.1,
    )
    engine = StructuralRepairEngine()
    result = engine.parse_and_repair(raw, sample_request)

    assert result["status"] == "ERROR"
    assert len(result["uncertainties"]) >= 1
    validate_payload("execution-result.schema.json", result)


def test_parse_unrepairable_syntax_marks_repair_failed(sample_request):
    raw = RawExecutionResponse(
        content="Completely malformed non-json content { unclosed",
        status_code="OK",
        duration_seconds=0.5,
    )
    engine = StructuralRepairEngine()
    result = engine.parse_and_repair(raw, sample_request)

    assert result["status"] == "REPAIR_FAILED"
    assert result["proposedArtifacts"] == {}
    assert result["evidence"] == []
    assert len(result["uncertainties"]) >= 1
    validate_payload("execution-result.schema.json", result)
