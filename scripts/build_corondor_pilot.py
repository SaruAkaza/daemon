from __future__ import annotations

import re
from datetime import datetime
from typing import Iterable

from docx import Document

from common import ROOT, slugify, write_json


SOURCE = "corondor"
TITLE = "Corondor"
SOURCE_FILE = "Corondor.docx"
SOURCE_CANDIDATES = [
    ROOT / "Livros" / "word" / SOURCE_FILE,
    ROOT / "Livros" / "word" / "feito" / SOURCE_FILE,
]
SOURCE_PATH = next(path for path in SOURCE_CANDIDATES if path.exists())
OUT_PATH = ROOT / "data" / "pilot" / f"{SOURCE}.json"
DOCS_OUT_PATH = ROOT / "docs" / "assets" / "data" / "pilot" / f"{SOURCE}.json"


TEXT_FIXES = {
    "conehcidas": "conhecidas",
    "artifical": "artificial",
    "planinauta": "planeswalker",
    "planinalta": "planeswalker",
    "coma  planinauta": "com a planeswalker",
    "cria aCidadela": "cria a Cidadela",
    "Impéri Madaran": "Império Madaran",
    "frustados": "frustrados",
    "prerevisionist ocorreu": "pré-revisionistas ocorreram",
    "Dungeons perigosa": "masmorras perigosas",
    "profundesas": "profundezas",
    "disfarção": "disfarçam",
    "dimenção": "dimensão",
    "vitima": "vítima",
    "ate ": "até ",
    "rotada": "rodada",
    "rnax": "máx",
    "superficies livremante": "superfícies livremente",
    "Péle": "Pele",
    "Peçonha": "Peçonha",
    "critico": "crítico",
    "Vêr": "ver",
    "Pericias": "Perícias",
    "Maximo": "Máximo",
    "qual quer": "qualquer",
    "passara": "passará",
    "Server": "serve",
    "Chail Heal": "Chain Heal",
    "Feral Spisrit": "Feral Spirit",
    "Spiritun": "Spiritum",
    "fies ao conjurador": "fiéis ao conjurador",
    "Saring Toten": "Searing Totem",
    "Mana Soring Totem": "Mana Spring Totem",
    "Elemenmtal Resistence Totem": "Elemental Resistance Totem",
    "Flametogue Totem": "Flametongue Totem",
    "Grouding Totem": "Grounding Totem",
    "Eartbind Totem": "Earthbind Totem",
    "duarbilidade": "durabilidade",
    "paracada": "para cada",
    "Pontos Heróicos": "Pontos Heroicos",
    "combaté": "combate",
    "Você e mais poderoso": "Você é mais poderoso",
    "A única restrição e que": "A única restrição é que",
    "uma único": "um único",
    "distancia": "distância",
    "Máximo": "máximo",
    "portőes": "portões",
    "passarám": "passaram",
    "dissaparecendo": "desaparecendo",
    "Idade: ?? Anos, altura 3,00 cm, ???kg": "Idade desconhecida, altura 3,00 m, peso desconhecido.",
    "Idade:?? Anos, altura 3,00 cm,???kg": "Idade desconhecida, altura 3,00 m, peso desconhecido.",
    "PVs": "PVs",
    "Pvs": "PVs",
    "Pvs.": "PVs.",
    "Pvs,": "PVs,",
}

INLINE_TITLES = [
    "Aceleração",
    "Adaptação",
    "Ambiente Especial",
    "Armas Naturais",
    "Ataque Especial",
    "Ataque Extra",
    "Contra ataque",
    "Contra ataque aprimorado",
    "Elasticidade",
]

POWER_TITLES = {
    "Aumento de Atributos",
    "Asas",
    "Ataque Extra",
    "Bafo",
    "Chifres",
    "Defesas Especiais",
    "Dentes e Boca",
    "Disfarces",
    "Garras",
    "Inspirar Terror",
    "Moldar Exoesqueleto",
    "Matilha",
    "Mutilação",
    "Patas de Aracnídeas ou Insectóide",
    "Patas e Cascos",
    "Pele Grossa",
    "Pinças",
    "Peçonha",
    "Regeneração",
    "Sentir o Sobrenatural",
    "Sombras",
    "Tamanho",
    "Visão Noturna",
}

