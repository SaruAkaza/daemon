from __future__ import annotations

import hashlib
from pathlib import Path
import pytest
from dataclasses import FrozenInstanceError

from scripts.agents.contracts import ContractValidationError, validate_payload
from scripts.agents.execution_validator import ExecutionValidationVerdict


def _make_valid_request(write_scope: list[str] | None = None) -> dict:
    return {
        "schemaVersion": "2.0",
        "requestId": "REQ-JOB-TREVAS-001-EXTRACTION-01",
        "jobId": "JOB-TREVAS-001",
        "bookId": "trevas-3-0",
        "targetStage": "extraction",
        "assignedAgent": "extraction-agent",
        "allowedWriteScope": write_scope or ["data/text/**", "data/structured/**"],
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
        "metadata": {"test": True},
    }


def _make_valid_result(artifacts: dict[str, str] | None = None) -> dict:
    return {
        "schemaVersion": "2.0",
        "executionId": "EXEC-REQ-JOB-TREVAS-001-EXTRACTION-01-01",
        "requestId": "REQ-JOB-TREVAS-001-EXTRACTION-01",
        "agent": "extraction-agent",
        "stage": "extraction",
        "status": "SUCCESS",
        "proposedArtifacts": artifacts if artifacts is not None else {
            "data/text/trevas-3-0.txt": "Extracted content from Trevas 3.0",
        },
        "evidence": [
            {
                "book": "trevas-3-0",
                "page": 1,
                "section": "Introducao",
                "excerpt": "Original excerpt",
            }
        ],
        "uncertainties": [],
        "metadata": {},
    }


def test_changeset_schema_accepts_valid_payload():
    from scripts.agents.change_set import ChangeOperation, ChangeSet

    op = ChangeOperation(
        operation_id="OP-001",
        type="CREATE",
        target_path="data/text/trevas-3-0.txt",
        expected_base_sha256=None,
        candidate_content="Hello world",
        encoding="utf-8",
        format="text",
    )
    cs = ChangeSet(
        change_set_id="CS-REQ-JOB-TREVAS-001-EXTRACTION-01",
        request_id="REQ-JOB-TREVAS-001-EXTRACTION-01",
        job_id="JOB-TREVAS-001",
        book_id="trevas-3-0",
        stage="extraction",
        agent="extraction-agent",
        operations=(op,),
        metadata={"created_by": "test"},
    )
    payload = cs.to_dict()
    validate_payload("change-set.schema.json", payload)
    assert payload["changeSetId"] == "CS-REQ-JOB-TREVAS-001-EXTRACTION-01"
    assert len(payload["operations"]) == 1
    assert payload["operations"][0]["type"] == "CREATE"


def test_changeset_schema_rejects_delete_rename_move():
    from scripts.agents.change_set import ChangeOperation, ChangeSet

    for forbidden_type in ["DELETE", "RENAME", "MOVE", "REMOVE"]:
        payload = {
            "schemaVersion": "2.1",
            "changeSetId": "CS-001",
            "requestId": "REQ-001",
            "jobId": "JOB-001",
            "bookId": "trevas-3-0",
            "stage": "extraction",
            "agent": "extraction-agent",
            "operations": [
                {
                    "operationId": "OP-001",
                    "type": forbidden_type,
                    "targetPath": "data/text/test.txt",
                    "expectedBaseSha256": None,
                    "candidateContent": "",
                    "encoding": "utf-8",
                    "format": "text",
                }
            ],
            "metadata": {},
        }
        with pytest.raises(ContractValidationError):
            validate_payload("change-set.schema.json", payload)


def test_changeset_builder_creates_create_operation_when_file_not_exists(tmp_path: Path):
    from scripts.agents.change_set import ChangeSetBuilder

    builder = ChangeSetBuilder(repo_root=tmp_path)
    request = _make_valid_request()
    result = _make_valid_result({"data/text/new_file.txt": "New content"})
    verdict = ExecutionValidationVerdict(verdict="ACCEPT", reasons=("Valid",), code="ACCEPT")

    cs = builder.build(request, result, verdict=verdict)

    assert cs.change_set_id == f"CS-{request['requestId']}"
    assert len(cs.operations) == 1
    op = cs.operations[0]
    assert op.type == "CREATE"
    assert op.target_path == "data/text/new_file.txt"
    assert op.expected_base_sha256 is None
    assert op.candidate_content == "New content"
    assert op.format == "text"


