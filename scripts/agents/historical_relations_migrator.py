from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.agents.pilot_review import AUTOMATED_AGENT_IDENTIFIERS


class MigrationSecurityError(Exception):
    """Raised when migration security or human-gate verification fails."""
    pass


class MigrationGateError(MigrationSecurityError):
    """Alias/subclass for migration gate verification errors."""
    pass


class MigrationBlockedError(Exception):
    """Raised when migration is blocked due to unhandled ambiguous records."""
    pass


VALID_RELATION_KEYS = {
    "schemaVersion",
    "id",
    "type",
    "sourceEntityId",
    "targetEntityId",
    "source",
    "page",
    "confidence",
}


def _atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp_path, path)


class HistoricalRelationsMigrator:
    """Human-gated apply engine for Relations V2 historical migration."""

    def __init__(
        self,
        approval_decision_path: Path | str,
        audit_report_path: Path | str,
        data_dir: Path | str | None = None,
    ) -> None:
        self.approval_decision_path = Path(approval_decision_path).resolve()
        self.audit_report_path = Path(audit_report_path).resolve()

        if data_dir is None:
            self.data_dir = (ROOT / "data").resolve()
        else:
            self.data_dir = Path(data_dir).resolve()

        self.approval_decision: dict[str, Any] = self._verify_and_load_decision()
        self.audit_report: dict[str, Any] = self._verify_and_load_audit_report()
        self.audit_report_sha256 = self.approval_decision["auditReportSha256"]
        self.approval_decision_id = self.approval_decision.get("decisionId", "")

    def _verify_and_load_decision(self) -> dict[str, Any]:
        if not self.approval_decision_path.is_file():
            raise MigrationSecurityError(
                f"Approval decision file not found: {self.approval_decision_path}"
            )

        try:
            decision_data = json.loads(self.approval_decision_path.read_text(encoding="utf-8"))
        except Exception as e:
            raise MigrationSecurityError(
                f"Failed to read approval decision JSON: {e}"
            ) from e

        if not isinstance(decision_data, dict):
            raise MigrationSecurityError("Approval decision payload must be a JSON object.")

        # Check status and decision
        status = str(decision_data.get("status", "")).strip().upper()
        decision = str(decision_data.get("decision", "")).strip().upper()
        if status != "APPROVED" and decision != "APPROVE":
            raise MigrationSecurityError(
                f"Approval decision is not approved (status='{status}', decision='{decision}')."
            )

        # Check decidedBy / reviewer is not an automated agent
        decided_by = decision_data.get("decidedBy") or decision_data.get("reviewer")
        if not decided_by or not isinstance(decided_by, str):
            raise MigrationSecurityError("Approval decision missing 'decidedBy' or 'reviewer'.")

        decided_by_clean = decided_by.strip().lower()
        if (
            decided_by_clean in AUTOMATED_AGENT_IDENTIFIERS
            or any(agt in decided_by_clean for agt in ("-agent", "llm", "gemini", "gpt", "claude", "bot"))
        ):
            raise MigrationSecurityError(
                f"ERR_REVIEW_AUTHORITY_VIOLATION: Decided by automated agent '{decided_by}'. Human approval required."
            )

        # Check audit report hash is present
        cited_hash = decision_data.get("auditReportSha256") or decision_data.get("reviewedResultManifestSha256")
        if not cited_hash or not isinstance(cited_hash, str):
            raise MigrationSecurityError("Approval decision missing 'auditReportSha256'.")

        decision_data["auditReportSha256"] = cited_hash.strip().lower()
        return decision_data

    def _verify_and_load_audit_report(self) -> dict[str, Any]:
        if not self.audit_report_path.is_file():
            raise MigrationSecurityError(
                f"Audit report file not found: {self.audit_report_path}"
            )

        try:
            content_bytes = self.audit_report_path.read_bytes()
            audit_report = json.loads(content_bytes.decode("utf-8"))
        except Exception as e:
            raise MigrationSecurityError(
                f"Failed to read audit report JSON: {e}"
            ) from e

        if not isinstance(audit_report, dict):
            raise MigrationSecurityError("Audit report payload must be a JSON object.")

        actual_sha256 = hashlib.sha256(content_bytes).hexdigest().lower()
        expected_sha256 = self.approval_decision["auditReportSha256"]

        if actual_sha256 != expected_sha256:
            raise MigrationSecurityError(
                f"Audit report SHA-256 hash mismatch: cited '{expected_sha256}' in decision, computed '{actual_sha256}'."
            )

        return audit_report

    def apply_migration(
        self,
        target_relations_file: Path | str | None = None,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        """Apply approved historical relations migrations.

        Fails-closed if any AMBIGUOUS records exist.
        Performs validated no-op if total relations to migrate is 0 or target file missing.
        """
        # 1. Fail-closed on AMBIGUOUS records
        for item in self.audit_report.get("itemized", []):
            classification = str(item.get("classification", "")).upper()
            recommendation = str(item.get("recommendation", "")).upper()
            if "AMBIGUOUS" in classification or "AMBIGUOUS" in recommendation:
                raise MigrationBlockedError(
                    f"Migration blocked: unhandled ambiguous relation found (id: {item.get('relationId')})."
                )

        recs = self.audit_report.get("recommendations", {})
        if recs.get("AMBIGUOUS", 0) > 0 or recs.get("ambiguous", 0) > 0:
            raise MigrationBlockedError(
                "Migration blocked: unhandled ambiguous relations present in audit report."
            )

        # 2. Determine target relations path
        if target_relations_file is not None:
            target_path = Path(target_relations_file).resolve()
        elif (self.data_dir / "entities" / "relations.json").is_file():
            target_path = (self.data_dir / "entities" / "relations.json").resolve()
        elif (self.data_dir / "relations.json").is_file():
            target_path = (self.data_dir / "relations.json").resolve()
        else:
            target_path = (self.data_dir / "entities" / "relations.json").resolve()

        to_migrate_count = (
            recs.get("migrateToCanChoosePower", 0)
            + recs.get("migrateToHasWeakness", 0)
            + recs.get("migrateToUnresolved", 0)
        )
        itemized_to_migrate = sum(
            1
            for item in self.audit_report.get("itemized", [])
            if item.get("recommendation") in ("migrateToCanChoosePower", "migrateToHasWeakness", "migrateToUnresolved")
            or item.get("classification") in ("SELECTABLE_OPTION", "WEAKNESS", "UNRESOLVED_REFERENCE")
        )
        total_to_migrate = max(to_migrate_count, itemized_to_migrate)

        # 3. Check for validated no-op
        if not target_path.is_file() or total_to_migrate == 0:
            return {
                "status": "SUCCESS",
                "dryRun": dry_run,
                "totalScanned": self.audit_report.get("totalRelationsScanned", 0),
                "migratedCanChoosePower": 0,
                "migratedHasWeakness": 0,
                "migratedUnresolved": 0,
                "unmodifiedHasPower": recs.get("keepHasPower", 0),
                "auditReportSha256": self.audit_report_sha256,
                "approvalDecisionId": self.approval_decision_id,
            }

        # 4. Read existing relations
        with open(target_path, "r", encoding="utf-8") as f:
            relations_content = json.load(f)

        if isinstance(relations_content, list):
            relations_list = relations_content
        elif isinstance(relations_content, dict) and "relations" in relations_content:
            relations_list = relations_content["relations"]
        else:
            relations_list = []

        item_by_id: dict[str, dict[str, Any]] = {}
        item_by_pair: dict[tuple[str, str], dict[str, Any]] = {}
        for item in self.audit_report.get("itemized", []):
            rid = item.get("relationId")
            if rid:
                item_by_id[rid] = item
            src = item.get("sourceEntityId")
            tgt = item.get("targetEntityId")
            if src and tgt:
                item_by_pair[(src, tgt)] = item

        new_relations: list[dict[str, Any]] = []
        unresolved_relations: list[dict[str, Any]] = []

        migrated_can_choose_power = 0
        migrated_has_weakness = 0
        migrated_unresolved = 0
        unmodified_has_power = 0

        for rel in relations_list:
            if not isinstance(rel, dict):
                continue

            matched_item = item_by_id.get(rel.get("id")) or item_by_pair.get(
                (rel.get("sourceEntityId"), rel.get("targetEntityId"))
            )

            if not matched_item:
                if rel.get("type") == "HAS_POWER":
                    unmodified_has_power += 1
                clean_rel = {k: v for k, v in rel.items() if k in VALID_RELATION_KEYS}
                new_relations.append(clean_rel)
                continue

            rec = matched_item.get("recommendation")
            cls_type = matched_item.get("classification")

            if cls_type == "SELECTABLE_OPTION" or rec == "migrateToCanChoosePower":
                rel_copy = dict(rel)
                rel_copy["type"] = "CAN_CHOOSE_POWER"
                clean_rel = {k: v for k, v in rel_copy.items() if k in VALID_RELATION_KEYS}
                clean_rel.setdefault("schemaVersion", "2.0")
                clean_rel.setdefault("confidence", 1.0)
                clean_rel.setdefault("source", rel.get("source", "historical"))
                clean_rel.setdefault("page", rel.get("page", 1))
                new_relations.append(clean_rel)
                migrated_can_choose_power += 1

            elif cls_type == "WEAKNESS" or rec == "migrateToHasWeakness":
                rel_copy = dict(rel)
                rel_copy["type"] = "HAS_WEAKNESS"
                clean_rel = {k: v for k, v in rel_copy.items() if k in VALID_RELATION_KEYS}
                clean_rel.setdefault("schemaVersion", "2.0")
                clean_rel.setdefault("confidence", 1.0)
                clean_rel.setdefault("source", rel.get("source", "historical"))
                clean_rel.setdefault("page", rel.get("page", 1))
                new_relations.append(clean_rel)
                migrated_has_weakness += 1

            elif cls_type == "UNRESOLVED_REFERENCE" or rec == "migrateToUnresolved":
                unresolved_entry: dict[str, Any] = {
                    "sourceEntityId": rel.get("sourceEntityId", ""),
                    "candidateRelationType": rel.get("type", "HAS_POWER"),
                    "rawReferenceText": (
                        rel.get("rawReferenceText")
                        or rel.get("evidence")
                        or rel.get("targetEntityId")
                        or "Target entity reference unresolved in local book context"
                    ),
                    "sourcePage": int(rel.get("sourcePage") or rel.get("page") or 1),
                    "sourceParagraph": int(rel.get("sourceParagraph") or 1),
                    "reason": matched_item.get("reason") or "Target entity reference not found in local context.",
                    "status": (
                        rel.get("status")
                        if rel.get("status") in {
                            "UNRESOLVED_PENDING_CROSS_BOOK_LINK",
                            "UNRESOLVED_AMBIGUOUS_NAME",
                            "UNRESOLVED_MISSING_TARGET",
                        }
                        else "UNRESOLVED_MISSING_TARGET"
                    ),
                }
                if rel.get("targetEntityId"):
                    unresolved_entry["candidateTargetEntityId"] = rel["targetEntityId"]
                unresolved_relations.append(unresolved_entry)
                migrated_unresolved += 1

            elif cls_type == "ACTUAL_POSSESSION" or rec == "keepHasPower":
                rel_copy = dict(rel)
                rel_copy["type"] = "HAS_POWER"
                clean_rel = {k: v for k, v in rel_copy.items() if k in VALID_RELATION_KEYS}
                clean_rel.setdefault("schemaVersion", "2.0")
                clean_rel.setdefault("confidence", 1.0)
                clean_rel.setdefault("source", rel.get("source", "historical"))
                clean_rel.setdefault("page", rel.get("page", 1))
                new_relations.append(clean_rel)
                unmodified_has_power += 1

            else:
                clean_rel = {k: v for k, v in rel.items() if k in VALID_RELATION_KEYS}
                new_relations.append(clean_rel)

        # 5. Atomic write if not dry_run
        if not dry_run:
            _atomic_write_json(target_path, new_relations)

            if migrated_unresolved > 0 or unresolved_relations:
                unresolved_path = target_path.parent / "unresolved-relations.json"
                final_unres: list[dict[str, Any]] = []
                if unresolved_path.is_file():
                    try:
                        with open(unresolved_path, "r", encoding="utf-8") as f:
                            existing_unres = json.load(f)
                        if isinstance(existing_unres, list):
                            final_unres = list(existing_unres)
                    except Exception:
                        final_unres = []

                for u in unresolved_relations:
                    if u not in final_unres:
                        final_unres.append(u)

                _atomic_write_json(unresolved_path, final_unres)

        total_scanned = self.audit_report.get("totalRelationsScanned", len(relations_list))
        return {
            "status": "SUCCESS",
            "dryRun": dry_run,
            "totalScanned": total_scanned,
            "migratedCanChoosePower": migrated_can_choose_power,
            "migratedHasWeakness": migrated_has_weakness,
            "migratedUnresolved": migrated_unresolved,
            "unmodifiedHasPower": unmodified_has_power,
            "auditReportSha256": self.audit_report_sha256,
            "approvalDecisionId": self.approval_decision_id,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Apply Relations V2 migration to historical relations."
    )
    parser.add_argument(
        "--approval-decision",
        type=Path,
        required=True,
        help="Path to human approval decision JSON file",
    )
    parser.add_argument(
        "--audit-report",
        type=Path,
        required=True,
        help="Path to audit report JSON file",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Path to data directory (default: repo data/)",
    )
    parser.add_argument(
        "--target-relations",
        type=Path,
        default=None,
        help="Specific path to target relations.json file",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Perform simulation without writing changes to disk",
    )
    parser.add_argument(
        "--output-result",
        type=Path,
        default=None,
        help="Path to write migration execution result JSON",
    )
    args = parser.parse_args(argv)

    migrator = HistoricalRelationsMigrator(
        approval_decision_path=args.approval_decision,
        audit_report_path=args.audit_report,
        data_dir=args.data_dir,
    )
    result = migrator.apply_migration(
        target_relations_file=args.target_relations,
        dry_run=args.dry_run,
    )

    if args.output_result:
        out_p = Path(args.output_result).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Result written to: {out_p}")

    print("Historical Relations Migration Result:")
    print(f"  Status                  : {result['status']}")
    print(f"  Dry Run                 : {result['dryRun']}")
    print(f"  Total Scanned           : {result['totalScanned']}")
    print(f"  CAN_CHOOSE_POWER        : {result['migratedCanChoosePower']}")
    print(f"  HAS_WEAKNESS            : {result['migratedHasWeakness']}")
    print(f"  Unresolved Routed       : {result['migratedUnresolved']}")
    print(f"  Unmodified HAS_POWER    : {result['unmodifiedHasPower']}")
    print(f"  Audit Report SHA-256    : {result['auditReportSha256']}")
    print(f"  Approval Decision ID    : {result['approvalDecisionId']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
