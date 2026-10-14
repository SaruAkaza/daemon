import copy
from pathlib import Path
import pytest

from scripts.agents.context_loader import (
    ContextEncodingError,
    ContextLoader,
    ContextLoaderError,
    ContextNotFoundError,
    ContextPathError,
)
from scripts.agents.context_pack_builder import (
    CANONICAL_LAYERS,
    ContextPackBuilder,
    ContextPackBuilderError,
)
from scripts.agents.contracts import (
    ContractValidationError,
    validate_payload,
)

ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Test Helpers & Fixtures
# ---------------------------------------------------------------------------


def _create_sample_repo(tmp_path: Path) -> dict[str, Path]:
    """Create a minimal mock repository structure with valid UTF-8 documents."""
    docs = {
        "constitution.md": tmp_path / "docs" / "architecture" / "constitution.md",
        "project.md": tmp_path / "docs" / "architecture" / "project-context.md",
        "taxonomy.md": tmp_path / "docs" / "context" / "domain" / "taxonomy.md",
        "book_trevas.md": tmp_path / "coordination" / "books" / "trevas.md",
        "job_queue.json": tmp_path / "coordination" / "queue" / "job-001.json",
        "handoff.json": tmp_path / "coordination" / "handoff" / "handoff-001.json",
        "output_schema.json": tmp_path / "schemas" / "agent-handoff.schema.json",
    }
    for rel_path, full_path in docs.items():
        full_path.parent.mkdir(parents=True, exist_ok=True)
        if full_path.suffix == ".json":
            full_path.write_text('{"type": "mock_data"}', encoding="utf-8")
        else:
            full_path.write_text(f"# Content of {rel_path}\n\nTexto de teste com acentuação: ação, bênção, demônio.\n", encoding="utf-8")
    return docs


def _valid_metadata() -> dict:
    return {
        "schemaVersion": "1.0",
        "contextPackId": "CTX-TEST-EDITORIAL-001",
        "jobId": "JOB-TREVAS-001",
        "agent": "editorial-agent",
        "stage": "editorial",
        "task": {
            "type": "classify_editorial_segments",
            "scope": {
                "bookId": "trevas",
                "pages": [1, 2, 3]
            },
            "parameters": {
                "strictCoverage": True
            }
        },
        "outputContract": "schemas/agent-handoff.schema.json"
    }


def _valid_layers() -> dict[str, list[str]]:
    return {
        "mandatory": [
            "docs/architecture/constitution.md",
            "docs/architecture/project-context.md"
        ],
        "domain": [
            "docs/context/domain/taxonomy.md"
        ],
        "bookContext": [
            "coordination/books/trevas.md"
        ],
        "jobContext": [
            "coordination/queue/job-001.json"
        ],
        "handoffContext": [
            "coordination/handoff/handoff-001.json"
        ]
    }


# ---------------------------------------------------------------------------
# Hierarchy & Initialization Tests
# ---------------------------------------------------------------------------


def test_context_pack_builder_error_hierarchy():
    assert issubclass(ContextPackBuilderError, RuntimeError)


def test_context_pack_builder_default_init():
    builder = ContextPackBuilder()
    assert isinstance(builder.loader, ContextLoader)
    assert builder.loader.root.resolve() == ROOT.resolve()


def test_context_pack_builder_custom_loader(tmp_path):
    loader = ContextLoader(root=tmp_path)
    builder = ContextPackBuilder(loader=loader)
    assert builder.loader is loader
    assert builder.loader.root.resolve() == tmp_path.resolve()


# ---------------------------------------------------------------------------
# Positive Build Tests
# ---------------------------------------------------------------------------


