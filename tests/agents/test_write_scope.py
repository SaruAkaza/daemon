from __future__ import annotations

import pytest
from dataclasses import FrozenInstanceError

from scripts.agents.write_scope import (
    WriteScopeDecision,
    WriteScopeValidator,
)


def test_write_scope_exact_match_allowed():
    validator = WriteScopeValidator()
    decision = validator.validate(
        proposed_artifacts={"data/text/trevas.txt": "content"},
        allowed_patterns=["data/text/trevas.txt"],
    )
    assert decision.allowed is True
    assert decision.code == "ALLOW"
    assert decision.violations == ()


def test_write_scope_glob_pattern_allowed():
    validator = WriteScopeValidator()
    decision = validator.validate(
        proposed_artifacts={
            "data/text/trevas.txt": "content 1",
            "data/text/trevas-clean.txt": "content 2",
        },
        allowed_patterns=["data/text/*.txt"],
    )
    assert decision.allowed is True
    assert decision.code == "ALLOW"
    assert decision.violations == ()


def test_write_scope_rejects_path_traversal():
    validator = WriteScopeValidator()
    decision = validator.validate(
        proposed_artifacts={"../schemas/rogue.json": "{}"},
        allowed_patterns=["data/text/*"],
    )
    assert decision.allowed is False
    assert decision.code in ("ERR_WRITE_SCOPE_VIOLATION", "INVALID_PATH")
    assert "../schemas/rogue.json" in decision.violations


def test_write_scope_rejects_absolute_paths():
    validator = WriteScopeValidator()
    for abs_path in ["/etc/passwd", "C:\\Windows\\System32\\cmd.exe", "\\\\unc\\share\\file"]:
        decision = validator.validate(
            proposed_artifacts={abs_path: "malicious"},
            allowed_patterns=["*"],
        )
        assert decision.allowed is False
        assert abs_path in decision.violations


def test_write_scope_rejects_out_of_scope_stage_path():
    validator = WriteScopeValidator()
    decision = validator.validate(
        proposed_artifacts={"data/entities/magias.json": "{}"},
        allowed_patterns=["data/text/trevas-3-0.txt"],
    )
    assert decision.allowed is False
    assert decision.code == "ERR_WRITE_SCOPE_VIOLATION"
    assert "data/entities/magias.json" in decision.violations


def test_write_scope_atomic_rejection_on_single_violation():
    validator = WriteScopeValidator()
    artifacts = {
        "data/text/trevas.txt": "valid content 1",
        "data/handoffs/handoff-extraction.json": "valid content 2",
        "scripts/rogue_script.py": "malicious injection",
    }
    allowed = [
        "data/text/trevas.txt",
        "data/handoffs/handoff-extraction.json",
    ]
    decision = validator.validate(artifacts, allowed)

    assert decision.allowed is False
    assert decision.code == "ERR_WRITE_SCOPE_VIOLATION"
    assert "scripts/rogue_script.py" in decision.violations
    assert len(decision.violations) == 1


def test_write_scope_empty_artifacts_is_allowed():
    validator = WriteScopeValidator()
    decision = validator.validate({}, ["data/text/*"])
    assert decision.allowed is True
    assert decision.code == "ALLOW"


def test_write_scope_immutability():
    validator = WriteScopeValidator()
    decision = validator.validate({"data/text/trevas.txt": "ok"}, ["data/text/*"])
    with pytest.raises(FrozenInstanceError):
        decision.allowed = False  # type: ignore
