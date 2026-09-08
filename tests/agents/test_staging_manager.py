from __future__ import annotations

from pathlib import Path
from unittest.mock import patch
import pytest

from scripts.agents.application_runtime import ApplicationRuntimeConfig
from scripts.agents.patch_applier import CandidateArtifact
from scripts.agents.staging_manager import StagingManager
from scripts.agents.transaction_journal import TransactionJournal, JournalOperationEntry


def test_verify_same_filesystem_success(tmp_path: Path):
    repo_root = tmp_path / "repo"
    staging_root = tmp_path / ".daemon_staging"
    audit_root = tmp_path / "audit"
    repo_root.mkdir()
    staging_root.mkdir()
    audit_root.mkdir()

    config = ApplicationRuntimeConfig(
        repository_root=repo_root,
        staging_root=staging_root,
        audit_root=audit_root,
    )
    manager = StagingManager(config)
    assert manager.verify_same_filesystem() is True


def test_verify_same_filesystem_cross_volume_rejected(tmp_path: Path):
    repo_root = tmp_path / "repo"
    staging_root = tmp_path / ".daemon_staging"
    audit_root = tmp_path / "audit"
    repo_root.mkdir()
    staging_root.mkdir()
    audit_root.mkdir()

    config = ApplicationRuntimeConfig(
        repository_root=repo_root,
        staging_root=staging_root,
        audit_root=audit_root,
    )
    manager = StagingManager(config)

    # Simulate cross-volume by mocking drive letters or verify_same_filesystem
    with patch.object(manager, "verify_same_filesystem", return_value=False):
        assert manager.verify_same_filesystem() is False
        with pytest.raises(ValueError, match="ERR_CROSS_VOLUME_STAGING"):
            manager.prepare_staging("cs-cross")


def test_prepare_staging_and_stage_candidates(tmp_path: Path):
    repo_root = tmp_path / "repo"
    staging_root = tmp_path / ".daemon_staging"
    audit_root = tmp_path / "audit"
    repo_root.mkdir()
    staging_root.mkdir()
    audit_root.mkdir()

    config = ApplicationRuntimeConfig(
        repository_root=repo_root,
        staging_root=staging_root,
        audit_root=audit_root,
    )
    manager = StagingManager(config)

    staging_dir = manager.prepare_staging("cs-123")
    assert staging_dir.exists()
    assert (staging_dir / "candidates").exists()
    assert (staging_dir / "backups").exists()

    candidates = (
        CandidateArtifact(
            operation_id="op-1",
            target_path="data/text/test.txt",
            content_bytes=b"Hello Candidate",
            candidate_sha256="fake-sha",
            encoding="utf-8",
            format="text",
        ),
    )

    staged_paths = manager.stage_candidates(staging_dir, candidates)
    assert "op-1" in staged_paths
    cand_path = staged_paths["op-1"]
    assert cand_path.is_file()
    assert cand_path.read_bytes() == b"Hello Candidate"


def test_create_backup(tmp_path: Path):
    repo_root = tmp_path / "repo"
    staging_root = tmp_path / ".daemon_staging"
    audit_root = tmp_path / "audit"
    repo_root.mkdir()
    staging_root.mkdir()
    audit_root.mkdir()

    orig_file = repo_root / "data" / "text" / "orig.txt"
    orig_file.parent.mkdir(parents=True)
    orig_file.write_text("Original content", encoding="utf-8")

    config = ApplicationRuntimeConfig(
        repository_root=repo_root,
        staging_root=staging_root,
        audit_root=audit_root,
    )
    manager = StagingManager(config)
    staging_dir = manager.prepare_staging("cs-123")

    backup_path = manager.create_backup(staging_dir, "data/text/orig.txt", repo_root)
    assert backup_path.is_file()
    assert backup_path.read_text(encoding="utf-8") == "Original content"


def test_cleanup_staging(tmp_path: Path):
    repo_root = tmp_path / "repo"
    staging_root = tmp_path / ".daemon_staging"
    audit_root = tmp_path / "audit"
    repo_root.mkdir()
    staging_root.mkdir()
    audit_root.mkdir()

    config = ApplicationRuntimeConfig(
        repository_root=repo_root,
        staging_root=staging_root,
        audit_root=audit_root,
    )
    manager = StagingManager(config)
    staging_dir = manager.prepare_staging("cs-clean")
    assert staging_dir.exists()

    manager.cleanup_staging(staging_dir)
    assert not staging_dir.exists()


def test_preserve_for_audit(tmp_path: Path):
    repo_root = tmp_path / "repo"
    staging_root = tmp_path / ".daemon_staging"
    audit_root = tmp_path / "audit"
    repo_root.mkdir()
    staging_root.mkdir()
    audit_root.mkdir()

    config = ApplicationRuntimeConfig(
        repository_root=repo_root,
        staging_root=staging_root,
        audit_root=audit_root,
    )
    manager = StagingManager(config)
    staging_dir = manager.prepare_staging("cs-audit")

    journal = TransactionJournal(
        change_set_id="cs-audit",
        request_id="req-1",
        started_at="2026-09-08T12:00:00Z",
        staging_dir=str(staging_dir),
        operations=(),
        rollback_attempted=True,
        rollback_succeeded=False,
        filesystem_state="ROLLBACK_FAILED",
    )

    preserved_dir = manager.preserve_for_audit(staging_dir, journal)
    assert preserved_dir.exists()
    journal_file = preserved_dir / "journal.json"
    assert journal_file.is_file()
    assert '"ROLLBACK_FAILED"' in journal_file.read_text(encoding="utf-8")
