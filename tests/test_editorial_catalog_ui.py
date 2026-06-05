from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_source_family_facets_are_published() -> None:
    summary = read_json(ROOT / "data" / "index" / "area-summary.json")
    families = summary["filters"].get("sourceFamilies", [])
    family_ids = {family["id"] for family in families}

    assert "official_core" in family_ids
    assert "supplement_misc" in family_ids
    assert len(families) >= 5


def test_navigation_areas_are_user_facing_groups() -> None:
    summary = read_json(ROOT / "data" / "index" / "area-summary.json")
    area_ids = [area["id"] for area in summary["areas"]]

    assert "regras_base" in area_ids
    assert "fontes" not in area_ids
    assert "atributos_pericias" not in area_ids
    assert "combate" not in area_ids


def test_docs_data_matches_built_catalog() -> None:
    source_summary = read_json(ROOT / "data" / "index" / "area-summary.json")
    docs_summary = read_json(ROOT / "docs" / "assets" / "data" / "area-summary.json")

    assert docs_summary["readySourceCount"] == source_summary["readySourceCount"]
    assert docs_summary["sourcePartCount"] == source_summary["sourcePartCount"]
    assert docs_summary["entityCount"] == source_summary["entityCount"]


def test_regras_base_is_certified_and_not_raw_source_parts() -> None:
    area = read_json(ROOT / "data" / "areas" / "regras_base.json")

    assert area["entityCount"] >= 100
    assert area["sourcePartCount"] == 0
    assert {entity["lockedArea"] for entity in area["entities"]} == {"regras_base"}
    assert {entity["category"] for entity in area["entities"]} <= {"core_rule", "attribute_skill", "combat"}


def test_ui_has_current_navigation_and_filter_controls() -> None:
    app = (ROOT / "docs" / "assets" / "app.js").read_text(encoding="utf-8")
    html = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")

    assert "brandHomeButton" in html
    assert "DAEMON/TREVAS" in html
    assert "areaFilter" in html
    assert "filterOpenButton" in html
    assert "categoryFilterButton" in html
    assert "globalFilters" in app
    assert "function globalScopedItems" in app
    assert "openFilters(\"global\")" in app
    assert "openFilters(\"category\")" in app