ENHANCEMENT_HEADINGS = {"Novos Aprimoramentos:", "Aprimoramentos Positivos", "Aprimoramentos Negativos"}

ENHANCEMENT_TITLES = {
    "Aceleração",
    "Adaptador",
    "Adaptação",
    "Adiar Magia",
    "Alergia",
    "Ambiente Especial",
    "Ampliar Magia",
    "Armas Naturais",
    "Ataque Especial",
    "Ataque Extra",
    "Atropelar",
    "Caçado",
    "Contra ataque",
    "Contra ataque aprimorado",
    "Corpo Flexível",
    "Dano Maciço",
    "Deslocamento em velocidade",
    "Deslocamento em velocidade Aprimorado",
    "Deslocamento Especial",
    "Dominado",
    "Elasticidade",
    "Empatia com Animais",
    "Energia Extra",
    "Expert",
    "Feitiçaria",
    "Foco em Caminho",
    "Forma Alternativa",
    "Fracote",
    "Gênio",
    "Hábil",
    "Ignorar componente",
    "Imortalidade Química",
    "Imunidade",
    "Iniciativa",
    "Invisibilidade",
    "Invocação Aprimorada",
    "Inábil",
    "Item Pessoal",
    "Ligação Natural",
    "Maestria em Caminho",
    "Magia Cooperativa",
    "Magia Sequencial",
    "Marcado a Ferro",
    "Memória Expandida",
    "Mente Repartilhada",
    "Mesclar-se as Sombras",
    "Paralisia",
    "Pele Metálica",
    "Poder Elevado",
    "Poder Oculto (1 a 12 Pontos)",
    "Ponto Fraco",
    "Pontos de Vida Extras",
    "Presença Invisível",
    "Reflexão",
    "Regeneração",
    "Resistência",
    "Ritualismo",
    "Saque rápido",
    "Saúde de Rato",
    "Sensibilidade a Luz",
    "Sentido de Perigo",
    "Supremacia em Caminho",
    "Tamanho Especial",
    "Telepatia",
    "Teletransporte",
    "Vidas Gastas Apenas para Gnomos",
    "Vulnerabilidade",
    "Vírus",
    "Vôo",
}


