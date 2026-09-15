from __future__ import annotations

import json
from pathlib import Path
import pytest

from scripts.agents.archive_inventory_loader import (
    ArchiveInventoryLoader,
    ArchiveInventoryError,
    ProcessedStateReadError,
    load_certified_pilot_artifacts,
)


def test_archive_inventory_loader_loads_281_books_unworked_by_default():
    loader = ArchiveInventoryLoader()
    books = loader.load_inventory()
    assert len(books) == 281
    # Check default fields of an unworked book
    sample = next(b for b in books if b["bookId"] == "4killers")
    assert sample["title"] == "4killers"
    assert sample["pipelineStatus"] == "WAITING"
    assert sample["rightsStatus"] == "UNKNOWN"
    assert sample["publicationMode"] == "NOT_PUBLIC"
    assert sample["entities"] == []
    assert sample["relations"] == []
    assert sample["currentStage"] is None
    assert sample["pageCount"] == 8


def test_archive_inventory_loader_integrates_operational_job_store():
    loader = ArchiveInventoryLoader()
    # Certified operational state from JobStore
    certified_job = {
        "animalidade": {
            "bookId": "animalidade",
            "pipelineStatus": "RUNNING",
            "currentStage": "relations",
            "entities": [{"id": f"ent-{i}", "name": f"Poder {i}", "source": "animalidade"} for i in range(56)],
            "relations": [
                {
                    "relationId": "r-1",
                    "type": "CAN_CHOOSE_POWER",
                    "sourceEntityId": "ent-1",
                    "targetEntityId": "ent-2",
                    "source": "animalidade",
                }
            ],
            "groups": [],
        }
    }
    books = loader.load_inventory(operational_overlay=certified_job)
    anim = next(b for b in books if b["bookId"] == "animalidade")
    # Operational fields applied from JobStore:
    assert anim["pipelineStatus"] == "RUNNING"
    assert anim["currentStage"] == "relations"
    assert len(anim["entities"]) == 56
    # Rights must remain strictly canonical:
    assert anim["rightsStatus"] == "UNKNOWN"
    assert anim["publicationMode"] == "NOT_PUBLIC"


def test_archive_inventory_loader_overlay_cannot_modify_rights():
    loader = ArchiveInventoryLoader()
    # Buggy or unauthorized overlay attempting to escalate rights
    hostile_overlay = {
        "4killers": {
            "bookId": "4killers",
            "rightsStatus": "AUTHORIZED",
            "publicationMode": "FULL_TEXT",
            "pipelineStatus": "DONE",
            "currentStage": "qa",
            "entities": [{"id": "ent-1", "name": "Killer", "source": "4killers"}],
        }
    }
    books = loader.load_inventory(operational_overlay=hostile_overlay)
    sample = next(b for b in books if b["bookId"] == "4killers")
    assert sample["pipelineStatus"] == "DONE"
    assert sample["currentStage"] == "qa"
    assert len(sample["entities"]) == 1
    # Rights escalation strictly rejected; canonical values preserved:
    assert sample["rightsStatus"] == "UNKNOWN"
    assert sample["publicationMode"] == "NOT_PUBLIC"


def test_archive_inventory_loader_relation_without_source_fails_closed():
    loader = ArchiveInventoryLoader()
    # Relation with missing or invalid source must never be assigned to animalidade
    bad_overlay = {
        "animalidade": {
            "bookId": "animalidade",
            "pipelineStatus": "RUNNING",
            "currentStage": "relations",
            "entities": [],
            "relations": [
                {
                    "relationId": "r-bad",
                    "type": "CAN_CHOOSE_POWER",
                    "sourceEntityId": "e1",
                    "targetEntityId": "e2",
                }
            ],
        }
    }
    with pytest.raises(ProcessedStateReadError, match="missing required source provenance"):
        loader.load_inventory(operational_overlay=bad_overlay)


def test_archive_inventory_loader_corrupt_artifact_fails_closed(tmp_path):
    jobs_dir = tmp_path / "jobs"
    jobs_dir.mkdir(parents=True)
    corrupt_file = jobs_dir / "corrupt_job.json"
    corrupt_file.write_text("{malformed json", encoding="utf-8")
    with pytest.raises(ProcessedStateReadError):
        load_certified_pilot_artifacts(runtime_dir=tmp_path)


