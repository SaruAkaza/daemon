import copy
import json
from pathlib import Path
import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS_DIR = ROOT / "schemas"
UNRESOLVED_RELATION_SCHEMA_PATH = SCHEMAS_DIR / "unresolved-relation.schema.json"
COLLECTION_SCHEMA_PATH = SCHEMAS_DIR / "unresolved-relation-collection.schema.json"

VALID_UNRESOLVED_ITEM = {
    "sourceEntityId": "kit:cacador-de-bruxas",
    "candidateRelationType": "REQUIRES",
    "candidateTargetEntityId": "skill:ocultismo",
    "rawReferenceText": "Exige conhecimento prévio de Ocultismo 40%",
    "sourcePage": 14,
    "sourceParagraph": 3,
    "reason": "Perícia externa não catalogada no livro local.",
    "status": "UNRESOLVED_PENDING_CROSS_BOOK_LINK",
}


def get_item_validator() -> Draft202012Validator:
    raw = UNRESOLVED_RELATION_SCHEMA_PATH.read_text(encoding="utf-8")
    schema = json.loads(raw)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def get_collection_validator() -> Draft202012Validator:
    raw_item = UNRESOLVED_RELATION_SCHEMA_PATH.read_text(encoding="utf-8")
    item_schema = json.loads(raw_item)
    raw_coll = COLLECTION_SCHEMA_PATH.read_text(encoding="utf-8")
    coll_schema = json.loads(raw_coll)
    Draft202012Validator.check_schema(coll_schema)
    resource = Resource.from_contents(item_schema)
    registry = (resource @ Registry()).with_resource("unresolved-relation.schema.json", resource)
    return Draft202012Validator(coll_schema, registry=registry)


def test_unresolved_relation_valid_item():
    validator = get_item_validator()
    validator.validate(VALID_UNRESOLVED_ITEM)
    assert validator.is_valid(VALID_UNRESOLVED_ITEM)


def test_unresolved_relation_missing_evidence_rejected():
    validator = get_item_validator()
    for field in ["rawReferenceText", "sourcePage", "sourceParagraph"]:
        invalid_item = copy.deepcopy(VALID_UNRESOLVED_ITEM)
        del invalid_item[field]
        assert not validator.is_valid(invalid_item)
        with pytest.raises(ValidationError):
            validator.validate(invalid_item)


def test_unresolved_relation_missing_source_id_rejected():
    validator = get_item_validator()
    invalid_item = copy.deepcopy(VALID_UNRESOLVED_ITEM)
    del invalid_item["sourceEntityId"]
    assert not validator.is_valid(invalid_item)
    with pytest.raises(ValidationError):
        validator.validate(invalid_item)


def test_unresolved_relation_collection_valid():
    coll_validator = get_collection_validator()
    item2 = copy.deepcopy(VALID_UNRESOLVED_ITEM)
    item2["sourceEntityId"] = "kit:inquisidor"
    item2["candidateRelationType"] = "CAN_CHOOSE_POWER"
    item2["sourcePage"] = 16
    item2["sourceParagraph"] = 1
    item2["status"] = "UNRESOLVED_MISSING_TARGET"

    array_payload = [copy.deepcopy(VALID_UNRESOLVED_ITEM), item2]
    coll_validator.validate(array_payload)
    assert coll_validator.is_valid(array_payload)


def test_unresolved_relation_collection_rejects_invalid_item():
    coll_validator = get_collection_validator()
    invalid_item = copy.deepcopy(VALID_UNRESOLVED_ITEM)
    del invalid_item["reason"]

    array_payload = [invalid_item]
    assert not coll_validator.is_valid(array_payload)
    with pytest.raises(ValidationError):
        coll_validator.validate(array_payload)
