from __future__ import annotations

import json
from pathlib import Path
import pytest

from scripts.agents.canonical_json import sha256_bytes
from scripts.agents.bundle_importer import ResultBundleEnvelope
from scripts.agents.bundle_integrity_validator import (
    BundleIntegrityValidator,
    IntegrityVerdict,
)


@pytest.fixture
def make_valid_bundle(tmp_path: Path):
    def _create(
        bundle_id="RB-ANIM-EXTRACTION-att1-12345678",
        request_id="REQ-01",
        input_manifest_hash="a" * 64,
        art_content=b"hello world",
        exec_verdict="ACCEPT",
    ) -> ResultBundleEnvelope:
        bdir = tmp_path / bundle_id
        bdir.mkdir(parents=True, exist_ok=True)
        art_dir = bdir / "artifacts"
        art_dir.mkdir(parents=True, exist_ok=True)

        art_file = art_dir / "extracted.txt"
        art_file.write_bytes(art_content)
        art_hash = sha256_bytes(art_content)

        exec_res_path = bdir / "execution-result.json"
        exec_res_payload = {
            "schemaVersion": "2.0",
            "resultId": "RES-01",
            "requestId": request_id,
            "verdict": exec_verdict,
            "artifacts": [{"path": "artifacts/extracted.txt"}],
        }
        exec_res_path.write_text(json.dumps(exec_res_payload), encoding="utf-8")

        manifest_path = bdir / "result-manifest.json"
        manifest_payload = {
            "resultBundleId": bundle_id,
            "executionBundleId": "EB-ANIM-EXTRACTION-att1-12345678",
            "requestId": request_id,
            "bookId": "animalidade",
            "attemptNumber": 1,
            "inputManifestSha256": input_manifest_hash,
            "resultManifestSha256": "placeholder",
            "executionResultPath": "execution-result.json",
            "resultManifestPath": "result-manifest.json",
            "artifacts": [
                {
                    "path": "artifacts/extracted.txt",
                    "sha256": art_hash,
                    "sizeBytes": len(art_content),
                }
            ],
            "completedAt": "2026-09-08T12:00:00Z",
        }
        manifest_path.write_text(json.dumps(manifest_payload), encoding="utf-8")

        return ResultBundleEnvelope(
            bundle_id=bundle_id,
            bundle_dir=bdir,
            result_manifest_path=manifest_path,
            execution_result_path=exec_res_path,
            artifacts_dir=art_dir,
        )

    return _create


def test_validate_success(make_valid_bundle):
    envelope = make_valid_bundle()
    validator = BundleIntegrityValidator()
    verdict = validator.validate(
        envelope,
        expected_request_id="REQ-01",
        expected_bundle_id="RB-ANIM-EXTRACTION-att1-12345678",
        expected_input_manifest_hash="a" * 64,
    )
    assert verdict.is_valid is True
    assert len(verdict.errors) == 0
    assert len(verdict.result_manifest_sha256) == 64
    assert "artifacts/extracted.txt" in verdict.artifact_hashes


def test_validate_request_id_mismatch(make_valid_bundle):
    envelope = make_valid_bundle(request_id="REQ-WRONG")
    validator = BundleIntegrityValidator()
    verdict = validator.validate(
        envelope,
        expected_request_id="REQ-EXPECTED",
        expected_bundle_id="RB-ANIM-EXTRACTION-att1-12345678",
        expected_input_manifest_hash="a" * 64,
    )
    assert verdict.is_valid is False
    assert any("ERR_REQUEST_ID_MISMATCH" in err for err in verdict.errors)


def test_validate_bundle_id_mismatch(make_valid_bundle):
    envelope = make_valid_bundle(bundle_id="RB-ANIM-EXTRACTION-att1-DIFF")
    validator = BundleIntegrityValidator()
    verdict = validator.validate(
        envelope,
        expected_request_id="REQ-01",
        expected_bundle_id="RB-ANIM-EXTRACTION-att1-EXPECTED",
        expected_input_manifest_hash="a" * 64,
    )
    assert verdict.is_valid is False
    assert any("ERR_BUNDLE_ID_MISMATCH" in err for err in verdict.errors)


