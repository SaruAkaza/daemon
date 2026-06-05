from __future__ import annotations

import argparse
import json
import math
import re
import unicodedata
import zipfile
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree

from common import ROOT, slugify, write_json


WORD_DIR = ROOT / "Livros" / "word"
QUALITY_REPORT = ROOT / "docs" / "reports" / "manual-review" / "word-docx-quality-report.json"
SEGMENTS_DIR = ROOT / "data" / "segments"
SOURCE_SEGMENTS_DIR = SEGMENTS_DIR / "sources"
SEGMENT_INDEX = SEGMENTS_DIR / "index.json"
AREA_SEGMENTS = SEGMENTS_DIR / "area_segments.json"
REPORT_MD = ROOT / "docs" / "reports" / "manual-review" / "docx-segment-catalog.md"

NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


AREA_LABELS = {
    "regras_base": "Regras Base",
    "pericias": "Pericias",
    "aprimoramentos": "Aprimoramentos",
    "kits": "Kits",
    "classes": "Classes",
    "racas": "Racas",
    "linhagens": "Linhagens",
    "poderes": "Poderes",
    "magias": "Magias",
    "rituais": "Rituais",
    "itens_equipamentos": "Itens e Equipamentos",
    "criaturas_npcs": "Criaturas e NPCs",
    "cenarios_lore": "Cenarios e Lore",
    "aventuras": "Aventuras",
    "tabelas": "Tabelas e Geradores",
}


AREA_PATTERNS: dict[str, list[str]] = {
    "regras_base": [
        r"\bregra(?:s)?\b",
        r"\bsistema\b",
        r"\bteste(?:s)?\b",
        r"\bdificuldade\b",
        r"\bresist[eê]ncia\b",
        r"\batributo(?:s)?\b",
        r"\bCON\b|\bFR\b|\bDEX\b|\bAGI\b|\bINT\b|\bWILL\b|\bCAR\b|\bPER\b",
        r"\bpontos?\b",
        r"\bdano\b",
        r"\bIP\b|\bPVs?\b|\bPMs?\b",
    ],
    "pericias": [
        r"\bper[ií]cia(?:s)?\b",
        r"\bespecializa[cç][aã]o(?:es)?\b",
        r"\bvalor inicial\b",
        r"\bci[eê]ncia(?:s)?\b",
        r"\bconhecimento(?:s)?\b",
        r"\bsobreviv[eê]ncia\b",
        r"\brastreio\b",
        r"\bnavega[cç][aã]o\b",
    ],
    "aprimoramentos": [
        r"\baprimoramento(?:s)?\b",
        r"\bvantagem(?:ns)?\b",
        r"\bdesvantagem(?:ns)?\b",
        r"\btalento(?:s)?\b",
        r"\bbenef[ií]cio(?:s)?\b",
        r"\b\d+\s*(?:pontos?|pts?)\b",
    ],
    "kits": [
        r"\bkit(?:s)?\b",
        r"\barqu[eé]tipo(?:s)?\b",
        r"\bocupa[cç][aã]o(?:es)?\b",
        r"\bprofiss[aã]o(?:es)?\b",
    ],
    "classes": [
        r"\bclasse(?:s)?\b",
        r"\bclasse de prest[ií]gio\b",
        r"\bnível\b|\bnivel\b",
        r"\bexperi[eê]ncia\b",
    ],
    "racas": [
        r"\bra[cç]a(?:s)?\b",
        r"\bpovo(?:s)?\b",
        r"\belfo(?:s)?\b",
        r"\ban[aã]o(?:es)?\b",
        r"\bgigante(?:s)?\b",
        r"\bhumano(?:s)?\b",
        r"\bdeus(?:es)?\b",
        r"\bsemi-?deus(?:es)?\b",
    ],
    "linhagens": [
        r"\blinhagem(?:ns)?\b",
        r"\bdescend[eê]ncia\b",
        r"\bsangue\b",
        r"\bvampiro(?:s)?\b",
        r"\blobisomem(?:ns)?\b",
        r"\bimortal(?:is|s)?\b",
        r"\bh[ií]brido(?:s)?\b",
    ],
    "poderes": [
        r"\bpoder(?:es)?\b",
        r"\bsuperpoder(?:es)?\b",
        r"\bpsi(?:quismo|quico|quicos)?\b",
        r"\bmilagre(?:s)?\b",
        r"\bhabilidade(?:s)? especial(?:is)?\b",
        r"\bf[eé]\b",
    ],
    "magias": [
        r"\bmagia(?:s)?\b",
        r"\bfeiti[cç]o(?:s)?\b",
        r"\bcaminho(?:s)?\b",
        r"\bfocus\b",
        r"\bmetamagia\b",
        r"\belement(?:o|os|al|ais)\b",
        r"\bruna(?:s)?\b",
    ],
    "rituais": [
        r"\britual(?:is|s)?\b",
        r"\bgrim[oó]rio\b",
        r"\binvoca[cç][aã]o(?:es)?\b",
        r"\bencantamento(?:s)?\b",
        r"\bc[ií]rculo(?:s)?\b",
        r"\btempo de conjura[cç][aã]o\b",
        r"\bcomponentes?\b",
        r"\bmateriais?\b",
    ],
    "itens_equipamentos": [
        r"\bitem(?:s)?\b",
        r"\bequipamento(?:s)?\b",
        r"\barma(?:s)?\b",
        r"\barmadura(?:s)?\b",
        r"\bescudo(?:s)?\b",
        r"\bartefato(?:s)?\b",
        r"\breliquia(?:s)?\b|\brel[ií]quia(?:s)?\b",
        r"\bpre[cç]o\b",
        r"\bpeso\b",
    ],
    "criaturas_npcs": [
        r"\bcriatura(?:s)?\b",
        r"\bmonstro(?:s)?\b",
        r"\bNPCs?\b",
        r"\bpersonagem do mestre\b",
        r"\bdem[oô]nio(?:s)?\b",
        r"\banjo(?:s)?\b",
        r"\bdrag[aã]o(?:oes|es)?\b",
        r"\bmorto(?:s)?-?vivo(?:s)?\b",
        r"\bestat[ií]sticas\b",
        r"\bataque(?:s)?\b",
    ],
    "cenarios_lore": [
        r"\bhist[oó]ria\b",
        r"\bmitologia\b",
        r"\blenda(?:s)?\b",
        r"\bdeus(?:es)?\b",
        r"\bpante[aã]o\b",
        r"\bmundo(?:s)?\b",
        r"\breino(?:s)?\b",
        r"\bcidade(?:s)?\b",
        r"\bcultura(?:s)?\b",
        r"\breligi[aã]o(?:oes|es)?\b",
        r"\borganiza[cç][aã]o(?:es)?\b",
        r"\bordem(?:ns)?\b",
        r"\bculto(?:s)?\b",
        r"\bcl[aã](?:s)?\b",
    ],
    "aventuras": [
        r"\baventura(?:s)?\b",
        r"\bcampanha(?:s)?\b",
        r"\bcena(?:s)?\b",
        r"\bencontro(?:s)?\b",
        r"\bgancho(?:s)?\b",
        r"\bmiss[aã]o(?:es)?\b",
        r"\bquick[- ]?start\b",
    ],
    "tabelas": [
        r"\btabela(?:s)?\b",
        r"\bgerador(?:es)?\b",
        r"\baleat[oó]rio(?:s)?\b",
        r"\b1d\d+\b|\bd\d+\b",
        r"\bresultado(?:s)?\b",
        r"\bmodificador(?:es)?\b",
    ],
}

