from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Iterable

from common import ROOT, slugify, write_json


SOURCE = "spiritum"
TITLE = "Spiritum"
SOURCE_FILE = "Spiritum_OCR_parcial_com_imagens.docx"
TXT_PATH = ROOT / "data" / "text" / "spiritum.txt"
OUT_PATH = ROOT / "data" / "pilot" / f"{SOURCE}.json"
DOCS_OUT_PATH = ROOT / "docs" / "assets" / "data" / "pilot" / f"{SOURCE}.json"


TEXT_FIXES = {
    "1dó": "1d6",
    "2dó": "2d6",
    "3dó": "3d6",
    "4dó": "4d6",
    "dó pontos": "d6 pontos",
    "idéia": "ideia",
    "idéias": "ideias",
    "à partir": "a partir",
    "sentí-lo": "senti-lo",
    "resíde": "reside",
    "Useo": "Use o",
    "Personagm": "Personagem",
    "Personagmns": "Personagens",
    "Personagmnes": "Personagens",
    "personagm": "personagem",
    "persongem": "personagem",
    "aerícia": "perícia",
    "primerias": "primeiras",
    "encamação": "encarnação",
    "encamações": "encarnações",
    "reencamações": "reencarnações",
    "Infemo": "Inferno",
    "Aúltima": "A última",
    "pesíodos": "períodos",
    "fecnológicos": "tecnológicos",
    "imediatamente": "imediatamente",
    "superficie": "superfície",
    "Estudiosos do Umbral têm permissão": "Estudiosos do Umbral têm permissão",
    "porsero": "por ser o",
    "dado e nome": "dado o nome",
    "icou provado": "Ficou provado",
    "A Igreja c as Mentiras": "A Igreja e as Mentiras",
    "Espíritos 0 Reino dos Mortos": "Espíritos e o Reino dos Mortos",
    "Siíbilas": "Sibilas",
    "adomos": "adornos",
    "Christo": "Cristo",
    "fisi- cos": "físicos",
    "MWILL": "WILL",
    "zodada": "rodada",
    "Sal e o Nível": "Salto e o Nível",
    "duas vezés": "duas vezes",
    "Etérca": "Etérea",
    "forma-penasmento": "forma-pensamento",
    "formas-penasmento": "formas-pensamento",
    "regides": "regiões",
    "=ão": "são",
    "grentureiros": "aventureiros",
    "tipso": "tipos",
    "acizentados": "acinzentados",
    "Intemet": "Internet",
    "simpelsmente": "simplesmente",
    "humanso": "humanos",
    "fomece": "fornece",
    "dificil": "difícil",
    "construíndo": "construindo",
    "humanóides": "humanoides",
    "Contatos c Aliados": "Contatos e Aliados",
    "Obcessores": "Obsessores",
    "obcessores": "obsessores",
    "obcessor": "obsessor",
    "obcessão": "obsessão",
    "obcessões": "obsessões",
    "obcediado": "obsediado",
    "obcediados": "obsediados",
    "obcediado": "obsediado",
    "obcediar": "obsediar",
    "AGla": "AGI",
    "AGT": "AGI",
    "capza": "capaz",
    "Ysca": "Ysea",
    "Ysea são": "Ysea são",
    "petimitériiaos": "permitem aos",
    "iverem": "viverem",
    "fomece": "fornece",
    "definído": "definido",
    "sacrificio": "sacrifício",
}

DROP_PARAGRAPHS = {
    TITLE,
    "Texto extraído por OCR / camada textual, com limpeza de quebras de linha e caracteres indevidos.",
}


def load_pages() -> dict[int, str]:
    raw = TXT_PATH.read_text(encoding="utf-8")
    parts = re.split(r"^--- page (\d+) ---\s*$", raw, flags=re.MULTILINE)
    return {int(parts[index]): parts[index + 1] for index in range(1, len(parts), 2)}


PAGES = load_pages()


def normalize_text(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = text.replace("|", " ")
    text = text.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    text = text.replace("—", "-").replace("–", "-")
    for old, new in TEXT_FIXES.items():
        text = text.replace(old, new)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"\(\s+", "(", text)
    text = re.sub(r"\s+\)", ")", text)
    text = re.sub(r"\b0 Personagem\b", "O Personagem", text)
    return text


