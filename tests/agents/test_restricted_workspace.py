from __future__ import annotations

from pathlib import Path
from scripts.agents.restricted_workspace import RestrictedPilotWorkspace


def test_workspace_layout_and_path(tmp_path: Path):
    runtime_root = tmp_path / ".daemon_runtime"
    ws_path = RestrictedPilotWorkspace.get_workspace_path(runtime_root, "animalidade")

    expected_path = runtime_root / "workspaces" / "pilot" / "animalidade" / "repository"
    assert ws_path == expected_path

    RestrictedPilotWorkspace.initialize_layout(ws_path)

    assert (ws_path / "data" / "text").is_dir()
    assert (ws_path / "data" / "blocks").is_dir()
    assert (ws_path / "data" / "segments" / "sources").is_dir()
    assert (ws_path / "data" / "books").is_dir()
    assert (ws_path / "data" / "entities").is_dir()
    assert (ws_path / "data" / "pilot").is_dir()