def test_archive_inventory_loader_entity_provenance_mismatch_fails_closed():
    loader = ArchiveInventoryLoader()
    bad_overlay = {
        "animalidade": {
            "bookId": "animalidade",
            "pipelineStatus": "RUNNING",
            "currentStage": "entities",
            "entities": [
                {
                    "id": "ent-1",
                    "name": "Poder Alien",
                    "provenance": {"source": "wrong_book", "pages": [1]},
                }
            ],
            "relations": [],
        }
    }
    with pytest.raises(ProcessedStateReadError, match="source mismatch: 'wrong_book' != 'animalidade'"):
        loader.load_inventory(operational_overlay=bad_overlay)


def test_archive_inventory_loader_relation_source_mismatch_fails_closed():
    loader = ArchiveInventoryLoader()
    bad_overlay = {
        "animalidade": {
            "bookId": "animalidade",
            "pipelineStatus": "RUNNING",
            "currentStage": "relations",
            "entities": [],
            "relations": [
                {
                    "relationId": "r-1",
                    "type": "CAN_CHOOSE_POWER",
                    "sourceEntityId": "e1",
                    "targetEntityId": "e2",
                    "source": "different_book",
                }
            ],
        }
    }
    with pytest.raises(ProcessedStateReadError, match="source provenance or mismatch: 'different_book' != 'animalidade'"):
        loader.load_inventory(operational_overlay=bad_overlay)



def test_archive_inventory_loader_loads_real_animalidade_runtime_artifacts():
    loader = ArchiveInventoryLoader()
    books = loader.load_inventory()
    assert len(books) == 281

    anim = next(b for b in books if b["bookId"] == "animalidade")
    # Animalidade has real accepted bundle in .daemon_runtime with 56 entities and 164 relations
    assert len(anim["entities"]) == 56
    assert len(anim["relations"]) == 164
    assert anim["pipelineStatus"] in ("RUNNING", "NEEDS_HUMAN_REVIEW", "WAITING")
    # Rights must strictly remain canonical
    assert anim["rightsStatus"] == "UNKNOWN"
    assert anim["publicationMode"] == "NOT_PUBLIC"


def _make_test_job(job_id: str, book_id: str, status: str = "in_progress", current_stage: str | None = "entities") -> dict:
    return {
        "schemaVersion": "1.0",
        "jobId": job_id,
        "kind": "book_ingestion",
        "bookId": book_id,
        "status": status,
        "createdAt": "2026-09-09T17:00:00Z",
        "updatedAt": "2026-09-09T17:00:00Z",
        "requestedBy": "human",
        "currentStage": current_stage,
        "stages": {
            "source": "pass",
            "extraction": "pass",
            "editorial": "pass",
            "entities": "pass" if status in ("approved", "done") else "ready",
            "relations": "ready" if current_stage == "relations" else "waiting",
            "frontend": "waiting",
            "qa": "waiting",
            "release": "waiting",
        },
        "humanReviewRequired": False,
        "blockingReasons": [],
        "artifacts": [],
        "history": [],
    }


