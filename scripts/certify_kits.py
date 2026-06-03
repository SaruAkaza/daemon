from __future__ import annotations

import re
from collections import Counter
from typing import Any

from common import DATA_DIR, INDEX_DIR, ROOT, slugify, read_json, write_json
from granular_validation import certification_quality_failure, first_locked_area, locked_names_for_areas


ENTITIES_PATH = DATA_DIR / "entities" / "kit_class_granular.json"
LOCK_PATH = INDEX_DIR / "kits-certified-lock.json"
REJECTED_PATH = DATA_DIR / "work" / "kits-certification-rejected.json"
REPORT_PATH = ROOT / "docs" / "reports" / "certification" / "kits-certification.md"

KIT_CONTEXT_RE = re.compile(r"source-title|book-part|text-kit-term|classlike-kit")
COST_RE = re.compile(r"\bCustos?\s*:|\bCusto em pontos de Aprimoramento\s*:", re.IGNORECASE)
MECHANICAL_RE = re.compile(
    r"\bCustos?\s*:|\bCusto em pontos de Aprimoramento\s*:|"
    r"\bPer[ií]cias?(?:\s+(?:Obrigat[oó]rias|Obrigatorias|Sugeridas))?\s*:|"
    r"\bAprimoramentos?\s*:|\bAtributos Principais\s*:|\bPoderes? de Classe\b|"
    r"\bPoder B[aá]sico\b|\bB[oô]nus de Treino\s*:|\bPontos Her[oó]icos\b|"
    r"\bPontos de Per[ií]cia\b|\bRestri[cç][oõ]es?\s*:",
    re.IGNORECASE,
)
SKILL_OR_OPTION_RE = re.compile(
    r"\bPer[ií]cias?(?:\s+(?:Obrigat[oó]rias|Obrigatorias|Sugeridas))?\s*:|"
    r"\bAprimoramentos?\s*:|\bAtributos Principais\s*:|\bPoderes? de Classe\b|"
    r"\bPoder B[aá]sico\b|\bPontos Her[oó]icos\b|\bPontos de Magia\b|\bPontos de F[eé]\b",
    re.IGNORECASE,
)

BAD_NAMES = {
    "3d t",
    "a terra",
    "alma",
    "anjos",
    "aprimoramento",
    "aprimoramentos",
    "armas",
    "armas brancas",
    "arqueiros",
    "ciencias",
    "ciências",
    "arrancar",
    "como",
    "conhecimento",
    "costuma",
    "costumam",
    "daemon",
    "daemon medieval",
    "eles",
    "gnomos",
    "graus",
    "humanos",
    "informatica",
    "informática",
    "kit tartaruga mutante",
    "kits",
    "kits angelicais",
    "kits de personagem",
    "kits demonicos",
    "kits demoníacos",
    "kits militares",
    "lutadores",
    "manipulacao",
    "manipulação",
    "mesmo",
    "muitas",
    "normalmente",
    "novos kits",
    "outros",
    "personagem",
    "personagens",
    "pericia",
    "pericias",
    "perícia",
    "perícias",
    "pode",
    "ponto de magia",
    "ponto heroico",
    "ponto heróico",
    "pontos",
    "pontos de fe",
    "pontos de fé",
    "pontos de magia",
    "pontos heroicos",
    "pontos heróicos",
    "ptero",
    "quanto",
    "racas",
    "raças",
    "teologia",
    "rodrigo lamazuus linn",
}


def normalize_key(value: str) -> str:
    return slugify(value).replace("-", " ")


def has_text_only_name_evidence(entity: dict[str, Any], body: str) -> bool:
    if entity.get("extractionMethod") == "auto-kit-label-pass-1":
        return True
    contexts = {item.strip() for item in str(entity.get("kitContext") or "").split(",") if item.strip()}
    if contexts != {"text-kit-term"}:
        return True
    name_key = normalize_key(str(entity.get("name") or ""))
    body_key = normalize_key(body)
    return (
        f"kit {name_key}" in body_key
        or f"{name_key} kit" in body_key
        or f"{name_key} kits" in body_key
    )