def clean_block(text: str) -> list[str]:
    text = re.sub(r"(?<=\w)-\s*\n\s*(?=[a-zà-ÿ])", "", text)
    paragraphs: list[str] = []
    for raw in re.split(r"\n\s*\n+", text):
        cleaned_lines = []
        for line in raw.splitlines():
            line = line.strip()
            if not line or line in DROP_PARAGRAPHS:
                continue
            if re.fullmatch(r"\d{1,3}", line):
                continue
            if re.fullmatch(r"[$&|/\\\s]+", line):
                continue
            if line.startswith("--- page"):
                continue
            cleaned_lines.append(line)
        paragraph = normalize_text(" ".join(cleaned_lines))
        if paragraph and paragraph not in DROP_PARAGRAPHS:
            paragraphs.append(paragraph)
    return paragraphs


def page_text(pages: Iterable[int]) -> str:
    return "\n".join(PAGES[page] for page in pages if page in PAGES)


def paragraphs_from_pages(pages: Iterable[int], *, drop_headings: Iterable[str] = ()) -> list[str]:
    paragraphs = clean_block(page_text(pages))
    drops = {normalize_text(value).lower() for value in drop_headings}
    return [paragraph for paragraph in paragraphs if paragraph.lower() not in drops]


def extract_between(pages: Iterable[int], start: str, end: str | None = None) -> list[str]:
    text = page_text(pages)
    start_match = re.search(rf"(?m)^\s*{re.escape(start)}\s*$", text)
    if not start_match:
        return []
    start_index = start_match.end()
    end_index = len(text)
    if end:
        end_match = re.search(rf"(?m)^\s*{re.escape(end)}\s*$", text[start_index:])
        if end_match:
            end_index = start_index + end_match.start()
    return clean_block(text[start_index:end_index])


def item(
    title: str,
    area: str,
    kind: str,
    paragraphs: list[str] | None = None,
    sections: list[dict] | None = None,
    **extra: str,
) -> dict:
    return {
        "id": slugify(title),
        "title": title,
        "area": area,
        "kind": kind,
        "sectionId": kind,
        "sectionTitle": title,
        "paragraphs": paragraphs or [],
        "sections": sections or [],
        **extra,
    }


def block(title: str, area: str, paragraphs: list[str]) -> dict:
    return {
        "id": slugify(title),
        "title": title,
        "area": area,
        "paragraphs": paragraphs,
    }


def sectioned_from_pages(title: str, pages: Iterable[int], headings: list[str], area: str) -> dict:
    sections = []
    for index, heading in enumerate(headings):
        next_heading = headings[index + 1] if index + 1 < len(headings) else None
        paragraphs = extract_between(pages, heading, next_heading)
        if paragraphs:
            sections.append(block(heading, area, paragraphs))
    return item(title, area, "setting", [], sections)


def aprimoramento(title: str, cost: list[str], description: list[str], polarity: str) -> dict:
    return item(
        title,
        "aprimoramentos",
        "aprimoramento",
        description,
        [
            block("Custo", "aprimoramentos", cost),
            block("Descrição", "aprimoramentos", description),
        ],
        polarity=polarity,
    )


APRIMORAMENTO_HEADINGS = [
    ("Afinidade com Almas", ["Afinidade com Almas"], "positivo"),
    ("Afinidade com Fadas", ["Afinidade com Fadas"], "positivo"),
    ("Alma Pura", ["Alma Pura"], "positivo"),
    ("Amigo Espírito", ["Amigo Espírito"], "positivo"),
    ("Anjo da Guarda", ["Anjo da Guarda"], "positivo"),
    ("Capaz de Enxergar Auras", ["Capaz de Enxergar Auras"], "positivo"),
    ("Conjuração", ["Conjuração"], "positivo"),
    ("Contatos e Aliados", ["Contatos e Aliados", "Contatos c Aliados"], "positivo"),
    ("Desalmado", ["Desalmado"], "positivo"),
    ("Empatia Sobrenatural", ["Empatia Sobrenatural"], "positivo"),
    ("Filho de Espectros", ["Filho de Espectros"], "positivo"),
    ("Poderes Espectrais ou Mediúnicos", ["Poderes Espectrais ou Mediúnicos"], "positivo"),
    ("Pontos Heróicos", ["Pontos Heróicos"], "positivo"),
    ("Pontos de Fé", ["Pontos de Fé"], "positivo"),
    ("Portal Natural", ["Portal Natural"], "positivo"),
    ("Sensitivo", ["Sensitivo"], "positivo"),
    ("Vampiro Psíquico", ["Vampiro Psíquico"], "positivo"),
    ("Viagem Astral", ["Viagem Astral"], "positivo"),
    ("Ysea", ["Ysea", "Ysca"], "positivo"),
    ("Alma Escravizada", ["Alma Escravizada"], "negativo"),
    ("Alma Vendida", ["Alma Vendida"], "negativo"),
    ("Alucinado", ["Alucinado"], "negativo"),
    ("Aura de Inquietude", ["Aura de Inquietude"], "negativo"),
    ("Sombras", ["Sombras"], "negativo"),
]


