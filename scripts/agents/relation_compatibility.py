from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS_DIR = (ROOT / "schemas").resolve()


class RelationCompatibilityValidator:
    """Validates relation semantic compatibility against relation-compatibility-v2.json."""

    def __init__(self, matrix_path: Path | str | None = None) -> None:
        if matrix_path is None:
            self._matrix_path = SCHEMAS_DIR / "relation-compatibility-v2.json"
        else:
            self._matrix_path = Path(matrix_path)

        self._schema_path = SCHEMAS_DIR / "relation-compatibility.schema.json"

        if not self._schema_path.is_file():
            raise FileNotFoundError(f"Compatibility schema not found: {self._schema_path}")
        if not self._matrix_path.is_file():
            raise FileNotFoundError(f"Compatibility matrix not found: {self._matrix_path}")

        schema_data = json.loads(self._schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema_data)
        schema_validator = Draft202012Validator(schema_data)

        matrix_data = json.loads(self._matrix_path.read_text(encoding="utf-8"))
        schema_validator.validate(matrix_data)

        self._matrix = matrix_data
        self._rules: dict[str, dict[str, Any]] = {
            rule["relationType"]: rule for rule in matrix_data.get("rules", [])
        }

    def validate_relation(
        self,
        relation: dict[str, Any],
        entity_index: dict[str, dict[str, Any]],
    ) -> tuple[bool, str | None]:
        """Validate a single relation against the canonical compatibility matrix.

        Args:
            relation: Dictionary representation of a relation item.
            entity_index: Mapping of entityId -> entity dictionary.

        Returns:
            Tuple of (is_valid, error_message). If valid, error_message is None.
        """
        src_id = relation.get("sourceEntityId")
        tgt_id = relation.get("targetEntityId")
        rel_type = relation.get("type")

        # Check 1: Source entity exists in context
        src_entity = entity_index.get(src_id) if src_id is not None else None
        if src_entity is None:
            return (False, f"Source entity '{src_id}' not found in local entities context.")

        # Check 2: Target entity exists in context
        tgt_entity = entity_index.get(tgt_id) if tgt_id is not None else None
        if tgt_entity is None:
            return (False, f"Target entity '{tgt_id}' not found in local entities context.")

        # Check 3: Unsupported relation type
        rule = self._rules.get(rel_type) if rel_type is not None else None
        if rule is None:
            return (False, f"Unsupported relation type: '{rel_type}'.")

        # Check 4: Source category allowed
        src_cat = src_entity.get("category")
        allowed_src_cats = rule.get("allowedSourceCategories", [])
        if src_cat not in allowed_src_cats:
            return (False, f"Source category '{src_cat}' not allowed for {rel_type}.")

        # Check 5: Source subtype allowed if restricted
        if "allowedSourceSubtypes" in rule:
            src_sub = src_entity.get("subtype")
            if src_sub not in rule["allowedSourceSubtypes"]:
                return (False, f"Source subtype '{src_sub}' not allowed for {rel_type}.")

        # Check 6: Target category allowed
        tgt_cat = tgt_entity.get("category")
        allowed_tgt_cats = rule.get("allowedTargetCategories", [])
        if tgt_cat not in allowed_tgt_cats:
            return (False, f"Target category '{tgt_cat}' not allowed for {rel_type}.")

        # Check 7: Target subtype allowed if restricted
        if "allowedTargetSubtypes" in rule:
            tgt_sub = tgt_entity.get("subtype")
            if tgt_sub not in rule["allowedTargetSubtypes"]:
                return (False, f"Target subtype '{tgt_sub}' not allowed for {rel_type}.")

        return (True, None)

    validate_relation_item = validate_relation

    def validate_collection(
        self,
        relations: list[dict[str, Any]],
        entity_index: dict[str, dict[str, Any]],
    ) -> list[str]:
        """Validate a collection of relations, returning all error messages.

        Args:
            relations: List of relation items.
            entity_index: Mapping of entityId -> entity dictionary.

        Returns:
            List of collected error messages. Empty list if all are valid.
        """
        errors: list[str] = []
        for rel in relations:
            valid, err = self.validate_relation(rel, entity_index)
            if not valid and err:
                errors.append(err)
        return errors
