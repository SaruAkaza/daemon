from __future__ import annotations

import os
from pathlib import Path
import pytest

from scripts.agents.application_runtime import ApplicationRuntimeConfig, ResourceBounds
from scripts.agents.application_policy import ApplicationPolicy, PolicyEvaluationResult
from scripts.agents.change_set import ChangeOperation, ChangeSet


@pytest.fixture
def runtime_config(tmp_path: Path) -> ApplicationRuntimeConfig:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    staging = tmp_path / "runtime" / "staging"
    staging.mkdir(parents=True)
    audit = tmp_path / "runtime" / "audit"
    audit.mkdir(parents=True)

    return ApplicationRuntimeConfig(
        repository_root=repo,
        staging_root=staging,
        audit_root=audit,
        auto_apply_roots=(
            "data/text/",
            "data/structured/",
            "data/blocks/",
            "data/segments/",
            "data/entities/",
            "data/index/",
            "data/books/",
            "data/work/",
            "data/editorial/",
            "data/pilot/",
            "data/areas/",
            "docs/reports/",
        ),
        protected_roots=(
            "scripts/",
            "schemas/",
            ".github/",
            "tests/",
            "Livros/",
            "coordination/",
            "docs/architecture/",
            "docs/reference/",
            "docs/superpowers/",
            "docs/agents/",
            "docs/missions/",
            "docs/obsidian/",
            "docs/index.html",
            "docs/assets/",
            "AGENTS.md",
            "PROJECT-BRAIN.md",
            "README.md",
        ),
        hard_blocked_roots=(
            ".git/",
            ".daemon_staging/",
            ".daemon_runtime/",
            ".venv/",
            "node_modules/",
        ),
        resource_bounds=ResourceBounds(),
    )


def test_policy_auto_apply_eligible_for_allowlisted_path(runtime_config):
    policy = ApplicationPolicy(runtime_config)
    res = policy.evaluate_path("data/text/trevas.txt", allowed_write_scope=["data/text/**"])
    assert res.allowed is True
    assert res.action == "AUTO_APPLY_ELIGIBLE"
    assert res.code is None


def test_policy_human_review_for_non_allowlisted_path(runtime_config):
    policy = ApplicationPolicy(runtime_config)
    # A path not in auto_apply_roots and not in protected_roots defaults to HUMAN_REVIEW
    res = policy.evaluate_path("new_folder/unknown.txt", allowed_write_scope=["new_folder/**"])
    assert res.allowed is False
    assert res.action == "HUMAN_REVIEW"
    assert res.code == "ERR_NON_ALLOWLISTED_PATH"


def test_policy_human_review_for_protected_path(runtime_config):
    policy = ApplicationPolicy(runtime_config)
    # Even if in allowed_write_scope, protected paths escalate to HUMAN_REVIEW
    res = policy.evaluate_path("scripts/agents/test.py", allowed_write_scope=["scripts/**"])
    assert res.allowed is False
    assert res.action == "HUMAN_REVIEW"
    assert res.code == "ERR_PROTECTED_PATH"


def test_policy_blocked_for_write_scope_violation(runtime_config):
    policy = ApplicationPolicy(runtime_config)
    # Path is in auto_apply_roots, but not in request write scope
    res = policy.evaluate_path("data/text/trevas.txt", allowed_write_scope=["data/structured/**"])
    assert res.allowed is False
    assert res.action == "BLOCKED"
    assert res.code == "ERR_WRITE_SCOPE_VIOLATION"


def test_policy_blocked_for_hard_blocked_paths(runtime_config):
    policy = ApplicationPolicy(runtime_config)
    for p in [".git/config", ".git/HEAD", ".daemon_staging/test.txt", ".venv/lib.py"]:
        res = policy.evaluate_path(p, allowed_write_scope=["**"])
        assert res.allowed is False
        assert res.action == "BLOCKED"
        assert res.code == "ERR_HARD_BLOCKED_PATH"


