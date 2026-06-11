from __future__ import annotations

import re
from collections import Counter
from datetime import UTC, datetime
from typing import Iterable

from docx import Document

from common import ROOT, slugify, write_json


SOURCE = "masmorras"
TITLE = "Masmorras"
SOURCE_CANDIDATES = [
    ROOT / "Livros" / "word" / "Masmorras.docx",
    ROOT / "Livros" / "word" / "feito" / "Masmorras.docx",
]
SOURCE_PATH = next((path for path in SOURCE_CANDIDATES if path.exists()), SOURCE_CANDIDATES[0])
OUT_PATH = ROOT / "data" / "pilot" / f"{SOURCE}.json"
DOCS_OUT_PATH = ROOT / "docs" / "assets" / "data" / "pilot" / f"{SOURCE}.json"


TEXT_FIXES = {
    "Lá existe três Dungeons": "Lá existem três dungeons",
    "Lá existe três dungeons": "Lá existem três dungeons",
    "baus": "baús",
    "bau": "baú",
    "senecessário": "necessário",
    "Flexas": "Flechas",
    "flexas": "flechas",
    "comtra": "contra",
    "Pessimo": "Péssimo",
    "operérios": "operários",
    "estivererm": "estiverem",
    "proximos": "próximos",
    "proximo": "próximo",
    "Rok in rolls": "Rock in Rolls",
    "caiem": "caem",
    "anél": "anel",
    "luz continua": "luz contínua",
    "magicos": "mágicos",
    "usuario": "usuário",
    "qual quer": "qualquer",
    "magica": "mágica",
    "aplicavel": "aplicável",
    "umFrasco": "um Frasco",
    "óleo inflamavel": "óleo inflamável",
    "fragil": "frágil",
    "morerá": "morrerá",
    "corporeos": "corpóreos",
    "ficara": "ficará",
    "esta": "está",
    "vitimas": "vítimas",
    "superficie": "superfície",
    "Esxelente": "Excelente",
    "conceguiram": "conseguiram",
    "comseguiram": "conseguiram",
    "brceletes": "braceletes",
    "rebe": "recebe",
    "pericia arquearia": "perícia Arquearia",
    "não perde a concentração": "não perder a concentração",
    "eas palavres magicas ditas": "e as palavras mágicas ditas",
    "eas palavres mágicas ditas": "e as palavras mágicas ditas",
    "reio": "raio",
    "incandecentes": "incandescentes",
    "mágicamente": "magicamente",
    "reicatdo": "recitado",
    "reciatdo": "recitado",
    "conciderada": "considerada",
    "qulaquer": "qualquer",
    "onde de energia": "onda de energia",
    "dodos": "dados",
    "mada": "nada",
    "detreminar": "determinar",
    "encixada": "encaixada",
    "tranforma": "transforma",
    "enêrgia": "energia",
    "Ip": "IP",
    "Wil": "WILL",
    "WILLl": "WILL",
    "O Geonúcleo possuem": "O Geonúcleo possui",
}


def normalize_text(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = text.replace("Dungeons", "dungeons")
    for old, new in TEXT_FIXES.items():
        text = text.replace(old, new)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"\(\s+", "(", text)
    text = re.sub(r"\s+\)", ")", text)
    return text


def raw_paragraphs() -> list[str]:
    return [paragraph.text.strip() for paragraph in Document(SOURCE_PATH).paragraphs if paragraph.text.strip()]


def clean(values: Iterable[str]) -> list[str]:
    return [text for value in values if (text := normalize_text(value))]


def block(block_id: str, title: str, area: str, paragraphs: list[str]) -> dict:
    return {
        "id": slugify(block_id),
        "title": title,
        "area": area,
        "paragraphs": paragraphs,
    }


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


def creature_table(lines: list[str]) -> list[str]:
    return [re.sub(r"^(\d+)\s*=", r"\1.", line) for line in clean(lines)]


def split_area(paragraphs: list[str], start: int, end: int) -> list[str]:
    return clean(paragraphs[start:end])


