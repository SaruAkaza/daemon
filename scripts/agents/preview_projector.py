from __future__ import annotations

import json
import os
import shutil
import stat
import uuid
from pathlib import Path
from typing import Any

from scripts.agents.canonical_json import canonical_json_bytes
from scripts.agents.frontend_projector import FrontendProjector
from scripts.agents.site_view_model import ProjectionError


class LocalPreviewProjectorError(RuntimeError):
    """Raised when preview projection violates security boundaries or filesystem invariants."""
    pass


class LocalPreviewProjector:
    """Projects restricted pilot data exclusively to untracked runtime preview directory."""

    def project_local_preview(
        self,
        workspace_root: Path,
        preview_root: Path,
        book_id: str,
        rights_status: str,
        publication_mode: str,
        repository_root: Path | None = None,
    ) -> Path:
        """Projects local navigable/searchable preview bundle under preview_root/<bookId>/."""
        resolved_preview = Path(preview_root).resolve()
        repo = Path(repository_root).resolve() if repository_root else Path(__file__).resolve().parents[2]

        # Enforce RESTRICTED_CONTENT_NEVER_ENTERS_MAIN_WORKTREE
        if rights_status.upper() in ("UNKNOWN", "PRIVATE") or publication_mode.upper() == "NOT_PUBLIC":
            if any(p.lower() == "docs" for p in resolved_preview.parts):
                raise LocalPreviewProjectorError(
                    f"ERR_RESTRICTED_CONTENT_PROJECTION_BLOCKED: Cannot project restricted book '{book_id}' into docs: {resolved_preview}"
                )
            try:
                resolved_preview.relative_to(repo)
                raise LocalPreviewProjectorError(
                    f"ERR_RESTRICTED_CONTENT_PROJECTION_BLOCKED: Cannot project restricted book '{book_id}' into repository: {resolved_preview}"
                )
            except ValueError:
                # Outside repository root
                pass

        target_dir = resolved_preview / book_id
        if target_dir.exists() and any(target_dir.iterdir()):
            raise LocalPreviewProjectorError(
                f"ERR_PREVIEW_TARGET_EXISTS: Target directory '{target_dir}' already exists and is not empty"
            )

        # Retrieve pilot data from workspace
        pilot_file = Path(workspace_root) / "data" / "pilot" / f"{book_id}.json"
        if pilot_file.exists():
            with open(pilot_file, encoding="utf-8") as f:
                pilot_data = json.load(f)
            canonical_title = pilot_data.get("title") or book_id
        else:
            entities: list[dict[str, Any]] = []
            entities_dir = Path(workspace_root) / "data" / "entities"
            if entities_dir.exists():
                for ef in sorted(entities_dir.glob("*.json")):
                    if ef.name in ("relations.json", "unresolved-relations.json"):
                        continue
                    with open(ef, encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            entities.extend(data)
                        else:
                            entities.append(data)

            relations: list[dict[str, Any]] = []
            rel_file = entities_dir / "relations.json"
            if rel_file.exists():
                with open(rel_file, encoding="utf-8") as f:
                    rdata = json.load(f)
                    relations = rdata if isinstance(rdata, list) else [rdata]

            book_meta_file = Path(workspace_root) / "data" / "books" / f"{book_id}.json"
            if book_meta_file.exists():
                with open(book_meta_file, encoding="utf-8") as bf:
                    bmeta = json.load(bf)
                    canonical_title = bmeta.get("title", book_id)
            else:
                canonical_title = book_id

            pilot_data = {
                "source": book_id,
                "bookId": book_id,
                "title": book_id.capitalize(),
                "entities": entities,
                "relations": relations,
            }

        # Normalize required metadata for legacy index.json
        pilot_data.setdefault("source", pilot_data.get("bookId", book_id))
        pilot_data.setdefault("bookId", pilot_data.get("source", book_id))
        pilot_data.setdefault("title", book_id.capitalize())

        # Unresolved references from canonical artifact
        unresolved_file = Path(workspace_root) / "data" / "entities" / "unresolved-relations.json"
        unresolved_references: list[dict[str, Any]] = []
        if unresolved_file.exists():
            with open(unresolved_file, encoding="utf-8") as uf:
                udata = json.load(uf)
                unresolved_references = udata if isinstance(udata, list) else [udata]
        elif "unresolvedReferences" in pilot_data and isinstance(pilot_data["unresolvedReferences"], list):
            unresolved_references = list(pilot_data["unresolvedReferences"])

        # Project entities into characters for backwards compatibility with frontend
        characters = list(pilot_data.get("characters", []))
        if not characters and "entities" in pilot_data:
            for ent in pilot_data["entities"]:
                cat = ent.get("category", "")
                if cat in ("creature_npc", "creature", "npc") or ent.get("area") == "criaturas_npcs":
                    ent_id = ent.get("id", "")
                    clean_id = ent_id.split("-", 1)[1] if ent_id.startswith("creature-") else ent_id
                    sections = ent.get("sections", [])
                    if not sections:
                        pars = ent.get("paragraphs") or ent.get("entries") or []
                        sections = [
                            {
                                "id": "ficha",
                                "title": "Ficha",
                                "paragraphs": pars if isinstance(pars, list) else [str(pars)],
                            }
                        ]
                    characters.append(
                        {
                            "id": clean_id,
                            "name": ent.get("name", clean_id),
                            "sections": sections,
                        }
                    )
            if characters:
                pilot_data["characters"] = characters

        # Adapt workspace entities to ApprovedBook contract
        adapted_entities: list[dict[str, Any]] = []
        for ent in pilot_data.get("entities", []):
            eid = ent.get("id") or ent.get("entityId")
            if not eid:
                continue
            cat = ent.get("category") or ent.get("type", "core_rule")
            subtype = ent.get("subtype")
            display_type = ent.get("displayType")
            raw_prov = ent.get("provenance")
            if isinstance(raw_prov, dict) and "source" in raw_prov and "pages" in raw_prov:
                prov = {"source": str(raw_prov["source"]), "pages": list(raw_prov["pages"])}
            else:
                ent_src = ent.get("source", book_id)
                ent_pages = ent.get("pages") or ([ent["page"]] if ent.get("page") else [1])
                prov = {"source": str(ent_src), "pages": list(ent_pages)}

            content: list[dict[str, Any]] = []
            if "content" in ent and isinstance(ent["content"], list):
                for blk in ent["content"]:
                    if isinstance(blk, dict) and "title" in blk and "paragraphs" in blk:
                        content.append({"title": str(blk["title"]), "paragraphs": [str(p) for p in blk["paragraphs"]]})
            elif "entries" in ent and isinstance(ent["entries"], list):
                content = [{"title": "Conteúdo", "paragraphs": [str(e) for e in ent["entries"]]}]
            elif "sections" in ent and isinstance(ent["sections"], list):
                for sec in ent["sections"]:
                    if isinstance(sec, dict):
                        content.append({
                            "title": str(sec.get("title", "Seção")),
                            "paragraphs": [str(p) for p in (sec.get("paragraphs") or [])],
                        })
            elif "paragraphs" in ent and isinstance(ent["paragraphs"], list):
                content = [{"title": "Descrição", "paragraphs": [str(p) for p in ent["paragraphs"]]}]

            adapted_ent = {
                "id": str(eid),
                "name": str(ent.get("name", eid)),
                "category": str(cat),
                "provenance": prov,
                "content": content,
                "aliases": list(ent.get("aliases", [])),
                "tags": list(ent.get("tags", [])),
            }
            if subtype:
                adapted_ent["subtype"] = str(subtype)
            if display_type:
                adapted_ent["displayType"] = str(display_type)
            if "technicalDetails" in ent:
                adapted_ent["technicalDetails"] = dict(ent["technicalDetails"])
            adapted_entities.append(adapted_ent)

        adapted_relations: list[dict[str, Any]] = []
        for rel in pilot_data.get("relations", []):
            rid = rel.get("id") or rel.get("relationId")
            if not rid:
                continue
            adapted_rel = {
                "id": str(rid),
                "relationId": str(rid),
                "type": str(rel["type"]),
                "sourceEntityId": str(rel["sourceEntityId"]),
                "targetEntityId": str(rel["targetEntityId"]),
            }
            if "outgoingLabel" in rel:
                adapted_rel["outgoingLabel"] = str(rel["outgoingLabel"])
            if "incomingLabel" in rel:
                adapted_rel["incomingLabel"] = str(rel["incomingLabel"])
            adapted_relations.append(adapted_rel)

        approved_book: dict[str, Any] = {
            "bookId": book_id,
            "title": canonical_title,
            "rightsStatus": rights_status,
            "publicationMode": publication_mode,
            "entities": adapted_entities,
            "relations": adapted_relations,
            "groups": list(pilot_data.get("groups", [])),
        }
        if unresolved_references:
            approved_book["unresolvedReferences"] = unresolved_references

        # Build site view model files using FrontendProjector
        projector = FrontendProjector()
        try:
            site_files = projector.build([approved_book], "restricted_preview")
        except ProjectionError as pe:
            raise LocalPreviewProjectorError(f"ERR_PREVIEW_BUILD_FAILED: {pe}") from pe

        # Staging directory on the same parent volume
        resolved_preview.mkdir(parents=True, exist_ok=True)
        staging_dir = resolved_preview / f".tmp_staging_{book_id}_{os.getpid()}_{uuid.uuid4().hex[:8]}"
        staging_dir.mkdir(parents=True, exist_ok=False)

        try:
            # 1. Write legacy index.json
            legacy_index = staging_dir / "index.json"
            legacy_index.write_bytes(canonical_json_bytes(pilot_data))
            try:
                os.chmod(legacy_index, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
            except Exception:
                pass

            # 2. Write site-data using FrontendProjector.write
            site_data_dir = staging_dir / "site-data"
            projector.write(site_files, site_data_dir, repo)

            # 3. Promote staging_dir to target_dir atomically
            if target_dir.exists():
                target_dir.rmdir()
            os.replace(staging_dir, target_dir)
        except Exception as exc:
            shutil.rmtree(staging_dir, ignore_errors=True)
            if isinstance(exc, LocalPreviewProjectorError):
                raise
            raise LocalPreviewProjectorError(f"ERR_PREVIEW_WRITE_FAILED: {exc}") from exc

        return target_dir
