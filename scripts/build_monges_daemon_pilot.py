from __future__ import annotations

import re
import shutil
from collections import Counter
from datetime import UTC, datetime
from typing import Iterable

from docx import Document

from common import ROOT, slugify, write_json


SOURCE = "monges-daemon"
TITLE = "Monges Daemon"
SOURCE_CANDIDATES = [
    ROOT / "Livros" / "word" / "Monges_Daemon_OCR_alta_qualidade.docx",
    ROOT / "Livros" / "word" / "feito" / "Monges_Daemon_OCR_alta_qualidade.docx",
]
SOURCE_PATH = next((path for path in SOURCE_CANDIDATES if path.exists()), SOURCE_CANDIDATES[0])
OUT_PATH = ROOT / "data" / "pilot" / f"{SOURCE}.json"
DOCS_OUT_PATH = ROOT / "docs" / "assets" / "data" / "pilot" / f"{SOURCE}.json"


TEXT_FIXES = {
    "Monges Copyright © 2004 – Francisco Antônio da Silva Souza 1": "",
    "Mundo Daemon – o seu portal sobre Daemon.": "",
    "Monges para Daemon": TITLE,
    "Budistas": "budistas",
    "Monastérios": "monastérios",
    "aperfeiçoamento técnico": "aprimoramento técnico",
    "Dano desarmado": "Dano Desarmado",
    "WILLvsWILL": "WILL vs WILL",
    "Magia –": "magia,",
    "mágicas!!": "mágicas.",
    "1° nível": "1º nível",
    "4° nível": "4º nível",
    "6° nível": "6º nível",
    "8° nível": "8º nível",
    "10° nível": "10º nível",
}


PAGE_RE = re.compile(r"^Página\s+\d+$", flags=re.IGNORECASE)
TECHNIQUE_RE = re.compile(r"^(?P<title>.+?)\s+\((?P<cost>\d+\s+pontos?)\)\s*[–-]\s*(?P<desc>.+)$", flags=re.IGNORECASE)
LEVEL_DAMAGE_RE = re.compile(r"(\d+º nível)\s*[–-]\s*(.+?)(?=\s+\d+º nível|$)")


def normalize_text(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = text.replace("\r", "\n")
    for old, new in TEXT_FIXES.items():
        text = text.replace(old, new)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return text.strip()


def raw_paragraphs() -> list[str]:
    return [paragraph.text.strip() for paragraph in Document(SOURCE_PATH).paragraphs if paragraph.text.strip()]


def clean(values: Iterable[str]) -> list[str]:
    return [text for value in values if (text := normalize_text(value))]


def content_paragraphs() -> list[str]:
    ignored = {
        TITLE,
        "Texto extraído por OCR/camada textual. Arquivo de origem: Monges Daemon.pdf",
        "Agradecimentos",
    }
    return [
        paragraph
        for paragraph in clean(raw_paragraphs())
        if paragraph and paragraph not in ignored and not PAGE_RE.match(paragraph)
    ]


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


def make_monk_class(paragraphs: list[str]) -> dict:
    damage_source = next(paragraph for paragraph in paragraphs if paragraph.startswith("By Francisco Souza"))
    damage_lines = [
        f"{level}: {damage.strip()}"
        for level, damage in LEVEL_DAMAGE_RE.findall(damage_source.replace("By Francisco Souza", "").strip())
    ]
    cost_text = paragraphs[7].replace("Monges em números ", "")
    sections = [
        block("conceito", "Conceito", "classes", paragraphs[2:4]),
        block("combate-desarmado", "Combate Desarmado", "classes", paragraphs[5:7]),
        block("custo", "Custo", "classes", [
            cost_text,
        ]),
        block("dano-desarmado", "Dano Desarmado", "classes", damage_lines),
    ]
    return item(
        "Monge",
        "classes",
        "class",
        "Classes e Raças",
        [paragraph for section in sections for paragraph in section["paragraphs"]],
        sections,
    )


def make_technique(paragraph: str) -> dict:
    match = TECHNIQUE_RE.match(paragraph)
    if not match:
        raise ValueError(f"Não foi possível interpretar manobra/especialidade: {paragraph}")
    title = match.group("title").strip()
    cost = match.group("cost").strip().capitalize()
    desc = match.group("desc").strip()
    sections = [
        block(f"{title}-custo", "Custo", "manobras_combate", [cost]),
        block(f"{title}-descricao", "Descrição", "manobras_combate", [desc]),
    ]
    return item(
        title,
        "manobras_combate",
        "technique",
        "Manobras e Especialidades",
        [cost, desc],
        sections,
    )


def build_payload() -> dict:
    paragraphs = content_paragraphs()
    technique_paragraphs = [paragraph for paragraph in paragraphs if TECHNIQUE_RE.match(paragraph)]
    sections = [
        make_monk_class(paragraphs),
        *[make_technique(paragraph) for paragraph in technique_paragraphs],
    ]
    counts = Counter(section["area"] for section in sections)
    return {
        "version": 1,
        "source": SOURCE,
        "title": TITLE,
        "sourceFile": SOURCE_PATH.name,
        "sourcePath": str(SOURCE_PATH.relative_to(ROOT)),
        "status": "pilot_review",
        "summary": "Adaptação de monges para Sistema Daemon, com classe Monge, dano desarmado por nível e técnicas compráveis.",
        "areas": sorted(counts),
        "groups": [],
        "sections": sections,
        "counts": dict(counts),
        "reviewNotes": [
            "Créditos, rodapé e nota de distribuição foram removidos da catalogação.",
            "Monge foi tratado como classe, pois o próprio texto descreve o arquétipo como classe e traz progressão por nível.",
            "As técnicas compráveis foram classificadas como Manobras e Especialidades, pois são compradas junto das perícias e descrevem recursos de treinamento marcial.",
        ],
        "generatedAt": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }


def move_source_to_done() -> None:
    done_dir = ROOT / "Livros" / "word" / "feito"
    done_dir.mkdir(parents=True, exist_ok=True)
    source_in_word = ROOT / "Livros" / "word" / "Monges_Daemon_OCR_alta_qualidade.docx"
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
