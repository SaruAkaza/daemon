from __future__ import annotations

import json
import re
import zipfile
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree

from common import ROOT, slugify, write_json


SOURCE_PATH = ROOT / "Livros" / "word" / "feito" / "4killers.docx"
OUT_PATH = ROOT / "data" / "pilot" / "4killers.json"
DOCS_OUT_PATH = ROOT / "docs" / "assets" / "data" / "pilot" / "4killers.json"
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

KILLER_NAMES = [
    "Fred Krueger",
    "Jason Voorhees",
    "Michael Myers",
    "Thomas Hewitt (Leatherface)",
]
SECTION_NAMES = {"Personalidade", "Poderes", "Curiosidades"}


def docx_paragraphs(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as archive:
        root = ElementTree.fromstring(archive.read("word/document.xml"))

    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:body/w:p", NS):
        text = "".join(node.text or "" for node in paragraph.findall(".//w:t", NS)).strip()
        if text:
            paragraphs.append(normalize_text(text))
    return join_split_paragraphs(paragraphs)


def normalize_text(text: str) -> str:
    replacements = {
        "oito,.é": "oito, é",
        "fio achada": "foi achada",
        "policias": "policiais",
        "As vezes": "Às vezes",
        "fa perseguição": "da perseguição",
        "faze-lo": "fazê-lo",
        "segura-lo": "segurá-lo",
        "derrota-lo": "derrotá-lo",
        "mata-lo": "matá-lo",
        "silencio": "silêncio",
        "assumi o controle": "assume o controle",
        "não de decomporá": "não se decomporá",
        "nave estrelar": "nave estelar",
        "Descreve-lo": "Descrevê-lo",
        "vitima": "vítima",
        "paises": "países",
        "som a série": "com a série",
    }
    cleaned = re.sub(r"\s+", " ", text).strip()
    for source, target in replacements.items():
        cleaned = cleaned.replace(source, target)
    return cleaned


def join_split_paragraphs(paragraphs: list[str]) -> list[str]:
    joined: list[str] = []
    for paragraph in paragraphs:
        if joined and should_join(joined[-1], paragraph):
            joined[-1] = f"{joined[-1]} {paragraph}"
        else:
            joined.append(paragraph)
    return joined


def should_join(previous: str, current: str) -> bool:
    if current in SECTION_NAMES or current in KILLER_NAMES:
        return False
    if previous in SECTION_NAMES or previous in KILLER_NAMES:
        return False
    if re.match(r"^(?:Assassino|CON|PV|Garras|Armas|Faca|Motosserra|Ganha)", current):
        return False
    if previous.endswith((" e neste", "ele", "vai", "de", "máscara de", "mestre")):
        return True
    if len(current) < 32 and current[:1].islower():
        return True
    return False


def parse_attributes(line: str) -> dict[str, int]:
    attrs = {}
    for key in ["CON", "FR", "DEX", "AGI", "INT", "WILL", "PER", "CAR"]:
        match = re.search(rf"(?<![A-Z]){key}\s*(\d+)", line)
        if match:
            attrs[key] = int(match.group(1))
    return attrs


def parse_vitals(line: str) -> dict[str, str]:
    vitals = {}
    pv = re.search(r"\bPV\s*([^,]+)", line, flags=re.IGNORECASE)
    ip = re.search(r"\bIP\s*(\d+)", line, flags=re.IGNORECASE)
    if pv:
        vitals["PV"] = pv.group(1).strip()
    if ip:
        vitals["IP"] = ip.group(1).strip()
    return vitals


def parse_attack_line(line: str) -> str:
    parts = []
    attack = re.search(r"\bAtaques?\s*([^,]+)", line, flags=re.IGNORECASE)
    damage = re.search(r"\bdano\s*([^,]+)", line, flags=re.IGNORECASE)
    if attack:
        parts.append(f"Ataques {attack.group(1).strip()}")
    if damage:
        parts.append(f"dano {damage.group(1).strip()}")
    return ", ".join(parts) if parts else line


def parse_inline_skill_after_ip(line: str) -> str:
    match = re.search(r"\bIP\s*\d+\s+(.+)$", line, flags=re.IGNORECASE)
    return match.group(1).strip() if match else ""


def looks_like_skill_line(line: str) -> bool:
    if len(line) > 180:
        return False
    return bool(
        re.search(
            r"\b(?:garras|artes\s*marciais|armas\s*brancas|furtividade|rastreio|"
            r"sobrevivência|mecânica|ocultismo|faca|motosserra)\b",
            line,
            flags=re.IGNORECASE,
        )
    )


def parse_character(name: str, paragraphs: list[str]) -> dict:
    if paragraphs[0] != name:
        raise ValueError(f"Expected {name}, got {paragraphs[0]}")

    role = paragraphs[1]
    attributes_line = paragraphs[2]
    combat_line = paragraphs[3]
    cursor = 4
    skills_line = ""
    if cursor < len(paragraphs) and looks_like_skill_line(paragraphs[cursor]):
        skills_line = paragraphs[cursor]
        cursor += 1
    special_lines = []
    while cursor < len(paragraphs) and paragraphs[cursor] not in SECTION_NAMES:
        if cursor == 5 and name == "Fred Krueger":
            special_lines.append(paragraphs[cursor])
            cursor += 1
            continue
        break

    history_start = cursor
    while cursor < len(paragraphs) and paragraphs[cursor] != "Personalidade":
        cursor += 1
    history = paragraphs[history_start:cursor]

    cursor += 1
    personality_start = cursor
    while cursor < len(paragraphs) and paragraphs[cursor] != "Poderes":
        cursor += 1
    personality = paragraphs[personality_start:cursor]

    cursor += 1
    powers_start = cursor
    while cursor < len(paragraphs) and paragraphs[cursor] != "Curiosidades":
        cursor += 1
    powers = paragraphs[powers_start:cursor]

    cursor += 1
    curiosities = paragraphs[cursor:]

    return {
        "id": slugify(name),
        "name": name,
        "type": "character_npc",
        "role": role,
        "classifications": [
            {"area": "criaturas_npcs", "confidence": 1.0, "reason": "Ficha de antagonista com atributos Daemon"},
        ],
        "statBlock": {
            "attributes": parse_attributes(attributes_line),
            "vitals": parse_vitals(combat_line),
            "attributesText": attributes_line,
            "skills": "\n".join(
                item
                for item in [parse_attack_line(combat_line), parse_inline_skill_after_ip(combat_line), skills_line]
                if item
            ),
            "special": special_lines,
        },
        "sections": [
            {
                "id": "ficha",
                "title": "Ficha",
                "area": "criaturas_npcs",
                "paragraphs": [item for item in [role, attributes_line, combat_line, skills_line, *special_lines] if item],
            },
            {"id": "historia", "title": "História", "area": "criaturas_npcs", "paragraphs": history},
            {"id": "personalidade", "title": "Personalidade", "area": "criaturas_npcs", "paragraphs": personality},
            {"id": "poderes_npc", "title": "Poderes", "area": "criaturas_npcs", "paragraphs": powers},
            {"id": "curiosidades", "title": "Curiosidades", "area": "criaturas_npcs", "paragraphs": curiosities},
        ],
    }


def build_pilot() -> dict:
    paragraphs = docx_paragraphs(SOURCE_PATH)
    starts = {name: paragraphs.index(name) for name in KILLER_NAMES}
    ordered_starts = [(name, starts[name]) for name in KILLER_NAMES]
    intro = paragraphs[: starts[KILLER_NAMES[0]]]
    characters = []
    for index, (name, start) in enumerate(ordered_starts):
        end = ordered_starts[index + 1][1] if index + 1 < len(ordered_starts) else len(paragraphs)
        characters.append(parse_character(name, paragraphs[start:end]))

    return {
        "version": 1,
        "status": "pilot_review",
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "source": "4killers",
        "sourceFile": SOURCE_PATH.name,
        "sourcePath": str(SOURCE_PATH.relative_to(ROOT)),
        "title": "4 Killers",
        "summary": "Suplemento com quatro antagonistas de horror adaptados para o Sistema Daemon.",
        "areas": ["criaturas_npcs", "cenarios_lore"],
        "intro": {
            "title": intro[0],
            "quote": intro[1:5],
            "paragraphs": intro[5:],
        },
        "characters": characters,
        "reviewNotes": [
            "Este piloto usa estrutura explícita do livro, não classificação automática por palavra-chave.",
            "O texto foi normalizado a partir do DOCX, com correções pontuais de OCR e quebras de parágrafo.",
            "Neste livro, as seções de poderes pertencem aos NPCs; não são poderes jogáveis globais.",
            "Ainda precisa de revisão humana antes de virar entidade final da base.",
        ],
    }


def main() -> None:
    payload = build_pilot()
    write_json(OUT_PATH, payload)
    write_json(DOCS_OUT_PATH, payload)
    print(json.dumps({"source": payload["source"], "characters": len(payload["characters"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
