import copy
import json
import os
from pathlib import Path
import pytest

from scripts.agents.context_loader import (
    ContextEncodingError,
    ContextLoader,
    ContextLoaderError,
    ContextNotFoundError,
    ContextPathError,
)

ROOT = Path(__file__).resolve().parents[2]

REQUIRED_CORE_CONTEXT = [
    "AGENTS.md",
    "PROJECT-BRAIN.md",
    "docs/architecture/constitution.md",
    "docs/architecture/project-context.md",
    "docs/architecture/pipeline.md",
    "docs/architecture/context-system.md",
    "docs/architecture/decision-policy.md",
]

REQUIRED_ROLE_CONTRACTS = [
    "docs/agents/orchestrator.md",
    "docs/agents/source-agent.md",
    "docs/agents/extraction-agent.md",
    "docs/agents/editorial-agent.md",
    "docs/agents/entity-agent.md",
    "docs/agents/relations-agent.md",
    "docs/agents/frontend-agent.md",
    "docs/agents/qa-release-agent.md",
]

REQUIRED_DOMAIN_CONTEXT_FILES = [
    "docs/agents/README.md",
    "docs/context/README.md",
    "docs/context/domain/taxonomy.md",
    "docs/context/domain/entity-patterns.md",
    "docs/context/domain/relation-types.md",
    "docs/context/decisions/ADR-0001-repository-context-is-agent-memory.md",
    "docs/context/decisions/ADR-0002-human-validation-required-for-done.md",
    "docs/context/decisions/ADR-0003-development-fork-and-upstream-release-model.md",
]

REQUIRED_PROJECT_BRAIN_FILES = [
    "PROJECT-BRAIN.md",
    "docs/obsidian/README.md",
    "docs/obsidian/manifest.json",
    "docs/obsidian/mocs/Agents.md",
    "docs/obsidian/mocs/Architecture.md",
    "docs/obsidian/mocs/Books.md",
    "docs/obsidian/mocs/Decisions.md",
    "docs/obsidian/mocs/Development.md",
    "docs/obsidian/mocs/Domain.md",
    "docs/obsidian/mocs/Missions.md",
    "docs/obsidian/templates/adr-template.md",
    "docs/obsidian/templates/book-template.md",
    "docs/obsidian/templates/human-review-template.md",
    "docs/obsidian/templates/mission-template.md",
    "docs/obsidian/templates/precedent-template.md",
]

MANDATORY_CONTRACT_SECTIONS = [
    "## Identity",
    "## Mission",
    "## Question This Role Answers",
    "## Mandatory Context",
    "## Optional Context",
    "## Input Contract",
    "## Output Contract",
    "## Primary Write Scope",
    "## Read-Only Scope",
    "## Forbidden Actions",
    "## Entry Gate",
    "## Exit Gate",
    "## Human Escalation",
    "## Failure Routing",
    "## Examples",
    "## Base Prompt",
]


# ---------------------------------------------------------------------------
# Structural Integrity Tests (Existing)
# ---------------------------------------------------------------------------


def test_required_core_context_files_exist():
    missing = [
        path
        for path in REQUIRED_CORE_CONTEXT
        if not (ROOT / path).exists()
    ]
    assert missing == []


def test_all_role_contracts_exist():
    missing = [
        path
        for path in REQUIRED_ROLE_CONTRACTS
        if not (ROOT / path).exists()
    ]
    assert missing == []


def test_required_domain_context_files_exist():
    missing = [
        path
        for path in REQUIRED_DOMAIN_CONTEXT_FILES
        if not (ROOT / path).exists()
    ]
    assert missing == []


def test_role_contracts_have_mandatory_sections():
    for contract_path in REQUIRED_ROLE_CONTRACTS:
        file_path = ROOT / contract_path
        if not file_path.exists():
            continue
        content = file_path.read_text(encoding="utf-8")
        for section in MANDATORY_CONTRACT_SECTIONS:
            assert section in content, f"Missing section '{section}' in {contract_path}"


def test_project_brain_manifest_and_files_exist():
    manifest_path = ROOT / "docs" / "obsidian" / "manifest.json"
    assert manifest_path.exists(), "docs/obsidian/manifest.json not found"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["entry"] == "PROJECT-BRAIN.md"
    assert (ROOT / manifest["entry"]).exists()

    for declared_file in manifest.get("files", []):
        assert (ROOT / declared_file).exists(), f"File declared in manifest.json missing: {declared_file}"

    for required_file in REQUIRED_PROJECT_BRAIN_FILES:
        assert (ROOT / required_file).exists(), f"Project brain file missing: {required_file}"


