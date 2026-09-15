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

