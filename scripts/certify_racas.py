from __future__ import annotations

import hashlib
import re
from collections import Counter
from typing import Any

from common import DATA_DIR, INDEX_DIR, ROOT, slugify, read_json, write_json
from granular_validation import certification_quality_failure


ENTITIES_PATH = DATA_DIR / "entities" / "race_lineage_granular.json"
LOCK_PATH = INDEX_DIR / "racas-certified-lock.json"
LINEAGES_LOCK_PATH = INDEX_DIR / "linhagens-certified-lock.json"
REJECTED_PATH = DATA_DIR / "work" / "racas-certification-rejected.json"
REPORT_PATH = ROOT / "docs" / "reports" / "certification" / "racas-certification.md"

MECHANICAL_RACE_RE = re.compile(
    r"\bCusto\s*:|\bIdade Inicial\s*:|\bAtributos\s*:|\bVantagens\s*:|\bDesvantagens\s*:",
    re.IGNORECASE,
)
KITLIKE_RE = re.compile(
    r"\bPer[iíÃ­]cias?\s*:.*\bAprimoramentos?\s*:.*\bPontos (?:Her[oóÃ³]icos|de F[eéÃ©]|de Magia)\b",
    re.IGNORECASE | re.DOTALL,
)
RACE_SIGNAL_RE = re.compile(
    r"\bra[cçÃ§]as?\b|\blinhagens?\b|\besp[éeÃ©]cies?\b|\bdescendentes?\b|\bfilhos?\b|\bsangue de\b|"
    r"\bh[íiÃ­]bridos?\b|\bvampiros?\b|\blobisomens?\b|\bfadas?\b|\byoukais?\b|"
    r"\bghou?ls?\b|\brakshasas?\b|\bdrag[õoÃµ]es?\b|\bimortais?\b|\bferas?\b|\bmetamorfos?\b|"
    r"\bdem[ôoÃ´]nios?\b|\besp[íiÃ­]ritos?\b|\borigem e hist[oóÃ³]ria\b|\bcaracter[íiÃ­]sticas\b",
    re.IGNORECASE,
)
CONTEXT_RE = re.compile(r"race_lineage|dedicated-source|text-race-term|manual-race-lineage|source-specific-race-lineage", re.IGNORECASE)

BAD_NAMES = {
    "agradecimentos",
    "aprimoramentos",
    "atributos",
    "caracteristicas",
    "características",
    "consideracoes",
    "considerações",
    "daemon medieval",
    "desvantagens",
    "fraqueza",
    "fraquezas",
    "geralmente",
    "historia",
    "história",
    "idade inicial",
    "introduo",
    "introducao",
    "introdução",
    "organizacao",
    "organização",
    "pagina inicial",
    "poderes",
    "racas",
    "racas vampiricas de vampiros mitologicos",
    "raças",
    "sistema",
    "vantagens",
}


def has_strong_mechanical_race(body: str) -> bool:
    return (
        bool(re.search(r"\bIdade Inicial\s*:", body, flags=re.IGNORECASE))
        and bool(re.search(r"\bAtributos\s*:", body, flags=re.IGNORECASE))
        and bool(re.search(r"\bCusto\s*:", body, flags=re.IGNORECASE))
        and bool(re.search(r"\b(?:Vantagens|Desvantagens)\s*:", body, flags=re.IGNORECASE))
    )


def lock_source_names(path_name: str) -> set[tuple[str, str]]:
    lock = read_json(INDEX_DIR / path_name, {"records": []})
    return {
        (record["source"], record["nameKey"])
        for record in lock.get("records", [])
        if record.get("source") and record.get("nameKey")
    }


def body_text(entity: dict[str, Any]) -> str:
    entries = entity.get("entries") or []
    return "\n".join(entry for entry in entries if isinstance(entry, str))


def content_key(entity: dict[str, Any]) -> tuple[str, str]:
    body = re.sub(r"\s+", " ", body_text(entity)).strip().lower()
    digest = hashlib.sha1(body.encode("utf-8", errors="ignore")).hexdigest()
    return (slugify(str(entity.get("name") or "")), digest)


