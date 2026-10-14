"""Prepare private provenance candidates without promoting historical pilots."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path, PurePosixPath
import shutil
import sys
import tempfile
from typing import Any

from common import ROOT

sys.path.insert(0, str(ROOT))
from scripts.agents.application_runtime import ApplicationRuntimeConfig, ResourceBounds  # noqa: E402
from scripts.agents.canonical_json import sha256_bytes  # noqa: E402
from scripts.agents.contracts import write_atomic  # noqa: E402
from scripts.agents.patch_applier import CandidateArtifact  # noqa: E402
from scripts.agents.staging_manager import StagingManager  # noqa: E402
from scripts.reconcile_sources import ReconciliationError, encoded, read_object, reconcile, saved_outputs  # noqa: E402

PAGE_KEYS = {"page", "pages", "sourcePage", "sourcePages"}
CONTENT_KEYS = {"paragraphs", "entries", "text", "content"}
PLAN_PATH = Path("data/index/source-migration-plan.json")


class MigrationPreparationError(ValueError):
    """A review candidate or its private staging package cannot be verified."""


def page_audit(payload: dict[str, Any]) -> dict[str, Any]:
    page_count = 0
    content_count = 0
    invalid = []

    def positive(value: Any) -> bool:
        return type(value) is int and value > 0

    def visit(value: Any, pointer: str = "") -> None:
        nonlocal page_count, content_count
        if isinstance(value, dict):
            if any(key in value and value[key] for key in CONTENT_KEYS):
                content_count += 1
            for key, child in value.items():
                location = pointer + "/" + key.replace("~", "~0").replace("/", "~1")
                if key in PAGE_KEYS:
                    page_count += 1
                    valid = (
                        isinstance(child, list) and bool(child) and all(positive(page) for page in child)
                    ) if key in {"pages", "sourcePages"} else positive(child)
                    if not valid:
                        invalid.append(location)
                visit(child, location)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, pointer + "/" + str(index))

    visit(payload)
    return {
        "contentBlockCount": content_count,
        "pageFieldCount": page_count,
        "invalidPageFieldPaths": invalid,
        "status": "INVALID_PAGE_CLAIMS" if invalid else ("MISSING_PAGE_CLAIMS" if not page_count else "UNVERIFIED_PAGE_CLAIMS"),
    }


def prepare(repo_root: Path) -> tuple[dict[str, Any], tuple[CandidateArtifact, ...]]:
    repo_root = repo_root.resolve()
    fresh, manifests = reconcile(repo_root)
    reconciliation_path = repo_root / "data/index/source-reconciliation.json"
    reconciliation_raw, _ = read_object(reconciliation_path)
    if reconciliation_raw != encoded(fresh):
        raise MigrationPreparationError("Source reconciliation is stale; regenerate its review artifacts first.")
    outputs = saved_outputs(repo_root, fresh, manifests)
    for path, raw in outputs.items():
        if not path.is_file() or path.read_bytes() != raw:
            raise MigrationPreparationError("Missing or stale source manifest: " + path.name)
    manifest_inputs = sorted([{
        "path": path.relative_to(repo_root).as_posix(), "sha256": sha256_bytes(raw)
    } for path, raw in outputs.items() if path.parent == repo_root / "data/source-manifests"], key=lambda row: row["path"])
    variants = {variant["sourceId"]: variant for variant in fresh["sourceVariants"]}
    items = []
    candidates = []
    operations: set[str] = set()
    for row in fresh["pilotReview"]:
        pilot_file = row["pilotFile"]
        relative = PurePosixPath(pilot_file)
        if relative.parent != PurePosixPath("data/pilot") or relative.suffix != ".json" or ".." in relative.parts:
            raise MigrationPreparationError("Invalid pilot target path.")
        pilot_raw, original = read_object(repo_root / pilot_file)
        if sha256_bytes(pilot_raw) != row["pilotSha256"]:
            raise MigrationPreparationError("Pilot changed after source verification: " + relative.name)
        audit = page_audit(original)
        item: dict[str, Any] = {
            "pilotFile": pilot_file,
            "legacySourceId": row["legacySourceId"],
            "inputSha256": row["pilotSha256"],
            "candidateSourceId": row["candidateSourceId"],
            "matchMethod": row["matchMethod"],
            "pageAudit": audit,
            "reviewStatus": "NEEDS_HUMAN_REVIEW",
            "promotionAllowed": False,
            "blockingReasons": ["SOURCE_VERSION_REVIEW_REQUIRED", audit["status"]],
            "proposedRootChanges": [],
            "operationId": None,
            "candidateSha256": None,
        }
        items.append(item)
        if row["status"] != "FILE_IDENTIFIED":
            item["blockingReasons"].append(row["status"])
            continue
        if "sourceVariantId" in original or "sourceMigration" in original:
            raise MigrationPreparationError("Existing migration metadata requires review: " + relative.name)
        variant = variants[row["candidateSourceId"]]
        candidate = deepcopy(original)
        candidate["sourcePath"] = variant["path"]
        candidate["sourceFile"] = PurePosixPath(variant["path"]).name
        candidate["sourceVariantId"] = variant["sourceId"]
        candidate["sourceMigration"] = {
            "status": "NEEDS_HUMAN_REVIEW",
            "inputPilotSha256": row["pilotSha256"],
            "sourceSha256": variant["sha256"],
            "sourceVersionStatus": "UNVERIFIED",
            "pageMappingStatus": audit["status"],
            "publicReleaseAllowed": False,
        }
        for key in ("sourcePath", "sourceFile", "sourceVariantId", "sourceMigration"):
            if original.get(key) != candidate[key] or key not in original:
                item["proposedRootChanges"].append({
                    "field": key, "existed": key in original, "before": original.get(key), "after": candidate[key],
                })
        # The complete original source IDs, content, rules and page claims stay
        # unchanged. The proposal changes only the explicit root metadata above.
        raw = encoded(candidate)
        operation_id = "pilot-" + sha256_bytes(pilot_file.encode("utf-8"))[:16]
        if operation_id in operations:
            raise MigrationPreparationError("Pilot operation ID collision; no package can be staged.")
        operations.add(operation_id)
        digest = sha256_bytes(raw)
        candidates.append(CandidateArtifact(operation_id, pilot_file, raw, digest, format="json"))
        item.update(operationId=operation_id, candidateSha256=digest)
    plan = {
        "version": 1,
        "mode": "PRIVATE_REVIEW_ONLY",
        "sourceTreeOid": fresh["sourceTreeOid"],
        "reconciliationSha256": sha256_bytes(reconciliation_raw),
        "sourceManifestInputs": manifest_inputs,
        "summary": {
            "pilotCount": len(items),
            "candidateCount": len(candidates),
            "pilotsMissingPages": sum(item["pageAudit"]["status"] == "MISSING_PAGE_CLAIMS" for item in items),
            "pilotsWithInvalidPages": sum(item["pageAudit"]["status"] == "INVALID_PAGE_CLAIMS" for item in items),
            "contentBlockCount": sum(item["pageAudit"]["contentBlockCount"] for item in items),
            "canonicalPromotionCount": 0,
        },
        "items": items,
    }
    return plan, tuple(candidates)


def verify_package(root: Path, expected: dict[str, bytes]) -> None:
    if root.is_symlink():
        raise MigrationPreparationError("Staging package cannot be a symlink.")
    for relative, raw in expected.items():
        path = root / relative
        if path.is_symlink() or path.parent.is_symlink() or not path.is_file() or path.read_bytes() != raw:
            raise MigrationPreparationError("Existing staging package differs: " + relative)
    actual = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file() or path.is_symlink()}
    if actual != set(expected):
        raise MigrationPreparationError("Existing staging package contains unexpected files.")


def stage(repo_root: Path, staging_root: Path, bounds: ResourceBounds | None = None) -> Path:
    repo_root = repo_root.resolve()
    staging_root = staging_root.resolve()
    if staging_root == repo_root or repo_root in staging_root.parents:
        raise MigrationPreparationError("Private staging must be outside the repository.")
    plan, candidates = prepare(repo_root)
    plan_raw = encoded(plan)
    saved = repo_root / PLAN_PATH
    if not saved.is_file() or saved.read_bytes() != plan_raw:
        raise MigrationPreparationError("Saved migration plan is missing or stale; use --write-plan first.")
    limits = bounds or ResourceBounds()
    total = sum(len(candidate.content_bytes) for candidate in candidates)
    if (
        len(candidates) > limits.max_operations_per_changeset
        or any(len(candidate.content_bytes) > limits.max_file_size_bytes for candidate in candidates)
        or total > min(limits.max_changeset_size_bytes, limits.max_total_staging_bytes)
    ):
        raise MigrationPreparationError("Private staging exceeds configured resource bounds.")
    config = ApplicationRuntimeConfig.create(repo_root, staging_root=staging_root, resource_bounds=limits)
    if not StagingManager(config).verify_same_filesystem():
        raise MigrationPreparationError("Private staging must share the repository filesystem.")
    key = sha256_bytes(plan_raw)
    destination = staging_root / key
    expected = {"plan.json": plan_raw, **{f"candidates/{c.operation_id}.bin": c.content_bytes for c in candidates}}
    staging_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = staging_root / f".{key}.lock"
    try:
        with lock.open("xb"):
            pass
    except FileExistsError as exc:
        raise MigrationPreparationError("Another process owns this staging plan.") from exc
    temporary = None
    try:
        if destination.exists() or destination.is_symlink():
            verify_package(destination, expected)
            return destination
        temporary = Path(tempfile.mkdtemp(prefix=f".{key[:12]}-", dir=staging_root))
        config = ApplicationRuntimeConfig.create(repo_root, staging_root=temporary, resource_bounds=limits)
        manager = StagingManager(config)
        package = manager.prepare_staging(key)
        package.chmod(0o700)
        manager.stage_candidates(package, candidates)
        write_atomic(package / "plan.json", plan_raw)
        verify_package(package, expected)
        package.rename(destination)
        return destination
    finally:
        if temporary is not None:
            shutil.rmtree(temporary)
        lock.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare source migration plans and private review copies; never apply to canonical data.")
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write-plan", action="store_true")
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--stage", action="store_true")
    args = parser.parse_args()
    repo = args.repo_root.resolve()
    try:
        plan, _ = prepare(repo)
        raw = encoded(plan)
        path = repo / PLAN_PATH
        if args.write_plan:
            if not path.exists() or path.read_bytes() != raw:
                write_atomic(path, raw)
        elif args.check:
            if not path.is_file() or path.read_bytes() != raw:
                raise MigrationPreparationError("Saved migration plan is missing or stale.")
        elif args.stage:
            target = stage(repo, repo.parent / ".daemon_runtime" / "source-migrations" / repo.name)
            print(f"Private review package: {target}")
        print(json.dumps(plan["summary"], sort_keys=True))
    except (MigrationPreparationError, ReconciliationError, ValueError, OSError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
