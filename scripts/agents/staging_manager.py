from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
from typing import Any

from scripts.agents.application_runtime import ApplicationRuntimeConfig
from scripts.agents.patch_applier import CandidateArtifact
from scripts.agents.transaction_journal import TransactionJournal


class StagingManager:
    """Manages the isolated staging lifecycle on the same filesystem as repository targets."""

    def __init__(self, config: ApplicationRuntimeConfig) -> None:
        self.config = config

    def verify_same_filesystem(self) -> bool:
        """Verifies that repository_root and staging_root reside on the same filesystem/volume.
        Fail-closed if volumes differ (ERR_CROSS_VOLUME_STAGING).
        """
        repo_root = self.config.repository_root
        staging_root = self.config.staging_root

        try:
            repo_stat = repo_root.stat()
        except OSError:
            return False

        # Find closest existing ancestor of staging_root
        curr = staging_root
        while not curr.exists() and curr != curr.parent:
            curr = curr.parent

        try:
            staging_stat = curr.stat()
        except OSError:
            return False

        # On Windows, drive letters must match
        if repo_root.drive and curr.drive:
            if repo_root.drive.lower() != curr.drive.lower():
                return False

        # On POSIX / general, compare st_dev
        if hasattr(repo_stat, "st_dev") and hasattr(staging_stat, "st_dev"):
            if repo_stat.st_dev != staging_stat.st_dev and not (
                repo_root.drive and repo_root.drive.lower() == curr.drive.lower()
            ):
                return False

        return True

    def prepare_staging(self, change_set_id: str) -> Path:
        """Creates an isolated staging directory for the change set under staging_root."""
        if not self.verify_same_filesystem():
            raise ValueError(
                f"ERR_CROSS_VOLUME_STAGING: repository_root '{self.config.repository_root}' "
                f"and staging_root '{self.config.staging_root}' are on different filesystems/volumes."
            )
        staging_dir = self.config.staging_root / change_set_id
        staging_dir.mkdir(parents=True, exist_ok=True)
        (staging_dir / "candidates").mkdir(exist_ok=True)
        (staging_dir / "backups").mkdir(exist_ok=True)
        return staging_dir

    def stage_candidates(
        self,
        staging_dir: Path,
        candidates: tuple[CandidateArtifact, ...],
    ) -> dict[str, Path]:
        """Writes candidate files into staging_dir/candidates/<operation_id>.bin."""
        paths: dict[str, Path] = {}
        candidates_dir = staging_dir / "candidates"
        candidates_dir.mkdir(parents=True, exist_ok=True)

        total_bytes = 0
        for c in candidates:
            total_bytes += len(c.content_bytes)
            if total_bytes > self.config.resource_bounds.max_total_staging_bytes:
                raise ValueError(
                    f"ERR_RESOURCE_BOUND_EXCEEDED: Staging size exceeds max_total_staging_bytes "
                    f"({self.config.resource_bounds.max_total_staging_bytes} bytes)"
                )
            cand_file = candidates_dir / f"{c.operation_id}.bin"
            cand_file.write_bytes(c.content_bytes)
            paths[c.operation_id] = cand_file

        return paths

    def create_backup(
        self,
        staging_dir: Path,
        target_path: str,
        repo_root: Path,
    ) -> Path:
        """Copies an existing repository file into staging_dir/backups/<hash>_<filename>."""
        backups_dir = staging_dir / "backups"
        backups_dir.mkdir(parents=True, exist_ok=True)
        src = repo_root / target_path
        if not src.is_file():
            raise FileNotFoundError(f"Cannot backup non-existent file: {src}")

        path_hash = hashlib.sha256(target_path.encode("utf-8")).hexdigest()[:16]
        dst = backups_dir / f"{path_hash}_{src.name}"
        shutil.copy2(src, dst)
        return dst

    def cleanup_staging(self, staging_dir: Path) -> None:
        """Removes the temporary staging directory and all its files."""
        if staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)

    def preserve_for_audit(
        self,
        staging_dir: Path,
        journal: TransactionJournal,
    ) -> Path:
        """Preserves the staging artifacts and writes journal.json into audit_root."""
        audit_dir = self.config.audit_root / journal.change_set_id
        audit_dir.mkdir(parents=True, exist_ok=True)

        journal_file = audit_dir / "journal.json"
        journal_file.write_text(
            json.dumps(journal.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return audit_dir
