from __future__ import annotations

import hashlib
import os
from pathlib import Path


class FileSystemPrimitives:
    """Safe, single-operation filesystem primitives with atomic and compensating guarantees."""

    @staticmethod
    def exclusive_create(target_path: Path, staged_source: Path) -> str:
        """Atomically creates target_path with staged_source contents using O_CREAT | O_EXCL.
        Raises FileExistsError if target_path already exists without mutating it.
        Returns the SHA256 hex digest of the written file.
        """
        target = Path(target_path)
        source = Path(staged_source)
        target.parent.mkdir(parents=True, exist_ok=True)

        content = source.read_bytes()
        with open(target, "xb") as dst:
            dst.write(content)

        return hashlib.sha256(content).hexdigest()

    @staticmethod
    def atomic_replace(target_path: Path, staged_source: Path) -> str:
        """Atomically replaces target_path with staged_source using os.replace on the same volume.
        Returns the SHA256 hex digest of the replaced file.
        """
        target = Path(target_path)
        source = Path(staged_source)
        target.parent.mkdir(parents=True, exist_ok=True)

        os.replace(source, target)
        content = target.read_bytes()
        return hashlib.sha256(content).hexdigest()

    @staticmethod
    def compensating_remove(target_path: Path, expected_candidate_sha256: str) -> bool:
        """Compensating removal for CREATE operation.
        Removes target_path ONLY if its live disk hash matches expected_candidate_sha256.
        If live disk hash differs, refuses to remove and returns False.
        """
        target = Path(target_path)
        if not target.is_file():
            return False

        try:
            current_bytes = target.read_bytes()
        except OSError:
            return False

        current_sha256 = hashlib.sha256(current_bytes).hexdigest()
        if current_sha256 != expected_candidate_sha256:
            return False

        try:
            target.unlink()
            return True
        except OSError:
            return False

    @staticmethod
    def compensating_restore(
        target_path: Path,
        backup_snapshot: Path,
        expected_post_apply_sha256: str,
    ) -> bool:
        """Compensating restoration for UPDATE operation.
        Restores target_path from backup_snapshot ONLY if live disk hash matches expected_post_apply_sha256.
        If live disk hash differs, refuses to restore and returns False.
        """
        target = Path(target_path)
        backup = Path(backup_snapshot)

        if not target.is_file() or not backup.is_file():
            return False

        try:
            current_bytes = target.read_bytes()
        except OSError:
            return False

        current_sha256 = hashlib.sha256(current_bytes).hexdigest()
        if current_sha256 != expected_post_apply_sha256:
            return False

        try:
            os.replace(backup, target)
            return True
        except OSError:
            return False
