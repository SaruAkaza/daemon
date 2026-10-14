from __future__ import annotations

import json
from pathlib import Path
import pytest

from scripts.agents.restricted_workspace import RestrictedPilotWorkspace
from scripts.agents.pilot_qa_validator import PilotQAValidator, DatasetQAVerdict


@pytest.fixture
def make_workspace(tmp_path: Path):
    def _create(
        entities: list[dict],
        relations: list[dict] | None = None,
        unresolved_relations: list[dict] | None = None,
    ) -> Path:
        ws_root = RestrictedPilotWorkspace.get_workspace_path(tmp_path, "animalidade")
        RestrictedPilotWorkspace.initialize_layout(ws_root)

        # Write entities
        ent_file = ws_root / "data" / "entities" / "creature_npc.json"
        ent_file.write_text(json.dumps(entities), encoding="utf-8")

        # Write relations
        if relations is not None:
            rel_file = ws_root / "data" / "entities" / "relations.json"
            rel_file.write_text(json.dumps(relations), encoding="utf-8")

        # Write unresolved relations
        if unresolved_relations is not None:
            unrel_file = ws_root / "data" / "entities" / "unresolved-relations.json"
            unrel_file.write_text(json.dumps(unresolved_relations), encoding="utf-8")

        return ws_root

    return _create


def test_validate_dataset_success(make_workspace):
    entities = [
        {
            "id": "creature-lobo",
            "name": "Lobo",
            "category": "creature_npc",
            "source": "animalidade",
            "page": 1,
            "entries": ["Descrição do lobo selvagem."],
        },
        {
            "id": "power-faro",
            "name": "Faro Aguçado",
            "category": "character_option",
            "subtype": "poder",
            "source": "animalidade",
            "page": 2,
            "entries": ["Sentidos apurados."],
        },
    ]
    relations = [
        {
            "schemaVersion": "1.0",
            "id": "rel-lobo-faro-001",
            "type": "HAS_POWER",
            "sourceEntityId": "creature-lobo",
            "targetEntityId": "power-faro",
            "source": "animalidade",
            "page": 1,
            "confidence": 1.0,
        }
    ]

    ws = make_workspace(entities, relations)
    validator = PilotQAValidator()
    verdict = validator.validate_dataset(ws, "animalidade", expected_pages=2)

    assert isinstance(verdict, DatasetQAVerdict)
    assert verdict.passed is True
    assert len(verdict.errors) == 0
    assert verdict.pages_covered == {1, 2}
    assert verdict.total_pages == 2
    assert verdict.entity_count == 2
    assert verdict.relation_count == 1


def test_validate_dataset_missing_page_coverage(make_workspace):
    # Only page 1 covered, expected 2
    entities = [
        {
            "id": "creature-lobo",
            "name": "Lobo",
            "category": "creature_npc",
            "source": "animalidade",
            "page": 1,
            "entries": ["Lobo selvagem."],
        }
    ]
    ws = make_workspace(entities)
    validator = PilotQAValidator()
    verdict = validator.validate_dataset(ws, "animalidade", expected_pages=2)

    assert verdict.passed is False
    assert any("Missing coverage for page 2" in err for err in verdict.errors)
    assert verdict.pages_covered == {1}


def test_validate_dataset_missing_provenance(make_workspace):
    entities = [
        {
            "id": "creature-lobo",
            "name": "Lobo",
            "category": "creature_npc",
            "source": "animalidade",
            "page": None,  # Missing page
            "entries": ["Lobo selvagem."],
        }
    ]
    ws = make_workspace(entities)
    validator = PilotQAValidator()
    verdict = validator.validate_dataset(ws, "animalidade", expected_pages=1)

    assert verdict.passed is False
    assert any("provenance" in err.lower() or "page" in err.lower() for err in verdict.errors)


