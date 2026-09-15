from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
from typing import Any
import uuid

from scripts.agents.canonical_json import canonical_json_bytes
from scripts.agents.frontend_labels import relation_labels
from scripts.agents.frontend_policy import project_allowed_book
from scripts.agents.site_view_model import (
    EXPECTED_VERSION,
    ProjectionError,
    validate_projection,
)


class FrontendProjector:
    """Core projection engine for Site View Model transformation, filtering, and indexing."""

    def build(self, books: list[dict[str, Any]], mode: str) -> dict[str, dict[str, Any]]:
        """Transform canonical approved books into protected, deterministic Site View Model files.

        Returns a dictionary mapping relative logical paths ('catalog.json', 'search-index.json',
        'books/<bookId>.json') to their validated JSON object payloads.
        """
        if mode not in {"restricted_preview", "public"}:
            raise ProjectionError(f"Invalid projection mode: '{mode}'")

        # Immutability: deepcopy input books so caller's memory is never mutated
        input_books = deepcopy(books)

        # Step 1 & 2: Referential integrity check across all approved input entities
        all_ids: set[str] = set()
        for b in input_books:
            for ent in b.get("entities", []):
                eid = ent.get("id") or ent.get("entityId")
                if eid:
                    all_ids.add(str(eid))

        for b in input_books:
            for rel in b.get("relations", []):
                src = rel.get("sourceEntityId")
                tgt = rel.get("targetEntityId")
                if src not in all_ids or tgt not in all_ids:
                    raise ProjectionError(
                        f"Resolved relation target missing: source='{src}', target='{tgt}'"
                    )

        # Step 3: Apply rights and publication policy to each book
        allowed_books: list[dict[str, Any]] = []
        for b in input_books:
            allowed = project_allowed_book(b, mode)
            if allowed is not None:
                allowed_books.append(allowed)

        # Sort allowed books deterministically
        allowed_books.sort(key=lambda x: x["bookId"])

        # Step 4: Collect visible entity IDs across all allowed books
        visible_ids: set[str] = set()
        for b in allowed_books:
            for ent in b.get("entities", []):
                visible_ids.add(ent["entityId"])

        # Step 5: Filter and label relations; omit edges if either endpoint is not visible
        for b in allowed_books:
            projected_relations: list[dict[str, Any]] = []
            for rel in b.get("relations", []):
                src = rel["sourceEntityId"]
                tgt = rel["targetEntityId"]
                if src not in visible_ids or tgt not in visible_ids:
                    # Omit cross-book or filtered relation to prevent leaking restricted entity
                    continue
                out_lbl, in_lbl = relation_labels(rel["type"])
                projected_relations.append({
                    "relationId": rel["relationId"],
                    "type": rel["type"],
                    "sourceEntityId": src,
                    "targetEntityId": tgt,
                    "outgoingLabel": out_lbl,
                    "incomingLabel": in_lbl,
                })
            # Deterministic sorting of relations
            projected_relations.sort(key=lambda r: r["relationId"])
            b["relations"] = projected_relations

        # Step 5b: In restricted_preview, link matching unresolved references to entity technicalDetails
        if mode == "restricted_preview":
            for b in allowed_books:
                unres_list = b.get("unresolvedReferences", [])
                if unres_list:
                    for ent in b.get("entities", []):
                        eid = ent["entityId"]
                        matching = [
                            u for u in unres_list
                            if isinstance(u, dict) and u.get("sourceEntityId") == eid
                        ]
                        if matching:
                            if "technicalDetails" not in ent:
                                ent["technicalDetails"] = {}
                            ent["technicalDetails"]["unresolvedReferences"] = [
                                {"name": u["name"], **({"status": u["status"]} if "status" in u else {})}
                                for u in matching
                            ]

        # Step 6: Build search index entries
        search_entries: list[dict[str, Any]] = []
        for b in allowed_books:
            for ent in b.get("entities", []):
                eid = ent["entityId"]
                name = ent["name"]
                aliases = list(ent.get("aliases", []))
                tags = list(ent.get("tags", []))
                text_parts = [name] + aliases + tags
                for blk in ent.get("content", []):
                    text_parts.extend(blk.get("paragraphs", []))
                search_text = " ".join(text_parts).lower().strip()

                search_entries.append({
                    "entityId": eid,
                    "route": f"#/entity/{eid}",
                    "name": name,
                    "aliases": aliases,
                    "type": ent["type"],
                    "displayType": ent["displayType"],
                    "bookId": b["bookId"],
                    "bookTitle": b["title"],
                    "tags": tags,
                    "searchText": search_text,
                })

        # Deterministic search index ordering: displayType, then name, then entityId
        search_entries.sort(key=lambda e: (e["displayType"], e["name"], e["entityId"]))

        # Step 7: Build catalog books metadata
        catalog_books: list[dict[str, Any]] = []
        for b in allowed_books:
            cat_entry = {
                "bookId": b["bookId"],
                "title": b["title"],
                "rightsStatus": b.get("rightsStatus", "UNKNOWN"),
                "publicationMode": b["publicationMode"],
                "path": f"books/{b['bookId']}.json",
                "groups": b.get("groups", []),
                "entityCount": len(b.get("entities", [])),
                "pageCount": b.get("pageCount", 0),
                "categoryHints": list(b.get("categoryHints", [])),
                "sizeBytes": b.get("sizeBytes", 0),
            }
            if mode == "restricted_preview":
                cat_entry["pipelineStatus"] = b.get("pipelineStatus", "WAITING")
                cat_entry["currentStage"] = b.get("currentStage")
            catalog_books.append(cat_entry)
        catalog_books.sort(key=lambda b: b["bookId"])

        # Step 8: Build file envelopes before projectionId computation
        files: dict[str, dict[str, Any]] = {
            "catalog.json": {
                "siteViewModelVersion": EXPECTED_VERSION,
                "mode": mode,
                "books": catalog_books,
            },
            "search-index.json": {
                "siteViewModelVersion": EXPECTED_VERSION,
                "mode": mode,
                "entries": search_entries,
            },
        }

        for b in allowed_books:
            book_meta: dict[str, Any] = {
                "bookId": b["bookId"],
                "title": b["title"],
                "rightsStatus": b.get("rightsStatus", "UNKNOWN"),
                "publicationMode": b["publicationMode"],
                "entityCount": len(b.get("entities", [])),
                "pageCount": b.get("pageCount", 0),
                "categoryHints": list(b.get("categoryHints", [])),
                "sizeBytes": b.get("sizeBytes", 0),
            }
            if mode == "restricted_preview":
                book_meta["pipelineStatus"] = b.get("pipelineStatus", "WAITING")
                book_meta["currentStage"] = b.get("currentStage")

            book_payload: dict[str, Any] = {
                "siteViewModelVersion": EXPECTED_VERSION,
                "mode": mode,
                "book": book_meta,
                "groups": b.get("groups", []),
                "entities": b.get("entities", []),
                "relations": b.get("relations", []),
            }
            if mode == "restricted_preview" and "unresolvedReferences" in b:
                book_payload["unresolvedReferences"] = b["unresolvedReferences"]
            files[f"books/{b['bookId']}.json"] = book_payload

        # Step 9: Compute deterministic projectionId
        # Hash canonical JSON representation of the entire sorted payload map
        sorted_keys = sorted(files.keys())
        raw_manifest_list = []
        for k in sorted_keys:
            raw_manifest_list.append({"path": k, "data": files[k]})

        projection_id = hashlib.sha256(canonical_json_bytes(raw_manifest_list)).hexdigest()

        # Assign projectionId to every file envelope
        for k in files:
            files[k]["projectionId"] = projection_id

        # Step 10: Fail-closed contract validation
        validate_projection(files)

        return files

    def write(
        self,
        files: dict[str, dict[str, Any]],
        output_root: Path | str,
        repository_root: Path | str,
    ) -> Path:
        """Write projected files atomically to output_root with strict security boundaries.

        Rejects destinations within repository_root or containing 'docs' segments.
        Rejects non-empty pre-existing directories.
        """
        validate_projection(files)

        out_p = Path(output_root).resolve()
        repo_p = Path(repository_root).resolve()

        # Boundary check 1: Reject if destination is inside repository_root
        is_inside_repo = False
        try:
            out_p.relative_to(repo_p)
            is_inside_repo = True
        except ValueError:
            is_inside_repo = False

        if is_inside_repo:
            raise ProjectionError(
                f"Forbidden destination: output_root '{out_p}' is inside repository_root '{repo_p}'"
            )

        # Boundary check 2: Reject if destination path contains 'docs' (case-insensitive)
        if any(part.lower() == "docs" for part in out_p.parts):
            raise ProjectionError(
                f"Forbidden destination: output_root '{out_p}' contains forbidden 'docs' segment"
            )

        # Boundary check 3: Reject existing non-empty directory
        if out_p.exists() and any(out_p.iterdir()):
            raise ProjectionError(
                f"Output directory '{out_p}' already exists and is non-empty"
            )

        # Atomic staging: write to a unique temporary directory on the same parent volume
        out_p.parent.mkdir(parents=True, exist_ok=True)
        staging_dir = out_p.parent / f".tmp_staging_{os.getpid()}_{uuid.uuid4().hex[:8]}"
        staging_dir.mkdir(parents=True, exist_ok=False)

        try:
            for rel_path, content in files.items():
                dest_file = staging_dir / rel_path
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                dest_file.write_bytes(canonical_json_bytes(content))

            # Atomic rename / move into target
            if out_p.exists():
                # If target was empty directory, remove it before replacing
                out_p.rmdir()

            os.replace(staging_dir, out_p)
        except Exception:
            shutil.rmtree(staging_dir, ignore_errors=True)
            raise

        return out_p