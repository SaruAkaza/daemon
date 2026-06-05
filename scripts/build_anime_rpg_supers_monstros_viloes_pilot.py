from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from docx import Document

from common import ROOT, slugify, write_json


SOURCE = "anime-rpg-supers-monstros-viloes"
SOURCE_GLOB = "Anime RPG - Supers - Monstros*.docx"
DONE_NAME = "Anime RPG - Supers - Monstros e Vilões.docx"
OUT_PATH = ROOT / "data" / "pilot" / f"{SOURCE}.json"
DOCS_OUT_PATH = ROOT / "docs" / "assets" / "data" / "pilot" / f"{SOURCE}.json"

ATTRIBUTES = ("CON", "FR", "DEX", "AGI", "INT", "WILL", "CAR", "PER")
DROP_HEADINGS = {"MEDONHO"}
SKILL_TERMS = (
    "Armadilhas",
    "Armas",
    "Artes",
    "Avaliação",
    "Briga",
    "Camuflagem",
    "Ciências",
    "Condução",
    "Disfarce",
    "Escutar",
    "Esportes",
    "Explosivos",
    "Falsificação",
    "Furtar",
    "Furtividade",
    "Informática",
    "Manipulação",
    "Manobras",
    "Manuseio",
    "Mecânica",
    "Negociação",
    "Pesquisa",
)


def source_path() -> Path:
    candidates = list((ROOT / "Livros" / "word").glob(SOURCE_GLOB))
    candidates += list((ROOT / "Livros" / "word" / "feito").glob(SOURCE_GLOB))
    if not candidates:
        raise FileNotFoundError(f"{SOURCE_GLOB} nao encontrado em Livros/word ou Livros/word/feito")
    return candidates[0]


def normalize_text(text: str) -> str:
    replacements = {
        "\ufb01": "fi",
        "\ufb02": "fl",
        "\u00a0": " ",
        "C iências": "Ciências",
        "p e ": "e ",
        "e x p eriente": "experiente",
        "matil has": "matilhas",
        "distãncia": "distância",
        "heroicos": "heróicos",
        "pericias": "perícias",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"\(\s+", "(", text)
    text = re.sub(r"\s+\)", ")", text)
    text = text.replace("PVs15", "PVs 15")
    return text


def is_heading_style(style_name: str) -> bool:
    return style_name in {"Heading 1", "Heading 2"}


def heading_level(style_name: str) -> int:
    return 1 if style_name == "Heading 1" else 2


def is_pseudo_heading(text: str, style_name: str) -> bool:
    if is_heading_style(style_name):
        return False
    if len(text) > 70 or len(text) < 3:
        return False
    if re.search(r"\b(?:CON|FR|DEX|AGI|INT|WILL|CAR|PER|PVs?|IP|dano)\b", text):
        return False
    if re.search(r"[.!?:,;]", text):
        return False
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return False
    return sum(1 for char in letters if char.isupper()) / len(letters) >= 0.75


def split_embedded_heading(text: str) -> tuple[str, str] | None:
    match = re.match(r"^([A-ZÁÉÍÓÚÃÕÂÊÔÇ0-9 /()'-]{4,}?)\s+([“\"].+)$", text)
    if not match:
        return None
    title = normalize_text(match.group(1))
    remainder = normalize_text(match.group(2))
    if not has_stat_block([remainder]):
        return None
    return title, remainder


def read_entries(path: Path) -> list[dict]:
    document = Document(path)
    entries = []
    for index, paragraph in enumerate(document.paragraphs):
        text = normalize_text(paragraph.text)
        if not text:
            continue
        style = paragraph.style.name
        embedded = split_embedded_heading(text)
        if embedded:
            title, remainder = embedded
            entries.append({"index": index, "text": title, "style": style, "level": 1})
            entries.append({"index": index, "text": remainder, "style": style, "level": None})
            continue
        entries.append(
            {
                "index": index,
                "text": text,
                "style": style,
                "level": heading_level(style) if is_heading_style(style) else (1 if is_pseudo_heading(text, style) else None),
            }
        )
    return entries


def join_fragments(paragraphs: list[str]) -> list[str]:
    result: list[str] = []
    for paragraph in paragraphs:
        if not paragraph:
            continue
        if result and should_join(result[-1], paragraph):
            result[-1] = normalize_text(f"{result[-1]} {paragraph}")
        else:
            result.append(paragraph)
    return result


