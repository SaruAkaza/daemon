from __future__ import annotations

import json
from pathlib import Path
import pytest

from scripts.agents.restricted_workspace import RestrictedPilotWorkspace
from scripts.agents.pilot_persistence_adapter import PilotPersistenceAdapter


@pytest.fixture
def workspace_env(tmp_path: Path) -> tuple[Path, Path]:
    runtime_root = tmp_path / ".daemon_runtime"
    ws_root = RestrictedPilotWorkspace.get_workspace_path(runtime_root, "animalidade")
    RestrictedPilotWorkspace.initialize_layout(ws_root)
    staging_root = runtime_root / "staging"
    return ws_root, staging_root


def test_apply_to_isolated_workspace_success(workspace_env: tuple[Path, Path]):
    ws_root, staging_root = workspace_env
    adapter = PilotPersistenceAdapter()

    req = {
        "schemaVersion": "2.0",
        "requestId": "REQ-ANIM-01",
        "jobId": "JOB-ANIM-01",
        "bookId": "animalidade",
        "targetStage": "extraction",
        "assignedAgent": "extraction-agent",
        "allowedWriteScope": ["data/text/animalidade.txt", "data/pilot/animalidade.json"],
        "executionProfile": "manual-antigravity",
        "contextPack": {
            "schemaVersion": "1.0",
            "contextPackId": "CTX-REQ-ANIM-01",
            "jobId": "JOB-ANIM-01",
            "agent": "extraction-agent",
            "stage": "extraction",
            "mandatory": ["docs/architecture/constitution.md"],
            "domain": ["docs/context/domain/taxonomy.md"],
            "bookContext": ["coordination/books/animalidade.md"],
            "jobContext": ["coordination/queue/codex.json"],
            "handoffContext": [],
            "task": {
                "type": "persist_pilot_artifacts",
                "sourceType": "docx",
                "sourcePath": "Livros/word/feito/animalidade.docx",
            },
            "outputContract": "schemas/raw-text-block.schema.json",
        },
        "taskInstruction": "Extract and clean text paragraphs from animalidade source.",
        "outputSchemaName": "entity.schema.json",
    }

    entity_content = json.dumps({
        "id": "creature-lobo",
        "name": "Lobo",
        "category": "creature_npc",
        "source": "animalidade",
        "page": 1,
        "entries": ["Lobo selvagem."],
    })

    res = {
        "schemaVersion": "2.0",
        "executionId": "EXEC-REQ-ANIM-01-01",
        "requestId": "REQ-ANIM-01",
        "agent": "extraction-agent",
        "stage": "extraction",
        "status": "SUCCESS",
        "proposedArtifacts": {
            "data/text/animalidade.txt": "Paragraph 1\nParagraph 2\n",
            "data/pilot/animalidade.json": entity_content,
        },
        "evidence": [{"book": "animalidade", "page": 1}],
        "uncertainties": [],
    }

    decision = {
        "decisionId": "DEC-001",
        "requestId": "REQ-ANIM-01",
        "resultBundleId": "RB-ANIM-01",
        "reviewedResultManifestSha256": "0" * 64,
        "decision": "APPROVE",
        "reviewer": "human-editor",
        "reviewNotes": "Approved for isolated workspace persistence.",
        "decidedAt": "2026-09-08T15:00:00Z",
    }

    result = adapter.apply_pilot_artifacts(
        workspace_root=ws_root,
        staging_root=staging_root,
        execution_request=req,
        execution_result=res,
        review_decision=decision,
    )

    assert result.status == "APPLIED"
    assert (ws_root / "data/text/animalidade.txt").exists()
    assert (ws_root / "data/text/animalidade.txt").read_text(encoding="utf-8") == "Paragraph 1\nParagraph 2\n"
    assert (ws_root / "data/pilot/animalidade.json").exists()


