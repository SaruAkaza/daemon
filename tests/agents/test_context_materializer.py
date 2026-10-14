from __future__ import annotations

import copy
import pytest
from pathlib import Path
from dataclasses import FrozenInstanceError

from scripts.agents.context_loader import ContextLoader
from scripts.agents.context_materializer import (
    ContextMaterializer,
    ContextMaterializationError,
    MaterializedContext,
)


@pytest.fixture
def sample_repo(tmp_path):
    # Setup dummy directory and files
    docs_arch = tmp_path / "docs" / "architecture"
    docs_arch.mkdir(parents=True)
    constitution = docs_arch / "constitution.md"
    constitution.write_text("# Constitution\nDeterministic rules.", encoding="utf-8")

    docs_domain = tmp_path / "docs" / "context" / "domain"
    docs_domain.mkdir(parents=True)
    taxonomy = docs_domain / "taxonomy.md"
    taxonomy.write_text("# Taxonomy\nCanonical types.", encoding="utf-8")

    books = tmp_path / "coordination" / "books"
    books.mkdir(parents=True)
    trevas_book = books / "trevas.md"
    trevas_book.write_text("# Trevas Book Context\nMetadata here.", encoding="utf-8")

    queue = tmp_path / "coordination" / "queue"
    queue.mkdir(parents=True)
    job_queue = queue / "codex.json"
    job_queue.write_text('{"job": "active"}', encoding="utf-8")

    schemas = tmp_path / "schemas"
    schemas.mkdir(parents=True)
    contract = schemas / "agent-handoff.schema.json"
    contract.write_text('{"title": "Handoff Contract"}', encoding="utf-8")

    return tmp_path


@pytest.fixture
def valid_context_pack():
    return {
        "schemaVersion": "1.0",
        "contextPackId": "CTX-TREVAS-EXTRACTION-001",
        "jobId": "JOB-TREVAS-001",
        "agent": "extraction-agent",
        "stage": "extraction",
        "mandatory": [
            "docs/architecture/constitution.md",
        ],
        "domain": [
            "docs/context/domain/taxonomy.md",
        ],
        "bookContext": [
            "coordination/books/trevas.md",
        ],
        "jobContext": [
            "coordination/queue/codex.json",
        ],
        "handoffContext": [],
        "task": {
            "type": "extract_raw_text",
            "scope": {
                "bookId": "trevas-3-0",
                "pages": [1, 2, 3],
            },
            "parameters": {
                "strictCoverage": True,
            },
        },
        "outputContract": "schemas/agent-handoff.schema.json",
    }


def test_materialize_valid_context_pack(sample_repo, valid_context_pack):
    loader = ContextLoader(root=sample_repo)
    materializer = ContextMaterializer(loader=loader)

    result = materializer.materialize(valid_context_pack)

    assert isinstance(result, MaterializedContext)
    assert result.metadata["contextPackId"] == "CTX-TREVAS-EXTRACTION-001"
    assert result.metadata["jobId"] == "JOB-TREVAS-001"
    assert result.metadata["agent"] == "extraction-agent"
    assert result.metadata["stage"] == "extraction"
    assert result.metadata["task"]["type"] == "extract_raw_text"

    # Mandatory layer
    assert len(result.layers["mandatory"]) == 1
    assert result.layers["mandatory"][0]["path"] == "docs/architecture/constitution.md"
    assert "Deterministic rules." in result.layers["mandatory"][0]["content"]

    # Domain layer
    assert len(result.layers["domain"]) == 1
    assert result.layers["domain"][0]["path"] == "docs/context/domain/taxonomy.md"
    assert "Canonical types." in result.layers["domain"][0]["content"]

    # Book context layer
    assert len(result.layers["bookContext"]) == 1
    assert result.layers["bookContext"][0]["path"] == "coordination/books/trevas.md"
    assert "Trevas Book Context" in result.layers["bookContext"][0]["content"]

    # Job context layer
    assert len(result.layers["jobContext"]) == 1
    assert result.layers["jobContext"][0]["path"] == "coordination/queue/codex.json"
    assert '{"job": "active"}' in result.layers["jobContext"][0]["content"]

    # Handoff context (empty)
    assert len(result.layers["handoffContext"]) == 0

    # Output contract layer
    assert len(result.layers["outputContract"]) == 1
    assert result.layers["outputContract"][0]["path"] == "schemas/agent-handoff.schema.json"
    assert "Handoff Contract" in result.layers["outputContract"][0]["content"]


def test_materialize_immutability(sample_repo, valid_context_pack):
    loader = ContextLoader(root=sample_repo)
    materializer = ContextMaterializer(loader=loader)
    result = materializer.materialize(valid_context_pack)

    with pytest.raises(FrozenInstanceError):
        result.metadata = {}

    with pytest.raises(FrozenInstanceError):
        result.layers = {}


def test_materialize_schema_invalid_pack(sample_repo):
    loader = ContextLoader(root=sample_repo)
    materializer = ContextMaterializer(loader=loader)

    with pytest.raises(ContextMaterializationError) as exc_info:
        materializer.materialize({"invalid": "pack"})
    assert "schema" in str(exc_info.value).lower() or "validation" in str(exc_info.value).lower()


def test_materialize_missing_file_raises(sample_repo, valid_context_pack):
    loader = ContextLoader(root=sample_repo)
    materializer = ContextMaterializer(loader=loader)

    pack = copy.deepcopy(valid_context_pack)
    pack["mandatory"].append("docs/non_existent_file.md")

    with pytest.raises(ContextMaterializationError) as exc_info:
        materializer.materialize(pack)
    assert "not found" in str(exc_info.value).lower() or "non_existent" in str(exc_info.value)


def test_materialize_path_traversal_raises(sample_repo, valid_context_pack):
    loader = ContextLoader(root=sample_repo)
    materializer = ContextMaterializer(loader=loader)

    pack = copy.deepcopy(valid_context_pack)
    pack["mandatory"].append("../secret.md")

    with pytest.raises(ContextMaterializationError) as exc_info:
        materializer.materialize(pack)
    assert "traversal" in str(exc_info.value).lower() or "escape" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()


def test_materialize_preserves_multiple_files_order(sample_repo, valid_context_pack):
    f1 = sample_repo / "docs" / "doc1.md"
    f2 = sample_repo / "docs" / "doc2.md"
    f1.write_text("content 1", encoding="utf-8")
    f2.write_text("content 2", encoding="utf-8")

    pack = copy.deepcopy(valid_context_pack)
    pack["mandatory"] = ["docs/doc1.md", "docs/doc2.md"]

    loader = ContextLoader(root=sample_repo)
    materializer = ContextMaterializer(loader=loader)
    result = materializer.materialize(pack)

    assert len(result.layers["mandatory"]) == 2
    assert result.layers["mandatory"][0]["path"] == "docs/doc1.md"
    assert result.layers["mandatory"][0]["content"] == "content 1"
    assert result.layers["mandatory"][1]["path"] == "docs/doc2.md"
    assert result.layers["mandatory"][1]["content"] == "content 2"


def test_materialize_does_not_mutate_input(sample_repo, valid_context_pack):
    pack_copy = copy.deepcopy(valid_context_pack)
    loader = ContextLoader(root=sample_repo)
    materializer = ContextMaterializer(loader=loader)

    materializer.materialize(valid_context_pack)
    assert valid_context_pack == pack_copy