def should_join(previous: str, current: str) -> bool:
    if re.fullmatch(r"\d{1,2}\.", current):
        return True
    if current[0].islower():
        return True
    if previous.endswith(("-", ",", " de", " do", " da", " dos", " das", " e", " ou", " para", " com")):
        return True
    if re.fullmatch(r"\d{1,2}", current) and re.search(r"\b(?:PVs?|PER|CAR|AGI)$", previous):
        return True
    return False


def block(section_id: str, title: str, area: str, paragraphs: list[str]) -> dict:
    return {
        "id": slugify(section_id),
        "title": title,
        "area": area,
        "paragraphs": join_fragments([normalize_text(paragraph) for paragraph in paragraphs if normalize_text(paragraph)]),
    }


def next_heading(entries: list[dict], start: int, level: int) -> int:
    for index in range(start + 1, len(entries)):
        entry_level = entries[index]["level"]
        if entry_level is not None and entry_level <= level:
            return index
    return len(entries)


def body_between(entries: list[dict], start: int, end: int) -> list[str]:
    paragraphs = []
    for entry in entries[start:end]:
        if entry["level"] is not None:
            continue
        text = entry["text"]
        if re.fullmatch(r"\d+", text):
            continue
        paragraphs.append(text)
    return join_fragments(paragraphs)


def has_stat_block(paragraphs: list[str]) -> bool:
    text = " ".join(paragraphs)
    return bool(re.search(r"\bCON\s+\d", text) and re.search(r"\b(?:FR|DEX|AGI|INT|WILL|PER)\s+\d", text))


def is_attribute_line(text: str) -> bool:
    return bool(re.search(r"\b(?:CON|FR|DEX|AGI|INT|WILL|CAR|PER)\s+\d", text))


def is_vital_line(text: str) -> bool:
    return bool(re.search(r"\b(?:#\s*Ataques?|IP:?|PVs?)\b", text))


def is_attack_line(text: str) -> bool:
    if is_ability_line(text):
        return False
    if not re.search(r"\b(?:dano|d\d+|\d+/\d+|\d+%)\b", text, re.IGNORECASE):
        return False
    return bool(
        re.search(
            r"\b(?:Artes Marciais|Briga|Pistola|Revólver|Faca|Garras?|Mordida|Chifre|Coice|Cauda|Clava|Espada|Lança|Metralhadora|Escopeta|Presas|Ferrão|Tentáculos?|Pancada|Rajada|Bico|Dentes|Arma mágica|Motosserra|Boxe|Nunchaco|Estrelinhas)\b",
            text,
            re.IGNORECASE,
        )
    )


def is_skill_list_line(text: str) -> bool:
    if is_ability_line(text):
        return False
    if re.search(r"\bperícias? mais (?:comuns|utilizadas|usadas)\b", text, re.IGNORECASE):
        return True
    if len(re.findall(r"\d+%", text)) >= 2 and any(term in text for term in SKILL_TERMS):
        return True
    return False


def is_magic_line(text: str) -> bool:
    return bool(re.search(r"\b(?:Pontos de Magia|Focus|Caminhos|Magia:)\b", text))


def is_ability_line(text: str) -> bool:
    if re.search(r"\bperícias? mais (?:comuns|utilizadas|usadas)\b", text, re.IGNORECASE):
        return False
    if re.match(r"^(?:Pode|Podem|Caso|Ao contrário|Regenera|Regeneram|Infravisão|Ver o Invisível|Visão Aguçada|Temores|Vulnerabilidade|Forma de Névoa|Imortal|Invulnerabilidade|Monstruoso)\b", text):
        return True
    if re.search(r"\b(?:por rodada|por turno|vezes por dia|veneno|imunes?|vulnerabilidades?|não precisam dormir|sofre dano|recebe dano|perde \d+ PV)\b", text, re.IGNORECASE):
        return True
    return False


def is_sheet_line(text: str) -> bool:
    return is_attribute_line(text) or is_vital_line(text) or is_attack_line(text) or is_skill_list_line(text) or is_magic_line(text)