def certification_failure(
    entity: dict[str, Any],
    aprimoramento_names: set[tuple[str, str]],
    kit_names: set[tuple[str, str]],
    class_names: set[tuple[str, str]],
) -> str | None:
    name = str(entity.get("name") or "").strip()
    name_key = slugify(name)
    source_name = (entity.get("source"), name_key)
    body = body_text(entity)
    context = str(entity.get("raceContext") or "")
    subtype = entity.get("subtype")

    if source_name in aprimoramento_names:
        return "locked_as_aprimoramento"
    if source_name in kit_names:
        return "locked_as_kit"
    if source_name in class_names:
        return "locked_as_class"
    if entity.get("category") != "race_lineage":
        return "category_is_not_race_lineage"
    if subtype not in {"raca", "linhagem"}:
        return "subtype_is_not_raca_or_linhagem"
    if not str(entity.get("id") or "").startswith("raca-"):
        return "id_is_not_raca"
    if not CONTEXT_RE.search(context):
        return "no_explicit_race_context"
    if not name or name_key.replace("-", " ") in BAD_NAMES:
        return "name_is_section_or_empty"
    if any(char in name for char in [";", ":", "?", "!"]):
        return "name_has_sentence_punctuation"
    if len(body) < 45:
        return "entry_too_short"
    if quality_failure := certification_quality_failure(entity):
        return quality_failure

    strong_mechanical_race = has_strong_mechanical_race(body)
    if KITLIKE_RE.search(body) and not strong_mechanical_race:
        return "looks_like_kit_or_class"
    if subtype == "raca":
        if strong_mechanical_race:
            return None
        if "manual-race-lineage" in context and RACE_SIGNAL_RE.search(body):
            return None
        return "no_mechanical_race_signal"
    if subtype == "linhagem":
        if len(body) < 90:
            return "lineage_entry_too_short"
        if strong_mechanical_race:
            return None
        if "manual-race-lineage" in context and RACE_SIGNAL_RE.search(f"{name} {body}"):
            return None
        if "source-specific-race-lineage" in context and RACE_SIGNAL_RE.search(f"{name} {body}"):
            return None
        return "no_lineage_signal"
    return None


def certified_payload(entity: dict[str, Any]) -> dict[str, Any]:
    certified_area = "racas" if entity["subtype"] == "raca" else "linhagens"
    lock_prefix = "raca-lock" if entity["subtype"] == "raca" else "linhagem-lock"
    certification_id = f"{lock_prefix}:{entity['source']}:{slugify(entity['name'])}"
    payload = {
        **entity,
        "category": "race_lineage",
        "certificationStatus": "certified",
        "certifiedAs": entity["subtype"],
        "certifiedArea": certified_area,
        "lockedArea": certified_area,
        "certificationId": certification_id,
        "certificationMethod": "race-lineage-explicit-context-pass-1",
    }
    payload["tags"] = sorted(set([*payload.get("tags", []), entity["subtype"], "raca-linhagem", "certificado"]))
    return payload


