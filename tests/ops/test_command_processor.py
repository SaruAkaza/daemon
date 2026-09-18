from pathlib import Path
import pytest

from scripts.ops.command_processor import CommandProcessor, RiskValidationError
from scripts.ops.command_store import CommandStore, CommandConflictError
from scripts.ops.command_audit import CommandAuditLog
from scripts.ops.review_store import ReviewStore


def test_submit_command_returns_202_accepted_without_sync_execution(tmp_path):
    cs = CommandStore(stores_dir=tmp_path)
    audit = CommandAuditLog(stores_dir=tmp_path)
    rs = ReviewStore(stores_dir=tmp_path)
    proc = CommandProcessor(command_store=cs, audit_log=audit, review_store=rs)

    cmd = {
        "commandId": "CMD-ASYNC-001",
        "commandType": "PAUSE_BOOK",
        "bookId": "trevas-3ed",
        "payload": {},
        "reason": "Pause request",
        "operatorId": "alice",
        "confirmation": {"confirmed": True},
    }

    record, http_code = proc.submit_command(cmd)
    assert http_code == 202
    assert record["status"] == "ACCEPTED"
    assert record["commandId"] == "CMD-ASYNC-001"

    # Verify not synchronously processed yet
    assert "trevas-3ed" not in cs.get_control_state().get("pausedBooks", [])


def test_idempotent_resubmission_returns_200(tmp_path):
    cs = CommandStore(stores_dir=tmp_path)
    audit = CommandAuditLog(stores_dir=tmp_path)
    rs = ReviewStore(stores_dir=tmp_path)
    proc = CommandProcessor(command_store=cs, audit_log=audit, review_store=rs)

    cmd = {
        "commandId": "CMD-IDEM-999",
        "commandType": "PRIORITIZE_BOOK",
        "bookId": "demonio-guia",
        "payload": {"priorityWeight": 120},
        "reason": "Priority bump",
        "operatorId": "alice",
        "confirmation": {"confirmed": True},
    }

    rec1, code1 = proc.submit_command(cmd)
    assert code1 == 202

    # Resubmission returns 200
    rec2, code2 = proc.submit_command(cmd)
    assert code2 == 200
    assert rec2["commandId"] == rec1["commandId"]

    # Conflict on changed payload
    cmd_conflict = dict(cmd)
    cmd_conflict["payload"] = {"priorityWeight": 999}
    with pytest.raises(CommandConflictError):
        proc.submit_command(cmd_conflict)


def test_server_side_risk_validation(tmp_path):
    cs = CommandStore(stores_dir=tmp_path)
    audit = CommandAuditLog(stores_dir=tmp_path)
    rs = ReviewStore(stores_dir=tmp_path)
    proc = CommandProcessor(command_store=cs, audit_log=audit, review_store=rs)

    # MEDIUM risk: REPROCESS_STAGE missing reason -> rejected
    cmd_med_no_reason = {
        "commandId": "CMD-MED-00001",
        "commandType": "REPROCESS_STAGE",
        "bookId": "trevas-3ed",
        "payload": {"stage": "EDITORIAL"},
        "reason": "   ",
        "operatorId": "alice",
        "confirmation": {"confirmed": True},
    }
    with pytest.raises(RiskValidationError) as exc1:
        proc.submit_command(cmd_med_no_reason)
    assert "reason" in str(exc1.value).lower()

    # MEDIUM risk: confirmation.confirmed is False -> rejected
    cmd_med_unconfirmed = {
        "commandId": "CMD-MED-00002",
        "commandType": "REPROCESS_STAGE",
        "bookId": "trevas-3ed",
        "payload": {"stage": "EDITORIAL"},
        "reason": "Reprocess due to error",
        "operatorId": "alice",
        "confirmation": {"confirmed": False},
    }
    with pytest.raises(RiskValidationError) as exc2:
        proc.submit_command(cmd_med_unconfirmed)
    assert "confirmation" in str(exc2.value).lower()

    # HIGH risk: APPROVE_REVIEW for POLICY_OR_RIGHTS requires typedConfirmation == bookId
    rs.create_review({
        "reviewId": "REV-RIGHTS-01",
        "bookId": "livro-secreto",
        "stage": "EDITORIAL",
        "category": "POLICY_OR_RIGHTS",
        "problem": "Direitos não claros",
        "evidence": {},
        "recommendation": "Aprovar",
        "impact": "Alto",
    })

    cmd_high_wrong_typed = {
        "commandId": "CMD-HIGH-00001",
        "commandType": "APPROVE_REVIEW",
        "bookId": "livro-secreto",
        "reviewId": "REV-RIGHTS-01",
        "payload": {},
        "reason": "Autorização checada",
        "operatorId": "alice",
        "confirmation": {"confirmed": True, "typedConfirmation": "wrong-book-id"},
    }
    with pytest.raises(RiskValidationError) as exc3:
        proc.submit_command(cmd_high_wrong_typed)
    assert "typedconfirmation" in str(exc3.value).lower()


