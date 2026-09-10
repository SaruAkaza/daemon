from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.agents.contracts import validate_payload
from scripts.agents.historical_relations_migrator import (
    HistoricalRelationsMigrator,
    MigrationBlockedError,
    MigrationSecurityError,
)


def test_migrator_blocks_without_human_approval(tmp_path: Path):
    audit_report = {
        "totalRelationsScanned": 0,
        "hasPowerCount": 0,
        "recommendations": {
            "keepHasPower": 0,
            "migrateToCanChoosePower": 0,
            "migrateToHasWeakness": 0,
            "migrateToUnresolved": 0,
            "invalidTriplets": 0,
        },
        "itemized": [],
    }
    report_file = tmp_path / "audit_report.json"
    report_bytes = json.dumps(audit_report).encode("utf-8")
    report_file.write_bytes(report_bytes)
    report_hash = hashlib.sha256(report_bytes).hexdigest()

    # Case 1: Missing decision file
    missing_decision = tmp_path / "missing_decision.json"
    with pytest.raises(MigrationSecurityError, match="not found"):
        HistoricalRelationsMigrator(
            approval_decision_path=missing_decision,
            audit_report_path=report_file,
        )

    # Case 2: Rejected decision
    rejected_decision = {
        "decisionId": "DEC-REJECT-01",
        "status": "REJECTED",
        "decision": "REJECT",
        "decidedBy": "human-reviewer",
        "auditReportSha256": report_hash,
    }
    rejected_file = tmp_path / "rejected_decision.json"
    rejected_file.write_text(json.dumps(rejected_decision), encoding="utf-8")
    with pytest.raises(MigrationSecurityError, match="not approved"):
        HistoricalRelationsMigrator(
            approval_decision_path=rejected_file,
            audit_report_path=report_file,
        )

    # Case 3: Automated agent decision
    automated_decision = {
        "decisionId": "DEC-AUTO-01",
        "status": "APPROVED",
        "decision": "APPROVE",
        "decidedBy": "relations-agent",
        "auditReportSha256": report_hash,
    }
    automated_file = tmp_path / "automated_decision.json"
    automated_file.write_text(json.dumps(automated_decision), encoding="utf-8")
    with pytest.raises(MigrationSecurityError, match="automated agent"):
        HistoricalRelationsMigrator(
            approval_decision_path=automated_file,
            audit_report_path=report_file,
        )

    # Case 4: Ambiguous records fail-closed
    ambiguous_report = {
        "totalRelationsScanned": 1,
        "hasPowerCount": 1,
        "recommendations": {
            "keepHasPower": 0,
            "migrateToCanChoosePower": 0,
            "migrateToHasWeakness": 0,
            "migrateToUnresolved": 0,
            "invalidTriplets": 0,
            "ambiguous": 1,
        },
        "itemized": [
            {
                "relationId": "rel-ambig",
                "classification": "AMBIGUOUS",
                "recommendation": "needsHumanResolution",
            }
        ],
    }
    ambig_bytes = json.dumps(ambiguous_report).encode("utf-8")
    ambig_file = tmp_path / "ambig_report.json"
    ambig_file.write_bytes(ambig_bytes)
    ambig_decision = {
        "decisionId": "DEC-AMBIG",
        "status": "APPROVED",
        "decision": "APPROVE",
        "decidedBy": "human-curator",
        "auditReportSha256": hashlib.sha256(ambig_bytes).hexdigest(),
    }
    ambig_dec_file = tmp_path / "ambig_decision.json"
    ambig_dec_file.write_text(json.dumps(ambig_decision), encoding="utf-8")
    migrator_ambig = HistoricalRelationsMigrator(
        approval_decision_path=ambig_dec_file,
        audit_report_path=ambig_file,
    )
    with pytest.raises(MigrationBlockedError, match="ambiguous"):
        migrator_ambig.apply_migration(dry_run=True)


def test_migrator_blocks_on_hash_mismatch(tmp_path: Path):
    audit_report = {
        "totalRelationsScanned": 0,
        "hasPowerCount": 0,
        "recommendations": {
            "keepHasPower": 0,
            "migrateToCanChoosePower": 0,
            "migrateToHasWeakness": 0,
            "migrateToUnresolved": 0,
            "invalidTriplets": 0,
        },
        "itemized": [],
    }
    report_file = tmp_path / "audit_report.json"
    report_file.write_text(json.dumps(audit_report), encoding="utf-8")

    bogus_hash = "0" * 64
    decision = {
        "decisionId": "DEC-MISMATCH-01",
        "status": "APPROVED",
        "decision": "APPROVE",
        "decidedBy": "human-reviewer",
        "auditReportSha256": bogus_hash,
    }
    decision_file = tmp_path / "decision_mismatch.json"
    decision_file.write_text(json.dumps(decision), encoding="utf-8")

    with pytest.raises(MigrationSecurityError, match="mismatch"):
        HistoricalRelationsMigrator(
            approval_decision_path=decision_file,
            audit_report_path=report_file,
        )


