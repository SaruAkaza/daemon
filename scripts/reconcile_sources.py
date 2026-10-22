"""Identify legacy source candidates without migrating data or granting rights."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any

from common import ROOT, slugify

sys.path.insert(0, str(ROOT))
from scripts.agents.contracts import ContractValidationError, validate_payload, write_atomic  # noqa: E402


class ReconciliationError(ValueError):
    """Source identity or a saved review artifact cannot be verified."""


def encoded(payload: Any) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def read_object(path: Path) -> tuple[bytes, dict[str, Any]]:
    try:
        raw = path.read_bytes()
        payload = json.loads(raw)
    except (OSError, ValueError) as exc:
        raise ReconciliationError(f"Cannot read JSON input: {path.name}") from exc
    if not isinstance(payload, dict):
        raise ReconciliationError(f"Expected JSON object: {path.name}")
    return raw, payload


def source_path(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise ReconciliationError("Missing source path.")
    normalized = value.replace("\\", "/")
    parts = normalized.split("/")
    if parts[0] != "Livros" or any(part in {"", ".", ".."} for part in parts):
        raise ReconciliationError("Source path must stay within Livros/.")
    return normalized


def tracked_sources(repo_root: Path) -> tuple[str, dict[str, str]]:
    """Read only Git tree metadata; no blob sizes, checkout, or source changes."""
    try:
        tree = subprocess.check_output(["git", "rev-parse", "HEAD:Livros"], cwd=repo_root, text=True).strip()
        raw = subprocess.check_output(["git", "ls-tree", "-rz", "HEAD", "Livros"], cwd=repo_root)
    except subprocess.CalledProcessError as exc:
        raise ReconciliationError("Cannot inspect the committed Livros/ tree.") from exc
    paths: dict[str, str] = {}
    for entry in raw.split(b"\0"):
        if not entry:
            continue
        metadata, raw_path = entry.split(b"\t", 1)
        mode, kind, oid = metadata.decode("ascii").split()
        path = raw_path.decode("utf-8")
        if kind == "blob" and mode in {"100644", "100755"} and PurePosixPath(path).suffix.lower() in {".pdf", ".docx"}:
            paths[source_path(path)] = oid
    return tree, paths


def filename_key(path: str) -> str:
    # This key generates review candidates only, never an identity/rights alias.
    stem = PurePosixPath(path).stem
    stem = re.sub(r"(?i)[ _-]+OCR(?:[ _-].*)?$", "", stem)
    return slugify(stem)


def verify_file(repo_root: Path, path: str, oid: str) -> bytes:
    repo_root = repo_root.resolve()
    local = repo_root / path
    parents = [repo_root.joinpath(*PurePosixPath(path).parts[:index]) for index in range(1, len(PurePosixPath(path).parts))]
    if local.is_symlink() or any(parent.is_symlink() for parent in parents):
        raise ReconciliationError(f"Symlink cannot certify source custody: {path}")
    try:
        local.resolve().relative_to(repo_root.resolve())
        raw = local.read_bytes()
    except (OSError, ValueError) as exc:
        raise ReconciliationError(f"Source is not materialized in this checkout: {path}") from exc
    hasher = hashlib.sha1() if len(oid) == 40 else hashlib.sha256()
    hasher.update(f"blob {len(raw)}\0".encode("ascii"))
    hasher.update(raw)
    if hasher.hexdigest() != oid:
        raise ReconciliationError(f"Source differs from committed bytes: {path}")
    return raw


def reconcile(repo_root: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    repo_root = repo_root.resolve()
    tree, tracked = tracked_sources(repo_root)
    inventory_raw, inventory = read_object(repo_root / "data" / "index" / "sources.json")
    rows = inventory.get("sources")
    if not isinstance(rows, list):
        raise ReconciliationError("Inventory sources must be a list.")
    indexed: dict[str, dict[str, Any]] = {}
    inventory_review = []
    for source in rows:
        if not isinstance(source, dict) or not isinstance(source.get("id"), str) or not source["id"]:
            raise ReconciliationError("Invalid inventoried source ID.")
        if source["id"] in indexed:
            raise ReconciliationError(f"Duplicate inventory ID: {source['id']}")
        indexed[source["id"]] = source
        path = source_path(source.get("path"))
        candidates = sorted(p for p in tracked if filename_key(p) == filename_key(path))
        inventory_review.append({
            "sourceId": source["id"],
            "inventoriedPath": path,
            "pathState": "TRACKED" if path in tracked else "ABSENT_FROM_CURRENT_TREE",
            "candidatePaths": candidates,
            "reviewStatus": "NEEDS_HUMAN_REVIEW",
        })

    pilots = []
    variants: dict[str, dict[str, Any]] = {}
    manifests: dict[str, dict[str, Any]] = {}
    for file in sorted((repo_root / "data" / "pilot").glob("*.json")):
        if file.name == "index.json":
            continue
        pilot_raw, payload = read_object(file)
        legacy_id = payload.get("source")
        if not isinstance(legacy_id, str) or not legacy_id:
            raise ReconciliationError(f"Pilot source ID required: {file.name}")
        row: dict[str, Any] = {
            "pilotFile": file.relative_to(repo_root).as_posix(),
            "pilotSha256": hashlib.sha256(pilot_raw).hexdigest(),
            "legacySourceId": legacy_id,
            "inventoriedPath": indexed.get(legacy_id, {}).get("path"),
            "claimedSourcePath": payload.get("sourcePath"),
            "claimedSourceFile": payload.get("sourceFile"),
            "candidatePaths": [],
            "matchMethod": None,
            "candidateSourceId": None,
            "reviewStatus": "NEEDS_HUMAN_REVIEW",
            "status": "UNRESOLVED",
        }
        pilots.append(row)
        claimed = source_path(payload["sourcePath"]) if "sourcePath" in payload else None
        basename = payload.get("sourceFile")
        if basename is not None and (not isinstance(basename, str) or not basename or "/" in basename or "\\" in basename):
            raise ReconciliationError(f"Pilot sourceFile must be a filename: {file.name}")
        if claimed and basename and PurePosixPath(claimed).name != basename:
            row["status"] = "CONFLICTING_PROVENANCE"
            continue
        if claimed in tracked:
            candidates = [claimed]
            method = "EXACT_PATH"
        else:
            name = basename or (PurePosixPath(claimed).name if claimed else None)
            candidates = sorted(p for p in tracked if PurePosixPath(p).name == name) if name else []
            method = "UNIQUE_FILENAME"
        row["candidatePaths"] = candidates
        if len(candidates) != 1:
            row["status"] = "AMBIGUOUS_FILENAME" if candidates else "SOURCE_NOT_FOUND"
            continue
        path = candidates[0]
        row["matchMethod"] = method
        local = repo_root / path
        if not local.exists() and not local.is_symlink():
            row["status"] = "SOURCE_NOT_MATERIALIZED"
            continue
        raw = verify_file(repo_root, path, tracked[path])
        digest = hashlib.sha256(raw).hexdigest()
        variant_id = f"file-{digest}"
        variant = {
            "sourceId": variant_id,
            "title": PurePosixPath(path).stem,
            "path": path,
            "extension": PurePosixPath(path).suffix.lower(),
            "sha256": digest,
            "gitBlobOid": tracked[path],
            "sizeBytes": len(raw),
        }
        if variant_id in variants and variants[variant_id]["path"] != path:
            raise ReconciliationError("Identical source bytes at different paths need an explicit custody decision.")
        variants[variant_id] = variant
        manifest = {
            "schemaVersion": "1.0",
            **{key: variant[key] for key in ("sourceId", "title", "path", "extension", "sha256")},
            "rightsStatus": "UNKNOWN",
            "visibility": "private",
            "publicationMode": "NOT_PUBLIC",
        }
        validate_payload("source-manifest.schema.json", manifest)
        manifests[variant_id] = manifest
        row.update(status="FILE_IDENTIFIED", candidateSourceId=variant_id)

    counts = Counter(row["status"] for row in pilots)
    report = {
        "version": 1,
        "sourceTreeOid": tree,
        "inventorySha256": hashlib.sha256(inventory_raw).hexdigest(),
        "summary": {
            "trackedSourceCount": len(tracked),
            "inventorySourceCount": len(rows),
            "inventoryPathsAbsent": sum(row["pathState"] != "TRACKED" for row in inventory_review),
            "pilotCount": len(pilots),
            "identifiedPilotCount": counts["FILE_IDENTIFIED"],
            "sourceVariantCount": len(variants),
            "unresolvedPilotCount": len(pilots) - counts["FILE_IDENTIFIED"],
        },
        "inventoryReview": sorted(inventory_review, key=lambda row: row["sourceId"]),
        "sourceVariants": sorted(variants.values(), key=lambda row: row["path"]),
        "pilotReview": pilots,
    }
    return report, manifests


def saved_outputs(repo_root: Path, report: dict[str, Any], manifests: dict[str, dict[str, Any]]) -> dict[Path, bytes]:
    """Preserve explicit decisions, reject conflicts, and plan all writes first."""
    repo_root = repo_root.resolve()
    outputs = {repo_root / "data" / "index" / "source-reconciliation.json": encoded(report)}
    manifest_dir = repo_root / "data" / "source-manifests"
    existing_by_id: dict[str, Path] = {}
    for path in sorted(manifest_dir.glob("*.json")):
        _, existing = read_object(path)
        validate_payload("source-manifest.schema.json", existing)
        source_id = existing["sourceId"]
        if source_id in existing_by_id:
            raise ReconciliationError(f"Duplicate source manifest: {source_id}")
        existing_by_id[source_id] = path
    for source_id, manifest in sorted(manifests.items()):
        path = existing_by_id.get(source_id, manifest_dir / f"{source_id}.json")
        if path.exists():
            raw, existing = read_object(path)
            validate_payload("source-manifest.schema.json", existing)
            if (
                existing["sourceId"] != source_id
                or source_path(existing["path"]) != manifest["path"]
                or existing["extension"] != manifest["extension"]
                or existing["sha256"].lower() != manifest["sha256"]
            ):
                raise ReconciliationError(f"Existing manifest identity conflicts: {path.name}")
            outputs[path] = raw
        else:
            outputs[path] = encoded(manifest)
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconcile source candidates without migrating the canonical inventory.")
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="Save the review report and missing UNKNOWN/NOT_PUBLIC manifests.")
    mode.add_argument("--check", action="store_true", help="Verify saved artifacts are current without writing.")
    args = parser.parse_args()
    args.repo_root = args.repo_root.resolve()
    try:
        report, manifests = reconcile(args.repo_root)
        outputs = saved_outputs(args.repo_root, report, manifests)
        if args.check:
            stale = [str(path.relative_to(args.repo_root)) for path, raw in outputs.items() if not path.is_file() or path.read_bytes() != raw]
            if stale:
                raise ReconciliationError("Missing or stale reconciliation artifacts:\n" + "\n".join(stale))
        elif args.write:
            for path, raw in outputs.items():
                if not path.exists() or path.read_bytes() != raw:
                    write_atomic(path, raw)
        print(json.dumps(report["summary"], ensure_ascii=False, sort_keys=True))
        if report["summary"]["unresolvedPilotCount"]:
            parser.exit(1, "Unresolved source candidates require review; no rights were granted.\n")
    except (ReconciliationError, ContractValidationError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
