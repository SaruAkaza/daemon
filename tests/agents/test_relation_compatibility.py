from __future__ import annotations

import pytest

from scripts.agents.relation_compatibility import RelationCompatibilityValidator


def test_validator_accepts_valid_has_power():
    validator = RelationCompatibilityValidator()
    entity_index = {
        "ent-creature": {
            "id": "ent-creature",
            "name": "Lobo das Cavernas",
            "category": "creature_npc",
        },
        "ent-power": {
            "id": "ent-power",
            "name": "Visao Noturna",
            "category": "character_option",
            "subtype": "aprimoramento",
        },
    }
    relation = {
        "id": "rel-01",
        "type": "HAS_POWER",
        "sourceEntityId": "ent-creature",
        "targetEntityId": "ent-power",
    }
    is_valid, error = validator.validate_relation(relation, entity_index)
    assert is_valid is True
    assert error is None


def test_validator_accepts_valid_can_choose_power():
    validator = RelationCompatibilityValidator()
    entity_index = {
        "ent-creature": {
            "id": "ent-creature",
            "name": "Lobo das Cavernas",
            "category": "creature_npc",
        },
        "ent-power": {
            "id": "ent-power",
            "name": "Faro Agucado",
            "category": "character_option",
            "subtype": "poder",
        },
    }
    relation = {
        "id": "rel-02",
        "type": "CAN_CHOOSE_POWER",
        "sourceEntityId": "ent-creature",
        "targetEntityId": "ent-power",
    }
    is_valid, error = validator.validate_relation(relation, entity_index)
    assert is_valid is True
    assert error is None


def test_validator_accepts_valid_has_weakness():
    validator = RelationCompatibilityValidator()
    entity_index = {
        "ent-creature": {
            "id": "ent-creature",
            "name": "Lobo das Cavernas",
            "category": "creature_npc",
        },
        "ent-weakness": {
            "id": "ent-weakness",
            "name": "Vulnerabilidade ao Fogo",
            "category": "character_option",
            "subtype": "aprimoramento",
        },
    }
    relation = {
        "id": "rel-03",
        "type": "HAS_WEAKNESS",
        "sourceEntityId": "ent-creature",
        "targetEntityId": "ent-weakness",
    }
    is_valid, error = validator.validate_relation(relation, entity_index)
    assert is_valid is True
    assert error is None


def test_validator_rejects_has_power_with_invalid_target_category():
    validator = RelationCompatibilityValidator()
    entity_index = {
        "ent-creature": {
            "id": "ent-creature",
            "name": "Lobo das Cavernas",
            "category": "creature_npc",
        },
        "ent-rule": {
            "id": "ent-rule",
            "name": "Regra de Dano",
            "category": "rules_mechanics",
        },
    }
    relation = {
        "id": "rel-04",
        "type": "HAS_POWER",
        "sourceEntityId": "ent-creature",
        "targetEntityId": "ent-rule",
    }
    is_valid, error = validator.validate_relation(relation, entity_index)
    assert is_valid is False
    assert error == "Target category 'rules_mechanics' not allowed for HAS_POWER."


def test_validator_rejects_missing_target_entity():
    validator = RelationCompatibilityValidator()
    entity_index = {
        "ent-creature": {
            "id": "ent-creature",
            "name": "Lobo das Cavernas",
            "category": "creature_npc",
        },
    }
    relation = {
        "id": "rel-05",
        "type": "HAS_POWER",
        "sourceEntityId": "ent-creature",
        "targetEntityId": "missing-entity-id",
    }
    is_valid, error = validator.validate_relation(relation, entity_index)
    assert is_valid is False
    assert error == "Target entity 'missing-entity-id' not found in local entities context."


def test_validator_collection_aggregates_errors():
    validator = RelationCompatibilityValidator()
    entity_index = {
        "ent-creature": {
            "id": "ent-creature",
            "name": "Lobo das Cavernas",
            "category": "creature_npc",
        },
        "ent-power": {
            "id": "ent-power",
            "name": "Visao Noturna",
            "category": "character_option",
            "subtype": "aprimoramento",
        },
        "ent-rule": {
            "id": "ent-rule",
            "name": "Regra de Dano",
            "category": "rules_mechanics",
        },
    }
    relations = [
        {
            "id": "rel-ok",
            "type": "HAS_POWER",
            "sourceEntityId": "ent-creature",
            "targetEntityId": "ent-power",
        },
        {
            "id": "rel-bad-target-cat",
            "type": "HAS_POWER",
            "sourceEntityId": "ent-creature",
            "targetEntityId": "ent-rule",
        },
        {
            "id": "rel-missing-target",
            "type": "HAS_POWER",
            "sourceEntityId": "ent-creature",
            "targetEntityId": "nonexistent-id",
        },
    ]
    errors = validator.validate_collection(relations, entity_index)
    assert len(errors) == 2
    assert "Target category 'rules_mechanics' not allowed for HAS_POWER." in errors
    assert "Target entity 'nonexistent-id' not found in local entities context." in errors
