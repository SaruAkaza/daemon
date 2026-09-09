from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Any

from scripts.agents.canonical_json import canonical_json_bytes


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
            parts = resolved_preview.parts
            if "docs" in parts:
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
        target_dir.mkdir(parents=True, exist_ok=True)

        # Retrieve pilot data from workspace
        pilot_file = Path(workspace_root) / "data" / "pilot" / f"{book_id}.json"
        if pilot_file.exists():
            with open(pilot_file, encoding="utf-8") as f:
                pilot_data = json.load(f)
        else:
            entities: list[dict[str, Any]] = []
            entities_dir = Path(workspace_root) / "data" / "entities"
            if entities_dir.exists():
                for ef in sorted(entities_dir.glob("*.json")):
                    if ef.name == "relations.json":
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

            pilot_data = {
                "source": book_id,
                "bookId": book_id,
                "title": book_id.capitalize(),
                "entities": entities,
                "relations": relations,
            }

        # Normalize required metadata
        pilot_data.setdefault("source", pilot_data.get("bookId", book_id))
        pilot_data.setdefault("bookId", pilot_data.get("source", book_id))
        pilot_data.setdefault("title", book_id.capitalize())

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

        index_file = target_dir / "index.json"
        index_file.write_bytes(canonical_json_bytes(pilot_data))

        # Seal index.json as read-only
        try:
            os.chmod(index_file, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
        except Exception:
            pass

        return target_dir
