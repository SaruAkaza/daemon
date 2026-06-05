from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Iterable

from docx import Document

from common import ROOT, slugify, write_json


SOURCE = "anoes"
TITLE = "Anões"
SOURCE_CANDIDATES = [
    ROOT / "Livros" / "word" / "Anoes_OCR_alta_qualidade.docx",
    ROOT / "Livros" / "word" / "feito" / "Anoes_OCR_alta_qualidade.docx",
]
SOURCE_PATH = next(path for path in SOURCE_CANDIDATES if path.exists())
OUT_PATH = ROOT / "data" / "pilot" / f"{SOURCE}.json"
DOCS_OUT_PATH = ROOT / "docs" / "assets" / "data" / "pilot" / f"{SOURCE}.json"


def normalize_text(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = text.replace("â€œ", '"').replace("â€", '"').replace("â€™", "'")
    text = text.replace("entre os forças", "entre as forças")
    text = text.replace("muitos mais", "muito mais")
    text = text.replace("um arquitetura", "uma arquitetura")
    text = text.replace("artificies", "artífices")
    text = text.replace("atraente e tampouco", "atraentes e tampouco")
    text = text.replace("a conservarem a barba", "conservar a barba")
    text = text.replace("dizem é necessária", "dizem que é necessária")
    text = text.replace("suas tendência", "suas tendências")
    text = text.replace("começassem a aventurarem-se", "começassem a aventurar-se")
    text = re.sub(r"\barmas mágicas+", "armas mágicas", text)
    text = re.sub(r"\baja por perto\b", "haja por perto", text)
    text = text.replace("realizá-lo nas forjas", "realizá-la nas forjas")
    text = text.replace("para nas cortes", "para as cortes")
    text = text.replace("os cidades", "as cidades")
    text = text.replace("Não existia nenhum Anão tivera contato", "Não existia nenhum Anão que tivesse contato")
    text = text.replace("são resultados que intricados processos", "são resultado de intricados processos")
    text = text.replace("Magos de todos as nações", "Magos de todas as nações")
    text = text.replace("maravilho Martelo", "maravilhoso Martelo")
    text = text.replace("com a arma utilizada", "como a arma utilizada")
    text = text.replace("partí-la", "parti-la")
    text = text.replace("encontrá-los é não é", "encontrá-los não é")
    text = text.replace("labirintos subterrâneo", "labirintos subterrâneos")
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return text


def should_join(previous: str, current: str) -> bool:
    if not previous or not current:
        return False
    if previous.endswith("-") and current[:1].islower():
        return True
    if current[:1].islower() and not previous.endswith((".", "!", "?", ":", ";", '"')):
        return True
    if previous.endswith(("de", "do", "da", "dos", "das", "em", "por", "com", "para", "e")):
        return True
    return False


def clean(values: Iterable[str]) -> list[str]:
    paragraphs: list[str] = []
    skip_exact = {
        "Anões",
        "Texto extraído por OCR/camada de texto e normalizado para leitura em DOCX.",
        "By Rodrigo “Lamazuus” Linn",
        "Arma",
        "Tempo de construção",
    }
    for raw in values:
        text = normalize_text(raw)
        if not text or text in skip_exact:
            continue
        if re.fullmatch(r"Página \d+", text):
            continue
        if paragraphs and should_join(paragraphs[-1], text):
            previous = paragraphs.pop()
            if previous.endswith("-") and text[:1].islower():
                paragraphs.append(normalize_text(previous[:-1] + text))
            else:
                paragraphs.append(normalize_text(f"{previous} {text}"))
        else:
            paragraphs.append(text)
    return paragraphs


def docx_paragraphs() -> list[str]:
    return [paragraph.text for paragraph in Document(SOURCE_PATH).paragraphs]


def collect(paragraphs: list[str], start: int, end: int) -> list[str]:
    return clean(paragraphs[start:end])


def collect_after(paragraphs: list[str], start: int, end: int) -> list[str]:
    return collect(paragraphs, start + 1, end)


def section(section_id: str, title: str, area: str, paragraphs: list[str]) -> dict:
    return {
        "id": section_id,
        "title": title,
        "area": area,
        "paragraphs": paragraphs,
    }


def make_section(paragraphs: list[str], title: str, area: str, start: int, end: int) -> dict:
    return section(slugify(title), title, area, collect_after(paragraphs, start, end))


def typed_item(
    title: str,
    area: str,
    kind: str,
    section_title: str,
    paragraphs: list[str],
    sections: list[dict] | None = None,
) -> dict:
    return {
        "id": slugify(title),
        "title": title,
        "area": area,
        "kind": kind,
        "sectionId": slugify(section_title),
        "sectionTitle": section_title,
        "paragraphs": paragraphs,
        "sections": sections or [section("descricao", "Descrição", area, paragraphs)],
    }


def enhancement(title: str, paragraphs: list[str], costs: list[str], description: list[str]) -> dict:
    return typed_item(
        title,
        "aprimoramentos",
        "enhancement",
        "Aprimoramento",
        paragraphs,
        [
            section("custo", "Custo", "aprimoramentos", costs),
            section("descricao", "Descrição", "aprimoramentos", description),
        ],
    )


def kit(title: str, raw_paragraphs: list[str]) -> dict:
    paragraphs = clean(raw_paragraphs)
    if paragraphs and paragraphs[0] == title:
        paragraphs = paragraphs[1:]
    sections: list[dict] = []
    current_title = "Descrição"
    current: list[str] = []

    def flush() -> None:
        nonlocal current, current_title
        if current:
            sections.append(section(slugify(current_title), current_title, "classes", current))
            current = []

    for paragraph in paragraphs:
        match = re.match(r"^(Custo|Perícias|Aprimoramentos|Pontos de Fé|Pontos de Magia|Pontos Heróicos|Formas e Caminhos Principais):\s*(.+)$", paragraph)
        if match:
            flush()
            current_title = match.group(1)
            current = [normalize_text(match.group(2))]
            continue
        if paragraph == "Apenas para Duegares":
            flush()
            current_title = "Pré-requisito"
            current = [paragraph]
            continue
        current.append(paragraph)
    flush()
    return typed_item(title, "classes", "class", "Classe/Kit", paragraphs, sections)


def build_weapon_time_table(paragraphs: list[str]) -> dict:
    rows = collect(paragraphs, 96, 110)
    entries: list[str] = []
    for row in rows:
        match = re.match(r"^(.+?)\s+(\d+.+)$", row)
        entries.append(f"{match.group(1)}: {match.group(2)}" if match else row)
    return typed_item(
        "Tempo de construção de armas",
        "itens_equipamentos",
        "equipment_table",
        "Tabela",
        entries,
        [section("tabela", "Tabela", "itens_equipamentos", entries)],
    )


def build_pilot() -> dict:
    paragraphs = docx_paragraphs()

    lore_sections = [
        section("introducao", "Introdução", "cenarios_lore", collect(paragraphs, 7, 10)),
        make_section(paragraphs, "Origem das Lendas", "cenarios_lore", 10, 16),
        make_section(paragraphs, "O Reino dos Anões", "cenarios_lore", 16, 32),
        make_section(paragraphs, "Cidades Gloriosas", "cenarios_lore", 32, 36),
        make_section(paragraphs, "Pequenos Habitantes", "cenarios_lore", 37, 49),
        make_section(paragraphs, "Civilização Subterrânea", "cenarios_lore", 49, 58),
        make_section(paragraphs, "Honra, Respeito e Coragem", "cenarios_lore", 59, 68),
        make_section(paragraphs, "Oposição à Magia", "cenarios_lore", 68, 74),
        make_section(paragraphs, "Os Irmãos Corrompidos", "cenarios_lore", 74, 80),
        make_section(paragraphs, "Duegares", "cenarios_lore", 81, 90),
        make_section(paragraphs, "O Trabalho nas Forjas", "cenarios_lore", 90, 96),
        make_section(paragraphs, "Campanha", "cenarios_lore", 166, 170),
    ]

    race_anoes_sections = [
        section("descricao", "Descrição", "racas", clean(collect(paragraphs, 7, 10) + collect(paragraphs, 37, 49))),
        section("sociedade", "Sociedade", "racas", clean(collect(paragraphs, 49, 68))),
        section("restricoes-e-habilidades", "Restrições e Habilidades", "racas", clean(collect(paragraphs, 68, 74) + collect(paragraphs, 115, 126))),
    ]
    race_duegares_sections = [
        section("historia", "História", "racas", collect_after(paragraphs, 74, 90)),
        section("uso-em-jogo", "Uso em Jogo", "racas", ["Apenas os Duegares podem comprar o Aprimoramento Poderes Mágicos entre os personagens anões apresentados neste suplemento."]),
    ]

    races = [
        typed_item("Anões", "racas", "race", "Raça/Linhagem", [p for block in race_anoes_sections for p in block["paragraphs"]], race_anoes_sections),
        typed_item("Duegares", "racas", "lineage", "Raça/Linhagem", [p for block in race_duegares_sections for p in block["paragraphs"]], race_duegares_sections),
    ]

    enhancements = [
        enhancement(
            "Visão Noturna",
            clean(collect(paragraphs, 117, 120)),
            ["2 pontos"],
            clean(collect(paragraphs, 118, 120)),
        ),
        enhancement(
            "Resistência à Magia",
            clean(collect(paragraphs, 120, 126)),
            [
                "1 ponto: 1D de resistência.",
                "2 pontos: 2D de resistência.",
                "3 pontos: 3D de resistência.",
                "4 pontos: 4D de resistência.",
                "5 pontos: 5D de resistência.",
            ],
            ["O personagem possui uma aura de proteção contra magias arcanas. Não é totalmente imune à Magia; possui uma resistência sobrenatural capaz de reduzir ou anular efeitos mágicos."],
        ),
    ]

    classes = [
        kit("Ferreiro", paragraphs[127:134]),
        kit("Guerreiro", paragraphs[136:143]),
        kit("Ladrão", paragraphs[143:150]),
        kit("Clérigo", paragraphs[150:157]),
        kit("Mago", paragraphs[157:166]),
    ]

    groups = [
        {
            "id": "anoes-nidavellir",
            "title": "Anões",
            "kind": "setting",
            "area": "cenarios_lore",
            "sectionTitle": "Cenário",
            "sections": lore_sections,
        }
    ]
    sections = races + enhancements + classes + [build_weapon_time_table(paragraphs)]
    areas = sorted({group["area"] for group in groups} | {item["area"] for item in sections})
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
        "summary": "Suplemento sobre Anões e Duegares, com lore de Nidavellir, características raciais, aprimoramentos, kits de personagem e regras de forja.",
        "areas": areas,
        "groups": groups,
        "sections": sections,
        "areaCounts": area_counts,
        "reviewNotes": [
            "Livro tratado individualmente após interrupção dos Anjos.",
            "Nenhum custo racial foi inferido para Anões ou Duegares, pois o texto não apresenta custo explícito para usar a raça.",
            "Visão Noturna e Resistência à Magia foram tratados como aprimoramentos com custo separado.",
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