def test_context_pack_builder_build_minimal_valid(tmp_path):
    _create_sample_repo(tmp_path)
    loader = ContextLoader(root=tmp_path)
    builder = ContextPackBuilder(loader=loader)

    metadata = _valid_metadata()
    layers = _valid_layers()

    pack = builder.build(metadata=metadata, layers=layers)

    assert pack["schemaVersion"] == "1.0"
    assert pack["contextPackId"] == "CTX-TEST-EDITORIAL-001"
    assert pack["jobId"] == "JOB-TREVAS-001"
    assert pack["agent"] == "editorial-agent"
    assert pack["stage"] == "editorial"
    assert pack["mandatory"] == [
        "docs/architecture/constitution.md",
        "docs/architecture/project-context.md"
    ]
    assert pack["domain"] == ["docs/context/domain/taxonomy.md"]
    assert pack["bookContext"] == ["coordination/books/trevas.md"]
    assert pack["jobContext"] == ["coordination/queue/job-001.json"]
    assert pack["handoffContext"] == ["coordination/handoff/handoff-001.json"]
    assert pack["task"]["type"] == "classify_editorial_segments"
    assert pack["outputContract"] == "schemas/agent-handoff.schema.json"

    # Must validate directly against canonical schema
    validate_payload("context-pack.schema.json", pack)


def test_context_pack_builder_canonical_layers_order(tmp_path):
    _create_sample_repo(tmp_path)
    loader = ContextLoader(root=tmp_path)
    builder = ContextPackBuilder(loader=loader)

    # Pass layers intentionally inverted
    unordered_layers = {
        "handoffContext": ["coordination/handoff/handoff-001.json"],
        "bookContext": ["coordination/books/trevas.md"],
        "mandatory": ["docs/architecture/constitution.md"],
        "jobContext": ["coordination/queue/job-001.json"],
        "domain": ["docs/context/domain/taxonomy.md"],
    }

    pack = builder.build(metadata=_valid_metadata(), layers=unordered_layers)

    # Check key ordering in output pack
    pack_keys = list(pack.keys())
    for layer in CANONICAL_LAYERS:
        assert layer in pack_keys

    idx_mandatory = pack_keys.index("mandatory")
    idx_domain = pack_keys.index("domain")
    idx_book = pack_keys.index("bookContext")
    idx_job = pack_keys.index("jobContext")
    idx_handoff = pack_keys.index("handoffContext")

    assert idx_mandatory < idx_domain < idx_book < idx_job < idx_handoff


def test_context_pack_builder_empty_layers_default_to_empty_lists(tmp_path):
    _create_sample_repo(tmp_path)
    loader = ContextLoader(root=tmp_path)
    builder = ContextPackBuilder(loader=loader)

    # Provide only mandatory layer, others omitted
    minimal_layers = {
        "mandatory": ["docs/architecture/constitution.md"]
    }

    pack = builder.build(metadata=_valid_metadata(), layers=minimal_layers)

    assert pack["mandatory"] == ["docs/architecture/constitution.md"]
    assert pack["domain"] == []
    assert pack["bookContext"] == []
    assert pack["jobContext"] == []
    assert pack["handoffContext"] == []

    validate_payload("context-pack.schema.json", pack)


def test_context_pack_builder_same_layer_deduplication(tmp_path):
    _create_sample_repo(tmp_path)
    loader = ContextLoader(root=tmp_path)
    builder = ContextPackBuilder(loader=loader)

    layers = {
        "mandatory": [
            "docs/architecture/constitution.md",
            "docs/architecture/project-context.md",
            "docs/architecture/constitution.md"  # duplicate
        ]
    }

    pack = builder.build(metadata=_valid_metadata(), layers=layers)
    assert pack["mandatory"] == [
        "docs/architecture/constitution.md",
        "docs/architecture/project-context.md"
    ]


def test_context_pack_builder_input_immutability(tmp_path):
    _create_sample_repo(tmp_path)
    loader = ContextLoader(root=tmp_path)
    builder = ContextPackBuilder(loader=loader)

    metadata = _valid_metadata()
    layers = _valid_layers()

    metadata_clone = copy.deepcopy(metadata)
    layers_clone = copy.deepcopy(layers)

    builder.build(metadata=metadata, layers=layers)

    assert metadata == metadata_clone
    assert layers == layers_clone


