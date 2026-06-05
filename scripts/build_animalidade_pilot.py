from __future__ import annotations

import json
import re
from datetime import datetime

from docx import Document

from common import ROOT, slugify, write_json


SOURCE = "animalidade"
SOURCE_PATH = ROOT / "Livros" / "word" / "feito" / "animalidade.docx"
OUT_PATH = ROOT / "data" / "pilot" / f"{SOURCE}.json"
DOCS_OUT_PATH = ROOT / "docs" / "assets" / "data" / "pilot" / f"{SOURCE}.json"


def normalize_text(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = text.replace("“", '"').replace("”", '"').replace("’", "'")
    text = re.sub(r"([a-záàâãéêíóôõúç])- ([a-záàâãéêíóôõúç])", r"\1\2", text)
    text = re.sub(r"([a-záàâãéêíóôõúç])-([a-záàâãéêíóôõúç])", r"\1\2", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return text


def should_join(previous: str, current: str) -> bool:
    if previous.endswith("-") and current[:1].islower():
        return True
    if current[:1].islower() and not previous.endswith((".", "!", "?", ":", ";", '"')):
        return True
    if len(current) < 70 and current[:1].islower():
        return True
    if previous.endswith(("persona", "pode", "po", "esp", "ambi", "defin", "interes", "protegi")):
        return True
    return False


def merge_fragments(previous: str, current: str) -> str:
    if previous.endswith("-") and current[:1].islower():
        return normalize_text(f"{previous[:-1]}{current}")
    return normalize_text(f"{previous} {current}")


def clean(values: list[str]) -> list[str]:
    paragraphs: list[str] = []
    for value in values:
        text = normalize_text(value)
        if not text:
            continue
        if text.startswith("By Rodrigo"):
            continue
        if paragraphs and should_join(paragraphs[-1], text):
            paragraphs[-1] = merge_fragments(paragraphs[-1], text)
        else:
            paragraphs.append(text)
    return paragraphs


def docx_paragraphs() -> list[str]:
    return [paragraph.text for paragraph in Document(SOURCE_PATH).paragraphs]


def section(section_id: str, title: str, area: str, paragraphs: list[str]) -> dict:
    return {"id": section_id, "title": title, "area": area, "paragraphs": paragraphs}


def collect(paragraphs: list[str], start: int, end: int) -> list[str]:
    return clean(paragraphs[start:end])


def collect_after(paragraphs: list[str], start: int, end: int) -> list[str]:
    return collect(paragraphs, start + 1, end)


def make_section(paragraphs: list[str], title: str, area: str, start: int, end: int) -> dict:
    return section(slugify(title), title, area, collect_after(paragraphs, start, end))


def as_typed_item(item: dict, kind: str, section_title: str) -> dict:
    item["kind"] = kind
    item["sectionId"] = item["id"]
    item["sectionTitle"] = section_title
    return item


def split_level_sections(title: str, area: str, paragraphs: list[str], kind: str) -> dict:
    text = " ".join(paragraphs)
    marker = re.compile(r"(?i)\bN[íi]vel\s+(\d+):\s*")
    matches = list(marker.finditer(text))
    blocks = []
    intro = normalize_text(text[: matches[0].start()]) if matches else text
    if intro:
        blocks.append(section("descricao", "Descrição", area, [intro]))
    for index, match in enumerate(matches):
        level = match.group(1)
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        content = normalize_text(text[match.end():end])
        if content:
            blocks.append(section(f"nivel-{level}-{index + 1}", f"Nível {level}", area, [content]))
    return {
        "id": slugify(title),
        "title": title,
        "area": area,
        "kind": kind,
        "sectionId": slugify(title),
        "sectionTitle": title,
        "paragraphs": paragraphs,
        "sections": blocks or [section("descricao", "Descrição", area, paragraphs)],
    }


def split_cost_sections(title: str, paragraphs: list[str]) -> dict:
    cost_pattern = re.compile(r"(?i)\b(\d+\s+pontos?|ponto|pontos)\s*[:.]\s*")
    costs: list[dict[str, str]] = []
    cost_effects: list[str] = []
    inferred = 1
    text = normalize_text(" ".join(paragraphs))
    matches = list(cost_pattern.finditer(text))
    if matches:
        description = normalize_text(text[: matches[0].start()])
        for index, match in enumerate(matches):
            label = match.group(1)
            number = re.match(r"(\d+)", label)
            if number:
                inferred = max(inferred, int(number.group(1)) + 1)
            else:
                label = f"{inferred} {'ponto' if inferred == 1 else 'pontos'}"
                inferred += 1
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            effect = normalize_text(text[match.end():end])
            costs.append({"label": normalize_text(label), "effect": effect})
            if effect:
                cost_effects.append(effect)
    else:
        description = text
    blocks = []
    if costs:
        cost_lines = [
            item["label"] if len(costs) == 1 or not item["effect"] else f"{item['label']}: {item['effect']}"
            for item in costs
        ]
        blocks.append(section("custo", "Custo", "aprimoramentos", cost_lines))
    if len(costs) == 1:
        description_text = normalize_text(" ".join(part for part in [description, *cost_effects] if part))
    else:
        description_text = normalize_text(description or " ".join(cost_effects) or text)
    blocks.append(section("descricao", "Descrição", "aprimoramentos", [description_text] if description_text else []))
    return {
        "id": slugify(title),
        "title": title,
        "area": "aprimoramentos",
        "kind": "enhancement",
        "sectionId": "descricao",
        "sectionTitle": "Aprimoramento",
        "paragraphs": paragraphs,
        "sections": blocks,
    }


def split_race(title: str, paragraphs: list[str]) -> dict:
    description: list[str] = []
    powers: list[str] = []
    weaknesses: list[str] = []
    for paragraph in paragraphs:
        if re.match(r"(?i)^poderes poss", paragraph):
            powers.append(paragraph.split(":", 1)[1].strip() if ":" in paragraph else paragraph)
        elif re.match(r"(?i)^fraquezas", paragraph):
            weaknesses.append(paragraph.split(":", 1)[1].strip() if ":" in paragraph else paragraph)
        else:
            description.append(paragraph)
    blocks = [section("descricao", "Descrição", "racas", description)]
    if powers:
        blocks.append(section("poderes-possiveis", "Poderes Possíveis", "racas", powers))
    if weaknesses:
        blocks.append(section("fraquezas", "Fraquezas", "racas", weaknesses))
    return {
        "id": slugify(title),
        "title": title,
        "area": "racas",
        "kind": "race",
        "sectionId": "descricao",
        "sectionTitle": "Raça/Linhagem",
        "paragraphs": paragraphs,
        "sections": blocks,
    }


def build_pilot() -> dict:
    paragraphs = docx_paragraphs()

    lore_sections = [
        section("abertura", "Abertura", "cenarios_lore", collect(paragraphs, 5, 11)),
        make_section(paragraphs, "Instintos Despertos", "cenarios_lore", 12, 19),
        make_section(paragraphs, "Cultura e Costumes", "cenarios_lore", 27, 32),
        make_section(paragraphs, "As Leis", "cenarios_lore", 32, 39),
        make_section(paragraphs, "O Umbral", "cenarios_lore", 39, 44),
        make_section(paragraphs, "Os Ciganos", "cenarios_lore", 60, 65),
        make_section(paragraphs, "Modo de Vida", "cenarios_lore", 65, 68),
        make_section(paragraphs, "O Despertar da Fera", "cenarios_lore", 68, 74),
    ]

    rules_sections = [
        make_section(paragraphs, "Metamorfose", "regras_base", 19, 27),
        make_section(paragraphs, "Criação de um Fera", "regras_base", 74, 94),
        make_section(paragraphs, "Poderes Animais", "regras_base", 94, 102),
        section("fraquezas-introducao", "Fraquezas", "regras_base", collect_after(paragraphs, 208, 211)),
    ]

    ritual_ranges = [
        ("Adentrar no Umbral", 44, 48),
        ("Criação de Domínio", 48, 52),
        ("Chamado do Espírito Ancião", 52, 56),
        ("Fúria de Gaea", 56, 60),
    ]
    ritual_sections = [
        as_typed_item(make_section(paragraphs, title, "rituais", start, end), "ritual", "Ritual")
        for title, start, end in ritual_ranges
    ]

    power_ranges = [
        ("Reprodutor", 102, 106),
        ("Pele Grossa", 106, 113),
        ("Aquático", 113, 117),
        ("Sangue Frio", 117, 120),
        ("Sombras", 120, 125),
        ("Aumento de Atributos", 125, 135),
        ("Garras", 135, 138),
        ("Regeneração", 138, 142),
        ("Sentir o Sobrenatural", 142, 148),
        ("Asas", 148, 154),
        ("Peçonha", 154, 159),
        ("Sentidos Aguçados", 159, 162),
        ("Chifres", 162, 167),
        ("Comunicação Animal", 167, 173),
        ("Presas", 173, 177),
        ("Bico", 177, 180),
        ("Visão Noturna", 180, 184),
        ("Matilha", 184, 189),
        ("Inspirar Terror", 189, 197),
        ("Teia", 197, 208),
    ]
    power_sections = [
        split_level_sections(title, "poderes", collect_after(paragraphs, start, end), "power")
        for title, start, end in power_ranges
    ]

    weakness_ranges = [
        ("Época de Transformação", 211, 214),
        ("Vulnerável", 214, 217),
        ("Inconsciência", 217, 220),
        ("Fome", 220, 222),
        ("Transmissor", 222, 225),
        ("Incapacidade de Assumir Forma", 225, 228),
        ("Forma Perpétua", 228, 231),
        ("Transformação Trocada", 231, 234),
        ("Pânico", 234, 237),
        ("Reação a Estímulos", 237, 240),
        ("Fala Limitada", 240, 243),
        ("Instintividade", 243, 246),
        ("Decapitação", 246, 249),
        ("Espinheiro", 249, 252),
        ("Ligação a Terra", 252, 254),
    ]
    weakness_sections = [make_section(paragraphs, title, "regras_base", start, end) for title, start, end in weakness_ranges]

    enhancement_ranges = [
        ("Poder Elevado", 257, 264),
        ("Elo duplo", 264, 271),
        ("Escolhido", 271, 277),
        ("Conhecimento do Umbral", 277, 283),
        ("Adentrar no Umbral", 283, 288),
    ]
    enhancement_sections = [
        split_cost_sections(title, collect_after(paragraphs, start, end))
        for title, start, end in enhancement_ranges
    ]

    race_ranges = [
        ("Nagas", 291, 298),
        ("Beliors", 298, 306),
        ("Reflictys", 306, 315),
        ("Minotauros", 315, 323),
        ("Herats", 323, 331),
        ("Licantropos", 331, 342),
        ("Pantros", 342, 349),
        ("Garudas", 349, 356),
        ("Bastet", 356, 363),
        ("Rocs", 363, 370),
        ("Defensores do Ragnarok", 370, 377),
        ("Garras de Sharikan", 377, 385),
        ("Croatan", 385, 392),
        ("Parentes", 392, 399),
        ("Harpias", 399, 408),
        ("Filhos de Aracne", 408, 417),
        ("Crias do Caos", 417, 423),
    ]
    race_sections = [
        split_race(title, collect_after(paragraphs, start, end))
        for title, start, end in race_ranges
    ]

    groups = [
        {
            "id": "animalidade-feras-lore",
            "title": "Animalidade",
            "kind": "setting",
            "area": "cenarios_lore",
            "sectionTitle": "Cenário",
            "sections": lore_sections,
        },
        {
            "id": "animalidade-regras",
            "title": "Regra base - Animalidade",
            "kind": "ruleset",
            "area": "regras_base",
            "sectionTitle": "Regra Base",
            "sections": rules_sections + weakness_sections,
        },
    ]

    sections = ritual_sections + power_sections + enhancement_sections + race_sections
    area_counts: dict[str, int] = {}
    for group in groups:
        area_counts[group["area"]] = area_counts.get(group["area"], 0) + 1
    for item in sections:
        area_counts[item["area"]] = area_counts.get(item["area"], 0) + 1

    return {
        "version": 1,
        "status": "pilot_review",
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "source": SOURCE,
        "sourceFile": SOURCE_PATH.name,
        "sourcePath": str(SOURCE_PATH.relative_to(ROOT)),
        "title": "Animalidade",
        "summary": "Suplemento sobre Feras, metamorfose, poderes animais, fraquezas, aprimoramentos e linhagens prontas.",
        "areas": sorted(area_counts),
        "groups": groups,
        "sections": sections,
        "areaCounts": area_counts,
        "reviewNotes": [
            "Piloto inicial por faixas do DOCX.",
            "Fraquezas foram tratadas provisoriamente como regras base, pois ainda não há categoria lateral própria para desvantagens/fraquezas.",
            "Feras prontos foram tratados como raças/linhagens.",
        ],
    }


def main() -> None:
    payload = build_pilot()
    write_json(OUT_PATH, payload)
    write_json(DOCS_OUT_PATH, payload)
    print(json.dumps({"source": payload["source"], "areas": payload["areaCounts"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
