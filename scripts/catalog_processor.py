"""catalog_processor — entity type config, claim/quarantine logic, item builders.

EntityTypeConfig drives duplicate detection and quarantine by iteration instead
of 9 parallel if-chains. build_entity_items, build_source_part_items,
enrich_display_quality, and facet_records are the core processing functions.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable

from common import slugify, read_json, write_json
from lock_manager import LockManager
from audit_entity_highlights import quality_flags
from presentation_quality import presentation_status, CRITICAL_PRESENTATION_FLAGS
from editorial_classifier import classify_source_part, content_kind_for_entity
from catalog_loader import (
    BOOKS_DATA_DIR,
    ENTITIES_DIR,
    WORK_DIR,
    AREA_LABELS,
    AREA_KEYWORDS,
    CATEGORY_TO_AREA,
    SOURCE_FAMILY_LABELS,
    normalize_for_search,
    normalize_uppercase_name,
    normalize_display_entries,
    display_source_title,
    source_classification_for,
    source_classification_lookup,
    valid_entity_refs,
)


NEGATIVE_APRIMORAMENTO_COST_RE = re.compile(
    r"(?<![\w+])[-‐-―−]\s*[1-9]\d?\s*(?:pontos?|pts?\.?)\b",
    re.IGNORECASE,
)
APRIMORAMENTO_COST_MARKER_RE = re.compile(
    r"(?<!\w)([-‐-―−]?)\s*[1-9]\d?\s*(?:pontos?|pts?\.?)\s*:",
    re.IGNORECASE,
)

_CONFIDENCE_EXPLICIT = 0.84
_CONFIDENCE_SPECIFIC_AREA_BASE = 0.76
_CONFIDENCE_SPECIFIC_AREA_MAX = 0.92
_CONFIDENCE_SPECIFIC_AREA_STEP = 0.04
_CONFIDENCE_GENERIC_BASE = 0.72
_CONFIDENCE_GENERIC_MAX = 0.88
_CONFIDENCE_CATEGORY_MATCH = 0.78
_CONFIDENCE_FALLBACK = 0.64

_HIGH_CONFIDENCE_AREAS = {"aprimoramentos", "classes", "kits", "racas", "linhagens", "poderes", "magias"}

_OPTIONAL_ENTITY_FIELDS = [
    "subtype", "pages", "costs", "costText", "aprimoramentoCost", "periciaCost",
    "skillsText", "aprimoramentosText", "requirements", "primaryAttributes",
    "requiredSkillsText", "suggestedSkillsText", "classKind", "certificationStatus",
    "certifiedAs", "certifiedArea", "lockedArea", "certificationId", "certificationMethod",
    "kitContext", "classContext", "raceContext", "powerMagicContext", "ritualContext",
    "initialAgeText", "attributesText", "advantagesText", "disadvantagesText",
    "weaknessesText", "tables",
]


@dataclass(frozen=True)
class EntityTypeConfig:
    key: str
    certified_category: str | None  # None = keep entity's own category (regras_base special case)
    claim_fn: Callable[[dict[str, Any], str, str], bool] | None  # None = no quarantine (rituais)
    quarantine_reason: str | None   # None = no quarantine
    work_prefix: str                # prefix for work/ output filenames


def is_aprimoramento_claim(entity: dict[str, Any], category: str, name: str) -> bool:
    tags = {normalize_for_search(str(tag)) for tag in entity.get("tags", [])}
    normalized_name = normalize_for_search(name)
    entity_id = str(entity.get("id") or "")
    return (
        entity.get("subtype") == "aprimoramento"
        or entity_id.startswith("aprimoramento-")
        or category == "character_option"
        or "aprimoramento" in tags
        or "aprimoramentos" in tags
        or "fraqueza" in tags
        or "aprimoramento" in normalized_name
    )


def is_kit_claim(entity: dict[str, Any], category: str, name: str) -> bool:
    tags = {normalize_for_search(str(tag)) for tag in entity.get("tags", [])}
    normalized_name = normalize_for_search(name)
    entity_id = str(entity.get("id") or "")
    return (
        entity.get("subtype") == "kit"
        or entity_id.startswith("kit-")
        or category == "kit_class"
        or "kit" in tags
        or "kits" in tags
        or "kit" in normalized_name
    )


def is_class_claim(entity: dict[str, Any], category: str, name: str) -> bool:
    tags = {normalize_for_search(str(tag)) for tag in entity.get("tags", [])}
    normalized_name = normalize_for_search(name)
    entity_id = str(entity.get("id") or "")
    return (
        entity.get("subtype") == "class"
        or entity_id.startswith("classe-")
        or category == "character_class"
        or "class" in tags
        or "classe" in tags
        or "classes" in tags
        or "classe" in normalized_name
    )


def is_race_claim(entity: dict[str, Any], category: str, name: str) -> bool:
    tags = {normalize_for_search(str(tag)) for tag in entity.get("tags", [])}
    normalized_name = normalize_for_search(name)
    name_terms = set(normalized_name.split())
    entity_id = str(entity.get("id") or "")
    return (
        entity.get("subtype") in {"raca", "race"}
        or entity_id.startswith("raca-")
        or category == "race_lineage"
        or "raca" in tags
        or "racas" in tags
        or "raca" in name_terms
        or "racas" in name_terms
    )


def is_lineage_claim(entity: dict[str, Any], category: str, name: str) -> bool:
    tags = {normalize_for_search(str(tag)) for tag in entity.get("tags", [])}
    normalized_name = normalize_for_search(name)
    name_terms = set(normalized_name.split())
    return (
        entity.get("subtype") in {"linhagem", "lineage"}
        or "linhagem" in tags
        or "linhagens" in tags
        or "linhagem" in name_terms
        or "linhagens" in name_terms
    )


def is_power_claim(entity: dict[str, Any], category: str, name: str) -> bool:
    tags = {normalize_for_search(str(tag)) for tag in entity.get("tags", [])}
    normalized_name = normalize_for_search(name)
    name_terms = set(normalized_name.split())
    entity_id = str(entity.get("id") or "")
    return (
        entity.get("subtype") == "poder"
        or entity_id.startswith("poder-")
        or "poder" in tags
        or "poderes" in tags
        or "superpoder" in tags
        or "superpoderes" in tags
        or "poder" in name_terms
        or "poderes" in name_terms
        or (category == "power_magic" and "magia" not in tags and "magias" not in tags)
    )


def is_magic_claim(entity: dict[str, Any], category: str, name: str) -> bool:
    tags = {normalize_for_search(str(tag)) for tag in entity.get("tags", [])}
    normalized_name = normalize_for_search(name)
    name_terms = set(normalized_name.split())
    entity_id = str(entity.get("id") or "")
    return (
        entity.get("subtype") == "magia"
        or entity_id.startswith("magia-")
        or "magia" in tags
        or "magias" in tags
        or "caminho" in tags
        or "caminhos" in tags
        or "magia" in name_terms
        or "magias" in name_terms
        or (category == "power_magic" and ("magia" in tags or "magias" in tags))
    )


def is_regras_base_claim(entity: dict[str, Any], category: str, name: str) -> bool:
    if category not in {"core_rule", "attribute_skill", "combat"}:
        return False
    tags = {normalize_for_search(str(tag)) for tag in entity.get("tags", [])}
    entity_id = str(entity.get("id") or "")
    return (
        entity_id.startswith(("regra-", "core-rule-", "combat-", "pericia-", "atributo-"))
        or bool(tags & {"regra", "regras", "regras basicas", "sistema", "atributo", "atributos", "pericia", "pericias", "combate"})
        or normalize_for_search(name) in {"regra", "regras", "sistema", "atributos", "pericias", "combate"}
    )


# Keyed dict so lookup is O(1); order in _*_ORDER lists governs priority.
ENTITY_TYPE_CONFIGS: dict[str, EntityTypeConfig] = {
    "aprimoramentos": EntityTypeConfig("aprimoramentos", "character_option", is_aprimoramento_claim, "uncertified_aprimoramento_claim", "aprimoramentos"),
    "kits":           EntityTypeConfig("kits",           "kit_class",        is_kit_claim,           "uncertified_kit_claim",           "kits"),
    "classes":        EntityTypeConfig("classes",        "character_class",  is_class_claim,         "uncertified_class_claim",         "classes"),
    "racas":          EntityTypeConfig("racas",          "race_lineage",     is_race_claim,          "uncertified_race_claim",          "racas"),
    "linhagens":      EntityTypeConfig("linhagens",      "race_lineage",     is_lineage_claim,       "uncertified_lineage_claim",       "linhagens"),
    "poderes":        EntityTypeConfig("poderes",        "power_magic",      is_power_claim,         "uncertified_power_claim",         "poderes"),
    "magias":         EntityTypeConfig("magias",         "power_magic",      is_magic_claim,         "uncertified_magic_claim",         "magias"),
    "rituais":        EntityTypeConfig("rituais",        "ritual_spell",     None,                   None,                              "rituais"),
    "regras_base":    EntityTypeConfig("regras_base",    None,               is_regras_base_claim,   "uncertified_regras_base_claim",   "regras-base"),
}

# Duplicate detection: first match wins. racas before linhagens (matches original).
_DUPLICATE_CHECK_ORDER = ["aprimoramentos", "kits", "classes", "racas", "linhagens", "poderes", "magias", "rituais", "regras_base"]

# Quarantine claim: first match wins. linhagens before racas (matches original).
_QUARANTINE_CLAIM_ORDER = ["aprimoramentos", "kits", "classes", "linhagens", "racas", "poderes", "magias", "regras_base"]


def aprimoramento_subgroup(entity: dict[str, Any]) -> tuple[str, str, str]:
    searchable = " ".join(
        str(value)
        for value in [
            entity.get("name", ""),
            entity.get("costText", ""),
            " ".join(str(cost) for cost in entity.get("costs", []) if cost),
            " ".join(str(entry) for entry in entity.get("entries", []) if entry),
        ]
        if value
    )
    first_marker = APRIMORAMENTO_COST_MARKER_RE.search(searchable)
    if first_marker:
        marker_sign = first_marker.group(1)
        if marker_sign:
            return "aprimoramentos_negativos", "Aprimoramentos Negativos", "aprimoramento-negativo"
        return "aprimoramentos_positivos", "Aprimoramentos Positivos", "aprimoramento-positivo"
    if NEGATIVE_APRIMORAMENTO_COST_RE.search(searchable):
        return "aprimoramentos_negativos", "Aprimoramentos Negativos", "aprimoramento-negativo"
    return "aprimoramentos_positivos", "Aprimoramentos Positivos", "aprimoramento-positivo"


def infer_area(category: str, name: str, summary: str, source_title: str) -> tuple[str, float, list[str]]:
    explicit_area = CATEGORY_TO_AREA.get(category)
    if explicit_area and category != "source":
        return explicit_area, _CONFIDENCE_EXPLICIT, [explicit_area]

    haystack = normalize_for_search(" ".join([name, summary, source_title]))
    matches: list[str] = []
    for area, keywords in AREA_KEYWORDS:
        normalized_keywords = [normalize_for_search(keyword) for keyword in keywords]
        hit_count = sum(1 for keyword in normalized_keywords if keyword in haystack)
        if hit_count:
            matches.append(area)
            if area in _HIGH_CONFIDENCE_AREAS:
                return area, min(_CONFIDENCE_SPECIFIC_AREA_MAX, _CONFIDENCE_SPECIFIC_AREA_BASE + hit_count * _CONFIDENCE_SPECIFIC_AREA_STEP), matches
            if area != CATEGORY_TO_AREA.get(category):
                return area, min(_CONFIDENCE_GENERIC_MAX, _CONFIDENCE_GENERIC_BASE + hit_count * _CONFIDENCE_SPECIFIC_AREA_STEP), matches

    area = CATEGORY_TO_AREA.get(category, "fontes")
    confidence = _CONFIDENCE_CATEGORY_MATCH if area != "fontes" else _CONFIDENCE_FALLBACK
    return area, confidence, matches


def area_for_entity(entity: dict[str, Any], category: str, name: str, summary: str, source_title: str) -> tuple[str, float, list[str]]:
    subtype = entity.get("subtype")
    if subtype == "aprimoramento":
        return "aprimoramentos", 0.9, ["aprimoramentos"]
    if subtype in {"kit", "class"}:
        return "kits" if subtype == "kit" else "classes", 0.9, [subtype]
    if subtype in {"raca", "race"}:
        return "racas", 0.9, ["racas"]
    if subtype in {"linhagem", "lineage"}:
        return "linhagens", 0.9, ["linhagens"]
    if subtype == "poder":
        return "poderes", 0.9, ["poderes"]
    if subtype == "magia":
        return "magias", 0.9, ["magias"]
    area, confidence, matches = infer_area(category, name, summary, source_title)
    if area in {"classes", "kits"} and category != "kit_class":
        return CATEGORY_TO_AREA.get(category, "fontes"), 0.78, matches
    if area == "racas" and category != "race_lineage":
        return CATEGORY_TO_AREA.get(category, "fontes"), 0.78, matches
    if area == "linhagens" and category != "race_lineage":
        return CATEGORY_TO_AREA.get(category, "fontes"), 0.78, matches
    if area in {"poderes", "magias"} and category != "power_magic":
        return CATEGORY_TO_AREA.get(category, "fontes"), 0.78, matches
    return area, confidence, matches


def catalog_sort_key(item: dict[str, Any]) -> tuple[str, str, int, str]:
    return (
        slugify(str(item.get("name") or "")),
        slugify(str(item.get("sourceTitle") or item.get("source") or "")),
        int(item.get("page") or 0),
        str(item.get("id") or ""),
    )


def page_value(part: dict[str, Any]) -> int | None:
    pages = part.get("pages") or []
    if pages and isinstance(pages[0], int):
        return pages[0]
    page = part.get("page")
    return page if isinstance(page, int) else None


def build_entity_items(
    source_ids: set[str],
    source_lookup: dict[str, dict[str, Any]],
    classifications: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    lm = LockManager()
    quarantined: dict[str, list[dict[str, Any]]] = {key: [] for key in ENTITY_TYPE_CONFIGS}
    duplicates: dict[str, list[dict[str, Any]]] = {key: [] for key in ENTITY_TYPE_CONFIGS}

    for path in sorted(ENTITIES_DIR.glob("*.json")):
        if path.name == "source.json":
            continue
        category_entities = read_json(path, [])
        if not isinstance(category_entities, list):
            continue
        for entity in category_entities:
            source_id = entity.get("source")
            if source_id not in source_ids:
                continue
            category = entity.get("category") or CATEGORY_TO_AREA.get(path.stem, "source")
            name = entity.get("name", entity.get("id", ""))
            entity_id = entity.get("id")
            source_name_key = (source_id, slugify(str(name)))
            is_structured_docx = entity.get("extractionMethod") == "docx-structured-import-v1"

            # Duplicate detection: first match in _DUPLICATE_CHECK_ORDER wins.
            skip = False
            for key in _DUPLICATE_CHECK_ORDER:
                _, by_source_name = lm.load(key)
                if source_name_key in by_source_name and not lm.is_certified(key, entity_id):
                    duplicates[key].append({
                        "id": entity_id,
                        "name": name,
                        "source": source_id,
                        "category": category,
                        "subtype": entity.get("subtype"),
                        "entityFile": path.name,
                        "duplicateOf": by_source_name[source_name_key]["id"],
                    })
                    skip = True
                    break
            if skip:
                continue

            # Quarantine: only when entity is not certified in any type.
            certified_keys = {key for key in ENTITY_TYPE_CONFIGS if lm.is_certified(key, entity_id)}
            if not is_structured_docx and not certified_keys:
                for key in _QUARANTINE_CLAIM_ORDER:
                    cfg = ENTITY_TYPE_CONFIGS[key]
                    if cfg.claim_fn and cfg.quarantine_reason and cfg.claim_fn(entity, category, str(name)):
                        quarantined[key].append({
                            "id": entity_id,
                            "name": name,
                            "source": source_id,
                            "category": category,
                            "subtype": entity.get("subtype"),
                            "entityFile": path.name,
                            "reason": cfg.quarantine_reason,
                        })
                        skip = True
                        break
            if skip:
                continue

            # Category override: iterate all types; last certified wins (preserves original behavior).
            for key in _DUPLICATE_CHECK_ORDER:
                if key in certified_keys:
                    cfg = ENTITY_TYPE_CONFIGS[key]
                    if cfg.certified_category is not None:
                        category = cfg.certified_category
                    else:
                        # regras_base: keep entity's own valid category, else fall back to core_rule.
                        category = (
                            entity.get("category")
                            if entity.get("category") in {"core_rule", "attribute_skill", "combat"}
                            else "core_rule"
                        )

            entries = entity.get("entries") or []
            display_name = normalize_uppercase_name(str(name))
            display_entries = normalize_display_entries(entries)
            summary = " ".join(entry for entry in entries if isinstance(entry, str))
            source_title = display_source_title(source_id, source_lookup)
            classification = source_classification_for(source_id, classifications, source_title)

            # Area/confidence: first certified key in _DUPLICATE_CHECK_ORDER wins.
            area: str
            confidence: float
            matched_areas: list[str]
            for key in _DUPLICATE_CHECK_ORDER:
                if key in certified_keys:
                    area, confidence, matched_areas = key, 1.0, [key, "certificado"]
                    break
            else:
                area, confidence, matched_areas = area_for_entity(entity, category, str(name), summary, source_title)

            # DOCX editorial area takes precedence over automatic inference.
            if entity.get("extractionMethod") == "docx-structured-import-v1" and entity.get("area") in AREA_LABELS:
                area = str(entity["area"])
                confidence = max(confidence, float(entity.get("confidence", confidence)))

            subgroup: str | None = None
            subgroup_label: str | None = None
            subgroup_tag: str | None = None
            if area == "aprimoramentos":
                subgroup, subgroup_label, subgroup_tag = aprimoramento_subgroup(entity)
                matched_areas = [*matched_areas, subgroup_tag]
            elif area in {"kits", "classes", "racas", "linhagens", "poderes", "magias", "rituais"}:
                family_id = classification.get("family", {}).get("id") or ""
                family_label = classification.get("family", {}).get("label") or ""
                if family_id and family_label:
                    subgroup = family_id
                    subgroup_label = family_label
                    subgroup_tag = f"family-{family_id}"

            item: dict[str, Any] = {
                "id": entity_id,
                "name": display_name,
                "area": area,
                "category": category,
                "source": source_id,
                "sourceTitle": source_title,
                "page": entity.get("page"),
                "entries": display_entries,
                "tags": sorted(set([area, category, *entity.get("tags", []), *matched_areas])),
                "confidence": round(float(entity.get("confidence", confidence)), 2),
                "extractionMethod": entity.get("extractionMethod", "entity-area-pass-1"),
                "sourceKind": classification["kind"],
                "sourceKindLabel": classification["label"],
                "officialSource": classification["kind"] == "official",
                "sourceFamily": classification["family"]["id"],
                "sourceFamilyLabel": classification["family"]["label"],
            }
            if subgroup and subgroup_label:
                item["subgroup"] = subgroup
                item["subgroupLabel"] = subgroup_label
            item.update(content_kind_for_entity(item))
            for field in _OPTIONAL_ENTITY_FIELDS:
                if field in entity:
                    item[field] = entity[field]
            items.append(item)

    WORK_DIR.mkdir(parents=True, exist_ok=True)
    for key, cfg in ENTITY_TYPE_CONFIGS.items():
        if cfg.quarantine_reason:
            write_json(WORK_DIR / f"{cfg.work_prefix}-quarantine.json", quarantined[key])
        write_json(WORK_DIR / f"{cfg.work_prefix}-duplicate-blocks.json", duplicates[key])
    return items


def build_source_part_items(
    source_ids: list[str],
    source_lookup: dict[str, dict[str, Any]],
    known_entity_ids: set[str],
    classifications: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for source_id in source_ids:
        book = read_json(BOOKS_DATA_DIR / f"{source_id}.json", {})
        source_title = display_source_title(source_id, source_lookup, book)
        for part in book.get("parts", []):
            name = part.get("name") or part.get("id") or source_title
            category = part.get("category") or "source"
            summary = part.get("summary") or ""
            area, confidence, matched_areas = infer_area(category, name, summary, source_title)
            classification = source_classification_for(source_id, classifications, source_title)
            item = {
                "id": f"{source_id}--{slugify(part.get('id') or name)}",
                "name": name,
                "area": area,
                "category": category,
                "source": source_id,
                "sourceTitle": source_title,
                "pages": part.get("pages", []),
                "page": page_value(part),
                "summary": summary,
                "entityRefs": valid_entity_refs(part.get("entityRefs", []), known_entity_ids),
                "tags": sorted(set([area, category, *matched_areas])),
                "confidence": round(confidence, 2),
                "extractionMethod": "book-part-area-pass-1",
                "sourceKind": classification["kind"],
                "sourceKindLabel": classification["label"],
                "officialSource": classification["kind"] == "official",
                "sourceFamily": classification["family"]["id"],
                "sourceFamilyLabel": classification["family"]["label"],
            }
            item.update(classify_source_part(item, source_title))
            items.append(item)
    return items


def build_source_entities(source_ids: list[str], source_lookup: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    classifications = source_classification_lookup()
    source_entities_payload = read_json(ENTITIES_DIR / "source.json", [])
    source_entities_by_source = {
        str(entity.get("source")): entity
        for entity in source_entities_payload
        if isinstance(entity, dict) and entity.get("source")
    }
    items: list[dict[str, Any]] = []
    for source_id in source_ids:
        book = read_json(BOOKS_DATA_DIR / f"{source_id}.json", {})
        source_title = display_source_title(source_id, source_lookup, book)
        source_entity = source_entities_by_source.get(source_id, {})
        classification = source_classification_for(source_id, classifications, source_title)
        entries = source_entity.get("entries") or [
            f"Fonte processada para consulta digital: {source_title}.",
        ]
        tags = set(source_entity.get("tags", []))
        tags.update(["fontes", "source", classification["kind"]])
        item = {
            "id": f"source-{source_id}",
            "name": source_title,
            "area": "fontes",
            "category": "source",
            "source": source_id,
            "sourceTitle": source_title,
            "page": source_entity.get("page") or 1,
            "entries": normalize_display_entries(entries),
            "tags": sorted(tags),
            "confidence": round(float(source_entity.get("confidence", 1 if classification["kind"] == "official" else 0.8)), 2),
            "extractionMethod": "source-catalog-pass-1",
            "sourceKind": classification["kind"],
            "sourceKindLabel": classification["label"],
            "officialSource": classification["kind"] == "official",
            "sourceFamily": classification["family"]["id"],
            "sourceFamilyLabel": classification["family"]["label"],
        }
        if classification.get("officialName"):
            item["officialName"] = classification["officialName"]
        if classification.get("classificationNote"):
            item["classificationNote"] = classification["classificationNote"]
        item.update(content_kind_for_entity(item))
        items.append(item)
    return items


def enrich_display_quality(item: dict[str, Any], item_type: str) -> dict[str, Any]:
    if item_type == "entity" and (item.get("area") == "fontes" or item.get("category") == "source"):
        item.setdefault("qualityStatus", "ok")
        item.setdefault("qualityFlags", [])
        item.setdefault("qualitySeverity", "ok")
        item.setdefault("presentationStatus", "public")
        return item
    flags = quality_flags({**item, "itemType": item_type})
    flags = sorted(set([*flags, *item.get("editorialFlags", [])]))
    item["qualityFlags"] = flags
    item["qualitySeverity"] = "critical" if set(flags) & CRITICAL_PRESENTATION_FLAGS else ("warning" if flags else "ok")
    status_hint = item.get("presentationStatusHint")
    if item_type == "sourcePart" and flags:
        item["presentationStatus"] = "quarantine"
    else:
        item["presentationStatus"] = "quarantine" if status_hint == "quarantine" else presentation_status({**item, "itemType": item_type}, flags)
    item["qualityStatus"] = "quarentena" if item["presentationStatus"] == "quarantine" else ("revisar" if flags else "ok")
    return item


def facet_records(items: list[dict[str, Any]]) -> dict[str, Any]:
    sources: dict[str, dict[str, Any]] = {}
    categories: dict[str, int] = {}
    subtypes: dict[str, int] = {}
    source_kinds: dict[str, dict[str, Any]] = {}
    source_families: dict[str, dict[str, Any]] = {}
    areas: dict[str, int] = {}
    for item in items:
        source_id = str(item.get("source") or "")
        if source_id:
            source = sources.setdefault(
                source_id,
                {
                    "id": source_id,
                    "title": item.get("sourceTitle") or source_id,
                    "sourceKind": item.get("sourceKind") or "supplement",
                    "sourceKindLabel": item.get("sourceKindLabel") or "Suplemento de jogo/campanha",
                    "officialSource": bool(item.get("officialSource")),
                    "sourceFamily": item.get("sourceFamily") or "supplement_misc",
                    "sourceFamilyLabel": item.get("sourceFamilyLabel") or SOURCE_FAMILY_LABELS["supplement_misc"],
                    "count": 0,
                },
            )
            source["count"] += 1
        category = item.get("category")
        if category:
            categories[str(category)] = categories.get(str(category), 0) + 1
        subtype = item.get("contentKind") or item.get("subtype") or item.get("itemType")
        if subtype:
            subtypes[str(subtype)] = subtypes.get(str(subtype), 0) + 1
        kind = item.get("sourceKind") or "supplement"
        kind_record = source_kinds.setdefault(
            str(kind),
            {
                "id": str(kind),
                "label": item.get("sourceKindLabel") or ("Livro oficial" if kind == "official" else "Suplemento de jogo/campanha"),
                "count": 0,
            },
        )
        kind_record["count"] += 1
        family = item.get("sourceFamily") or "supplement_misc"
        family_record = source_families.setdefault(
            str(family),
            {
                "id": str(family),
                "label": item.get("sourceFamilyLabel") or SOURCE_FAMILY_LABELS.get(str(family), str(family)),
                "count": 0,
            },
        )
        family_record["count"] += 1
        area = item.get("area")
        if area:
            areas[str(area)] = areas.get(str(area), 0) + 1
    return {
        "sources": sorted(sources.values(), key=lambda row: (not row.get("officialSource"), slugify(str(row.get("title") or "")))),
        "categories": [{"id": key, "count": value} for key, value in sorted(categories.items())],
        "subtypes": [{"id": key, "count": value} for key, value in sorted(subtypes.items())],
        "sourceKinds": sorted(source_kinds.values(), key=lambda row: row["id"]),
        "sourceFamilies": sorted(source_families.values(), key=lambda row: row["label"]),
        "areas": [{"id": key, "count": value} for key, value in sorted(areas.items())],
    }