def build_rules(paragraphs: list[str]) -> dict:
    areas = [
        ("Fundações", 2, 22),
        ("Masmorras", 22, 46),
        ("Geonúcleo", 46, 69),
    ]
    sections: list[dict] = []
    all_paragraphs: list[str] = []

    for name, start, end in areas:
        chunk = paragraphs[start:end]
        rule = [normalize_text(chunk[0])]
        creatures_start = chunk.index("Se nos dados cair criaturas deve-se jogar 1D10 para ver o que pode ser:") if "Se nos dados cair criaturas deve-se jogar 1D10 para ver o que pode ser:" in chunk else -1
        if creatures_start == -1:
            creatures_start = chunk.index("Se nos dodos cair criaturas deve-se jogar 1D10 para ver o que pode ser:")
        traps_start = chunk.index("Armadilhas:")
        treasures_start = chunk.index("Tesouros:") if "Tesouros:" in chunk else None
        if treasures_start is None:
            for index, line in enumerate(chunk):
                if re.match(r"^(Bom|Muito Bom|Muito bom|Excelente|Excelente 2|Maravilha|Nossa!!!)\b", line):
                    treasures_start = index
                    break

        creature_lines = creature_table(chunk[creatures_start + 1:traps_start])
        trap_lines = clean(chunk[traps_start + 1:treasures_start])
        treasure_lines = clean(chunk[treasures_start + 1:] if treasures_start is not None else [])

        section_paragraphs = rule + creature_lines + trap_lines + treasure_lines
        sections.extend(
            [
                block(f"{name}-regra", f"{name} - Baús", "regras_base", rule),
                block(f"{name}-criaturas", f"{name} - Encontros Aleatórios", "regras_base", creature_lines),
                block(f"{name}-armadilhas", f"{name} - Armadilhas", "regras_base", trap_lines),
                block(f"{name}-tesouros", f"{name} - Tesouros", "regras_base", treasure_lines),
            ]
        )
        all_paragraphs.extend(section_paragraphs)

    return item(
        "Regra base - Masmorras",
        "regras_base",
        "ruleset",
        "Regra Base",
        all_paragraphs,
        sections,
    )


def build_lore(paragraphs: list[str]) -> dict:
    sections = [
        block("masmorras-castelo", "Castelo Voador Sneerra", "cenarios_lore", split_area(paragraphs, 0, 2)),
        block(
            "masmorras-dungeons",
            "Dungeons não exploradas",
            "cenarios_lore",
            [
                "O castelo possui três áreas exploráveis catalogadas: Fundações, Masmorras e Geonúcleo. Cada uma possui sua própria regra de busca por baús, encontros, armadilhas e tesouros."
            ],
        ),
        block("masmorras-mapa", "Observações do mapa", "cenarios_lore", split_area(paragraphs, 69, 72)),
    ]
    return item(
        "Cenários/Lore - Masmorras",
        "cenarios_lore",
        "setting",
        "Cenário",
        [p for section in sections for p in section["paragraphs"]],
        sections,
    )


def build_payload() -> dict:
    paragraphs = raw_paragraphs()
    cleaned = clean(paragraphs)
    sections = [build_lore(paragraphs), build_rules(paragraphs)]
    areas = sorted({section["area"] for section in sections})
    counts = Counter(section["area"] for section in sections)
    return {
        "version": 1,
        "source": SOURCE,
        "title": TITLE,
        "sourceFile": SOURCE_PATH.name,
        "sourcePath": str(SOURCE_PATH.relative_to(ROOT)),
        "status": "pilot_review",
        "summary": (
            "Mini suplemento de exploração do Castelo Voador Sneerra, com três áreas de masmorra "
            "e tabelas de baús, encontros, armadilhas e tesouros."
        ),
        "areas": areas,
        "groups": [],
        "sections": sections,
        "counts": dict(counts),
        "reviewNotes": [
            "Referências a criaturas por página foram mantidas como tabela de encontros, não como NPCs sem ficha.",
            "Tesouros foram mantidos dentro da regra de rolagem; itens mágicos individuais podem ser extraídos depois se o usuário quiser esse nível de granularidade.",
            f"O DOCX possui {len(cleaned)} parágrafos úteis e não apresenta tabelas estruturais.",
        ],
        "generatedAt": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }


def main() -> None:
    payload = build_payload()
    write_json(OUT_PATH, payload)
    write_json(DOCS_OUT_PATH, payload)
    print(f"Wrote {OUT_PATH}")
    print(f"Wrote {DOCS_OUT_PATH}")
    print(f"Sections: {len(payload['sections'])}")


if __name__ == "__main__":
    main()
