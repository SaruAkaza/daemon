from __future__ import annotations

import pytest

from scripts.agents.transaction_journal import JournalOperationEntry, TransactionJournal


def test_journal_operation_entry_immutability():
    entry = JournalOperationEntry(
        operation_id="op-1",
        type="CREATE",
        target_path="data/text/file.txt",
        original_exists=False,
        expected_base_sha256=None,
        candidate_sha256="abc123sha",
        applied_status="NOT_APPLIED",
    )
    with pytest.raises(Exception):
        entry.applied_status = "APPLIED"  # frozen


def test_transaction_journal_transitions():
    entry1 = JournalOperationEntry(
        operation_id="op-1",
        type="CREATE",
        target_path="data/text/file1.txt",
        original_exists=False,
        expected_base_sha256=None,
        candidate_sha256="sha1",
        applied_status="NOT_APPLIED",
    )
    journal = TransactionJournal(
        change_set_id="cs-1",
        request_id="req-1",
        started_at="2026-09-08T10:00:00Z",
        staging_dir="/tmp/staging",
        operations=(entry1,),
        filesystem_state="IN_FLIGHT",
    )

    updated_entry = JournalOperationEntry(
        operation_id="op-1",
        type="CREATE",
        target_path="data/text/file1.txt",
        original_exists=False,
        expected_base_sha256=None,
        candidate_sha256="sha1",
        applied_status="APPLIED",
        applied_at="2026-09-08T10:01:00Z",
        observed_post_apply_sha256="sha1",
    )
    journal2 = journal.with_updated_operation(updated_entry)

    assert journal2.operations[0].applied_status == "APPLIED"
    assert journal.operations[0].applied_status == "NOT_APPLIED"  # original unchanged


def test_transaction_journal_to_dict():
    entry = JournalOperationEntry(
        operation_id="op-1",
        type="CREATE",
        target_path="data/text/file.txt",
        original_exists=False,
        expected_base_sha256=None,
        candidate_sha256="sha",
        applied_status="APPLIED",
    )
    journal = TransactionJournal(
        change_set_id="cs-1",
        request_id="req-1",
        started_at="2026-09-08T10:00:00Z",
        staging_dir="/tmp/staging",
        operations=(entry,),
        filesystem_state="CLEAN",
    )
    d = journal.to_dict()
    assert d["changeSetId"] == "cs-1"
    assert len(d["operations"]) == 1
    assert d["operations"][0]["operationId"] == "op-1"
    assert d["filesystemState"] == "CLEAN"
