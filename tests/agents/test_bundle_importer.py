from __future__ import annotations

import json
import os
import stat
from pathlib import Path
import pytest

from scripts.agents.bundle_importer import (
    ResultBundleImporter,
    ResultBundleImporterError,
    ResultBundleEnvelope,
)


@pytest.fixture
def valid_bundle_dir(tmp_path: Path) -> Path:
    bdir = tmp_path / "incoming" / "RB-ANIM-EXTRACTION-att1-12345678"
    bdir.mkdir(parents=True)
    artifacts_dir = bdir / "artifacts"
    artifacts_dir.mkdir()

    (artifacts_dir / "output.txt").write_text("Extracted text payload", encoding="utf-8")
    
    exec_result = {
        "schemaVersion": "2.0",
        "resultId": "RES-01",
        "requestId": "REQ-01",
        "verdict": "ACCEPT",
        "artifacts": [{"path": "artifacts/output.txt"}],
    }
    (bdir / "execution-result.json").write_text(json.dumps(exec_result), encoding="utf-8")

    manifest = {
        "resultBundleId": "RB-ANIM-EXTRACTION-att1-12345678",
        "executionBundleId": "EB-ANIM-EXTRACTION-att1-12345678",
        "requestId": "REQ-01",
        "bookId": "animalidade",
        "attemptNumber": 1,
        "resultManifestSha256": "0" * 64,
        "executionResultPath": "execution-result.json",
        "resultManifestPath": "result-manifest.json",
        "artifacts": [
            {
                "path": "artifacts/output.txt",
                "sha256": "0" * 64,
                "sizeBytes": 22,
            }
        ],
        "completedAt": "2026-09-08T12:00:00Z",
    }
    (bdir / "result-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return bdir


def test_import_from_directory_success(valid_bundle_dir: Path):
    importer = ResultBundleImporter()
    envelope = importer.import_from_directory(valid_bundle_dir)

    assert isinstance(envelope, ResultBundleEnvelope)
    assert envelope.bundle_id == "RB-ANIM-EXTRACTION-att1-12345678"
    assert envelope.bundle_dir == valid_bundle_dir
    assert envelope.execution_result_path == valid_bundle_dir / "execution-result.json"
    assert envelope.result_manifest_path == valid_bundle_dir / "result-manifest.json"
    assert envelope.artifacts_dir == valid_bundle_dir / "artifacts"


def test_import_from_directory_missing_files(tmp_path: Path):
    importer = ResultBundleImporter()
    bdir = tmp_path / "RB-EMPTY"
    bdir.mkdir()

    # Missing all
    with pytest.raises(ResultBundleImporterError) as exc:
        importer.import_from_directory(bdir)
    assert "execution-result.json" in str(exc.value)

    # Missing manifest
    (bdir / "execution-result.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ResultBundleImporterError) as exc:
        importer.import_from_directory(bdir)
    assert "result-manifest.json" in str(exc.value)

    # Missing artifacts dir
    (bdir / "result-manifest.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ResultBundleImporterError) as exc:
        importer.import_from_directory(bdir)
    assert "artifacts" in str(exc.value)


def test_seal_and_quarantine(valid_bundle_dir: Path, tmp_path: Path):
    importer = ResultBundleImporter()
    rejected_dir = tmp_path / "rejected"

    quarantined = importer.seal_and_quarantine(
        valid_bundle_dir, rejected_dir, reason="Integrity check failed: hash mismatch"
    )

    assert not valid_bundle_dir.exists()
    assert quarantined.exists()
    assert quarantined.parent == rejected_dir
    assert (quarantined / "rejection-reason.txt").exists()
    assert "Integrity check failed" in (quarantined / "rejection-reason.txt").read_text(encoding="utf-8")

    # Verify read-only
    test_file = quarantined / "execution-result.json"
    assert not (test_file.stat().st_mode & stat.S_IWUSR)

    # Cleanup permissions for pytest
    for root, _, files in os.walk(quarantined):
        for fname in files:
            os.chmod(Path(root) / fname, stat.S_IWRITE | stat.S_IREAD)


def test_promote_to_accepted(valid_bundle_dir: Path, tmp_path: Path):
    importer = ResultBundleImporter()
    accepted_dir = tmp_path / "accepted"

    promoted = importer.promote_to_accepted(valid_bundle_dir, accepted_dir)

    assert not valid_bundle_dir.exists()
    assert promoted.exists()
    assert promoted.parent == accepted_dir

    test_file = promoted / "execution-result.json"
    assert not (test_file.stat().st_mode & stat.S_IWUSR)

    # Cleanup permissions for pytest
    for root, _, files in os.walk(promoted):
        for fname in files:
            os.chmod(Path(root) / fname, stat.S_IWRITE | stat.S_IREAD)
