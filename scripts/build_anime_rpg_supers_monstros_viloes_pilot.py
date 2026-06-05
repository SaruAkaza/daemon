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
    replacements["Intim idação"] = "Intimidação"
    replacements["doseleme ntos"] = "dos elementos"
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
    if previous.endswith(("-", ",", " a", " de", " do", " da", " dos", " das", " e", " ou", " para", " com")):
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
    if re.match(r"^(?:#\s*Ataques?|IP:?|PVs?)\b", text, re.IGNORECASE):
        return True
    return bool(re.search(r"\b(?:IP:|PVs?\s*\d)", text, re.IGNORECASE))


def is_attack_line(text: str) -> bool:
    if is_ability_line(text):
        return False
    if not re.search(r"\b(?:dano|d\d+|\d+/\d+|\d+%)\b", text, re.IGNORECASE):
        return False
    attack_start = (
        "Artes Marciais",
        "Briga",
        "Pistola",
        "Revólver",
        "Faca",
        "Garras",
        "Garra",
        "Mordida",
        "Chifre",
        "Chifres",
        "Coice",
        "Cauda",
        "Clava",
        "Espada",
        "Lança",
        "Metralhadora",
        "Escopeta",
        "Espingarda",
        "Presas",
        "Ferrão",
        "Tentáculos",
        "Tentáculo",
        "Pancada",
        "Rajada",
        "Bico",
        "Dentes",
        "Arma mágica",
        "Motosserra",
        "Boxe",
        "Nunchaco",
        "Estrelinhas",
        "Golpe de corpo",
    )
    if not text.startswith("#") and not any(text.lower().startswith(term.lower()) for term in attack_start):
        if not re.search(r"\b(?:Garras?|Mordida|Briga|Faca|Pistola|Espingarda|Clava|Lança|Ferrão|Tentáculos?)\s+\d", text, re.IGNORECASE):
            return False
    return bool(
        re.search(
            r"\b(?:Artes Marciais|Briga|Pistola|Revólver|Faca|Garras?|Mordida|Chifres?|Coice|Cauda|Clava|Espada|Lança|Metralhadora|Escopeta|Espingarda|Presas|Ferrão|Tentáculos?|Pancada|Rajada|Bico|Dentes|Arma mágica|Motosserra|Boxe|Nunchaco|Estrelinhas|Golpe de corpo)\b",
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
    if re.match(r"^(?:Pode|Podem|Caso|Ao contrário|Regenera|Regeneram|Infravisão|Ver o Invisível|Visão Aguçada|Temores|Vulnerabilidade|Forma de Névoa|Formas Alternativas|Imortal|Invulnerabilidade|Monstruoso)\b", text):
        return True
    if re.search(r"\bregeneram? \d+ (?:Pontos de Vida|PVs?)\b", text, re.IGNORECASE):
        return True
    if re.search(r"\b(?:vezes por dia|imunes?|vulnerabilidades?|não precisam dormir|sofre dano|recebe dano|perde \d+ PV)\b", text, re.IGNORECASE):
        return True
    return False


def is_sheet_line(text: str) -> bool:
    return is_attribute_line(text) or is_vital_line(text) or is_attack_line(text) or is_skill_list_line(text) or is_magic_line(text)


def split_mixed_paragraph(text: str) -> list[str]:
    quote_attr = re.match(r"^([“\"].+?[”\"])\s+(CON\b.+)$", text)
    if quote_attr:
        return [normalize_text(quote_attr.group(1)), normalize_text(quote_attr.group(2))]

    sheet_ability = re.split(r"(?<=\.)\s+(Regenera(?:m)?\b)", text, maxsplit=1, flags=re.IGNORECASE)
    if len(sheet_ability) == 3 and is_vital_line(sheet_ability[0]):
        return [normalize_text(sheet_ability[0]), normalize_text(sheet_ability[1] + sheet_ability[2])]

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
        return remove_matching(paragraphs, [r"^O assaltante de banco é", r"assaltante comum"]) + [
            "Para qualquer fim, as perícias mais utilizadas por assassinos são: Armadilhas, Camuflagem, Ciências (Anatomia), Condução (Carros, Motos), Disfarce, Escutar, Explosivos, Furtividade, Manipulação (Impressionar, Tortura), Manobras de Combate (Todas), Manuseio de Fechaduras, Rastreio. Com valores entre 30% a 95%.",
        ]
    if title == "ASSALTANTE DE BANCO":
        return paragraphs + [
            "O assaltante de banco é um criminoso especializado em crimes mais ousados, seu objetivo é um cofre lotado de sacos com um cifrão desenhado. Diferente do assaltante comum, um assaltante de banco é mais especializado, mais ousado e melhor armado.",
        ]
    if title == "KRAKEN":
        return remove_matching(paragraphs, [r"^Lobisomens regeneram"])
    if title == "LOBISOMEM":
        return paragraphs + [
            "Lobisomens regeneram 2 Pontos de Vida por rodada e só podem ser verdadeiramente mortos por prata pura. Ataques feitos por armas de prata não são regenerados. Os lobisomens possuem todos os sentidos superiores, bem como alguns deles podem possuir poderes que simulam os Caminhos em Ar e Trevas. Alguns super poderes também podem ser simulados pelos lobisomens, de acordo com o Mestre.",
        ]
    if title == "VAMPIRO":
        cleaned = remove_matching(
            paragraphs,
            [
                r"também não pode ser atacado",
                r"PER 16- O vampiro pode se 24",
                r"^O vampiro pode se$",
                r"^24\.$",
                r"^transformar em um lobo ou morcego",
                r"^TODOS os vampiros sofrem dano quando repulsiva",
            ],
        )
        return [
            "CON 16-36, FR 16-36, DEX 12-24, AGI 16-36, INT 12-20, WILL 12-20, CAR 00-20, PER 16-24.",
            "Formas Alternativas: o vampiro pode se transformar em um lobo ou morcego.",
        ] + cleaned
    if title == "TERIZINOSSAURO":
        return remove_matching(
            paragraphs,
            [
                r"INT 01, WILL 01, CAR 00, PER 04-08",
                r"# Ataques \[1\], IP: 8/4",
                r"Chifres 60/20",
                r"Em eras pré-históricas, o triceratops",
                r"Infelizmente, são também muito irritadiços",
            ],
        )
    if title == "TRICERATOPS":
        return [
            "CON 42-50, FR 36-50, DEX 03, AGI 06-10, INT 01, WILL 01, CAR 00, PER 04-08.",
            "# Ataques [1], IP: 8/4 (carapaça/pele), PVs 50-60.",
            "Chifres 60/20 dano 3d6+6 ou Carga 50% dano 5d6+6.",
            "Em eras pré-históricas, o triceratops foi o mais comum entre os grandes dinossauros herbívoros, encontrado em vastas manadas. Um triceratops adulto pode atingir dez metros de comprimento, com chifres medindo mais de um metro. Sua cabeça, pescoço e ombros são protegidos por um escudo de osso, que ele pode usar como um escudo normal, e capaz de proteger a si mesmo ou alguém que o esteja cavalgando.",
            "Infelizmente, são também muito irritadiços e territoriais, atacando qualquer criatura que se aproxime do bando. Viajam em grandes manadas de 10 a 30 indivíduos.",
        ]
    if title == "ELEMENTAIS":
        return remove_matching(
            paragraphs,
            [
                r"^Estes são o tipo mais fraco de morto vivo",
                r"^Esqueletos são imunes",
                r"^por controle mental",
                r"^restaurados",
                r"^Quase todos os esqueletos",
            ],
        )
    if title == "ESQUELETO":
        return paragraphs + [
            "Estes são o tipo mais fraco de morto vivo, um simples amontoado de ossos que andam e lutam. Eles não surgem naturalmente, costumam ser invocados por forças malignas para servirem para algum propósito sombrio. É raro que tenham qualquer vontade própria.",
            "Esqueletos são imunes a acertos críticos, não podem ser afetados por ataques baseados em frio ou gelo, não são afetados por controle mental e sofrem dano menor quando atacados com ataques perfurantes. Esqueletos nunca podem recuperar Pontos de Vida, nem por descanso, magia ou super poder. Uma vez danificados, é para sempre, exceto se forem restaurados.",
            "Quase todos os esqueletos são silenciosos, totalmente mudos, e aqueles capazes de falar o fazem com uma voz estridente e arranhada.",
        ]
    return paragraphs


def display_name(title: str) -> str:
    name = normalize_text(title.title() if title.isupper() else title)
    return re.sub(r"\b(Da|De|Do|Das|Dos|E)\b", lambda match: match.group(1).lower(), name)


def make_character(title: str, paragraphs: list[str]) -> dict:
    paragraphs = postprocess_character_inputs(title, paragraphs)
    ficha, habilidades, descricao = split_character_sections(paragraphs)
    skill_lines = [paragraph for paragraph in ficha if not is_attribute_line(paragraph)]
    sections = [block("ficha", "Ficha", "criaturas_npcs", ficha)]
    if habilidades:
        sections.append(block("habilidades", "Habilidades", "criaturas_npcs", habilidades))
    if descricao:
        sections.append(block("descricao", "Descrição", "criaturas_npcs", descricao))
    return {
        "id": slugify(title),
        "name": display_name(title),
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


def collect_characters_and_classes(entries: list[dict]) -> tuple[list[dict], list[dict]]:
    characters = []
    class_sections = []
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
            class_sections.append(block(title, display_name(title), "classes", paragraphs))
    return characters, class_sections


def build_payload() -> dict:
    src = source_path()
    entries = read_entries(src)
    characters, class_sections = collect_characters_and_classes(entries)
    rules_sections = collect_intro(entries)
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
    if class_sections:
        area_counts["classes"] = len(class_sections)
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
        "sections": class_sections,
        "characters": characters,
        "adventures": [],
        "areaCounts": area_counts,
        "reviewNotes": [
            "Piloto conservador: apenas headings com ficha detectável viraram criaturas/NPCs.",
            "Perfis humanos sem ficha própria completa foram tratados como Classes, não como Regra Base.",
            "Habilidades especiais foram separadas de Perícias e Combate quando detectadas por frase de efeito, teste, veneno, regeneração ou voo.",
            "O DOCX possui quebras e trechos fora de ordem; revisar manualmente entradas com descrições curtas ou herdadas de variantes.",
            "Pendência conhecida: Crocodilo do Pântano não traz linha de PV/IP/# Ataques no trecho extraído do DOCX; foram mantidos atributos, ataques e descrição sem inventar valores.",
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
