from __future__ import annotations

from pathlib import Path


class RestrictedPilotWorkspace:
    """Provides untracked runtime isolation for restricted pilot candidate content."""

    @staticmethod
    def get_workspace_path(runtime_root: Path | str, book_id: str) -> Path:
        """Derives standard isolated workspace repository root for book_id."""
        return Path(runtime_root).resolve() / "workspaces" / "pilot" / book_id / "repository"

    @staticmethod
    def initialize_layout(workspace_root: Path | str) -> None:
        """Pre-creates canonical content directory tree under isolated workspace."""
        root = Path(workspace_root).resolve()
        subdirs = [
            "data/text",
            "data/blocks",
            "data/segments/sources",
            "data/books",
            "data/entities",
            "data/pilot",
        ]
        for s in subdirs:
            (root / s).mkdir(parents=True, exist_ok=True)