def test_apply_rejects_when_execution_result_validator_rejects(workspace_env: tuple[Path, Path]):
    ws_root, staging_root = workspace_env
    adapter = PilotPersistenceAdapter()

    req = {
        "schemaVersion": "2.0",
        "requestId": "REQ-ANIM-01",
        "jobId": "JOB-ANIM-01",
        "bookId": "animalidade",
        "targetStage": "extraction",
        "assignedAgent": "extraction-agent",
        "allowedWriteScope": ["data/text/animalidade.txt"],
        "executionProfile": "manual-antigravity",
        "contextPack": {
            "schemaVersion": "1.0",
            "contextPackId": "CTX-REQ-ANIM-01",
            "jobId": "JOB-ANIM-01",
            "agent": "extraction-agent",
            "stage": "extraction",
            "mandatory": ["docs/architecture/constitution.md"],
            "domain": ["docs/context/domain/taxonomy.md"],
            "bookContext": ["coordination/books/animalidade.md"],
            "jobContext": ["coordination/queue/codex.json"],
            "handoffContext": [],
            "task": {
                "type": "persist_pilot_artifacts",
                "sourceType": "docx",
                "sourcePath": "Livros/word/feito/animalidade.docx",
            },
            "outputContract": "schemas/raw-text-block.schema.json",
        },
        "taskInstruction": "Extract",
        "outputSchemaName": "raw-text-block.schema.json",
    }

    # Result with status ERROR must fail technical validation
    res = {
        "schemaVersion": "2.0",
        "executionId": "EXEC-REQ-ANIM-01-01",
        "requestId": "REQ-ANIM-01",
        "agent": "extraction-agent",
        "stage": "extraction",
        "status": "ERROR",
        "proposedArtifacts": {
            "data/text/animalidade.txt": "Partial text",
        },
        "evidence": [{"book": "animalidade", "page": 1}],
        "uncertainties": [],
    }

    decision = {
        "decisionId": "DEC-001",
        "requestId": "REQ-ANIM-01",
        "resultBundleId": "RB-ANIM-01",
        "reviewedResultManifestSha256": "0" * 64,
        "decision": "APPROVE",
        "reviewer": "human-editor",
        "reviewNotes": "Approved.",
        "decidedAt": "2026-09-08T15:00:00Z",
    }

    result = adapter.apply_pilot_artifacts(
        workspace_root=ws_root,
        staging_root=staging_root,
        execution_request=req,
        execution_result=res,
        review_decision=decision,
    )

    assert result.status == "BLOCKED"
    assert not (ws_root / "data/text/animalidade.txt").exists()


def test_apply_rejects_artifacts_outside_original_allowed_write_scope(workspace_env: tuple[Path, Path]):
    ws_root, staging_root = workspace_env
    adapter = PilotPersistenceAdapter()

    req = {
        "schemaVersion": "2.0",
        "requestId": "REQ-ANIM-01",
        "jobId": "JOB-ANIM-01",
        "bookId": "animalidade",
        "targetStage": "extraction",
        "assignedAgent": "extraction-agent",
        # Only text path is allowed in request
        "allowedWriteScope": ["data/text/animalidade.txt"],
        "executionProfile": "manual-antigravity",
        "contextPack": {
            "schemaVersion": "1.0",
            "contextPackId": "CTX-REQ-ANIM-01",
            "jobId": "JOB-ANIM-01",
            "agent": "extraction-agent",
            "stage": "extraction",
            "mandatory": ["docs/architecture/constitution.md"],
            "domain": ["docs/context/domain/taxonomy.md"],
            "bookContext": ["coordination/books/animalidade.md"],
            "jobContext": ["coordination/queue/codex.json"],
            "handoffContext": [],
            "task": {
                "type": "persist_pilot_artifacts",
                "sourceType": "docx",
                "sourcePath": "Livros/word/feito/animalidade.docx",
            },
            "outputContract": "schemas/raw-text-block.schema.json",
        },
        "taskInstruction": "Extract",
        "outputSchemaName": "raw-text-block.schema.json",
    }

    # Result tries to write outside allowed scope
    res = {
        "schemaVersion": "2.0",
        "executionId": "EXEC-REQ-ANIM-01-01",
        "requestId": "REQ-ANIM-01",
        "agent": "extraction-agent",
        "stage": "extraction",
        "status": "SUCCESS",
        "proposedArtifacts": {
            "data/text/animalidade.txt": "Text",
            "data/entities/creature.json": "{}",
        },
        "evidence": [{"book": "animalidade", "page": 1}],
        "uncertainties": [],
    }

    decision = {
        "decisionId": "DEC-001",
        "requestId": "REQ-ANIM-01",
        "resultBundleId": "RB-ANIM-01",
        "reviewedResultManifestSha256": "0" * 64,
        "decision": "APPROVE",
        "reviewer": "human-editor",
        "reviewNotes": "Approved.",
        "decidedAt": "2026-09-08T15:00:00Z",
    }

    result = adapter.apply_pilot_artifacts(
        workspace_root=ws_root,
        staging_root=staging_root,
        execution_request=req,
        execution_result=res,
        review_decision=decision,
    )

    assert result.status == "BLOCKED"
    assert not (ws_root / "data/text/animalidade.txt").exists()
    assert not (ws_root / "data/entities/creature.json").exists()


