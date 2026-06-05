from __future__ import annotations

import re
import zipfile
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree

from common import ROOT, slugify, write_json


SOURCE_NAME = "Anime RPG - Supers - Powers.docx"
SOURCE_CANDIDATES = [
    ROOT / "Livros" / "word" / "feito" / SOURCE_NAME,
    ROOT / "Livros" / "word" / SOURCE_NAME,
]
OUT_PATH = ROOT / "data" / "pilot" / "anime-rpg-supers-powers.json"
DOCS_OUT_PATH = ROOT / "docs" / "assets" / "data" / "pilot" / "anime-rpg-supers-powers.json"
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


RULE_HEADINGS = {
    "natureza dos superpoderes",
    "nivel de poder np",
    "regra opcional sem custo",
    "aprimoramentos",
    "regra opcional sem mortes",
}

SETTING_HEADINGS = {
    "eras heroicas",
    "ideias para aventuras",
}

DROP_STYLES = {"TOC1", "TOC2", "TOC3"}


def source_path() -> Path:
    for path in SOURCE_CANDIDATES:
        if path.exists():
            return path
    raise FileNotFoundError(f"{SOURCE_NAME} nao encontrado em Livros/word ou Livros/word/feito")


def paragraph_text(p: ElementTree.Element) -> str:
    return "".join(t.text or "" for t in p.findall(".//w:t", NS)).strip()


def paragraph_style(p: ElementTree.Element) -> str:
    style = p.find("./w:pPr/w:pStyle", NS)
    if style is None:
        return ""
    return style.attrib.get(f"{{{NS['w']}}}val", "")


def read_docx_paragraphs(path: Path) -> list[dict[str, str]]:
    with zipfile.ZipFile(path) as archive:
        root = ElementTree.fromstring(archive.read("word/document.xml"))

    paragraphs: list[dict[str, str]] = []
    for p in root.findall(".//w:p", NS):
        text = paragraph_text(p)
        if not text:
            continue
        style = paragraph_style(p)
        if style in DROP_STYLES:
            continue
        paragraphs.append({"style": style, "text": clean_text(text)})
    return paragraphs


