import copy
import json
from pathlib import Path
import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS_DIR = ROOT / "schemas"
RELATION_SCHEMA_PATH = SCHEMAS_DIR / "relation.schema.json"
COLLECTION_SCHEMA_PATH = SCHEMAS_DIR / "relation-collection.schema.json"

VALID_RELATION_ITEM = {
    "schemaVersion": "1.0",
    "id": "rel-cacador-teologia-001",
    "type": "REQUIRES",
    "sourceEntityId": "kit:cacador-de-bruxas",
    "targetEntityId": "skill:teologia",
    "source": "inquisicao",
    "page": 14,
    "confidence": 1.0,
}


def get_item_validator() -> Draft202012Validator:
    raw = RELATION_SCHEMA_PATH.read_text(encoding="utf-8")
    schema = json.loads(raw)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def get_collection_validator() -> Draft202012Validator:
    raw_item = RELATION_SCHEMA_PATH.read_text(encoding="utf-8")
    item_schema = json.loads(raw_item)
    raw_coll = COLLECTION_SCHEMA_PATH.read_text(encoding="utf-8")
    coll_schema = json.loads(raw_coll)
    Draft202012Validator.check_schema(coll_schema)
    resource = Resource.from_contents(item_schema)
    registry = (resource @ Registry()).with_resource("relation.schema.json", resource)
    return Draft202012Validator(coll_schema, registry=registry)


def test_relation_item_schema_accepts_valid_item():
    validator = get_item_validator()
    validator.validate(VALID_RELATION_ITEM)
    assert validator.is_valid(VALID_RELATION_ITEM)


def test_relation_item_schema_accepts_v2_predicates():
    validator = get_item_validator()
    for predicate in ["CAN_CHOOSE_POWER", "HAS_WEAKNESS"]:
        item = copy.deepcopy(VALID_RELATION_ITEM)
        item["id"] = f"rel-test-{predicate.lower()}-001"
        item["type"] = predicate
        validator.validate(item)
        assert validator.is_valid(item)


def test_relation_item_schema_rejects_array():
    validator = get_item_validator()
    array_payload = [copy.deepcopy(VALID_RELATION_ITEM)]
    assert not validator.is_valid(array_payload)
    with pytest.raises(ValidationError):
        validator.validate(array_payload)


def test_relation_collection_schema_accepts_valid_array():
    coll_validator = get_collection_validator()
    array_payload = [
        copy.deepcopy(VALID_RELATION_ITEM),
        {
            **VALID_RELATION_ITEM,
            "id": "rel-cacador-visao-002",
            "type": "GRANTS",
            "targetEntityId": "power:visao-noturna",
            "page": 15,
        },
    ]
    coll_validator.validate(array_payload)
    assert coll_validator.is_valid(array_payload)


def test_relation_collection_schema_rejects_single_object():
    coll_validator = get_collection_validator()
    assert not coll_validator.is_valid(VALID_RELATION_ITEM)
    with pytest.raises(ValidationError):
        coll_validator.validate(VALID_RELATION_ITEM)


def test_relation_collection_schema_rejects_invalid_member():
    coll_validator = get_collection_validator()
    # Test missing required field
    invalid_item_missing_field = copy.deepcopy(VALID_RELATION_ITEM)
    del invalid_item_missing_field["confidence"]
    assert not coll_validator.is_valid([invalid_item_missing_field])
    with pytest.raises(ValidationError):
        coll_validator.validate([invalid_item_missing_field])

    # Test invalid predicate type
    invalid_item_bad_type = copy.deepcopy(VALID_RELATION_ITEM)
    invalid_item_bad_type["type"] = "INVALID_RELATION_PREDICATE"
    assert not coll_validator.is_valid([invalid_item_bad_type])
    with pytest.raises(ValidationError):
        coll_validator.validate([invalid_item_bad_type])


def test_relation_collection_schema_accepts_empty_array():
    coll_validator = get_collection_validator()
    coll_validator.validate([])
    assert coll_validator.is_valid([])
