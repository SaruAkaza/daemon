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
from scripts.agents.execution_validator import ExecutionValidationVerdict
from scripts.agents.patch_applier import PatchApplier
from scripts.agents.precondition_validator import PreconditionValidator
from scripts.agents.staging_manager import StagingManager


def _make_request(write_scope: list[str] | None = None) -> dict:
    return {
        "schemaVersion": "2.0",
        "requestId": "REQ-JOB-TREVAS-001-EXTRACTION-01",
        "jobId": "JOB-TREVAS-001",
        "bookId": "trevas-3-0",
        "targetStage": "extraction",
        "assignedAgent": "extraction-agent",
        "allowedWriteScope": write_scope or ["data/text/**", "data/structured/**"],
        "executionProfile": "offline-test",
        "contextPack": {
            "schemaVersion": "1.0",
            "contextPackId": "CTX-TREVAS-EXTRACTION-001",
            "jobId": "JOB-TREVAS-001",
            "agent": "extraction-agent",
            "stage": "extraction",
            "mandatory": ["docs/architecture/constitution.md"],
            "domain": ["docs/context/domain/taxonomy.md"],
            "bookContext": ["coordination/books/trevas.md"],
            "jobContext": ["coordination/queue/codex.json"],
            "handoffContext": [],
            "task": {
                "type": "extract_raw_text",
                "scope": {"bookId": "trevas-3-0", "pages": [1, 2, 3]},
                "parameters": {"strictCoverage": True},
            },
            "outputContract": "schemas/agent-handoff.schema.json",
        },
        "taskInstruction": "Extract and clean raw text",
        "outputSchemaName": "agent-handoff.schema.json",
        "timeoutSeconds": 120,
        "metadata": {"test": True},
    }


def _make_result(artifacts: dict[str, str] | None = None) -> dict:
    return {
        "schemaVersion": "2.0",
        "executionId": "EXEC-REQ-JOB-TREVAS-001-EXTRACTION-01-01",
        "requestId": "REQ-JOB-TREVAS-001-EXTRACTION-01",
        "agent": "extraction-agent",
        "stage": "extraction",
        "status": "SUCCESS",
        "proposedArtifacts": artifacts if artifacts is not None else {
            "data/text/spells.txt": "Bola de fogo causa 6d6 de dano.",
        },
        "evidence": [
            {
                "book": "trevas-3-0",
                "page": 1,
                "section": "Magias",
                "snippet": "Original excerpt",
            }
        ],
        "uncertainties": [],
        "metadata": {},
    }


def _build_coordinator(tmp_path: Path) -> tuple[ApplicationCoordinator, ApplicationRuntimeConfig]:
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
    builder = ChangeSetBuilder(repository_root=repo_root)
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
    return coordinator, config


def test_coordinator_happy_path_applied(tmp_path: Path):
    coord, config = _build_coordinator(tmp_path)
    request = _make_request(["data/text/**"])
    result = _make_result({
        "data/text/spells.txt": "Bola de fogo causa 6d6 de dano.",
    })
    verdict = ExecutionValidationVerdict(
        verdict="ACCEPT",
        code="ACCEPT",
        reasons=(),
    )
    app_res = coord.coordinate_application(request, result, verdict)
    assert app_res.status == "APPLIED"
    assert app_res.failure_code is None
    assert len(app_res.applied_operations) == 1

    target = config.repository_root / "data" / "text" / "spells.txt"
    assert target.is_file()
    assert "Bola de fogo" in target.read_text(encoding="utf-8")


def test_coordinator_human_review_for_protected_path(tmp_path: Path):
    coord, config = _build_coordinator(tmp_path)
    request = _make_request(["scripts/**"])
    result = _make_result({
        "scripts/malicious.py": "import os",
    })
    verdict = ExecutionValidationVerdict(
        verdict="ACCEPT",
        code="ACCEPT",
        reasons=(),
    )
    app_res = coord.coordinate_application(request, result, verdict)
    assert app_res.status == "HUMAN_REVIEW"
    assert app_res.failure_code in ("ERR_PROTECTED_PATH", "ERR_NON_ALLOWLISTED_PATH")
    assert not (config.repository_root / "scripts" / "malicious.py").exists()


def test_coordinator_blocked_for_scope_violation(tmp_path: Path):
    coord, config = _build_coordinator(tmp_path)
    request = _make_request(["data/text/allowed/**"])
    result = _make_result({
        "data/text/other/forbidden.txt": "forbidden content",
    })
    verdict = ExecutionValidationVerdict(
        verdict="ACCEPT",
        code="ACCEPT",
        reasons=(),
    )
    app_res = coord.coordinate_application(request, result, verdict)
    assert app_res.status == "BLOCKED"
    assert app_res.failure_code == "ERR_WRITE_SCOPE_VIOLATION"