def find_heading(text: str, aliases: list[str]) -> re.Match[str] | None:
    matches = []
    for alias in aliases:
        match = re.search(rf"(?m)^\s*{re.escape(alias)}\s*$", text)
        if match:
            matches.append(match)
    return min(matches, key=lambda found: found.start()) if matches else None


def make_aprimoramentos() -> list[dict]:
    text = page_text([43, 44, 45, 46])
    positions = []
    for title, aliases, polarity in APRIMORAMENTO_HEADINGS:
        match = find_heading(text, aliases)
        if match:
            positions.append((match.start(), match.end(), title, polarity))
    positions.sort()
    results = []
    for index, (_, start_end, title, polarity) in enumerate(positions):
        next_start = positions[index + 1][0] if index + 1 < len(positions) else len(text)
        paragraphs = clean_block(text[start_end:next_start])
        costs = [p for p in paragraphs if re.match(r"^-?\d[\d\s/-]*(?:Ponto|ponto)", p)]
        if not costs:
            costs = [p for p in paragraphs if "ponto" in p.lower() and len(p) < 120]
        description = [p for p in paragraphs if p not in costs]
        # Multiple cost options keep their benefit text inside the cost block.
        if len(costs) == 1 and ":" in costs[0]:
            label, rest = costs[0].split(":", 1)
            costs = [normalize_text(label)]
            description = [normalize_text(rest)] + description
        results.append(aprimoramento(title, costs, description, polarity))
    return results


POWER_HEADINGS = [
    "Armas Espectrais",
    "Armaduras Espectrais",
    "Asas Espectrais",
    "Comunicação",
    "Cura",
    "Detectar mentiras",
    "Detectar Mudança de Forma",
    "Emoções",
    "Escrever",
    "Falar",
    "Grandes Jornadas",
    "Gremlinint",
    "Idéia Original",
    "Invisibilidade",
    "Intangibilidade",
    "Isolamento Astral",
    "Lembranças",
    "Linhas do Tempo",
    "Localizar Outros Espíritos",
    "Localizar Espíritos Encarnados",
    "Luzes",
    "Manipulação de Ectoplasma",
    "Materialização",
    "Modificar Outros Espíritos",
    "Modificar a Forma-Pensamento",
    "Mudança de Forma",
    "Olhar Morto",
    "Orientação",
    "Possessão",
    "Poderes Angelicais",
    "Poderes Demoníacos",
    "Poderes Vampíricos",
    "Prisão Etérca",
    "Quebrar a Barreira Infernal",
    "Saltos Etéreos",
    "Sentidos Aguçados",
    "Sintonia",
    "Vozes",
    "Criando Seus Próprios Poderes",
]


def make_powers() -> list[dict]:
    results = []
    for index, heading in enumerate(POWER_HEADINGS[:-1]):
        next_heading = POWER_HEADINGS[index + 1]
        title = normalize_text(heading).replace("Idéia", "Ideia").replace("Etérca", "Etérea")
        paragraphs = extract_between(range(53, 61), heading, next_heading)
        if not paragraphs:
            continue
        intro: list[str] = []
        level_sections: list[dict] = []
        current_title = ""
        current_lines: list[str] = []
        for paragraph in paragraphs:
            if paragraph.startswith("Nível "):
                if current_title:
                    level_sections.append(block(current_title, "poderes", current_lines))
                label = paragraph.split(":", 1)[0]
                current_title = label
                current_lines = [paragraph]
            elif current_title:
                current_lines.append(paragraph)
            else:
                intro.append(paragraph)
        if current_title:
            level_sections.append(block(current_title, "poderes", current_lines))
        sections = []
        if intro:
            sections.append(block("Descrição", "poderes", intro))
        sections.extend(level_sections)
        results.append(item(title, "poderes", "poder", intro, sections))
    return results


RITUAL_HEADINGS = [
    "Aríete Espectral",
    "Armadura Espectral",
    "Conversar com Espíritos",
    "Conversar com Mortos",
    "Espada Espiritual",
    "Espelho Secreto",
    "Iniciação",
    "Lembrete",
    "Mãos Espectrais",
    "Mapeador Astral",
    "Marca Pessoal",
    "Mesas Girantes",
    "Morte da Alma",
    "Olhar de Pedinte",
    "Olhar de Penitência",
    "Pânico",
    "Pesadelo",
    "Ressurreição em Outro Corpo",
    "Rompimento Sagrado",
    "Servos Mumificados",
]


