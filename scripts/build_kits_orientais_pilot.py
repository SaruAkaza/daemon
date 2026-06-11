from __future__ import annotations

import re
import shutil
from datetime import datetime
from typing import Iterable

from docx import Document

from common import ROOT, slugify, write_json


SOURCE = "kits-orientais"
TITLE = "Kits Orientais"
SOURCE_FILE = "Kits Orientais.docx"
SOURCE_CANDIDATES = [
    ROOT / "Livros" / "word" / SOURCE_FILE,
    ROOT / "Livros" / "word" / "feito" / SOURCE_FILE,
]
SOURCE_PATH = next(path for path in SOURCE_CANDIDATES if path.exists())
OUT_PATH = ROOT / "data" / "pilot" / f"{SOURCE}.json"
DOCS_OUT_PATH = ROOT / "docs" / "assets" / "data" / "pilot" / f"{SOURCE}.json"


TEXT_FIXES = {
    "Espadachin": "Espadachim",
    "Espachin": "Espadachim",
    "Moge Shaolin": "Monge Shaolin",
    "Perícas": "Perícias",
    "prescisar": "precisar",
    "prescisa": "precisa",
    "exedente": "excedente",
    "contitução": "constituição",
    "Persongem": "Personagem",
    "persongem": "personagem",
    "desfeir": "desferir",
    "conciderados": "considerados",
    "concegue": "consegue",
    "enêrgias": "energias",
    "acada": "a cada",
    "d'agua": "d'água",
    "d’agua": "d’água",
    "faze-lo": "fazê-lo",
    "vôo": "voo",
    "Vôo": "Voo",
    "seqüência": "sequência",
    "místico": "místico",
    "magico": "mágico",
    "Magico": "Mágico",
    "marcias": "marciais",
    "Aroupa": "A roupa",
    "Armeiro": "Armeiro",
    "Heroicos": "Heróicos",
    "heroicos": "heróicos",
    "Heroico": "Heróico",
    "heroico": "heróico",
}


KIT_SPECS = [
    ("Samurai", 0, 4, 25),
    ("Espadachim", 25, 28, 38),
    ("Mestre de Iaijutsu", 38, 41, 56),
    ("Ninja", 56, 59, 64),
    ("Shinobi", 56, 64, 69),
    ("Ninja Regra antiga", 56, 69, 81),
    ("Mestre Maho-Jutsu", 81, 85, 90),
    ("Mandarin", 90, 94, 99),
    ("Monge", 101, 107, 114),
    ("Monge Shaolin", 187, 188, 195),
    ("Artista Marcial Treinado", 239, 240, 251),
]

STYLE_RANGES = [
    ("Tigre", 205, 211),
    ("Falcão", 211, 218),
    ("Macaco", 218, 225),
    ("Louva a Deus", 225, 233),
    ("Gato (Hê Ko Ashi Daichi)", 233, 239),
]

ENHANCEMENT_RANGES = [
    ("Ataques Múltiplos", 252, 263),
    ("Defesas Múltiplas", 263, 274),
    ("Deslocamento em Velocidade", 274, 275),
    ("Deslocamento em Velocidade Aprimorado", 275, 276),
    ("Disparo de Energia", 276, 282),
    ("Arremesso em Combate", 282, 283),
    ("Atropelar", 283, 284),
    ("Contra Ataque", 284, 285),
    ("Contra Ataque Aprimorado", 285, 286),
    ("Iniciativa", 286, 287),
    ("Mente Repartilhada", 287, 288),
    ("Foco em Caminho", 288, 290),
    ("Maestria em Caminho", 290, 294),
    ("Supremacia em Caminho", 294, 298),
    ("Saque Rápido", 298, 299),
    ("Sentido de Perigo", 299, 300),
    ("Pontos de Treinamento (Técnica)", 300, 314),
]