SECTION_HEADINGS = {
    "pericias": "pericias",
    "lista de pericias": "pericias",
    "aprimoramentos": "aprimoramentos",
    "kits": "kits",
    "classes": "classes",
    "racas": "racas",
    "linhagens": "linhagens",
    "poderes": "poderes",
    "magias": "magias",
    "rituais": "rituais",
    "grimorio": "rituais",
    "equipamentos": "itens_equipamentos",
    "armas": "itens_equipamentos",
    "itens": "itens_equipamentos",
    "criaturas": "criaturas_npcs",
    "monstros": "criaturas_npcs",
    "npcs": "criaturas_npcs",
    "historia": "cenarios_lore",
    "cenario": "cenarios_lore",
    "mitologia": "cenarios_lore",
    "aventuras": "aventuras",
    "tabelas": "tabelas",
}

FRONT_MATTER_RE = re.compile(
    r"\b(?:sum[aá]rio|[ií]ndice|cr[eé]ditos|agradecimentos|diagrama[cç][aã]o|"
    r"autor(?:es)?|copyright|bibliografia|download|e-mail|email)\b",
    re.IGNORECASE,
)
NOISE_RE = re.compile(r"[~^`|<>]{2,}|\.{5,}|[{}]{2,}|[�]")
STAT_BLOCK_RE = re.compile(r"\b(?:CON|FR|DEX|AGI|INT|WILL|CAR|PER|PVs?|IP)\b")
STRONG_STAT_BLOCK_RE = re.compile(
    r"\b(?:CON|FR|DEX|AGI|INT|WILL|CAR|PER)\b.*\b(?:PVs?|IP|ataques?|dano)\b|"
    r"\b(?:PVs?|IP)\b.*\b(?:ataques?|dano|CON|FR|DEX|AGI|INT|WILL|CAR|PER)\b",
    re.IGNORECASE | re.DOTALL,
)