def make_rituals() -> list[dict]:
    results = []
    for index, heading in enumerate(RITUAL_HEADINGS):
        next_heading = RITUAL_HEADINGS[index + 1] if index + 1 < len(RITUAL_HEADINGS) else "Regras e Testes"
        paragraphs = extract_between(range(61, 68), heading, next_heading)
        if not paragraphs:
            continue
        meta: list[str] = []
        desc: list[str] = []
        for paragraph in paragraphs:
            if re.match(r"^(Criar|Controlar|Entender|Componentes|Tempo de Formulação|Alcance|Alvo|Efeitos|Duração|Teste de Resistência)", paragraph):
                meta.append(paragraph)
            else:
                desc.append(paragraph)
        sections = []
        if meta:
            sections.append(block("Ficha do Ritual", "rituais", meta))
        if desc:
            sections.append(block("Descrição", "rituais", desc))
        results.append(item(heading, "rituais", "ritual", desc, sections))
    return results


def make_races() -> list[dict]:
    specs = [
        ("Espíritos", [25], "Fantasmas"),
        ("Fantasmas", [25, 26], "Aparição"),
        ("Aparição", [26, 27], "Espectros"),
        ("Espectros", [27], "Obsessores"),
        ("Obsessores", [27, 28], "Médiuns"),
        ("Médiuns", [28, 29, 30], "Ordem da Rosa e da Cruz"),
        ("Nephalins", [37, 38], "Habitantes"),
        ("Habitantes do Sonhar", [39, 40], "Loa"),
        ("Loa", [41, 42], "Viajante Espiritual"),
    ]
    results = []
    for title, pages, end in specs:
        start = "Obcessores" if title == "Obsessores" else title
        start = "Habitantes" if title == "Habitantes do Sonhar" else start
        if title == "Obsessores":
            source = page_text(pages)
            matches = list(re.finditer(r"(?m)^\s*Obcessores\s*$", source))
            if len(matches) > 1:
                end_match = re.search(r"(?m)^\s*Médiuns\s*$", source[matches[1].end() :])
                end_pos = matches[1].end() + end_match.start() if end_match else len(source)
                paragraphs = clean_block(source[matches[1].end() : end_pos])
            else:
                paragraphs = extract_between(pages, start, end)
        else:
            paragraphs = extract_between(pages, start, end)
        sections = []
        creation_start = next((i for i, p in enumerate(paragraphs) if p.lower().startswith("criação de personagem")), None)
        if creation_start is not None:
            sections.append(block("Descrição", "racas", paragraphs[:creation_start]))
            sections.append(block("Criação de Personagem", "racas", paragraphs[creation_start + 1 :]))
        else:
            sections.append(block("Descrição", "racas", paragraphs))
        results.append(item(title, "racas", "raca", paragraphs, sections))
    return results


def make_classes() -> list[dict]:
    rosa_text = extract_between([31, 32], "Rosa Cruz", "Estudiosos do Umbral")
    viajante_text = extract_between([41, 42], "Viajante Espiritual", None)
    classes = [
        ("Rosa Cruz", rosa_text),
        ("Vidente", extract_between([35, 36], "Videntes", "Siíbilas")),
        ("Sibila", extract_between([36], "Siíbilas", "Criação de Personagem")),
        ("Viajante Espiritual", viajante_text),
    ]
    results = []
    for title, paragraphs in classes:
        sections = []
        cost = [p for p in paragraphs if p.startswith("Custo:")]
        skill_cost = [p for p in paragraphs if p.startswith("Perícias:")]
        if cost:
            sections.append(block("Custo", "classes", cost))
        if skill_cost:
            sections.append(block("Custo de Perícia", "classes", skill_cost))
        rest = [p for p in paragraphs if p not in cost and p not in skill_cost]
        if rest:
            sections.append(block("Descrição", "classes", rest))
        results.append(item(title, "classes", "classe", rest, sections))
    return results


