from __future__ import annotations

import pytest
from scripts.agents.legacy_comparator import (
    LegacyComparator,
    LegacyComparisonResult,
    LegacyDiscrepancy,
)


def test_compare_exact_semantic_equivalent():
    extracted = [
        {
            "id": "power-anim-01",
            "name": "Olhos da Fera",
            "cost": 1,
            "description": "Permite enxergar no escuro.\n",
            "provenance": {"bookId": "animalidade", "page": 10},
        }
    ]
    legacy = [
        {
            "id": "power-anim-01",
            "name": "Olhos da Fera ",
            "cost": 1,
            "description": "Permite enxergar no escuro.",
        }
    ]

    comparator = LegacyComparator()
    result = comparator.compare_entities(extracted, legacy)

    assert isinstance(result, LegacyComparisonResult)
    assert result.verdict == "SEMANTIC_EQUIVALENT"
    assert result.equivalent_count == 1
    assert result.semantic_diff_count == 0
    assert len(result.discrepancies) == 0


def test_compare_semantic_difference():
    extracted = [
        {
            "id": "creature-lobo",
            "name": "Lobo",
            "attributes": {"forca": 14, "agilidade": 16},
            "source": "Animalidade p. 25",
        }
    ]
    legacy = [
        {
            "id": "creature-lobo",
            "name": "Lobo",
            "attributes": {"forca": 12, "agilidade": 16},
            "source": "Trevas 3a ed p. 110",
        }
    ]

    comparator = LegacyComparator()
    result = comparator.compare_entities(extracted, legacy)

    assert result.verdict == "SEMANTIC_DIFFERENCE"
    assert result.semantic_diff_count == 1
    assert len(result.discrepancies) == 1

    disc = result.discrepancies[0]
    assert disc.entity_id == "creature-lobo"
    assert "attributes.forca" in disc.field_path
    assert disc.extracted_value == 14
    assert disc.legacy_value == 12


def test_compare_structural_difference_only():
    extracted = [
        {
            "id": "spell-anim-01",
            "name": "Garras",
            "stats": {"damage": "1d6"},
            "schemaVersion": "2.0",
        }
    ]
    legacy = [
        {
            "id": "spell-anim-01",
            "name": "Garras",
            "damage": "1d6",
        }
    ]

    comparator = LegacyComparator()
    result = comparator.compare_entities(extracted, legacy)

    assert result.verdict == "STRUCTURAL_DIFFERENCE_ONLY"
    assert result.structural_diff_count == 1
    assert result.semantic_diff_count == 0


def test_compare_no_legacy_reference():
    extracted = [
        {
            "id": "new-ritual-anim-99",
            "name": "Ritual Inedito",
            "source": "Animalidade p. 50",
        }
    ]
    legacy = []

    comparator = LegacyComparator()
    result = comparator.compare_entities(extracted, legacy)

    assert result.verdict == "NO_LEGACY_REFERENCE"
    assert result.new_entities_count == 1
    assert result.semantic_diff_count == 0


def test_mixed_with_semantic_difference_precedence():
    extracted = [
        {
            "id": "ent-01",
            "name": "Equivalent Entity",
            "val": 10,
        },
        {
            "id": "ent-02",
            "name": "Divergent Entity",
            "val": 99,
        },
    ]
    legacy = [
        {
            "id": "ent-01",
            "name": "Equivalent Entity",
            "val": 10,
        },
        {
            "id": "ent-02",
            "name": "Divergent Entity",
            "val": 20,
        },
    ]

    comparator = LegacyComparator()
    result = comparator.compare_entities(extracted, legacy)

    assert result.verdict == "SEMANTIC_DIFFERENCE"
    assert result.equivalent_count == 1
    assert result.semantic_diff_count == 1
    assert len(result.discrepancies) == 1


def test_terminal_key_collision_preserves_all_discrepancies():
    # Both combat.attack.bonus and combat.defense.bonus end with 'bonus'
    extracted = [
        {
            "id": "item-sword",
            "name": "Sword",
            "combat": {
                "attack": {"bonus": 2},
                "defense": {"bonus": 1},
            },
        }
    ]
    # In legacy, structure has attack.bonus = 5 and defense.bonus = 4
    legacy = [
        {
            "id": "item-sword",
            "name": "Sword",
            "stats": {
                "attack": {"bonus": 5},
                "defense": {"bonus": 4},
            },
        }
    ]

    comparator = LegacyComparator()
    result = comparator.compare_entities(extracted, legacy)

    assert result.verdict == "SEMANTIC_DIFFERENCE"
    assert result.semantic_diff_count == 1
    # MUST detect BOTH discrepancies without overwriting terminal keys
    assert len(result.discrepancies) == 2
    paths = {d.field_path for d in result.discrepancies}
    assert "combat.attack.bonus" in paths
    assert "combat.defense.bonus" in paths