def test_apply_fails_if_decision_not_approved(workspace_env: tuple[Path, Path]):
    ws_root, staging_root = workspace_env
    adapter = PilotPersistenceAdapter()

    req = {
        "schemaVersion": "2.0",
        "requestId": "REQ-ANIM-01",
        "jobId": "JOB-ANIM-01",
        "bookId": "animalidade",
        "targetStage": "extraction",
        "assignedAgent": "extraction-agent",
        "allowedWriteScope": ["data/text/animalidade.txt"],
        "executionProfile": "manual-antigravity",
        "contextPack": {
            "schemaVersion": "1.0",
            "contextPackId": "CTX-REQ-ANIM-01",
            "jobId": "JOB-ANIM-01",
            "agent": "extraction-agent",
            "stage": "extraction",
            "mandatory": ["docs/architecture/constitution.md"],
            "domain": ["docs/context/domain/taxonomy.md"],
            "bookContext": ["coordination/books/animalidade.md"],
            "jobContext": ["coordination/queue/codex.json"],
            "handoffContext": [],
            "task": {
                "type": "persist_pilot_artifacts",
                "sourceType": "docx",
                "sourcePath": "Livros/word/feito/animalidade.docx",
            },
            "outputContract": "schemas/raw-text-block.schema.json",
        },
        "taskInstruction": "Extract",
        "outputSchemaName": "raw-text-block.schema.json",
    }

    res = {
        "schemaVersion": "2.0",
        "executionId": "EXEC-REQ-ANIM-01-01",
        "requestId": "REQ-ANIM-01",
        "agent": "extraction-agent",
        "stage": "extraction",
        "status": "SUCCESS",
        "proposedArtifacts": {
            "data/text/animalidade.txt": "Text",
        },
        "evidence": [{"book": "animalidade", "page": 1}],
        "uncertainties": [],
    }

    decision = {
        "decisionId": "DEC-002",
        "requestId": "REQ-ANIM-01",
        "resultBundleId": "RB-ANIM-01",
        "reviewedResultManifestSha256": "0" * 64,
        "decision": "REJECT",
        "reviewer": "human-editor",
        "reviewNotes": "Rejected.",
        "decidedAt": "2026-09-08T15:00:00Z",
    }

    result = adapter.apply_pilot_artifacts(
        workspace_root=ws_root,
        staging_root=staging_root,
        execution_request=req,
        execution_result=res,
        review_decision=decision,
    )

    assert result.status == "BLOCKED"
    assert not (ws_root / "data/text/animalidade.txt").exists()


def test_v21_auto_apply_roots_enforced(workspace_env: tuple[Path, Path]):
    ws_root, staging_root = workspace_env
    adapter = PilotPersistenceAdapter()

    req = {
        "schemaVersion": "2.0",
        "requestId": "REQ-ANIM-01",
        "jobId": "JOB-ANIM-01",
        "bookId": "animalidade",
        "targetStage": "extraction",
        "assignedAgent": "extraction-agent",
        "allowedWriteScope": ["scripts/malicious.py"],
        "executionProfile": "manual-antigravity",
        "contextPack": {
            "schemaVersion": "1.0",
            "contextPackId": "CTX-REQ-ANIM-01",
            "jobId": "JOB-ANIM-01",
            "agent": "extraction-agent",
            "stage": "extraction",
            "mandatory": ["docs/architecture/constitution.md"],
            "domain": ["docs/context/domain/taxonomy.md"],
            "bookContext": ["coordination/books/animalidade.md"],
            "jobContext": ["coordination/queue/codex.json"],
            "handoffContext": [],
            "task": {
                "type": "persist_pilot_artifacts",
                "sourceType": "docx",
                "sourcePath": "Livros/word/feito/animalidade.docx",
            },
            "outputContract": "schemas/raw-text-block.schema.json",
        },
        "taskInstruction": "Attack",
        "outputSchemaName": "raw-text-block.schema.json",
    }

    res = {
        "schemaVersion": "2.0",
        "executionId": "EXEC-REQ-ANIM-01-01",
        "requestId": "REQ-ANIM-01",
        "agent": "extraction-agent",
        "stage": "extraction",
        "status": "SUCCESS",
        "proposedArtifacts": {
            "scripts/malicious.py": "print('attack')",
        },
        "evidence": [{"book": "animalidade", "page": 1}],
        "uncertainties": [],
    }

    decision = {
        "decisionId": "DEC-003",
        "requestId": "REQ-ANIM-01",
        "resultBundleId": "RB-ANIM-01",
        "reviewedResultManifestSha256": "0" * 64,
        "decision": "APPROVE",
        "reviewer": "human-editor",
        "reviewNotes": "Approved.",
        "decidedAt": "2026-09-08T15:00:00Z",
    }

    result = adapter.apply_pilot_artifacts(
        workspace_root=ws_root,
        staging_root=staging_root,
        execution_request=req,
        execution_result=res,
        review_decision=decision,
    )

    assert result.status in ("BLOCKED", "HUMAN_REVIEW")
    assert not (ws_root / "scripts/malicious.py").exists()