# ---------------------------------------------------------------------------
# Hierarchy & API Contract Tests
# ---------------------------------------------------------------------------


def test_context_loader_error_hierarchy():
    assert issubclass(ContextLoaderError, RuntimeError)
    assert issubclass(ContextNotFoundError, ContextLoaderError)
    assert issubclass(ContextPathError, ContextLoaderError)
    assert issubclass(ContextEncodingError, ContextLoaderError)


def test_context_loader_is_strictly_read_only():
    loader = ContextLoader()
    for forbidden_method in ["write", "save", "update", "create", "delete", "upsert", "rename", "move"]:
        assert not hasattr(loader, forbidden_method), f"Forbidden method '{forbidden_method}' found on ContextLoader"


def test_context_loader_has_no_premature_methods():
    loader = ContextLoader()
    for attr in ["load_json", "load_raw", "exists", "root_dir", "resolve_path"]:
        assert not hasattr(loader, attr), f"Premature attribute '{attr}' found on ContextLoader"


# ---------------------------------------------------------------------------
# Root & CWD Independence Tests
# ---------------------------------------------------------------------------


def test_context_loader_default_root():
    loader = ContextLoader()
    assert loader.root.resolve() == ROOT.resolve()
    assert loader.root.is_dir()


def test_context_loader_custom_root(tmp_path):
    custom_root = tmp_path / "custom_root"
    custom_root.mkdir()
    loader = ContextLoader(root=custom_root)
    assert loader.root.resolve() == custom_root.resolve()


