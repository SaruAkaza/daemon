import copy
import json
from pathlib import Path
import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS_DIR = ROOT / "schemas"
COMPATIBILITY_SCHEMA_PATH = SCHEMAS_DIR / "relation-compatibility.schema.json"
COMPATIBILITY_MATRIX_PATH = SCHEMAS_DIR / "relation-compatibility-v2.json"
DOC_PATH = ROOT / "docs" / "reference" / "relation-compatibility-v2.md"

ALL_13_PREDICATES = {
    "REQUIRES",
    "GRANTS",
    "BELONGS_TO",
    "DERIVED_FROM",
    "APPEARS_IN",
    "MODIFIES",
    "REPLACES",
    "ALTERNATIVE_TO",
    "HAS_POWER",
    "CAN_CHOOSE_POWER",
    "HAS_WEAKNESS",
    "HAS_SKILL",
    "USES_RULE",
}


def load_compatibility_schema() -> dict:
    if not COMPATIBILITY_SCHEMA_PATH.exists():
        raise FileNotFoundError(
            f"schemas/relation-compatibility.schema.json does not exist: {COMPATIBILITY_SCHEMA_PATH}"
        )
    return json.loads(COMPATIBILITY_SCHEMA_PATH.read_text(encoding="utf-8"))


def load_compatibility_matrix() -> dict:
    if not COMPATIBILITY_MATRIX_PATH.exists():
        raise FileNotFoundError(
            f"schemas/relation-compatibility-v2.json does not exist: {COMPATIBILITY_MATRIX_PATH}"
        )
    return json.loads(COMPATIBILITY_MATRIX_PATH.read_text(encoding="utf-8"))


def get_matrix_validator() -> Draft202012Validator:
    schema = load_compatibility_schema()
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def test_matrix_validates_against_compatibility_schema():
    validator = get_matrix_validator()
    matrix = load_compatibility_matrix()
    validator.validate(matrix)
    assert validator.is_valid(matrix)

    # Test rejecting invalid payload: additional top-level property
    invalid_matrix_extra_prop = copy.deepcopy(matrix)
    invalid_matrix_extra_prop["extraProp"] = "invalid"
    assert not validator.is_valid(invalid_matrix_extra_prop)
    with pytest.raises(ValidationError):
        validator.validate(invalid_matrix_extra_prop)

    # Test rejecting invalid payload: unknown relationType
    invalid_matrix_bad_type = copy.deepcopy(matrix)
    invalid_matrix_bad_type["rules"][0]["relationType"] = "INVALID_RELATION_TYPE"
    assert not validator.is_valid(invalid_matrix_bad_type)
    with pytest.raises(ValidationError):
        validator.validate(invalid_matrix_bad_type)


def test_matrix_contains_all_13_predicates():
    matrix = load_compatibility_matrix()
    assert matrix.get("version") == "2.0.0"
    assert matrix.get("ontologyVersion") == "relations-v2"

    rules = matrix.get("rules", [])
    assert len(rules) == 13

    predicates = [rule["relationType"] for rule in rules]
    assert set(predicates) == ALL_13_PREDICATES
    # Verify no duplicates among the 13 rule relationTypes
    assert len(predicates) == len(set(predicates))


def test_matrix_disallows_can_choose_weakness():
    matrix = load_compatibility_matrix()
    rules = matrix.get("rules", [])
    predicates = {rule["relationType"] for rule in rules}
    assert "CAN_CHOOSE_WEAKNESS" not in predicates


def test_explanatory_doc_references_matrix_without_triplet_duplication():
    assert DOC_PATH.exists(), f"Expected documentation file does not exist: {DOC_PATH}"
    content = DOC_PATH.read_text(encoding="utf-8")

    # Explanatory reference linking to canonical authority JSON
    assert "schemas/relation-compatibility-v2.json" in content
    assert "markdown = explanatory only" in content
    assert "canonical authority" in content.lower() or "autoridade canônica" in content.lower()

    # Verify no full triplet table duplication (e.g. no exhaustive source/target table)
    assert "| Origem Permitida | Destino Permitido |" not in content
    assert "| allowedSourceCategories | allowedTargetCategories |" not in content
