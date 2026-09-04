import copy
import json
from pathlib import Path
import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

ROOT = Path(__file__).resolve().parents[2]

SCHEMAS = [
    "agent-job.schema.json",
    "agent-handoff.schema.json",
    "context-pack.schema.json",
    "review-request.schema.json",
    "source-manifest.schema.json",
    "relation.schema.json",
]


def load_schema(name: str) -> dict:
    path = ROOT / "schemas" / name
    return json.loads(path.read_text(encoding="utf-8"))


def load_fixture(name: str) -> dict:
    path = ROOT / "tests" / "agents" / "fixtures" / name
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Schema Self-Validation
# ---------------------------------------------------------------------------


def test_agent_schemas_are_valid_json_objects():
    for name in SCHEMAS:
        path = ROOT / "schemas" / name
        assert path.exists(), f"Schema file not found: {name}"
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["type"] == "object"
        assert "$schema" in payload
        assert "additionalProperties" in payload


def test_all_schemas_are_valid_draft202012():
    for name in SCHEMAS:
        schema = load_schema(name)
        Draft202012Validator.check_schema(schema)


# ---------------------------------------------------------------------------
# Positive Tests
# ---------------------------------------------------------------------------


def test_job_fixture_validates():
    schema = load_schema("agent-job.schema.json")
    fixture = load_fixture("job-book-trevas.json")
    validator = Draft202012Validator(schema)
    validator.validate(fixture)


def test_extraction_handoff_fixture_validates():
    schema = load_schema("agent-handoff.schema.json")
    fixture = load_fixture("handoff-extraction.json")
    validator = Draft202012Validator(schema)
    validator.validate(fixture)


def test_context_pack_fixture_validates():
    schema = load_schema("context-pack.schema.json")
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
    validator = Draft202012Validator(schema)
    validator.validate(payload)


def test_review_request_fixture_validates():
    schema = load_schema("review-request.schema.json")
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
    validator = Draft202012Validator(schema)
    validator.validate(payload)


def test_source_manifest_fixture_validates():
    schema = load_schema("source-manifest.schema.json")
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
    validator = Draft202012Validator(schema)
    validator.validate(payload)


def test_relation_fixture_validates():
    schema = load_schema("relation.schema.json")
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
    validator = Draft202012Validator(schema)
    validator.validate(payload)


# ---------------------------------------------------------------------------
# Negative Tests
# ---------------------------------------------------------------------------


def test_job_negative_invalid_status():
    schema = load_schema("agent-job.schema.json")
    payload = copy.deepcopy(load_fixture("job-book-trevas.json"))
    payload["status"] = "invented-status"
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(payload)


def test_job_negative_invalid_stage_status():
    schema = load_schema("agent-job.schema.json")
    payload = copy.deepcopy(load_fixture("job-book-trevas.json"))
    payload["stages"]["entities"] = "magically_done"
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(payload)


def test_job_negative_unknown_property():
    schema = load_schema("agent-job.schema.json")
    payload = copy.deepcopy(load_fixture("job-book-trevas.json"))
    payload["surprise"] = True
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(payload)


def test_handoff_negative_status_done():
    schema = load_schema("agent-handoff.schema.json")
    payload = copy.deepcopy(load_fixture("handoff-extraction.json"))
    payload["status"] = "done"  # 'done' belongs to Job, not Handoff
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(payload)


def test_handoff_negative_unknown_agent():
    schema = load_schema("agent-handoff.schema.json")
    payload = copy.deepcopy(load_fixture("handoff-extraction.json"))
    payload["agent"] = "random-rogue-agent"
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(payload)


def test_relation_negative_invalid_type():
    schema = load_schema("relation.schema.json")
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
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(payload)


def test_relation_negative_invalid_confidence():
    schema = load_schema("relation.schema.json")
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
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(payload)


def test_source_manifest_negative_invalid_sha256():
    schema = load_schema("source-manifest.schema.json")
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
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(payload)


def test_source_manifest_negative_invalid_rights_status():
    schema = load_schema("source-manifest.schema.json")
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
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(payload)


def test_review_request_negative_invalid_purpose():
    schema = load_schema("review-request.schema.json")
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
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(payload)
