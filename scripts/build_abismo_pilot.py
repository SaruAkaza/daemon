from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from docx import Document

from common import ROOT, slugify, write_json


SOURCE = "abismo"
SOURCE_PATH = ROOT / "Livros" / "word" / "Abismo.docx"
DONE_PATH = ROOT / "Livros" / "word" / "feito" / "Abismo.docx"
OUT_PATH = ROOT / "data" / "pilot" / f"{SOURCE}.json"
DOCS_OUT_PATH = ROOT / "docs" / "assets" / "data" / "pilot" / f"{SOURCE}.json"

GENERIC_HEADINGS = {
    "Aparência",
    "Estatísticas",
    "Seguidores",
    "Abismais",
    "Habitantes",
    "Os Círculos",
    "Círculos",
    "O Povo",
    "A Fortaleza",
    "Locais de Interesse",
    "Os deuses",
    "Kit",
    "Iniciação",
    "Interpretação",
    "Relações",
    "Aprimoramentos por nível:",
    "Positivos",
    "Negativos",
}


def normalize_text(text: str) -> str:
    text = text.replace("\u00a0", " ").replace("\t", " ")
    text = text.replace("Ark- a- nun", "Ark-a-nun")
    text = text.replace("Yara- ma- yha- who", "Yara-ma-yha-who")
    text = text.replace("Yara- ma- yha-who", "Yara-ma-yha-who")
    text = text.replace("º ", "º ")
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"\(\s+", "(", text)
    text = re.sub(r"\s+\)", ")", text)
    return text


def heading_level(style_name: str) -> int | None:
    if style_name == "Title":
        return 0
    match = re.fullmatch(r"Heading (\d+)", style_name)
    if match:
        return int(match.group(1))
    return None


def docx_entries() -> list[dict]:
    path = SOURCE_PATH if SOURCE_PATH.exists() else DONE_PATH
    document = Document(path)
    entries = []
    for index, paragraph in enumerate(document.paragraphs):
        text = normalize_text(paragraph.text)
        if not text:
            continue
        level = heading_level(paragraph.style.name)
        entries.append(
            {
                "index": index,
                "text": text,
                "style": paragraph.style.name,
                "level": level,
            }
        )
    return entries


def next_heading(entries: list[dict], pos: int, max_level: int) -> int:
    for index in range(pos + 1, len(entries)):
        level = entries[index]["level"]
        if level is not None and level <= max_level:
            return index
    return len(entries)


def body_between(entries: list[dict], start: int, end: int) -> list[str]:
    body = []
    for entry in entries[start:end]:
        if entry["level"] is None:
            text = entry["text"]
            if re.fullmatch(r"\d+(?:\.\d+)?", text):
                continue
            if re.fullmatch(r"[.]+", text):
                continue
            body.append(text)
    return merge_fragments(body)


def direct_body_after(entries: list[dict], start: int) -> list[str]:
    body = []
    for entry in entries[start + 1 :]:
        if entry["level"] is not None:
            break
        text = entry["text"]
        if re.fullmatch(r"\d+(?:\.\d+)?", text):
            continue
        if re.fullmatch(r"[.]+", text):
            continue
        body.append(text)
    return merge_fragments(body)


def merge_fragments(paragraphs: list[str]) -> list[str]:
    merged: list[str] = []
    for paragraph in paragraphs:
        if not paragraph:
            continue
        if merged and should_join(merged[-1], paragraph):
            merged[-1] = normalize_text(f"{merged[-1]} {paragraph}")
        else:
            merged.append(paragraph)
    return merged


def should_join(previous: str, current: str) -> bool:
    if previous.endswith("-") and current[:1].islower():
        return True
    if current[:1].islower() and not previous.endswith((".", "!", "?", ":", ";", '"')):
        return True
    if previous.endswith(("de", "da", "do", "das", "dos", "em", "por", "com", "para")):
        return True
    return False


def block(section_id: str, title: str, area: str, paragraphs: list[str]) -> dict:
    return {
        "id": section_id,
        "title": title,
        "area": area,
        "paragraphs": paragraphs,
    }


def section_item(title: str, area: str, kind: str, paragraphs: list[str], section_title: str) -> dict:
    sections = [block("descricao", "Descrição", area, paragraphs)]
    if area == "aprimoramentos":
        sections = enhancement_sections(paragraphs)
    return {
        "id": slugify(title),
        "title": title,
        "area": area,
        "kind": kind,
        "sectionId": "descricao",
        "sectionTitle": section_title,
        "paragraphs": paragraphs,
        "sections": sections,
    }