def normalize_text(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = text.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    text = text.replace("–", "-").replace("—", "-")
    text = re.sub(r"(?<=\w)-\s+(?=[a-záéíóúâêôãõç])", "", text)
    for old, new in TEXT_FIXES.items():
        text = text.replace(old, new)
    text = re.sub(r"\bId6\b", "1d6", text)
    text = re.sub(r"\bIPn\b", "IP natural", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"^([+-])\s+(\d+\s+pontos?)", r"\1\2", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"\(\s+", "(", text)
    text = re.sub(r"\s+\)", ")", text)
    return text


def should_join(previous: str, current: str) -> bool:
    if not previous or not current:
        return False
    if previous.endswith("-") and current[:1].islower():
        return True
    if current[:1].islower() and not previous.endswith((".", "!", "?", ":", ";", '"')):
        return True
    if previous.split()[-1].lower().strip(".,;:!?") in {
        "de",
        "do",
        "da",
        "dos",
        "das",
        "em",
        "por",
        "com",
        "para",
        "que",
        "e",
        "a",
        "o",
    }:
        return True
    return False


def clean(values: Iterable[str]) -> list[str]:
    paragraphs: list[str] = []
    for raw in values:
        for part in re.split(r"\n\s*\n+", raw):
            text = normalize_text(" ".join(line.strip() for line in part.splitlines() if line.strip()))
            if not text or text in ENHANCEMENT_HEADINGS:
                continue
            if re.fullmatch(r"\d{1,3}", text):
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
    return [paragraph.text for paragraph in Document(SOURCE_PATH).paragraphs if paragraph.text.strip()]


def collect(paragraphs: list[str], start: int, end: int) -> list[str]:
    return clean(paragraphs[start:end])


def section(section_id: str, title: str, area: str, paragraphs: list[str]) -> dict:
    return {"id": section_id, "title": title, "area": area, "paragraphs": paragraphs}


def typed_item(title: str, area: str, kind: str, sections: list[dict], paragraphs: list[str] | None = None) -> dict:
    visible_paragraphs = paragraphs if paragraphs is not None else [p for block in sections for p in block["paragraphs"]]
    return {
        "id": slugify(f"{area}-{title}"),
        "title": title,
        "area": area,
        "kind": kind,
        "sectionId": slugify(title),
        "sectionTitle": title,
        "paragraphs": visible_paragraphs,
        "sections": sections,
    }


def simple_item(title: str, area: str, kind: str, paragraphs: list[str]) -> dict:
    return typed_item(title, area, kind, [section("descricao", "Descrição", area, paragraphs)], paragraphs)


def split_compound_segments(values: Iterable[str]) -> list[str]:
    raw = "\n\n".join(values)
    for title in INLINE_TITLES:
        raw = re.sub(rf"(?<!\n)({re.escape(title)})(?=\s+(?:-?\d|Variável|O personagem|Para cada|Pra cada))", r"\n\n\1", raw)
    segments: list[str] = []
    for part in re.split(r"\n\s*\n+", raw):
        text = normalize_text(" ".join(line.strip() for line in part.splitlines() if line.strip()))
        if text:
            segments.append(text)
    return segments


def is_title_segment(value: str) -> bool:
    if value in ENHANCEMENT_TITLES:
        return True
    if value in ENHANCEMENT_HEADINGS:
        return False
    if not value[:1].isupper():
        return False
    if re.match(r"^-?\s*\d", value) or value == "Variável":
        return False
    if re.match(r"^(Restrição|Poderes Possíveis|Fraquezas|Custo|Perícias|Aprimoramentos|Formas e Caminhos|Fetiches|Descrição):", value):
        return False
    if ":" in value and len(value) > 45:
        return False
    if len(value) > 80:
        return False
    return False


def split_title_with_cost(value: str) -> tuple[str, str] | None:
    for title in sorted(ENHANCEMENT_TITLES, key=len, reverse=True):
        if value.startswith(title + " "):
            rest = value[len(title) :].strip()
            if is_cost_segment(rest):
                return title, rest
    return None


def is_cost_segment(value: str) -> bool:
    return bool(re.match(r"^-?\s*\d+(?:,\d+)?\s+pontos?\b", value, re.IGNORECASE)) or value == "Variável" or bool(
        re.search(r"\(\s*-?\d+\s+pontos?\s*\)", value, re.IGNORECASE)
    )


def split_single_cost(value: str) -> tuple[str, str] | None:
    match = re.match(r"^(-?\s*\d+(?:,\d+)?\s+pontos?(?:\s+por\s+nível)?)\s*[:.-]\s*(.+)$", value, re.IGNORECASE)
    if not match:
        return None
    return normalize_text(match.group(1)), normalize_text(match.group(2))


def expand_inline_cost_options(costs: list[str], description: list[str]) -> tuple[list[str], list[str]]:
    if len(costs) != 1 or not description:
        return costs, description
    first = description[0]
    matches = list(re.finditer(r"(?<!\w)(-?\s*\d+(?:,\d+)?\s+pontos?)\s*:\s*", first, flags=re.IGNORECASE))
    if not matches:
        return costs, description

    expanded = costs[:]
    prefix = normalize_text(first[: matches[0].start()])
    if prefix:
        expanded[0] = normalize_text(f"{expanded[0]}: {prefix}")
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(first)
        option_text = normalize_text(first[match.end() : end])
        expanded.append(normalize_text(f"{match.group(1)}: {option_text}"))
    return expanded, description[1:]


def build_enhancements(paragraphs: list[str]) -> list[dict]:
    segments = split_compound_segments(paragraphs[415:497])
    items: list[dict] = []
    current_title: str | None = None
    current: list[str] = []
    negative = False

    def flush() -> None:
        nonlocal current_title, current, negative
        if not current_title:
            current = []
            return
        values = clean(current)
        costs = [value for value in values if is_cost_segment(value)]
        description = [value for value in values if value not in costs]
        if len(costs) == 1:
            split = split_single_cost(costs[0])
            if split:
                costs = [split[0]]
                description.insert(0, split[1])
        costs, description = expand_inline_cost_options(costs, description)
        paren_cost = re.search(r"\(([^)]*\d+\s+(?:Pontos?|pontos?)[^)]*)\)$", current_title)
        if not costs and paren_cost:
            costs.append(normalize_text(paren_cost.group(1)))
            title = current_title[: paren_cost.start()].strip()
        else:
            title = current_title
        if not costs and re.search(r"\s+\d+\s+pontos?(?:\s+por\s+\w+)?$", current_title, re.IGNORECASE):
            title = re.sub(r"\s+\d+\s+pontos?(?:\s+por\s+\w+)?$", "", current_title, flags=re.IGNORECASE).strip()
            costs.append(current_title[len(title):].strip())
        sections = [
            section("custo", "Custo", "aprimoramentos", costs),
            section("descricao", "Descrição", "aprimoramentos", description),
        ]
        items.append(typed_item(title, "aprimoramentos", "enhancement_negative" if negative else "enhancement", sections, values))
        current_title = None
        current = []

    for segment in segments:
        if segment == "Aprimoramentos Positivos":
            flush()
            negative = False
            continue
        if segment == "Aprimoramentos Negativos":
            flush()
            negative = True
            continue
        if segment in ENHANCEMENT_HEADINGS:
            continue
        title_with_cost = split_title_with_cost(segment)
        if title_with_cost:
            flush()
            current_title, cost = title_with_cost
            current.append(cost)
            continue
        if is_title_segment(segment):
            flush()
            current_title = segment
        elif current_title:
            current.append(segment)
    flush()
    return items


def build_powers(paragraphs: list[str]) -> list[dict]:
    values = clean(paragraphs[227:386])
    items: list[dict] = []
    current_title: str | None = None
    current: list[str] = []

    def flush() -> None:
        nonlocal current_title, current
        if not current_title:
            current = []
            return
        blocks: list[dict] = []
        intro: list[str] = []
        levels: dict[str, list[str]] = {}
        for value in current:
            match = re.match(r"^(Nível\s+[^:]+):\s*(.*)$", value, flags=re.IGNORECASE)
            if match:
                key = normalize_text(match.group(1))
                levels.setdefault(key, [])
                if match.group(2).strip():
                    levels[key].append(normalize_text(match.group(2)))
            elif levels and not value.endswith(":"):
                last = next(reversed(levels))
                levels[last].append(value)
            else:
                intro.append(value)
        if intro:
            blocks.append(section("descricao", "Descrição", "poderes", intro))
        for key, vals in levels.items():
            blocks.append(section(slugify(key), key, "poderes", vals))
        items.append(typed_item(current_title, "poderes", "power", blocks, current))
        current_title = None
        current = []

    for value in values:
        if value in POWER_TITLES:
            flush()
            current_title = value
        elif current_title:
            current.append(value)
    flush()
    return items


def parse_named_rituals(values: list[str], start: int, end: int) -> list[dict]:
    paragraphs = clean(values[start:end])
    items: list[dict] = []
    current_title: str | None = None
    current: list[str] = []

    def flush() -> None:
        nonlocal current_title, current
        if not current_title:
            current = []
            return
        buckets = {
            "pre_requisitos": [],
            "formas": [],
            "custo": [],
            "fetiches": [],
            "descricao": [],
        }
        for value in current:
            match = re.match(r"^(Formas e Caminhos|Custo|Fetiches|Descrição):\s*(.*)$", value, re.IGNORECASE)
            if match:
                label = match.group(1).lower()
                key = {"formas e caminhos": "formas", "custo": "custo", "fetiches": "fetiches", "descrição": "descricao"}[label]
                if match.group(2).strip():
                    buckets[key].append(match.group(2).strip())
            else:
                buckets["descricao"].append(value)
        blocks = []
        if buckets["pre_requisitos"]:
            blocks.append(section("pre-requisitos", "Pré-requisitos", "rituais", buckets["pre_requisitos"]))
        if buckets["formas"]:
            blocks.append(section("formas-e-caminhos", "Formas e Caminhos", "rituais", buckets["formas"]))
        if buckets["custo"]:
            blocks.append(section("custo", "Custo", "rituais", buckets["custo"]))
        if buckets["fetiches"]:
            blocks.append(section("fetiches", "Fetiches", "rituais", buckets["fetiches"]))
        blocks.append(section("descricao", "Descrição", "rituais", buckets["descricao"]))
        items.append(typed_item(current_title, "rituais", "ritual", blocks, current))
        current_title = None
        current = []

    for value in paragraphs:
        match = re.match(r"^Nome:\s*(.+)$", value)
        if match:
            flush()
            current_title = match.group(1).strip()
        elif current_title:
            current.append(value)
    flush()
    return items


def build_specialties(paragraphs: list[str]) -> list[dict]:
    values = clean(paragraphs[386:413])
    intro = values[:1]
    title_re = re.compile(r"^(.+?\[\d+\])$")
    items: list[dict] = []
    current_title: str | None = None
    current: list[str] = []

    def flush() -> None:
        nonlocal current_title, current
        if current_title:
            items.append(simple_item(current_title, "manobras_combate", "skill_specialty", current))
        current_title = None
        current = []

    if intro:
        items.append(simple_item("Especialidades Mágicas", "manobras_combate", "skill_rule", intro))
    for value in values[1:]:
        if title_re.match(value):
            flush()
            current_title = value
        elif current_title:
            current.append(value)
    flush()
    return items


def race_or_creature(title: str, paragraphs: list[str]) -> list[dict]:
    sections = [section("descricao", "Descrição", "racas", paragraphs)]
    race = typed_item(title, "racas", "race", sections, paragraphs)
    creature_sections = [section("descricao", "Descrição", "criaturas_npcs", paragraphs)]
    creature = typed_item(title, "criaturas_npcs", "creature", creature_sections, paragraphs)
    return [race, creature]


def make_race(title: str, paragraphs: list[str], kind: str = "race") -> dict:
    return typed_item(title, "racas", kind, [section("descricao", "Descrição", "racas", paragraphs)], paragraphs)


def make_creature(title: str, paragraphs: list[str], kind: str = "creature") -> dict:
    blocks: list[dict] = []
    attrs = [value for value in paragraphs if re.search(r"\b(CON|FOR|FR)\b.*\b(DEX|AGI)\b", value)]
    skills = [value for value in paragraphs if value.startswith(("Perícias", "Pericias")) or "Dano" in value or "#Ataques" in value]
    abilities = [value for value in paragraphs if value not in attrs and value not in skills]
    if attrs:
        blocks.append(section("atributos", "Atributos", "criaturas_npcs", attrs))
    if skills:
        blocks.append(section("pericias-e-combate", "Perícias e Combate", "criaturas_npcs", skills))
    blocks.append(section("habilidades", "Habilidades", "criaturas_npcs", abilities))
    return typed_item(title, "criaturas_npcs", kind, blocks, paragraphs)


def build_races_and_lore(paragraphs: list[str]) -> list[dict]:
    items: list[dict] = []
    lore_sections = [
        section("cronologia", "Cronologia", "cenarios_lore", collect(paragraphs, 0, 85)),
        section("corondor-e-regioes", "Corondor e Regiões", "cenarios_lore", collect(paragraphs, 85, 141)),
        section("adam-carthalion", "Adam Carthalion", "cenarios_lore", collect(paragraphs, 141, 146)),
        section("aves", "Aves", "cenarios_lore", collect(paragraphs, 146, 150)),
    ]
    items.append(typed_item("Cenarios/Lore - Corondor", "cenarios_lore", "setting", lore_sections))
    items.extend(race_or_creature("Insectóides", collect(paragraphs, 150, 153)))
    items.extend(race_or_creature("Mantídeos", collect(paragraphs, 153, 161)))
    items.extend(race_or_creature("Nerubiano", collect(paragraphs, 161, 165)))
    items.extend(race_or_creature("Drider", collect(paragraphs, 165, 168)))
    items.extend(race_or_creature("Minotauros", collect(paragraphs, 178, 181)))
    items.extend(race_or_creature("Draconianos", collect(paragraphs, 183, 193)))
    for title, start, end in [
        ("Aurak", 193, 203),
        ("Baaz", 203, 208),
        ("Bozak", 208, 214),
        ("Kapak", 214, 220),
        ("Sivak", 220, 226),
    ]:
        values = collect(paragraphs, start, end)
        items.append(make_race(title, values, "draconian_subrace"))
        items.append(make_creature(title, values, "draconian_creature"))
    items.append(make_race("Mecanóides", collect(paragraphs, 559, 561), "race"))
    return items


def build_items(paragraphs: list[str]) -> list[dict]:
    values = paragraphs
    return [
        typed_item(
            "Forja e Criação de Itens Mágicos",
            "itens_equipamentos",
            "item_rule",
            [
                section("forja", "Forja", "itens_equipamentos", collect(values, 561, 617)),
                section("trabalho-nas-forjas", "O Trabalho nas Forjas", "itens_equipamentos", collect(values, 617, 655)),
                section("armas", "Armas", "itens_equipamentos", collect(values, 655, 697)),
                section("armaduras-e-escudos", "Armaduras e Escudos", "itens_equipamentos", collect(values, 697, 714)),
                section("inscricoes-magicas-dos-anoes", "Inscrições Mágicas dos Anões", "itens_equipamentos", collect(values, 714, 794)),
            ],
        ),
        typed_item(
            "Mecanóides - Corpos e Componentes",
            "itens_equipamentos",
            "item_rule",
            [
                section("conceito", "Conceito", "itens_equipamentos", collect(values, 497, 505)),
                section("membro-mecanico-magico", "Membro Mecânico Mágico", "itens_equipamentos", collect(values, 505, 512)),
                section("corpos-mecanoides", "Corpos Mecanóides", "itens_equipamentos", collect(values, 512, 546)),
                section("modelos-de-combate", "Modelos de Combate", "itens_equipamentos", collect(values, 529, 555)),
            ],
        ),
    ]


def build_kits(paragraphs: list[str]) -> list[dict]:
    common_cost = clean([paragraphs[795]])
    common_description = clean([paragraphs[796]])
    variants = [
        ("Shaman de Combate", 797, 800),
        ("Shaman Curandeiro", 800, 808),
        ("Shaman Elemental", 808, 810),
    ]
    items = []
    for title, start, end in variants:
        values = clean(paragraphs[start:end])
        skills = [value for value in values if value.startswith("Perícias")]
        enhancements = [value for value in values if value.startswith("Aprimoramentos:")]
        description = [value for value in values if value not in skills and value not in enhancements]
        items.append(
            typed_item(
                title,
                "kits",
                "kit",
                [
                    section("custo", "Custo", "kits", common_cost),
                    section("custo-de-pericia", "Custo de Perícia", "kits", skills),
                    section("aprimoramentos", "Aprimoramentos", "kits", enhancements),
                    section("descricao", "Descrição", "kits", common_description + description),
                ],
                common_cost + values,
            )
        )
    return items


def build_mechanoid_kit(paragraphs: list[str]) -> list[dict]:
    values = clean(paragraphs[555:559])
    costs = [value.replace("Custo: ", "") for value in values if value.startswith("Custo:")]
    skills = [value.replace("Perícias: ", "") for value in values if value.startswith("Perícias:")]
    enhancements = [value.replace("Aprimoramentos: ", "") for value in values if value.startswith("Aprimoramentos:")]
    description = [value for value in values if not value.startswith(("Custo:", "Perícias:", "Aprimoramentos:"))]
    return [
        typed_item(
            "Máquina de Guerra Mecanóide",
            "kits",
            "kit",
            [
                section("custo", "Custo", "kits", costs),
                section("custo-de-pericia", "Custo de Perícia", "kits", skills),
                section("aprimoramentos", "Aprimoramentos", "kits", enhancements),
                section("descricao", "Descrição", "kits", description),
            ],
            values,
        )
    ]


def build_totems(paragraphs: list[str]) -> list[dict]:
    items: list[dict] = []
    items.append(
        typed_item(
            "Totens",
            "itens_equipamentos",
            "totem_rule",
            [
                section("custo", "Custo", "itens_equipamentos", collect(paragraphs, 810, 825)),
                section("descricao", "Descrição", "itens_equipamentos", ["Regras de custo e permanência para totens do Shaman."]),
            ],
        )
    )
    npc_ranges = [
        ("Totem Elemental do Fogo", 825, 848),
        ("Totem Elemental da Terra", 848, 868),
        ("Totem Elemental da Tempestade", 868, 890),
    ]
    for title, start, end in npc_ranges:
        values = clean(paragraphs[start:end])
        attrs = [value for value in values if re.search(r"\bCON\b.*\bFR\b.*\bDEX\b", value)]
        skills = [value for value in values if "Dano" in value or value.startswith("Perícias:") or value.startswith("Pericias:")]
        abilities = [value for value in values if value not in attrs and value not in skills and not value.startswith(("Tempo de permanência", "0,5", "1 ponto", "1,5"))]
        items.append(
            typed_item(
                title,
                "itens_equipamentos",
                "totem",
                [
                    section("atributos", "Atributos", "itens_equipamentos", attrs),
                    section("pericias-e-combate", "Perícias e Combate", "itens_equipamentos", skills),
                    section("habilidades", "Habilidades", "itens_equipamentos", abilities),
                ],
                values,
            )
        )
    power_names = [
        "Stoneskin Totem.",
        "Earthbind Totem.",
        "Searing Totem.",
        "Strength of Earth Totem.",
        "Tremor Totem.",
        "Healing Stream Totem.",
        "Mana Spring Totem.",
        "Elemental Resistance Totem.",
        "Flametongue Totem.",
        "Grounding Totem.",
        "Windfury Totem.",
    ]
    values = clean(paragraphs[890:984])
    current_title: str | None = None
    current: list[str] = []

    def flush() -> None:
        nonlocal current_title, current
        if current_title:
            costs = [value for value in current if is_cost_segment(value)]
            description = [value for value in current if value not in costs]
            items.append(
                typed_item(
                    current_title.rstrip("."),
                    "itens_equipamentos",
                    "totem",
                    [
                        section("custo", "Custo", "itens_equipamentos", costs),
                        section("descricao", "Descrição", "itens_equipamentos", description),
                    ],
                    current,
                )
            )
        current_title = None
        current = []

    for value in values:
        if value in power_names:
            flush()
            current_title = value
        elif current_title:
            current.append(value)
    flush()
    return items


def build_payload() -> dict:
    paragraphs = docx_paragraphs()
    sections: list[dict] = []
    sections.extend(build_races_and_lore(paragraphs))
    sections.extend(parse_named_rituals(paragraphs, 168, 178))
    sections.extend(build_powers(paragraphs))
    sections.extend(build_specialties(paragraphs))
    sections.extend(build_enhancements(paragraphs))
    sections.extend(build_items(paragraphs))
    sections.extend(build_kits(paragraphs))
    sections.extend(build_mechanoid_kit(paragraphs))
    sections.extend(build_totems(paragraphs))
    sections.extend(parse_named_rituals(paragraphs, 984, len(paragraphs)))

    sections.sort(key=lambda item: (item["area"], item["title"].casefold()))
    areas = sorted({item["area"] for item in sections})
    return {
        "version": 1,
        "source": SOURCE,
        "title": TITLE,
        "sourceFile": SOURCE_FILE,
        "status": "pilot_review",
        "summary": "Catálogo revisado a partir do DOCX de Corondor, com lore, raças/criaturas, poderes, perícias, aprimoramentos, itens, kits, totens e rituais separados por entidade.",
        "areas": areas,
        "groups": [],
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "sections": sections,
    }


def main() -> None:
    payload = build_payload()
    write_json(OUT_PATH, payload)
    write_json(DOCS_OUT_PATH, payload)
    print(f"Wrote {OUT_PATH.relative_to(ROOT)} with {len(payload['sections'])} items.")


if __name__ == "__main__":
    main()
