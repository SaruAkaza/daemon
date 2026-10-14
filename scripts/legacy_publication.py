"""Rights preflight for legacy publishers that copy complete JSON payloads."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from scripts.agents.contracts import ContractValidationError, validate_payload
from scripts.agents.frontend_policy import public_combination_allowed


class PublicationBlocked(ValueError):
    """The complete legacy payload is not authorized for public distribution."""


def read_publication_input(path: Path) -> tuple[bytes, dict[str, Any]]:
    try:
        raw = path.read_bytes()
        payload = json.loads(raw)
    except (OSError, ValueError) as exc:
        raise PublicationBlocked(f"Cannot read publication input: {path.name}") from exc
    if not isinstance(payload, dict):
        raise PublicationBlocked(f"Publication input must be an object: {path.name}")
    return raw, payload


def _source_id(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PublicationBlocked("Missing or invalid source provenance in publication input.")
    return value


def referenced_sources(payload: dict[str, Any], kind: str) -> set[str]:
    """Inspect provenance in every payload, including secondary nested sources."""
    sources: set[str] = set()
    if kind == "area":
        for key in ("entities", "sourceParts"):
            items = payload.get(key)
            if not isinstance(items, list):
                raise PublicationBlocked(f"Area {key} must be a list.")
            for item in items:
                if not isinstance(item, dict):
                    raise PublicationBlocked(f"Area {key} must contain objects.")
                sources.add(_source_id(item.get("source")))
    elif kind == "area-summary":
        ready = payload.get("readySources")
        if not isinstance(ready, list):
            raise PublicationBlocked("Area summary readySources must be a list.")
        sources.update(_source_id(source) for source in ready)
    elif kind == "pilot":
        sources.add(_source_id(payload.get("source")))
    elif kind == "pilot-index":
        if not isinstance(payload.get("sources"), list):
            raise PublicationBlocked("Pilot index sources must be a list.")
    else:
        raise PublicationBlocked(f"Unknown legacy publication kind: {kind}")

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key in {"source", "sourceId"}:
                    sources.add(_source_id(child))
                elif key in {"sources", "readySources"}:
                    if isinstance(child, list):
                        for source in child:
                            if isinstance(source, str):
                                sources.add(_source_id(source))
                            elif isinstance(source, dict):
                                sources.add(_source_id(source.get("sourceId") or source.get("source") or source.get("id")))
                                visit(source)
                            else:
                                raise PublicationBlocked("Invalid nested sources list.")
                    elif isinstance(child, dict):
                        sources.update(_source_id(source) for source in child)
                        visit(child)
                    else:
                        raise PublicationBlocked("Invalid nested sources collection.")
                else:
                    visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(payload)
    return sources


def validate_publication(
    payloads: Iterable[tuple[dict[str, Any], str]],
    *,
    inventory_path: Path,
    manifests_dir: Path,
) -> set[str]:
    """Require explicit FULL_TEXT permission bound to the inventoried source bytes.

    No rights are inferred from editorial status, embedded payload fields, or
    technical approval. Narrower publication modes require the public projector.
    This function is read-only and must run before any destination is touched.
    """
    inputs = list(payloads)
    required: set[str] = set()
    for payload, kind in inputs:
        required.update(referenced_sources(payload, kind))

    _, inventory = read_publication_input(inventory_path)
    rows = inventory.get("sources")
    if not isinstance(rows, list):
        raise PublicationBlocked("Source inventory must contain a sources list.")
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise PublicationBlocked("Source inventory contains an invalid source.")
        source_id = _source_id(row.get("id"))
        if source_id in indexed:
            raise PublicationBlocked(f"Duplicate inventoried source: {source_id}")
        indexed[source_id] = row

    # Pilot DOCX/PDF claims must identify the same source as their permission.
    # A similarly named edition or a different file cannot borrow that grant.
    for payload, kind in inputs:
        if kind == "pilot" and ("sourcePath" in payload or "sourceFile" in payload):
            source = indexed.get(payload["source"])
            claimed_path = payload.get("sourcePath")
            claimed_file = payload.get("sourceFile")
            if (
                source is None
                or ("sourcePath" in payload and (
                    not isinstance(claimed_path, str)
                    or claimed_path.replace("\\", "/") != str(source.get("path", "")).replace("\\", "/")
                ))
                or ("sourceFile" in payload and (
                    not isinstance(claimed_file, str)
                    or claimed_file != str(source.get("path", "")).replace("\\", "/").rsplit("/", 1)[-1]
                ))
            ):
                raise PublicationBlocked(f"{payload['source']}: pilot sourcePath/sourceFile does not match inventory")

    manifests: dict[str, dict[str, Any]] = {}
    for path in sorted(manifests_dir.glob("*.json")):
        _, manifest = read_publication_input(path)
        try:
            validate_payload("source-manifest.schema.json", manifest)
        except ContractValidationError as exc:
            raise PublicationBlocked(f"Invalid source manifest: {path.name}") from exc
        source_id = manifest["sourceId"]
        if source_id in manifests:
            raise PublicationBlocked(f"Duplicate source manifest: {source_id}")
        manifests[source_id] = manifest

    errors: list[str] = []
    for source_id in sorted(required):
        source = indexed.get(source_id)
        manifest = manifests.get(source_id)
        if source is None:
            errors.append(f"{source_id}: absent from source inventory")
            continue
        if manifest is None:
            errors.append(f"{source_id}: source manifest required")
            continue
        if (
            manifest["sha256"].lower() != str(source.get("sha256", "")).lower()
            or manifest["path"].replace("\\", "/") != str(source.get("path", "")).replace("\\", "/")
            or manifest["extension"] != source.get("extension")
        ):
            errors.append(f"{source_id}: manifest does not match inventoried source")
        if (
            manifest["visibility"] != "public"
            or manifest["publicationMode"] != "FULL_TEXT"
            or not public_combination_allowed(manifest["rightsStatus"], manifest["publicationMode"])
        ):
            errors.append(f"{source_id}: public FULL_TEXT permission required")
    if errors:
        raise PublicationBlocked("Legacy publication blocked:\n" + "\n".join(errors))
    return required


def validate_public_write(path: Path, payload: Any, *, repo_root: Path) -> None:
    """Guard shared legacy JSON writes, including individual book generators."""
    public = repo_root / "docs" / "assets" / "data"
    relative = None
    for candidate, base in ((path.absolute(), public.absolute()), (path.resolve(), public.resolve())):
        try:
            relative = candidate.relative_to(base)
            break
        except ValueError:
            continue
    if relative is None:
        return
    if not isinstance(payload, dict):
        raise PublicationBlocked("Public legacy JSON must be an object.")
    if relative == Path("area-summary.json"):
        kind = "area-summary"
    elif relative.parent == Path("areas"):
        kind = "area"
    elif relative.parent == Path("pilot"):
        kind = "pilot-index" if relative.name == "index.json" else "pilot"
    else:
        raise PublicationBlocked(f"Unsupported public legacy destination: {relative}")
    validate_publication(
        [(payload, kind)],
        inventory_path=repo_root / "data" / "index" / "sources.json",
        manifests_dir=repo_root / "data" / "source-manifests",
    )