def test_context_pack_builder_determinism(tmp_path):
    _create_sample_repo(tmp_path)
    loader = ContextLoader(root=tmp_path)
    builder = ContextPackBuilder(loader=loader)

    metadata = _valid_metadata()
    layers = _valid_layers()

    pack1 = builder.build(metadata=metadata, layers=layers)
    pack2 = builder.build(metadata=metadata, layers=layers)

    assert pack1 == pack2


def test_context_pack_builder_no_cache_rereads_disk(tmp_path):
    docs = _create_sample_repo(tmp_path)
    loader = ContextLoader(root=tmp_path)
    builder = ContextPackBuilder(loader=loader)

    metadata = _valid_metadata()
    layers = {"mandatory": ["docs/architecture/constitution.md"]}

    pack1 = builder.build(metadata=metadata, layers=layers)
    assert pack1["mandatory"] == ["docs/architecture/constitution.md"]

    # If file is deleted, next build must fail immediately (no caching)
    docs["constitution.md"].unlink()
    with pytest.raises(ContextNotFoundError):
        builder.build(metadata=metadata, layers=layers)


def test_context_pack_builder_minimum_sufficient_context(tmp_path):
    _create_sample_repo(tmp_path)
    # Create an unreferenced file
    unreferenced = tmp_path / "docs" / "unreferenced.md"
    unreferenced.write_text("Unreferenced file content", encoding="utf-8")

    loader = ContextLoader(root=tmp_path)
    builder = ContextPackBuilder(loader=loader)

    pack = builder.build(metadata=_valid_metadata(), layers=_valid_layers())

    all_included_paths = []
    for layer_name in CANONICAL_LAYERS:
        all_included_paths.extend(pack[layer_name])

    assert "docs/unreferenced.md" not in all_included_paths


def test_context_pack_builder_real_repo_documents():
    builder = ContextPackBuilder()
    metadata = {
        "schemaVersion": "1.0",
        "contextPackId": "CTX-REAL-REPO-001",
        "jobId": "JOB-REAL-001",
        "agent": "qa-release-agent",
        "stage": "qa",
        "task": {
            "type": "verify_release_integrity"
        },
        "outputContract": "schemas/agent-handoff.schema.json"
    }
    layers = {
        "mandatory": [
            "AGENTS.md",
            "docs/architecture/constitution.md"
        ],
        "domain": [
            "docs/context/domain/taxonomy.md"
        ]
    }

    pack = builder.build(metadata=metadata, layers=layers)
    assert pack["contextPackId"] == "CTX-REAL-REPO-001"
    assert "AGENTS.md" in pack["mandatory"]
    validate_payload("context-pack.schema.json", pack)


# ---------------------------------------------------------------------------
# Negative Tests
# ---------------------------------------------------------------------------


def test_context_pack_builder_unknown_layer_fails(tmp_path):
    _create_sample_repo(tmp_path)
    loader = ContextLoader(root=tmp_path)
    builder = ContextPackBuilder(loader=loader)

    layers = {
        "mandatory": ["docs/architecture/constitution.md"],
        "unexpected_layer": ["docs/architecture/project-context.md"]
    }

    with pytest.raises(ContextPackBuilderError) as exc_info:
        builder.build(metadata=_valid_metadata(), layers=layers)
    assert "unexpected_layer" in str(exc_info.value)


def test_context_pack_builder_cross_layer_duplicate_fails(tmp_path):
    _create_sample_repo(tmp_path)
    loader = ContextLoader(root=tmp_path)
    builder = ContextPackBuilder(loader=loader)

    layers = {
        "mandatory": ["docs/architecture/constitution.md"],
        "domain": ["docs/architecture/constitution.md"]  # Same path in different layer
    }

    with pytest.raises(ContextPackBuilderError) as exc_info:
        builder.build(metadata=_valid_metadata(), layers=layers)
    assert "constitution.md" in str(exc_info.value)
    assert "duplicate" in str(exc_info.value).lower() or "multiple layers" in str(exc_info.value).lower()


