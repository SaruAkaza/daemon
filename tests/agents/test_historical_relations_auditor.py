from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.agents.historical_relations_auditor import HistoricalRelationsAuditor


def test_auditor_scans_historical_relations_read_only(tmp_path: Path):
    data_dir = tmp_path / "data"
    entities_dir = data_dir / "entities"
    entities_dir.mkdir(parents=True)

    entities = [
        {
            "id": "creature-lobo",
            "name": "Lobo",
            "category": "creature_npc",
            "source": "manual-monstros",
            "page": 10,
        },
        {
            "id": "power-visao",
            "name": "Visão Noturna",
            "category": "character_option",
            "subtype": "aprimoramento",
            "source": "manual-monstros",
            "page": 11,
        },
    ]
    (entities_dir / "creature_npc.json").write_text(
        json.dumps(entities, ensure_ascii=False), encoding="utf-8"
    )

    relations = [
        {
            "id": "rel-01",
            "type": "HAS_POWER",
            "sourceEntityId": "creature-lobo",
            "targetEntityId": "power-visao",
        },
        {
            "id": "rel-02",
            "type": "REQUIRES",
            "sourceEntityId": "creature-lobo",
            "targetEntityId": "power-visao",
        },
    ]
    rel_file = entities_dir / "relations.json"
    rel_file.write_text(json.dumps(relations, ensure_ascii=False), encoding="utf-8")

    initial_content = rel_file.read_text(encoding="utf-8")
    initial_mtime = rel_file.stat().st_mtime

    auditor = HistoricalRelationsAuditor(data_dir=data_dir)
    report = auditor.scan()

    # Verify read-only: files must not be modified
    assert rel_file.read_text(encoding="utf-8") == initial_content
    assert rel_file.stat().st_mtime == initial_mtime

    # Verify report structure
    assert report["totalRelationsScanned"] == 2
    assert report["hasPowerCount"] == 1
    assert report["recommendations"] == {
        "keepHasPower": 1,
        "migrateToCanChoosePower": 0,
        "migrateToHasWeakness": 0,
        "migrateToUnresolved": 0,
        "invalidTriplets": 0,
    }
    assert len(report["itemized"]) == 1
    item = report["itemized"][0]
    assert item["relationId"] == "rel-01"
    assert item["classification"] == "ACTUAL_POSSESSION"
    assert item["recommendation"] == "keepHasPower"


def test_auditor_correctly_classifies_selectable_options(tmp_path: Path):
    data_dir = tmp_path / "data"
    entities_dir = data_dir / "entities"
    entities_dir.mkdir(parents=True)

    entities = [
        {
            "id": "creature-mago",
            "name": "Mago Aprendiz",
            "category": "creature_npc",
            "source": "grimorio",
            "page": 5,
        },
        {
            "id": "power-bola-fogo",
            "name": "Bola de Fogo",
            "category": "character_option",
            "subtype": "magia",
            "source": "grimorio",
            "page": 20,
        },
    ]
    (entities_dir / "creatures.json").write_text(
        json.dumps(entities, ensure_ascii=False), encoding="utf-8"
    )

    relations = [
        {
            "id": "rel-choice-01",
            "type": "HAS_POWER",
            "sourceEntityId": "creature-mago",
            "targetEntityId": "power-bola-fogo",
            "evidence": "O conjurador tem como escolha uma magia da lista de possíveis opções.",
        }
    ]
    (entities_dir / "relations.json").write_text(
        json.dumps(relations, ensure_ascii=False), encoding="utf-8"
    )

    auditor = HistoricalRelationsAuditor(data_dir=data_dir)
    report = auditor.scan()

    assert report["totalRelationsScanned"] == 1
    assert report["hasPowerCount"] == 1
    assert report["recommendations"]["migrateToCanChoosePower"] == 1
    assert len(report["itemized"]) == 1
    item = report["itemized"][0]
    assert item["relationId"] == "rel-choice-01"
    assert item["classification"] == "SELECTABLE_OPTION"
    assert item["recommendation"] == "migrateToCanChoosePower"


def test_auditor_identifies_unresolved_references(tmp_path: Path):
    data_dir = tmp_path / "data"
    entities_dir = data_dir / "entities"
    entities_dir.mkdir(parents=True)

    entities = [
        {
            "id": "creature-vampiro",
            "name": "Vampiro",
            "category": "creature_npc",
            "source": "manual",
            "page": 12,
        }
    ]
    (entities_dir / "creature_npc.json").write_text(
        json.dumps(entities, ensure_ascii=False), encoding="utf-8"
    )

    relations = [
        {
            "id": "rel-unresolved-01",
            "type": "HAS_POWER",
            "sourceEntityId": "creature-vampiro",
            "targetEntityId": "power-inexistente",
        }
    ]
    (entities_dir / "relations.json").write_text(
        json.dumps(relations, ensure_ascii=False), encoding="utf-8"
    )

    auditor = HistoricalRelationsAuditor(data_dir=data_dir)
    report = auditor.scan()

    assert report["totalRelationsScanned"] == 1
    assert report["hasPowerCount"] == 1
    assert report["recommendations"]["migrateToUnresolved"] == 1
    assert len(report["itemized"]) == 1
    item = report["itemized"][0]
    assert item["relationId"] == "rel-unresolved-01"
    assert item["classification"] == "UNRESOLVED_REFERENCE"
    assert item["recommendation"] == "migrateToUnresolved"