def test_lineage_selection_favors_certified_reference_over_highest_attempt(tmp_path):
    jobs_dir = tmp_path / "jobs"
    jobs_dir.mkdir(parents=True)
    job_payload = _make_test_job("JOB-SYN-001", "synbook", status="in_progress", current_stage="entities")
    (jobs_dir / "JOB-SYN-001.json").write_text(json.dumps(job_payload), encoding="utf-8")

    # Create 2 accepted entity bundles: att1 (certified) and att2 (unapproved rogue attempt)
    b1_dir = tmp_path / "bundles" / "accepted" / "RB-SYN-ENTITIES-att1-11111111"
    b1_art = b1_dir / "artifacts"
    b1_art.mkdir(parents=True)
    (b1_art / "entities.json").write_text(
        json.dumps([{"id": "ent-1", "name": "Approved Ent", "provenance": {"source": "synbook", "pages": [1]}}]),
        encoding="utf-8",
    )
    (b1_dir / "result-manifest.json").write_text(
        json.dumps({
            "bookId": "synbook",
            "resultBundleId": "RB-SYN-ENTITIES-att1-11111111",
            "attemptNumber": 1,
            "resultManifestSha256": "hash-att1",
        }),
        encoding="utf-8",
    )

    b2_dir = tmp_path / "bundles" / "accepted" / "RB-SYN-ENTITIES-att2-22222222"
    b2_art = b2_dir / "artifacts"
    b2_art.mkdir(parents=True)
    (b2_art / "entities.json").write_text(
        json.dumps([{"id": "ent-2", "name": "Rogue Ent", "provenance": {"source": "synbook", "pages": [1]}}]),
        encoding="utf-8",
    )
    (b2_dir / "result-manifest.json").write_text(
        json.dumps({
            "bookId": "synbook",
            "resultBundleId": "RB-SYN-ENTITIES-att2-22222222",
            "attemptNumber": 2,
            "resultManifestSha256": "hash-att2",
        }),
        encoding="utf-8",
    )

    # Decision certifies att1 explicitly
    dec_dir = tmp_path / "audit" / "pilot" / "synbook" / "decisions"
    dec_dir.mkdir(parents=True)
    (dec_dir / "DEC-SYN-001-ENTITIES-01.json").write_text(
        json.dumps({
            "decisionId": "DEC-SYN-001-ENTITIES-01",
            "decision": "APPROVE",
            "resultBundleId": "RB-SYN-ENTITIES-att1-11111111",
            "reviewedResultManifestSha256": "hash-att1",
        }),
        encoding="utf-8",
    )

    overlay = load_certified_pilot_artifacts(runtime_dir=tmp_path)
    assert "synbook" in overlay
    # Must select att1 entities, NOT att2
    assert len(overlay["synbook"]["entities"]) == 1
    assert overlay["synbook"]["entities"][0]["name"] == "Approved Ent"


def test_multiple_accepted_bundles_without_certification_fails_closed(tmp_path):
    jobs_dir = tmp_path / "jobs"
    jobs_dir.mkdir(parents=True)
    job_payload = _make_test_job("JOB-SYN-001", "synbook", status="in_progress", current_stage="entities")
    (jobs_dir / "JOB-SYN-001.json").write_text(json.dumps(job_payload), encoding="utf-8")

    # Create 2 accepted entity bundles without decision or request
    for att in [1, 2]:
        b_dir = tmp_path / "bundles" / "accepted" / f"RB-SYN-ENTITIES-att{att}-abcdef{att}"
        art = b_dir / "artifacts"
        art.mkdir(parents=True)
        (art / "entities.json").write_text(
            json.dumps([{"id": f"ent-{att}", "name": f"Ent {att}", "provenance": {"source": "synbook", "pages": [1]}}]),
            encoding="utf-8",
        )
        (b_dir / "result-manifest.json").write_text(
            json.dumps({
                "bookId": "synbook",
                "resultBundleId": f"RB-SYN-ENTITIES-att{att}-abcdef{att}",
                "attemptNumber": att,
            }),
            encoding="utf-8",
        )

    with pytest.raises(ProcessedStateReadError, match="Multiple accepted entities bundles"):
        load_certified_pilot_artifacts(runtime_dir=tmp_path)


def test_multiple_jobs_for_same_book_fails_closed(tmp_path):
    jobs_dir = tmp_path / "jobs"
    jobs_dir.mkdir(parents=True)
    j1 = _make_test_job("JOB-A-001", "booka", status="in_progress")
    j2 = _make_test_job("JOB-A-002", "booka", status="todo")
    (jobs_dir / "JOB-A-001.json").write_text(json.dumps(j1), encoding="utf-8")
    (jobs_dir / "JOB-A-002.json").write_text(json.dumps(j2), encoding="utf-8")

    with pytest.raises(ProcessedStateReadError, match="Multiple jobs found for bookId 'booka'"):
        load_certified_pilot_artifacts(runtime_dir=tmp_path)