def test_context_pack_builder_missing_context_file_raises_not_found(tmp_path):
    _create_sample_repo(tmp_path)
    loader = ContextLoader(root=tmp_path)
    builder = ContextPackBuilder(loader=loader)

    layers = {
        "mandatory": ["docs/architecture/non_existent.md"]
    }

    with pytest.raises(ContextNotFoundError):
        builder.build(metadata=_valid_metadata(), layers=layers)


def test_context_pack_builder_traversal_path_raises_path_error(tmp_path):
    _create_sample_repo(tmp_path)
    loader = ContextLoader(root=tmp_path)
    builder = ContextPackBuilder(loader=loader)

    layers = {
        "mandatory": ["../outside.md"]
    }

    with pytest.raises(ContextPathError):
        builder.build(metadata=_valid_metadata(), layers=layers)


def test_context_pack_builder_invalid_utf8_raises_encoding_error(tmp_path):
    _create_sample_repo(tmp_path)
    bad_file = tmp_path / "docs" / "bad_utf8.md"
    bad_file.write_bytes(b"\xff\xfe\xfa")

    loader = ContextLoader(root=tmp_path)
    builder = ContextPackBuilder(loader=loader)

    layers = {
        "mandatory": ["docs/bad_utf8.md"]
    }

    with pytest.raises(ContextEncodingError):
        builder.build(metadata=_valid_metadata(), layers=layers)


def test_context_pack_builder_missing_output_contract_file(tmp_path):
    _create_sample_repo(tmp_path)
    loader = ContextLoader(root=tmp_path)
    builder = ContextPackBuilder(loader=loader)

    metadata = _valid_metadata()
    metadata["outputContract"] = "schemas/missing-schema.json"

    with pytest.raises(ContextNotFoundError):
        builder.build(metadata=metadata, layers=_valid_layers())


def test_context_pack_builder_non_dict_metadata_raises(tmp_path):
    loader = ContextLoader(root=tmp_path)
    builder = ContextPackBuilder(loader=loader)

    for invalid_metadata in [None, "string", [1, 2, 3], 123]:
        with pytest.raises(ContextPackBuilderError):
            builder.build(metadata=invalid_metadata, layers=_valid_layers())


def test_context_pack_builder_non_dict_layers_raises(tmp_path):
    loader = ContextLoader(root=tmp_path)
    builder = ContextPackBuilder(loader=loader)

    for invalid_layers in [None, "string", [1, 2, 3], 123]:
        with pytest.raises(ContextPackBuilderError):
            builder.build(metadata=_valid_metadata(), layers=invalid_layers)


def test_context_pack_builder_non_iterable_layer_value_raises(tmp_path):
    loader = ContextLoader(root=tmp_path)
    builder = ContextPackBuilder(loader=loader)

    layers = {
        "mandatory": 123  # Not a sequence of paths
    }

    with pytest.raises(ContextPackBuilderError):
        builder.build(metadata=_valid_metadata(), layers=layers)


def test_context_pack_builder_schema_violation_raises_contract_validation_error(tmp_path):
    _create_sample_repo(tmp_path)
    loader = ContextLoader(root=tmp_path)
    builder = ContextPackBuilder(loader=loader)

    metadata = _valid_metadata()
    metadata["agent"] = "unknown-rogue-agent"  # Invalid agent enum

    with pytest.raises(ContractValidationError):
        builder.build(metadata=metadata, layers=_valid_layers())


def test_context_pack_builder_unknown_metadata_property_raises_contract_validation_error(tmp_path):
    _create_sample_repo(tmp_path)
    loader = ContextLoader(root=tmp_path)
    builder = ContextPackBuilder(loader=loader)

    metadata = _valid_metadata()
    metadata["rogueProperty"] = "disallowed"

    with pytest.raises(ContractValidationError):
        builder.build(metadata=metadata, layers=_valid_layers())