def main() -> None:
    DATA_DIR.joinpath("work").mkdir(parents=True, exist_ok=True)
    entities = read_json(ENTITIES_PATH, [])
    if not isinstance(entities, list):
        raise SystemExit("race_lineage_granular.json is not a list.")

    aprimoramento_names = lock_source_names("aprimoramentos-certified-lock.json")
    kit_names = lock_source_names("kits-certified-lock.json")
    class_names = lock_source_names("classes-certified-lock.json")

    certified: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_source_names: set[tuple[str, str]] = set()
    seen_content_keys: set[tuple[str, str]] = set()

    for entity in entities:
        failure = certification_failure(entity, aprimoramento_names, kit_names, class_names)
        source_name = (entity.get("source"), slugify(str(entity.get("name") or "")))
        duplicate_content_key = content_key(entity)
        if entity.get("id") in seen_ids or source_name in seen_source_names:
            failure = "duplicate_certification_key"
        elif duplicate_content_key in seen_content_keys:
            failure = "duplicate_certification_content"
        if failure:
            rejected.append({**entity, "certificationStatus": "rejected", "rejectionReason": failure})
            continue
        payload = certified_payload(entity)
        certified.append(payload)
        seen_ids.add(payload["id"])
        seen_source_names.add((payload["source"], slugify(payload["name"])))
        seen_content_keys.add(duplicate_content_key)

    write_json(ENTITIES_PATH, certified)
    write_json(REJECTED_PATH, rejected)

    race_lock_records = [
        {
            "id": entity["id"],
            "source": entity["source"],
            "name": entity["name"],
            "nameKey": slugify(entity["name"]),
            "category": "race_lineage",
            "subtype": entity["subtype"],
            "lockedArea": entity["lockedArea"],
            "certificationId": entity["certificationId"],
        }
        for entity in certified
        if entity["subtype"] == "raca"
    ]
    lineage_lock_records = [
        {
            "id": entity["id"],
            "source": entity["source"],
            "name": entity["name"],
            "nameKey": slugify(entity["name"]),
            "category": "race_lineage",
            "subtype": entity["subtype"],
            "lockedArea": entity["lockedArea"],
            "certificationId": entity["certificationId"],
        }
        for entity in certified
        if entity["subtype"] == "linhagem"
    ]
    race_lock = {
        "version": 1,
        "area": "racas",
        "policy": {
            "certified_items_are_locked_to_area": True,
            "certified_items_must_not_be_duplicated_in_other_categories": True,
            "uncertified_race_claims_do_not_enter_racas": True,
            "certified_aprimoramentos_kits_and_classes_are_not_reclassified_as_racas": True,
        },
        "certifiedCount": len(race_lock_records),
        "rejectedCount": len(rejected),
        "records": race_lock_records,
    }
    lineage_lock = {
        "version": 1,
        "area": "linhagens",
        "policy": {
            "certified_items_are_locked_to_area": True,
            "certified_items_must_not_be_duplicated_in_other_categories": True,
            "uncertified_lineage_claims_do_not_enter_linhagens": True,
            "certified_aprimoramentos_kits_classes_and_racas_are_not_reclassified_as_linhagens": True,
        },
        "certifiedCount": len(lineage_lock_records),
        "rejectedCount": len(rejected),
        "records": lineage_lock_records,
    }
    write_json(LOCK_PATH, race_lock)
    write_json(LINEAGES_LOCK_PATH, lineage_lock)

    counts = Counter(entity["source"] for entity in certified)
    kinds = Counter(entity["subtype"] for entity in certified)
    rejection_counts = Counter(entity["rejectionReason"] for entity in rejected)
    lines = [
        "# Racas e linhagens certification",
        "",
        "Varredura das fontes prontas com travas separadas para racas mecanicas e linhagens narrativas.",
        "",
        f"- Certified items: {len(certified)}",
        f"- Certified racas: {kinds.get('raca', 0)}",
        f"- Certified linhagens: {kinds.get('linhagem', 0)}",
        f"- Rejected candidates: {len(rejected)}",
        "",
        "## Policy",
        "",
        "- A certified raca is locked to `racas`.",
        "- A certified linhagem is locked to `linhagens`.",
        "- Certified racas/linhagens cannot be duplicated in another category.",
        "- Items already locked as `aprimoramentos`, `kits` or `classes` are rejected here.",
        "- Blocks that look like kits/classes are rejected even when found inside race-related chapters.",
        "",
        "## Certified by source",
        "",
        "| Source | Certified |",
        "| --- | ---: |",
    ]
    for source, count in counts.most_common():
        lines.append(f"| `{source}` | {count} |")
    lines.extend(["", "## Rejection reasons", "", "| Reason | Count |", "| --- | ---: |"])
    for reason, count in rejection_counts.most_common():
        lines.append(f"| `{reason}` | {count} |")
    if rejected:
        lines.extend(["", "## Rejected sample", ""])
        for entity in rejected[:100]:
            lines.append(f"- `{entity.get('source')}` / `{entity.get('name')}`: {entity.get('rejectionReason')}")
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Certified {len(certified)} racas/linhagens; rejected {len(rejected)} candidates.")


if __name__ == "__main__":
    main()