def norm(value: str) -> str:
    value = value.lower()
    value = value.replace("í", "i").replace("é", "e").replace("á", "a").replace("ã", "a").replace("ó", "o")
    value = value.replace("ç", "c")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def clean_text(text: str) -> str:
    text = text.replace("\ufb01", "fi").replace("\ufb02", "fl")
    text = text.replace("#", "ti")
    text = text.replace("!l", "til")
    text = text.replace("!c", "tic")
    text = text.replace("!v", "tiv")
    text = text.replace("!s", "tis")
    text = text.replace("!z", "tiz")
    text = text.replace('"', "ti")
    text = text.replace("$", "fí")
    text = text.replace('"vel', "tivel")
    text = text.replace('"veis', "tiveis")
    text = text.replace('"co', "tico")
    text = text.replace('"ca', "tica")
    text = text.replace('"ca', "tica")
    text = re.sub(r"^(\d{1,2})\1(?=[A-ZÁÉÍÓÚÃÕ])", "", text)
    text = re.sub(r"^\d{1,2}$", "", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\bpo(?=\s+(?:de|do|da|dos|das|para)\b)", "tipo", text)
    replacements = {
        "mo va": "motiva",
        "polí cas": "políticas",
        "heroi cas": "heroicas",
        "alterna va": "alternativa",
        "alterna vo": "alternativo",
        "alterna vas": "alternativas",
        "múl plas": "múltiplas",
        "a vada": "ativada",
        "ga lho": "gatilho",
        "galác co": "galáctico",
        "telepá ca": "telepática",
        "en dade": "entidade",
        "nega vo": "negativo",
        "di ceis": "difíceis",
        "ar sta": "artista",
        "robó co": "robótico",
        "úl mo": "último",
        "subs tu": "substitu",
        "re rado": "retirado",
        "re rar": "retirar",
        "u lizado": "utilizado",
        "u lizados": "utilizados",
        "u lizada": "utilizada",
        "u lizar": "utilizar",
        "u liza": "utiliza",
        "u lidade": "utilidade",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.strip()


def join_paragraphs(paragraphs: list[str]) -> list[str]:
    result: list[str] = []
    for paragraph in paragraphs:
        paragraph = clean_text(paragraph)
        if not paragraph:
            continue
        if result and should_join(result[-1], paragraph):
            result[-1] = f"{result[-1].rstrip()} {paragraph}"
        else:
            result.append(paragraph)
    return result


def should_join(previous: str, current: str) -> bool:
    if current.startswith(("+", "-", "contra ", "encorajamento.", "50.")):
        return True
    if previous.endswith((",", " de", " do", " da", " que", " o", " a", " e")):
        return True
    if current and current[0].islower():
        return True
    return False


def section(section_id: str, title: str, area: str, paragraphs: list[str]) -> dict:
    cleaned = [clean_text(paragraph) for paragraph in paragraphs if clean_text(paragraph)]
    return {
        "id": slugify(section_id),
        "title": title,
        "area": area,
        "paragraphs": cleaned if title == "Custo" else join_paragraphs(cleaned),
    }


def split_heading_cost(raw_title: str) -> tuple[str, str | None]:
    title = clean_text(raw_title)
    match = re.search(r"(.+?)(-?\d+\s*pontos?|vari[aá]vel)$", title, re.IGNORECASE)
    if not match:
        return title, None
    name = match.group(1).strip()
    cost = match.group(2).strip()
    cost = re.sub(r"(\d+)\s*(pontos?)", r"\1 \2", cost, flags=re.IGNORECASE)
    return name, cost


def infer_cost_lines(cost: str | None, body: list[str]) -> tuple[list[str], list[str]]:
    if not cost:
        if body and re.search(r"\bentre\s+3\s+e\s+5\s+pontos\b", body[0], re.IGNORECASE):
            return ["3 a 5 pontos"], body
        return [], body

    if norm(cost) != "variavel":
        return [cost], body

    description: list[str] = []
    cost_lines: list[str] = []
    next_cost = 1
    for paragraph in body:
        match = re.match(r"^(ponto|pontos):\s*(.+)$", paragraph, re.IGNORECASE)
        if not match:
            if cost_lines and should_join(cost_lines[-1], paragraph):
                cost_lines[-1] = f"{cost_lines[-1].rstrip()} {paragraph}"
                continue
            description.append(paragraph)
            continue
        label = f"{next_cost} {'ponto' if next_cost == 1 else 'pontos'}"
        cost_lines.append(f"{label}: {match.group(2).strip()}")
        next_cost += 1
    return cost_lines, description


def make_enhancement(raw_title: str, paragraphs: list[str]) -> dict:
    title, cost = split_heading_cost(raw_title)
    cleaned = [clean_text(paragraph) for paragraph in paragraphs if clean_text(paragraph)]
    cost_lines, description_parts = infer_cost_lines(cost, cleaned)
    description = join_paragraphs(description_parts)
    body = join_paragraphs(cleaned)
    blocks: list[dict] = []
    if cost_lines:
        blocks.append(section("custo", "Custo", "aprimoramentos", cost_lines))
    blocks.append(section("descricao", "Descrição", "aprimoramentos", description or body))
    return {
        "id": slugify(title),
        "title": title,
        "area": "aprimoramentos",
        "kind": "enhancement",
        "sectionId": "descricao",
        "sectionTitle": "Aprimoramento",
        "paragraphs": body,
        "sections": blocks,
    }


def collect_blocks(paragraphs: list[dict[str, str]]) -> tuple[list[dict], list[dict]]:
    groups: dict[str, dict] = {
        "anime-rpg-supers-regras": {
            "id": "anime-rpg-supers-regras",
            "title": "Regra base - Anime RPG - Supers - Powers",
            "kind": "ruleset",
            "area": "regras_base",
            "sectionTitle": "Regra Base",
            "sections": [],
        },
        "anime-rpg-supers-cenarios": {
            "id": "anime-rpg-supers-cenarios",
            "title": "Cenários e Lore",
            "kind": "setting",
            "area": "cenarios_lore",
            "sectionTitle": "Cenário",
            "sections": [],
        },
    }
    enhancements: list[dict] = []
    current_h3 = ""
    current_h4 = ""
    current_body: list[str] = []

    def flush() -> None:
        nonlocal current_h4, current_body
        if not current_h4:
            current_body = []
            return
        parent = norm(current_h3)
        title_norm = norm(current_h4)
        if parent == "aprimoramentos gerais":
            enhancements.append(make_enhancement(current_h4, current_body))
        elif parent in RULE_HEADINGS or title_norm in RULE_HEADINGS:
            groups["anime-rpg-supers-regras"]["sections"].append(
                section(current_h4, current_h4, "regras_base", current_body)
            )
        elif parent in SETTING_HEADINGS or title_norm in SETTING_HEADINGS:
            groups["anime-rpg-supers-cenarios"]["sections"].append(
                section(current_h4, current_h4, "cenarios_lore", current_body)
            )
        current_h4 = ""
        current_body = []

    for item in paragraphs:
        style = item["style"]
        text = item["text"]
        if not text:
            continue
        if style in {"Heading1", "Heading2"}:
            flush()
            current_h3 = norm(text)
            continue
        if style == "Heading3":
            flush()
            current_h3 = norm(text)
            if current_h3 in RULE_HEADINGS or current_h3 in SETTING_HEADINGS:
                current_h4 = text
                current_body = []
            continue
        if style == "Heading4":
            flush()
            current_h4 = text
            current_body = []
            continue
        if current_h4:
            current_body.append(text)
    flush()

    return [group for group in groups.values() if group["sections"]], enhancements


def build_payload() -> dict:
    src = source_path()
    paragraphs = read_docx_paragraphs(src)
    groups, sections = collect_blocks(paragraphs)
    areas = sorted({item["area"] for item in sections} | {group["area"] for group in groups})
    return {
        "version": 1,
        "status": "pilot_review",
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "source": "anime-rpg-supers-powers",
        "sourceFile": SOURCE_NAME,
        "sourcePath": str(src.relative_to(ROOT)).replace("\\", "/"),
        "title": "Anime RPG - Supers - Powers",
        "summary": (
            "Suplemento curto de superpoderes para Anime RPG/SUPERS. Inclui regras iniciais "
            "sobre eras heroicas, natureza dos superpoderes, nível de poder, ideias de aventura "
            "e uma seleção de aprimoramentos gerais com custos."
        ),
        "areas": areas,
        "groups": groups,
        "sections": sections,
        "characters": [],
        "adventures": [],
        "notes": [
            "Heading4 com custo colado ao título foi separado em nome + bloco Custo.",
            "Aprimoramentos variáveis tiveram custos inferidos sequencialmente a partir das listas do DOCX.",
        ],
    }


def main() -> None:
    payload = build_payload()
    write_json(OUT_PATH, payload)
    write_json(DOCS_OUT_PATH, payload)
    print(f"Wrote {OUT_PATH.relative_to(ROOT)}")
    print(f"Sections: {len(payload['sections'])}; groups: {len(payload['groups'])}; areas: {payload['areas']}")


if __name__ == "__main__":
    main()
