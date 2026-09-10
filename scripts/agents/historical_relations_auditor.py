from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from scripts.agents.relation_compatibility import RelationCompatibilityValidator

ROOT = Path(__file__).resolve().parents[2]


class HistoricalRelationsAuditor:
    """Strictly READ-ONLY auditor for historical relations to guide Relations V2 migration."""

    def __init__(
        self,
        data_dir: Path | str | None = None,
        compatibility_validator: RelationCompatibilityValidator | None = None,
    ) -> None:
        if data_dir is None:
            self.data_dir = (ROOT / "data").resolve()
        else:
            self.data_dir = Path(data_dir).resolve()

        self._validator = compatibility_validator or RelationCompatibilityValidator()

    def _get_entities_dir(self) -> Path:
        if (self.data_dir / "entities").is_dir():
            return self.data_dir / "entities"
        if (self.data_dir / "data" / "entities").is_dir():
            return self.data_dir / "data" / "entities"
        if self.data_dir.name == "entities":
            return self.data_dir
        return self.data_dir / "entities"

    def _index_entities(self, entities_dir: Path) -> dict[str, dict[str, Any]]:
        entity_index: dict[str, dict[str, Any]] = {}
        if not entities_dir.is_dir():
            return entity_index

        for ent_file in sorted(entities_dir.glob("*.json")):
            if ent_file.name in ("relations.json", "unresolved-relations.json"):
                continue
            try:
                with open(ent_file, "r", encoding="utf-8") as f:
                    content = json.load(f)
                items = content if isinstance(content, list) else [content]
                for item in items:
                    if isinstance(item, dict) and "id" in item:
                        entity_index[item["id"]] = item
            except Exception:
                continue

        return entity_index

    def _find_relation_files(self) -> list[Path]:
        relation_files: list[Path] = []
        if not self.data_dir.is_dir():
            return relation_files

        for p in sorted(self.data_dir.rglob("*.json")):
            name_lower = p.name.lower()
            if "unresolved" in name_lower or "schema" in name_lower:
                continue
            if p.name == "relations.json" or "relation" in name_lower:
                relation_files.append(p)

        return sorted(set(relation_files))

    def classify_has_power(
        self,
        relation: dict[str, Any],
        entity_index: dict[str, dict[str, Any]],
    ) -> tuple[str, str, str]:
        """Classify a HAS_POWER relation into V2 migration taxonomy.

        Returns:
            Tuple of (classification, recommendation, reason)
        """
        src_id = relation.get("sourceEntityId")
        tgt_id = relation.get("targetEntityId")

        src_entity = entity_index.get(src_id) if src_id else None
        tgt_entity = entity_index.get(tgt_id) if tgt_id else None

        # a) UNRESOLVED_REFERENCE (migrateToUnresolved)
        if src_entity is None or tgt_entity is None:
            missing = []
            if src_entity is None:
                missing.append(f"source '{src_id}'")
            if tgt_entity is None:
                missing.append(f"target '{tgt_id}'")
            return (
                "UNRESOLVED_REFERENCE",
                "migrateToUnresolved",
                f"Entity reference not found in local entities context: {', '.join(missing)}.",
            )

        # b) WEAKNESS (migrateToHasWeakness)
        tgt_subtype = str(tgt_entity.get("subtype", "")).lower()
        tgt_id_str = str(tgt_id).lower()
        tgt_tags = [str(t).lower() for t in tgt_entity.get("tags", [])]
        weakness_keywords = ("fraqueza", "desvantagem", "weakness")

        is_weakness = (
            tgt_subtype in ("fraqueza", "desvantagem", "fraquezas", "desvantagens")
            or any(kw in tgt_id_str for kw in weakness_keywords)
            or any(any(kw in tag for kw in weakness_keywords) for tag in tgt_tags)
        )
        if is_weakness:
            return (
                "WEAKNESS",
                "migrateToHasWeakness",
                f"Target entity '{tgt_id}' denotes a weakness or disadvantage.",
            )

        # c) SELECTABLE_OPTION (migrateToCanChoosePower)
        selectable_keywords = (
            "possíveis",
            "possiveis",
            "menu",
            "escolha",
            "escolhas",
            "opção",
            "opcao",
            "opções",
            "opcoes",
            "selecionável",
            "selecionavel",
            "pode escolher",
            "selectable",
            "choice",
        )

        texts_to_check: list[str] = []
        meta = relation.get("metadata")
        if isinstance(meta, dict):
            texts_to_check.append(json.dumps(meta, ensure_ascii=False))
        elif meta:
            texts_to_check.append(str(meta))

        for field in ("evidence", "notes", "description", "selectionType", "mode"):
            val = relation.get(field)
            if isinstance(val, (list, dict)):
                texts_to_check.append(json.dumps(val, ensure_ascii=False))
            elif val:
                texts_to_check.append(str(val))

        tgt_entries = tgt_entity.get("entries", [])
        if isinstance(tgt_entries, list):
            texts_to_check.append(" ".join(str(e) for e in tgt_entries))
        elif tgt_entries:
            texts_to_check.append(str(tgt_entries))
        if tgt_entity.get("description"):
            texts_to_check.append(str(tgt_entity["description"]))

        src_entries = src_entity.get("entries", [])
        if isinstance(src_entries, list):
            texts_to_check.append(" ".join(str(e) for e in src_entries))
        elif src_entries:
            texts_to_check.append(str(src_entries))

        combined_text = " ".join(texts_to_check).lower()
        if any(kw in combined_text for kw in selectable_keywords):
            return (
                "SELECTABLE_OPTION",
                "migrateToCanChoosePower",
                "Relation metadata, evidence, or entity text indicates selectable option or menu choice.",
            )

        # d) INVALID_SEMANTIC_TRIPLET (invalidTriplets) & e) ACTUAL_POSSESSION (keepHasPower)
        is_valid, err = self._validator.validate_relation(relation, entity_index)
        if not is_valid:
            return (
                "INVALID_SEMANTIC_TRIPLET",
                "invalidTriplets",
                err or "Categories or subtypes violate compatibility matrix for HAS_POWER.",
            )

        return (
            "ACTUAL_POSSESSION",
            "keepHasPower",
            "Valid possession matching HAS_POWER compatibility rules.",
        )

    def scan(self) -> dict[str, Any]:
        """Perform strictly read-only audit of historical relations across data directory."""
        entities_dir = self._get_entities_dir()
        entity_index = self._index_entities(entities_dir)
        relation_files = self._find_relation_files()

        total_relations_scanned = 0
        has_power_count = 0
        recommendations = {
            "keepHasPower": 0,
            "migrateToCanChoosePower": 0,
            "migrateToHasWeakness": 0,
            "migrateToUnresolved": 0,
            "invalidTriplets": 0,
        }
        itemized: list[dict[str, Any]] = []

        for rel_file in relation_files:
            try:
                with open(rel_file, "r", encoding="utf-8") as f:
                    content = json.load(f)
            except Exception:
                continue

            if isinstance(content, list):
                rel_items = content
            elif isinstance(content, dict) and "relations" in content and isinstance(content["relations"], list):
                rel_items = content["relations"]
            elif isinstance(content, dict) and "sourceEntityId" in content and "targetEntityId" in content:
                rel_items = [content]
            else:
                rel_items = []

            for rel in rel_items:
                if not isinstance(rel, dict):
                    continue

                total_relations_scanned += 1
                if rel.get("type") != "HAS_POWER":
                    continue

                has_power_count += 1
                classification, recommendation, reason = self.classify_has_power(rel, entity_index)
                recommendations[recommendation] += 1
                itemized.append({
                    "relationId": rel.get("id"),
                    "sourceEntityId": rel.get("sourceEntityId"),
                    "targetEntityId": rel.get("targetEntityId"),
                    "classification": classification,
                    "recommendation": recommendation,
                    "reason": reason,
                    "relation": rel,
                })

        return {
            "totalRelationsScanned": total_relations_scanned,
            "hasPowerCount": has_power_count,
            "recommendations": recommendations,
            "itemized": itemized,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit historical HAS_POWER relations for Relations V2 migration."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Path to data directory (default: repo data/)",
    )
    parser.add_argument(
        "--output-report",
        type=Path,
        default=None,
        help="Path to output JSON report file",
    )
    args = parser.parse_args(argv)

    auditor = HistoricalRelationsAuditor(data_dir=args.data_dir)
    report = auditor.scan()

    if args.output_report:
        out_path = Path(args.output_report).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Report written to: {out_path}")

    print("Historical Relations Audit Summary:")
    print(f"  Total Relations Scanned : {report['totalRelationsScanned']}")
    print(f"  HAS_POWER Count         : {report['hasPowerCount']}")
    print("  Recommendations:")
    for rec_key, rec_val in report["recommendations"].items():
        print(f"    - {rec_key}: {rec_val}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
