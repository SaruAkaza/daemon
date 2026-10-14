from pathlib import Path
import json

import pytest

from scripts.agents.canonical_json import canonical_json_bytes, compute_result_manifest_hash


@pytest.fixture(scope="session")
def certified_archive_runtime(tmp_path_factory) -> Path:
    """Certified synthetic bundles; no dependence on a developer runtime."""
    runtime_dir = tmp_path_factory.mktemp("certified_archive")
    jobs_dir = runtime_dir / "jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    job_data = {
        "schemaVersion": "1.0",
        "jobId": "JOB-ANIM-001",
        "kind": "book_ingestion",
        "bookId": "animalidade",
        "status": "in_progress",
        "createdAt": "2026-09-09T17:12:08.418844+00:00",
        "updatedAt": "2026-09-09T18:56:11.482194+00:00",
        "requestedBy": "human",
        "currentStage": "relations",
        "stages": {
            "source": "pass",
            "extraction": "pass",
            "editorial": "pass",
            "entities": "pass",
            "relations": "ready",
            "frontend": "waiting",
            "qa": "waiting",
            "release": "waiting",
        },
        "humanReviewRequired": False,
        "blockingReasons": [],
        "artifacts": [],
        "history": [],
    }
    (jobs_dir / "JOB-ANIM-001.json").write_text(json.dumps(job_data), encoding="utf-8")

    dec_dir = runtime_dir / "audit" / "pilot" / "animalidade" / "decisions"
    dec_dir.mkdir(parents=True, exist_ok=True)
    req_dir = runtime_dir / "audit" / "pilot" / "animalidade" / "requests"
    req_dir.mkdir(parents=True, exist_ok=True)

    ent_manifest = {
        "bookId": "animalidade",
        "resultBundleId": "RB-ANIM-ENTITIES-att1-50691836",
        "attemptNumber": 1,
    }
    ent_manifest_hash = compute_result_manifest_hash(ent_manifest)
    ent_manifest["resultManifestSha256"] = ent_manifest_hash

    rel_manifest = {
        "bookId": "animalidade",
        "resultBundleId": "RB-ANIM-RELATIONS-att2-3c451b57",
        "attemptNumber": 2,
        "inputEntitiesBundle": "RB-ANIM-ENTITIES-att1-50691836",
    }
    rel_manifest_hash = compute_result_manifest_hash(rel_manifest)
    rel_manifest["resultManifestSha256"] = rel_manifest_hash

    dec_data = {
        "decisionId": "DEC-ANIM-001-ENTITIES-01",
        "decision": "APPROVE",
        "reviewer": "human-evaluator",
        "resultBundleId": "RB-ANIM-ENTITIES-att1-50691836",
        "reviewedResultManifestSha256": ent_manifest_hash,
    }
    (dec_dir / "DEC-ANIM-001-ENTITIES-01.json").write_text(json.dumps(dec_data), encoding="utf-8")

    req_data = {
        "reviewRequestId": "REV-ANIM-001-RELATIONS-02",
        "jobId": "JOB-ANIM-001",
        "stage": "relations",
        "attemptNumber": 2,
        "resultBundleId": "RB-ANIM-RELATIONS-att2-3c451b57",
        "inputEntitiesBundle": "RB-ANIM-ENTITIES-att1-50691836",
        "resultManifestSha256": rel_manifest_hash,
        "status": "NEEDS_HUMAN_REVIEW",
    }
    (req_dir / "REV-ANIM-001-RELATIONS-02.json").write_text(json.dumps(req_data), encoding="utf-8")

    ent_bundle = runtime_dir / "bundles" / "accepted" / "RB-ANIM-ENTITIES-att1-50691836"
    ent_art = ent_bundle / "artifacts"
    ent_art.mkdir(parents=True, exist_ok=True)
    entities = [
        {
            "id": f"ent-anim-{i}",
            "name": f"Poder Animal {i}",
            "category": "character_option",
            "subtype": "poder",
            "displayType": "Poder",
            "provenance": {"source": "animalidade", "pages": [1]},
        }
        for i in range(56)
    ]
    (ent_art / "entities.json").write_text(json.dumps(entities), encoding="utf-8")
    (ent_bundle / "result-manifest.json").write_bytes(canonical_json_bytes(ent_manifest))

    rel_bundle = runtime_dir / "bundles" / "accepted" / "RB-ANIM-RELATIONS-att2-3c451b57"
    rel_art = rel_bundle / "artifacts"
    rel_art.mkdir(parents=True, exist_ok=True)
    relations = [
        {
            "relationId": f"rel-anim-{i}",
            "type": "CAN_CHOOSE_POWER" if i < 108 else "HAS_WEAKNESS",
            "sourceEntityId": "ent-anim-0",
            "targetEntityId": f"ent-anim-{(i % 55) + 1}",
            "source": "animalidade",
        }
        for i in range(164)
    ]
    (rel_art / "relations.json").write_text(json.dumps(relations), encoding="utf-8")
    (rel_bundle / "result-manifest.json").write_bytes(canonical_json_bytes(rel_manifest))

    return runtime_dir
