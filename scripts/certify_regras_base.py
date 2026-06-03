from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

from common import DATA_DIR, INDEX_DIR, ROOT, slugify, read_json, write_json
from granular_validation import certification_quality_failure


ENTITY_FILES = [
    DATA_DIR / "entities" / "regras_base_granular.json",
    DATA_DIR / "entities" / "core_rule.json",
    DATA_DIR / "entities" / "combat.json",
    DATA_DIR / "entities" / "attribute_skill.json",
]
LOCK_PATH = INDEX_DIR / "regras-base-certified-lock.json"
REJECTED_PATH = DATA_DIR / "work" / "regras-base-certification-rejected.json"
REPORT_PATH = ROOT / "docs" / "reports" / "certification" / "regras-base-certification.md"

VALID_CATEGORIES = {"core_rule", "attribute_skill", "combat"}
MECHANICAL_RE = re.compile(
    r"\b(?:regra|regras|sistema|teste|testes|atributo|atributos|per[ií]cia|per[ií]cias|"
    r"especializa[cç][aã]o|combate|dano|ferimentos|pontos?|modificadores?|penalidade|"
    r"b[oô]nus|dificuldade|resolu[cç][aã]o|cria[cç][aã]o de personagem|narrador|mestre)\b",
    re.IGNORECASE,
)
BAD_NAMES = {
    "agradecimentos",
    "atributos",
    "capitulo",
    "combate",
    "creditos",
    "indice",
    "introducao",
    "pericias",
    "regras",
    "sumario",
}
STAT_BLOCK_RE = re.compile(
    r"\bCON\s*\[?\d|\bFR\s*\[?\d|\bDEX\s*\[?\d|\bAGI\s*\[?\d|\bWILL\s*\[?\d|\bPER\s*\[?\d|"
    r"\bCAR\s*\[?\d|\bPVs?\b|\bIP\s*:?\s*\d|#?Ataques?",
    re.IGNORECASE,
)
CHARACTER_OPTION_RE = re.compile(
    r"\b(?:aprimoramentos?|kits?|classes?|ra[cç]as?|linhagens?)\b.{0,120}\b(?:pontos?|pts?\.?)\b|"
    r"\b(?:per[ií]cias?|aprimoramentos?)\s*:.{0,200}\b(?:pontos? her[oó]icos|pontos? de per[ií]cia|pts?\.?)\b",
    re.IGNORECASE,
)
POWER_MAGIC_RE = re.compile(
    r"\b(?:magias?|poderes?|rituais?|c[ií]rculos?|focus|pontos? de magia|tempo de conjura[cç][aã]o|materiais?)\s*:",
    re.IGNORECASE,
)


def body_text(entity: dict[str, Any]) -> str:
    entries = entity.get("entries") or []
    return "\n".join(entry for entry in entries if isinstance(entry, str)).strip()


def lock_source_names(path_name: str) -> set[tuple[str, str]]:
    lock = read_json(INDEX_DIR / path_name, {"records": []})
    return {
        (record["source"], record["nameKey"])
        for record in lock.get("records", [])
        if record.get("source") and record.get("nameKey")
    }


def certification_failure(entity: dict[str, Any], locked_names: dict[str, set[tuple[str, str]]]) -> str | None:
    name = str(entity.get("name") or "").strip()
    name_key = slugify(name).replace("-", " ")
    body = body_text(entity)
    category = entity.get("category")
    source_name = (entity.get("source"), slugify(name))

    for lock_name, names in locked_names.items():
        if source_name in names:
            return f"locked_as_{lock_name}"
    if category not in VALID_CATEGORIES:
        return "category_is_not_regras_base"
    if not str(entity.get("id") or ""):
        return "missing_id"
    if not entity.get("source"):
        return "missing_source"
    if not name or name_key in BAD_NAMES:
        return "name_is_section_or_empty"
    if any(char in name for char in [";", "?", "!"]):
        return "name_has_sentence_punctuation"
    if len(body) < 45:
        return "entry_too_short"
    if quality_failure := certification_quality_failure(entity):
        return quality_failure
    if len(STAT_BLOCK_RE.findall(body[:1000])) >= 5:
        return "looks_like_stat_block"
    if CHARACTER_OPTION_RE.search(body[:1400]):
        return "looks_like_character_option"
    if POWER_MAGIC_RE.search(body[:1000]) and category not in {"core_rule", "combat", "attribute_skill"}:
        return "looks_like_power_magic_or_ritual"
    if not MECHANICAL_RE.search(f"{name} {body} {' '.join(entity.get('tags', []) or [])}"):
        return "no_rule_mechanical_signal"
    return None


