from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]


def test_relation_documentation_contains_canonical_ontology_v2():
    relation_types_path = ROOT / "docs" / "context" / "domain" / "relation-types.md"
    cataloging_rules_path = ROOT / "docs" / "reference" / "cataloging-rules.md"
    data_model_path = ROOT / "docs" / "reference" / "data-model.md"
    relations_agent_path = ROOT / "docs" / "agents" / "relations-agent.md"

    for path in (
        relation_types_path,
        cataloging_rules_path,
        data_model_path,
        relations_agent_path,
    ):
        assert path.exists(), f"Expected documentation file does not exist: {path}"

    rel_content = relation_types_path.read_text(encoding="utf-8")
    cat_content = cataloging_rules_path.read_text(encoding="utf-8")
    model_content = data_model_path.read_text(encoding="utf-8")
    agent_content = relations_agent_path.read_text(encoding="utf-8")

    # HAS_POWER canonical definition
    has_power_def = "the source entity actually possesses the target power."
    assert has_power_def in rel_content, "relation-types.md must contain exact HAS_POWER canonical definition"
    assert "actual possession" in rel_content.lower()

    # CAN_CHOOSE_POWER canonical definition
    can_choose_def = "the source entity/template is explicitly allowed to select the target power as a build or configuration option."
    assert can_choose_def in rel_content, "relation-types.md must contain exact CAN_CHOOSE_POWER canonical definition"

    # HAS_WEAKNESS canonical definition
    has_weakness_def = "the source entity possesses the target weakness, vulnerability, or limitation."
    assert has_weakness_def in rel_content, "relation-types.md must contain exact HAS_WEAKNESS canonical definition"

    # CAN_CHOOSE_WEAKNESS rejection under YAGNI
    assert "CAN_CHOOSE_WEAKNESS" in rel_content
    assert "YAGNI" in rel_content

    # Ontology Versioning
    assert "relations-v1" in rel_content
    assert "relations-v2" in rel_content
    assert "historical" in rel_content.lower() or "read-only" in rel_content.lower()
    assert "mandatory for new execution" in rel_content.lower() or "obrigatório para novas execuções" in rel_content.lower()

    # Canonical Compatibility Authority
    assert "schemas/relation-compatibility-v2.json" in rel_content
    assert "markdown = explanatory only" in rel_content or "explanatory only" in rel_content

    # Cataloging Rules checks
    assert "CAN_CHOOSE_POWER" in cat_content
    assert "HAS_POWER" in cat_content
    assert "HAS_WEAKNESS" in cat_content

    # Data Model checks
    assert "relations-v2" in model_content
    assert "CAN_CHOOSE_POWER" in model_content
    assert "HAS_WEAKNESS" in model_content
    assert "relation-collection.schema.json" in model_content

    # Relations Agent checks
    assert "CAN_CHOOSE_POWER" in agent_content
    assert "HAS_WEAKNESS" in agent_content
    assert "relations-v2" in agent_content


def test_adr_0004_exists_and_accepted():
    adr_path = ROOT / "docs" / "context" / "decisions" / "ADR-0004-relations-v2-ontology-and-contracts.md"
    assert adr_path.exists(), f"ADR-0004 file missing: {adr_path}"

    content = adr_path.read_text(encoding="utf-8")

    # Check Title
    assert (
        "ADR-0004: Relations V2 Ontology, Collection Contract, and Compatibility Governance" in content
        or "ADR-0004 — Relations V2 Ontology, Collection Contract, and Compatibility Governance" in content
    ), "ADR-0004 title does not match canonical name"

    # Check Status: Accepted
    status_match = re.search(r"##\s*Status\s*\n+([A-Za-z]+)", content)
    assert status_match is not None, "ADR-0004 missing Status section"
    assert status_match.group(1).strip() == "Accepted", "ADR-0004 status must be Accepted"

    # Canonical ontology definitions in ADR-0004
    assert "the source entity actually possesses the target power." in content
    assert "the source entity/template is explicitly allowed to select the target power as a build or configuration option." in content
    assert "the source entity possesses the target weakness, vulnerability, or limitation." in content
    assert "CAN_CHOOSE_WEAKNESS" in content
    assert "YAGNI" in content

    # Authority and Versioning
    assert "schemas/relation-compatibility-v2.json" in content
    assert "markdown = explanatory only" in content
    assert "relations-v1" in content
    assert "relations-v2" in content
    assert "relation-collection.schema.json" in content
