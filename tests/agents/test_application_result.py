from __future__ import annotations

import pytest

from scripts.agents.application_result import ApplicationResult, AppliedOperationRecord
from scripts.agents.contracts import validate_payload


def test_application_result_valid_schema():
    op = AppliedOperationRecord(
        operation_id="op-1",
        target_path="data/text/test.txt",
        type="CREATE",
        post_apply_sha256="abc123",
        applied_at="2026-09-08T12:00:00Z",
        previous_sha256=None,
        bytes_written=15,
    )
    result = ApplicationResult(
        change_set_id="cs-1",
        request_id="req-1",
        status="APPLIED",
        applied_operations=(op,),
        blocked_operations=(),
        failure_code=None,
        reasons=(),
        applied_at="2026-09-08T12:00:00Z",
        duration_ms=45.2,
        journal=None,
        metadata={"bookId": "book-1"},
    )
    d = result.to_dict()
    # Must validate against schema
    validate_payload("application-result.schema.json", d)
    assert d["status"] == "APPLIED"
    assert len(d["appliedOperations"]) == 1


def test_application_result_all_statuses():
    statuses = [
        "APPLIED",
        "NOT_APPLIED",
        "ROLLED_BACK",
        "ROLLBACK_FAILED",
        "HUMAN_REVIEW",
        "BLOCKED",
    ]
    for st in statuses:
        res = ApplicationResult(
            change_set_id="cs-st",
            request_id="req-st",
            status=st,
            applied_operations=(),
            blocked_operations=(),
            failure_code="ERR_TEST" if st != "APPLIED" else None,
            reasons=("Test reason",),
            applied_at=None,
            duration_ms=10.0,
            journal=None,
            metadata={},
        )
        validate_payload("application-result.schema.json", res.to_dict())
