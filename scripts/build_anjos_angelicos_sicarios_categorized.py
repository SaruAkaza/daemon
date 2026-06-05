#!/usr/bin/env python3
"""
Build categorized pilot JSON for: Anjos - Angélicos Sicários
Separates lore, powers, equipment, and combat rules into distinct areas
"""

import re
from datetime import datetime
from docx import Document

from common import ROOT, slugify, write_json

SOURCE = "anjos-angelicos-sicarios"
TITLE = "Anjos - A Cidade de Prata - Angélicos Sicários"
SOURCE_PATH = ROOT / "Livros" / "word" / "Anjos - A Cidade de Prata - Angélicos Sicários.docx"
OUT_PATH = ROOT / "data" / "pilot" / f"{SOURCE}-categorized.json"
DOCS_OUT_PATH = ROOT / "docs" / "assets" / "data" / "pilot" / f"{SOURCE}-categorized.json"

def normalize_text(text: str) -> str:
    """Clean and normalize OCR text"""
    text = text.replace(" ", " ")
    text = text.replace("—", "-").replace("–", "-")
    text = text.replace(""", '"').replace(""", '"').replace("'", "'")
    text = text.replace("l O", "10").replace("l d", "1d").replace("l D", "1D")
    text = text.replace("1d10O", "1d100")
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return text

def docx_paragraphs() -> list[str]:
    """Extract paragraphs from DOCX and apply OCR cleanup"""
    document = Document(SOURCE_PATH)
    values = []

    for paragraph in document.paragraphs:
        text = normalize_text(paragraph.text)
        if not text:
            values.append("")
            continue
        if text == TITLE:
            continue
        values.append(text)

    return values

def categorize_content(paragraphs: list[str]) -> dict:
    """Categorize content into sections"""

    groups = {
        "cenarios_lore": {
            "id": "cenarios_lore",
            "title": "Lore & História",
            "kind": "setting",
            "area": "cenarios_lore",
            "sectionTitle": "Cenário",
            "sections": []
        },
        "poderes": {
            "id": "poderes_sicarios",
            "title": "Argúcias (Poderes)",
            "kind": "ability",
            "area": "poderes",
            "sectionTitle": "Poder",
            "sections": []
        },
        "itens": {
            "id": "equipamentos_sicarios",
            "title": "Equipamentos & Armas",
            "kind": "equipment",
            "area": "itens_equipamentos",
            "sectionTitle": "Equipamento",
            "sections": []
        },
        "regras": {
            "id": "tecnicas_combate_sicarios",
            "title": "Técnicas de Combate",
            "kind": "rule",
            "area": "regras_base",
            "sectionTitle": "Técnica",
            "sections": []
        }
    }

    # Parse sections
    current_section = None
    current_content = []
    current_category = None

    for para in paragraphs:
        if not para.strip():
            continue

        # Detect section boundaries
        if para.lower().startswith("argúcias"):
            current_category = "poderes"
            current_section = "Poderes dos Sicários"
        elif para.lower().startswith("yaldabaoth"):
            current_category = "itens"
            current_section = "Armas Especiais"
        elif para.lower().startswith("desarm") or "manobra" in para.lower():
            current_category = "regras"
            current_section = "Manobras de Combate"
        elif para.lower().startswith("as luminárias"):
            current_category = "cenarios_lore"
            current_section = "Prisões Secretas"
        elif len(para) < 80 and para.isupper() and len(para.split()) < 10:
            # New heading
            if current_category and current_section and current_content:
                groups[current_category]["sections"].append({
                    "id": slugify(current_section),
                    "title": current_section,
                    "area": groups[current_category]["area"],
                    "paragraphs": [p for p in current_content if p.strip()]
                })
            current_section = para
            if not current_category:
                current_category = "cenarios_lore"
            current_content = []
            continue

        # Add to current section
        if current_category:
            current_content.append(para)
        else:
            # First section (default to lore)
            current_category = "cenarios_lore"
            if not current_section:
                current_section = "Origem e História"
            current_content.append(para)

    # Save last section
    if current_category and current_section and current_content:
        groups[current_category]["sections"].append({
            "id": slugify(current_section),
            "title": current_section,
            "area": groups[current_category]["area"],
            "paragraphs": [p for p in current_content if p.strip()]
        })

    return groups

def build_pilot() -> dict:
    """Build pilot structure with categorization"""
    paragraphs = docx_paragraphs()
    groups_dict = categorize_content(paragraphs)

    # Filter out empty groups
    groups = [g for g in groups_dict.values() if g["sections"]]

    area_counts = {}
    for group in groups:
        area = group["area"]
        area_counts[area] = area_counts.get(area, 0) + len(group["sections"])

    return {
        "version": 1,
        "status": "pilot_review",
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "source": SOURCE,
        "sourceFile": SOURCE_PATH.name,
        "sourcePath": str(SOURCE_PATH.relative_to(ROOT)),
        "title": TITLE,
        "summary": "Suplemento de lore sobre os Angélicos Sicários, assassinos divinos da Cidade de Prata. Inclui história, organização, habilidades, técnicas de combate, equipamentos especiais e informações sobre prisões secretas.",
        "areas": list(area_counts.keys()),
        "groups": groups,
        "sections": [],
        "areaCounts": area_counts,
    }

def main() -> None:
    print(f"Reading: {SOURCE_PATH}")
    payload = build_pilot()

    write_json(OUT_PATH, payload)
    write_json(DOCS_OUT_PATH, payload)

    print(f"Wrote {OUT_PATH.relative_to(ROOT)}")
    print(f"Wrote {DOCS_OUT_PATH.relative_to(ROOT)}")

    total_sections = sum(len(g["sections"]) for g in payload["groups"])
    print(f"Groups: {len(payload['groups'])}, Total sections: {total_sections}")
    print(f"Areas: {payload['areas']}")

if __name__ == "__main__":
    main()