def split_mixed_paragraph(text: str) -> list[str]:
    pieces = [text]
    weapon_terms = (
        "Garras",
        "Briga",
        "Mordida",
        "Golpe de corpo",
        "Artes Marciais",
        "Faca",
        "Pistola",
        "Revólver",
        "Metralhadora",
        "Escopeta",
    )
    for term in weapon_terms:
        next_pieces = []
        pattern = rf"(?<=\.)\s+({re.escape(term)}\b)"
        for piece in pieces:
            split = re.split(pattern, piece, maxsplit=1)
            if len(split) == 3 and is_ability_line(split[0]):
                next_pieces.append(normalize_text(split[0]))
                next_pieces.append(normalize_text(split[1] + split[2]))
            else:
                next_pieces.append(piece)
        pieces = next_pieces
    return [piece for piece in pieces if piece]


def parse_attributes(paragraphs: list[str]) -> dict:
    text = " ".join(paragraphs)
    attributes = {}
    for attr in ATTRIBUTES:
        match = re.search(rf"\b{attr}\s+([0-9]+(?:\s*-\s*[0-9]+)?)", text)
        if match:
            attributes[attr] = normalize_text(match.group(1).replace(" ", ""))
    return attributes


def parse_vitals(paragraphs: list[str]) -> dict:
    text = " ".join(paragraphs)
    vitals = {}
    pv = re.search(r"\bPVs?\s*([0-9]+(?:\s*-\s*[0-9]+)?)", text, re.IGNORECASE)
    ip = re.search(r"\bIP:?\s*([^,.;]+)", text, re.IGNORECASE)
    attacks = re.search(r"#\s*Ataques?\s*\[([^\]]+)\]", text, re.IGNORECASE)
    if pv:
        vitals["PV"] = normalize_text(pv.group(1).replace(" ", ""))
    if ip:
        vitals["IP"] = normalize_text(ip.group(1))
    if attacks:
        vitals["Ataques"] = normalize_text(attacks.group(1))
    return vitals


def split_character_sections(paragraphs: list[str]) -> tuple[list[str], list[str], list[str]]:
    ficha = []
    habilidades = []
    descricao = []
    for paragraph in paragraphs:
        for part in split_mixed_paragraph(paragraph):
            if is_ability_line(part):
                habilidades.append(part)
            elif is_sheet_line(part):
                ficha.append(part)
            else:
                descricao.append(part)
    return ficha, habilidades, descricao


def remove_matching(paragraphs: list[str], patterns: list[str]) -> list[str]:
    result = []
    for paragraph in paragraphs:
        if any(re.search(pattern, paragraph, re.IGNORECASE) for pattern in patterns):
            continue
        result.append(paragraph)
    return result


def postprocess_character_inputs(title: str, paragraphs: list[str]) -> list[str]:
    if title == "BOMBEIRO":
        return remove_matching(
            paragraphs,
            [
                r"# Ataques \[1\].*Kevlar",
                r"balístico\).*PVs 17-23",
                r"Briga 50/40.*Faca 35/0",
                r"Diferente de um capanga comum",
                r"^CAPANGA$",
            ],
        )
    if title == "CAPANGA FORTE":
        return paragraphs + [
            "# Ataques [1], IP: 0 ou Kevlar: 3 (cinético) e 5 (balístico), PVs 17-23.",
            "Briga 50/40 dano 1d3+bônus. Faca 35/0 dano 1d3+bônus.",
            "Diferente de um capanga comum, um capanga forte é contratado para serviços mais pesados, geralmente onde haja necessidade de um confronto físico direto. Não são necessariamente muito inteligentes, porém a maioria possui maior massa corporal do que massa cerebral.",
        ]
    if title == "ASSASSINO":
        return remove_matching(paragraphs, [r"^O assaltante de banco é", r"assaltante comum"])
    if title == "ASSALTANTE DE BANCO":
        return paragraphs + [
            "O assaltante de banco é um criminoso especializado em crimes mais ousados, seu objetivo é um cofre lotado de sacos com um cifrão desenhado. Diferente do assaltante comum, um assaltante de banco é mais especializado, mais ousado e melhor armado.",
        ]
    return paragraphs


