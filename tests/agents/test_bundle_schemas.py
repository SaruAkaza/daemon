from __future__ import annotations

import json
from pathlib import Path
import jsonschema
import pytest

SCHEMAS_DIR = Path("schemas")


def test_execution_bundle_schema_validates():
    schema_path = SCHEMAS_DIR / "execution-bundle.schema.json"
    assert schema_path.exists(), "execution-bundle.schema.json must exist"
    with open(schema_path, encoding="utf-8") as f:
        schema = json.load(f)
    validator_cls = jsonschema.validators.validator_for(schema)
    validator_cls.check_schema(schema)

    valid_bundle = {
        "executionBundleId": "EB-ANIM-EXT-att1-12345678",
        "requestId": "req-anim-001",
        "jobId": "job-anim-001",
        "stage": "EXTRACTION",
        "bookId": "animalidade",
        "attemptNumber": 1,
        "inputManifestSha256": "a" * 64,
        "executionRequestPath": "execution-request.json",
        "promptPath": "prompt.md",
        "outputContractPath": "output-contract.json",
        "contextManifestPath": "context-manifest.json",
        "instructionsPath": "ANTIGRAVITY-INSTRUCTIONS.md",
        "createdAt": "2026-09-08T16:00:00Z",
    }
    jsonschema.validate(instance=valid_bundle, schema=schema)


def test_result_bundle_schema_validates():
    schema_path = SCHEMAS_DIR / "result-bundle.schema.json"
    assert schema_path.exists(), "result-bundle.schema.json must exist"
    with open(schema_path, encoding="utf-8") as f:
        schema = json.load(f)
    validator_cls = jsonschema.validators.validator_for(schema)
    validator_cls.check_schema(schema)

    valid_bundle = {
        "resultBundleId": "RB-ANIM-EXT-att1-87654321",
        "executionBundleId": "EB-ANIM-EXT-att1-12345678",
        "requestId": "req-anim-001",
        "bookId": "animalidade",
        "attemptNumber": 1,
        "resultManifestSha256": "b" * 64,
        "executionResultPath": "execution-result.json",
        "resultManifestPath": "result-manifest.json",
        "artifacts": [
            {"path": "data/pilot/animalidade.json", "sha256": "c" * 64, "sizeBytes": 1234}
        ],
        "completedAt": "2026-09-08T16:30:00Z",
    }
    jsonschema.validate(instance=valid_bundle, schema=schema)


def test_execution_bundle_schema_accepts_lowercase_and_full_stages():
    schema_path = SCHEMAS_DIR / "execution-bundle.schema.json"
    with open(schema_path, encoding="utf-8") as f:
        schema = json.load(f)

    for stage in ("extraction", "source", "editorial", "entities", "relations", "qa", "preview", "frontend", "release"):
        instance = {
            "executionBundleId": "EB-01",
            "requestId": "req-01",
            "jobId": "job-01",
            "stage": stage,
            "bookId": "animalidade",
            "attemptNumber": 1,
            "inputManifestSha256": "a" * 64,
            "executionRequestPath": "execution-request.json",
            "promptPath": "prompt.md",
            "outputContractPath": "output-contract.json",
            "contextManifestPath": "context-manifest.json",
            "instructionsPath": "ANTIGRAVITY-INSTRUCTIONS.md",
            "createdAt": "2026-09-08T16:00:00Z",
        }
        jsonschema.validate(instance=instance, schema=schema)


def test_pilot_review_request_schema_accepts_needs_semantic_review():
    schema_path = SCHEMAS_DIR / "pilot-review-request.schema.json"
    with open(schema_path, encoding="utf-8") as f:
        schema = json.load(f)

    req = {
        "jobId": "job-01",
        "attemptNumber": 1,
        "requestId": "req-01",
        "resultBundleId": "RB-01",
        "resultManifestSha256": "a" * 64,
        "legacyComparison": {
            "verdict": "NEEDS_SEMANTIC_REVIEW",
            "equivalentCount": 0,
            "structuralDiffCount": 0,
            "semanticDiffCount": 1,
            "newEntitiesCount": 0,
            "discrepancies": [],
        },
        "status": "PENDING",
        "createdAt": "2026-09-08T16:00:00Z",
    }
    jsonschema.validate(instance=req, schema=schema)