def parse_cost_line(text: str) -> tuple[str, str] | None:
    match = re.match(r"^\s*-?\s*(\d+\s+Pontos?|Pontos?|Ponto|pontos?|ponto)\s*:\s*(.+)$", text, re.IGNORECASE)
    if not match:
        return None
    label = normalize_text(match.group(1))
    if label.casefold() in {"ponto", "pontos"}:
        label = "1 Ponto"
    if text.lstrip().startswith("-") and re.match(r"^\d", label):
        label = f"-{label}"
    return label, normalize_text(match.group(2))


def enhancement_sections(paragraphs: list[str]) -> list[dict]:
    description: list[str] = []
    cost_entries: list[tuple[str, str]] = []
    for paragraph in paragraphs:
        parsed = parse_cost_line(paragraph)
        if parsed:
            cost_entries.append(parsed)
        elif cost_entries and not paragraph.endswith(":"):
            label, effect = cost_entries[-1]
            cost_entries[-1] = (label, normalize_text(f"{effect} {paragraph}"))
        else:
            description.append(paragraph)

    if not cost_entries:
        return [block("descricao", "Descrição", "aprimoramentos", paragraphs)]

    if len(cost_entries) == 1:
        cost_paragraphs = [cost_entries[0][0]]
        desc_paragraphs = description + [cost_entries[0][1]]
    else:
        cost_paragraphs = [f"{label}: {effect}" for label, effect in cost_entries]
        desc_paragraphs = description

    sections = [block("custo", "Custo", "aprimoramentos", cost_paragraphs)]
    if desc_paragraphs:
        sections.append(block("descricao", "Descrição", "aprimoramentos", desc_paragraphs))
    return sections


def collect_child_blocks(entries: list[dict], start_heading: str, stop_headings: set[str], area: str) -> list[dict]:
    start = next(i for i, entry in enumerate(entries) if entry["text"] == start_heading)
    output = []
    index = start + 1
    while index < len(entries):
        entry = entries[index]
        if entry["text"] in stop_headings:
            break
        if entry["level"] is not None and entry["level"] >= 3 and entry["text"] not in GENERIC_HEADINGS:
            end = next_heading(entries, index, entry["level"])
            paragraphs = body_between(entries, index + 1, end)
            if paragraphs:
                output.append(block(slugify(entry["text"]), entry["text"], area, paragraphs))
            index = end
            continue
        index += 1
    return output


def collect_named_items(
    entries: list[dict],
    start_heading: str,
    stop_heading: str,
    heading_levels: set[int],
    area: str,
    kind: str,
    section_title: str,
) -> list[dict]:
    start = next(i for i, entry in enumerate(entries) if entry["text"] == start_heading)
    stop = next(i for i, entry in enumerate(entries[start + 1 :], start + 1) if entry["text"] == stop_heading)
    items = []
    for index in range(start + 1, stop):
        entry = entries[index]
        if entry["level"] not in heading_levels or entry["text"] in GENERIC_HEADINGS:
            continue
        end = next_heading(entries, index, entry["level"])
        paragraphs = body_between(entries, index + 1, min(end, stop))
        if paragraphs:
            items.append(section_item(entry["text"], area, kind, paragraphs, section_title))
    return items


def collect_kits(entries: list[dict]) -> list[dict]:
    return collect_named_items(entries, "Kits Aprimorados", "Cultos", {6}, "classes", "class", "Kit")


def collect_enhancements(entries: list[dict]) -> list[dict]:
    positives = collect_named_items(entries, "Positivos", "Negativos", {7}, "aprimoramentos", "enhancement", "Aprimoramento")
    negatives = collect_named_items(entries, "Negativos", "Poderes", {7}, "aprimoramentos", "enhancement", "Aprimoramento")
    return positives + negatives


def collect_weakness_rule_blocks(entries: list[dict]) -> list[dict]:
    start = next(i for i, entry in enumerate(entries) if entry["text"] == "Fraquezas")
    stop = next(i for i, entry in enumerate(entries[start + 1 :], start + 1) if entry["text"] == "Capítulo VIII")
    blocks = []
    for index in range(start + 1, stop):
        entry = entries[index]
        if entry["level"] != 7 or entry["text"] in GENERIC_HEADINGS:
            continue
        end = next_heading(entries, index, entry["level"])
        paragraphs = body_between(entries, index + 1, min(end, stop))
        if paragraphs:
            blocks.append(block(slugify(f"fraqueza-{entry['text']}"), f"Fraqueza: {entry['text']}", "regras_base", paragraphs))
    return blocks


