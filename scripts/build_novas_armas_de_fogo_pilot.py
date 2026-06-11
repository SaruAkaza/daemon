from __future__ import annotations

import re
import shutil
from collections import Counter
from datetime import UTC, datetime
from typing import Iterable

from docx import Document

from common import ROOT, slugify, write_json


SOURCE = "novas-armas-de-fogo"
TITLE = "Novas Armas de Fogo"
SOURCE_CANDIDATES = [
    ROOT / "Livros" / "word" / "Novas_Armas_de_Fogo_OCR_alta_qualidade.docx",
    ROOT / "Livros" / "word" / "feito" / "Novas_Armas_de_Fogo_OCR_alta_qualidade.docx",
]
SOURCE_PATH = next((path for path in SOURCE_CANDIDATES if path.exists()), SOURCE_CANDIDATES[0])
OUT_PATH = ROOT / "data" / "pilot" / f"{SOURCE}.json"
DOCS_OUT_PATH = ROOT / "docs" / "assets" / "data" / "pilot" / f"{SOURCE}.json"


TEXT_FIXES = {
    "Novas Armas de Fogo(2)": TITLE,
    "idéia": "ideia",
    "vende-lo": "vendê-lo",
    "NINGUÉM": "ninguém",
    "Guaruhara": "Guarujá",
    "ROF:1": "ROF: 1",
    "Pente: .6": "Pente: 6",
    "2 - cano duplo": "2 (cano duplo)",
}


FIELD_RE = re.compile(r"^(Munição|Pente|Alcance|Dano|ROF):\s*(.+)$", flags=re.IGNORECASE)
PAGE_RE = re.compile(r"^Página\s+\d+$", flags=re.IGNORECASE)


def normalize_text(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = text.replace("\r", "\n")
    for old, new in TEXT_FIXES.items():
        text = text.replace(old, new)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"\s+([,;:!?])", r"\1", text)
    text = re.sub(r"\b(\d+)\s*m\b", r"\1 m", text, flags=re.IGNORECASE)
    text = re.sub(r"\bcal\.\s*", "cal. ", text, flags=re.IGNORECASE)
    return text.strip()


def raw_paragraphs() -> list[str]:
    return [paragraph.text.strip() for paragraph in Document(SOURCE_PATH).paragraphs if paragraph.text.strip()]


def clean(values: Iterable[str]) -> list[str]:
    return [text for value in values if (text := normalize_text(value))]


def block(block_id: str, title: str, area: str, paragraphs: list[str]) -> dict:
    return {"id": slugify(block_id), "title": title, "area": area, "paragraphs": paragraphs}


def item(
    title: str,
    area: str,
    kind: str,
    section_title: str,
    paragraphs: list[str],
    sections: list[dict],
) -> dict:
    return {
        "id": slugify(title),
        "title": title,
        "area": area,
        "kind": kind,
        "sectionId": slugify(section_title),
        "sectionTitle": section_title,
        "paragraphs": paragraphs,
        "sections": sections,
    }


def useful_lines(paragraphs: list[str]) -> list[str]:
    lines: list[str] = []
    for paragraph in paragraphs:
        for raw_line in paragraph.splitlines():
            line = normalize_text(raw_line)
            if not line or PAGE_RE.match(line):
                continue
            if line in {TITLE, "Texto extraído por camada textual e OCR quando disponível. Quebras de linha e caracteres indevidos foram normalizados quando possível."}:
                continue
            lines.append(line)
    return lines


def one_line(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\n", " ")).strip()


def split_weapon_chunks(lines: list[str]) -> list[tuple[str, dict[str, str]]]:
    chunks: list[tuple[str, dict[str, str]]] = []
    current_title = ""
    current_fields: dict[str, str] = {}

    def flush() -> None:
        nonlocal current_title, current_fields
        if current_title and current_fields:
            chunks.append((current_title, current_fields))
        current_title = ""
        current_fields = {}

    for line in lines:
        field_match = FIELD_RE.match(line)
        if field_match:
            key = field_match.group(1).capitalize()
            current_fields[key] = normalize_text(field_match.group(2))
            continue
        if current_title and current_fields:
            flush()
        if current_title and not current_fields:
            current_title = normalize_text(f"{current_title} {line}")
        else:
            current_title = line

    flush()
    return chunks


def make_weapon(title: str, fields: dict[str, str]) -> dict:
    order = ["Munição", "Pente", "Alcance", "Dano", "Rof"]
    labels = {"Rof": "ROF"}
    lines = [
        f"{labels.get(key, key)}: {fields[key]}"
        for key in order
        if key in fields
    ]
    return item(
        title,
        "itens_equipamentos",
        "equipment",
        "Itens e Equipamentos",
        lines,
        [block(f"{title}-ficha", "Ficha", "itens_equipamentos", lines)],
    )


def build_payload() -> dict:
    paragraphs = clean(raw_paragraphs())
    lines = useful_lines(paragraphs)
    weapon_start = lines.index("Lista das Armas") + 1
    intro_lines = [
        one_line(paragraph)
        for paragraph in paragraphs
        if paragraph.startswith("Neste livro virtual") or paragraph.startswith("ATENÇÃO:")
    ]
    weapons = [make_weapon(title, fields) for title, fields in split_weapon_chunks(lines[weapon_start:])]
    rule_sections = [
        block("uso", "Uso", "regras_base", intro_lines),
    ]
    rule = item(
        "Regra base - Novas Armas de Fogo",
        "regras_base",
        "ruleset",
        "Regras Base",
        intro_lines,
        rule_sections,
    )
    sections = [rule, *weapons]
    counts = Counter(section["area"] for section in sections)
    return {
        "version": 1,
        "source": SOURCE,
        "title": TITLE,
        "sourceFile": SOURCE_PATH.name,
        "sourcePath": str(SOURCE_PATH.relative_to(ROOT)),
        "status": "pilot_review",
        "summary": "Lista de novas armas de fogo para Sistema Daemon, com munição, pente, alcance, dano e ROF.",
        "areas": sorted(counts),
        "groups": [],
        "sections": sections,
        "counts": dict(counts),
        "reviewNotes": [
            "Créditos, avisos editoriais e divulgação foram removidos da catalogação por não agregarem regra ou item jogável.",
            "Cada arma foi separada como item/equipamento com ficha técnica própria.",
            "A grafia 'Pente: .6' da arma .38 foi normalizada para 'Pente: 6' por coerência com o padrão das demais armas.",
        ],
        "generatedAt": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }


def move_source_to_done() -> None:
    done_dir = ROOT / "Livros" / "word" / "feito"
    done_dir.mkdir(parents=True, exist_ok=True)
    source_in_word = ROOT / "Livros" / "word" / "Novas_Armas_de_Fogo_OCR_alta_qualidade.docx"
    if source_in_word.exists():
        shutil.move(str(source_in_word), str(done_dir / source_in_word.name))


def main() -> None:
    payload = build_payload()
    write_json(OUT_PATH, payload)
    write_json(DOCS_OUT_PATH, payload)
    move_source_to_done()
    print(f"Wrote {OUT_PATH}")
    print(f"Wrote {DOCS_OUT_PATH}")
    print(f"Sections: {len(payload['sections'])}")


if __name__ == "__main__":
    main()