def certified_payload(entity: dict[str, Any]) -> dict[str, Any]:
    certification_id = f"regras-base-lock:{entity['source']}:{slugify(entity['name'])}"
    payload = {
        **entity,
        "certificationStatus": "certified",
        "certifiedAs": "regra_base",
        "certifiedArea": "regras_base",
        "lockedArea": "regras_base",
        "certificationId": certification_id,
        "certificationMethod": "regras-base-mechanical-pass-1",
    }
    payload["tags"] = sorted(set([*payload.get("tags", []), "regras-base", "certificado"]))
    return payload


def read_entities(path: Path) -> list[dict[str, Any]]:
    payload = read_json(path, [])
    if not isinstance(payload, list):
        raise SystemExit(f"{path.name} is not a list.")
    return [item for item in payload if isinstance(item, dict)]


def write_entities(path: Path, entities: list[dict[str, Any]]) -> None:
    if path.exists() or entities:
        write_json(path, entities)


def main() -> None:
    DATA_DIR.joinpath("work").mkdir(parents=True, exist_ok=True)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    certified_by_file: dict[Path, list[dict[str, Any]]] = {path: [] for path in ENTITY_FILES}
    rejected: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_source_names: set[tuple[str, str]] = set()
    locked_names = {
        "aprimoramento": lock_source_names("aprimoramentos-certified-lock.json"),
        "kit": lock_source_names("kits-certified-lock.json"),
        "class": lock_source_names("classes-certified-lock.json"),
        "raca": lock_source_names("racas-certified-lock.json"),
        "linhagem": lock_source_names("linhagens-certified-lock.json"),
        "poder": lock_source_names("poderes-certified-lock.json"),
        "magia": lock_source_names("magias-certified-lock.json"),
        "ritual": lock_source_names("rituais-certified-lock.json"),
    }

    for path in ENTITY_FILES:
        for entity in read_entities(path):
            failure = certification_failure(entity, locked_names)
            source_name = (entity.get("source"), slugify(str(entity.get("name") or "")))
            if entity.get("id") in seen_ids or source_name in seen_source_names:
                failure = "duplicate_certification_key"
            if failure:
                rejected.append({**entity, "entityFile": path.name, "certificationStatus": "rejected", "rejectionReason": failure})
                continue
            payload = certified_payload(entity)
            certified_by_file[path].append(payload)
            seen_ids.add(payload["id"])
            seen_source_names.add((payload["source"], slugify(payload["name"])))

    for path, entities in certified_by_file.items():
        write_entities(path, entities)

    certified = [entity for entities in certified_by_file.values() for entity in entities]
    lock = {
        "version": 1,
        "area": "regras_base",
        "policy": {
            "certified_items_are_locked_to_area": True,
            "certified_items_must_not_be_duplicated_in_other_categories": True,
            "uncertified_regras_base_claims_do_not_enter_regras_base": True,
        },
        "records": [
            {
                "id": entity["id"],
                "source": entity["source"],
                "name": entity["name"],
                "nameKey": slugify(entity["name"]),
                "category": entity["category"],
                "lockedArea": "regras_base",
                "certificationId": entity["certificationId"],
            }
            for entity in certified
        ],
    }
    write_json(LOCK_PATH, lock)
    write_json(REJECTED_PATH, rejected)

    rejected_counts = Counter(item["rejectionReason"] for item in rejected)
    report = [
        "# Certificacao de Regras Base",
        "",
        f"- Certificados: {len(certified)}",
        f"- Rejeitados: {len(rejected)}",
        "",
        "## Politica",
        "",
        "- Somente registros com categoria `core_rule`, `attribute_skill` ou `combat` entram em `Regras Base` como entidade certificada.",
        "- Registros certificados ficam travados em `regras_base` e nao devem ser publicados em outra area.",
        "- Registros ja travados como aprimoramento, kit, classe, raca, linhagem, poder, magia ou ritual sao rejeitados aqui.",
        "- Reivindicacoes de regra base sem certificacao sao enviadas para quarentena operacional.",
        "",
        "## Rejeicoes",
        "",
    ]
    if rejected_counts:
        report.extend(f"- {reason}: {count}" for reason, count in sorted(rejected_counts.items()))
    else:
        report.append("- Nenhuma rejeicao.")
    report.extend(["", "## Registros certificados", ""])
    report.extend(f"- {entity['name']} ({entity['source']}, {entity['category']})" for entity in certified)
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"certified {len(certified)} regras_base records; rejected {len(rejected)}")


if __name__ == "__main__":
    main()