def test_cross_stage_lineage_mismatch_fails_closed(tmp_path):
    jobs_dir = tmp_path / "jobs"
    jobs_dir.mkdir(parents=True)
    job_payload = _make_test_job("JOB-SYN-001", "synbook", status="needs_review", current_stage="relations")
    (jobs_dir / "JOB-SYN-001.json").write_text(json.dumps(job_payload), encoding="utf-8")

    # Certified entities bundle att1
    ent_dir = tmp_path / "bundles" / "accepted" / "RB-SYN-ENTITIES-att1-11111111"
    ent_art = ent_dir / "artifacts"
    ent_art.mkdir(parents=True)
    (ent_art / "entities.json").write_text(
        json.dumps([{"id": "ent-1", "name": "Ent 1", "provenance": {"source": "synbook", "pages": [1]}}]),
        encoding="utf-8",
    )
    (ent_dir / "result-manifest.json").write_text(
        json.dumps({"bookId": "synbook", "resultBundleId": "RB-SYN-ENTITIES-att1-11111111", "attemptNumber": 1}),
        encoding="utf-8",
    )

    # Relations bundle claiming to be built from mismatched ent att2
    rel_dir = tmp_path / "bundles" / "accepted" / "RB-SYN-RELATIONS-att1-99999999"
    rel_art = rel_dir / "artifacts"
    rel_art.mkdir(parents=True)
    (rel_art / "relations.json").write_text(
        json.dumps([{"relationId": "r-1", "type": "CAN_CHOOSE_POWER", "sourceEntityId": "ent-1", "targetEntityId": "ent-2", "source": "synbook"}]),
        encoding="utf-8",
    )
    (rel_dir / "result-manifest.json").write_text(
        json.dumps({
            "bookId": "synbook",
            "resultBundleId": "RB-SYN-RELATIONS-att1-99999999",
            "attemptNumber": 1,
            "inputEntitiesBundle": "RB-SYN-ENTITIES-att2-22222222",
        }),
        encoding="utf-8",
    )

    with pytest.raises(ProcessedStateReadError, match="Cross-stage lineage mismatch"):
        load_certified_pilot_artifacts(runtime_dir=tmp_path)


def test_manifest_hash_mismatch_fails_closed(tmp_path):
    jobs_dir = tmp_path / "jobs"
    jobs_dir.mkdir(parents=True)
    job_payload = _make_test_job("JOB-SYN-001", "synbook", status="approved", current_stage="entities")
    (jobs_dir / "JOB-SYN-001.json").write_text(json.dumps(job_payload), encoding="utf-8")

    ent_dir = tmp_path / "bundles" / "accepted" / "RB-SYN-ENTITIES-att1-11111111"
    ent_art = ent_dir / "artifacts"
    ent_art.mkdir(parents=True)
    (ent_art / "entities.json").write_text(
        json.dumps([{"id": "ent-1", "name": "Ent 1", "provenance": {"source": "synbook", "pages": [1]}}]),
        encoding="utf-8",
    )
    (ent_dir / "result-manifest.json").write_text(
        json.dumps({"bookId": "synbook", "resultBundleId": "RB-SYN-ENTITIES-att1-11111111", "attemptNumber": 1, "resultManifestSha256": "actual_sha"}),
        encoding="utf-8",
    )

    dec_dir = tmp_path / "audit" / "pilot" / "synbook" / "decisions"
    dec_dir.mkdir(parents=True)
    (dec_dir / "DEC-SYN-001-ENTITIES-01.json").write_text(
        json.dumps({
            "decisionId": "DEC-SYN-001-ENTITIES-01",
            "decision": "APPROVE",
            "resultBundleId": "RB-SYN-ENTITIES-att1-11111111",
            "reviewedResultManifestSha256": "tampered_sha_expected",
        }),
        encoding="utf-8",
    )

    with pytest.raises(ProcessedStateReadError, match="Manifest hash mismatch"):
        load_certified_pilot_artifacts(runtime_dir=tmp_path)


def test_canonical_runtime_resolution_precedence(tmp_path, monkeypatch):
    from scripts.agents.archive_inventory_loader import resolve_canonical_runtime_dir

    # Tier 1: Explicit argument
    explicit_dir = tmp_path / "explicit_runtime"
    explicit_dir.mkdir()
    res1 = resolve_canonical_runtime_dir(explicit_dir)
    assert res1 == explicit_dir.resolve()

    # Tier 2: Environment variable
    env_dir = tmp_path / "env_runtime"
    env_dir.mkdir()
    monkeypatch.setenv("DAEMON_RUNTIME_DIR", str(env_dir))
    res2 = resolve_canonical_runtime_dir()
    assert res2 == env_dir.resolve()

    # Explicit argument still beats env var
    res3 = resolve_canonical_runtime_dir(explicit_dir)
    assert res3 == explicit_dir.resolve()

