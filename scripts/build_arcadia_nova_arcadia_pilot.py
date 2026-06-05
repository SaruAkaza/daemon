from __future__ import annotations

import re
from datetime import datetime
from typing import Iterable

from docx import Document

from common import ROOT, slugify, write_json


SOURCE = "arcadia-nova-arcadia"
TITLE = "Arcádia - Nova Arcádia"
SOURCE_CANDIDATES = [
    ROOT / "Livros" / "word" / "Arcadia_Nova_Arcadia_OCR_alta_qualidade.docx",
    ROOT / "Livros" / "word" / "feito" / "Arcadia_Nova_Arcadia_OCR_alta_qualidade.docx",
]
SOURCE_PATH = next((path for path in SOURCE_CANDIDATES if path.exists()), SOURCE_CANDIDATES[0])
OUT_PATH = ROOT / "data" / "pilot" / f"{SOURCE}.json"
DOCS_OUT_PATH = ROOT / "docs" / "assets" / "data" / "pilot" / f"{SOURCE}.json"

DROP_EXACT = {
    TITLE,
    "Texto extraído por OCR / camada textual, com limpeza de quebras de linha e caracteres indevidos.",
    "rR | Be VO a ar AC) A",
    "A Id AN",
    'SC i Ny',
    'ny 3 Da, f " a, ~',
}

TEXT_FIXES = {
    "Historia de Nova Arcádia": "História de Nova Arcádia",
    "póprio": "próprio",
    "acol hia": "acolhia",
    "idéias": "ideias",
    "houveram diversos": "houve diversos",
    "Começou então diversas": "Começaram então diversas",
    "povosapo": "povo-sapo",
    "mulherespeixe": "mulheres-peixe",
    "homenspeixe": "homens-peixe",
    "Anao": "Anão",
    "Satiro": "Sátiro",
    "Grégia": "Grécia",
    "raríssimamente": "rarissimamente",
    "humanóides": "humanoides",
    "pêlos": "pelos",
    "Vôo": "Voo",
    "Construcao": "Construção",
    "Racas": "Raças",
    "Guia de Construção de Raças Arcadianas": "Guia de Construção de Raças Arcadianas",
    "SobrevivênciaPlanície": "Sobrevivência (Planície)",
    "CON- 4": "CON-4",
    "rgenerar-se": "regenerar-se",
    "d´água": "d'água",
    "Domini Ubis": "Domini Urbs",
    "Domini UBIS": "DOMINI URBS",
    "DOMINI UBIS": "DOMINI URBS",
    "podem possuir Comandos Complexos": "pode possuir Comandos Complexos",
    "corormpeu": "corrompeu",
    "idéia": "ideia",
    "Idéias": "Ideias",
    "Idéia": "Ideia",
    "seres seres": "seres",
    "no entretanto": "no entanto",
    "mutios": "muitos",
    "tornandose": "tornando-se",
    "1, 30m": "1,30m",
    "1, 50": "1,50m",
    "Sobrevivência (Planície))": "Sobrevivência (Planície)",
}


