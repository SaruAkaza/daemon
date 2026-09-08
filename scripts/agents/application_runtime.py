from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ResourceBounds:
    """Configurable limits preventing unbounded file creation or resource exhaustion."""
    max_file_size_bytes: int = 50 * 1024 * 1024       # 50 MB
    max_changeset_size_bytes: int = 200 * 1024 * 1024  # 200 MB
    max_operations_per_changeset: int = 100
    max_total_staging_bytes: int = 500 * 1024 * 1024   # 500 MB


DEFAULT_AUTO_APPLY_ROOTS: tuple[str, ...] = (
    "data/text/",
    "data/structured/",
    "data/blocks/",
    "data/segments/",
    "data/entities/",
    "data/index/",
    "data/books/",
    "data/work/",
    "data/editorial/",
    "data/pilot/",
    "data/areas/",
    "docs/reports/",
)

DEFAULT_PROTECTED_ROOTS: tuple[str, ...] = (
    "scripts/",
    "schemas/",
    ".github/",
    "tests/",
    "Livros/",
    "coordination/",
    "docs/architecture/",
    "docs/reference/",
    "docs/superpowers/",
    "docs/agents/",
    "docs/missions/",
    "docs/obsidian/",
    "docs/index.html",
    "docs/assets/",
    "AGENTS.md",
    "PROJECT-BRAIN.md",
    "README.md",
    "CLAUDE.md",
    "OCR_CLEANUP_SUMMARY.md",
    "requirements.txt",
    "requirements-dev.txt",
    "ruff.toml",
    ".coveragerc",
    ".gitattributes",
    ".gitignore",
    ".nojekyll",
)

DEFAULT_HARD_BLOCKED_ROOTS: tuple[str, ...] = (
    ".git/",
    ".daemon_staging/",
    ".daemon_runtime/",
    ".venv/",
    "node_modules/",
)


@dataclass(frozen=True)
class ApplicationRuntimeConfig:
    """Trusted local configuration for the persistence and application layer."""
    repository_root: Path
    staging_root: Path
    audit_root: Path
    auto_apply_roots: tuple[str, ...] = DEFAULT_AUTO_APPLY_ROOTS
    protected_roots: tuple[str, ...] = DEFAULT_PROTECTED_ROOTS
    hard_blocked_roots: tuple[str, ...] = DEFAULT_HARD_BLOCKED_ROOTS
    resource_bounds: ResourceBounds = field(default_factory=ResourceBounds)

    def __post_init__(self) -> None:
        object.__setattr__(self, "repository_root", Path(self.repository_root).resolve())
        object.__setattr__(self, "staging_root", Path(self.staging_root).resolve())
        object.__setattr__(self, "audit_root", Path(self.audit_root).resolve())

    @classmethod
    def create(
        cls,
        repository_root: Path | str,
        staging_root: Path | str | None = None,
        audit_root: Path | str | None = None,
        auto_apply_roots: tuple[str, ...] = DEFAULT_AUTO_APPLY_ROOTS,
        protected_roots: tuple[str, ...] = DEFAULT_PROTECTED_ROOTS,
        hard_blocked_roots: tuple[str, ...] = DEFAULT_HARD_BLOCKED_ROOTS,
        resource_bounds: ResourceBounds | None = None,
    ) -> ApplicationRuntimeConfig:
        repo = Path(repository_root).resolve()
        staging = (
            Path(staging_root).resolve()
            if staging_root
            else (repo.parent / ".daemon_staging" / repo.name)
        )
        audit = (
            Path(audit_root).resolve()
            if audit_root
            else (repo / "docs" / "reports" / "audit")
        )
        return cls(
            repository_root=repo,
            staging_root=staging,
            audit_root=audit,
            auto_apply_roots=auto_apply_roots,
            protected_roots=protected_roots,
            hard_blocked_roots=hard_blocked_roots,
            resource_bounds=resource_bounds or ResourceBounds(),
        )

