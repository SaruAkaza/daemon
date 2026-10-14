from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import patch
import pytest

from scripts.agents.application_coordinator import ApplicationCoordinator
from scripts.agents.application_policy import ApplicationPolicy
from scripts.agents.application_runtime import ApplicationRuntimeConfig
from scripts.agents.change_set import ChangeSetBuilder
from scripts.agents.change_set_applier import ChangeSetApplier
from scripts.agents.content_validator import ContentValidator
from scripts.agents.execution_adapter import FakeExecutionAdapter, RawExecutionResponse
from scripts.agents.execution_coordinator import ExecutionCoordinator
from scripts.agents.execution_validator import ExecutionResultValidator, ExecutionValidationVerdict
from scripts.agents.filesystem_primitives import FileSystemPrimitives
from scripts.agents.patch_applier import PatchApplier
from scripts.agents.precondition_validator import PreconditionValidator
from scripts.agents.staging_manager import StagingManager


@pytest.fixture
def repo_env(tmp_path: Path):
    """Hermetic repository environment with Daemon Tools layout."""
    repo = tmp_path / "repo"
    staging = tmp_path / ".daemon_staging"
    audit = tmp_path / "audit"

    # Directory layout
    for d in ["data/text", "data/structured", "scripts", "docs/reports/audit"]:
        (repo / d).mkdir(parents=True, exist_ok=True)
    staging.mkdir(parents=True, exist_ok=True)
    audit.mkdir(parents=True, exist_ok=True)

    config = ApplicationRuntimeConfig(
        repository_root=repo,
        staging_root=staging,
        audit_root=audit,
    )
    builder = ChangeSetBuilder(repository_root=repo)
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
    coordinator = ApplicationCoordinator(
        config=config,
        builder=builder,
        policy=policy,
        applier=applier,
    )
    return {
        "repo": repo,
        "staging": staging,
        "audit": audit,
        "config": config,
        "coordinator": coordinator,
    }


def _make_e2e_request(req_id: str, scope: list[str]) -> dict:
    return {
        "schemaVersion": "2.0",
        "requestId": req_id,
        "jobId": "JOB-E2E-001",
        "bookId": "trevas-3-0",
        "targetStage": "extraction",
        "assignedAgent": "extraction-agent",
        "allowedWriteScope": scope,
        "executionProfile": "offline-test",
        "contextPack": {
            "schemaVersion": "1.0",
            "contextPackId": "CTX-E2E-001",
            "jobId": "JOB-E2E-001",
            "agent": "extraction-agent",
            "stage": "extraction",
            "mandatory": ["docs/architecture/constitution.md"],
            "domain": ["docs/context/domain/taxonomy.md"],
            "bookContext": ["coordination/books/trevas.md"],
            "jobContext": ["coordination/queue/codex.json"],
            "handoffContext": [],
            "task": {
                "type": "extract_raw_text",
                "scope": {"bookId": "trevas-3-0", "pages": [1]},
                "parameters": {"strictCoverage": True},
            },
            "outputContract": "schemas/agent-handoff.schema.json",
        },
        "taskInstruction": "Extract spells into data/text/",
        "outputSchemaName": "agent-handoff.schema.json",
        "timeoutSeconds": 60,
        "metadata": {"test": True},
    }


def _make_e2e_result(req_id: str, artifacts: dict[str, str]) -> dict:
    return {
        "schemaVersion": "2.0",
        "executionId": f"EXEC-{req_id}-01",
        "requestId": req_id,
        "agent": "extraction-agent",
        "stage": "extraction",
        "status": "SUCCESS",
        "proposedArtifacts": artifacts,
        "evidence": [
            {
                "book": "trevas-3-0",
                "page": 1,
                "section": "Magias",
                "snippet": "Bola de fogo",
            }
        ],
        "uncertainties": [],
        "metadata": {},
    }


def test_e2e_happy_path_applied(repo_env):
    coord: ApplicationCoordinator = repo_env["coordinator"]
    repo: Path = repo_env["repo"]

    req = _make_e2e_request("REQ-E2E-SUCCESS", ["data/text/**"])
    res = _make_e2e_result("REQ-E2E-SUCCESS", {
        "data/text/spells.txt": "Bola de fogo: 6d6 de dano.",
    })
    verdict = ExecutionValidationVerdict(verdict="ACCEPT", code="ACCEPT", reasons=())

    app_result = coord.coordinate_application(req, res, verdict)
    assert app_result.status == "APPLIED"
    assert app_result.failure_code is None
    assert len(app_result.applied_operations) == 1

    # Verify physical file on disk
    target = repo / "data" / "text" / "spells.txt"
    assert target.is_file()
    assert "Bola de fogo: 6d6 de dano." in target.read_text(encoding="utf-8")


def test_e2e_protected_path_human_review(repo_env):
    coord: ApplicationCoordinator = repo_env["coordinator"]
    repo: Path = repo_env["repo"]

    req = _make_e2e_request("REQ-E2E-PROTECTED", ["scripts/**"])
    res = _make_e2e_result("REQ-E2E-PROTECTED", {
        "scripts/danger.py": "print('exploit')",
    })
    verdict = ExecutionValidationVerdict(verdict="ACCEPT", code="ACCEPT", reasons=())

    app_result = coord.coordinate_application(req, res, verdict)
    assert app_result.status == "HUMAN_REVIEW"
    assert app_result.failure_code in ("ERR_PROTECTED_PATH", "ERR_NON_ALLOWLISTED_PATH")
    assert not (repo / "scripts" / "danger.py").exists()