def normalize_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", ascii_value.lower()).strip()


def read_quality_report() -> dict:
    if not QUALITY_REPORT.exists():
        raise SystemExit(f"Missing quality report: {QUALITY_REPORT}")
    return json.loads(QUALITY_REPORT.read_text(encoding="utf-8"))


def docx_paragraphs(path: Path) -> list[dict]:
    with zipfile.ZipFile(path) as archive:
        root = ElementTree.fromstring(archive.read("word/document.xml"))

    paragraphs: list[dict] = []
    index = 0
    for block in root.findall(".//w:body/*", NS):
        if block.tag == f"{{{NS['w']}}}p":
            text = "".join(node.text or "" for node in block.findall(".//w:t", NS)).strip()
            if not text:
                continue
            p_style = block.find(".//w:pStyle", NS)
            style = p_style.attrib.get(f"{{{NS['w']}}}val", "") if p_style is not None else ""
            index += 1
            paragraphs.append({"index": index, "text": text, "style": style, "kind": "paragraph"})
        elif block.tag == f"{{{NS['w']}}}tbl":
            rows = []
            for row in block.findall(".//w:tr", NS):
                cells = []
                for cell in row.findall(".//w:tc", NS):
                    cell_text = " ".join(
                        "".join(node.text or "" for node in paragraph.findall(".//w:t", NS)).strip()
                        for paragraph in cell.findall(".//w:p", NS)
                    ).strip()
                    if cell_text:
                        cells.append(cell_text)
                if cells:
                    rows.append(" | ".join(cells))
            if rows:
                index += 1
                paragraphs.append(
                    {
                        "index": index,
                        "text": "\n".join(rows),
                        "style": "Table",
                        "kind": "table",
                    }
                )
    return paragraphs


def is_heading(paragraph: dict) -> bool:
    text = " ".join(paragraph["text"].split())
    style = paragraph.get("style", "").lower()
    if style.startswith("heading") or style.startswith("titulo") or style.startswith("ttulo"):
        return True
    if len(text) > 110 or len(text) < 3:
        return False
    words = text.split()
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return False
    uppercase_ratio = sum(1 for char in letters if char.isupper()) / len(letters)
    if len(words) <= 9 and uppercase_ratio > 0.62:
        return True
    if len(words) <= 7 and text.endswith(":"):
        return True
    key = normalize_key(text)
    return key in SECTION_HEADINGS or key.startswith("capitulo ")


def section_area_for_heading(text: str) -> str | None:
    key = normalize_key(text)
    if key in SECTION_HEADINGS:
        return SECTION_HEADINGS[key]
    for heading, area in SECTION_HEADINGS.items():
        if re.search(rf"\b{re.escape(heading)}\b", key):
            return area
    return None


def should_split_for_size(current_chars: int, next_chars: int, target_chars: int, max_chars: int) -> bool:
    if current_chars >= max_chars:
        return True
    return current_chars >= target_chars and current_chars + next_chars > target_chars


def build_segments(paragraphs: list[dict], target_chars: int, max_chars: int) -> list[dict]:
    segments = []
    current: list[dict] = []
    current_chars = 0
    current_heading = ""
    current_area_hint: str | None = None

    def flush() -> None:
        nonlocal current, current_chars, current_heading, current_area_hint
        if not current:
            return
        text = "\n\n".join(item["text"] for item in current).strip()
        segments.append(
            {
                "heading": current_heading,
                "areaHint": current_area_hint,
                "paragraphStart": current[0]["index"],
                "paragraphEnd": current[-1]["index"],
                "blockKinds": sorted({item["kind"] for item in current}),
                "text": text,
            }
        )
        current = []
        current_chars = 0
        current_heading = ""
        current_area_hint = None

    for paragraph in paragraphs:
        text = paragraph["text"]
        heading = is_heading(paragraph)
        paragraph_area = section_area_for_heading(text) if heading else None
        if current and heading and current_chars >= 450:
            flush()
        elif current and should_split_for_size(current_chars, len(text), target_chars, max_chars):
            flush()

        if heading:
            current_heading = text[:160]
            current_area_hint = paragraph_area or current_area_hint
        elif paragraph_area:
            current_area_hint = paragraph_area

        current.append(paragraph)
        current_chars += len(text) + 2

    flush()
    return segments