def test_validate_dataset_broken_relation(make_workspace):
    entities = [
        {
            "id": "creature-lobo",
            "name": "Lobo",
            "category": "creature_npc",
            "source": "animalidade",
            "page": 1,
            "entries": ["Lobo selvagem."],
        }
    ]
    relations = [
        {
            "schemaVersion": "1.0",
            "id": "rel-lobo-broken",
            "type": "HAS_POWER",
            "sourceEntityId": "creature-lobo",
            "targetEntityId": "power-nonexistent",  # Broken target
            "source": "animalidade",
            "page": 1,
            "confidence": 1.0,
        }
    ]
    ws = make_workspace(entities, relations)
    validator = PilotQAValidator()
    verdict = validator.validate_dataset(ws, "animalidade", expected_pages=1)

    assert verdict.passed is False
    assert any("broken" in err.lower() or "power-nonexistent" in err for err in verdict.errors)


def test_qa_validator_enforces_semantic_compatibility(make_workspace):
    entities = [
        {
            "id": "creature-lobo",
            "name": "Lobo",
            "category": "creature_npc",
            "source": "animalidade",
            "page": 1,
            "entries": ["Lobo selvagem."],
        },
        {
            "id": "creature-urso",
            "name": "Urso",
            "category": "creature_npc",
            "source": "animalidade",
            "page": 2,
            "entries": ["Urso pardo."],
        },
    ]
    relations = [
        {
            "schemaVersion": "1.0",
            "id": "rel-lobo-urso-bad",
            "type": "HAS_POWER",
            "sourceEntityId": "creature-lobo",
            "targetEntityId": "creature-urso",
            "source": "animalidade",
            "page": 1,
            "confidence": 1.0,
        }
    ]
    ws = make_workspace(entities, relations)
    validator = PilotQAValidator()
    verdict = validator.validate_dataset(ws, "animalidade", expected_pages=2)

    assert verdict.passed is False
    assert any("Semantic compatibility failed" in err for err in verdict.errors)


def test_qa_validator_validates_unresolved_relations_file(make_workspace):
    entities = [
        {
            "id": "creature-lobo",
            "name": "Lobo",
            "category": "creature_npc",
            "source": "animalidade",
            "page": 1,
            "entries": ["Lobo selvagem."],
        }
    ]
    unresolved_relations = [
        {
            "sourceEntityId": "creature-lobo",
            "candidateRelationType": "REQUIRES",
            "candidateTargetEntityId": "skill-rastreamento-externa",
            "rawReferenceText": "Exige perícia Rastreamento.",
            "sourcePage": 1,
            "sourceParagraph": 2,
            "reason": "Perícia externa não catalogada no livro local.",
            "status": "UNRESOLVED_PENDING_CROSS_BOOK_LINK",
        }
    ]
    ws = make_workspace(entities, unresolved_relations=unresolved_relations)
    validator = PilotQAValidator()
    verdict = validator.validate_dataset(ws, "animalidade", expected_pages=1)

    assert verdict.passed is True
    assert len(verdict.errors) == 0


def test_qa_validator_rejects_unresolved_pointing_to_known_entity(make_workspace):
    entities = [
        {
            "id": "creature-lobo",
            "name": "Lobo",
            "category": "creature_npc",
            "source": "animalidade",
            "page": 1,
            "entries": ["Lobo selvagem."],
        },
        {
            "id": "power-faro",
            "name": "Faro Aguçado",
            "category": "character_option",
            "subtype": "poder",
            "source": "animalidade",
            "page": 1,
            "entries": ["Sentidos apurados."],
        },
    ]
    unresolved_relations = [
        {
            "sourceEntityId": "creature-lobo",
            "candidateRelationType": "HAS_POWER",
            "candidateTargetEntityId": "power-faro",
            "rawReferenceText": "Possui faro aguçado.",
            "sourcePage": 1,
            "sourceParagraph": 1,
            "reason": "Deveria estar em relations.json.",
            "status": "UNRESOLVED_PENDING_CROSS_BOOK_LINK",
        }
    ]
    ws = make_workspace(entities, unresolved_relations=unresolved_relations)
    validator = PilotQAValidator()
    verdict = validator.validate_dataset(ws, "animalidade", expected_pages=1)

    assert verdict.passed is False
    assert any("targets local known entity" in err or "must be in relations.json" in err for err in verdict.errors)

