from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Iterable

from docx import Document

from common import ROOT, slugify, write_json


SOURCE = "aprimoramentos-2"
TITLE = "Aprimoramentos 2"
SOURCE_PATH = ROOT / "Livros" / "word" / "Aprimoramentos_2_OCR_alta_qualidade.docx"
OUT_PATH = ROOT / "data" / "pilot" / f"{SOURCE}.json"
DOCS_OUT_PATH = ROOT / "docs" / "assets" / "data" / "pilot" / f"{SOURCE}.json"

COST_RE = re.compile(r"^([+-]?\d+)\s+pontos?(?:\s*\([^)]*\))?\s*[:.]?\s*(.*)$", re.IGNORECASE)

DROP_EXACT = {
    "Aprimoramentos 2.0",
    "Texto extraido por OCR/camada de texto e normalizado para leitura em DOCX.",
}

TEXT_FIXES = {
    "corpo-acorpo": "corpo-a-corpo",
    "corpo-acorpo": "corpo-a-corpo",
    "dentre 9m": "dentro de 9m",
    "Barbaro": "Barbaro",
    "Barbáro": "Bárbaro",
    "parceiro (Pc ou Npc)": "parceiro (PC ou NPC)",
    "tem efeitos maiores": "tenha efeitos maiores",
    "Os psiônico": "O psiônico",
    "os psiônico": "o psiônico",
    "ativados a causarão": "ativados e causarão",
    "à Todo Vapor": "a Todo Vapor",
    "à todo vapor": "a todo vapor",
    "efeitos vísiveis": "efeitos visíveis",
    "VÍSIVEIS": "VISÍVEIS",
    "1ponto": "1 ponto",
    "facas,etc": "facas, etc.",
    "dragão,entre": "dragão, entre",
    "aliados.Ao": "aliados. Ao",
    "batalha,se": "batalha, se",
    "Constituição,o": "Constituição, o",
    "sortudo...O": "sortudo... O",
    "PONTO.": "PONTO:",
    "Pontos Heróicos": "Pontos Heroicos",
    "Heróicos": "Heroicos",
}

RULE_HEADINGS = {
    "APRIMORAMENTOS METAMAGICOS",
    "AMPLIACOES E LIMITACOES PSIQUICAS",
}


def strip_accents(value: str) -> str:
    return slugify(value).replace("-", " ").upper()


