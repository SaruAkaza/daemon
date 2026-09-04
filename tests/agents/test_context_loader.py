from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

REQUIRED_CORE_CONTEXT = [
    "AGENTS.md",
    "docs/architecture/constitution.md",
    "docs/architecture/project-context.md",
    "docs/architecture/pipeline.md",
    "docs/architecture/context-system.md",
    "docs/architecture/decision-policy.md",
]


def test_required_core_context_files_exist():
    missing = [
        path
        for path in REQUIRED_CORE_CONTEXT
        if not (ROOT / path).exists()
    ]
    assert missing == []