def test_context_loader_cwd_independence(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    loader = ContextLoader()
    assert loader.root.resolve() == ROOT.resolve()


# ---------------------------------------------------------------------------
# Resolve Method & Path Security Tests
# ---------------------------------------------------------------------------


def test_context_loader_resolve_nested_file(tmp_path):
    loader = ContextLoader(root=tmp_path)
    nested_dir = tmp_path / "docs" / "architecture"
    nested_dir.mkdir(parents=True)
    target_file = nested_dir / "doc.md"
    target_file.write_text("content", encoding="utf-8")

    resolved = loader.resolve("docs/architecture/doc.md")
    assert resolved == target_file.resolve()


def test_context_loader_resolve_accepts_path_object(tmp_path):
    loader = ContextLoader(root=tmp_path)
    (tmp_path / "file.txt").write_text("content", encoding="utf-8")

    resolved = loader.resolve(Path("file.txt"))
    assert resolved == (tmp_path / "file.txt").resolve()


def test_context_loader_resolve_parent_traversal(tmp_path):
    loader = ContextLoader(root=tmp_path)
    with pytest.raises(ContextPathError):
        loader.resolve("../outside.md")


def test_context_loader_resolve_nested_traversal(tmp_path):
    loader = ContextLoader(root=tmp_path)
    with pytest.raises(ContextPathError):
        loader.resolve("docs/../../outside.md")


def test_context_loader_resolve_absolute_windows_path(tmp_path):
    loader = ContextLoader(root=tmp_path)
    with pytest.raises(ContextPathError):
        loader.resolve("C:\\Windows\\System32\\file.txt")


def test_context_loader_resolve_absolute_posix_path(tmp_path):
    loader = ContextLoader(root=tmp_path)
    with pytest.raises(ContextPathError):
        loader.resolve("/tmp/file.txt")


def test_context_loader_resolve_invalid_empty_or_whitespace(tmp_path):
    loader = ContextLoader(root=tmp_path)
    with pytest.raises(ContextPathError):
        loader.resolve("")
    with pytest.raises(ContextPathError):
        loader.resolve("   ")


def test_context_loader_resolve_invalid_types(tmp_path):
    loader = ContextLoader(root=tmp_path)
    for invalid_input in [None, 123, [], {}, 3.14]:
        with pytest.raises(ContextPathError):
            loader.resolve(invalid_input)


def test_context_loader_resolve_nonexistent_returns_path_without_error(tmp_path):
    loader = ContextLoader(root=tmp_path)
    resolved = loader.resolve("docs/missing.md")
    assert resolved == (tmp_path / "docs" / "missing.md").resolve()
    assert not resolved.exists()


# ---------------------------------------------------------------------------
# Load Text Tests
# ---------------------------------------------------------------------------


def test_context_loader_load_text_success(tmp_path):
    loader = ContextLoader(root=tmp_path)
    sample_file = tmp_path / "sample.md"
    sample_file.write_text("# Title\n\nContent here.\n", encoding="utf-8")

    text = loader.load_text("sample.md")
    assert text == "# Title\n\nContent here.\n"


def test_context_loader_load_text_preserves_utf8(tmp_path):
    loader = ContextLoader(root=tmp_path)
    sample = "Daemon\nextração\nbênção\ndemônio\nrelação\nação\n"
    sample_file = tmp_path / "utf8_sample.txt"
    sample_file.write_text(sample, encoding="utf-8")

    loaded = loader.load_text("utf8_sample.txt")
    assert loaded == sample


def test_context_loader_load_text_preserves_whitespace_and_newlines(tmp_path):
    loader = ContextLoader(root=tmp_path)
    sample = "Linha 1\n\n  Linha indentada\nLinha final\n"
    sample_file = tmp_path / "whitespace.txt"
    sample_file.write_text(sample, encoding="utf-8")

    loaded = loader.load_text("whitespace.txt")
    assert loaded == sample
    assert loaded.endswith("\n")
    assert "  Linha indentada" in loaded


def test_context_loader_load_text_no_cache_rereads_disk(tmp_path):
    loader = ContextLoader(root=tmp_path)
    dynamic_file = tmp_path / "dynamic.txt"
    dynamic_file.write_text("first version", encoding="utf-8")

    assert loader.load_text("dynamic.txt") == "first version"

    dynamic_file.write_text("second version", encoding="utf-8")
    assert loader.load_text("dynamic.txt") == "second version"


def test_context_loader_load_text_missing_file(tmp_path):
    loader = ContextLoader(root=tmp_path)
    with pytest.raises(ContextNotFoundError) as exc_info:
        loader.load_text("missing/file.md")
    assert "missing/file.md" in str(exc_info.value)
    assert isinstance(exc_info.value, ContextLoaderError)


def test_context_loader_load_text_directory_fails(tmp_path):
    loader = ContextLoader(root=tmp_path)
    target_dir = tmp_path / "docs" / "architecture"
    target_dir.mkdir(parents=True)

    with pytest.raises(ContextNotFoundError) as exc_info:
        loader.load_text("docs/architecture")
    assert "docs/architecture" in str(exc_info.value)
    assert isinstance(exc_info.value, ContextLoaderError)


def test_context_loader_load_text_non_utf8_fails(tmp_path):
    loader = ContextLoader(root=tmp_path)
    binary_file = tmp_path / "invalid_utf8.bin"
    binary_file.write_bytes(b"\xff\xfe\xfa")

    with pytest.raises(ContextEncodingError) as exc_info:
        loader.load_text("invalid_utf8.bin")
    assert "invalid_utf8.bin" in str(exc_info.value)
    assert isinstance(exc_info.value, ContextLoaderError)
    assert "\xff" not in str(exc_info.value)



def test_context_loader_symlink_escape_protection(tmp_path):
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    secret_file = outside_dir / "secret.md"
    secret_file.write_text("secret content", encoding="utf-8")

    inside_dir = tmp_path / "inside"
    inside_dir.mkdir()

    symlink_path = inside_dir / "link_outside"
    try:
        symlink_path.symlink_to(outside_dir, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation not permitted or supported in this Windows environment")

    loader = ContextLoader(root=inside_dir)
    with pytest.raises(ContextPathError):
        loader.load_text("link_outside/secret.md")


# ---------------------------------------------------------------------------
# Real Repository Document Tests (Read-Only)
# ---------------------------------------------------------------------------


def test_context_loader_reads_real_agents_md():
    loader = ContextLoader()
    text = loader.load_text("AGENTS.md")
    assert text
    assert "Daemon" in text
    assert "constitution.md" in text


def test_context_loader_reads_real_architecture_doc():
    loader = ContextLoader()
    text = loader.load_text("docs/architecture/constitution.md")
    assert text
    assert "Constituição" in text or "Constitution" in text or "Daemon" in text
