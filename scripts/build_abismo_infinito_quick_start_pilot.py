from __future__ import annotations

import json
import re
import zipfile
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree

from common import ROOT, slugify, write_json


SOURCE_PATH = ROOT / "Livros" / "word" / "feito" / "Abismo-Infinito-Quick-Start.docx"
OUT_PATH = ROOT / "data" / "pilot" / "abismo-infinito-quick-start.json"
DOCS_OUT_PATH = ROOT / "docs" / "assets" / "data" / "pilot" / "abismo-infinito-quick-start.json"
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

SECTION_AREAS = {
    "que é um jogo narrativo?": "regras_base",
    "Sessões de jogo": "regras_base",
    "material para jogo": "regras_base",
    "os personagens": "regras_base",
    "o mestre do Espaço": "regras_base",
    "o abismo do universo": "cenarios_lore",
    "a era da viagem espacial": "cenarios_lore",
    "autoctônias": "cenarios_lore",
    "a Iniciativa Cronos": "cenarios_lore",
    "as hipérions": "cenarios_lore",
    "os Prometeus": "cenarios_lore",
    "os argos": "cenarios_lore",
    "a exploração intergaláctica": "cenarios_lore",
    "braços galácticos": "cenarios_lore",
    "a febre do espaço": "cenarios_lore",
    "astronautas Expedicionários": "regras_base",
    "as missões": "cenarios_lore",
    "hibernação": "regras_base",
    "Pesadelo lúcido": "regras_base",
    "as Regras do jogo": "regras_base",
    "Cenas": "regras_base",
    "Involução": "regras_base",
    "organizando cenas": "regras_base",
    "Resolvendo cenas": "regras_base",
    "Vantagens e desvantagens": "regras_base",
    "gênese do protagonista": "regras_base",
    "nomE:CaRgo:CITação:jogadoR:SonolênCIamEdo PaRTICUlaRfERImEnToSânCoRaSS. B. CortezJohnExobiólogo\"Um dia as pessoas vão entender queeu sou o maior cientísta desta década\"Medo de nunca maisrever minha mulher e omeu filhoAbraçar meu filho,beijar minha esposa,ouvir música.S. B. CortezJohnExobiólogo\"Um dia as pessoas vão entender queeu sou o maior cientísta desta década\"Medo de nunca maisrever minha mulher e omeu filhoAbraçar meu filho,beijar minha esposa,ouvir música.": "none",
    "Cargos": "classes",
    "Trauma e Estresse": "regras_base",
    "medo particular": "regras_base",
    "loucura do Espaço": "regras_base",
    "manifestando": "regras_base",
    "os próprios medos": "regras_base",
    "Surto de medo": "regras_base",
    "Sonolência": "regras_base",
    "Eterno despertar": "regras_base",
    "olvidamento": "regras_base",
    "Camadas de Sonhos": "regras_base",
    "Controle do sonho": "regras_base",
    "âncoras": "regras_base",
    "Perdendo âncoras": "regras_base",
    "ferimentos": "regras_base",
    "Infligir danos": "regras_base",
    "armas e equipamento de proteção": "itens_equipamentos",
    "males do Espaço": "regras_base",
    "manifestações dos medos": "regras_base",
    "narrando manifestações e ilusões": "regras_base",
    "a história": "aventuras",
    "fase 1: despertar": "aventuras",
    "fase 2: Pesadelo": "aventuras",
    "fase 3: Redenção": "aventuras",
}

CARGO_NAMES = {
    "astrogeólogo",
    "Cosmólogo",
    "Criptólogo",
    "Engenheiro",
    "Exobiólogo",
    "médico",
    "Psicólogo",
    "Segurança",
    "Videomaker",
    "navegador",
}

DROP_PATTERNS = [
    re.compile(r"^\d+$"),
    re.compile(r"^(?:john bogéa|QUICK STaRT|www\.|abISmo InfInITo)+", re.IGNORECASE),
    re.compile(r"^Este livro é inadequado", re.IGNORECASE),
]


