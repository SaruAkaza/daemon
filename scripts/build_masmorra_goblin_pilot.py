from __future__ import annotations

import re
from collections import Counter
from datetime import UTC, datetime
from typing import Iterable

from docx import Document

from common import ROOT, slugify, write_json


SOURCE = "masmorra-goblin"
TITLE = "Masmorra Goblin"
SOURCE_CANDIDATES = [
    ROOT / "Livros" / "word" / "Masmorra  Goblin.docx",
    ROOT / "Livros" / "word" / "feito" / "Masmorra  Goblin.docx",
]
SOURCE_PATH = next((path for path in SOURCE_CANDIDATES if path.exists()), SOURCE_CANDIDATES[0])
OUT_PATH = ROOT / "data" / "pilot" / f"{SOURCE}.json"
DOCS_OUT_PATH = ROOT / "docs" / "assets" / "data" / "pilot" / f"{SOURCE}.json"


TEXT_FIXES = {
    "Masmorra  Goblin": "Masmorra Goblin",
    "Os Números Indicam": "Os números indicam",
    "tezouros": "tesouros",
    "Goblis": "Goblins",
    "estivem": "estiverem",
    "Este e o modele": "Este é o modelo",
    "Usuário de N": "usuário em +N",
    "o Usuário": "O usuário",
    "O Usuário": "O usuário",
    "O usuário": "o usuário",
    ". o usuário": ". O usuário",
    "o Personagem": "O personagem",
    "dO usuário": "do usuário",
    "aO usuário": "ao usuário",
    "podem escolher": "pode escolher",
    "ate": "até",
    "tome extremamente": "torne extremamente",
    "combaté": "combate",
    "dane": "dano",
    "Id6": "1D6",
    "Vitimas": "Vítimas",
    "pr6ximas": "próximas",
    "dais tipos": "dois tipos",
    "Pratéada": "Prateada",
    "Prateada": "prateada",
    "pratéada": "prateada",
    "urna vez": "uma vez",
    "urna hora": "uma hora",
    "será quebrada": "será quebrado",
    "ofeitiço": "o feitiço",
    "começara": "começará",
    "s em peso": "sem peso",
    "e1as": "elas",
    ".de design": " de design",
    "5m/ s": "5m/s",
}


def normalize_text(text: str) -> str:
    text = text.replace("\u00a0", " ")
    for old, new in TEXT_FIXES.items():
        text = text.replace(old, new)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"^(\d+)\s*=", r"\1.", text)
    text = re.sub(r"\b1d", "1D", text, flags=re.I)
    return text


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


def parse_roll_line(text: str) -> str:
    text = normalize_text(text)
    text = re.sub(r"^(\+?\d|00|[0-9]{2}-[0-9]{2}|[0-9]-[0-9]|[0-9]-0)\s+", r"\1 | ", text)
    return text


def make_equipment(title: str, paragraphs: list[str], sections: list[dict] | None = None) -> dict:
    detail_sections = sections or [block(f"{title}-descricao", "Descrição", "itens_equipamentos", paragraphs)]
    return item(
        title,
        "itens_equipamentos",
        "equipment",
        "Itens e Equipamentos",
        [paragraph for section in detail_sections for paragraph in section["paragraphs"]],
        detail_sections,
    )


def build_payload() -> dict:
    paragraphs = clean(raw_paragraphs())

    rule_sections = [
        block("descricao", "Descrição", "regras_base", paragraphs[1:2]),
        block("encontros", "Encontros", "regras_base", paragraphs[2:3]),
        block("baus-de-tesouros", "Baús de Tesouros", "regras_base", [parse_roll_line(line) for line in paragraphs[4:10]]),
    ]
    rule = item(
        "Regra base - Masmorra Goblin",
        "regras_base",
        "rule",
        "Regras Base",
        [paragraph for section in rule_sections for paragraph in section["paragraphs"]],
        rule_sections,
    )

    armor_table = make_equipment(
        "Tabela de Armaduras Mágicas",
        [parse_roll_line(line) for line in paragraphs[10:20]],
        [
            block("tipo-de-armadura", "Tipo de Armadura", "itens_equipamentos", [parse_roll_line(line) for line in paragraphs[10:20]]),
            block("habilidade", "Habilidade da Armadura", "itens_equipamentos", [paragraphs[20]]),
        ],
    )
    armor_x = make_equipment(
        "Armadura +X",
        [],
        [
            block("descricao", "Descrição", "itens_equipamentos", [" ".join(paragraphs[21:24])]),
            block("ip", "IP", "itens_equipamentos", [parse_roll_line(line) for line in paragraphs[24:30]]),
        ],
    )
    disguise = make_equipment(
        "Armadura de Disfarce",
        [],
        [
            block("descricao", "Descrição", "itens_equipamentos", [" ".join(paragraphs[30:34])]),
            block("variantes", "Variantes Conhecidas", "itens_equipamentos", [parse_roll_line(line) for line in paragraphs[34:37]]),
        ],
    )
    immolation = make_equipment(
        "Armadura de Imolação +N",
        [],
        [
            block("descricao", "Descrição", "itens_equipamentos", paragraphs[37:39]),
            block("ip", "IP", "itens_equipamentos", [parse_roll_line(line) for line in paragraphs[39:45]]),
        ],
    )
    invisibility = make_equipment(
        "Armadura de Invisibilidade",
        [],
        [
            block("descricao", "Descrição", "itens_equipamentos", [" ".join(paragraphs[45:47])]),
            block("tipo", "Tipo de Armadura", "itens_equipamentos", [parse_roll_line(line) for line in paragraphs[47:50]]),
            block("ip", "IP", "itens_equipamentos", [parse_roll_line(line) for line in paragraphs[50:56]]),
            block("versoes", "Versões", "itens_equipamentos", [" ".join(paragraphs[56:60])]),
        ],
    )
    traveler = make_equipment("Armadura do Viajante", [" ".join(paragraphs[60:63])])
    regenerative = make_equipment("Armadura Regenerativa", [" ".join(paragraphs[63:65])])
    weightless = make_equipment("Armadura Sem Peso", [" ".join(paragraphs[65:68])])
    levitation = make_equipment("Armadura de Levitação", [" ".join(paragraphs[68:71])])

    sections = [
        rule,
        armor_table,
        armor_x,
        disguise,
        immolation,
        invisibility,
        traveler,
        regenerative,
        weightless,
        levitation,
    ]
    counts = Counter(section["area"] for section in sections)
    return {
        "version": 1,
        "source": SOURCE,
        "title": TITLE,
        "sourceFile": SOURCE_PATH.name,
        "sourcePath": str(SOURCE_PATH.relative_to(ROOT)),
        "status": "pilot_review",
        "summary": "Mini masmorra goblin com rolagens de tesouro, encontros e armaduras mágicas sorteáveis.",
        "areas": sorted(counts),
        "groups": [],
        "sections": sections,
        "counts": dict(counts),
        "reviewNotes": [
            "O procedimento da masmorra, encontros e baús foi classificado como regra base por funcionar como instrução de uso/rolagem.",
            "Goblins aparecem apenas como encontro sem ficha, portanto não foram criados como NPCs.",
            "Armaduras mágicas foram extraídas como itens/equipamentos individuais.",
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