def normalize_text(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = text.replace("–", "-")
    text = text.replace("“", '"').replace("”", '"')
    text = text.replace("’", "'")
    for old, new in TEXT_FIXES.items():
        text = text.replace(old, new)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(
        r"^([+-]?\d+)\s+PONTOS?\b",
        lambda m: f"{int(m.group(1))} {'Ponto' if abs(int(m.group(1))) == 1 else 'Pontos'}",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"^([+-]?\d+)\s+PONTO\.", r"\1 PONTO:", text, flags=re.IGNORECASE)
    text = re.sub(r"^([+-]?\d+)\s+PONTOS\(", r"\1 PONTOS (", text, flags=re.IGNORECASE)
    return text.strip()


def should_join(previous: str, current: str) -> bool:
    if not previous or not current:
        return False
    if previous.endswith("-") and current[:1].islower():
        return True
    if current.startswith("-") and re.match(r"^-\d+%", current):
        return True
    if previous[-1:].isdigit() and current.upper() in {"PM.", "PMS.", "PSI."}:
        return True
    last_word = previous.split()[-1].lower().strip(".,;:!?")
    if last_word in {"de", "do", "da", "dos", "das", "em", "por", "com", "para", "que", "o"}:
        return True
    if current[:1].islower() and not previous.endswith((".", "!", "?", ":", ";", '"')):
        return True
    return False


def clean(values: Iterable[str]) -> list[str]:
    paragraphs: list[str] = []
    for raw in values:
        text = normalize_text(raw)
        if not text:
            continue
        if strip_accents(text) in {strip_accents(value) for value in DROP_EXACT}:
            continue
        if re.fullmatch(r"Pagina \d+", strip_accents(text), flags=re.IGNORECASE):
            continue
        if paragraphs and should_join(paragraphs[-1], text):
            previous = paragraphs.pop()
            if previous.endswith("-") and text[:1].islower():
                paragraphs.append(normalize_text(previous[:-1] + text))
            else:
                paragraphs.append(normalize_text(f"{previous} {text}"))
            continue
        paragraphs.append(text)
    return paragraphs


def docx_paragraphs() -> list[str]:
    return [paragraph.text for paragraph in Document(SOURCE_PATH).paragraphs]


def is_cost(text: str) -> bool:
    return bool(COST_RE.match(text))


def is_upper_title(text: str) -> bool:
    if is_cost(text) or text.upper().startswith("RESTRICAO"):
        return False
    if text.endswith((".", ":")):
        return False
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return False
    upper_ratio = sum(1 for char in letters if char.upper() == char) / len(letters)
    return upper_ratio >= 0.86 and len(text) <= 80


def split_inline_title(text: str) -> tuple[str, str] | None:
    patterns = [
        r"^(PONTOS HEROICOS)\s+(Pontos Heroicos\b.*)$",
        r"^(METAMAGICOS)\s+(Eles tornam\b.*)$",
        r"^(PSIQUICAS)\s+(E possivel\b.*)$",
    ]
    normalized = strip_accents(text)
    for pattern in patterns:
        match = re.match(pattern, normalized, flags=re.IGNORECASE)
        if not match:
            continue
        title_words = len(match.group(1).split())
        original_words = text.split()
        title = " ".join(original_words[:title_words])
        description = " ".join(original_words[title_words:])
        return title, description
    return None


def section(section_id: str, title: str, area: str, paragraphs: list[str]) -> dict:
    return {"id": section_id, "title": title, "area": area, "paragraphs": paragraphs}


def cost_label(text: str) -> str:
    match = COST_RE.match(text)
    if not match:
        return text
    value = int(match.group(1))
    unit = "Ponto" if abs(value) == 1 else "Pontos"
    suffix_match = re.match(r"^[+-]?\d+\s+pontos?\s*(\([^)]*\))", text, flags=re.IGNORECASE)
    suffix = f" {suffix_match.group(1)}" if suffix_match else ""
    return f"{value} {unit}{suffix}"


def format_cost_segment(text: str) -> str:
    match = COST_RE.match(text)
    if not match:
        return text
    detail = match.group(2).strip()
    return f"{cost_label(text)}: {detail}".strip()


def build_enhancement(title: str, raw_parts: list[str]) -> dict:
    title = normalize_text(title)
    intro: list[str] = []
    cost_segments: list[list[str]] = []
    current_cost: list[str] | None = None

    for part in raw_parts:
        if is_cost(part):
            current_cost = [part]
            cost_segments.append(current_cost)
            continue
        if current_cost is not None:
            current_cost.append(part)
        else:
            intro.append(part)

    polarity = "negativo" if any(segment[0].lstrip().startswith("-") for segment in cost_segments) else "positivo"
    costs: list[str] = []
    description = list(intro)

    if len(cost_segments) == 1:
        first = cost_segments[0][0]
        match = COST_RE.match(first)
        costs = [cost_label(first)]
        detail = match.group(2).strip() if match else ""
        description.extend([text for text in [detail, *cost_segments[0][1:]] if text])
    else:
        for segment_parts in cost_segments:
            first = format_cost_segment(segment_parts[0])
            costs.append(normalize_text(" ".join([first, *segment_parts[1:]])))

    return {
        "id": slugify(title),
        "title": title.title() if title.isupper() else title,
        "area": "aprimoramentos",
        "kind": "enhancement",
        "polarity": polarity,
        "sectionId": "aprimoramento",
        "sectionTitle": "Aprimoramento",
        "paragraphs": costs + description,
        "sections": [
            section("custo", "Custo", "aprimoramentos", costs),
            section("descricao", "Descrição", "aprimoramentos", description),
        ],
    }


def parse_content(paragraphs: list[str]) -> tuple[list[dict], list[dict]]:
    content = clean(paragraphs)
    intro_end = next(index for index, text in enumerate(content) if strip_accents(text) == "ACERTO CRITICO APRIMORADO")
    rules = [
        section(
            "introducao",
            f"Regra base - {TITLE}",
            "regras_base",
            content[:intro_end],
        )
    ]

    items: list[dict] = []
    current_title: str | None = None
    current_parts: list[str] = []
    pending_rule_heading: str | None = None
    active_rule: dict | None = None

    def flush() -> None:
        nonlocal current_title, current_parts
        if current_title and any(is_cost(part) for part in current_parts):
            items.append(build_enhancement(current_title, current_parts))
        current_title = None
        current_parts = []

    index = intro_end
    while index < len(content):
        text = content[index]
        normalized = strip_accents(text)
        inline = split_inline_title(text)

        if normalized in {"APRIMORAMENTOS", "AMPLIACOES E LIMITACOES"}:
            flush()
            pending_rule_heading = text
            active_rule = None
            index += 1
            continue

        if pending_rule_heading and inline:
            title, description = inline
            heading = normalize_text(f"{pending_rule_heading} {title}")
            if strip_accents(heading) in RULE_HEADINGS:
                active_rule = section(slugify(heading), heading.title(), "regras_base", [description])
                rules.append(active_rule)
                pending_rule_heading = None
                index += 1
                continue

        if inline and strip_accents(inline[0]) == "PONTOS HEROICOS":
            flush()
            active_rule = None
            current_title = inline[0]
            current_parts = [inline[1]]
            index += 1
            continue

        if is_upper_title(text):
            active_rule = None
            next_text = content[index + 1] if index + 1 < len(content) else ""
            next_next = content[index + 2] if index + 2 < len(content) else ""
            if is_upper_title(next_text) and is_cost(next_next):
                flush()
                current_title = normalize_text(f"{text} {next_text}")
                current_parts = []
                index += 2
                continue
            flush()
            current_title = text
            current_parts = []
            index += 1
            continue

        if active_rule is not None and current_title is None and not is_cost(text):
            active_rule["paragraphs"].append(text)
            index += 1
            continue

        if current_title is not None:
            current_parts.append(text)
        index += 1

    flush()
    return items, rules


def build_pilot() -> dict:
    enhancements, rule_sections = parse_content(docx_paragraphs())
    sections = sorted(enhancements, key=lambda item: item["title"].casefold())
    groups = [
        {
            "id": "regra-base-aprimoramentos-2",
            "title": "Regra base - Aprimoramentos 2",
            "kind": "ruleset",
            "area": "regras_base",
            "sectionTitle": "Regra Base",
            "sections": rule_sections,
        }
    ]
    areas = sorted({group["area"] for group in groups} | {item["area"] for item in sections})
    positive_count = len([item for item in sections if item["polarity"] == "positivo"])
    negative_count = len([item for item in sections if item["polarity"] == "negativo"])
    area_counts = {
        area: len([group for group in groups if group["area"] == area])
        + len([item for item in sections if item["area"] == area])
        for area in areas
    }
    return {
        "version": 1,
        "status": "pilot_review",
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "source": SOURCE,
        "sourceFile": SOURCE_PATH.name,
        "sourcePath": str(SOURCE_PATH.relative_to(ROOT)),
        "title": TITLE,
        "summary": "Compilacao de aprimoramentos de combate, metamágicos e psiquicos, com custos positivos e limitacoes negativas.",
        "areas": areas,
        "groups": groups,
        "sections": sections,
        "areaCounts": area_counts,
        "reviewNotes": [
            "Livro tratado individualmente, sem incluir outros Anjos ou proximos livros.",
            "Texto revisado antes da catalogacao; marcadores de pagina e cabecalho OCR foram removidos.",
            "Aprimoramentos com uma unica opcao exibem custo isolado e descricao abaixo.",
            "Aprimoramentos com variacoes preservam cada custo junto ao efeito correspondente.",
            "A polaridade foi inferida pelo sinal do custo, ja que o documento nao possui secoes explicitas de positivos e negativos.",
            f"Total de aprimoramentos catalogados: {len(sections)} ({positive_count} positivos, {negative_count} negativos).",
        ],
    }


def main() -> None:
    payload = build_pilot()
    write_json(OUT_PATH, payload)
    write_json(DOCS_OUT_PATH, payload)
    print(f"Wrote {OUT_PATH.relative_to(ROOT)}")
    print(f"Wrote {DOCS_OUT_PATH.relative_to(ROOT)}")
    print(f"Sections: {len(payload['sections'])}; groups: {len(payload['groups'])}; areas: {payload['areaCounts']}")


if __name__ == "__main__":
    main()