def normalize_text(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = text.replace("“", '"').replace("”", '"')
    text = text.replace("–", "-").replace("—", "-")
    for old, new in TEXT_FIXES.items():
        text = text.replace(old, new)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = text.replace(" 1, 5m", " 1,5m")
    return text


def raw_paragraphs() -> list[str]:
    return [paragraph.text for paragraph in Document(SOURCE_PATH).paragraphs if paragraph.text.strip()]


def is_page_noise(text: str) -> bool:
    return bool(re.fullmatch(r"Página \d+", text, flags=re.IGNORECASE))


def should_join(previous: str, current: str) -> bool:
    if not previous or not current:
        return False
    if current.startswith(("Custo:", "Modificadores", "Vantagens", "Aparência:", "DESVANTAGENS", "VANTAGENS")):
        return False
    if previous.endswith((",", ":", "-", "/", "\\")):
        return True
    if current[:1].islower() and not previous.endswith((".", "!", "?", ":", ";", ")")):
        return True
    last_word = previous.split()[-1].lower().strip(".,;:!?")
    if last_word in {"de", "do", "da", "dos", "das", "em", "por", "com", "para", "que", "o", "os", "as", "um", "uma", "no", "na", "e", "ou", "se", "ao", "à", "com", "grécia", "nova", "elfos", "esse", "chamado"}:
        return True
    return False


def clean(values: Iterable[str]) -> list[str]:
    paragraphs: list[str] = []
    for raw in values:
        text = normalize_text(raw)
        if not text or text in DROP_EXACT or is_page_noise(text):
            continue
        if paragraphs and should_join(paragraphs[-1], text):
            paragraphs[-1] = normalize_text(f"{paragraphs[-1]} {text}")
        else:
            paragraphs.append(text)
    return paragraphs


def section(section_id: str, title: str, area: str, paragraphs: list[str]) -> dict:
    return {"id": section_id, "title": title, "area": area, "paragraphs": paragraphs}


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


def collect(paragraphs: list[str], start: int, end: int) -> list[str]:
    return clean(paragraphs[start:end])


def parse_race(title: str, paragraphs: list[str]) -> dict:
    parts = clean(paragraphs)
    if parts and slugify(parts[0]) == slugify(title):
        parts = parts[1:]
    split_parts: list[str] = []
    for part in parts:
        if " Aparência:" in part:
            before, after = part.split(" Aparência:", 1)
            split_parts.append(before)
            split_parts.append(f"Aparência: {after}")
        else:
            split_parts.append(part)
    parts = split_parts

    description: list[str] = []
    appearance: list[str] = []
    cost: list[str] = []
    attributes: list[str] = []
    traits: list[str] = []
    mode = "description"

    for part in parts:
        lower = part.lower()
        if lower.startswith("custo:"):
            mode = "cost"
            cost = [normalize_text(part.split(":", 1)[1])]
            continue
        if lower.startswith("modificadores"):
            mode = "attributes"
            value = part.split(":", 1)[1].strip() if ":" in part else ""
            if value:
                attributes.append(value)
            continue
        if lower.startswith("vantagens"):
            mode = "traits"
            value = part.split(":", 1)[1].strip() if ":" in part else ""
            if value:
                traits.append(value)
            continue
        if lower.startswith("aparência:"):
            mode = "appearance"
            value = part.split(":", 1)[1].strip()
            if value:
                appearance.append(value)
            continue

        if mode == "cost":
            description.append(part)
        elif mode == "attributes":
            attributes.append(part)
        elif mode == "traits":
            traits.append(part)
        elif mode == "appearance":
            appearance.append(part)
        else:
            description.append(part)

    attributes_text = normalize_text(" ".join(attributes))
    traits_text = normalize_text(" ".join(traits))

    sections: list[dict] = []
    if cost:
        sections.append(section("custo", "Custo", "racas", cost))
    sections.append(section("descricao", "Descrição", "racas", description))
    if appearance:
        sections.append(section("aparencia", "Aparência", "racas", appearance))
    if attributes_text:
        sections.append(section("modificadores-de-atributos", "Modificadores de Atributos", "racas", [attributes_text]))
    if traits_text:
        sections.append(section("vantagens-e-desvantagens", "Vantagens e Desvantagens", "racas", [traits_text]))

    return typed_item(title, "racas", "race", "Raça/Linhagem", [p for block in sections for p in block["paragraphs"]], sections)


def racial_enhancement(line: str, polarity: str) -> dict:
    match = re.match(r"^(.+?)\s*\(([^)]+)\):\s*(.+)$", line)
    if not match:
        title = line.split(":", 1)[0]
        cost = []
        description = [line]
    else:
        title = normalize_text(match.group(1))
        cost = [normalize_text(match.group(2))]
        description = [normalize_text(match.group(3))]
    sections = []
    if cost:
        sections.append(section("custo", "Custo", "aprimoramentos", cost))
    prerequisite = "Aprimoramento racial; usado na construção de raças arcadianas."
    sections.append(section("pre-requisito", "Pré-requisito", "aprimoramentos", [prerequisite]))
    sections.append(section("descricao", "Descrição", "aprimoramentos", description))
    item = typed_item(
        title,
        "aprimoramentos",
        "racial_enhancement",
        "Aprimoramento Racial",
        [paragraph for block in sections for paragraph in block["paragraphs"]],
        sections,
    )
    item["metadata"] = {"tipo": "aprimoramento-racial", "polaridade": "positivo" if polarity == "positive" else "negativo"}
    return item


def build_rule_items(paragraphs: list[str]) -> tuple[dict, list[dict]]:
    intro = collect(paragraphs, 216, 224)
    advantages_raw = collect(paragraphs, 225, 285)
    disadvantages_raw = collect(paragraphs, 286, 293)

    merged_advantages: list[str] = []
    for line in advantages_raw:
        if re.match(r"^\d+\s+pontos?:", line, flags=re.IGNORECASE) and merged_advantages:
            merged_advantages[-1] = normalize_text(f"{merged_advantages[-1]} {line}")
        elif (
            line in {"PRATA,", "DEMÔNIOS:", "A DIVINA", "DIVINA", "COMÉDIA,", "COMÉDIA, VAMPIROS", "VAMPIROS", "MITOLÓGICOS,", "MITOLÓGICOS, JYHAD: GUERRA", "JYHAD:", "GUERRA", "SANTA,", "SANTA, SPIRITUM: REINO", "SPIRITUM:", "REINO", "DOS MORTOS, VIKINGS, DOMINI URBS,", "LOBISOMEM:", "A MALDIÇÃO,"}
            or line.startswith("MALDIÇÃO, DAIPHIR:")
            or line.startswith("DOS MORTOS, VIKINGS")
            or line.startswith("LOBISOMEM:")
        ) and merged_advantages:
            merged_advantages[-1] = normalize_text(f"{merged_advantages[-1]} {line}")
        else:
            merged_advantages.append(line)

    rule = typed_item(
        "Regra base - Arcádia - Nova Arcádia",
        "regras_base",
        "ruleset",
        "Regra Base",
        intro,
        [
            section("introducao", "Introdução", "regras_base", intro[:2]),
            section("custo-racial", "Custo Racial", "regras_base", intro[2:4]),
            section("vantagens-e-desvantagens-raciais", "Vantagens e Desvantagens Raciais", "regras_base", intro[4:]),
        ],
    )
    traits = [racial_enhancement(line, "positive") for line in merged_advantages if "(" in line and ":" in line]
    traits.extend(racial_enhancement(line, "negative") for line in disadvantages_raw if "(" in line and ":" in line)
    deduped_traits: dict[str, dict] = {}
    for trait in traits:
        key = trait["id"]
        if key in deduped_traits:
            existing_desc = next(section for section in deduped_traits[key]["sections"] if section["id"] == "descricao")
            new_desc = next(section for section in trait["sections"] if section["id"] == "descricao")
            existing_desc["paragraphs"].extend(new_desc["paragraphs"])
            deduped_traits[key]["paragraphs"].extend(new_desc["paragraphs"])
            continue
        deduped_traits[key] = trait
    traits = list(deduped_traits.values())
    return rule, traits


def build_payload() -> dict:
    paragraphs = raw_paragraphs()

    lore_sections = [
        section("historia-de-nova-arcadia", "História de Nova Arcádia", "cenarios_lore", collect(paragraphs, 15, 33)),
        section("azania", "Azania", "cenarios_lore", collect(paragraphs, 36, 49)),
        section("leonira", "Leonira", "cenarios_lore", collect(paragraphs, 50, 62)),
    ]
    lore_items = [
        typed_item(
            "Arcádia - Nova Arcádia",
            "cenarios_lore",
            "setting",
            "Cenário/Lore",
            [paragraph for block in lore_sections for paragraph in block["paragraphs"]],
            lore_sections,
        )
    ]

    races = [
        parse_race("Humano", paragraphs[64:69]),
        parse_race("Anão", paragraphs[69:88]),
        parse_race("Goblin", paragraphs[88:112]),
        parse_race("Sátiro", paragraphs[112:130]),
        parse_race("Pixie", paragraphs[130:158]),
        parse_race("Centauro", paragraphs[158:173]),
        parse_race("Elfo Negro", paragraphs[173:186]),
        parse_race("Elfo", paragraphs[186:203]),
        parse_race("Gnomo", paragraphs[203:215]),
    ]

    rule, traits = build_rule_items(paragraphs)
    sections = [*lore_items, *races, rule, *traits]

    return {
        "version": 1,
        "source": SOURCE,
        "title": TITLE,
        "sourceFile": SOURCE_PATH.name,
        "status": "pilot_review",
        "summary": "Lore de Nova Arcádia, raças jogáveis, regra de construção racial e aprimoramentos raciais.",
        "areas": ["cenarios_lore", "racas", "regras_base", "aprimoramentos"],
        "groups": [],
        "sections": sections,
        "counts": {
            "cenarios_lore": len(lore_items),
            "racas": len(races),
            "regras_base": 1,
            "aprimoramentos": len(traits),
            "itens": len(sections),
        },
        "reviewNotes": [
            "Quebras de página e fragmentos de OCR foram removidos antes da catalogação.",
            "O epílogo da última página foi descartado por estar com OCR severamente corrompido e não compor dados de jogo.",
            "Custos raciais foram mantidos nos blocos de cada raça.",
        ],
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
    }


def main() -> None:
    payload = build_payload()
    write_json(OUT_PATH, payload)
    write_json(DOCS_OUT_PATH, payload)
    print(f"Wrote {OUT_PATH}")
    print(f"Wrote {DOCS_OUT_PATH}")
    print(f"Sections: {len(payload['sections'])}; counts: {payload['counts']}")


if __name__ == "__main__":
    main()