CHI_POWER_RANGES = [
    ("Arma Corporal", "Ying", 379, 381),
    ("Armadura Corporal", "Ying", 381, 383),
    ("Ataques Extras", "Ying", 383, 385),
    ("Aumento de Atributos Físicos", "Ying", 385, 387),
    ("Defesas Extras", "Ying", 387, 389),
    ("Garras", "Ying", 389, 391),
    ("Regeneração", "Ying", 391, 393),
    ("Salto", "Ying", 393, 395),
    ("Absorver Chi", "Yang", 396, 398),
    ("Armas de Chi", "Yang", 398, 400),
    ("Aumento de Atributo Mental", "Yang", 400, 402),
    ("Aura de Energia", "Yang", 402, 404),
    ("Cura", "Yang", 404, 406),
    ("Dano Místico", "Yang", 406, 408),
    ("Tiro de Chi", "Yang", 408, 410),
    ("Voo", "Yang", 410, 411),
]

STOP_TITLES = {
    "Técnicas:",
    "Jutsus:",
    "Justsus:",
    "Ninjutsus básicos",
    "Outros ninjutsus",
    "Genjutsus",
    "Juin Jutsu",
    "Doujutsu",
    "Katon",
    "Suiton",
    "Doton",
    "Fuuton",
    "Mokuton",
    "Tecnica dos insetos",
    "Ver artigo principal em",
    "Marionetes do Anime Naruto",
}

TECHNIQUE_AREA = "manobras_combate"


