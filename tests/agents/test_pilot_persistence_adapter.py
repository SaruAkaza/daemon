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

    proposed = [
        {
            "path": "data/text/animalidade.txt",
            "content": "Paragraph 1\nParagraph 2\n",
            "action": "CREATE",
        },
        {
            "path": "data/pilot/animalidade.json",
            "content": json.dumps({"bookId": "animalidade", "title": "Animalidade"}),
            "action": "CREATE",
        },
    ]

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
        proposed_artifacts=proposed,
        review_decision=decision,
    )

    assert result.status == "APPLIED"
    assert (ws_root / "data/text/animalidade.txt").exists()
    assert (ws_root / "data/text/animalidade.txt").read_text(encoding="utf-8") == "Paragraph 1\nParagraph 2\n"
    assert (ws_root / "data/pilot/animalidade.json").exists()


def test_apply_fails_if_decision_not_approved(workspace_env: tuple[Path, Path]):
    ws_root, staging_root = workspace_env
    adapter = PilotPersistenceAdapter()

    proposed = [
        {
            "path": "data/text/animalidade.txt",
            "content": "Text",
            "action": "CREATE",
        }
    ]

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
        proposed_artifacts=proposed,
        review_decision=decision,
    )

    assert result.status == "BLOCKED"
    assert not (ws_root / "data/text/animalidade.txt").exists()


def test_v21_auto_apply_roots_enforced(workspace_env: tuple[Path, Path]):
    ws_root, staging_root = workspace_env
    adapter = PilotPersistenceAdapter()

    proposed = [
        {
            "path": "scripts/malicious.py",
            "content": "print('attack')",
            "action": "CREATE",
        }
    ]

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
        proposed_artifacts=proposed,
        review_decision=decision,
    )

    assert result.status in ("BLOCKED", "HUMAN_REVIEW")
    assert not (ws_root / "scripts/malicious.py").exists()
