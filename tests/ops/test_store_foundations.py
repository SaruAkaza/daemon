from pathlib import Path
import pytest

from scripts.agents.contracts import validate_payload, ContractValidationError
from scripts.ops.runtime_locator import get_ops_runtime_dir, get_ops_stores_dir
from scripts.ops.hash_chain import HashChainLogger, IntegrityError
from scripts.ops.command_audit import CommandAuditLog


def test_runtime_locator_canonical_resolution(tmp_path):
    ops_rt = get_ops_runtime_dir(tmp_path)
    assert ops_rt == (tmp_path / ".daemon_runtime" / "ops").resolve() or ops_rt == (tmp_path / "ops").resolve()
    assert ops_rt.name == "ops"

    stores_dir = get_ops_stores_dir(tmp_path)
    assert stores_dir == ops_rt / "stores"


def test_ops_command_schema_validates_canonical_commands():
    valid_cmd = {
        "commandId": "CMD-12345678",
        "commandType": "PAUSE_BOOK",
        "bookId": "trevas-3ed",
        "payload": {"reasonDetail": "Checkpoint inspection"},
        "reason": "Test pause",
        "operatorId": "operator-alice",
        "confirmation": {"confirmed": True},
        "submittedAt": "2026-09-18T10:00:00Z",
    }
    # Should not raise
    validate_payload("ops-command.schema.json", valid_cmd)


def test_ops_command_schema_rejects_invalid_commands():
    # Missing required commandId
    invalid_cmd1 = {
        "commandType": "PAUSE_BOOK",
        "payload": {},
        "reason": "missing id",
        "operatorId": "alice",
        "confirmation": {"confirmed": True},
    }
    with pytest.raises(ContractValidationError):
        validate_payload("ops-command.schema.json", invalid_cmd1)

    # Invalid commandType enum (e.g. PauseBook instead of canonical PAUSE_BOOK)
    invalid_cmd2 = {
        "commandId": "CMD-12345678",
        "commandType": "PauseBook",
        "payload": {},
        "reason": "wrong case",
        "operatorId": "alice",
        "confirmation": {"confirmed": True},
    }
    with pytest.raises(ContractValidationError):
        validate_payload("ops-command.schema.json", invalid_cmd2)

    # Book command missing required bookId
    invalid_cmd_no_book = {
        "commandId": "CMD-12345678",
        "commandType": "PAUSE_BOOK",
        "payload": {},
        "reason": "missing bookId",
        "operatorId": "alice",
        "confirmation": {"confirmed": True},
    }
    with pytest.raises(ContractValidationError):
        validate_payload("ops-command.schema.json", invalid_cmd_no_book)

    # Review command missing required reviewId
    invalid_cmd_no_rev = {
        "commandId": "CMD-12345678",
        "commandType": "APPROVE_REVIEW",
        "bookId": "trevas-3ed",
        "payload": {},
        "reason": "missing reviewId",
        "operatorId": "alice",
        "confirmation": {"confirmed": True},
    }
    with pytest.raises(ContractValidationError):
        validate_payload("ops-command.schema.json", invalid_cmd_no_rev)

    # PRIORITIZE_BOOK with invalid priorityWeight (outside 1..200)
    invalid_cmd_prio = {
        "commandId": "CMD-12345678",
        "commandType": "PRIORITIZE_BOOK",
        "bookId": "trevas-3ed",
        "payload": {"priorityWeight": 250},
        "reason": "out of range weight",
        "operatorId": "alice",
        "confirmation": {"confirmed": True},
    }
    with pytest.raises(ContractValidationError):
        validate_payload("ops-command.schema.json", invalid_cmd_prio)

    # REPROCESS_STAGE with invalid stage
    invalid_cmd_stage = {
        "commandId": "CMD-12345678",
        "commandType": "REPROCESS_STAGE",
        "bookId": "trevas-3ed",
        "payload": {"stage": "INVALID_STAGE"},
        "reason": "bad stage",
        "operatorId": "alice",
        "confirmation": {"confirmed": True},
    }
    with pytest.raises(ContractValidationError):
        validate_payload("ops-command.schema.json", invalid_cmd_stage)

    # operatorId with whitespace-only
    invalid_cmd_op = {
        "commandId": "CMD-12345678",
        "commandType": "PAUSE_BOOK",
        "bookId": "trevas-3ed",
        "payload": {},
        "reason": "blank operator",
        "operatorId": "   ",
        "confirmation": {"confirmed": True},
    }
    with pytest.raises(ContractValidationError):
        validate_payload("ops-command.schema.json", invalid_cmd_op)

    # confirmation with unexpected additional properties
    invalid_cmd_conf = {
        "commandId": "CMD-12345678",
        "commandType": "PAUSE_BOOK",
        "bookId": "trevas-3ed",
        "payload": {},
        "reason": "extra field",
        "operatorId": "alice",
        "confirmation": {"confirmed": True, "hacked": True},
    }
    with pytest.raises(ContractValidationError):
        validate_payload("ops-command.schema.json", invalid_cmd_conf)


def test_hash_chain_logger_lifecycle_and_tamper_detection(tmp_path):
    log_file = tmp_path / "test_audit.jsonl"
    logger = HashChainLogger(log_file)

    rec1 = logger.append_entry({"action": "INITIALIZE", "user": "alice"})
    assert rec1["prevHash"] == "0" * 64
    assert "entryHash" in rec1
    assert len(rec1["entryHash"]) == 64

    rec2 = logger.append_entry({"action": "UPDATE", "val": 42})
    assert rec2["prevHash"] == rec1["entryHash"]
    assert rec2["entryHash"] != rec1["entryHash"]

    # Verify integrity
    valid, count, err = logger.verify_integrity()
    assert valid is True
    assert count == 2
    assert err == ""

    entries = logger.read_all_entries()
    assert len(entries) == 2
    assert entries[0]["action"] == "INITIALIZE"
    assert entries[1]["action"] == "UPDATE"

    # Tamper with first line
    lines = log_file.read_text(encoding="utf-8").splitlines()
    lines[0] = lines[0].replace("alice", "mallory")
    log_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Tamper detection
    valid, failed_line, err = logger.verify_integrity()
    assert valid is False
    assert failed_line == 1
    assert "Hash mismatch" in err or "Integrity" in err

    with pytest.raises(IntegrityError):
        logger.read_all_entries()

    # Re-initialization fail-closed
    with pytest.raises(IntegrityError):
        HashChainLogger(log_file)


def test_tampered_command_audit_blocks_startup(tmp_path):
    audit = CommandAuditLog(stores_dir=tmp_path)
    audit.log_action({"commandId": "CMD-001", "action": "INITIALIZE", "operatorId": "alice"})
    audit.log_action({"commandId": "CMD-002", "action": "MUTATE", "operatorId": "alice"})

    # Tamper with first line
    log_file = tmp_path / "command_audit.jsonl"
    lines = log_file.read_text(encoding="utf-8").splitlines()
    lines[0] = lines[0].replace("INITIALIZE", "COMPROMISED")
    log_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # CommandAuditLog startup fail-closed
    with pytest.raises(IntegrityError):
        CommandAuditLog(stores_dir=tmp_path)
