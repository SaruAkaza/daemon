from __future__ import annotations

import json
from pathlib import Path
import pytest

from scripts.agents.restricted_workspace import RestrictedPilotWorkspace
from scripts.agents.preview_projector import LocalPreviewProjector, LocalPreviewProjectorError


@pytest.fixture
def workspace_with_data(tmp_path: Path) -> Path:
    ws_root = RestrictedPilotWorkspace.get_workspace_path(tmp_path, "animalidade")
    RestrictedPilotWorkspace.initialize_layout(ws_root)

    pilot_data = {
        "bookId": "animalidade",
        "title": "Animalidade Pilot",
        "entities": [
            {"id": "creature-lobo", "name": "Lobo", "category": "creature_npc"}
        ],
        "relations": [
            {"id": "rel-01", "type": "HAS_POWER", "sourceEntityId": "creature-lobo", "targetEntityId": "power-faro"}
        ],
    }
    (ws_root / "data" / "pilot" / "animalidade.json").write_text(json.dumps(pilot_data), encoding="utf-8")
    return ws_root


def test_project_local_preview_success(workspace_with_data: Path, tmp_path: Path):
    projector = LocalPreviewProjector()
    preview_root = tmp_path / ".daemon_runtime" / "preview"

    out_path = projector.project_local_preview(
        workspace_root=workspace_with_data,
        preview_root=preview_root,
        book_id="animalidade",
        rights_status="UNKNOWN",
        publication_mode="NOT_PUBLIC",
    )

    assert out_path.exists()
    assert out_path == preview_root / "animalidade"
    assert (out_path / "index.json").exists()

    with open(out_path / "index.json", encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded["bookId"] == "animalidade"
    assert len(loaded["entities"]) == 1


def test_project_blocked_if_target_is_docs(workspace_with_data: Path, tmp_path: Path):
    projector = LocalPreviewProjector()
    forbidden_root = tmp_path / "docs" / "assets" / "data"

    with pytest.raises(LocalPreviewProjectorError) as exc:
        projector.project_local_preview(
            workspace_root=workspace_with_data,
            preview_root=forbidden_root,
            book_id="animalidade",
            rights_status="UNKNOWN",
            publication_mode="NOT_PUBLIC",
        )
    assert "ERR_RESTRICTED_CONTENT_PROJECTION_BLOCKED" in str(exc.value)


def test_project_blocked_if_target_in_repo_docs(workspace_with_data: Path):
    projector = LocalPreviewProjector()
    forbidden_root = Path("docs/assets/data")

    with pytest.raises(LocalPreviewProjectorError) as exc:
        projector.project_local_preview(
            workspace_root=workspace_with_data,
            preview_root=forbidden_root,
            book_id="animalidade",
            rights_status="PRIVATE",
            publication_mode="NOT_PUBLIC",
        )
    assert "ERR_RESTRICTED_CONTENT_PROJECTION_BLOCKED" in str(exc.value)