def test_policy_blocked_for_path_traversal(runtime_config):
    policy = ApplicationPolicy(runtime_config)
    for bad in ["../outside.txt", "data/../../outside.txt", "/abs/path.txt"]:
        res = policy.evaluate_path(bad, allowed_write_scope=["**"])
        assert res.allowed is False
        assert res.action == "BLOCKED"
        assert res.code in ["ERR_PATH_TRAVERSAL", "ERR_HARD_BLOCKED_PATH"]


def test_policy_blocked_for_windows_anomalies(runtime_config):
    policy = ApplicationPolicy(runtime_config)
    # Alternate Data Stream
    res = policy.evaluate_path("data/text/file.txt:stream", allowed_write_scope=["**"])
    assert res.action == "BLOCKED"
    assert res.code == "ERR_HARD_BLOCKED_PATH"

    # Reserved names
    for reserved in ["data/text/con.txt", "data/text/NUL", "data/aux/file.txt", "data/text/com1.json"]:
        res = policy.evaluate_path(reserved, allowed_write_scope=["**"])
        assert res.action == "BLOCKED"
        assert res.code == "ERR_HARD_BLOCKED_PATH"

    # Drive letters & UNC
    for dev in ["C:/Windows/system32", "D:file.txt", "\\\\server\\share\\file.txt"]:
        res = policy.evaluate_path(dev, allowed_write_scope=["**"])
        assert res.action == "BLOCKED"
        assert res.code == "ERR_HARD_BLOCKED_PATH"


def test_policy_case_insensitivity_normalization(runtime_config):
    policy = ApplicationPolicy(runtime_config)
    # Casing differences in allowlist root
    res1 = policy.evaluate_path("DATA/TEXT/file.txt", allowed_write_scope=["data/text/**"])
    assert res1.action == "AUTO_APPLY_ELIGIBLE"

    # Casing differences in protected root
    res2 = policy.evaluate_path("Scripts/Agents/runner.py", allowed_write_scope=["**"])
    assert res2.action == "HUMAN_REVIEW"
    assert res2.code == "ERR_PROTECTED_PATH"


def test_policy_symlink_ancestor_triggers_human_review(runtime_config, tmp_path):
    repo = runtime_config.repository_root
    target_dir = repo / "data" / "text"
    target_dir.mkdir(parents=True, exist_ok=True)

    outside = tmp_path / "outside_dir"
    outside.mkdir()

    symlink_dir = repo / "data" / "linked_text"
    try:
        os.symlink(outside, symlink_dir, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation not permitted in this environment")

    policy = ApplicationPolicy(runtime_config)
    res = policy.evaluate_path("data/linked_text/file.txt", allowed_write_scope=["**"])
    assert res.action == "HUMAN_REVIEW"
    assert res.code == "ERR_SYMLINK_REPARSE_POINT_DETECTED"


def test_policy_evaluate_changeset_whole_batch_fails_to_human_review_if_one_fails(runtime_config):
    policy = ApplicationPolicy(runtime_config)
    op1 = ChangeOperation("OP-1", "CREATE", "data/text/a.txt", None, "A")
    op2 = ChangeOperation("OP-2", "CREATE", "scripts/agents/b.py", None, "B")
    cs = ChangeSet("CS-1", "REQ-1", "JOB-1", "trevas", "extraction", "extraction-agent", (op1, op2), {})

    res = policy.evaluate_changeset(cs, allowed_write_scope=["data/text/**", "scripts/**"])
    assert res.allowed is False
    assert res.action == "HUMAN_REVIEW"
    assert res.code == "ERR_PROTECTED_PATH"


def test_policy_evaluate_changeset_all_eligible(runtime_config):
    policy = ApplicationPolicy(runtime_config)
    op1 = ChangeOperation("OP-1", "CREATE", "data/text/a.txt", None, "A")
    op2 = ChangeOperation("OP-2", "UPDATE", "data/structured/b.json", "a"*64, "{}")
    cs = ChangeSet("CS-1", "REQ-1", "JOB-1", "trevas", "extraction", "extraction-agent", (op1, op2), {})

    res = policy.evaluate_changeset(cs, allowed_write_scope=["data/text/**", "data/structured/**"])
    assert res.allowed is True
    assert res.action == "AUTO_APPLY_ELIGIBLE"
