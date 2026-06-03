"""build_area_catalog — orchestration entry point.

Loads sources, delegates processing to catalog_processor, writes area JSON
files and the summary report. All heavy logic lives in catalog_loader and
catalog_processor; this module only wires them together and handles I/O.
"""
from __future__ import annotations

from typing import Any

from common import INDEX_DIR, ROOT, write_json
from catalog_loader import (
    AREA_LABELS,
    AREAS_DIR,
    all_entity_ids,
    current_source_lookup,
    ready_source_ids,
    source_classification_lookup,
)
from catalog_processor import (
    build_entity_items,
    build_source_entities,
    build_source_part_items,
    catalog_sort_key,
    enrich_display_quality,
    facet_records,
)


def write_area_files(source_ids: list[str], part_items: list[dict[str, Any]], entity_items: list[dict[str, Any]]) -> dict[str, Any]:
    AREAS_DIR.mkdir(parents=True, exist_ok=True)
    expected_area_files = {f"{area}.json" for area in AREA_LABELS}
    for stale_path in AREAS_DIR.glob("*.json"):
        if stale_path.name not in expected_area_files:
            stale_path.unlink()

    by_area: dict[str, dict[str, list[dict[str, Any]]]] = {
        area: {"entities": [], "sourceParts": []} for area in AREA_LABELS
    }
    for item in part_items:
        if item["area"] in {"regras_base", "aprimoramentos", "kits", "classes", "racas", "linhagens", "poderes", "magias", "rituais"}:
            continue
        by_area.setdefault(item["area"], {"entities": [], "sourceParts": []})["sourceParts"].append(enrich_display_quality(item, "sourcePart"))
    for item in entity_items:
        by_area.setdefault(item["area"], {"entities": [], "sourceParts": []})["entities"].append(enrich_display_quality(item, "entity"))

    area_summaries: list[dict[str, Any]] = []
    for area in AREA_LABELS:
        subgroup_counts: dict[str, dict[str, Any]] = {}
        for item in by_area[area]["entities"]:
            subgroup = item.get("subgroup")
            if not subgroup:
                continue
            current = subgroup_counts.setdefault(
                subgroup,
                {"id": subgroup, "name": item.get("subgroupLabel", subgroup), "entityCount": 0},
            )
            current["entityCount"] += 1
        all_area_items = [*by_area[area]["entities"], *by_area[area]["sourceParts"]]
        payload = {
            "version": 1,
            "id": area,
            "name": AREA_LABELS[area],
            "readySourceCount": len(source_ids),
            "entityCount": len(by_area[area]["entities"]),
            "sourcePartCount": len(by_area[area]["sourceParts"]),
            "subgroups": sorted(subgroup_counts.values(), key=lambda item: item["name"]),
            "filters": facet_records(all_area_items),
            "entities": sorted(by_area[area]["entities"], key=catalog_sort_key),
            "sourceParts": sorted(by_area[area]["sourceParts"], key=lambda item: (item.get("sourceTitle") or "", item.get("page") or 0, item.get("name") or "")),
        }
        write_json(AREAS_DIR / f"{area}.json", payload)
        area_summaries.append(
            {
                "id": area,
                "name": AREA_LABELS[area],
                "entityCount": payload["entityCount"],
                "sourcePartCount": payload["sourcePartCount"],
            }
        )

    summary = {
        "version": 1,
        "readySourceCount": len(source_ids),
        "areaCount": len(AREA_LABELS),
        "entityCount": len(entity_items),
        "sourcePartCount": len(part_items),
        "areas": area_summaries,
        "readySources": source_ids,
        "filters": facet_records([*entity_items, *part_items]),
    }
    write_json(INDEX_DIR / "area-summary.json", summary)
    return summary


def write_report(summary: dict[str, Any]) -> None:
    lines = [
        "# Area catalog pass 001",
        "",
        "Initial navigation/population layer for the sources marked as ready to proceed.",
        "",
        f"- Ready sources: {summary['readySourceCount']}",
        f"- Areas: {summary['areaCount']}",
        f"- Curated entities included: {summary['entityCount']}",
        f"- Book parts indexed: {summary['sourcePartCount']}",
        "",
        "## Areas",
        "",
        "| Area | Entities | Source parts |",
        "| --- | ---: | ---: |",
    ]
    for area in summary["areas"]:
        lines.append(f"| {area['name']} (`{area['id']}`) | {area['entityCount']} | {area['sourcePartCount']} |")

    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- This is a pass-1 catalog based on existing book parts plus curated entities already extracted.",
            "- Duplicate IDs are resolved to their canonical source before the ready-source list is built.",
            "- The next pass should keep splitting high-value source parts into individual mechanical records, including pericias and remaining uncategorized rules.",
            "",
        ]
    )
    report_dir = ROOT / "docs" / "reports" / "catalog"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "area-catalog-pass-001.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    source_lookup = current_source_lookup()
    source_ids = ready_source_ids()
    known_entity_ids = all_entity_ids()
    classifications = source_classification_lookup()
    part_items = build_source_part_items(source_ids, source_lookup, known_entity_ids, classifications)
    entity_items = build_entity_items(set(source_ids), source_lookup, classifications)
    source_entity_items = build_source_entities(source_ids, source_lookup)
    summary = write_area_files(source_ids, part_items, [*entity_items, *source_entity_items])
    write_report(summary)
    print(
        f"Area catalog built: {summary['readySourceCount']} sources, "
        f"{summary['sourcePartCount']} source parts, {summary['entityCount']} entities."
    )


if __name__ == "__main__":
    main()