def collect_powers(entries: list[dict]) -> list[dict]:
    return collect_named_items(entries, "Poderes", "Fraquezas", {6}, "poderes", "power", "Poder")


def collect_power_rule_blocks(entries: list[dict]) -> list[dict]:
    start = next(i for i, entry in enumerate(entries) if entry["text"] == "Poderes")
    stop = next(i for i, entry in enumerate(entries[start + 1 :], start + 1) if entry["text"] == "Fraquezas")
    blocks = []
    for index in range(start + 1, stop):
        entry = entries[index]
        if entry["level"] != 6 or entry["text"] in GENERIC_HEADINGS:
            continue
        end = next_heading(entries, index, entry["level"])
        paragraphs = body_between(entries, index + 1, min(end, stop))
        if paragraphs:
            blocks.append(block(slugify(f"poder-abissal-{entry['text']}"), f"Poder abissal: {entry['text']}", "regras_base", paragraphs))
    return blocks


def has_stat_block(paragraphs: list[str]) -> bool:
    text = " ".join(paragraphs)
    return bool(re.search(r"\bCON\s+\d+", text) and re.search(r"\b(?:FR|DEX|AGI|INT|WILL|PER)\s+\d+", text))


ATTRIBUTES = ("CON", "FR", "DEX", "AGI", "INT", "WILL", "PER", "CAR")
SKILL_TERMS = (
    "Armas Brancas",
    "Barganha",
    "Briga",
    "Conhecimento Proibido",
    "Diplomacia",
    "Escutar",
    "Esquiva",
    "Estratégia",
    "Furtividade",
    "Idiomas",
    "Intimidação",
    "Investigação",
    "Lábia",
    "Liderança",
    "Manha",
    "Oculto",
    "Pesquisa",
    "Rastreio",
    "Rituais",
    "Sobrevivência",
    "Spiritum",
    "Tortura",
)


def is_stat_or_combat_line(text: str) -> bool:
    if re.search(r"\b(?:CON|FR|DEX|AGI|INT|WILL|PER|CAR)\s+\d+", text):
        return True
    if re.search(r"\b(?:PVs?|IP|#\s*Ataques?)\b", text):
        return True
    if re.search(r"\b(?:Perícias|Ataques?|Dano|dano)\s*:", text, re.IGNORECASE):
        return True
    if is_attack_line(text):
        return True
    if is_skill_line(text):
        return True
    return False


def is_ability_line(text: str) -> bool:
    if not re.search(r"\b(?:\d+d\d+|dano|teste|vezes por dia|por rodada|Pontos de Magia|veneno)\b", text, re.IGNORECASE):
        return False
    if re.match(r"^(?:Pode|Podem|Caso|Seu|Sua|As caudas|Tem |Todas |Auxiliada|Uma vez|Deve-se|Alimenta-se|- Pode)\b", text):
        return True
    return bool(re.search(r"\bpode\b", text, re.IGNORECASE))


def is_attack_line(text: str) -> bool:
    if is_ability_line(text):
        return False
    if not re.search(r"\b\d+d\d+\b", text, re.IGNORECASE):
        return False
    return bool(re.search(r"\b(?:%|\d+/\d+|Dentes|Boca|Garras|Chifres|Bico|Lança|Espada|Adaga|Bastão|Toque|Hálito|Mordida|Tentáculos?)\b", text))


def is_skill_line(text: str) -> bool:
    if is_ability_line(text):
        return False
    if re.search(r"\b\d+/\d+\b", text):
        return True
    if len(re.findall(r"\d+%", text)) >= 2:
        return True
    if re.search(r"\b\d+%\b", text) and any(term in text for term in SKILL_TERMS):
        return True
    return False


def is_attribute_or_vital_line(text: str) -> bool:
    return bool(
        re.search(r"\b(?:CON|FR|DEX|AGI|INT|WILL|PER|CAR)\s+\d+", text)
        or re.search(r"\b(?:PVs?|IP|#\s*Ataques?)\b", text)
    )