def score_area(text: str, heading: str, area_hint: str | None, area: str) -> tuple[float, list[str]]:
    haystack = f"{heading}\n{text}"
    evidence: list[str] = []
    score = 0.0
    for pattern in AREA_PATTERNS[area]:
        matches = re.findall(pattern, haystack, flags=re.IGNORECASE)
        if not matches:
            continue
        count = min(len(matches), 8)
        score += 1.0 + math.log2(count)
        evidence.append(pattern)

    if area_hint == area:
        score += 5.0
        evidence.append("section_heading_hint")
    if area == "criaturas_npcs" and STRONG_STAT_BLOCK_RE.search(text):
        score += 8.0
        evidence.append("daemon_stat_block")
    elif area == "criaturas_npcs" and STAT_BLOCK_RE.search(text):
        score += 3.5
        evidence.append("partial_daemon_stat_block")
    if area == "tabelas" and "|" in text:
        score += 2.5
        evidence.append("table_structure")
    if area == "cenarios_lore" and len(text) > 1800 and score:
        score += 1.0
        evidence.append("long_lore_block")
    return score, evidence[:8]


def classify_segment(segment: dict) -> tuple[list[dict], list[str]]:
    text = segment["text"]
    heading = segment.get("heading") or ""
    area_hint = segment.get("areaHint")
    flags = []
    if FRONT_MATTER_RE.search(text[:1200]):
        flags.append("front_matter_possible")
    if NOISE_RE.search(text):
        flags.append("ocr_noise_possible")
    if len(text) < 280:
        flags.append("short_segment")
    if len(text) > 9000:
        flags.append("large_mixed_segment")

    raw_scores = {}
    evidence_by_area = {}
    for area in AREA_LABELS:
        score, evidence = score_area(text, heading, area_hint, area)
        if score > 0:
            raw_scores[area] = score
            evidence_by_area[area] = evidence

    if not raw_scores:
        return (
            [
                {
                    "area": "cenarios_lore",
                    "label": AREA_LABELS["cenarios_lore"],
                    "score": 0,
                    "confidence": 0.25,
                    "evidence": ["fallback_unclassified_text"],
                }
            ],
            sorted(set([*flags, "needs_manual_classification"])),
        )

    best = max(raw_scores.values())
    selected = []
    for area, score in sorted(raw_scores.items(), key=lambda item: item[1], reverse=True):
        if score >= 4.5 or score >= best * 0.65:
            confidence = min(0.93, 0.34 + score / 18)
            selected.append(
                {
                    "area": area,
                    "label": AREA_LABELS[area],
                    "score": round(score, 3),
                    "confidence": round(confidence, 3),
                    "evidence": evidence_by_area[area],
                }
            )
        if len(selected) >= 5:
            break

    if len(selected) > 1:
        flags.append("multi_area_segment")
    if selected[0]["confidence"] < 0.62:
        flags.append("low_confidence_classification")
    return selected, sorted(set(flags))


def source_id_for_document(document: dict) -> str:
    matched = document.get("matchedTxt")
    if matched:
        return Path(matched).stem
    return slugify(clean_source_title(Path(document["file"]).stem))


def clean_source_title(stem: str) -> str:
    cleaned = re.sub(r"_OCR_(?:alta_qualidade|parcial|extraido)$", "", stem)
    cleaned = re.sub(r"_OCR_.*$", "", cleaned)
    return cleaned.replace("_", " ")


def segment_id(source_id: str, ordinal: int, heading: str) -> str:
    heading_slug = slugify(heading)[:48] if heading else "segmento"
    return f"{source_id}-seg-{ordinal:04d}-{heading_slug}"


