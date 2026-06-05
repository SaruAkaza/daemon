#!/usr/bin/env python3
"""
Build pilot JSON for: Anjos - A Cidade de Prata - Angélicos Sicários
Lore/Scenario supplement focused on the Angelic Assassins class
"""

import re
from datetime import datetime
from docx import Document

from common import ROOT, slugify, write_json

SOURCE = "anjos-angelicos-sicarios"
TITLE = "Anjos - A Cidade de Prata - Angélicos Sicários"
SOURCE_PATH = ROOT / "Livros" / "word" / "Anjos - A Cidade de Prata - Angélicos Sicários.docx"
OUT_PATH = ROOT / "data" / "pilot" / f"{SOURCE}.json"
DOCS_OUT_PATH = ROOT / "docs" / "assets" / "data" / "pilot" / f"{SOURCE}.json"

def normalize_text(text: str) -> str:
    """Clean and normalize OCR text"""
    text = text.replace(" ", " ")
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

def build_pilot() -> dict:
    """Build pilot structure for lore-focused supplement"""
    paragraphs = docx_paragraphs()

    # Group content into sections based on headings
    sections = []
    current_section = None
    current_content = []

    for para in paragraphs:
        # Detect section headings (short, capitalized lines)
        if para and len(para) < 80 and para.isupper() and len(para.split()) < 10:
            # Save previous section
            if current_section and current_content:
                sections.append({
                    "id": slugify(current_section),
                    "title": current_section,
                    "area": "cenarios_lore",
                    "paragraphs": [p for p in current_content if p.strip()]
                })
            current_section = para
            current_content = []
        elif current_section:
            current_content.append(para)

    # Save last section
    if current_section and current_content:
        sections.append({
            "id": slugify(current_section),
            "title": current_section,
            "area": "cenarios_lore",
            "paragraphs": [p for p in current_content if p.strip()]
        })

    # If no clear sections found, create default
    if not sections:
        sections = [{
            "id": "conteudo",
            "title": "Conteúdo",
            "area": "cenarios_lore",
            "paragraphs": [p for p in paragraphs if p.strip()]
        }]

    # Build main group
    group = {
        "id": slugify(f"{SOURCE}-lore"),
        "title": TITLE,
        "kind": "setting",
        "area": "cenarios_lore",
        "sectionTitle": "Cenário",
        "sections": sections
    }

    return {
        "version": 1,
        "status": "pilot_review",
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "source": SOURCE,
        "sourceFile": SOURCE_PATH.name,
        "sourcePath": str(SOURCE_PATH.relative_to(ROOT)),
        "title": TITLE,
        "summary": "Suplemento de lore sobre os Angélicos Sicários, a casta de assassinos divinos da Cidade de Prata. Contém história, organização e detalhes sobre esta classe exclusiva de anjos.",
        "areas": ["cenarios_lore"],
        "groups": [group],
        "sections": [],
        "areaCounts": {"cenarios_lore": 1},
    }

def main() -> None:
    print(f"Reading: {SOURCE_PATH}")
    payload = build_pilot()

    write_json(OUT_PATH, payload)
    write_json(DOCS_OUT_PATH, payload)

    print(f"Wrote {OUT_PATH.relative_to(ROOT)}")
    print(f"Wrote {DOCS_OUT_PATH.relative_to(ROOT)}")

    sections_count = len(payload['groups'][0]['sections']) if payload['groups'] else 0
    print(f"Groups: {len(payload['groups'])}, Sections: {sections_count}")

if __name__ == "__main__":
    main()