def certification_failure(entity: dict[str, Any], locked_names: dict[str, set[tuple[str, str]]]) -> str | None:
    name = str(entity.get("name") or "").strip()
    name_key = normalize_key(name)
    body = "\n".join(entry for entry in entity.get("entries", []) if isinstance(entry, str))
    context = str(entity.get("kitContext") or "")
    if locked_area := first_locked_area(entity, locked_names):
        return f"locked_as_{locked_area}"
    if entity.get("category") != "kit_class":
        return "category_is_not_kit_class"
    if entity.get("subtype") != "kit":
        return "subtype_is_not_kit"
    if not str(entity.get("id") or "").startswith("kit-"):
        return "id_is_not_kit"
    if not KIT_CONTEXT_RE.search(context):
        return "no_explicit_kit_context"
    if not name or name_key in BAD_NAMES or name_key.startswith("kits "):
        return "name_is_section_or_empty"
    if " que " in f" {name_key} " or name_key.startswith("geralmente ") or name_key.startswith("natural "):
        return "name_is_broken_sentence"
    if any(char in name for char in [".", ",", ";", ":"]):
        return "name_has_sentence_punctuation"
    if not has_text_only_name_evidence(entity, body):
        return "text_only_context_without_name_kit_evidence"
    if len(body) < 45:
        return "entry_too_short"
    if quality_failure := certification_quality_failure(entity):
        return quality_failure
    if not COST_RE.search(body):
        return "no_cost_field"
    if not SKILL_OR_OPTION_RE.search(body):
        return "no_skill_or_option_field"
    if not MECHANICAL_RE.search(body):
        return "no_mechanical_kit_signal"
    return None


def certified_payload(entity: dict[str, Any]) -> dict[str, Any]:
    certification_id = f"kit-lock:{entity['source']}:{slugify(entity['name'])}"
    payload = {
        **entity,
        "category": "kit_class",
        "subtype": "kit",
        "certificationStatus": "certified",
        "certifiedAs": "kit",
        "certifiedArea": "kits",
        "lockedArea": "kits",
        "certificationId": certification_id,
        "certificationMethod": "kit-explicit-context-mechanical-pass-1",
    }
    payload["tags"] = sorted(set([*payload.get("tags", []), "kit", "certificado"]))
    return payload


def main() -> None:
    DATA_DIR.joinpath("work").mkdir(parents=True, exist_ok=True)
    entities = read_json(ENTITIES_PATH, [])
    if not isinstance(entities, list):
        raise SystemExit("kit_class_granular.json is not a list.")

    certified: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_source_names: set[tuple[str, str]] = set()
    locked_names = locked_names_for_areas([
        "aprimoramentos", "racas", "linhagens", "classes",
        "poderes", "magias", "rituais", "regras_base",
    ])

    for entity in entities:
        failure = certification_failure(entity, locked_names)
        source_name = (entity.get("source"), slugify(str(entity.get("name") or "")))
        if entity.get("id") in seen_ids or source_name in seen_source_names:
            failure = "duplicate_certification_key"
        if failure:
            rejected.append({**entity, "certificationStatus": "rejected", "rejectionReason": failure})
            continue
        payload = certified_payload(entity)
        certified.append(payload)
        seen_ids.add(payload["id"])
        seen_source_names.add((payload["source"], slugify(payload["name"])))

    write_json(ENTITIES_PATH, certified)
    write_json(REJECTED_PATH, rejected)
    lock_records = [
        {
            "id": entity["id"],
            "source": entity["source"],
            "name": entity["name"],
            "nameKey": slugify(entity["name"]),
            "category": "kit_class",
            "subtype": "kit",
            "lockedArea": "kits",
            "certificationId": entity["certificationId"],
        }
        for entity in certified
    ]
    lock = {
        "version": 1,
        "area": "kits",
        "policy": {
            "certified_items_are_locked_to_area": True,
            "certified_items_must_not_be_duplicated_in_other_categories": True,
            "uncertified_kit_claims_do_not_enter_kits": True,
        },
        "certifiedCount": len(certified),
        "rejectedCount": len(rejected),
        "records": lock_records,
    }
    write_json(LOCK_PATH, lock)

    counts = Counter(entity["source"] for entity in certified)
    rejection_counts = Counter(entity["rejectionReason"] for entity in rejected)
    lines = [
        "# Kits certification",
        "",
        "Varredura das 190 fontes com trava de certificacao para kits.",
        "",
        f"- Certified kits: {len(certified)}",
        f"- Rejected candidates: {len(rejected)}",
        "",
        "## Policy",
        "",
        "- A certified kit is locked to `kits`.",
        "- A certified kit cannot be duplicated in another category.",
        "- Generic/manual kit summaries are not allowed in `kits`.",
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
        for entity in rejected[:80]:
            lines.append(f"- `{entity.get('source')}` / `{entity.get('name')}`: {entity.get('rejectionReason')}")
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Certified {len(certified)} kits; rejected {len(rejected)} candidates.")


if __name__ == "__main__":
    main()
