from __future__ import annotations

import json
import os
import shutil
import stat
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


class ResultBundleImporterError(RuntimeError):
    """Raised when bundle importation or staging operations fail."""
    pass


@dataclass(frozen=True)
class ResultBundleEnvelope:
    """Envelope representing an imported Result Bundle on the local filesystem."""
    bundle_id: str
    bundle_dir: Path
    result_manifest_path: Path
    execution_result_path: Path
    artifacts_dir: Path


class ResultBundleImporter:
    """Safely ingests external Result Bundles into the daemon runtime boundary."""

    def import_from_directory(self, incoming_dir: Path) -> ResultBundleEnvelope:
        """Validates basic directory structure and returns an immutable ResultBundleEnvelope."""
        incoming_dir = Path(incoming_dir)
        if not incoming_dir.exists() or not incoming_dir.is_dir():
            raise ResultBundleImporterError(f"Bundle directory does not exist or is not a directory: {incoming_dir}")

        exec_result_path = incoming_dir / "execution-result.json"
        if not exec_result_path.exists() or not exec_result_path.is_file():
            raise ResultBundleImporterError(f"Missing required execution-result.json in {incoming_dir}")

        manifest_path = incoming_dir / "result-manifest.json"
        if not manifest_path.exists() or not manifest_path.is_file():
            raise ResultBundleImporterError(f"Missing required result-manifest.json in {incoming_dir}")

        artifacts_dir = incoming_dir / "artifacts"
        if not artifacts_dir.exists() or not artifacts_dir.is_dir():
            raise ResultBundleImporterError(f"Missing required artifacts directory in {incoming_dir}")

        bundle_id = incoming_dir.name
        try:
            with open(manifest_path, encoding="utf-8") as f:
                manifest_data = json.load(f)
            if isinstance(manifest_data, dict):
                bundle_id = manifest_data.get("resultBundleId") or manifest_data.get("bundleId") or bundle_id
        except Exception:
            pass

        return ResultBundleEnvelope(
            bundle_id=bundle_id,
            bundle_dir=incoming_dir,
            result_manifest_path=manifest_path,
            execution_result_path=exec_result_path,
            artifacts_dir=artifacts_dir,
        )

    def seal_and_quarantine(self, bundle_dir: Path, rejected_dir: Path, reason: str) -> Path:
        """Quarantines an invalid/corrupted bundle into rejected_dir, recording failure reason."""
        bundle_dir = Path(bundle_dir)
        rejected_dir = Path(rejected_dir)
        rejected_dir.mkdir(parents=True, exist_ok=True)

        dest_dir = rejected_dir / bundle_dir.name
        if dest_dir.exists():
            raise ResultBundleImporterError(f"Destination quarantine path already exists: {dest_dir}")

        reason_file = bundle_dir / "rejection-reason.txt"
        timestamp = datetime.now(timezone.utc).isoformat()
        reason_file.write_text(f"Rejected: {reason}\nTimestamp: {timestamp}\n", encoding="utf-8")

        shutil.move(str(bundle_dir), str(dest_dir))

        for root, _, files in os.walk(dest_dir):
            for fname in files:
                p = Path(root) / fname
                os.chmod(p, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)

        return dest_dir

    def promote_to_accepted(self, bundle_dir: Path, accepted_dir: Path) -> Path:
        """Promotes a structurally sound bundle to accepted_dir, sealing it read-only."""
        bundle_dir = Path(bundle_dir)
        accepted_dir = Path(accepted_dir)
        accepted_dir.mkdir(parents=True, exist_ok=True)

        dest_dir = accepted_dir / bundle_dir.name
        if dest_dir.exists():
            raise ResultBundleImporterError(f"Destination accepted path already exists: {dest_dir}")

        shutil.move(str(bundle_dir), str(dest_dir))

        for root, _, files in os.walk(dest_dir):
            for fname in files:
                p = Path(root) / fname
                os.chmod(p, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)

        return dest_dir