def normalize_text(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = text.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    text = text.replace("–", "-").replace("—", "-").replace("•", "•")
    text = re.sub(r"\[editar\]\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"(?<=\w)-\s*\n\s*(?=[a-záéíóúâêôãõç])", "", text)
    text = re.sub(r"(?<=\w)-\s+(?=[a-záéíóúâêôãõç])", "", text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s+", "\n", text)
    text = text.strip()
    for old, new in TEXT_FIXES.items():
        text = text.replace(old, new)
    text = re.sub(r"\b1\s*pts?\b", "1 ponto", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(\d+)\s*pts?\b", r"\1 pontos", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(\d+)\s*-\s*(\d+)\s*pts?\b", r"\1-\2 pontos", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(\d+)\s*pontos?\b", lambda m: f"{m.group(1)} ponto" if m.group(1) == "1" else f"{m.group(1)} pontos", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"\(\s+", "(", text)
    text = re.sub(r"\s+\)", ")", text)
    return text


def paragraph_texts() -> list[str]:
    doc = Document(SOURCE_PATH)
    return [normalize_text(paragraph.text) for paragraph in doc.paragraphs if normalize_text(paragraph.text)]


def join_paragraphs(items: Iterable[str]) -> list[str]:
    output: list[str] = []
    for item in items:
        item = normalize_text(item)
        if not item:
            continue
        if output and should_join(output[-1], item):
            output[-1] = normalize_text(output[-1] + " " + item)
        else:
            output.append(item)
    return output


def should_join(previous: str, current: str) -> bool:
    if not previous or not current:
        return False
    if re.match(r"^(Nível|Rank|Quem usa|Descrição|Nota|Selos|Primeira aparição|Restrição|Bônus|Penalidades|Perícias|Aprimoramentos|Custo)", current, re.IGNORECASE):
        return False
    if re.match(r"^\d+\s+pontos?\s*:", current, re.IGNORECASE):
        return False
    if previous.endswith((".", "!", "?", ":", ";", '"')):
        return False
    if current[:1].islower():
        return True
    if previous.split()[-1].lower().strip(".,;:!?") in {"de", "do", "da", "dos", "das", "em", "por", "para", "com", "que", "e"}:
        return True
    return False


def block(block_id: str, title: str, area: str, paragraphs: list[str]) -> dict:
    return {
        "id": slugify(block_id),
        "title": title,
        "area": area,
        "paragraphs": join_paragraphs(paragraphs),
    }


def item(area: str, kind: str, title: str, paragraphs: list[str], subsections: list[dict]) -> dict:
    return {
        "id": f"{area}-{slugify(title)}",
        "title": title,
        "area": area,
        "kind": kind,
        "sectionId": slugify(title),
        "sectionTitle": title,
        "paragraphs": join_paragraphs(paragraphs),
        "sections": subsections,
    }


def split_cost(text: str) -> tuple[list[str], list[str]]:
    text = re.sub(r"^Custos?:\s*", "", normalize_text(text), flags=re.IGNORECASE)
    parts = [part.strip(" .") for part in re.split(r",\s*", text) if part.strip(" .")]
    cost: list[str] = []
    skill: list[str] = []
    for part in parts:
        if re.search(r"per[íi]cias?", part, re.IGNORECASE):
            skill.append(part)
        else:
            cost.append(part)
    return cost, skill


def parse_labelled(lines: list[str], area: str, prefix: str) -> list[dict]:
    buckets: dict[str, list[str]] = {}
    order: list[str] = []
    current = "Descrição"
    for line in lines:
        if line.startswith("*"):
            current = "Características"
            if current not in buckets:
                buckets[current] = []
                order.append(current)
            buckets[current].append(line.lstrip("*").strip())
            continue
        if re.match(r"^Pontos de (Chi|T[ée]cnicas|Her[óo]icos)(?:\s+Iniciais)?\s*:", line, re.IGNORECASE):
            current = "Progressão"
            if current not in buckets:
                buckets[current] = []
                order.append(current)
            buckets[current].append(line)
            continue
        match = re.match(r"^(Restrições|Restrição|Perícias|Aprimoramentos|Bônus|Penalidades|Descrição|Pontos de Técnica)\s*:\s*(.*)", line, re.IGNORECASE)
        if match:
            current = {
                "restrição": "Restrições",
                "restrições": "Restrições",
                "perícias": "Perícias",
                "aprimoramentos": "Aprimoramentos",
                "bônus": "Bônus",
                "penalidades": "Penalidades",
                "descrição": "Descrição",
                "pontos de técnica": "Custo",
            }[match.group(1).lower()]
            if current not in buckets:
                buckets[current] = []
                order.append(current)
            if match.group(2).strip():
                buckets[current].append(match.group(2).strip())
        else:
            if current not in buckets:
                buckets[current] = []
                order.append(current)
            buckets[current].append(line)
    return [block(f"{prefix}-{name}", name, area, values) for name in order if (values := buckets.get(name))]


def build_kits(texts: list[str]) -> list[dict]:
    sections: list[dict] = []
    for title, desc_start, kit_index, end in KIT_SPECS:
        description_end = kit_index
        if title in {"Shinobi", "Ninja Regra antiga"}:
            description_end = 59
        description = [line for line in texts[desc_start:description_end] if line not in {title, "Ninjas", "Informações de jogo", "Informação de jogo"}]
        cost: list[str] = []
        skill_cost: list[str] = []
        rest: list[str] = []
        for line in texts[kit_index + 1:end]:
            if re.match(r"^Custos?:", line, re.IGNORECASE):
                cost, skill_cost = split_cost(line)
            else:
                rest.append(line)
        subsections = []
        if cost:
            subsections.append(block(f"{title}-custo", "Custo", "kits", cost))
        if skill_cost:
            subsections.append(block(f"{title}-custo-pericia", "Custo de Perícia", "kits", skill_cost))
        subsections.extend(parse_labelled(rest, "kits", title))
        if description:
            subsections.insert(0, block(f"{title}-descricao", "Descrição", "kits", description))
        sections.append(item("kits", "kit", title, description + rest, subsections))
    return sections


def build_styles(texts: list[str]) -> list[dict]:
    sections: list[dict] = [
        item(
            "regras_base",
            "core_rule",
            "Regra base - Kits Orientais",
            [],
            [
                block("kits-orientais-estilos-de-luta", "Estilos de Luta", "regras_base", texts[195:204]),
                block("kits-orientais-tecnicas", "Técnicas", "regras_base", texts[412:427]),
            ],
        )
    ]
    for title, start, end in STYLE_RANGES:
        body = [re.sub(r"^NOME\s*:\s*", "", line, flags=re.IGNORECASE) for line in texts[start:end]]
        body = [line for line in body if line.upper() != title.upper()]
        sections.append(item("manobras_combate", "maneuver", title, body, parse_labelled(body, "manobras_combate", title)))
    return sections


def split_enhancement_title(title: str, lines: list[str]) -> tuple[list[str], list[str]]:
    if not lines:
        return [], []
    first = lines[0]
    pattern = rf"^{re.escape(title)}\s+((?:\d+\s*-\s*\d+|\d+)\s*(?:pts?|pontos?)(?:\s*cada)?)\s*(.*)$"
    match = re.match(pattern, first, re.IGNORECASE)
    if match:
        return [normalize_text(match.group(1))], [match.group(2)] + lines[1:]
    if first.lower().startswith(title.lower()):
        return [], [normalize_text(first[len(title):])] + lines[1:]
    return [], lines


def build_enhancements(texts: list[str]) -> list[dict]:
    sections: list[dict] = []
    for title, start, end in ENHANCEMENT_RANGES:
        raw = texts[start:end]
        inline_cost, lines = split_enhancement_title(title, raw)
        description: list[str] = []
        restrictions: list[str] = []
        costs: list[str] = inline_cost[:]
        current_cost = ""
        for line in lines:
            restriction_match = re.match(r"^Restriç(?:ão|ões)\s*:\s*(.*)", line, re.IGNORECASE)
            cost_match = re.match(r"^((?:\d+\s*-\s*\d+|\d+)\s*(?:pts?|pontos?)(?:\s*cada)?)\s*:?\s*(.*)", line, re.IGNORECASE)
            if restriction_match:
                if current_cost:
                    costs.append(normalize_text(current_cost))
                    current_cost = ""
                restrictions.append(restriction_match.group(1).strip())
                continue
            if cost_match:
                if current_cost:
                    costs.append(normalize_text(current_cost))
                if ":" not in line:
                    costs.append(normalize_text(cost_match.group(1)))
                    if cost_match.group(2).strip():
                        description.append(cost_match.group(2).strip())
                    current_cost = ""
                else:
                    current_cost = normalize_text(f"{cost_match.group(1)}: {cost_match.group(2)}")
            elif current_cost and not re.match(r"^(Restrição|Descrição)\s*:", line, re.IGNORECASE):
                current_cost = normalize_text(current_cost + " " + line)
            else:
                description.append(line)
        if current_cost:
            costs.append(normalize_text(current_cost))
        subsections = []
        if costs:
            subsections.append(block(f"{title}-custo", "Custo", "aprimoramentos", costs))
        if restrictions:
            subsections.append(block(f"{title}-pre-requisitos", "Pré-requisitos", "aprimoramentos", restrictions))
        if description:
            subsections.append(block(f"{title}-descricao", "Descrição", "aprimoramentos", description))
        sections.append(item("aprimoramentos", "enhancement", title, description + costs, subsections))
    return sections


def build_chi(texts: list[str]) -> list[dict]:
    rule = item(
        "regras_base",
        "core_rule",
        "Regra base - Kits Orientais - Chi",
        [],
        [
            block("chi-introducao", "Introdução", "regras_base", texts[333:341]),
            block("chi-custos", "Custo", "regras_base", texts[341:349]),
            block("chi-foco", "Foco", "regras_base", texts[349:353]),
            block("chi-ying-yang", "Regra do Chi Ying/Yang", "regras_base", texts[353:361]),
            block("chi-ying", "Chi Ying", "regras_base", texts[361:365]),
            block("chi-yang", "Chi Yang", "regras_base", texts[365:369]),
            block("chi-demoniaco", "Chi Demoníaco", "regras_base", texts[369:377]),
        ],
    )
    powers = []
    for title, family, start, end in CHI_POWER_RANGES:
        powers.append(
            item(
                "poderes",
                "power",
                f"{title} ({family})",
                texts[start:end],
                [
                    block(f"{title}-{family}-familia", "Família", "poderes", [family]),
                    block(f"{title}-{family}-descricao", "Descrição", "poderes", texts[start + 1:end]),
                ],
            )
        )
    return [rule, *powers]


def candidate_title(text: str, next_text: str = "") -> bool:
    first = text.splitlines()[0].strip()
    if not first or first in STOP_TITLES:
        return False
    if first.startswith("("):
        return False
    if first.lower().startswith(("rank:", "quem usa", "usuários:", "descrição:", "nota:", "selos:", "primeira", "aparição:")):
        return False
    if len(first) > 120:
        return False
    if re.search(r"\b(Custo|Perícias|Aprimoramentos|Restrições)\b", first, re.IGNORECASE):
        return False
    if "\nRank:" in text or "\nQuem usa" in text or "\nDescrição:" in text:
        return True
    if next_text.startswith(("Rank:", "Quem usa", "Quem Usa", "Usuários:", "Descrição:", "(")):
        return True
    if re.match(r"^(Nível|Rank)\s+\d+", next_text, re.IGNORECASE):
        return True
    return False


def technique_availability(title: str, subsections: list[dict]) -> list[str]:
    labels = {section["title"]: section for section in subsections}
    users = labels.get("Quem usa") or labels.get("Usuários")
    rank = labels.get("Rank")
    title_text = slugify(title).replace("-", " ")
    if "cla" in title_text.split():
        return [
            "Agrupador ou especialidade de clã: usar como contexto/restrição das técnicas vinculadas, não como poder universal."
        ]
    user_text = " ".join(users.get("paragraphs", [])) if users else ""
    if users:
        if normalize_text(user_text).lower() in {"técnica ninja básica", "tecnica ninja basica"}:
            return ["Técnica básica: o texto indica uso geral por praticantes ninja, sem clã ou personagem exclusivo neste trecho."]
        return [
            "Restrita/contextual: o texto informa usuários conhecidos, clãs ou personagens associados. Não tratar como poder universal sem aprovação do Mestre.",
            f"Usuários conhecidos: {user_text}",
        ]
    if rank:
        if any(word in title_text for word in ["konoha", "suna", "ho ", "mokuton", "raiton", "suiton", "doton", "fuuton", "katon", "hyuuga", "uchiha"]):
            return ["Técnica contextual: possui rank e tema/clã/escola específico; confirmar pré-requisitos na mesa antes de liberar para personagens."]
        return ["Técnica aprendível: o texto apresenta rank, mas não informa usuário ou clã exclusivo neste trecho."]
    return ["Técnica ou especialidade sem restrição explícita no trecho catalogado."]


def parse_technique_body(body: list[str], title: str) -> list[dict]:
    buckets: dict[str, list[str]] = {}
    order: list[str] = []
    current = "Descrição"
    for paragraph in body:
        lines = [line.strip() for line in paragraph.splitlines() if line.strip()]
        for line in lines:
            label_match = re.match(r"^(Quem usa|Quem Usa|Usuários|Rank|Nota\d*|Nota|Selos|Primeira [Aa]parição|Aparição|Aparência|Descrição)\s*:?\s*(.*)", line)
            if label_match:
                raw_label = label_match.group(1).lower()
                label = {
                    "quem usa": "Quem usa",
                    "usuários": "Usuários",
                    "rank": "Rank",
                    "nota": "Nota",
                    "nota²": "Nota",
                    "nota2": "Nota",
                    "selos": "Selos",
                    "primeira aparição": "Primeira Aparição",
                    "aparição": "Primeira Aparição",
                    "aparência": "Aparência",
                    "descrição": "Descrição",
                }.get(raw_label, "Nota")
                current = label
                if label not in buckets:
                    buckets[label] = []
                    order.append(label)
                value = label_match.group(2).strip()
                if label == "Rank" and value:
                    rank_match = re.match(r"^([A-Z?/-]+)\.?\s*(.*)", value, re.IGNORECASE)
                    if rank_match:
                        buckets[label].append(rank_match.group(1).strip())
                        if rank_match.group(2).strip():
                            buckets.setdefault("Descrição", []).append(rank_match.group(2).strip())
                            if "Descrição" not in order:
                                order.append("Descrição")
                    else:
                        buckets[label].append(value)
                elif value:
                    buckets[label].append(value)
            elif line.startswith("(") and "Subtítulo" not in buckets:
                buckets.setdefault("Subtítulo", []).append(line)
                if "Subtítulo" not in order:
                    order.append("Subtítulo")
            else:
                buckets.setdefault(current, []).append(line)
                if current not in order:
                    order.append(current)
    return [block(f"{title}-{name}", name, TECHNIQUE_AREA, values) for name in order if (values := buckets.get(name))]


def build_techniques(texts: list[str]) -> list[dict]:
    sections: list[dict] = []
    start = 427
    current_title: str | None = None
    current_body: list[str] = []

    def flush() -> None:
        nonlocal current_title, current_body
        if not current_title or current_title in STOP_TITLES:
            current_title = None
            current_body = []
            return
        clean_title = normalize_text(current_title.splitlines()[0])
        if len(clean_title) < 3 or clean_title in STOP_TITLES:
            current_title = None
            current_body = []
            return
        subsections = parse_technique_body(current_body, clean_title)
        if not subsections:
            current_title = None
            current_body = []
            return
        subsections.insert(0, block(f"{clean_title}-disponibilidade", "Disponibilidade", TECHNIQUE_AREA, technique_availability(clean_title, subsections)))
        paragraphs = [p for section in subsections for p in section.get("paragraphs", [])]
        if paragraphs or current_body:
            sections.append(item(TECHNIQUE_AREA, "technique", clean_title, paragraphs or current_body, subsections))
        current_title = None
        current_body = []

    for index in range(start, len(texts)):
        text = texts[index]
        next_text = texts[index + 1] if index + 1 < len(texts) else ""
        if candidate_title(text, next_text):
            flush()
            lines = text.splitlines()
            current_title = lines[0].strip()
            current_body = ["\n".join(lines[1:]).strip()] if len(lines) > 1 and "\n".join(lines[1:]).strip() else []
        else:
            if text in STOP_TITLES:
                continue
            if current_title:
                current_body.append(text)
    flush()

    # Remove exact duplicates generated by duplicated source fragments.
    seen: set[str] = set()
    unique: list[dict] = []
    for section in sections:
        key = section["id"]
        if key in seen:
            continue
        seen.add(key)
        unique.append(section)
    return unique


def move_source_to_done() -> None:
    target = ROOT / "Livros" / "word" / "feito" / SOURCE_FILE
    if SOURCE_PATH == target:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(SOURCE_PATH), str(target))


def main() -> None:
    texts = paragraph_texts()
    sections: list[dict] = []
    sections.extend(build_kits(texts))
    sections.extend(build_styles(texts))
    sections.extend(build_enhancements(texts))
    sections.extend(build_chi(texts))
    sections.extend(build_techniques(texts))

    areas = sorted({section["area"] for section in sections})
    payload = {
        "version": 1,
        "source": SOURCE,
        "title": TITLE,
        "sourceFile": SOURCE_FILE,
        "status": "pilot_review",
        "summary": "Catálogo piloto de Kits Orientais com kits, regras de Chi, estilos de luta, aprimoramentos e técnicas orientais separados por entidade.",
        "areas": areas,
        "groups": [],
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "sections": sections,
    }
    write_json(OUT_PATH, payload)
    write_json(DOCS_OUT_PATH, payload)
    move_source_to_done()
    print(f"Wrote {OUT_PATH.relative_to(ROOT)}")
    print(f"Wrote {DOCS_OUT_PATH.relative_to(ROOT)}")
    print(f"Sections: {len(sections)}")


if __name__ == "__main__":
    main()