def make_character(title: str, paragraphs: list[str]) -> dict:
    ficha, habilidades, descricao = split_character_sections(paragraphs)
    skill_lines = [paragraph for paragraph in ficha if not is_attribute_line(paragraph)]
    sections = [block("ficha", "Ficha", "criaturas_npcs", ficha)]
    if habilidades:
        sections.append(block("habilidades", "Habilidades", "criaturas_npcs", habilidades))
    if descricao:
        sections.append(block("descricao", "Descrição", "criaturas_npcs", descricao))
    return {
        "id": slugify(title),
        "name": normalize_text(title.title() if title.isupper() else title),
        "type": "character_npc",
        "role": "Criatura/NPC",
        "classifications": [
            {
                "area": "criaturas_npcs",
                "confidence": 0.82,
                "reason": "Bloco com atributos/ficha operacional detectados no DOCX.",
            }
        ],
        "statBlock": {
            "attributes": parse_attributes(ficha),
            "vitals": parse_vitals(ficha),
            "skills": "\n".join(dict.fromkeys(skill_lines)),
            "special": [],
        },
        "sections": sections,
    }


def collect_intro(entries: list[dict]) -> list[dict]:
    first_heading = next((i for i, entry in enumerate(entries) if entry["level"] is not None), len(entries))
    paragraphs = body_between(entries, 0, first_heading)
    medonho = next((i for i, entry in enumerate(entries) if entry["text"] == "MEDONHO"), None)
    if medonho is not None:
        end = next_heading(entries, medonho, 1)
        paragraphs.extend(body_between(entries, medonho + 1, end))
    if not paragraphs:
        return []
    return [block("introducao", "Introdução", "regras_base", paragraphs)]


def collect_characters_and_notes(entries: list[dict]) -> tuple[list[dict], list[dict]]:
    characters = []
    notes = []
    seen = set()
    for index, entry in enumerate(entries):
        if entry["level"] is None:
            continue
        title = entry["text"]
        if title in DROP_HEADINGS:
            continue
        end = next_heading(entries, index, entry["level"])
        paragraphs = body_between(entries, index + 1, end)
        if not paragraphs:
            continue
        if has_stat_block(paragraphs):
            key = slugify(title)
            if key not in seen:
                seen.add(key)
                characters.append(make_character(title, paragraphs))
        elif entry["level"] == 1:
            notes.append(block(title, normalize_text(title.title() if title.isupper() else title), "regras_base", paragraphs))
    return characters, notes


def build_payload() -> dict:
    src = source_path()
    entries = read_entries(src)
    characters, notes = collect_characters_and_notes(entries)
    rules_sections = collect_intro(entries) + notes
    groups = []
    if rules_sections:
        groups.append(
            {
                "id": "anime-rpg-supers-monstros-viloes-regras",
                "title": "Regra base - Anime RPG - Supers - Monstros e Vilões",
                "kind": "ruleset",
                "area": "regras_base",
                "sectionTitle": "Regra Base",
                "sections": rules_sections,
            }
        )

    area_counts = {"criaturas_npcs": len(characters)}
    if groups:
        area_counts["regras_base"] = len(groups)
    return {
        "version": 1,
        "status": "pilot_review",
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "source": SOURCE,
        "sourceFile": src.name,
        "sourcePath": str(src.relative_to(ROOT)).replace("\\", "/"),
        "title": "Anime RPG - Supers - Monstros e Vilões",
        "summary": (
            "Suplemento de ameaças para Anime RPG/SUPERS com humanos comuns, criminosos, animais, "
            "criaturas fantásticas, mortos-vivos, demônios e robôs para uso como NPCs ou monstros."
        ),
        "areas": sorted(area_counts),
        "groups": groups,
        "sections": [],
        "characters": characters,
        "adventures": [],
        "areaCounts": area_counts,
        "reviewNotes": [
            "Piloto conservador: apenas headings com ficha detectável viraram criaturas/NPCs.",
            "Habilidades especiais foram separadas de Perícias e Combate quando detectadas por frase de efeito, teste, veneno, regeneração ou voo.",
            "O DOCX possui quebras e trechos fora de ordem; revisar manualmente entradas com descrições curtas ou herdadas de variantes.",
        ],
    }


def main() -> None:
    payload = build_payload()
    write_json(OUT_PATH, payload)
    write_json(DOCS_OUT_PATH, payload)
    src = source_path()
    if src.parent.name != "feito":
        done = ROOT / "Livros" / "word" / "feito" / DONE_NAME
        done.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(done))
    print(json.dumps({"source": payload["source"], "areas": payload["areaCounts"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
