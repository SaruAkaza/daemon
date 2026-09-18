from __future__ import annotations

from pathlib import Path

from scripts.agents.archive_inventory_loader import resolve_canonical_runtime_dir


def get_ops_runtime_dir(runtime_dir: Path | str | None = None) -> Path:
    """Resolves the canonical ops directory within the canonical .daemon_runtime."""
    canonical_rt = resolve_canonical_runtime_dir(runtime_dir)
    return (canonical_rt / "ops").resolve()


def get_ops_stores_dir(runtime_dir: Path | str | None = None) -> Path:
    """Resolves the canonical stores directory within the canonical ops directory."""
    ops_dir = get_ops_runtime_dir(runtime_dir)
    return (ops_dir / "stores").resolve()
