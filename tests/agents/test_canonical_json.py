from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.agents.canonical_json import (
    canonical_json_bytes,
    compute_input_manifest_hash,
    compute_result_manifest_hash,
    derive_execution_bundle_id,
    sha256_bytes,
    sha256_file,
)


def test_canonical_json_bytes_ordering_and_separators():
    payload1 = {"b": 1, "a": 2, "nested": {"z": 10, "y": 20}}
    payload2 = {"nested": {"y": 20, "z": 10}, "a": 2, "b": 1}
    b1 = canonical_json_bytes(payload1)
    b2 = canonical_json_bytes(payload2)
    assert b1 == b2
    assert b" " not in b1
    assert b1.decode("utf-8") == '{"a":2,"b":1,"nested":{"y":20,"z":10}}'


def test_sha256_bytes_and_file(tmp_path: Path):
    data = b"daemon tools pilot verification"
    digest = sha256_bytes(data)
    assert len(digest) == 64

    test_file = tmp_path / "sample.bin"
    test_file.write_bytes(data)
    assert sha256_file(test_file) == digest


def test_compute_input_manifest_hash_excludes_created_at():
    m1 = {
        "bundleId": "EB-ANIM-EXT-att1-12345678",
        "requestId": "req-001",
        "jobId": "job-001",
        "stage": "EXTRACTION",
        "bookId": "animalidade",
        "createdAt": "2026-09-08T10:00:00Z",
        "items": [{"path": "context/text.txt", "sha256": "abc"}],
    }
    m2 = dict(m1)
    m2["createdAt"] = "2026-09-08T12:34:56Z"

    h1 = compute_input_manifest_hash(m1)
    h2 = compute_input_manifest_hash(m2)
    assert h1 == h2
    assert len(h1) == 64


def test_compute_result_manifest_hash_excludes_self_hash():
    r1 = {
        "bundleId": "RB-ANIM-EXT-att1-87654321",
        "requestId": "req-001",
        "executionBundleId": "EB-ANIM-EXT-att1-12345678",
        "resultManifestSha256": "dummy_value",
        "status": "SUCCESS",
        "artifacts": [{"path": "data/pilot/test.json", "sha256": "111"}],
    }
    r2 = dict(r1)
    r2["resultManifestSha256"] = "different_self_hash"

    h1 = compute_result_manifest_hash(r1)
    h2 = compute_result_manifest_hash(r2)
    assert h1 == h2
    assert len(h1) == 64


def test_derive_execution_bundle_id():
    b_id = derive_execution_bundle_id(
        book_id="animalidade",
        stage="EXTRACTION",
        attempt=1,
        content_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    )
    assert b_id == "EB-ANIM-EXTRACTION-att1-e3b0c442"