def extract_stat_block(paragraphs: list[str]) -> dict:
    text = " ".join(paragraphs)
    attributes = {}
    for attr in ATTRIBUTES:
        match = re.search(rf"\b{attr}\s+(\d+(?:\s*\[[^\]]+\])?)", text)
        if match:
            value = normalize_text(match.group(1))
            attributes[attr] = int(value) if value.isdigit() else value

    vitals = {}
    pv_match = re.search(r"\bPVs?\s+([0-9]+(?:\s*\+\s*[0-9]+)?)", text, re.IGNORECASE)
    if pv_match:
        vitals["PV"] = normalize_text(pv_match.group(1).replace(" ", ""))
    ip_match = re.search(r"\bIP\s+([^,.;]+)", text, re.IGNORECASE)
    if ip_match:
        vitals["IP"] = normalize_text(ip_match.group(1))
    attack_match = re.search(r"#\s*Ataques?\s+([^,.;]+)", text, re.IGNORECASE)
    if attack_match:
        vitals["Ataques"] = normalize_text(attack_match.group(1))

    skills = []
    special = []
    for paragraph in paragraphs:
        if re.search(r"\bPerícias\s*:", paragraph, re.IGNORECASE):
            skills.append(normalize_text(re.sub(r"^.*?\bPerícias\s*:\s*", "", paragraph, flags=re.IGNORECASE)))
        elif re.search(r"\b(?:Ataques?|Dano|dano)\s*:", paragraph, re.IGNORECASE) or is_attack_line(paragraph):
            skills.append(paragraph)
        elif is_skill_line(paragraph) and not is_attribute_or_vital_line(paragraph):
            skills.append(paragraph)

    return {
        "attributes": attributes,
        "vitals": vitals,
        "attributesText": "".join(f"{key} {value}" for key, value in attributes.items()),
        "skills": "\n".join(dict.fromkeys(skills)),
        "special": [],
    }


def character_sections(paragraphs: list[str]) -> list[dict]:
    stat_lines = [paragraph for paragraph in paragraphs if is_stat_or_combat_line(paragraph)]
    ability_lines = [paragraph for paragraph in paragraphs if is_ability_line(paragraph)]
    description = [
        paragraph
        for paragraph in paragraphs
        if not is_stat_or_combat_line(paragraph) and not is_ability_line(paragraph)
    ]
    sections = []
    if stat_lines:
        sections.append(block("ficha", "Ficha", "criaturas_npcs", stat_lines))
    if ability_lines:
        sections.append(block("habilidades", "Habilidades", "criaturas_npcs", ability_lines))
    if description:
        sections.append(block("descricao", "Descrição", "criaturas_npcs", description))
    return sections


def character_item(title: str, paragraphs: list[str]) -> dict:
    return {
        "id": slugify(title),
        "name": title,
        "type": "character_npc",
        "role": "Criatura/NPC",
        "classifications": ["Criaturas e NPCs"],
        "statBlock": extract_stat_block(paragraphs),
        "sections": character_sections(paragraphs),
    }


def collect_characters(entries: list[dict]) -> list[dict]:
    output = []
    seen = set()
    for index, entry in enumerate(entries):
        if entry["level"] not in {4, 5, 6, 7}:
            continue
        title = entry["text"]
        if title in GENERIC_HEADINGS or len(title) > 70:
            continue
        if re.match(r"^Pontos de Obscuridade:", title):
            continue
        end = next_heading(entries, index, entry["level"])
        paragraphs = direct_body_after(entries, index)
        if not has_stat_block(paragraphs):
            # Deuses e entidades maiores trazem a ficha em subtópicos como "Abismais" ou "Estatísticas".
            paragraphs = body_between(entries, index + 1, end)
        if not has_stat_block(paragraphs):
            continue
        if entry["index"] > 2020 and entry["level"] in {4, 5, 6} and not has_stat_block(direct_body_after(entries, index)):
            continue
        key = slugify(title)
        if key in seen:
            continue
        seen.add(key)
        output.append(character_item(title, paragraphs))
    return output