def test_changeset_builder_creates_update_operation_when_file_exists(tmp_path: Path):
    from scripts.agents.change_set import ChangeSetBuilder

    existing_file = tmp_path / "data" / "text" / "existing.txt"
    existing_file.parent.mkdir(parents=True, exist_ok=True)
    existing_content = "Original existing content"
    existing_file.write_text(existing_content, encoding="utf-8")
    expected_sha = hashlib.sha256(existing_content.encode("utf-8")).hexdigest()

    builder = ChangeSetBuilder(repo_root=tmp_path)
    request = _make_valid_request()
    result = _make_valid_result({"data/text/existing.txt": "Updated content"})
    verdict = ExecutionValidationVerdict(verdict="ACCEPT", reasons=("Valid",), code="ACCEPT")

    cs = builder.build(request, result, verdict=verdict)

    assert len(cs.operations) == 1
    op = cs.operations[0]
    assert op.type == "UPDATE"
    assert op.target_path == "data/text/existing.txt"
    assert op.expected_base_sha256 == expected_sha
    assert op.candidate_content == "Updated content"


def test_changeset_builder_enforces_accept_boundary(tmp_path: Path):
    from scripts.agents.change_set import ChangeSetBuilder

    builder = ChangeSetBuilder(repo_root=tmp_path)
    request = _make_valid_request()
    result = _make_valid_result()

    for non_accept_status in ["HUMAN_REVIEW", "BLOCKED"]:
        verdict = ExecutionValidationVerdict(
            verdict=non_accept_status,
            reasons=(f"Rejected with {non_accept_status}",),
            code="POLICY_VIOLATION",
        )
        with pytest.raises(ValueError, match="ACCEPT"):
            builder.build(request, result, verdict=verdict)


def test_changeset_builder_auto_validates_if_no_verdict_passed(tmp_path: Path):
    from scripts.agents.change_set import ChangeSetBuilder

    builder = ChangeSetBuilder(repo_root=tmp_path)
    request = _make_valid_request()
    result = _make_valid_result()

    cs = builder.build(request, result)
    assert cs is not None
    assert len(cs.operations) == 1


def test_changeset_builder_deterministic_ordering(tmp_path: Path):
    from scripts.agents.change_set import ChangeSetBuilder

    builder = ChangeSetBuilder(repo_root=tmp_path)
    request = _make_valid_request(write_scope=["data/text/**", "data/structured/**"])
    result = _make_valid_result({
        "data/text/z_last.txt": "Z",
        "data/text/a_first.txt": "A",
        "data/structured/m_middle.json": "{}",
    })
    verdict = ExecutionValidationVerdict(verdict="ACCEPT", reasons=("Valid",), code="ACCEPT")

    cs = builder.build(request, result, verdict=verdict)
    paths = [op.target_path for op in cs.operations]
    assert paths == [
        "data/structured/m_middle.json",
        "data/text/a_first.txt",
        "data/text/z_last.txt",
    ]
    assert cs.operations[0].format == "json"


def test_changeset_and_operation_immutability():
    from scripts.agents.change_set import ChangeOperation, ChangeSet

    op = ChangeOperation(
        operation_id="OP-001",
        type="CREATE",
        target_path="data/text/test.txt",
        expected_base_sha256=None,
        candidate_content="text",
    )
    with pytest.raises(FrozenInstanceError):
        op.candidate_content = "modified"  # type: ignore

    cs = ChangeSet(
        change_set_id="CS-001",
        request_id="REQ-001",
        job_id="JOB-001",
        book_id="trevas",
        stage="extraction",
        agent="extraction-agent",
        operations=(op,),
        metadata={},
    )
    with pytest.raises(FrozenInstanceError):
        cs.change_set_id = "CS-002"  # type: ignore


def test_changeset_builder_input_immutability(tmp_path: Path):
    import copy
    from scripts.agents.change_set import ChangeSetBuilder

    builder = ChangeSetBuilder(repo_root=tmp_path)
    request = _make_valid_request()
    result = _make_valid_result()
    req_copy = copy.deepcopy(request)
    res_copy = copy.deepcopy(result)

    builder.build(request, result)
    assert request == req_copy
    assert result == res_copy
