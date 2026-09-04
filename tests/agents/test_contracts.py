import copy
import json
from pathlib import Path
import pytest

from scripts.agents.contracts import (
    ContractValidationError,
    load_json,
    load_schema,
    validate_payload,
)

ROOT = Path(__file__).resolve().parents[2]

SCHEMAS = [
    "agent-job.schema.json",
    "agent-handoff.schema.json",
    "context-pack.schema.json",
    "review-request.schema.json",
    "source-manifest.schema.json",
    "relation.schema.json",
]


def load_fixture(name: str) -> dict:
    path = ROOT / "tests" / "agents" / "fixtures" / name
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Schema Self-Validation & Loading Tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("schema_name", SCHEMAS)
def test_load_schema_accepts_all_agent_schemas(schema_name: str):
    schema = load_schema(schema_name)
    assert isinstance(schema, dict)
    assert schema["type"] == "object"
    assert "$schema" in schema
    assert "additionalProperties" in schema


def test_load_schema_accepts_name_without_extension():
    schema = load_schema("agent-job")
    assert isinstance(schema, dict)
    assert schema["title"] == "Agent Job"


def test_load_schema_non_existent():
    with pytest.raises(ContractValidationError) as exc_info:
        load_schema("non-existent-schema")
    assert "not found" in str(exc_info.value).lower() or "schema" in str(exc_info.value).lower()


def test_load_schema_path_traversal():
    with pytest.raises(ContractValidationError):
        load_schema("../agent-job.schema.json")
    with pytest.raises(ContractValidationError):
        load_schema("subdir/../../agent-job.schema.json")


