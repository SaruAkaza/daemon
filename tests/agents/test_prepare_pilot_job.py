from pathlib import Path
import pytest

from scripts.agents.prepare_pilot_job import (
    PilotJobPreparer,
    SourceCustodyReport,
    PilotReadinessStatus,
)


def test_verify_source_custody_existing_source():
    repo_root = Path(__file__).resolve().parents[2]
    preparer = PilotJobPreparer(repo_root=repo_root)

    report = preparer.verify_source_custody("animalidade")
    assert isinstance(report, SourceCustodyReport)
    assert report.book_id == "animalidade"
    assert report.exists is True
    assert report.status == "VERIFIED"
    assert len(report.sha256) == 64
    assert report.size_bytes > 0
    assert report.source_format == "docx"
    assert "animalidade.docx" in report.source_path.replace("\\", "/")


def test_verify_source_custody_missing_source(tmp_path: Path):
    empty_repo = tmp_path / "empty_repo"
    empty_repo.mkdir()
    preparer = PilotJobPreparer(repo_root=empty_repo)

    report = preparer.verify_source_custody("nonexistent_book")
    assert isinstance(report, SourceCustodyReport)
    assert report.book_id == "nonexistent_book"
    assert report.exists is False
    assert report.status == "MISSING"
    assert report.sha256 is None or report.sha256 == ""


def test_prepare_pilot_environment_success(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    runtime_base = tmp_path / ".daemon_runtime"
    preparer = PilotJobPreparer(repo_root=repo_root)

    status = preparer.prepare_pilot_environment("animalidade", runtime_base=runtime_base)
    assert isinstance(status, PilotReadinessStatus)
    assert status.ready is True
    assert status.book_id == "animalidade"
    assert status.workspace_ready is True
    assert status.schemas_ready is True
    assert status.coordinator_ready is True
    assert status.audit_store_ready is True
    assert status.errors == []

    # Verify directory structure
    assert (runtime_base / "workspaces" / "pilot" / "animalidade" / "repository" / "data" / "pilot").is_dir()
    assert (runtime_base / "bundles" / "outgoing").is_dir()
    assert (runtime_base / "bundles" / "incoming").is_dir()
    assert (runtime_base / "bundles" / "accepted").is_dir()
    assert (runtime_base / "bundles" / "rejected").is_dir()
    assert (runtime_base / "preview" / "animalidade").is_dir()
    assert (runtime_base / "audit" / "pilot" / "animalidade").is_dir()


def test_prepare_pilot_environment_missing_schemas(tmp_path: Path):
    empty_repo = tmp_path / "empty_repo"
    empty_repo.mkdir()
    runtime_base = tmp_path / ".daemon_runtime"
    preparer = PilotJobPreparer(repo_root=empty_repo)

    status = preparer.prepare_pilot_environment("animalidade", runtime_base=runtime_base)
    assert status.ready is False
    assert status.schemas_ready is False
    assert len(status.errors) > 0


def test_emit_infrastructure_verified_checkpoint():
    preparer = PilotJobPreparer()
    checkpoint = preparer.emit_infrastructure_verified_checkpoint()
    assert checkpoint == "INFRASTRUCTURE_VERIFIED"


def test_preparer_never_touches_main_worktree(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    preparer = PilotJobPreparer(repo_root=repo_root)

    # Custody verification
    rep = preparer.verify_source_custody("animalidade")
    assert rep.exists is True

    # Preparation in isolated tmp runtime
    runtime_base = tmp_path / ".daemon_runtime"
    status = preparer.prepare_pilot_environment("animalidade", runtime_base=runtime_base)
    assert status.ready is True

    # Ensure no pilot artifacts leaked into repo data
    assert not (repo_root / "data" / "pilot" / "animalidade").exists()
    assert not (repo_root / "data" / "entities" / "pilot").exists()

