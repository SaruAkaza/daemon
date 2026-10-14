from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import patch
import pytest

from scripts.agents.application_policy import ApplicationPolicy
from scripts.agents.application_runtime import ApplicationRuntimeConfig
from scripts.agents.change_set import ChangeOperation, ChangeSet
from scripts.agents.change_set_applier import (
    AppliedOperationRecord,
    ChangeSetApplicationOutcome,
    ChangeSetApplier,
)
from scripts.agents.content_validator import ContentValidator
from scripts.agents.filesystem_primitives import FileSystemPrimitives
from scripts.agents.patch_applier import PatchApplier
from scripts.agents.precondition_validator import PreconditionValidator
from scripts.agents.staging_manager import StagingManager


def _build_applier(tmp_path: Path) -> tuple[ChangeSetApplier, ApplicationRuntimeConfig]:
    repo_root = tmp_path / "repo"
    staging_root = tmp_path / ".daemon_staging"
    audit_root = tmp_path / "audit"
    repo_root.mkdir(parents=True)
    staging_root.mkdir(parents=True)
    audit_root.mkdir(parents=True)

    config = ApplicationRuntimeConfig(
        repository_root=repo_root,
        staging_root=staging_root,
        audit_root=audit_root,
    )
    policy = ApplicationPolicy(config)
    content_validator = ContentValidator(config.resource_bounds)
    precondition_validator = PreconditionValidator(config, policy, content_validator)
    patch_applier = PatchApplier()
    staging_manager = StagingManager(config)

    applier = ChangeSetApplier(
        config=config,
        precondition_validator=precondition_validator,
        patch_applier=patch_applier,
        staging_manager=staging_manager,
    )
    return applier, config


def test_apply_changeset_multi_file_success(tmp_path: Path):
    applier, config = _build_applier(tmp_path)

    # Setup existing file for UPDATE
    existing_file = config.repository_root / "data" / "text" / "existing.txt"
    existing_file.parent.mkdir(parents=True)
    initial_text = "Texto original"
    existing_file.write_text(initial_text, encoding="utf-8")
    initial_sha = hashlib.sha256(initial_text.encode("utf-8")).hexdigest()

    ops = (
        ChangeOperation(
            operation_id="op-1",
            type="CREATE",
            target_path="data/text/created.txt",
            expected_base_sha256=None,
            candidate_content="Arquivo criado com sucesso.",
        ),
        ChangeOperation(
            operation_id="op-2",
            type="UPDATE",
            target_path="data/text/existing.txt",
            expected_base_sha256=initial_sha,
            candidate_content="Texto devidamente atualizado.",
        ),
    )
    cs = ChangeSet(
        change_set_id="cs-success",
        request_id="req-1",
        job_id="job-1",
        book_id="book-1",
        stage="extraction",
        agent="extractor",
        operations=ops,
        metadata={},
    )
    scope = ["data/text/"]

    outcome = applier.apply(cs, scope)
    assert outcome.status == "APPLIED"
    assert outcome.failure_code is None
    assert len(outcome.applied_records) == 2

    # Check files on disk
    created_disk = config.repository_root / "data" / "text" / "created.txt"
    assert created_disk.is_file()
    assert created_disk.read_text(encoding="utf-8") == "Arquivo criado com sucesso."

    assert existing_file.read_text(encoding="utf-8") == "Texto devidamente atualizado."


def test_apply_changeset_partial_failure_rollback_success(tmp_path: Path):
    applier, config = _build_applier(tmp_path)

    ops = (
        ChangeOperation(
            operation_id="op-1",
            type="CREATE",
            target_path="data/text/file1.txt",
            expected_base_sha256=None,
            candidate_content="File 1 content",
        ),
        ChangeOperation(
            operation_id="op-2",
            type="CREATE",
            target_path="data/text/file2.txt",
            expected_base_sha256=None,
            candidate_content="File 2 content",
        ),
    )
    cs = ChangeSet(
        change_set_id="cs-rollback",
        request_id="req-1",
        job_id="job-1",
        book_id="book-1",
        stage="extraction",
        agent="extractor",
        operations=ops,
        metadata={},
    )
    scope = ["data/text/"]

    # Mock primitives.exclusive_create so op-1 succeeds, but op-2 raises an error
    orig_exclusive_create = FileSystemPrimitives.exclusive_create

    def mock_exclusive_create(target, source):
        if "file2.txt" in str(target):
            raise IOError("Simulated disk write failure on op-2")
        return orig_exclusive_create(target, source)

    with patch.object(FileSystemPrimitives, "exclusive_create", side_effect=mock_exclusive_create):
        outcome = applier.apply(cs, scope)

    assert outcome.status == "ROLLED_BACK"
    assert outcome.failure_code == "ERR_ATOMIC_COMMIT_FAILED"

    # Verify that file1 was compensated (removed from live disk)
    file1_disk = config.repository_root / "data" / "text" / "file1.txt"
    assert not file1_disk.exists()


def test_apply_changeset_external_mutation_rollback_failed(tmp_path: Path):
    applier, config = _build_applier(tmp_path)

    ops = (
        ChangeOperation(
            operation_id="op-1",
            type="CREATE",
            target_path="data/text/file1.txt",
            expected_base_sha256=None,
            candidate_content="File 1 content",
        ),
        ChangeOperation(
            operation_id="op-2",
            type="CREATE",
            target_path="data/text/file2.txt",
            expected_base_sha256=None,
            candidate_content="File 2 content",
        ),
    )
    cs = ChangeSet(
        change_set_id="cs-tamper",
        request_id="req-1",
        job_id="job-1",
        book_id="book-1",
        stage="extraction",
        agent="extractor",
        operations=ops,
        metadata={},
    )
    scope = ["data/text/"]

    orig_exclusive_create = FileSystemPrimitives.exclusive_create

    def mock_exclusive_create(target, source):
        if "file2.txt" in str(target):
            # Tamper with file1 before failing on file2!
            file1 = config.repository_root / "data" / "text" / "file1.txt"
            file1.write_text("External process modified file1 concurrently!", encoding="utf-8")
            raise IOError("Simulated failure on file2")
        return orig_exclusive_create(target, source)

    with patch.object(FileSystemPrimitives, "exclusive_create", side_effect=mock_exclusive_create):
        outcome = applier.apply(cs, scope)

    assert outcome.status == "ROLLBACK_FAILED"
    assert outcome.failure_code == "ERR_CRITICAL_ROLLBACK_FAILED"

    # Audit preservation must exist
    audit_dir = config.audit_root / "cs-tamper"
    assert audit_dir.exists()
    assert (audit_dir / "journal.json").is_file()
