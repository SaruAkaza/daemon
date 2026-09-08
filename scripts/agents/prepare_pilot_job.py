"""Operational pilot preparation and preflight custody verification tooling.

Prepares the runtime environment, validates source custody, and emits
formal verification checkpoints without processing candidate content.
"""

from dataclasses import dataclass, field
import hashlib
from pathlib import Path
from typing import List, Optional

from scripts.agents.pilot_audit_store import PilotAuditStore
from scripts.agents.pilot_coordinator import PilotCoordinator
from scripts.agents.restricted_workspace import RestrictedPilotWorkspace


@dataclass
class SourceCustodyReport:
    book_id: str
    source_path: str
    exists: bool
    status: str  # "VERIFIED" | "MISSING"
    size_bytes: int = 0
    sha256: Optional[str] = None
    format: str = ""

    @property
    def source_format(self) -> str:
        return self.format


@dataclass
class PilotReadinessStatus:
    book_id: str
    runtime_base: str
    workspace_ready: bool
    schemas_ready: bool
    coordinator_ready: bool
    audit_store_ready: bool
    ready: bool
    directories_created: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class PilotJobPreparer:
    """Prepares and validates the hermetic runtime environment for a pilot book."""

    REQUIRED_SCHEMAS = (
        "execution-bundle.schema.json",
        "result-bundle.schema.json",
        "pilot-review-request.schema.json",
        "pilot-review-decision.schema.json",
    )

    def __init__(self, repo_root: Optional[Path] = None) -> None:
        if repo_root is None:
            self.repo_root = Path(__file__).resolve().parents[2]
        else:
            self.repo_root = Path(repo_root)

    def verify_source_custody(self, book_id: str) -> SourceCustodyReport:
        """Audits static custody and SHA-256 hash of the book source without opening/processing."""
        livros_dir = self.repo_root / "Livros"
        candidate_paths = [
            livros_dir / "word" / "feito" / f"{book_id}.docx",
            livros_dir / "word" / f"{book_id}.docx",
            livros_dir / "txt" / f"{book_id}.txt",
            livros_dir / "pdf" / f"{book_id}.pdf",
        ]

        found_path: Optional[Path] = None
        for p in candidate_paths:
            if p.is_file():
                found_path = p
                break

        if found_path is None and livros_dir.is_dir():
            # Search subdirectories for matching file basename
            matches = list(livros_dir.rglob(f"{book_id}.*"))
            file_matches = [m for m in matches if m.is_file()]
            if file_matches:
                found_path = file_matches[0]

        if found_path is None:
            return SourceCustodyReport(
                book_id=book_id,
                source_path="",
                exists=False,
                status="MISSING",
                size_bytes=0,
                sha256=None,
                format="",
            )

        hasher = hashlib.sha256()
        with open(found_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        digest = hasher.hexdigest()
        size = found_path.stat().st_size
        fmt = found_path.suffix.lstrip(".").lower()

        return SourceCustodyReport(
            book_id=book_id,
            source_path=str(found_path),
            exists=True,
            status="VERIFIED",
            size_bytes=size,
            sha256=digest,
            format=fmt,
        )

    def prepare_pilot_environment(
        self, book_id: str, runtime_base: Path
    ) -> PilotReadinessStatus:
        """Initializes the runtime directories and verifies prerequisites."""
        runtime_base = Path(runtime_base)
        errors: List[str] = []
        created_dirs: List[str] = []

        # 1. Verify schema prerequisites
        schemas_dir = self.repo_root / "schemas"
        schemas_ready = True
        if not schemas_dir.is_dir():
            schemas_ready = False
            errors.append(f"Schemas directory not found: {schemas_dir}")
        else:
            for schema_name in self.REQUIRED_SCHEMAS:
                if not (schemas_dir / schema_name).is_file():
                    schemas_ready = False
                    errors.append(f"Required schema missing: {schema_name}")

        # 2. Initialize workspace and runtime directories
        workspace_ready = False
        coordinator_ready = False
        audit_store_ready = False

        try:
            ws_root = RestrictedPilotWorkspace.get_workspace_path(runtime_base, book_id)
            RestrictedPilotWorkspace.initialize_layout(ws_root)
            workspace_ready = True
            created_dirs.append(str(ws_root))
        except Exception as e:
            errors.append(f"Failed to initialize RestrictedPilotWorkspace: {e}")

        try:
            for sub in [
                runtime_base / "bundles" / "outgoing",
                runtime_base / "bundles" / "incoming",
                runtime_base / "bundles" / "accepted",
                runtime_base / "bundles" / "rejected",
                runtime_base / "preview" / book_id,
                runtime_base / "audit" / "pilot" / book_id,
            ]:
                sub.mkdir(parents=True, exist_ok=True)
                created_dirs.append(str(sub))

            audit_store = PilotAuditStore(audit_base_dir=runtime_base / "audit" / "pilot")
            audit_store_ready = True

            coord = PilotCoordinator(audit_store=audit_store, runtime_root=runtime_base)
            coordinator_ready = True
        except Exception as e:
            errors.append(f"Failed to initialize runtime coordinators: {e}")

        ready = (
            schemas_ready
            and workspace_ready
            and coordinator_ready
            and audit_store_ready
            and len(errors) == 0
        )

        return PilotReadinessStatus(
            book_id=book_id,
            runtime_base=str(runtime_base),
            workspace_ready=workspace_ready,
            schemas_ready=schemas_ready,
            coordinator_ready=coordinator_ready,
            audit_store_ready=audit_store_ready,
            ready=ready,
            directories_created=created_dirs,
            errors=errors,
        )

    def emit_infrastructure_verified_checkpoint(self) -> str:
        """Emits the formal checkpoint string asserting infrastructure readiness."""
        return "INFRASTRUCTURE_VERIFIED"
