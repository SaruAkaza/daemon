#!/usr/bin/env python3
"""
Final categorized build for Anjos - Angélicos Sicários
Groups content by topic: lore, powers, equipment, aprimoramentos
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

    # Manual section boundaries (line numbers)
    sections_map = {
        "cenarios_lore": {
            "label": "Lore & História",
            "kind": "setting",
            "area": "cenarios_lore",
            "subsections": {
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
        },
        "poderes": {
            "label": "Argúcias (Poderes)",
            "kind": "power",
            "area": "poderes",
            "subsections": {
                "Poderes dos Sicários": (152, 166),
            }
        },
        "aprimoramentos": {
            "label": "Manobras de Combate",
            "kind": "enhancement",
            "area": "aprimoramentos",
            "subsections": {
                "Técnicas de Combate": (177, 182),
            }
        },
        "itens_equipamentos": {
            "label": "Equipamentos & Armas",
            "kind": "equipment",
            "area": "itens_equipamentos",
            "subsections": {
                "Armas Especiais": (183, 199),
            }
        }
    }

    groups = []
    area_counts = {}

    for cat_key, cat_info in sections_map.items():
        sections = []
        for sec_title, (start, end) in cat_info["subsections"].items():
            if end > len(paras):
                end = len(paras)
            if start < len(paras):
                content = [p for p in paras[start:end] if p.strip()]
                if content:
                    sections.append({
                        "id": slugify(sec_title),
                        "title": sec_title,
                        "area": cat_info["area"],
                        "paragraphs": content
                    })

        if sections:
            groups.append({
                "id": slugify(cat_info["label"]),
                "title": cat_info["label"],
                "kind": cat_info["kind"],
                "area": cat_info["area"],
                "sectionTitle": sec_title.split()[0],
                "sections": sections
            })
            area_counts[cat_info["area"]] = area_counts.get(cat_info["area"], 0) + len(sections)

    return {
        "version": 1,
        "status": "pilot_review",
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "source": SOURCE,
        "sourceFile": SOURCE_PATH.name,
        "sourcePath": str(SOURCE_PATH.relative_to(ROOT)),
        "title": TITLE,
        "summary": "Suplemento de lore sobre os Angélicos Sicários: assassinos divinos e espiões da Cidade de Prata. Contém história completa da Ordem, habilidades (poderes), aprimoramentos de combate, equipamentos especiais e informações sobre prisões secretas.",
        "areas": list(area_counts.keys()),
        "groups": groups,
        "sections": [],
        "areaCounts": area_counts,
    }

def main() -> None:
    print(f"Building categorized pilot...")
    payload = build_pilot()

    write_json(OUT_PATH, payload)
    write_json(DOCS_OUT_PATH, payload)

    print(f"Groups: {len(payload['groups'])}")
    for g in payload['groups']:
        print(f"  - {g['title']}: {len(g['sections'])} sections")
    print(f"Areas: {list(payload['areaCounts'].keys())}")

if __name__ == "__main__":
    main()