def test_migrator_applies_approved_conversions_atomically(tmp_path: Path):
    data_dir = tmp_path / "data"
    entities_dir = data_dir / "entities"
    entities_dir.mkdir(parents=True)

    relations = [
        {
            "schemaVersion": "2.0",
            "id": "rel-01",
            "type": "HAS_POWER",
            "sourceEntityId": "creature-lobo",
            "targetEntityId": "power-opcao",
            "source": "manual-monstros",
            "page": 10,
            "confidence": 1.0,
        },
        {
            "schemaVersion": "2.0",
            "id": "rel-02",
            "type": "HAS_POWER",
            "sourceEntityId": "creature-lobo",
            "targetEntityId": "power-fraqueza",
            "source": "manual-monstros",
            "page": 10,
            "confidence": 1.0,
        },
        {
            "schemaVersion": "2.0",
            "id": "rel-03",
            "type": "HAS_POWER",
            "sourceEntityId": "creature-lobo",
            "targetEntityId": "power-morder",
            "source": "manual-monstros",
            "page": 10,
            "confidence": 1.0,
        },
        {
            "schemaVersion": "2.0",
            "id": "rel-04",
            "type": "HAS_POWER",
            "sourceEntityId": "creature-lobo",
            "targetEntityId": "power-ausente",
            "source": "manual-monstros",
            "page": 10,
            "confidence": 1.0,
        },
    ]
    rel_file = entities_dir / "relations.json"
    rel_file.write_text(json.dumps(relations, indent=2, ensure_ascii=False), encoding="utf-8")

    audit_report = {
        "totalRelationsScanned": 4,
        "hasPowerCount": 4,
        "recommendations": {
            "keepHasPower": 1,
            "migrateToCanChoosePower": 1,
            "migrateToHasWeakness": 1,
            "migrateToUnresolved": 1,
            "invalidTriplets": 0,
        },
        "itemized": [
            {
                "relationId": "rel-01",
                "sourceEntityId": "creature-lobo",
                "targetEntityId": "power-opcao",
                "classification": "SELECTABLE_OPTION",
                "recommendation": "migrateToCanChoosePower",
                "reason": "Opção selecionável de poder.",
            },
            {
                "relationId": "rel-02",
                "sourceEntityId": "creature-lobo",
                "targetEntityId": "power-fraqueza",
                "classification": "WEAKNESS",
                "recommendation": "migrateToHasWeakness",
                "reason": "Entidade denota fraqueza.",
            },
            {
                "relationId": "rel-03",
                "sourceEntityId": "creature-lobo",
                "targetEntityId": "power-morder",
                "classification": "ACTUAL_POSSESSION",
                "recommendation": "keepHasPower",
                "reason": "Posse efetiva do poder.",
            },
            {
                "relationId": "rel-04",
                "sourceEntityId": "creature-lobo",
                "targetEntityId": "power-ausente",
                "classification": "UNRESOLVED_REFERENCE",
                "recommendation": "migrateToUnresolved",
                "reason": "Referência não encontrada localmente.",
            },
        ],
    }
    report_file = tmp_path / "audit_report.json"
    report_bytes = json.dumps(audit_report, indent=2, ensure_ascii=False).encode("utf-8")
    report_file.write_bytes(report_bytes)
    report_hash = hashlib.sha256(report_bytes).hexdigest()

    decision = {
        "decisionId": "DEC-TEST-001",
        "status": "APPROVED",
        "decision": "APPROVE",
        "decidedBy": "human-curator",
        "auditReportSha256": report_hash,
    }
    decision_file = tmp_path / "decision.json"
    decision_file.write_text(json.dumps(decision, indent=2), encoding="utf-8")

    migrator = HistoricalRelationsMigrator(
        approval_decision_path=decision_file,
        audit_report_path=report_file,
        data_dir=data_dir,
    )

    # 1. Dry run: verify no changes written to disk
    dry_res = migrator.apply_migration(target_relations_file=rel_file, dry_run=True)
    assert dry_res["status"] == "SUCCESS"
    assert dry_res["dryRun"] is True
    assert dry_res["migratedCanChoosePower"] == 1
    assert dry_res["migratedHasWeakness"] == 1
    assert dry_res["migratedUnresolved"] == 1
    assert dry_res["unmodifiedHasPower"] == 1
    assert not (entities_dir / "unresolved-relations.json").exists()

    # 2. Real apply: write changes
    result = migrator.apply_migration(target_relations_file=rel_file, dry_run=False)
    assert result["status"] == "SUCCESS"
    assert result["dryRun"] is False
    assert result["totalScanned"] == 4
    assert result["migratedCanChoosePower"] == 1
    assert result["migratedHasWeakness"] == 1
    assert result["migratedUnresolved"] == 1
    assert result["unmodifiedHasPower"] == 1
    assert result["auditReportSha256"] == report_hash
    assert result["approvalDecisionId"] == "DEC-TEST-001"

    # 3. Check relations.json contents
    migrated_relations = json.loads(rel_file.read_text(encoding="utf-8"))
    assert len(migrated_relations) == 3
    rel_map = {r["id"]: r for r in migrated_relations}
    assert rel_map["rel-01"]["type"] == "CAN_CHOOSE_POWER"
    assert rel_map["rel-02"]["type"] == "HAS_WEAKNESS"
    assert rel_map["rel-03"]["type"] == "HAS_POWER"
    assert "rel-04" not in rel_map

    # 4. Check unresolved-relations.json contents
    unresolved_file = entities_dir / "unresolved-relations.json"
    assert unresolved_file.exists()
    unresolved_relations = json.loads(unresolved_file.read_text(encoding="utf-8"))
    assert len(unresolved_relations) == 1
    unrel = unresolved_relations[0]
    assert unrel["sourceEntityId"] == "creature-lobo"
    assert unrel["candidateRelationType"] == "HAS_POWER"
    assert unrel["candidateTargetEntityId"] == "power-ausente"
    assert unrel["status"] == "UNRESOLVED_MISSING_TARGET"

    # 5. Verify schemas
    validate_payload("relation-collection.schema.json", migrated_relations)
    validate_payload("unresolved-relation-collection.schema.json", unresolved_relations)