def build_pilot() -> dict:
    entries = docx_entries()
    source_path = SOURCE_PATH if SOURCE_PATH.exists() else DONE_PATH

    rules_sections = []
    for title in [
        "Introdução",
        "Uso dos",
        "Conhecimento Proibido: Abismo",
        "Conspirações Obscuras",
        "Horror Épico",
        "Terror",
        "Loucura",
        "Deterioração Física",
        "Decadência Espiritual",
    ]:
        match = next((i for i, entry in enumerate(entries) if entry["text"] == title), None)
        if match is None:
            continue
        end = next_heading(entries, match, entries[match]["level"] or 1)
        if title == "Conhecimento Proibido: Abismo":
            next_content = next(
                (i for i, entry in enumerate(entries[match + 1 :], match + 1) if entry["text"] == "Novos Aprimoramentos"),
                None,
            )
            if next_content is not None:
                end = min(end, next_content)
        paragraphs = body_between(entries, match + 1, end)
        if title == "Uso dos":
            title = "Uso dos Personagens"
            if paragraphs and paragraphs[0] == "Personagens":
                paragraphs = paragraphs[1:]
            elif paragraphs and paragraphs[0].startswith("Personagens "):
                paragraphs[0] = normalize_text(paragraphs[0].removeprefix("Personagens "))
        if paragraphs:
            rules_sections.append(block(slugify(title), title, "regras_base", paragraphs))
    rules_sections.extend(collect_power_rule_blocks(entries))
    rules_sections.extend(collect_weakness_rule_blocks(entries))

    lore_sections = []
    for title in [
        "Capítulo I: Origem das Trevas",
        "Capítulo II: O Abismo",
        "Capítulo III Deuses Negros e Suas",
        "Capítulo IV Filhos Bastardos das",
        "Cultos",
        "Sociedades Secretas e Cultos do Abismo",
        "Cultos Tenebrianos pelo Mundo",
        "Capítulo VI Filhos Renegados das",
    ]:
        match = next((i for i, entry in enumerate(entries) if entry["text"] == title), None)
        if match is None:
            continue
        end = next_heading(entries, match, entries[match]["level"] or 1)
        paragraphs = body_between(entries, match + 1, end)
        if paragraphs:
            lore_sections.append(block(slugify(title), title, "cenarios_lore", paragraphs))

    groups = [
        {
            "id": "abismo-regras-base",
            "title": "Regra base - Abismo",
            "kind": "ruleset",
            "area": "regras_base",
            "sectionTitle": "Regra Base",
            "sections": rules_sections,
        },
        {
            "id": "abismo-cenario-lore",
            "title": "Abismo",
            "kind": "setting",
            "area": "cenarios_lore",
            "sectionTitle": "Cenário",
            "sections": lore_sections,
        },
    ]

    sections = collect_kits(entries) + collect_enhancements(entries)
    characters = collect_characters(entries)

    area_counts: dict[str, int] = {}
    for group in groups:
        area_counts[group["area"]] = area_counts.get(group["area"], 0) + 1
    for item in sections:
        area_counts[item["area"]] = area_counts.get(item["area"], 0) + 1
    if characters:
        area_counts["criaturas_npcs"] = len(characters)

    return {
        "version": 1,
        "status": "pilot_review",
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "source": SOURCE,
        "sourceFile": source_path.name,
        "sourcePath": str(source_path.relative_to(ROOT)).replace("\\", "/"),
        "title": "Abismo",
        "summary": (
            "Suplemento de Trevas/Arkanun sobre o Abismo, Tenebras, Infernun, deuses negros, "
            "Geistkhalim, cultos, poderes, fraquezas e monstros."
        ),
        "areas": sorted(area_counts),
        "groups": groups,
        "sections": sections,
        "characters": characters,
        "areaCounts": area_counts,
        "reviewNotes": [
            "Piloto inicial por estilos do DOCX; livro amplo, requer revisão humana por categoria.",
            "Regras Base e Cenários e Lore foram aglutinados por livro.",
            "Kits, aprimoramentos com custo e fichas com atributos foram separados como itens individuais quando havia título claro.",
            "Poderes e fraquezas abissais foram mantidos como blocos internos de Regras Base por serem características/mecânicas de entidades, não poderes gerais de jogador.",
            "Antes de virar base final, revisar principalmente duplicidades entre deuses, abismais, cultistas e monstros.",
        ],
    }


def main() -> None:
    payload = build_pilot()
    write_json(OUT_PATH, payload)
    write_json(DOCS_OUT_PATH, payload)
    if SOURCE_PATH.exists():
        DONE_PATH.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(SOURCE_PATH), str(DONE_PATH))
    print(json.dumps({"source": payload["source"], "areas": payload["areaCounts"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