def test_worker_process_pending_commands_lifecycle(tmp_path):
    cs = CommandStore(stores_dir=tmp_path)
    audit = CommandAuditLog(stores_dir=tmp_path)
    rs = ReviewStore(stores_dir=tmp_path)
    proc = CommandProcessor(command_store=cs, audit_log=audit, review_store=rs)

    # 1. PAUSE_BOOK command
    proc.submit_command({
        "commandId": "CMD-WORK-00001",
        "commandType": "PAUSE_BOOK",
        "bookId": "trevas-3ed",
        "payload": {},
        "reason": "Testing pause",
        "operatorId": "alice",
        "confirmation": {"confirmed": True},
    })

    # 2. PRIORITIZE_BOOK command
    proc.submit_command({
        "commandId": "CMD-WORK-00002",
        "commandType": "PRIORITIZE_BOOK",
        "bookId": "demonio-guia",
        "payload": {"priorityWeight": 175},
        "reason": "Bump priority",
        "operatorId": "bob",
        "confirmation": {"confirmed": True},
    })

    # 3. APPROVE_REVIEW command
    rs.create_review({
        "reviewId": "REV-WORK-01",
        "bookId": "trevas-3ed",
        "stage": "ENTITIES",
        "category": "DOMAIN_AMBIGUITY",
        "problem": "Dúvida",
        "evidence": {},
        "recommendation": "",
        "impact": "",
    })
    proc.submit_command({
        "commandId": "CMD-WORK-00003",
        "commandType": "APPROVE_REVIEW",
        "bookId": "trevas-3ed",
        "reviewId": "REV-WORK-01",
        "payload": {},
        "reason": "Aprovado pelo manual",
        "operatorId": "carlos",
        "confirmation": {"confirmed": True},
    })

    # Execute worker loop
    count = proc.process_pending_commands()
    assert count == 3

    # Check terminal statuses
    assert cs.get_command("CMD-WORK-00001")["status"] == "SUCCEEDED"
    assert cs.get_command("CMD-WORK-00002")["status"] == "SUCCEEDED"
    assert cs.get_command("CMD-WORK-00003")["status"] == "SUCCEEDED"

    # Check state updates
    assert "trevas-3ed" in cs.get_control_state()["pausedBooks"]
    assert cs.get_control_state()["priorityOverrides"]["demonio-guia"] == 175
    assert rs.get_review("REV-WORK-01")["status"] == "RESOLVED"


def test_resume_and_dequeue_and_status(tmp_path):
    cs = CommandStore(stores_dir=tmp_path)
    audit = CommandAuditLog(stores_dir=tmp_path)
    proc = CommandProcessor(command_store=cs, audit_log=audit)

    # Setup initial state
    cs.set_control_override("pausedBooks", ["trevas-3ed", "demonio-guia"])
    cs.set_control_override("priorityOverrides", {"trevas-3ed": 150})

    # 1. RESUME_BOOK
    proc.submit_command({
        "commandId": "CMD-RESUME-00001",
        "commandType": "RESUME_BOOK",
        "bookId": "trevas-3ed",
        "payload": {},
        "reason": "Unpause book",
        "operatorId": "alice",
        "confirmation": {"confirmed": True},
    })

    # 2. DEQUEUE_BOOK
    proc.submit_command({
        "commandId": "CMD-DEQUEUE-00001",
        "commandType": "DEQUEUE_BOOK",
        "bookId": "demonio-guia",
        "payload": {},
        "reason": "Remove from active queue",
        "operatorId": "alice",
        "confirmation": {"confirmed": True},
    })

    proc.process_pending_commands()

    # Check status method
    status_resume = proc.get_command_status("CMD-RESUME-00001")
    assert status_resume is not None
    assert status_resume["status"] == "SUCCEEDED"

    state = cs.get_control_state()
    assert "trevas-3ed" not in state["pausedBooks"]
    assert "demonio-guia" not in state["pausedBooks"]


def test_worker_failure_recording(tmp_path):
    cs = CommandStore(stores_dir=tmp_path)
    audit = CommandAuditLog(stores_dir=tmp_path)
    # ReviewStore is intentionally None to trigger failure on review command execution
    proc = CommandProcessor(command_store=cs, audit_log=audit, review_store=None)

    proc.submit_command({
        "commandId": "CMD-FAIL-000001",
        "commandType": "APPROVE_REVIEW",
        "bookId": "trevas-3ed",
        "reviewId": "REV-NON-EXISTENT",
        "payload": {},
        "reason": "Try to approve without review store",
        "operatorId": "alice",
        "confirmation": {"confirmed": True},
    })

    count = proc.process_pending_commands()
    assert count == 1

    rec = cs.get_command("CMD-FAIL-000001")
    assert rec["status"] == "FAILED"
    assert "ReviewStore is required" in rec["error"]
