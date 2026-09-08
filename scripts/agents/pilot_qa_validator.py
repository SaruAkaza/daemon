from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.agents.contracts import validate_payload


@dataclass(frozen=True)
class DatasetQAVerdict:
    """Verdict produced by deterministic QA validation over RestrictedPilotWorkspace dataset."""
    passed: bool
    errors: list[str]
    pages_covered: set[int]
    total_pages: int
    entity_count: int
    relation_count: int


class PilotQAValidator:
    """Deterministically audits dataset schemas, complete page coverage, and relational integrity."""

    def validate_dataset(
        self,
        workspace_root: Path,
        book_id: str,
        expected_pages: int,
    ) -> DatasetQAVerdict:
        """Runs QA gates against the isolated workspace directory structure."""
        workspace_root = Path(workspace_root)
        entities_dir = workspace_root / "data" / "entities"
        errors: list[str] = []
        pages_covered: set[int] = set()
        entities_by_id: dict[str, dict[str, Any]] = {}
        relation_count = 0

        # 1. Audit Entities
        if entities_dir.exists():
            for ent_file in sorted(entities_dir.glob("*.json")):
                if ent_file.name == "relations.json":
                    continue
                try:
                    with open(ent_file, encoding="utf-8") as f:
                        data = json.load(f)
                    items = data if isinstance(data, list) else [data]
                    for ent in items:
                        if not isinstance(ent, dict):
                            errors.append(f"File {ent_file.name} contains non-object entity.")
                            continue
                        try:
                            validate_payload("entity.schema.json", ent)
                        except Exception as e:
                            errors.append(f"Entity schema validation failed in {ent_file.name}: {e}")

                        eid = ent.get("id")
                        if eid:
                            entities_by_id[eid] = ent

                        # Provenance check
                        source = ent.get("source")
                        page = ent.get("page")
                        pages = ent.get("pages")
                        if not source:
                            errors.append(f"Entity '{eid}' missing provenance: 'source' is required.")
                        if page is None and not pages:
                            errors.append(f"Entity '{eid}' missing provenance: valid 'page' or 'pages' is required.")

                        if isinstance(page, int) and page >= 1:
                            pages_covered.add(page)
                        if isinstance(pages, list):
                            for p in pages:
                                if isinstance(p, int) and p >= 1:
                                    pages_covered.add(p)
                except Exception as exc:
                    errors.append(f"Failed to read entity file {ent_file.name}: {exc}")

        # 2. Page Coverage Gate
        for p in range(1, expected_pages + 1):
            if p not in pages_covered:
                errors.append(f"Missing coverage for page {p} (expected 1..{expected_pages}).")

        # 3. Relational Integrity Gate
        rel_file = entities_dir / "relations.json"
        if rel_file.exists():
            try:
                with open(rel_file, encoding="utf-8") as rf:
                    relations_data = json.load(rf)
                rel_items = relations_data if isinstance(relations_data, list) else [relations_data]
                relation_count = len(rel_items)
                for rel in rel_items:
                    if not isinstance(rel, dict):
                        errors.append("Non-object entry in relations.json.")
                        continue
                    try:
                        validate_payload("relation.schema.json", rel)
                    except Exception as re:
                        errors.append(f"Relation schema validation failed: {re}")

                    src_id = rel.get("sourceEntityId")
                    tgt_id = rel.get("targetEntityId")
                    rel_id = rel.get("id", "unknown")

                    if src_id and src_id not in entities_by_id:
                        errors.append(f"Broken relation '{rel_id}': sourceEntityId '{src_id}' not found in entities.")
                    if tgt_id and tgt_id not in entities_by_id:
                        errors.append(f"Broken relation '{rel_id}': targetEntityId '{tgt_id}' not found in entities.")
            except Exception as e:
                errors.append(f"Failed to read relations.json: {e}")

        passed = len(errors) == 0
        return DatasetQAVerdict(
            passed=passed,
            errors=errors,
            pages_covered=pages_covered,
            total_pages=expected_pages,
            entity_count=len(entities_by_id),
            relation_count=relation_count,
        )
