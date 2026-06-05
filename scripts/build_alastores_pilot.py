from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Iterable

from docx import Document

from common import ROOT, slugify, write_json


SOURCE_PATH = next((ROOT / "Livros" / "word" / "feito").glob("Alastores*.docx"))
SOURCE = "alastores-a-justica-infernal"
OUT_PATH = ROOT / "data" / "pilot" / f"{SOURCE}.json"
DOCS_OUT_PATH = ROOT / "docs" / "assets" / "data" / "pilot" / f"{SOURCE}.json"


def normalize_text(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = text.replace("“", '"').replace("”", '"').replace("’", "'")
    text = text.replace("Jusiça", "Justiça")
    text = text.replace("Indtrodução", "Introdução")
    text = text.replace("Indece", "Índice")
    text = text.replace("Objsetos", "Objetos")
    text = text.replace("Jurisprudencia", "Jurisprudência")
    text = text.replace("Cami nho", "Caminho")
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return text


def merge_fragments(previous: str, current: str) -> str:
    if previous.endswith("-") and current[:1].islower():
        return normalize_text(f"{previous[:-1]}{current}")
    if current.startswith("-") and previous and previous[-1].isalpha():
        return normalize_text(f"{previous}{current[1:]}")
    return normalize_text(f"{previous} {current}")


def should_join(previous: str, current: str) -> bool:
    if not previous or not current:
        return False
    if current.startswith("+") and not previous.endswith((".", "!", "?", ":", ";", '"')):
        return True
    if previous.endswith("-") and current[:1].islower():
        return True
    if current.startswith("-") and previous[-1].isalpha():
        return True
    if current[:1].islower() and not previous.endswith((".", "!", "?", ":", ";", '"')):
        return True
    if len(current) < 65 and current[:1].islower():
        return True
    if previous.endswith(("um", "do", "da", "de", "em", "por", "com", "para")):
        return True
    return False


def clean_paragraphs(values: Iterable[str]) -> list[str]:
    paragraphs: list[str] = []
    for value in values:
        text = normalize_text(value)
        if not text:
            continue
        if re.fullmatch(r"\d+(?:\.\d+)?", text):
            continue
        if text.startswith("EMAIL:") or text == "Lao Tzi":
            continue
        if paragraphs and should_join(paragraphs[-1], text):
            paragraphs[-1] = merge_fragments(paragraphs[-1], text)
        else:
            paragraphs.append(text)
    return paragraphs


def docx_paragraphs() -> list[str]:
    document = Document(SOURCE_PATH)
    return [paragraph.text for paragraph in document.paragraphs]


def section(section_id: str, title: str, area: str, paragraphs: list[str]) -> dict:
    return {
        "id": section_id,
        "title": title,
        "area": area,
        "paragraphs": paragraphs,
    }


def split_enhancement(title: str, paragraphs: list[str]) -> dict:
    cost_entries: list[str] = []
    cost_effects: list[str] = []
    cost_pattern = re.compile(r"(?i)\b(\d+\s+pontos?|pontos?|ponto):\s*")
    inferred_cost = 1
    text = normalize_text(" ".join(paragraphs))
    matches = list(cost_pattern.finditer(text))

    if matches:
        description = normalize_text(text[: matches[0].start()])
        for index, match in enumerate(matches):
            label = match.group(1)
            label_key = label.casefold().strip()
            explicit_number = re.match(r"(\d+)", label_key)
            if explicit_number:
                inferred_cost = max(inferred_cost, int(explicit_number.group(1)) + 1)
            elif label_key in {"ponto", "pontos"}:
                label = f"{inferred_cost} {'ponto' if inferred_cost == 1 else 'pontos'}"
                inferred_cost += 1
            next_start = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            effect = text[match.end():next_start].strip()
            cost_entries.append(
                {
                    "label": normalize_text(label),
                    "effect": normalize_text(effect),
                }
            )
            if effect:
                cost_effects.append(normalize_text(effect))
    else:
        description = text

    sections = []
    if cost_entries:
        cost_paragraphs = [
            entry["label"] if len(cost_entries) == 1 or not entry["effect"] else f"{entry['label']}: {entry['effect']}"
            for entry in cost_entries
        ]
        sections.append(section("custo", "Custo", "aprimoramentos", cost_paragraphs))
    if len(cost_entries) == 1:
        description_text = normalize_text(" ".join(part for part in [description, *cost_effects] if part))
    else:
        description_text = normalize_text(description or " ".join(cost_effects) or text)
    sections.append(section("descricao", "Descrição", "aprimoramentos", [description_text] if description_text else []))

    return {
        "id": slugify(title),
        "title": title,
        "area": "aprimoramentos",
        "kind": "enhancement",
        "sectionId": "descricao",
        "sectionTitle": "Aprimoramento",
        "paragraphs": paragraphs,
        "sections": sections,
    }


def split_power(title: str, paragraphs: list[str]) -> dict:
    prereq: list[str] = []
    body = list(paragraphs)
    if body and re.fullmatch(r"\(.+\)", body[0]):
        prereq.append(body.pop(0).strip("()"))

    text = " ".join(body)
    text = re.sub(r"\bNivel\b", "Nível", text)
    marker = re.compile(r"(?i)\bN[íi]vel\s+(\d+):\s*")
    matches = list(marker.finditer(text))

    sections = []
    if prereq:
        sections.append(section("pre-requisito", "Pré-requisito", "poderes", prereq))

    if matches:
        for index, match in enumerate(matches):
            level = match.group(1)
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            content = normalize_text(text[start:end])
            if not content:
                continue
            sections.append(section(f"nivel-{level}-{index + 1}", f"Nível {level}", "poderes", [content]))
    elif body:
        sections.append(section("descricao", "Descrição", "poderes", body))

    return {
        "id": slugify(title),
        "title": title,
        "area": "poderes",
        "kind": "power",
        "sectionId": "poder",
        "sectionTitle": "Poder",
        "paragraphs": paragraphs,
        "sections": sections,
    }


def collect(paragraphs: list[str], start: int, end: int) -> list[str]:
    return clean_paragraphs(paragraphs[start:end])


def collect_after_heading(paragraphs: list[str], heading_index: int, end: int) -> list[str]:
    return collect(paragraphs, heading_index + 1, end)


def make_section(paragraphs: list[str], title: str, area: str, start: int, end: int) -> dict:
    return section(slugify(title), title, area, collect_after_heading(paragraphs, start, end))


def make_direct_section(paragraphs: list[str], title: str, area: str, start: int, end: int) -> dict:
    return section(slugify(title), title, area, collect(paragraphs, start, end))


EQUIPMENT_TITLES = [
    "Soro da Verdade",
    "Amuleto de Paralização",
    "Bússola Rastreadora",
    "Olhos da Alma",
    "Shakhor",
    "Granada de Água Maldita",
    "Arrebatador",
    "Joia dos Pensamentos",
    "Caixa e Besouro",
    "Areia de Agaures",
    "Grilhões dos Condenados",
    "Manto Negro",
    "Espada dos Cruzados",
    "Espada Ajanti",
    "Amuleto de Pena",
    "Incenso da Revelação",
    "Bafo de Dragão",
    "Tebori",
    "Amuleto de Thanatos",
    "Trogus Mali",
    "Arrebatador Consectetur",
    "Manto de Etlich",
]


def split_equipment_items(paragraphs: list[str], start: int, end: int) -> list[dict]:
    text = normalize_text(" ".join(collect(paragraphs, start, end)))
    title_pattern = "|".join(re.escape(title) for title in sorted(EQUIPMENT_TITLES, key=len, reverse=True))
    marker = re.compile(rf"\b({title_pattern})(?::|\.)\s*")
    matches = list(marker.finditer(text))
    items: list[dict] = []

    for index, match in enumerate(matches):
        title = match.group(1)
        next_start = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        description = normalize_text(text[match.end():next_start])
        sections = []
        paragraphs_out = [description] if description else []
        if title == "Tebori":
            option_matches = list(re.finditer(r"\*([^*]+)", description))
            if option_matches:
                description_text = normalize_text(description[: option_matches[0].start()])
                options = [normalize_text(match.group(1)) for match in option_matches if normalize_text(match.group(1))]
                paragraphs_out = ([description_text] if description_text else []) + options
                sections.append(section("descricao", "Descrição", "itens_equipamentos", [description_text] if description_text else []))
                sections.append(section("opcoes", "Opções", "itens_equipamentos", options))
        if not sections:
            sections = [section("descricao", "Descrição", "itens_equipamentos", paragraphs_out)]
        items.append(
            {
                "id": slugify(title),
                "title": title,
                "area": "itens_equipamentos",
                "kind": "equipment",
                "sectionId": "descricao",
                "sectionTitle": "Item",
                "paragraphs": paragraphs_out,
                "sections": sections,
            }
        )

    return items


def split_character_block(paragraphs: list[str]) -> tuple[list[str], list[str]]:
    ficha: list[str] = []
    habilidades: list[str] = []
    for paragraph in paragraphs:
        mixed = re.match(r"^(.*?\bPVs?\b)(?:\s+)(Pode .+|Regenera .+|Possui .+)$", paragraph)
        if mixed:
            ficha.append(normalize_text(mixed.group(1)))
            habilidades.append(normalize_text(mixed.group(2)))
            continue
        if re.match(r"^(?:Pode|Recebe|Regenera|Possui|Caso|Tem)\b", paragraph):
            habilidades.append(paragraph)
            continue
        ficha.append(paragraph)
    return ficha, habilidades


def stat_block(paragraphs: list[str]) -> dict:
    text = " ".join(paragraphs)
    attributes = {}
    for key in ["CON", "FR", "DEX", "AGI", "INT", "WILL", "CAR", "PER"]:
        match = re.search(rf"\b{key}\s+(\d+)", text)
        if match:
            attributes[key] = int(match.group(1))
    vitals = {}
    ip = re.search(r"\bIP\s+([\w()+-]+)", text)
    pv = re.search(r"\b(\d+)\s*PVs?\b", text)
    if pv:
        vitals["PV"] = pv.group(1)
    if ip:
        vitals["IP"] = ip.group(1)
    skill_lines = [
        paragraph
        for paragraph in paragraphs
        if not re.search(r"\b(?:CON|FR|DEX|AGI|INT|WILL|CAR|PER)\s+\d+", paragraph)
    ]
    return {
        "attributes": attributes,
        "vitals": vitals,
        "skills": "\n".join(skill_lines),
        "special": [],
    }


def make_character(paragraphs: list[str], name: str, start: int, end: int) -> dict:
    block = collect_after_heading(paragraphs, start, end)
    ficha, habilidades = split_character_block(block)
    sections = [section("ficha", "Ficha", "criaturas_npcs", ficha)]
    if habilidades:
        sections.append(section("habilidades", "Habilidades", "criaturas_npcs", habilidades))
    return {
        "id": slugify(name),
        "name": name,
        "type": "character_npc",
        "role": "Criatura/NPC",
        "classifications": [
            {
                "area": "criaturas_npcs",
                "confidence": 0.88,
                "reason": "Ficha com atributos, ataques, PV/IP e poderes.",
            }
        ],
        "statBlock": stat_block(ficha),
        "sections": sections,
    }


def build_pilot() -> dict:
    paragraphs = docx_paragraphs()

    lore_sections = [
        make_direct_section(paragraphs, "Introdução", "cenarios_lore", 69, 72),
        make_direct_section(paragraphs, "Origem", "cenarios_lore", 76, 83),
        make_direct_section(paragraphs, "O Índice Carmesim", "cenarios_lore", 86, 91),
        make_direct_section(paragraphs, "A Caçada", "cenarios_lore", 93, 99),
        make_section(paragraphs, "Os Coenobiuns", "cenarios_lore", 99, 104),
        make_section(paragraphs, "A Fidelitas Ordinis", "cenarios_lore", 104, 108),
        make_section(paragraphs, "Veniam Peto", "cenarios_lore", 108, 119),
        make_section(paragraphs, "No Inferno", "cenarios_lore", 119, 121),
        make_section(paragraphs, "A Milícia de Ferro", "cenarios_lore", 121, 127),
        make_section(paragraphs, "Os Templários Caídos", "cenarios_lore", 127, 133),
        make_section(paragraphs, "As leis dos Traidores", "cenarios_lore", 133, 145),
        make_section(paragraphs, "O exército do Escorpião Negro", "cenarios_lore", 145, 151),
        make_section(paragraphs, "O Reich", "cenarios_lore", 151, 160),
    ]

    power_ranges = [
        ("Veredictum", 160, 172),
        ("Cainismo", 172, 181),
        ("Esparciatas", 181, 189),
        ("Commilitonum Nigrus", 189, 208),
        ("Flagelo", 208, 224),
        ("Arrebate", 224, 232),
        ("Defesas Especiais", 232, 238),
    ]
    power_sections = [
        split_power(title, collect_after_heading(paragraphs, start, end))
        for title, start, end in power_ranges
    ]

    enhancement_ranges = [
        ("Alastor", 243, 247),
        ("Alastor Venerável", 247, 251),
        ("Burocracia Infernal", 251, 257),
        ("Caçador Experiente", 257, 261),
        ("Contatos e Aliados", 261, 271),
        ("Direito e Jurisprudência", 271, 278),
        ("Igreja", 278, 285),
        ("Luciferianos", 285, 288),
        ("Objetos Mágicos", 288, 297),
        ("O Olho Alastor", 297, 302),
        ("Passagem Livre", 302, 306),
        ("Submundo", 306, 312),
        ("Treinamento: Sebbiti", 312, 317),
        ("Treinamento: Seddim", 317, 319),
        ("Treinamento: Azazel", 319, 325),
    ]
    enhancement_sections = [
        split_enhancement(title, collect_after_heading(paragraphs, start, end))
        for title, start, end in enhancement_ranges
    ]

    class_sections = [
        make_direct_section(paragraphs, "Cainitas", "classes", 329, 331),
        make_section(paragraphs, "Ordem do Escorpião Negro", "classes", 358, 383),
        make_section(paragraphs, "Milícia de Ferro", "classes", 383, 392),
        make_section(paragraphs, "Irmandade DeMoley", "classes", 392, 400),
    ]

    equipment_sections = split_equipment_items(paragraphs, 405, 440)

    ritual_ranges = [
        ("Convocar Lukhavim", 446, 453),
        ("Convocar Duinum", 453, 458),
        ("Dammant Indicium", 458, 463),
        ("Sellas locum", 463, 466),
        ("Ipsa Nomina", 466, 474),
    ]
    ritual_sections = [make_direct_section(paragraphs, title, "rituais", start, end) for title, start, end in ritual_ranges]

    notable_sections = [
        make_section(paragraphs, "Alastor", "cenarios_lore", 477, 480),
        make_section(paragraphs, "Azazel", "cenarios_lore", 480, 482),
        make_section(paragraphs, "Arioch", "cenarios_lore", 482, 484),
        make_section(paragraphs, "Os Sebbiti", "cenarios_lore", 484, 487),
        make_section(paragraphs, "Seddim", "cenarios_lore", 487, 490),
        make_section(paragraphs, "Mekkhelot", "cenarios_lore", 490, 500),
    ]

    creature_ranges = [
        ("Demônio Menor", 500, 506),
        ("Death Knight", 506, 514),
        ("Succubi/Inccubi", 514, 522),
        ("Demônio Capanga", 522, 528),
        ("Anjo Caído", 528, 536),
        ("Satanista", 536, 541),
        ("Duque Infernal", 541, 548),
    ]
    characters = [make_character(paragraphs, name, start, end) for name, start, end in creature_ranges]

    groups = [
        {
            "id": "alastores-justica-infernal-lore",
            "title": "Alastores - A Justiça Infernal",
            "kind": "setting",
            "area": "cenarios_lore",
            "sectionTitle": "Cenário",
            "sections": lore_sections + notable_sections,
        },
    ]

    sections = power_sections + enhancement_sections + class_sections + equipment_sections + ritual_sections
    area_counts: dict[str, int] = {}
    for group in groups:
        area_counts[group["area"]] = area_counts.get(group["area"], 0) + 1
    for item in sections:
        area_counts[item["area"]] = area_counts.get(item["area"], 0) + 1
    if characters:
        area_counts["criaturas_npcs"] = area_counts.get("criaturas_npcs", 0) + len(characters)

    return {
        "version": 1,
        "status": "pilot_review",
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "source": SOURCE,
        "sourceFile": SOURCE_PATH.name,
        "sourcePath": str(SOURCE_PATH.relative_to(ROOT)),
        "title": "Alastores - A Justiça Infernal",
        "summary": "Suplemento sobre a Ordem Caçadora dos Alastores, suas leis infernais, poderes, aprimoramentos, kits, rituais, objetos e fichas.",
        "areas": sorted(area_counts),
        "groups": groups,
        "sections": sections,
        "characters": characters,
        "areaCounts": area_counts,
        "reviewNotes": [
            "Piloto inicial por faixas do DOCX.",
            "Lore foi agrupado como uma entidade maior.",
            "Objetos mágicos foram separados em entradas individuais por título.",
            "Fichas de criaturas/NPCs foram separadas de guerreiros notáveis narrativos.",
        ],
    }


def main() -> None:
    payload = build_pilot()
    write_json(OUT_PATH, payload)
    write_json(DOCS_OUT_PATH, payload)
    print(json.dumps({"source": payload["source"], "areas": payload["areaCounts"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
