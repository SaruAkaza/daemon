from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Iterable

from docx import Document

from common import ROOT, slugify, write_json
from ocr_cleanup import clean_ocr_aggressive


SOURCE = "anjos-a-cidade-de-prata"
TITLE = "Anjos - A Cidade de Prata"
SOURCE_CANDIDATES = [
    ROOT / "Livros" / "word" / "Anjos_A_Cidade_de_Prata.docx",
    ROOT / "Livros" / "word" / "feito" / "Anjos_A_Cidade_de_Prata.docx",
]
SOURCE_PATH = next(path for path in SOURCE_CANDIDATES if path.exists())
OUT_PATH = ROOT / "data" / "pilot" / f"{SOURCE}.json"
DOCS_OUT_PATH = ROOT / "docs" / "assets" / "data" / "pilot" / f"{SOURCE}.json"


TITLE_FIXES = {
    "GONcerres BÁsices": "Conceitos Básicos",
    "A HisréRiA De PARADÍSIA": "A História de Paradísia",
    "A PaimeiRA REBELIÀ": "A Primeira Rebelião",
    "PIAN0S DE EXISTÊNCIA": "Planos de Existência",
    "A CIDADE DeURADA DE RA": "A Cidade Dourada de Ra",
    "A ÁRven. 6 DA VIDA, A QUABALUA E s SEPHIRAH": "A Árvore da Vida, a Qabalah e as Sephirah",
    "RATmARAN": "Katmaran",
    "A PU'TICA NA CIDADE DE PRATA": "A Política na Cidade de Prata",
    "A EXPANSA DA CIDADE DE PRATA": "A Expansão da Cidade de Prata",
    "A INQUISICÃ": "A Inquisição",
    "A GUERRA oes cem AHOS": "A Guerra dos Cem Anos",
    "JANNA D'ARC.": "Joanna D'Arc",
    "A GUERRA DAS DUAS RSAS": "A Guerra das Duas Rosas",
    "A PCNÍNSULA IBÉRICA": "A Península Ibérica",
    "A CACA ÀS BRUXAS": "A Caça às Bruxas",
    "A ÁPRICA": "A África",
    "O SÉCUL XXI": "O Século XXI",
    "C0RP0RÊ": "Corpore",
    "ORGANIZACÃ0": "Organização",
    "PODSRÊS ÚNICQS": "Poderes Únicos",
    "PeoERfis ÚNices": "Poderes Únicos",
    "Peo6R. es ÚNICOS": "Poderes Únicos",
    "P0DERÊS ÚNICffiS DS ANJfflS G ARCANJffiS": "Poderes Únicos dos Anjos e Arcanjos",
    "P0D6RES ÚNIC0S": "Poderes Únicos",
    "RfitíPÊRfiS": "Recíperes",
    "NimBus": "Nimbus",
    "NimBus Os Nimbus": "Nimbus. Os Nimbus",
    "APRIinRAinENTS": "Aprimoramentos",
    "AFINIDADE cem PADAS": "Afinidade com Fadas",
    "AirnA DUPLA": "Alma Dupla",
    "AmBlDÉSTRIA": "Ambidestria",
    "BIBUSTÉCA ARCANA": "Biblioteca Arcana",
    "ClfiR": "Clero",
    "CfflNTATS": "Contatos",
    "DETÊCCA DE IIIAGIA": "Detecção de Magia",
    "GUARDIÃ DE um ARTEFAT IIIIPRTANTE": "Guardião de um Artefato Importante",
    "LCAL DE CNTRLE": "Local de Controle",
    "OB}fiTOs ilIÁGECes": "Objetos Mágicos",
    "PACres": "Pactos",
    "PALAVRA DÊ Deus": "Palavra de Deus",
    "PERTENCER A umA ESCLA DE- HIAGIA": "Pertencer a uma Escola de Magia",
    "PERTENCER eu COHIANDAR UIHA SEITA": "Pertencer ou Comandar uma Seita",
    "PODERES IIIÁGices": "Poderes Mágicos",
    "SENSO DE DlRECAO": "Senso de Direção",
    "ANGELICAIS": "Poderes Angelicais",
    "AumeNTe DE ATRiBures": "Aumento de Atributos",
    "BfiNCÃ": "Benção",
    "CefflBATÊ": "Combate",
    "CemuNHÃO": "Comunhão",
    "CNTR0Lfi niENTAL": "Controle Mental",
    "Gupe": "Glifo",
    "LfiXTALiems": "Lex Talionis",
    "IIIfiNSAGfilR CfiLfiSTIAL": "Mensageiro Celestial",
    "NlffiBUS": "Nimbus",
    "PAssAGfim ASTRAL": "Passagem Astral",
    "PfiRCfiPCÃ DIVINA": "Percepção Divina",
    "QUfiRUBIA": "Querubia",
    "RfiGENfiRACAO": "Regeneração",
    "SimuiACRe": "Simulacro",
    "TfiLECINlSIA": "Telecinesia",
    "0B|ETes ITIÁGices": "Objetos Mágicos",
    "CRIANDO srus paépRiO ITENS mAcices": "Criando seus Próprios Itens Mágicos",
    "PNTOS D6": "Pontos de Fé",
    "AFASTAR menres -vives": "Afastar Mortos-Vivos",
    "ATIVACA DÊ ITENS HlÁcices": "Ativação de Itens Mágicos",
    "REGRAS e TESTES": "Regras e Testes",
    "ÍNDICE DÊ PRTECÃ": "Índice de Proteção",
    "QUANDO SUA PRéPRlA GDADE DG ANJOS": "Criando sua Própria Cidade de Anjos",
}


