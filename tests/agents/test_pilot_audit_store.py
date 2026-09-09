from __future__ import annotations

import json
from pathlib import Path
import pytest

from scripts.agents.pilot_audit_store import PilotAuditStore, PilotAuditStoreError


def test_record_transition_monotonic_seq(tmp_path: Path):
    store = PilotAuditStore(audit_base_dir=tmp_path)
    store.record_transition("animalidade", "READY_TO_EXPORT", "EXPORT_BUNDLE", "WAITING_FOR_RESULT", {"att": 1})
    store.record_transition("animalidade", "WAITING_FOR_RESULT", "IMPORT_BUNDLE", "RESULT_IMPORTED", {"bundleId": "RB-01"})
    store.record_transition("animalidade", "RESULT_IMPORTED", "VALIDATE_PASS", "NEEDS_HUMAN_REVIEW", {"hash": "abc"})

    history = store.get_audit_history("animalidade")
    assert len(history) == 3
    assert history[0]["seq"] == 1
    assert history[0]["fromState"] == "READY_TO_EXPORT"
    assert history[1]["seq"] == 2
    assert history[1]["toState"] == "RESULT_IMPORTED"
    assert history[2]["seq"] == 3
    assert history[2]["toState"] == "NEEDS_HUMAN_REVIEW"


def test_record_transition_idempotency_deduplication(tmp_path: Path):
    store = PilotAuditStore(audit_base_dir=tmp_path)
    # Recording same transition with same details
    store.record_transition("animalidade", "A", "EV", "B", {"key": "val"})
    store.record_transition("animalidade", "A", "EV", "B", {"key": "val"})

    history = store.get_audit_history("animalidade")
    assert len(history) == 1
    assert history[0]["seq"] == 1


def test_record_review_request_and_decision(tmp_path: Path):
    store = PilotAuditStore(audit_base_dir=tmp_path)
    req_data = {"requestId": "REQ-01", "jobId": "JOB-01", "status": "PENDING"}
    req_path = store.record_review_request("animalidade", req_data)

    assert req_path.exists()
    assert req_path.parent.name == "requests"
    with open(req_path, encoding="utf-8") as f:
        assert json.load(f)["requestId"] == "REQ-01"

    dec_data = {"decisionId": "DEC-01", "requestId": "REQ-01", "decision": "APPROVE"}
    dec_path = store.record_review_decision("animalidade", dec_data)

    assert dec_path.exists()
    assert dec_path.parent.name == "decisions"
    with open(dec_path, encoding="utf-8") as f:
        assert json.load(f)["decisionId"] == "DEC-01"


def test_record_persistence_receipt(tmp_path: Path):
    store = PilotAuditStore(audit_base_dir=tmp_path)
    receipt_data = {"receiptId": "REC-01", "changeSetId": "CS-01", "appliedAt": "2026-09-08T15:00:00Z"}
    receipt_path = store.record_persistence_receipt("animalidade", receipt_data)

    assert receipt_path.exists()
    assert receipt_path.parent.name == "receipts"
    with open(receipt_path, encoding="utf-8") as f:
        assert json.load(f)["receiptId"] == "REC-01"


def test_resilience_to_malformed_lines(tmp_path: Path):
    store = PilotAuditStore(audit_base_dir=tmp_path)
    store.record_transition("animalidade", "S1", "E1", "S2", {})

    log_file = tmp_path / "animalidade" / "transitions.jsonl"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write("CORRUPTED_JSON_LINE\n")
        f.write('{"missing_seq": true}\n')

    store.record_transition("animalidade", "S2", "E2", "S3", {})
    history = store.get_audit_history("animalidade")
    assert len(history) == 2
    assert history[0]["seq"] == 1
    assert history[1]["seq"] == 2


def test_record_review_decision_rejects_unsafe_path_traversal(tmp_path: Path):
    store = PilotAuditStore(audit_base_dir=tmp_path)
    bad_dec = {"decisionId": "../unsafe_dec", "requestId": "REQ-01", "decision": "APPROVE"}
    with pytest.raises(PilotAuditStoreError) as exc:
        store.record_review_decision("animalidade", bad_dec)
    assert "ERR_UNSAFE_IDENTIFIER" in str(exc.value)

    bad_file = tmp_path / "animalidade" / "unsafe_dec.json"
    assert not bad_file.exists()


def test_record_review_request_rejects_unsafe_path_traversal(tmp_path: Path):
    store = PilotAuditStore(audit_base_dir=tmp_path)
    bad_req = {"requestId": "../../bad_req", "jobId": "JOB-01"}
    with pytest.raises(PilotAuditStoreError) as exc:
        store.record_review_request("animalidade", bad_req)
    assert "ERR_UNSAFE_IDENTIFIER" in str(exc.value)
