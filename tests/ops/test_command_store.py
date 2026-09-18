from pathlib import Path
import pytest

from scripts.ops.command_store import CommandStore, CommandConflictError
from scripts.ops.command_audit import CommandAuditLog
from scripts.ops.hash_chain import IntegrityError


def test_command_store_save_and_retrieve(tmp_path):
    store = CommandStore(stores_dir=tmp_path)

    cmd = {
        "commandId": "CMD-00000001",
        "commandType": "PAUSE_BOOK",
        "bookId": "trevas-3ed",
        "payload": {},
        "reason": "Test pause",
        "operatorId": "alice",
        "confirmation": {"confirmed": True},
    }

    record, is_dup = store.save_command_intent(cmd)
    assert is_dup is False
    assert record["status"] == "ACCEPTED"
    assert record["commandId"] == "CMD-00000001"
    assert "payloadHash" in record

    retrieved = store.get_command("CMD-00000001")
    assert retrieved == record


def test_durable_idempotency_same_payload(tmp_path):
    store = CommandStore(stores_dir=tmp_path)

    cmd = {
        "commandId": "CMD-IDEM-001",
        "commandType": "PRIORITIZE_BOOK",
        "bookId": "demonio-guia",
        "payload": {"priorityWeight": 150},
        "reason": "Prioritizing demonio-guia",
        "operatorId": "bob",
        "confirmation": {"confirmed": True},
    }

    rec1, is_dup1 = store.save_command_intent(cmd)
    assert is_dup1 is False

    # Second submission with identical payload -> returns cached command
    rec2, is_dup2 = store.save_command_intent(cmd)
    assert is_dup2 is True
    assert rec2["commandId"] == rec1["commandId"]
    assert rec2["payloadHash"] == rec1["payloadHash"]


def test_idempotency_conflict_different_payload(tmp_path):
    store = CommandStore(stores_dir=tmp_path)

    cmd1 = {
        "commandId": "CMD-CONFLICT-001",
        "commandType": "PRIORITIZE_BOOK",
        "bookId": "demonio-guia",
        "payload": {"priorityWeight": 150},
        "reason": "Initial priority",
        "operatorId": "bob",
        "confirmation": {"confirmed": True},
    }
    store.save_command_intent(cmd1)

    cmd2 = dict(cmd1)
    cmd2["payload"] = {"priorityWeight": 200}  # Conflicting payload!

    with pytest.raises(CommandConflictError) as exc:
        store.save_command_intent(cmd2)
    assert "conflict" in str(exc.value).lower() or "different payload" in str(exc.value).lower()


def test_crash_recovery_across_restarts(tmp_path):
    store1 = CommandStore(stores_dir=tmp_path)
    cmd = {
        "commandId": "CMD-RESTART-001",
        "commandType": "PAUSE_BOOK",
        "bookId": "trevas-3ed",
        "payload": {},
        "reason": "Pause for restart",
        "operatorId": "alice",
        "confirmation": {"confirmed": True},
    }
    store1.save_command_intent(cmd)
    store1.set_control_override("pausedBooks", ["trevas-3ed"])

    # Simulate process termination and re-initialization
    store2 = CommandStore(stores_dir=tmp_path)
    recovered = store2.get_command("CMD-RESTART-001")
    assert recovered is not None
    assert recovered["status"] == "ACCEPTED"

    control_state = store2.get_control_state()
    assert "trevas-3ed" in control_state.get("pausedBooks", [])

    # Replay on recovered instance still detects duplicate
    rec, is_dup = store2.save_command_intent(cmd)
    assert is_dup is True


def test_update_command_status_transitions(tmp_path):
    store = CommandStore(stores_dir=tmp_path)
    cmd = {
        "commandId": "CMD-TRANS-001",
        "commandType": "REPROCESS_STAGE",
        "bookId": "trevas-3ed",
        "payload": {"stage": "EDITORIAL"},
        "reason": "Reprocess editorial",
        "operatorId": "alice",
        "confirmation": {"confirmed": True},
    }
    store.save_command_intent(cmd)

    up1 = store.update_command_status("CMD-TRANS-001", "RUNNING")
    assert up1["status"] == "RUNNING"

    up2 = store.update_command_status("CMD-TRANS-001", "SUCCEEDED", result={"processed": True})
    assert up2["status"] == "SUCCEEDED"
    assert up2["result"] == {"processed": True}


def test_command_audit_hash_chain_and_tamper_detection(tmp_path):
    audit = CommandAuditLog(stores_dir=tmp_path)

    entry1 = audit.log_action({
        "commandId": "CMD-AUD-01",
        "commandType": "PAUSE_BOOK",
        "bookId": "b1",
        "operatorId": "alice",
        "action": "ACCEPTED",
    })
    assert entry1["prevHash"] == "0" * 64
    assert "entryHash" in entry1

    entry2 = audit.log_action({
        "commandId": "CMD-AUD-01",
        "commandType": "PAUSE_BOOK",
        "bookId": "b1",
        "operatorId": "alice",
        "action": "SUCCEEDED",
    })
    assert entry2["prevHash"] == entry1["entryHash"]

    assert audit.verify_audit_chain() is True

    # Tamper with log file
    audit_file = tmp_path / "command_audit.jsonl"
    lines = audit_file.read_text(encoding="utf-8").splitlines()
    lines[0] = lines[0].replace("alice", "mallory")
    audit_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    assert audit.verify_audit_chain() is False
