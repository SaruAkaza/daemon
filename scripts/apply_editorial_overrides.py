from __future__ import annotations

from typing import Any

from common import DATA_DIR, ROOT, read_json, write_json

AREAS_DIR = DATA_DIR / "areas"
OVERRIDES_PATH = DATA_DIR / "editorial" / "overrides.json"
REPORT_MD = ROOT / "docs" / "reports" / "editorial-overrides.md"

ALLOWED_ACTIONS = {"replace", "hide", "publish", "tag_review", "quarantine"}


def record_key(record: dict[str, Any]) -> tuple[str, str, str]:
    return (str(record.get("area") or ""), str(record.get("itemType") or ""), str(record.get("id") or ""))


def load_overrides() -> list[dict[str, Any]]:
    payload = read_json(OVERRIDES_PATH, {"records": []})
    records = payload.get("records", []) if isinstance(payload, dict) else []
    valid: list[dict[str, Any]] = []
    for row in records:
        if not isinstance(row, dict):
            continue
        action = row.get("action", "replace")
        if action not in ALLOWED_ACTIONS:
            continue
        if not row.get("id"):
            continue
        valid.append(row)
    return valid


def apply_to_record(item: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    action = override.get("action", "replace")
    item = dict(item)
    if action in {"hide", "quarantine"}:
        item["presentationStatus"] = "quarantine"
        item["qualitySeverity"] = "critical"
        item["qualityStatus"] = "quarentena"
        flags = set(item.get("qualityFlags", []))
        flags.add("manual_quarantine")
        item["qualityFlags"] = sorted(flags)
    if action == "publish":
        item["presentationStatus"] = "public"
        item["qualitySeverity"] = "ok"
        item["qualityStatus"] = "ok"
        item["qualityFlags"] = [flag for flag in item.get("qualityFlags", []) if not str(flag).startswith("manual_")]
    if action == "tag_review":
        item["presentationStatus"] = "public"
        item["qualitySeverity"] = "warning"
        item["qualityStatus"] = "revisar"
        flags = set(item.get("qualityFlags", []))
        flags.add("manual_review")
        item["qualityFlags"] = sorted(flags)
    for field in [
        "name", "summary", "entries", "tags", "category", "subtype", "contentKind", "contentKindLabel",
        "sourceFamily", "sourceFamilyLabel", "page", "pages", "entityRefs", "costText", "requirements",
        "skillsText", "aprimoramentosText", "attributesText", "advantagesText", "disadvantagesText",
    ]:
        if field in override:
            item[field] = override[field]
    item["manualOverride"] = True
    if override.get("note"):
        item["manualOverrideNote"] = override["note"]
    return item


def main() -> None:
    overrides = load_overrides()
    by_id = {str(row["id"]): row for row in overrides}
    changed: list[dict[str, Any]] = []
    if not overrides:
        REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
        REPORT_MD.write_text("# Substituições editoriais manuais\n\nNenhuma substituição manual cadastrada.\n", encoding="utf-8")
        print("No editorial overrides registered.")
        return
    for path in sorted(AREAS_DIR.glob("*.json")):
        payload = read_json(path, {})
        dirty = False
        for collection_name in ("entities", "sourceParts"):
            collection = payload.get(collection_name, []) or []
            item_type = "entity" if collection_name == "entities" else "sourcePart"
            for index, item in enumerate(collection):
                oid = str(item.get("id") or "")
                override = by_id.get(oid)
                if not override:
                    continue
                if override.get("area") and override.get("area") != payload.get("id"):
                    continue
                if override.get("itemType") and override.get("itemType") != item_type:
                    continue
                collection[index] = apply_to_record(item, override)
                dirty = True
                changed.append({"area": payload.get("id"), "itemType": item_type, "id": oid, "action": override.get("action", "replace")})
        if dirty:
            write_json(path, payload)
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Substituições editoriais manuais", "", f"Substituições aplicadas: {len(changed)}", ""]
    for row in changed:
        lines.append(f"- `{row['action']}` em `{row['area']}` / `{row['itemType']}` / `{row['id']}`")
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"Applied {len(changed)} editorial overrides.")


if __name__ == "__main__":
    main()
