from __future__ import annotations

import re
from collections import Counter
from typing import Any

from common import DATA_DIR, INDEX_DIR, ROOT, read_json, write_json
from presentation_quality import TEXT_FIELDS, presentation_flags


REPORT_JSON = INDEX_DIR / "entity-highlight-quality.json"
REPORT_MD = ROOT / "docs" / "reports" / "entity-highlight-quality.md"
TRAILING_CONNECTORS = {
    "a", "ao", "aos", "as", "com", "como", "da", "das", "de", "do", "dos", "e", "em", "entre",
    "para", "por", "que", "se", "sem", "seu", "sua", "seus", "suas", "um", "uma", "o", "os", "no", "na",
    "nos", "nas", "ou", "pelo", "pela", "pelos", "pelas", "quando", "onde", "porque",
}
OCR_MARKERS = ["Ã", "Â", "â€", "�", "\ufffd", "\u00ad"]
PAGE_FOOTER_RE = re.compile(r"(?:^|\s)(?:aprimoramentos|kits|classes|r[aá]ças|poderes|magias|rituais)\s+\d{1,3}\s*$", re.I)
COST_RE = re.compile(r"(?:^|\s)(?:[-–—−]\s*)?\d+\s*(?:pontos?|pts?\.?)\s*:", re.I)


def normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def text_for_record(record: dict[str, Any]) -> str:
    values: list[str] = []
    for field in TEXT_FIELDS:
        value = record.get(field)
        if isinstance(value, list):
            values.extend(str(item) for item in value if item)
        elif value:
            values.append(str(value))
    return "\n".join(values)


def repeated_fragment_ratio(text: str) -> float:
    tokens = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9]{3,}", text.casefold())
    if len(tokens) < 80:
        return 0.0
    trigrams = [tuple(tokens[index:index + 3]) for index in range(len(tokens) - 2)]
    counts = Counter(trigrams)
    repeated = sum(count for count in counts.values() if count >= 4)
    return repeated / max(1, len(trigrams))


def quality_flags(record: dict[str, Any]) -> list[str]:
    text = text_for_record(record)
    compact = normalize_spaces(text)
    flags: list[str] = []
    if not compact:
        return ["empty_display_text"]
    if re.match(r"^[,;:.!?]|^(?:e|ou|mas|porém|porem|então|entao)\b", compact, flags=re.I):
        flags.append("starts_mid_sentence_possible_left_cut")
    if re.search(r"\b(?:Custo|Perícias|Pericias|Aprimoramentos|Pontos Heroicos|Pontos Heróicos|Especial|Sistema|Efeito)\s*:", compact, flags=re.I):
        if re.search(r"\.\s+[a-záéíóúàâêôãõç]{3,}\b", compact):
            flags.append("lowercase_sentence_after_section_possible_leak")
    if record.get("itemType") == "entity" or record.get("category") != "source":
        if len(compact) < 80:
            flags.append("too_short_possible_cut")
    # Texto longo não é problema por si só. A flag de bloco colado só aparece
    # quando há indícios estruturais de que mais de uma regra/entrada entrou no mesmo destaque.
    cost_markers = COST_RE.findall(compact)
    structural_breaks = len(re.findall(r"\b(?:Custo|Perícias|Pericias|Aprimoramentos|Pontos Heroicos|Especial|Requisitos|Sistema|Efeito|Duração|Duracao|Alcance)\s*:", compact, flags=re.I))
    if len(compact) > 2400 and (len(cost_markers) >= 5 or structural_breaks >= 9 or repeated_fragment_ratio(compact) > 0.08):
        flags.append("too_long_possible_merged_blocks")
    if any(marker in text for marker in OCR_MARKERS):
        flags.append("encoding_or_ocr_artifact")
    if re.search(r"[A-Za-zÀ-ÖØ-öø-ÿ]-\s+[a-zà-ÿ]", text):
        flags.append("hyphenated_word_split")
    if re.search(r"\n\s*\d{1,3}\s*\n", text):
        flags.append("page_number_inside_text")
    if PAGE_FOOTER_RE.search(compact):
        flags.append("trailing_section_footer_or_page_number")
    last_word_match = re.search(r"([A-Za-zÀ-ÖØ-öø-ÿ]+)\W*$", compact)
    if last_word_match and last_word_match.group(1).casefold() in TRAILING_CONNECTORS:
        flags.append("ends_with_connector_possible_cut")
    if compact and not re.search(r"[.!?:;)\]\}]\s*$", compact):
        flags.append("does_not_end_like_complete_sentence")
    if compact.count("(") != compact.count(")"):
        flags.append("unbalanced_parentheses")
    if compact.count("[") != compact.count("]"):
        flags.append("unbalanced_brackets")
    if repeated_fragment_ratio(compact) > 0.08:
        flags.append("repeated_fragment_possible_duplication")
    flags.extend(presentation_flags({**record, "itemType": record.get("itemType") or "entity"}))
    if record.get("subtype") == "aprimoramento" or str(record.get("id", "")).startswith("aprimoramento-"):
        costs = COST_RE.findall(compact)
        if not costs:
            flags.append("aprimoramento_without_cost_marker")
        if len(costs) >= 5 and len(compact) > 1200:
            flags.append("many_cost_markers_possible_merged_aprimoramentos")
    return sorted(set(flags))