def make_settings() -> list[dict]:
    settings = [
        item("Cenarios/Lore - Spiritum", "cenarios_lore", "setting", [], [
            block("Introdução e Meta-Jogo", "cenarios_lore", paragraphs_from_pages([4], drop_headings=["Introdução"])),
            block("O Reino dos Mortos", "cenarios_lore", paragraphs_from_pages([13, 14, 15, 16], drop_headings=["O Reino dos Mortos"])),
            block("Ordem da Rosa e da Cruz", "cenarios_lore", extract_between([31, 32], "Ordem da Rosa e da Cruz", "Rosa Cruz")),
            block("Estudiosos do Umbral", "cenarios_lore", extract_between([33, 34], "Estudiosos do Umbral", "Videntes, Oráculos e Sibilas")),
            block("Spiritum e Plano Astral", "cenarios_lore", paragraphs_from_pages([79, 81, 82, 83, 84], drop_headings=["Spiritum", "Plano Astral"])),
            block("Umbral e Vales Espirituais", "cenarios_lore", paragraphs_from_pages([85, 86, 87], drop_headings=["Umbral", "Vales Espirituais"])),
            block("O Sonhar", "cenarios_lore", paragraphs_from_pages([89, 91, 92], drop_headings=["Sonhar"])),
            block("O Mercado de Almas", "cenarios_lore", paragraphs_from_pages([93, 95, 96], drop_headings=["O Mercado de Almas"])),
            block("Lanka", "cenarios_lore", paragraphs_from_pages([97, 98], drop_headings=["Lanka"])),
            block("Metrópolis", "cenarios_lore", paragraphs_from_pages([99, 101, 102], drop_headings=["Metrópolis"])),
            block("Inferno", "cenarios_lore", paragraphs_from_pages([103, 104], drop_headings=["Inferno"])),
            block("O Abismo", "cenarios_lore", paragraphs_from_pages([105, 106], drop_headings=["O Abismo"])),
            block("Inferno Oriental", "cenarios_lore", paragraphs_from_pages([107, 108], drop_headings=["Inferno Oriental"])),
            block("Arkanun", "cenarios_lore", paragraphs_from_pages([109], drop_headings=["Arkanun"])),
        ]),
    ]
    return settings


def make_core_rules() -> list[dict]:
    return [
        item("Regra base - Spiritum", "regras_base", "core_rule", [], [
            block("Conceitos Básicos", "regras_base", paragraphs_from_pages([5, 6], drop_headings=["Conceitos"])),
            block("Criação de Personagens", "regras_base", paragraphs_from_pages([17, 18, 19, 20, 21], drop_headings=["Criação de Personagens"])),
            block("Atributos", "regras_base", paragraphs_from_pages([23, 24], drop_headings=["Atributos"])),
            block("Perícias", "regras_base", paragraphs_from_pages([47, 48], drop_headings=["Perícias"])),
            block("Pontos Heróicos e Fé", "regras_base", paragraphs_from_pages([49, 51, 52], drop_headings=["Pontos Heróicos", "Pontos de Fé"])),
            block("Regras e Testes", "regras_base", paragraphs_from_pages([67, 68, 69, 70, 71], drop_headings=["Regras e Testes"])),
            block("Combate e Experiência", "regras_base", paragraphs_from_pages([72, 73, 74, 75, 76, 77, 78], drop_headings=["Combate", "Experiência"])),
        ])
    ]


def make_npcs() -> list[dict]:
    specs = [
        ("Senhor dos Prazeres", [96, 97], "O Imperador Chin"),
        ("Kali", [98], None),
        ("Pinhead", [102], "Ravena"),
        ("Ravena", [102], "Herr Giger"),
        ("Herr Giger", [102], None),
    ]
    results = []
    for title, pages, end in specs:
        paragraphs = extract_between(pages, title, end)
        if not paragraphs:
            continue
        results.append(item(title, "criaturas_npcs", "npc", paragraphs, [
            block("História", "criaturas_npcs", paragraphs)
        ]))
    return results


def make_items() -> list[dict]:
    specs = [
        ("Cordão de Prata", [82, 83], "Cidades Astrais"),
        ("Objetos em Spiritum", [84], None),
        ("Almas Forjadas", [95], None),
    ]
    results = []
    for title, pages, end in specs:
        start = "Objetos" if title == "Objetos em Spiritum" else title
        paragraphs = extract_between(pages, start, end)
        if paragraphs:
            results.append(item(title, "itens_equipamentos", "item", paragraphs, [
                block("Descrição", "itens_equipamentos", paragraphs)
            ]))
    return results


def build_payload() -> dict:
    sections: list[dict] = []
    sections.extend(make_core_rules())
    sections.extend(make_aprimoramentos())
    sections.extend(make_classes())
    sections.extend(make_races())
    sections.extend(make_powers())
    sections.extend(make_rituals())
    sections.extend(make_items())
    sections.extend(make_npcs())
    sections.extend(make_settings())

    return {
        "version": 1,
        "source": SOURCE,
        "title": TITLE,
        "sourceFile": SOURCE_FILE,
        "status": "pilot_review",
        "summary": "Tratamento piloto de Spiritum a partir da camada OCR TXT; páginas muito ruins foram evitadas ou consolidadas em blocos revisados.",
        "areas": sorted({section["area"] for section in sections}),
        "groups": [],
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "sections": sections,
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