def test_e2e_non_allowlisted_path_human_review(repo_env):
    coord: ApplicationCoordinator = repo_env["coordinator"]
    repo: Path = repo_env["repo"]

    req = _make_e2e_request("REQ-E2E-CUSTOM", ["custom_dir/**"])
    res = _make_e2e_result("REQ-E2E-CUSTOM", {
        "custom_dir/notes.txt": "some notes",
    })
    verdict = ExecutionValidationVerdict(verdict="ACCEPT", code="ACCEPT", reasons=())

    app_result = coord.coordinate_application(req, res, verdict)
    assert app_result.status == "HUMAN_REVIEW"
    assert app_result.failure_code == "ERR_NON_ALLOWLISTED_PATH"
    assert not (repo / "custom_dir" / "notes.txt").exists()


def test_e2e_hard_blocked_path_blocked(repo_env):
    coord: ApplicationCoordinator = repo_env["coordinator"]
    repo: Path = repo_env["repo"]

    req = _make_e2e_request("REQ-E2E-GIT", [".git/**"])
    res = _make_e2e_result("REQ-E2E-GIT", {
        ".git/config": "corrupted",
    })
    verdict = ExecutionValidationVerdict(verdict="ACCEPT", code="ACCEPT", reasons=())

    app_result = coord.coordinate_application(req, res, verdict)
    assert app_result.status == "BLOCKED"
    assert app_result.failure_code == "ERR_HARD_BLOCKED_PATH"


def test_e2e_toctou_stale_base_not_applied(repo_env):
    coord: ApplicationCoordinator = repo_env["coordinator"]
    repo: Path = repo_env["repo"]

    # Pre-existing file
    target = repo / "data" / "text" / "existing.txt"
    target.write_text("Versao inicial", encoding="utf-8")

    req = _make_e2e_request("REQ-E2E-TOCTOU", ["data/text/**"])
    res = _make_e2e_result("REQ-E2E-TOCTOU", {
        "data/text/existing.txt": "Versao nova",
    })
    verdict = ExecutionValidationVerdict(verdict="ACCEPT", code="ACCEPT", reasons=())

    # Tamper with file before coordination/apply TOCTOU check
    with patch.object(coord.applier.precondition_validator, "validate_toctou_pre_mutation") as mock_toctou:
        from scripts.agents.precondition_validator import PreconditionValidationResult
        mock_toctou.return_value = PreconditionValidationResult(
            valid=False,
            code="ERR_STALE_BASE",
            reasons=("Live base SHA256 diverged during TOCTOU inspection",),
        )
        app_result = coord.coordinate_application(req, res, verdict)

    assert app_result.status == "NOT_APPLIED"
    assert app_result.failure_code == "ERR_STALE_BASE"
    assert target.read_text(encoding="utf-8") == "Versao inicial"


def test_e2e_partial_failure_rolled_back(repo_env):
    coord: ApplicationCoordinator = repo_env["coordinator"]
    repo: Path = repo_env["repo"]

    req = _make_e2e_request("REQ-E2E-ROLLBACK", ["data/text/**"])
    res = _make_e2e_result("REQ-E2E-ROLLBACK", {
        "data/text/file1.txt": "Content 1",
        "data/text/file2.txt": "Content 2",
    })
    verdict = ExecutionValidationVerdict(verdict="ACCEPT", code="ACCEPT", reasons=())

    orig_exclusive_create = FileSystemPrimitives.exclusive_create

    def fail_on_second(target, source):
        if "file2.txt" in str(target):
            raise IOError("Simulated disk error on file2")
        return orig_exclusive_create(target, source)

    with patch.object(FileSystemPrimitives, "exclusive_create", side_effect=fail_on_second):
        app_result = coord.coordinate_application(req, res, verdict)

    assert app_result.status == "ROLLED_BACK"
    assert app_result.failure_code == "ERR_ATOMIC_COMMIT_FAILED"
    # file1 was rolled back and deleted
    assert not (repo / "data" / "text" / "file1.txt").exists()


def test_e2e_external_tamper_rollback_failed(repo_env):
    coord: ApplicationCoordinator = repo_env["coordinator"]
    repo: Path = repo_env["repo"]
    audit: Path = repo_env["audit"]

    req = _make_e2e_request("REQ-E2E-TAMPER", ["data/text/**"])
    res = _make_e2e_result("REQ-E2E-TAMPER", {
        "data/text/file1.txt": "Content 1",
        "data/text/file2.txt": "Content 2",
    })
    verdict = ExecutionValidationVerdict(verdict="ACCEPT", code="ACCEPT", reasons=())

    orig_exclusive_create = FileSystemPrimitives.exclusive_create

    def tamper_then_fail(target, source):
        if "file2.txt" in str(target):
            # Concurrent process alters file1 before rollback
            (repo / "data" / "text" / "file1.txt").write_text("TAMPERED", encoding="utf-8")
            raise IOError("Simulated disk error on file2")
        return orig_exclusive_create(target, source)

    with patch.object(FileSystemPrimitives, "exclusive_create", side_effect=tamper_then_fail):
        app_result = coord.coordinate_application(req, res, verdict)

    assert app_result.status == "ROLLBACK_FAILED"
    assert app_result.failure_code == "ERR_CRITICAL_ROLLBACK_FAILED"

    # Audit preservation must exist on disk
    preserved_audit = audit / app_result.change_set_id
    assert preserved_audit.exists()
    assert (preserved_audit / "journal.json").is_file()