def test_load_schema_invalid_schema_structure(tmp_path, monkeypatch):
    invalid_schema_file = tmp_path / "bad.schema.json"
    invalid_schema_file.write_text(
        json.dumps({"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "invalid_type"}),
        encoding="utf-8"
    )
    import scripts.agents.contracts as contracts_mod
    monkeypatch.setattr(contracts_mod, "SCHEMAS_DIR", tmp_path)

    with pytest.raises(ContractValidationError) as exc_info:
        load_schema("bad.schema.json")
    # Must raise ContractValidationError, not jsonschema.exceptions.SchemaError
    assert isinstance(exc_info.value, ContractValidationError)


# ---------------------------------------------------------------------------
# load_json Tests
# ---------------------------------------------------------------------------


def test_load_json_valid(tmp_path):
    f = tmp_path / "valid.json"
    f.write_text('{"key": "value", "count": 1}', encoding="utf-8")
    data = load_json(f)
    assert data == {"key": "value", "count": 1}


def test_load_json_non_existent(tmp_path):
    f = tmp_path / "missing.json"
    with pytest.raises(ContractValidationError):
        load_json(f)


def test_load_json_invalid_syntax(tmp_path):
    f = tmp_path / "syntax_error.json"
    f.write_text('{"unclosed": "brace"', encoding="utf-8")
    with pytest.raises(ContractValidationError) as exc_info:
        load_json(f)
    assert "JSON" in str(exc_info.value) or "syntax" in str(exc_info.value).lower() or "decode" in str(exc_info.value).lower()


def test_load_json_top_level_non_object(tmp_path):
    array_file = tmp_path / "array.json"
    array_file.write_text('[1, 2, 3]', encoding="utf-8")
    with pytest.raises(ContractValidationError):
        load_json(array_file)

    string_file = tmp_path / "string.json"
    string_file.write_text('"just a string"', encoding="utf-8")
    with pytest.raises(ContractValidationError):
        load_json(string_file)


# ---------------------------------------------------------------------------
# Positive Validation Tests
# ---------------------------------------------------------------------------


def test_validate_payload_accepts_valid_job():
    fixture = load_fixture("job-book-trevas.json")
    validate_payload("agent-job.schema.json", fixture)
    # Also test with short name
    validate_payload("agent-job", fixture)


def test_extraction_handoff_fixture_validates():
    fixture = load_fixture("handoff-extraction.json")
    validate_payload("agent-handoff.schema.json", fixture)


def test_context_pack_fixture_validates():
    payload = {
        "schemaVersion": "1.0",
        "contextPackId": "CTX-TREVAS-EDITORIAL-001",
        "jobId": "BOOK-TREVAS-001",
        "agent": "editorial-agent",
        "stage": "editorial",
        "mandatory": [
            "docs/architecture/constitution.md",
            "docs/reference/cataloging-rules.md"
        ],
        "domain": [
            "docs/context/domain/taxonomy.md",
            "docs/context/domain/entity-patterns.md"
        ],
        "bookContext": [
            "coordination/books/trevas.md"
        ],
        "jobContext": [
            "coordination/queue/codex.json"
        ],
        "handoffContext": [
            "data/handoffs/handoff-extraction.json"
        ],
        "task": {
            "type": "classify_editorial_segments",
            "scope": {
                "bookId": "trevas",
                "pages": [1, 2, 3, 4, 5]
            },
            "parameters": {
                "strictCoverage": True
            }
        },
        "outputContract": "schemas/agent-handoff.schema.json"
    }
    validate_payload("context-pack.schema.json", payload)


def test_review_request_fixture_validates():
    payload = {
        "reviewId": "REV-TREVAS-FINAL-001",
        "jobId": "BOOK-TREVAS-001",
        "requestedBy": "qa-release-agent",
        "purpose": "final_validation",
        "question": "Aprovar conclusão do processamento de Trevas 3.0 para done?",
        "options": ["Aprovar", "Solicitar ajustes"],
        "decision": "Aprovar",
        "rationale": "Todas as 214 páginas certificadas e suíte de testes passando com 100% de cobertura.",
        "decidedBy": "Matheus",
        "status": "resolved",
        "createdAt": "2026-09-04T10:30:00-03:00",
        "resolvedAt": "2026-09-04T10:45:00-03:00"
    }
    validate_payload("review-request.schema.json", payload)


def test_source_manifest_fixture_validates():
    payload = {
        "schemaVersion": "1.0",
        "sourceId": "trevas-3-0",
        "title": "Trevas 3.0",
        "path": "Livros/Trevas 3.0.pdf",
        "extension": ".pdf",
        "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "rightsStatus": "PRIVATE",
        "visibility": "internal",
        "publicationMode": "SUMMARY_AND_METADATA",
        "edition": "3a Edição",
        "publicationYear": 2005,
        "publisher": "Daemon Editora",
        "system": "Daemon",
        "setting": "Trevas",
        "language": "pt-BR"
    }
    validate_payload("source-manifest.schema.json", payload)


def test_relation_fixture_validates():
    payload = {
        "schemaVersion": "1.0",
        "id": "rel-cacador-teologia-001",
        "type": "REQUIRES",
        "sourceEntityId": "kit:cacador-de-bruxas",
        "targetEntityId": "skill:teologia",
        "source": "inquisicao",
        "page": 14,
        "confidence": 1.0
    }
    validate_payload("relation.schema.json", payload)


# ---------------------------------------------------------------------------
# Negative & Mutation Validation Tests
# ---------------------------------------------------------------------------


def test_validate_payload_rejects_invalid_job_state():
    payload = copy.deepcopy(load_fixture("job-book-trevas.json"))
    payload["status"] = "invented-status"
    with pytest.raises(ContractValidationError):
        validate_payload("agent-job.schema.json", payload)


def test_validate_payload_error_path():
    payload = copy.deepcopy(load_fixture("job-book-trevas.json"))
    payload["stages"]["entities"] = "magically_done"
    with pytest.raises(ContractValidationError) as exc_info:
        validate_payload("agent-job.schema.json", payload)
    assert "stages.entities" in str(exc_info.value)


def test_validate_payload_unknown_property():
    payload = copy.deepcopy(load_fixture("job-book-trevas.json"))
    payload["surprise"] = True
    with pytest.raises(ContractValidationError):
        validate_payload("agent-job.schema.json", payload)


def test_validate_payload_does_not_mutate_input():
    original = load_fixture("job-book-trevas.json")
    payload = copy.deepcopy(original)
    validate_payload("agent-job.schema.json", payload)
    assert payload == original


def test_handoff_negative_status_done():
    payload = copy.deepcopy(load_fixture("handoff-extraction.json"))
    payload["status"] = "done"  # 'done' belongs to Job, not Handoff
    with pytest.raises(ContractValidationError):
        validate_payload("agent-handoff.schema.json", payload)


def test_handoff_negative_unknown_agent():
    payload = copy.deepcopy(load_fixture("handoff-extraction.json"))
    payload["agent"] = "random-rogue-agent"
    with pytest.raises(ContractValidationError):
        validate_payload("agent-handoff.schema.json", payload)


def test_relation_negative_invalid_type():
    payload = {
        "schemaVersion": "1.0",
        "id": "rel-001",
        "type": "KNOWS_ABOUT",  # Not in relation-types.md
        "sourceEntityId": "kit:cacador",
        "targetEntityId": "skill:teologia",
        "source": "inquisicao",
        "page": 14,
        "confidence": 1.0
    }
    with pytest.raises(ContractValidationError):
        validate_payload("relation.schema.json", payload)


def test_relation_negative_invalid_confidence():
    payload = {
        "schemaVersion": "1.0",
        "id": "rel-001",
        "type": "REQUIRES",
        "sourceEntityId": "kit:cacador",
        "targetEntityId": "skill:teologia",
        "source": "inquisicao",
        "page": 14,
        "confidence": 1.4  # Must be <= 1.0
    }
    with pytest.raises(ContractValidationError):
        validate_payload("relation.schema.json", payload)


def test_source_manifest_negative_invalid_sha256():
    payload = {
        "schemaVersion": "1.0",
        "sourceId": "trevas-3-0",
        "title": "Trevas 3.0",
        "path": "Livros/Trevas 3.0.pdf",
        "extension": ".pdf",
        "sha256": "not-a-valid-64-char-hex-hash",
        "rightsStatus": "PRIVATE",
        "visibility": "internal",
        "publicationMode": "SUMMARY_AND_METADATA"
    }
    with pytest.raises(ContractValidationError):
        validate_payload("source-manifest.schema.json", payload)


def test_source_manifest_negative_invalid_rights_status():
    payload = {
        "schemaVersion": "1.0",
        "sourceId": "trevas-3-0",
        "title": "Trevas 3.0",
        "path": "Livros/Trevas 3.0.pdf",
        "extension": ".pdf",
        "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "rightsStatus": "CREATIVE_COMMONS_CUSTOM",
        "visibility": "internal",
        "publicationMode": "SUMMARY_AND_METADATA"
    }
    with pytest.raises(ContractValidationError):
        validate_payload("source-manifest.schema.json", payload)


def test_review_request_negative_invalid_purpose():
    payload = {
        "reviewId": "REV-001",
        "jobId": "BOOK-001",
        "requestedBy": "source-agent",
        "purpose": "unsupported_purpose_value",
        "question": "Dúvida?",
        "options": [],
        "decision": None,
        "rationale": None,
        "decidedBy": None,
        "status": "open",
        "createdAt": "2026-09-04T10:30:00-03:00",
        "resolvedAt": None
    }
    with pytest.raises(ContractValidationError):
        validate_payload("review-request.schema.json", payload)