def normalize_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = text.replace("QUICK STaRTQUICK STaRT", "")
    text = text.replace("abISmo InfInIToabISmo InfInITo", "")
    text = text.replace("VocêMesmo", "Você Mesmo")
    text = text.replace("premiadoem", "premiado em")
    text = text.replace("cientísta", "cientista")
    text = text.replace("haver com", "a ver com")
    text = text.replace("entando", "entanto")
    text = text.replace("dos nos", "dos nossos")
    text = text.replace("protagonista vai", "protagonista vai")
    text = re.sub(r"([a-záàâãéêíóôõúç])- ([a-záàâãéêíóôõúç])", r"\1\2", text)
    text = re.sub(r"([a-záàâãéêíóôõúç])-([a-záàâãéêíóôõúç])", r"\1\2", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return text.strip()


def expand_inline_markers(text: str) -> list[str]:
    replacements = {
        "as Regras do jogo": "\nas Regras do jogo\n",
        "Involução": "\nInvolução\n",
        "organizando cenas": "\norganizando cenas\n",
        "Resolvendo cenas": "\nResolvendo cenas\n",
        "Vantagens e desvantagens": "\nVantagens e desvantagens\n",
        "gênese do protagonista": "\ngênese do protagonista\n",
        "ExobiólogoDiversas": "\nExobiólogo\nDiversas",
        "médicoEspecialista": "\nmédico\nEspecialista",
        "navegadorTreinado": "\nnavegador\nTreinado",
    }
    expanded = text
    for source, target in replacements.items():
        expanded = expanded.replace(source, target)
    if expanded.startswith("Cenas "):
        expanded = expanded.replace("Cenas ", "Cenas\n", 1)
    parts = [normalize_text(part) for part in expanded.splitlines()]
    return [part for part in parts if part]


def docx_paragraphs(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as archive:
        root = ElementTree.fromstring(archive.read("word/document.xml"))

    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:body/w:p", NS):
        text = "".join(node.text or "" for node in paragraph.findall(".//w:t", NS)).strip()
        if not text:
            continue
        text = normalize_text(text)
        if not text or any(pattern.search(text) for pattern in DROP_PATTERNS):
            continue
        paragraphs.extend(expand_inline_markers(text))
    return join_fragments(paragraphs)


def join_fragments(paragraphs: list[str]) -> list[str]:
    joined: list[str] = []
    for paragraph in paragraphs:
        if not joined:
            joined.append(paragraph)
            continue
        if should_join(joined[-1], paragraph):
            joined[-1] = merge_fragments(joined[-1], paragraph)
        else:
            joined.append(paragraph)
    return joined


def merge_fragments(previous: str, current: str) -> str:
    if previous.endswith("-") and current.startswith("-") and current[1:2].islower():
        return normalize_text(f"{previous[:-1]}{current[1:]}")
    if previous.endswith("-") and current[:1].islower():
        return normalize_text(f"{previous[:-1]}{current}")
    if current.startswith("-") and previous and previous[-1].isalpha():
        return normalize_text(f"{previous}{current[1:]}")
    return normalize_text(f"{previous} {current}")


def should_join(previous: str, current: str) -> bool:
    if current in SECTION_AREAS or current in CARGO_NAMES:
        return False
    if previous in SECTION_AREAS or previous in CARGO_NAMES:
        return False
    if previous.endswith("-") and current.startswith("-") and current[1:2].islower():
        return True
    if previous.endswith("-") and current[:1].islower():
        return True
    if current.startswith("-") and previous and previous[-1].isalpha():
        return True
    if len(current) < 45 and current[:1].islower():
        return True
    if current[:1].islower() and not previous.endswith((".", "!", "?", ":", ";", "…")):
        return True
    if previous.endswith(("gran", "fa", "da", "Trau", "ex", "al", "perso")):
        return True
    return False


def find_sections(paragraphs: list[str]) -> list[dict]:
    sections = []
    current_heading = "Apresentação"
    current_area = "front_matter"
    current: list[str] = []

    def flush() -> None:
        nonlocal current
        if not current:
            return
        if current_area != "none":
            sections.append(
                {
                    "id": slugify(current_heading),
                    "title": pretty_title(current_heading),
                    "area": current_area,
                    "paragraphs": current,
                }
            )
        current = []

    for paragraph in paragraphs:
        if paragraph in SECTION_AREAS:
            flush()
            current_heading = paragraph
            current_area = SECTION_AREAS[paragraph]
            continue
        if paragraph in CARGO_NAMES:
            flush()
            current_heading = paragraph
            current_area = "classes"
            continue
        current.append(paragraph)
    flush()
    return postprocess_sections(sections)


def postprocess_sections(sections: list[dict]) -> list[dict]:
    clean_sections = []
    seen = set()
    for section in sections:
        paragraphs = [p for p in section["paragraphs"] if not is_noise_paragraph(p)]
        if not paragraphs:
            continue
        fingerprint = (section["title"], section["area"], "\n".join(paragraphs))
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        section["paragraphs"] = paragraphs
        clean_sections.append(section)
    return clean_sections


def is_noise_paragraph(paragraph: str) -> bool:
    if len(paragraph) <= 2:
        return True
    if re.fullmatch(r"-[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-Za-zÁÀÂÃÉÊÍÓÔÕÚÇáàâãéêíóôõúç]+", paragraph):
        return True
    if paragraph.startswith("nomE ") or paragraph.startswith("SonolênCIa"):
        return True
    return False


def pretty_title(title: str) -> str:
    overrides = {
        "que é um jogo narrativo?": "O que é um jogo narrativo?",
        "material para jogo": "Material para jogo",
        "os personagens": "Os personagens",
        "o mestre do Espaço": "O Mestre do Espaço",
        "o abismo do universo": "O abismo do universo",
        "a era da viagem espacial": "A era da viagem espacial",
        "autoctônias": "Autoctônias",
        "as hipérions": "As Hipérions",
        "os Prometeus": "Os Prometeus",
        "os argos": "Os Argos",
        "a exploração intergaláctica": "A exploração intergaláctica",
        "a febre do espaço": "A febre do espaço",
        "astronautas Expedicionários": "Astronautas Expedicionários",
        "as missões": "As missões",
        "medo particular": "Medo particular",
        "loucura do Espaço": "Loucura do Espaço",
        "manifestando": "Manifestando os próprios medos",
        "os próprios medos": "Manifestando os próprios medos",
        "olvidamento": "Olvidamento",
        "âncoras": "Âncoras",
        "ferimentos": "Ferimentos",
        "armas e equipamento de proteção": "Armas e equipamento de proteção",
        "males do Espaço": "Males do Espaço",
        "manifestações dos medos": "Manifestações dos medos",
        "narrando manifestações e ilusões": "Narrando manifestações e ilusões",
        "a história": "A história",
    }
    return overrides.get(title, title)


def build_pilot() -> dict:
    paragraphs = docx_paragraphs(SOURCE_PATH)
    sections = find_sections(paragraphs)
    adventure_titles = {"A história", "fase 1: despertar", "fase 2: Pesadelo", "fase 3: Redenção"}
    adventure_sections = [section for section in sections if section["area"] == "aventuras" and section["title"] in adventure_titles]
    grouped_areas = {
        "regras_base": {
            "id": "abismo-infinito-regras-base",
            "title": "Regra base - Abismo Infinito - Quick Start",
            "kind": "ruleset",
            "sectionTitle": "Regra Base",
        },
        "cenarios_lore": {
            "id": "abismo-infinito-cenario",
            "title": "Abismo Infinito",
            "kind": "setting",
            "sectionTitle": "Cenário",
        },
    }
    grouped_sections = {
        area: [section for section in sections if section["area"] == area]
        for area in grouped_areas
    }
    sections = [
        section
        for section in sections
        if section not in adventure_sections and section["area"] not in grouped_areas
    ]
    area_counts: dict[str, int] = {}
    for section in sections:
        area_counts[section["area"]] = area_counts.get(section["area"], 0) + 1
    groups = []
    for area, spec in grouped_areas.items():
        if not grouped_sections[area]:
            continue
        area_counts[area] = 1
        groups.append(
            {
                **spec,
                "area": area,
                "sections": grouped_sections[area],
            }
        )
    if adventure_sections:
        area_counts["aventuras"] = 1

    return {
        "version": 1,
        "status": "pilot_review",
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "source": "abismo-infinito-quick-start",
        "sourceFile": SOURCE_PATH.name,
        "sourcePath": str(SOURCE_PATH.relative_to(ROOT)),
        "title": "Abismo Infinito - Quick Start",
        "summary": "Quick start de horror espacial com regras introdutórias, cenário, cargos de astronauta e estrutura de aventura.",
        "areas": sorted(area_counts),
        "sections": sections,
        "groups": groups,
        "adventures": [
            {
                "id": "abismo-infinito",
                "title": "Abismo Infinito",
                "area": "aventuras",
                "sections": adventure_sections,
            }
        ] if adventure_sections else [],
        "areaCounts": area_counts,
        "reviewNotes": [
            "Piloto por seções explícitas do livro.",
            "Cargos foram tratados como classes/opções de função de personagem.",
            "As fases Despertar, Pesadelo e Redenção foram tratadas como estrutura de aventura.",
            "Ainda precisa de revisão humana antes de virar entidade final da base.",
        ],
    }


def main() -> None:
    payload = build_pilot()
    write_json(OUT_PATH, payload)
    write_json(DOCS_OUT_PATH, payload)
    print(json.dumps({"source": payload["source"], "sections": len(payload["sections"]), "areas": payload["areaCounts"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
