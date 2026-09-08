from __future__ import annotations

import hashlib
from pathlib import Path
import pytest

from scripts.agents.application_policy import ApplicationPolicy
from scripts.agents.application_runtime import ApplicationRuntimeConfig, ResourceBounds
from scripts.agents.change_set import ChangeOperation, ChangeSet
from scripts.agents.content_validator import ContentValidator
from scripts.agents.precondition_validator import (
    PreconditionValidationResult,
    PreconditionValidator,
)


def _setup_validator(repo_root: Path) -> tuple[PreconditionValidator, ApplicationRuntimeConfig]:
    config = ApplicationRuntimeConfig.create(repository_root=repo_root)
    policy = ApplicationPolicy(config)
    content_validator = ContentValidator(config.resource_bounds)
    validator = PreconditionValidator(config, policy, content_validator)
    return validator, config


def test_precondition_initial_valid(tmp_path: Path):
    validator, config = _setup_validator(tmp_path)
    # Existing file to update
    file_to_update = tmp_path / "data" / "text" / "existing.txt"
    file_to_update.parent.mkdir(parents=True, exist_ok=True)
    initial_content = "Linha inicial."
    file_to_update.write_text(initial_content, encoding="utf-8")
    base_sha = hashlib.sha256(initial_content.encode("utf-8")).hexdigest()

    ops = (
        ChangeOperation(
            operation_id="op-1",
            type="CREATE",
            target_path="data/text/new_file.txt",
            expected_base_sha256=None,
            candidate_content="Conteúdo novo.",
        ),
        ChangeOperation(
            operation_id="op-2",
            type="UPDATE",
            target_path="data/text/existing.txt",
            expected_base_sha256=base_sha,
            candidate_content="Conteúdo modificado.",
        ),
    )
    cs = ChangeSet(
        change_set_id="cs-1",
        request_id="req-1",
        job_id="job-1",
        book_id="book-1",
        stage="extraction",
        agent="extractor",
        operations=ops,
        metadata={},
    )
    scope = ["data/text/"]
    res = validator.validate_initial(cs, scope)
    assert res.valid is True
    assert res.code is None


def test_precondition_initial_policy_failure(tmp_path: Path):
    validator, config = _setup_validator(tmp_path)
    ops = (
        ChangeOperation(
            operation_id="op-1",
            type="CREATE",
            target_path="scripts/danger.py",
            expected_base_sha256=None,
            candidate_content="print(1)",
        ),
    )
    cs = ChangeSet(
        change_set_id="cs-1",
        request_id="req-1",
        job_id="job-1",
        book_id="book-1",
        stage="extraction",
        agent="extractor",
        operations=ops,
        metadata={},
    )
    res = validator.validate_initial(cs, ["scripts/"])
    assert res.valid is False
    assert res.code in ("ERR_PROTECTED_PATH", "ERR_NON_ALLOWLISTED_PATH")


def test_precondition_initial_create_conflict(tmp_path: Path):
    validator, config = _setup_validator(tmp_path)
    existing_file = tmp_path / "data" / "text" / "already_there.txt"
    existing_file.parent.mkdir(parents=True, exist_ok=True)
    existing_file.write_text("exists", encoding="utf-8")

    ops = (
        ChangeOperation(
            operation_id="op-1",
            type="CREATE",
            target_path="data/text/already_there.txt",
            expected_base_sha256=None,
            candidate_content="new",
        ),
    )
    cs = ChangeSet(
        change_set_id="cs-1",
        request_id="req-1",
        job_id="job-1",
        book_id="book-1",
        stage="extraction",
        agent="extractor",
        operations=ops,
        metadata={},
    )
    res = validator.validate_initial(cs, ["data/text/"])
    assert res.valid is False
    assert res.code == "ERR_CREATE_CONFLICT"
    assert any("already_there.txt" in r for r in res.reasons)


def test_precondition_initial_update_target_not_found(tmp_path: Path):
    validator, config = _setup_validator(tmp_path)
    ops = (
        ChangeOperation(
            operation_id="op-1",
            type="UPDATE",
            target_path="data/text/missing.txt",
            expected_base_sha256="abc123",
            candidate_content="update",
        ),
    )
    cs = ChangeSet(
        change_set_id="cs-1",
        request_id="req-1",
        job_id="job-1",
        book_id="book-1",
        stage="extraction",
        agent="extractor",
        operations=ops,
        metadata={},
    )
    res = validator.validate_initial(cs, ["data/text/"])
    assert res.valid is False
    assert res.code == "ERR_TARGET_NOT_FOUND"


def test_precondition_initial_update_stale_base(tmp_path: Path):
    validator, config = _setup_validator(tmp_path)
    target = tmp_path / "data" / "text" / "existing.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("Hello World", encoding="utf-8")

    ops = (
        ChangeOperation(
            operation_id="op-1",
            type="UPDATE",
            target_path="data/text/existing.txt",
            expected_base_sha256="deadbeef" * 8,
            candidate_content="Updated content",
        ),
    )
    cs = ChangeSet(
        change_set_id="cs-1",
        request_id="req-1",
        job_id="job-1",
        book_id="book-1",
        stage="extraction",
        agent="extractor",
        operations=ops,
        metadata={},
    )
    res = validator.validate_initial(cs, ["data/text/"])
    assert res.valid is False
    assert res.code == "ERR_STALE_BASE"


def test_precondition_toctou_stale_base(tmp_path: Path):
    validator, config = _setup_validator(tmp_path)
    target = tmp_path / "data" / "text" / "live.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("Initial State", encoding="utf-8")
    initial_sha = hashlib.sha256(b"Initial State").hexdigest()

    ops = (
        ChangeOperation(
            operation_id="op-1",
            type="UPDATE",
            target_path="data/text/live.txt",
            expected_base_sha256=initial_sha,
            candidate_content="Next State",
        ),
    )
    cs = ChangeSet(
        change_set_id="cs-1",
        request_id="req-1",
        job_id="job-1",
        book_id="book-1",
        stage="extraction",
        agent="extractor",
        operations=ops,
        metadata={},
    )
    # Initial validation passes
    assert validator.validate_initial(cs, ["data/text/"]).valid is True

    # Simulate concurrent modification on disk before mutation!
    target.write_text("Modified by concurrent process!", encoding="utf-8")

    # TOCTOU recheck must catch stale base and abort fail-closed
    res = validator.validate_toctou_pre_mutation(cs, ["data/text/"])
    assert res.valid is False
    assert res.code == "ERR_STALE_BASE"


def test_precondition_toctou_create_conflict(tmp_path: Path):
    validator, config = _setup_validator(tmp_path)
    ops = (
        ChangeOperation(
            operation_id="op-1",
            type="CREATE",
            target_path="data/text/newly_created.txt",
            expected_base_sha256=None,
            candidate_content="I should be new",
        ),
    )
    cs = ChangeSet(
        change_set_id="cs-1",
        request_id="req-1",
        job_id="job-1",
        book_id="book-1",
        stage="extraction",
        agent="extractor",
        operations=ops,
        metadata={},
    )
    # Initial passes because file does not exist
    assert validator.validate_initial(cs, ["data/text/"]).valid is True

    # Simulate concurrent file creation
    target = tmp_path / "data" / "text" / "newly_created.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("Surprise!", encoding="utf-8")

    # TOCTOU recheck catches concurrent creation
    res = validator.validate_toctou_pre_mutation(cs, ["data/text/"])
    assert res.valid is False
    assert res.code == "ERR_CREATE_CONFLICT"
