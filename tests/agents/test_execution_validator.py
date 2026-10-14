from __future__ import annotations

import copy
import json
import pytest
from dataclasses import FrozenInstanceError

from scripts.agents.contracts import (
    ContractValidationError,
    validate_payload,
)
from scripts.agents.execution_validator import (
    ExecutionResultValidator,
    ExecutionValidationVerdict,
)


@pytest.fixture
def valid_request():
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


@pytest.fixture
def valid_result(valid_request):
    return {
        "schemaVersion": "2.0",
        "executionId": "EXEC-REQ-JOB-TREVAS-001-EXTRACTION-01",
        "requestId": valid_request["requestId"],
        "agent": "extraction-agent",
        "stage": "extraction",
        "status": "SUCCESS",
        "proposedArtifacts": {
            "data/text/trevas-3-0.txt": "Cleaned raw text content of book",
        },
        "evidence": [
            {"book": "trevas-3-0", "page": 1, "section": "Intro"}
        ],
        "uncertainties": [],
        "rawResponse": "{}",
        "metadata": {"durationSeconds": 1.0},
    }


def test_validator_accepts_clean_valid_result(valid_result, valid_request):
    validator = ExecutionResultValidator()
    verdict = validator.validate(valid_result, valid_request)

    assert isinstance(verdict, ExecutionValidationVerdict)
    assert verdict.verdict == "ACCEPT"
    assert verdict.code == "ALLOW"
    assert verdict.reasons != ()


def test_validator_blocks_on_write_scope_violation(valid_result, valid_request):
    validator = ExecutionResultValidator()
    bad_result = copy.deepcopy(valid_result)
    bad_result["proposedArtifacts"]["data/entities/rogue.json"] = "{}"

    verdict = validator.validate(bad_result, valid_request)
    assert verdict.verdict == "BLOCKED"
    assert verdict.code == "ERR_WRITE_SCOPE_VIOLATION"
    assert "data/entities/rogue.json" in str(verdict.reasons)


def test_validator_blocks_on_request_correlation_mismatch(valid_result, valid_request):
    validator = ExecutionResultValidator()
    bad_result = copy.deepcopy(valid_result)
    bad_result["requestId"] = "REQ-MISMATCHED-ID"

    verdict = validator.validate(bad_result, valid_request)
    assert verdict.verdict == "BLOCKED"
    assert verdict.code == "ERR_REQUEST_CORRELATION"


def test_validator_blocks_on_adapter_failure_status(valid_result, valid_request):
    validator = ExecutionResultValidator()
    for status in ["TIMEOUT", "ERROR", "REPAIR_FAILED"]:
        bad_result = copy.deepcopy(valid_result)
        bad_result["status"] = status
        verdict = validator.validate(bad_result, valid_request)
        assert verdict.verdict == "BLOCKED"
        assert status in verdict.code


def test_validator_requests_human_review_on_uncertainties(valid_result, valid_request):
    validator = ExecutionResultValidator()
    review_result = copy.deepcopy(valid_result)
    review_result["uncertainties"] = [
        {"type": "AMBIGUITY", "description": "Unclear text in page 5"}
    ]
    verdict = validator.validate(review_result, valid_request)
    assert verdict.verdict == "HUMAN_REVIEW"
    assert verdict.code == "ERR_SEMANTIC_UNCERTAINTY"


def test_validator_requests_human_review_on_missing_evidence(valid_result, valid_request):
    validator = ExecutionResultValidator()
    no_evidence_result = copy.deepcopy(valid_result)
    no_evidence_result["evidence"] = []  # Has artifacts but no evidence
    verdict = validator.validate(no_evidence_result, valid_request)
    assert verdict.verdict == "HUMAN_REVIEW"
    assert verdict.code == "ERR_EVIDENCE_MISSING"


def test_validator_verdict_immutability(valid_result, valid_request):
    validator = ExecutionResultValidator()
    verdict = validator.validate(valid_result, valid_request)
    with pytest.raises(FrozenInstanceError):
        verdict.verdict = "BLOCKED"  # type: ignore


def test_regression_relations_attempt_1_schema_contract():
    relations_list = [
        {
            "schemaVersion": "1.0",
            "id": "rel-cacador-teologia-001",
            "type": "REQUIRES",
            "sourceEntityId": "kit:cacador-de-bruxas",
            "targetEntityId": "skill:teologia",
            "source": "inquisicao",
            "page": 14,
            "confidence": 1.0,
        }
    ]

    # Attempt 1 bug: validating against single relation.schema.json raises ContractValidationError
    with pytest.raises(ContractValidationError):
        validate_payload("relation.schema.json", relations_list)

    # Validating against relation-collection.schema.json succeeds
    validate_payload("relation-collection.schema.json", relations_list)


def test_execution_validator_accepts_relation_collection_payload():
    relations_list = [
        {
            "schemaVersion": "1.0",
            "id": "rel-cacador-teologia-001",
            "type": "REQUIRES",
            "sourceEntityId": "kit:cacador-de-bruxas",
            "targetEntityId": "skill:teologia",
            "source": "inquisicao",
            "page": 14,
            "confidence": 1.0,
        }
    ]

    request = {
        "schemaVersion": "2.0",
        "requestId": "REQ-JOB-TREVAS-001-RELATIONS",
        "jobId": "JOB-TREVAS-001",
        "bookId": "trevas-3-0",
        "targetStage": "relations",
        "assignedAgent": "relations-agent",
        "allowedWriteScope": [
            "data/entities/relations.json",
        ],
        "executionProfile": "offline-test",
        "contextPack": {
            "schemaVersion": "1.0",
            "contextPackId": "CTX-TREVAS-RELATIONS-001",
            "jobId": "JOB-TREVAS-001",
            "agent": "relations-agent",
            "stage": "relations",
            "mandatory": [],
            "domain": [],
            "bookContext": [],
            "jobContext": [],
            "handoffContext": [],
            "task": {"type": "extract_relations"},
            "outputContract": "schemas/relation-collection.schema.json",
        },
        "taskInstruction": "Extract relations",
        "outputSchemaName": "relation-collection.schema.json",
    }

    result = {
        "schemaVersion": "2.0",
        "executionId": "EXEC-REQ-JOB-TREVAS-001-RELATIONS-01",
        "requestId": "REQ-JOB-TREVAS-001-RELATIONS",
        "agent": "relations-agent",
        "stage": "relations",
        "status": "SUCCESS",
        "proposedArtifacts": {
            "data/entities/relations.json": json.dumps(relations_list),
        },
        "evidence": [
            {"book": "inquisicao", "source": "test", "page": 1}
        ],
        "uncertainties": [],
    }

    validator = ExecutionResultValidator()
    verdict = validator.validate(result, request)

    assert verdict.verdict == "ACCEPT", f"Failed with {verdict.code}: {verdict.reasons}"
    assert verdict.code == "ALLOW"

