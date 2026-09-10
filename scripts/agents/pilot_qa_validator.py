from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.agents.contracts import ContractValidationError, validate_payload
from scripts.agents.relation_compatibility import RelationCompatibilityValidator


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

    def __init__(
        self,
        compatibility_validator: RelationCompatibilityValidator | None = None,
    ) -> None:
        self._compatibility_validator = (
            compatibility_validator or RelationCompatibilityValidator()
        )

    def _validate_unresolved_payload(self, data: Any) -> None:
        try:
            validate_payload("unresolved-relation-collection.schema.json", data)
        except ContractValidationError as cve:
            if "must be a dict" in str(cve):
                from jsonschema import Draft202012Validator
                from referencing import Registry, Resource

                schemas_dir = Path(__file__).resolve().parents[2] / "schemas"
                raw_item = (schemas_dir / "unresolved-relation.schema.json").read_text(encoding="utf-8")
                item_schema = json.loads(raw_item)
                raw_coll = (schemas_dir / "unresolved-relation-collection.schema.json").read_text(encoding="utf-8")
                coll_schema = json.loads(raw_coll)
                res = Resource.from_contents(item_schema)
                reg = (res @ Registry()).with_resource("unresolved-relation.schema.json", res)
                validator = Draft202012Validator(coll_schema, registry=reg)
                validator.validate(data)
            else:
                raise

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
                if ent_file.name in ("relations.json", "unresolved-relations.json"):
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

                    valid, err = self._compatibility_validator.validate_relation(rel, entities_by_id)
                    if not valid:
                        errors.append(f"Semantic compatibility failed for relation '{rel_id}': {err}")
            except Exception as e:
                errors.append(f"Failed to read relations.json: {e}")

        # 4. Unresolved Relations Gate
        unresolved_file = entities_dir / "unresolved-relations.json"
        if unresolved_file.exists():
            try:
                with open(unresolved_file, encoding="utf-8") as uf:
                    unresolved_data = json.load(uf)
                self._validate_unresolved_payload(unresolved_data)
                unresolved_items = unresolved_data if isinstance(unresolved_data, list) else [unresolved_data]
                for item in unresolved_items:
                    cand_tgt = item.get("candidateTargetEntityId")
                    if cand_tgt and cand_tgt in entities_by_id:
                        errors.append(
                            f"Unresolved relation targets local known entity '{cand_tgt}'. "
                            f"Known entities must be in relations.json, not unresolved-relations.json."
                        )
            except Exception as e:
                errors.append(f"Unresolved relations validation failed: {e}")

        passed = len(errors) == 0
        return DatasetQAVerdict(
            passed=passed,
            errors=errors,
            pages_covered=pages_covered,
            total_pages=expected_pages,
            entity_count=len(entities_by_id),
            relation_count=relation_count,
        )