def test_validate_input_manifest_hash_mismatch(make_valid_bundle):
    envelope = make_valid_bundle(input_manifest_hash="b" * 64)
    validator = BundleIntegrityValidator()
    verdict = validator.validate(
        envelope,
        expected_request_id="REQ-01",
        expected_bundle_id="RB-ANIM-EXTRACTION-att1-12345678",
        expected_input_manifest_hash="a" * 64,
    )
    assert verdict.is_valid is False
    assert any("ERR_INPUT_MANIFEST_HASH_MISMATCH" in err for err in verdict.errors)


def test_validate_artifact_hash_mismatch(make_valid_bundle):
    envelope = make_valid_bundle()
    # Tamper with file
    (envelope.artifacts_dir / "extracted.txt").write_bytes(b"tampered content")
    validator = BundleIntegrityValidator()
    verdict = validator.validate(
        envelope,
        expected_request_id="REQ-01",
        expected_bundle_id="RB-ANIM-EXTRACTION-att1-12345678",
        expected_input_manifest_hash="a" * 64,
    )
    assert verdict.is_valid is False
    assert any("ERR_ARTIFACT_HASH_MISMATCH" in err for err in verdict.errors)


def test_validate_missing_artifact(make_valid_bundle):
    envelope = make_valid_bundle()
    (envelope.artifacts_dir / "extracted.txt").unlink()
    validator = BundleIntegrityValidator()
    verdict = validator.validate(
        envelope,
        expected_request_id="REQ-01",
        expected_bundle_id="RB-ANIM-EXTRACTION-att1-12345678",
        expected_input_manifest_hash="a" * 64,
    )
    assert verdict.is_valid is False
    assert any("ERR_MISSING_ARTIFACT" in err for err in verdict.errors)


def test_validate_unexpected_artifact(make_valid_bundle):
    envelope = make_valid_bundle()
    # Add an untracked file in artifacts
    (envelope.artifacts_dir / "rogue.txt").write_text("rogue payload", encoding="utf-8")
    validator = BundleIntegrityValidator()
    verdict = validator.validate(
        envelope,
        expected_request_id="REQ-01",
        expected_bundle_id="RB-ANIM-EXTRACTION-att1-12345678",
        expected_input_manifest_hash="a" * 64,
    )
    assert verdict.is_valid is False
    assert any("ERR_UNEXPECTED_ARTIFACT" in err for err in verdict.errors)


def test_validate_path_traversal_in_manifest(make_valid_bundle):
    envelope = make_valid_bundle()
    with open(envelope.result_manifest_path, "r+", encoding="utf-8") as f:
        data = json.load(f)
        data["artifacts"][0]["path"] = "artifacts/../../etc/passwd"
        f.seek(0)
        f.truncate()
        json.dump(data, f)

    validator = BundleIntegrityValidator()
    verdict = validator.validate(
        envelope,
        expected_request_id="REQ-01",
        expected_bundle_id="RB-ANIM-EXTRACTION-att1-12345678",
        expected_input_manifest_hash="a" * 64,
    )
    assert verdict.is_valid is False
    assert any("traversal" in err.lower() or "ERR_RESULT_BUNDLE_INTEGRITY_FAILED" in err for err in verdict.errors)


def test_validate_execution_result_non_accept(make_valid_bundle):
    envelope = make_valid_bundle(exec_verdict="REJECT")
    validator = BundleIntegrityValidator()
    verdict = validator.validate(
        envelope,
        expected_request_id="REQ-01",
        expected_bundle_id="RB-ANIM-EXTRACTION-att1-12345678",
        expected_input_manifest_hash="a" * 64,
    )
    assert verdict.is_valid is False
    assert any("ERR_RESULT_CONTRACT_INVALID" in err for err in verdict.errors)