def build_catalog(status: str, limit: int | None, target_chars: int, max_chars: int) -> dict:
    quality = read_quality_report()
    documents = [row for row in quality.get("documents", []) if row.get("status") == status]
    if limit:
        documents = documents[:limit]

    SOURCE_SEGMENTS_DIR.mkdir(parents=True, exist_ok=True)
    sources_payload = []
    area_index: dict[str, list[dict]] = defaultdict(list)
    totals = Counter()

    for document in documents:
        path = ROOT / document["path"]
        if not path.exists():
            continue
        source_id = source_id_for_document(document)
        title = clean_source_title(Path(document["file"]).stem)
        paragraphs = docx_paragraphs(path)
        raw_segments = build_segments(paragraphs, target_chars, max_chars)
        segments = []
        area_counts = Counter()
        review_counts = Counter()

        for ordinal, raw in enumerate(raw_segments, start=1):
            classifications, flags = classify_segment(raw)
            primary_area = classifications[0]["area"]
            segment = {
                "id": segment_id(source_id, ordinal, raw.get("heading") or title),
                "source": source_id,
                "sourceFile": document["file"],
                "sourcePath": document["path"],
                "sourceQualityStatus": document.get("status"),
                "title": title,
                "heading": raw.get("heading") or "",
                "paragraphRange": [raw["paragraphStart"], raw["paragraphEnd"]],
                "blockKinds": raw["blockKinds"],
                "charCount": len(raw["text"]),
                "wordCount": len(re.findall(r"\w+", raw["text"], flags=re.UNICODE)),
                "primaryArea": primary_area,
                "classifications": classifications,
                "reviewStatus": "draft_review",
                "reviewFlags": flags,
                "text": raw["text"],
            }
            segments.append(segment)
            totals["segments"] += 1
            area_counts[primary_area] += 1
            for classification in classifications:
                area_index[classification["area"]].append(
                    {
                        "segmentId": segment["id"],
                        "source": source_id,
                        "sourceFile": document["file"],
                        "heading": segment["heading"],
                        "primaryArea": primary_area,
                        "confidence": classification["confidence"],
                        "reviewFlags": flags,
                    }
                )
            for flag in flags:
                review_counts[flag] += 1

        source_payload = {
            "version": 1,
            "source": source_id,
            "title": title,
            "sourceFile": document["file"],
            "sourcePath": document["path"],
            "sourceQualityStatus": document.get("status"),
            "generatedAt": datetime.now().isoformat(timespec="seconds"),
            "paragraphs": len(paragraphs),
            "segments": segments,
            "areaCounts": dict(sorted(area_counts.items())),
            "reviewFlagCounts": dict(sorted(review_counts.items())),
        }
        write_json(SOURCE_SEGMENTS_DIR / f"{source_id}.json", source_payload)
        sources_payload.append(
            {
                "source": source_id,
                "title": title,
                "sourceFile": document["file"],
                "sourceQualityStatus": document.get("status"),
                "paragraphs": len(paragraphs),
                "segmentCount": len(segments),
                "areaCounts": source_payload["areaCounts"],
                "reviewFlagCounts": source_payload["reviewFlagCounts"],
            }
        )
        totals["sources"] += 1

    index_payload = {
        "version": 1,
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "inputQualityStatus": status,
        "sourceCount": totals["sources"],
        "segmentCount": totals["segments"],
        "sources": sources_payload,
    }
    area_payload = {
        "version": 1,
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "areas": {
            area: {
                "label": AREA_LABELS[area],
                "segmentCount": len(rows),
                "segments": sorted(rows, key=lambda row: (row["source"], row["segmentId"])),
            }
            for area, rows in sorted(area_index.items())
        },
    }
    write_json(SEGMENT_INDEX, index_payload)
    write_json(AREA_SEGMENTS, area_payload)
    write_markdown_report(index_payload, area_payload)
    return index_payload


def write_markdown_report(index_payload: dict, area_payload: dict) -> None:
    lines = [
        "# DOCX Segment Catalog",
        "",
        f"Generated at: {index_payload['generatedAt']}",
        f"Input quality status: `{index_payload['inputQualityStatus']}`",
        "",
        "## Summary",
        "",
        f"- Sources processed: {index_payload['sourceCount']}",
        f"- Segments created: {index_payload['segmentCount']}",
        "",
        "## Segments by Area",
        "",
    ]
    for area, payload in area_payload["areas"].items():
        lines.append(f"- {payload['label']}: {payload['segmentCount']}")
    lines.extend(["", "## Sources", ""])
    for source in index_payload["sources"]:
        areas = ", ".join(f"{area}={count}" for area, count in source["areaCounts"].items())
        lines.append(f"- `{source['source']}`: {source['segmentCount']} segments ({areas})")
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build semantic segment catalog from DOCX files.")
    parser.add_argument("--status", default="ok", choices=["ok", "revisar", "ruim"])
    parser.add_argument("--limit", type=int)
    parser.add_argument("--target-chars", type=int, default=4200)
    parser.add_argument("--max-chars", type=int, default=7600)
    args = parser.parse_args()

    payload = build_catalog(args.status, args.limit, args.target_chars, args.max_chars)
    print(json.dumps({"sources": payload["sourceCount"], "segments": payload["segmentCount"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
