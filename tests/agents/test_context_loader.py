import json
from pathlib import Path

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