def normalize_text(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = text.replace("—", "-")
    text = text.replace("“", '"').replace("”", '"').replace("’", "'")
    text = text.replace("l O", "10").replace("l d", "1d").replace("l D", "1D")
    text = text.replace("1d10O", "1d100").replace("Id", "1d")
    text = text.replace("P V", "PV").replace("PVs", "PVs")
    text = text.replace("dó", "d6").replace("Dó", "D6")
    text = text.replace("Demónios", "Demônios")
    text = text.replace("m issões", "missões")
    text = text.replace("ofajetos", "objetos")
    text = text.replace("SOkgs", "50kgs").replace("SOkgs", "50kgs")
    text = text.replace("lOOkgs", "100kgs").replace("lOOKg", "100Kg")
    text = text.replace("formase", "forma-se")
    text = text.replace("arrancálo", "arrancá-lo")
    text = text.replace("mágicalmente", "magicamente")
    text = text.replace("magicalmente", "magicamente")
    text = text.replace("pelaproteção", "pela proteção")
    text = text.replace("quemmanda", "quem manda")
    text = text.replace("1dade", "Idade")
    text = text.replace("fina1de", "final de")
    text = text.replace("fina1das", "final das")
    text = text.replace("norma1de", "normal de")
    text = text.replace("socia1", "social")
    text = text.replace("emociona1", "emocional")
    text = text.replace("emocionalde", "emocional de")
    text = text.replace("pessoa!", "pessoal")
    text = text.replace("Ane1", "Anel")
    text = text.replace("ane1", "anel")
    text = text.replace("Anelde", "Anel de")
    text = text.replace("Aneldo", "Anel do")
    text = text.replace("ane1dá", "anel dá")
    text = text.replace("expontâneos", "espontâneos")
    text = text.replace("átimo", "ótimo")
    text = text.replace("dejesar", "desejar")
    text = text.replace("Alifica", "Ali fica")
    text = text.replace("mor a", "mora")
    text = text.replace("certaforma", "certa forma")
    text = text.replace("contínua", "continua")
    text = text.replace("crêem", "creem")
    text = text.replace("fáci1de", "fácil de")
    text = text.replace("loca1de", "local de")
    text = text.replace("su1das", "sul das")
    text = text.replace("diminuíx das", "diminuídas")
    text = text.replace("socialdas", "social das")
    text = text.replace("l ponto", "1 ponto")
    text = text.replace("l inimigo", "1 inimigo")
    text = text.replace("lOPVs", "10 PVs")
    text = text.replace("lOd6", "10d6")
    text = text.replace("1do", "1d6")
    text = text.replace("2pontos", "2 pontos")
    text = text.replace("7pontos", "7 pontos")
    text = text.replace("QuACÃe DG PfiRSONAGfiNS", "Criação de Personagens")
    text = text.replace("I. £SCLHA A CAfflPANHA", "1. Escolha a Campanha")
    text = text.replace("2. fisceLHA UfflA HISTéRIA fflRTAL", "2. Escolha uma História Mortal")
    text = text.replace("5. fisceLHA seus ATRIBUTOS", "5. Escolha seus Atributos")
    text = text.replace("6. EsceiHA Os PODERES ANGELICAIS", "6. Escolha os Poderes Angelicais")
    text = text.replace("7. Penres DE ApRimeRAmENTe", "7. Pontos de Aprimoramento")
    text = text.replace("9. PERÍCIAS cem ARIHAS E PERÍCIAS cemuNs", "9. Perícias com Armas e Perícias Comuns")
    text = text.replace("10. PNTS DÊ VIDA E ÍNDICE DE PRTECÃ", "10. Pontos de Vida e Índice de Proteção")
    text = text.replace("11. SE? ER. sNAGem è um IIIAG.", "11. Se o personagem é um mago")
    text = text.replace("DEFINA S PONTOS DG IIlAGIA fi OS FOCUS,", "Defina os Pontos de Magia e os Focus")
    text = text.replace("12. ITENS mÁGices", "12. Itens Mágicos")
    text = text.replace("13. REUNINDO Os PERSONAGENS", "13. Reunindo os Personagens")
    text = text.replace("ITIeDipicADeR DE ARIHA", "Modificador de Arma")
    text = text.replace("IIIeDiFicADeR DE ARIHA TTIÁGICA", "Modificador de Arma Mágica")
    text = text.replace("IIIeDIFICADeR DE IIlAGIA", "Modificador de Magia")
    text = text.replace("CAfflPANHA", "Campanha")
    text = text.replace("PfiRSONAGfiNS", "Personagens")
    text = text.replace("PQDERES ANGELICAIS", "Poderes Angelicais")
    text = text.replace("'TESTE DE ATRIBUT", "Teste de Atributo")
    text = text.replace("Tesre FÁCIL", "Teste Fácil")
    text = text.replace("Tomaram-se", "Tornaram-se")
    text = text.replace("AumfiNTe miLAGRese DG ATRIBUTOS", "Aumento Milagroso de Atributos")
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return text


def fix_title(text: str) -> str:
    text = normalize_text(text)
    for bad, good in TITLE_FIXES.items():
        if text == bad:
            return good
        if text.startswith(f"{bad} "):
            return normalize_text(f"{good} {text[len(bad):]}")
    text = re.sub(r"^N[íi]vel l:", "Nível 1:", text)
    return text


def docx_paragraphs() -> list[str]:
    document = Document(SOURCE_PATH)
    values: list[str] = []
    for paragraph in document.paragraphs:
        style = paragraph.style.name if paragraph.style else ""
        text = normalize_text(paragraph.text)
        if style in {"Nota OCR", "Página OCR"}:
            values.append("")
            continue
        if text == "[sem texto reconhecível após a limpeza]":
            values.append("")
            continue
        if re.fullmatch(r"Página \d+", text):
            values.append("")
            continue
        values.append(fix_title(text))

    # Apply aggressive OCR cleanup before returning
    raw_text = "\n".join(values)
    cleaned_text = clean_ocr_aggressive(
        raw_text,
        phases={'ligatures', 'join', 'numerics', 'unicode'},
        title_fixes=TITLE_FIXES,
    )
    return cleaned_text.split("\n")


def should_join(previous: str, current: str) -> bool:
    if not previous or not current:
        return False
    if previous.endswith("-") and current[:1].islower():
        return True
    if current[:1].islower() and not previous.endswith((".", "!", "?", ":", ";", '"')):
        return True
    if re.match(r"^[,.;:)]", current):
        return True
    if previous.endswith(("de", "do", "da", "dos", "das", "em", "por", "com", "para", "e")):
        return True
    return False


def clean(values: Iterable[str]) -> list[str]:
    paragraphs: list[str] = []
    for raw in values:
        text = fix_title(raw)
        if not text or text == TITLE:
            continue
        if re.fullmatch(r"\d+(?:\.\d+)?", text):
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


def section(section_id: str, title: str, area: str, paragraphs: list[str]) -> dict:
    return {"id": section_id, "title": title, "area": area, "paragraphs": paragraphs}


def collect(paragraphs: list[str], start: int, end: int) -> list[str]:
    return clean(paragraphs[start:end])


def collect_after(paragraphs: list[str], start: int, end: int) -> list[str]:
    return collect(paragraphs, start + 1, end)


def make_section(paragraphs: list[str], title: str, area: str, start: int, end: int) -> dict:
    return section(slugify(title), title, area, collect_after(paragraphs, start, end))


def split_inline_heading(text: str, title: str) -> list[str]:
    text = fix_title(text)
    if text.casefold().startswith(title.casefold()):
        text = text[len(title):].strip(" .:-")
    return [text] if text else []


def split_cost_sections(title: str, paragraphs: list[str]) -> dict:
    text = normalize_text(" ".join(paragraphs))
    cost_pattern = re.compile(r"(?i)\b((?:\d+|variável|1 ponto por contato|1 ponto por local|1 ponto para cada sentido)\s+pontos?|(?:\d+|variável)\s+ponto|1 ponto por contato|1 ponto por local|1 ponto para cada sentido)\s*[:.]\s*")
    matches = list(cost_pattern.finditer(text))
    costs: list[dict[str, str]] = []
    if matches:
        description = normalize_text(text[: matches[0].start()])
        for index, match in enumerate(matches):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            label = normalize_text(match.group(1))
            effect = normalize_text(text[match.end():end])
            costs.append({"label": label, "effect": effect})
    else:
        description = text

    blocks = []
    if costs:
        cost_lines = [
            item["label"] if len(costs) == 1 or not item["effect"] else f"{item['label']}: {item['effect']}"
            for item in costs
        ]
        blocks.append(section("custo", "Custo", "aprimoramentos", cost_lines))
    description_text = description
    if len(costs) == 1 and costs[0]["effect"]:
        description_text = normalize_text(" ".join(part for part in [description, costs[0]["effect"]] if part))
    elif not description_text and costs:
        description_text = normalize_text(" ".join(item["effect"] for item in costs if item["effect"]))
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


def split_power(title: str, paragraphs: list[str]) -> dict:
    normalized = clean(paragraphs)
    prereq: list[str] = []
    body: list[str] = []
    seen_body = False
    for paragraph in normalized:
        if not seen_body and slugify(paragraph) == slugify(title):
            continue
        if not seen_body:
            inline = re.match(rf"^{re.escape(title)}\s*(\([^)]+\))?\s*(.*)$", paragraph, re.IGNORECASE)
            if inline:
                if inline.group(1):
                    prereq.append(inline.group(1).strip("()"))
                remainder = normalize_text(inline.group(2))
                if remainder:
                    body.append(remainder)
                    seen_body = True
                continue
        if not seen_body and re.fullmatch(r"\(.+\)", paragraph):
            prereq.append(paragraph.strip("()"))
            continue
        body.append(paragraph)
        seen_body = True
    text = normalize_text(" ".join(body))
    text = re.sub(r"\bNivel\b", "Nível", text)
    text = re.sub(r"\bNível l:", "Nível 1:", text)
    marker = re.compile(r"(?i)\bN[íi]vel\s+([0-9X]+):\s*")
    matches = list(marker.finditer(text))
    blocks = []
    if prereq:
        blocks.append(section("pre-requisito", "Pré-requisito", "poderes", prereq))
    intro = normalize_text(text[: matches[0].start()]) if matches else text
    if intro:
        blocks.append(section("descricao", "Descrição", "poderes", [intro]))
    for index, match in enumerate(matches):
        level = match.group(1).upper()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        content = normalize_text(text[match.end():end])
        if content:
            blocks.append(section(f"nivel-{level.lower()}-{index + 1}", f"Nível {level}", "poderes", [content]))
    return {
        "id": slugify(title),
        "title": title,
        "area": "poderes",
        "kind": "power",
        "sectionId": "poder",
        "sectionTitle": "Poder",
        "paragraphs": normalized,
        "sections": blocks or [section("descricao", "Descrição", "poderes", normalized)],
    }


def typed_item(title: str, area: str, kind: str, section_title: str, paragraphs: list[str], sections: list[dict] | None = None) -> dict:
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


def make_class(title: str, paragraphs: list[str]) -> dict:
    blocks: list[dict] = []
    current_title = "Descrição"
    current: list[str] = []
    subheadings = {
        "Organização",
        "Campanha",
        "Campanhas",
        "Poderes Únicos",
        "Poderes Únicos dos Anjos e Arcanjos",
        "Origem",
    }
    for paragraph in clean(paragraphs):
        if paragraph in subheadings or paragraph.startswith("Poderes Únicos"):
            if current:
                blocks.append(section(slugify(current_title), current_title, "classes", current))
            current_title = "Poderes Únicos" if paragraph.startswith("Poderes Únicos") else paragraph
            current = []
            continue
        current.append(paragraph)
    if current:
        blocks.append(section(slugify(current_title), current_title, "classes", current))
    return typed_item(title, "classes", "class", "Classe/Casta", clean(paragraphs), blocks)


def make_item(title: str, paragraphs: list[str]) -> dict:
    return typed_item(title, "itens_equipamentos", "item", "Item", clean(paragraphs))


def item_entries(paragraphs: list[str]) -> list[dict]:
    entries: list[tuple[str, list[str]]] = []
    intro_titles = {"Observações", "Tabela de Objetos Mágicos"}
    for paragraph in collect(paragraphs, 1267, 1375):
        if paragraph in intro_titles or paragraph.startswith("Neste capítulo"):
            continue
        match = re.match(r"^([^:]{3,80}):\s*(.+)$", paragraph)
        if match:
            title = fix_title(match.group(1)).strip()
            description = normalize_text(match.group(2))
            if title.lower().startswith(("poções", "anéis", "rod ", "varinhas", "armas mágicas")):
                continue
            entries.append((title, [description]))
        elif entries:
            entries[-1][1].append(paragraph)
    return [make_item(title, text) for title, text in entries]


def build_pilot() -> dict:
    paragraphs = docx_paragraphs()

    lore_sections = [
        make_section(paragraphs, "Introdução", "cenarios_lore", 61, 66),
        make_section(paragraphs, "A Cidade de Prata", "cenarios_lore", 124, 132),
        make_section(paragraphs, "Luna", "cenarios_lore", 131, 162),
        make_section(paragraphs, "Vênus", "cenarios_lore", 162, 166),
        make_section(paragraphs, "Marte", "cenarios_lore", 166, 180),
        make_section(paragraphs, "Júpiter e Solarium", "cenarios_lore", 180, 193),
        make_section(paragraphs, "A Política na Cidade de Prata", "cenarios_lore", 193, 203),
        make_section(paragraphs, "A História de Paradísia", "cenarios_lore", 204, 227),
        make_section(paragraphs, "Planos de Existência", "cenarios_lore", 227, 280),
        make_section(paragraphs, "A Guerra de Tróia", "cenarios_lore", 280, 298),
        make_section(paragraphs, "A Expansão da Cidade de Prata", "cenarios_lore", 298, 394),
        make_section(paragraphs, "Hierarquia", "cenarios_lore", 394, 407),
    ]

    rules_sections = [
        make_section(paragraphs, "Conceitos Básicos", "regras_base", 67, 124),
        make_section(paragraphs, "Criação de Personagens", "regras_base", 407, 552),
        make_section(paragraphs, "Atributos Básicos", "regras_base", 778, 828),
        make_section(paragraphs, "Perícias", "regras_base", 828, 889),
        make_section(paragraphs, "Poderes Angelicais", "regras_base", 975, 979),
        make_section(paragraphs, "Criação de Itens Mágicos", "regras_base", 1374, 1377),
        make_section(paragraphs, "Regras e Testes", "regras_base", 1421, 1732),
        make_section(paragraphs, "Criando sua Própria Cidade de Anjos", "regras_base", 1732, len(paragraphs)),
    ]

    class_ranges = [
        ("Corpore", 553, 589),
        ("Protetores", 589, 666),
        ("Captare", 666, 702),
        ("Recíperes", 702, 740),
        ("Nimbus", 740, 778),
    ]
    classes = [make_class(title, collect(paragraphs, start, end)) for title, start, end in class_ranges]

    enhancement_ranges = [
        ("Afinidade com Fadas", 893, 899),
        ("Alma Dupla", 899, 902),
        ("Ambidestria", 902, 904),
        ("Biblioteca Arcana", 904, 909),
        ("Clero", 909, 917),
        ("Contatos", 917, 918),
        ("Detecção de Magia", 918, 921),
        ("Gárgula", 921, 926),
        ("Guardião de um Artefato Importante", 926, 929),
        ("Local de Controle", 929, 931),
        ("Objetos Mágicos", 931, 932),
        ("Pactos", 932, 934),
        ("Palavra de Deus", 934, 936),
        ("Pertencer a uma Escola de Magia", 936, 940),
        ("Pertencer ou Comandar uma Seita", 940, 942),
        ("Poderes Mágicos", 942, 950),
        ("Sensitivo", 950, 956),
        ("Senso de Direção", 956, 958),
        ("Senso", 958, 960),
        ("Sentidos Aguçados", 960, 962),
        ("Sortudo", 962, 964),
        ("Talento", 964, 966),
        ("Tutor", 966, 970),
        ("Pontos de Fé", 1379, 1394),
    ]
    enhancements = [
        split_cost_sections(title, collect(paragraphs, start, end))
        for title, start, end in enhancement_ranges
    ]

    power_ranges = [
        ("Aumento de Atributos", 980, 991),
        ("Asas Astrais", 991, 1000),
        ("Bard", 1000, 1014),
        ("Benção", 1014, 1025),
        ("Captare", 1025, 1038),
        ("Combate", 1038, 1044),
        ("Comunhão", 1044, 1048),
        ("Controle Mental", 1048, 1076),
        ("Defesas", 1076, 1085),
        ("Defesas Especiais", 1085, 1100),
        ("Disfarces", 1100, 1105),
        ("Dreno", 1105, 1119),
        ("Druidia", 1119, 1157),
        ("Glifo", 1157, 1167),
        ("Lex Talionis", 1167, 1176),
        ("Mensageiro Celestial", 1176, 1190),
        ("Nimbus", 1190, 1208),
        ("Passagem Astral", 1208, 1219),
        ("Percepção Divina", 1219, 1230),
        ("Querubia", 1230, 1245),
        ("Regeneração", 1245, 1254),
        ("Simulacro", 1254, 1259),
        ("Telecinesia", 1259, 1266),
    ]
    powers = [
        split_power(title, collect(paragraphs, start, end))
        for title, start, end in power_ranges
    ]

    faith_uses = typed_item(
        "Usos de Pontos de Fé",
        "regras_base",
        "ruleset",
        "Regra Base",
        collect(paragraphs, 1394, 1421),
        [
            make_section(paragraphs, "Afastar Mortos-Vivos", "regras_base", 1394, 1406),
            make_section(paragraphs, "Ativação de Itens Mágicos", "regras_base", 1406, 1407),
            make_section(paragraphs, "Benção", "regras_base", 1407, 1409),
            make_section(paragraphs, "Controlar Mortos-Vivos", "regras_base", 1409, 1411),
            make_section(paragraphs, "Conversar com Pássaros e Animais", "regras_base", 1411, 1413),
            make_section(paragraphs, "Cura", "regras_base", 1413, 1415),
            make_section(paragraphs, "Criação de Água Benta", "regras_base", 1415, 1417),
            make_section(paragraphs, "Encantar", "regras_base", 1417, 1421),
        ],
    )

    groups = [
        {
            "id": "anjos-cidade-prata-lore",
            "title": TITLE,
            "kind": "setting",
            "area": "cenarios_lore",
            "sectionTitle": "Cenário",
            "sections": lore_sections,
        },
        {
            "id": "regra-base-anjos-cidade-prata",
            "title": f"Regra base - {TITLE}",
            "kind": "ruleset",
            "area": "regras_base",
            "sectionTitle": "Regra Base",
            "sections": rules_sections,
        },
    ]

    sections = classes + enhancements + powers + item_entries(paragraphs) + [faith_uses]
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
        "summary": "Livro-base sobre a Cidade de Prata, com lore de Paradísia, castas angelicais, criação de personagens, aprimoramentos, poderes angelicais, itens mágicos, Pontos de Fé e regras de testes/combate.",
        "areas": areas,
        "groups": groups,
        "sections": sections,
        "areaCounts": area_counts,
        "reviewNotes": [
            "Primeira revisão controlada após remoção do lote de Anjos; validar este livro antes de avançar para outro.",
            "O DOCX revisado foi usado como fonte primária porque está mais limpo que data/text/anjos-a-cidade-de-prata.txt.",
            "Nenhum NPC foi publicado nesta rodada: o DOCX disponível termina antes das fichas de NPCs indicadas no índice.",
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
