#!/usr/bin/env python3
"""
Build Anjos - Angélicos Sicários with individual equipment entities
"""

from pathlib import Path
import json
from datetime import datetime
from docx import Document
import re

from common import ROOT, slugify, write_json

SOURCE = "anjos-angelicos-sicarios"
TITLE = "Anjos - A Cidade de Prata - Angélicos Sicários"
SOURCE_PATH = ROOT / "Livros" / "word" / "Anjos - A Cidade de Prata - Angélicos Sicários.docx"
OUT_PATH = ROOT / "data" / "pilot" / f"{SOURCE}.json"
DOCS_OUT_PATH = ROOT / "docs" / "assets" / "data" / "pilot" / f"{SOURCE}.json"

def normalize_text(text: str) -> str:
    text = text.replace(" ", " ")
    text = text.replace("—", "-").replace("–", "-")
    text = text.replace(""", '"').replace(""", '"').replace("'", "'")
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return text

def extract_paragraphs() -> list[str]:
    doc = Document(SOURCE_PATH)
    paras = []
    for p in doc.paragraphs:
        text = normalize_text(p.text)
        if text and text != TITLE:
            paras.append(text)
    return paras

def build_pilot() -> dict:
    paras = extract_paragraphs()

    groups = []
    sections_list = []

    # 1. LORE & HISTÓRIA GROUP (9 subsections)
    lore_sections = []
    lore_subsections = {
        "Origem e Contexto": (0, 50),
        "Batalhas Patrísticas": (48, 70),
        "Império Romano": (70, 86),
        "Idade Média": (84, 99),
        "Cruzadas e Cismas": (99, 120),
        "Inquisição e Reforma": (120, 143),
        "Iniquidades": (142, 150),
        "Locais Estratégicos": (150, 175),
        "Limbo e Prisões": (200, 206),
    }

    for sec_title, (start, end) in lore_subsections.items():
        if end > len(paras):
            end = len(paras)
        content = [p for p in paras[start:end] if p.strip()]
        if content:
            lore_sections.append({
                "id": slugify(sec_title),
                "title": sec_title,
                "area": "cenarios_lore",
                "paragraphs": content
            })

    if lore_sections:
        groups.append({
            "id": "cenarios-lore-sicarios",
            "title": "Lore & História",
            "kind": "setting",
            "area": "cenarios_lore",
            "sectionTitle": "Cenário",
            "sections": lore_sections
        })

    # 2. PODERES GROUP
    power_content = [p for p in paras[152:166] if p.strip()]
    if power_content:
        groups.append({
            "id": "poderes-sicarios",
            "title": "Argúcias (Poderes)",
            "kind": "power",
            "area": "poderes",
            "sectionTitle": "Poder",
            "sections": [{
                "id": "poderes-dos-sicarios",
                "title": "Poderes dos Sicários",
                "area": "poderes",
                "paragraphs": power_content
            }]
        })

    # 3. APRIMORAMENTOS - TÉCNICAS DE COMBATE (individual manobras as entities)
    technique_entities = []
    technique_lines = {
        "Desarmar com Asa": (178, 178),
        "Ataque Rolante": (179, 179),
        "Finta": (179, 179),
        "Mata-Dragão": (179, 180),
        "Coração de Fafnir": (180, 180),
        "Calcanhar da Fera": (180, 180),
        "Asas Cortantes": (181, 181),
    }

    for tech_name, (start, end) in technique_lines.items():
        if end < len(paras):
            content = [p for p in paras[start:end+1] if p.strip() and tech_name in p]
            if content:
                technique_entities.append({
                    "id": slugify(tech_name),
                    "title": tech_name,
                    "area": "aprimoramentos",
                    "kind": "enhancement",
                    "paragraphs": content,
                    "sections": []
                })

    if technique_entities:
        groups.append({
            "id": "aprimoramentos-sicarios",
            "title": "Manobras de Combate",
            "kind": "enhancement",
            "area": "aprimoramentos",
            "sectionTitle": "Aprimoramento",
            "sections": technique_entities
        })

    # 4. ITENS EQUIPAMENTOS - Individual weapons/artifacts as entities
    weapon_defs = {
        "Yaldabaoth": (183, 186),
        "Nebro": (185, 186),
        "Saklas": (186, 186),
        "Harmathoth": (187, 188),
        "Galila": (189, 190),
        "Exarp": (191, 191),
        "Hcoma": (191, 193),
        "Manto do Sicário": (194, 195),
        "Angélica Sica": (196, 197),
        "Nanta Biton": (197, 198),
        "Escudo de Orichalko": (199, 200),
    }

    weapon_entities = []
    for weapon_name, (start, end) in weapon_defs.items():
        if end < len(paras):
            content = [p for p in paras[start:end+1] if p.strip()]
            if content:
                weapon_entities.append({
                    "id": slugify(weapon_name),
                    "title": weapon_name,
                    "area": "itens_equipamentos",
                    "kind": "equipment",
                    "paragraphs": content,
                    "sections": []
                })

    if weapon_entities:
        groups.append({
            "id": "equipamentos-sicarios",
            "title": "Equipamentos & Armas",
            "kind": "equipment",
            "area": "itens_equipamentos",
            "sectionTitle": "Equipamento",
            "sections": weapon_entities
        })

    # Count areas
    area_counts = {}
    for g in groups:
        area = g["area"]
        count = len(g.get("sections", []))
        area_counts[area] = area_counts.get(area, 0) + count

    return {
        "version": 1,
        "status": "pilot_review",
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "source": SOURCE,
        "sourceFile": SOURCE_PATH.name,
        "sourcePath": str(SOURCE_PATH.relative_to(ROOT)),
        "title": TITLE,
        "summary": "Suplemento de lore sobre os Angélicos Sicários: assassinos divinos da Cidade de Prata. Inclui 9 seções de história/lore, 7 técnicas de combate (aprimoramentos), 11 armas/artefatos individuais, e poderes especiais.",
        "areas": sorted(area_counts.keys()),
        "groups": groups,
        "sections": [],
        "areaCounts": area_counts,
    }

def main() -> None:
    print(f"Building with individual equipment entities...")
    payload = build_pilot()

    write_json(OUT_PATH, payload)
    write_json(DOCS_OUT_PATH, payload)

    print(f"Groups: {len(payload['groups'])}")
    for g in payload['groups']:
        print(f"  - {g['title']}: {len(g['sections'])} entities")
    print(f"Total areas: {payload['areaCounts']}")

if __name__ == "__main__":
    main()