def audit_area_records() -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    flag_counts: Counter[str] = Counter()
    area_counts: Counter[str] = Counter()
    for path in sorted((DATA_DIR / "areas").glob("*.json")):
        payload = read_json(path, {})
        area = payload.get("id") or path.stem
        for kind in ("entities", "sourceParts"):
            for record in payload.get(kind, []) or []:
                if area == "fontes" or record.get("category") == "source":
                    continue
                flags = quality_flags({**record, "itemType": "entity" if kind == "entities" else "sourcePart"})
                if not flags:
                    continue
                flag_counts.update(flags)
                area_counts[area] += 1
                records.append(
                    {
                        "area": area,
                        "kind": kind[:-1] if kind.endswith("s") else kind,
                        "id": record.get("id"),
                        "name": record.get("name"),
                        "source": record.get("source"),
                        "page": record.get("page"),
                        "flags": flags,
                        "sample": normalize_spaces(text_for_record(record))[:260],
                    }
                )
    severity_order = {
        "empty_display_text": 0,
        "too_short_possible_cut": 1,
        "ends_with_connector_possible_cut": 2,
        "does_not_end_like_complete_sentence": 3,
        "too_long_possible_merged_blocks": 4,
    }
    records.sort(key=lambda row: (min(severity_order.get(flag, 50) for flag in row["flags"]), row["area"], row.get("name") or ""))
    return {
        "version": 1,
        "summary": {
            "flaggedRecordCount": len(records),
            "flagCounts": dict(sorted(flag_counts.items())),
            "areaFlaggedCounts": dict(sorted(area_counts.items())),
        },
        "records": records,
    }


def write_markdown(payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Auditoria semântica inicial dos destaques",
        "",
        "Este relatório identifica trechos publicados que parecem cortados, colados, duplicados, incompletos ou contaminados por artefatos de extração.",
        "Ele não substitui conferência com o PDF/texto oficial; serve para priorizar revisão profissional.",
        "",
        "## Resumo",
        "",
        f"- Registros sinalizados: {summary['flaggedRecordCount']}",
        "",
        "### Flags",
        "",
    ]
    for flag, count in summary["flagCounts"].items():
        lines.append(f"- `{flag}`: {count}")
    lines.extend(["", "### Por área", ""])
    for area, count in summary["areaFlaggedCounts"].items():
        lines.append(f"- `{area}`: {count}")
    lines.extend(["", "## Primeiros itens para revisão", ""])
    for row in payload["records"][:120]:
        lines.extend([
            f"### {row.get('name') or row.get('id')}",
            "",
            f"- ID: `{row.get('id')}`",
            f"- Área: `{row.get('area')}`",
            f"- Fonte: `{row.get('source')}` p. {row.get('page') or '-'}",
            f"- Flags: {', '.join(f'`{flag}`' for flag in row['flags'])}",
            f"- Amostra: {row.get('sample')}",
            "",
        ])
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text("\n".join(line.rstrip() for line in lines), encoding="utf-8")


def main() -> None:
    payload = audit_area_records()
    write_json(REPORT_JSON, payload)
    write_markdown(payload)
    print("Entity highlight quality report written.")
    print(payload["summary"])


if __name__ == "__main__":
    main()
