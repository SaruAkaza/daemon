#!/usr/bin/env python3
"""
Build Anjos - Angélicos Sicários pilot.

Reads the DOCX directly. Critical: the source has many soft line-breaks that
split sentences mid-paragraph. This script reconstructs coherent paragraphs
BEFORE sectioning, then splits powers/maneuvers/weapons into individual
entities by their named anchors.
"""

from pathlib import Path
import json
import re
from datetime import datetime
from docx import Document

from common import ROOT, slugify, write_json

SOURCE = "anjos-angelicos-sicarios"
TITLE = "Anjos - A Cidade de Prata - Angélicos Sicários"
SOURCE_PATH = ROOT / "Livros" / "word" / "Anjos - A Cidade de Prata - Angélicos Sicários.docx"
OUT_PATH = ROOT / "data" / "pilot" / f"{SOURCE}.json"
DOCS_OUT_PATH = ROOT / "docs" / "assets" / "data" / "pilot" / f"{SOURCE}.json"

# Section titles that appear standalone (used as section delimiters / kept apart)
SECTION_TITLES = {
    "O Evangelho de Judas", "Angélicos Sicários", "Imagens internas:",
    "Agradecimentos", "O Plano de Christos", "A Origem", "Organização",
    "A Caçada sem fim", "Batalhas Patrísticas", "Atividades no Império Romano",
    "A Idade Média", "As Cruzadas", "Grandes cismas", "A Inquisição",
    "Reforma e Contrarreforma", "Iniquidades", "Arcádia", "Aasgard", "Katmaran",
    "A Cidade Dourada de Ra", "Tir Na Nog", "ArK-A-Nun", "Limbo",
    "O Mercado de Assassinos", "A Guilda", "Formas de Pagamento", "Especialistas",
    "Argúcias (Sicários)", "O Credo do Silêncio",
}

# Combat maneuvers (aprimoramentos) — anchored names, in document order
MANEUVER_NAMES = [
    "Desarmar com Asa", "Ataque Rolante", "Finta", "Mata-Dragão",
    "Coração de Fafnir", "Calcanhar da Fera", "Asas Cortantes",
]

# Weapons / equipment — anchored names, in document order
WEAPON_NAMES = [
    "Yaldabaoth", "Nebro", "Saklas", "Harmathoth", "Galila", "Exarp", "Hcoma",
    "Manto do Sicário", "Angélica Sica", "Nanta Biton", "Escudo de Orichalko",
]

# Prison entities (lore) — anchored names
PRISON_NAMES = ["Shamayim", "Raquia", "Shehaquim", "Machanon"]


def normalize(text: str) -> str:
    text = text.replace("\xa0", " ").replace("—", "-").replace("–", "-")
    return re.sub(r"\s+", " ", text).strip()


def coherent_paragraphs() -> list[str]:
    """Extract DOCX paragraphs, rejoining soft-broken fragments into
    coherent paragraphs."""
    doc = Document(SOURCE_PATH)
    raw = [normalize(p.text) for p in doc.paragraphs]
    raw = [t for t in raw if t and t != TITLE]

    # Merge the split title "Argúcias" + "(Sicários)"
    merged = []
    i = 0
    while i < len(raw):
        if raw[i] == "Argúcias" and i + 1 < len(raw) and raw[i + 1] == "(Sicários)":
            merged.append("Argúcias (Sicários)")
            i += 2
        else:
            merged.append(raw[i])
            i += 1
    raw = merged

    is_noise = lambda l: bool(re.match(r"^\d{1,3}$", l.strip()))
    is_epigraph = lambda l: l.lstrip().startswith("“")
    ends_terminal = lambda l: l.rstrip().endswith((".", "!", "?", "”", ")", "]", ":"))

    result: list[str] = []
    buffer = ""

    def flush():
        nonlocal buffer
        if buffer.strip():
            result.append(buffer.strip())
        buffer = ""

    for line in raw:
        if is_noise(line):
            continue
        if line in SECTION_TITLES:
            flush()
            result.append(line)
            continue
        if is_epigraph(line):
            flush()
            buffer = line
            # Epigraph closes immediately unless attribution is still open
            if not (buffer.rstrip().endswith("-") or buffer.rstrip().endswith("”")):
                flush()
            continue
        if not buffer:
            buffer = line
        elif ends_terminal(buffer):
            flush()
            buffer = line
        else:
            if buffer.endswith("-") and not buffer.endswith(" -"):
                buffer = buffer[:-1] + line  # hyphenated name (e.g. ArK-A-Nun)
            else:
                buffer = buffer + " " + line
    flush()
    return result


def split_by_anchors(blob: str, names: list[str], require_colon: bool = False) -> list[tuple[str, str]]:
    """Split a text blob into (name, text) chunks using known leading names.

    Only the FIRST definition of each name is used as a split point (later
    mentions inside descriptions are ignored). When require_colon is True the
    name must be followed by an optional cost and a colon (the definition form,
    e.g. ``Exarp:`` or ``Desarmar com Asa (25):``)."""
    escaped = [re.escape(n) for n in names]
    if require_colon:
        anchor = r"(?:(?<=^)|(?<=[\s.]))(" + "|".join(escaped) + r")(?:\s*\([^)]*\))?\s*:"
    else:
        anchor = r"(?:(?<=^)|(?<=[\s.]))(" + "|".join(escaped) + r")\b"
    pattern = re.compile(anchor)

    # Keep only the first match per name, in document order
    seen = set()
    starts = []
    for m in pattern.finditer(blob):
        name = m.group(1)
        if name in seen:
            continue
        seen.add(name)
        starts.append((m.start(), name))
    starts.sort()

    chunks = []
    for idx, (start, name) in enumerate(starts):
        end = starts[idx + 1][0] if idx + 1 < len(starts) else len(blob)
        chunks.append((name, blob[start:end].strip()))
    return chunks


def split_powers(blob: str) -> list[tuple[str, str]]:
    """Split Argúcias by 'Nível N: Nome.' markers."""
    # Normalize 'Nivel' -> 'Nível'
    blob = re.sub(r"\bNivel\b", "Nível", blob)
    pattern = re.compile(r"(Nível\s+\d+:\s*[^.]+\.)")
    parts = pattern.split(blob)
    chunks = []
    # parts: [pre, marker1, body1, marker2, body2, ...]
    i = 1
    while i < len(parts):
        marker = parts[i].strip()
        body = parts[i + 1].strip() if i + 1 < len(parts) else ""
        # marker looks like "Nível 1: Marca." -> name = "Marca"
        mm = re.match(r"Nível\s+\d+:\s*(.+?)\.", marker)
        name = mm.group(1).strip() if mm else marker
        text = (marker + " " + body).strip()
        chunks.append((name, text))
        i += 2
    return chunks


def build_section(title, area, paragraphs):
    return {
        "id": slugify(title),
        "title": title,
        "area": area,
        "paragraphs": [p for p in paragraphs if p.strip()],
    }


def build_maneuver_entity(name, text):
    """Combat maneuver: split inline '(custo):' from the description.
    Per cataloging rules, a single cost shows only the value."""
    m = re.match(r"^\s*.*?\(\s*(\d+)\s*\)\s*:\s*(.*)$", text, re.DOTALL)
    cost = m.group(1).strip() if m else ""
    desc = (m.group(2).strip() if m else text).strip()
    sections = []
    if cost:
        sections.append({
            "id": "custo", "title": "Custo", "area": "manobras_combate",
            "paragraphs": [cost],
        })
    sections.append({
        "id": "descricao", "title": "Descrição", "area": "manobras_combate",
        "paragraphs": [desc],
    })
    return {
        "id": slugify(name),
        "title": name,
        "area": "manobras_combate",
        "kind": "maneuver",
        "sectionId": "descricao",
        "sectionTitle": "Manobra",
        "paragraphs": [desc],
        "sections": sections,
    }


def build_entity(name, area, kind, section_title, paragraphs):
    """Build an individual, browsable entity for the top-level `sections` array.
    The app renders each top-level section as its own list item (groups, by
    contrast, collapse into a single item)."""
    return {
        "id": slugify(name),
        "title": name,
        "area": area,
        "kind": kind,
        "sectionId": slugify(section_title),
        "sectionTitle": section_title,
        "paragraphs": [p for p in paragraphs if p.strip()],
        "sections": [],
    }


def build_pilot() -> dict:
    paras = coherent_paragraphs()

    # Index helpers
    def find(title):
        return paras.index(title)

    # ---- LORE sections (title -> content until next title) ----
    lore_titles_in_order = [
        "O Plano de Christos", "A Origem", "Organização", "A Caçada sem fim",
        "Batalhas Patrísticas", "Atividades no Império Romano", "A Idade Média",
        "As Cruzadas", "Grandes cismas", "A Inquisição", "Reforma e Contrarreforma",
        "Iniquidades", "Arcádia", "Aasgard", "Katmaran", "A Cidade Dourada de Ra",
        "Tir Na Nog", "ArK-A-Nun", "Limbo", "O Mercado de Assassinos", "A Guilda",
        "Formas de Pagamento", "Especialistas",
    ]

    # Front matter = everything before first lore title
    first_lore_idx = find(lore_titles_in_order[0])
    front_matter = paras[:first_lore_idx]

    lore_sections = []
    # Apresentação (front matter)
    fm_content = [p for p in front_matter if p not in SECTION_TITLES or p in
                  ("O Evangelho de Judas", "Angélicos Sicários")]
    lore_sections.append(build_section("Apresentação", "cenarios_lore", front_matter))

    # Each lore title section
    all_title_positions = sorted(
        [find(t) for t in lore_titles_in_order] +
        [find("Argúcias (Sicários)")]
    )
    for t in lore_titles_in_order:
        start = find(t)
        # next title position after start
        nexts = [pos for pos in all_title_positions if pos > start]
        end = min(nexts) if nexts else len(paras)
        content = paras[start + 1:end]
        lore_sections.append(build_section(t, "cenarios_lore", content))

    # ---- POWERS (Argúcias) ----
    arg_idx = find("Argúcias (Sicários)")
    credo_idx = find("O Credo do Silêncio")
    powers_blob = " ".join(paras[arg_idx + 1:credo_idx])
    power_chunks = split_powers(powers_blob)
    power_entities = [build_entity(n, "poderes", "power", "Poder", [t])
                      for n, t in power_chunks]

    # ---- CREDO (lore) + verses ----
    # Credo verses run from after credo_idx until first epigraph that precedes maneuvers
    # Find the "Clube da Luta" epigraph (maneuvers start after it)
    luta_idx = next(i for i, p in enumerate(paras)
                    if p.startswith("“As lutas duram"))
    credo_content = paras[credo_idx + 1:luta_idx]
    lore_sections.append(build_section("O Credo do Silêncio", "cenarios_lore", credo_content))

    # ---- MANEUVERS (aprimoramentos) ----
    # From after Clube da Luta epigraph until the Looper epigraph
    looper_idx = next(i for i, p in enumerate(paras)
                      if p.startswith("“A única regra"))
    maneuvers_blob = " ".join(paras[luta_idx + 1:looper_idx])
    maneuver_chunks = split_by_anchors(maneuvers_blob, MANEUVER_NAMES, require_colon=True)
    maneuver_entities = [build_maneuver_entity(n, t) for n, t in maneuver_chunks]

    # ---- WEAPONS (itens) ----
    # From after Looper epigraph until the Nietzche/Abismo epigraph
    abismo_idx = next(i for i, p in enumerate(paras)
                      if p.startswith("“Não olhe muito tempo"))
    weapons_blob = " ".join(paras[looper_idx + 1:abismo_idx])
    weapon_chunks = split_by_anchors(weapons_blob, WEAPON_NAMES, require_colon=True)
    weapon_entities = [build_entity(n, "itens_equipamentos", "equipment", "Equipamento", [t])
                       for n, t in weapon_chunks]

    # ---- PRISONS (lore) ----
    prisons_blob = " ".join(paras[abismo_idx + 1:])
    # Keep the intro (As Luminárias...) as a lore section, then split prisons
    prison_chunks = split_by_anchors(prisons_blob, PRISON_NAMES, require_colon=True)
    intro_end = prisons_blob.find(prison_chunks[0][1]) if prison_chunks else len(prisons_blob)
    prison_intro = prisons_blob[:intro_end].strip()
    prison_sections = []
    if prison_intro:
        prison_sections.append(build_section("As Luminárias", "cenarios_lore", [prison_intro]))
    for n, t in prison_chunks:
        prison_sections.append(build_section(n, "cenarios_lore", [t]))
    lore_sections.extend(prison_sections)

    # ---- Assemble ----
    # Lore (history + prisons) stays as a single group → one "Cenário" item.
    groups = [
        {
            "id": "cenarios-lore-sicarios", "title": "Lore & História",
            "kind": "setting", "area": "cenarios_lore", "sectionTitle": "Cenário",
            "sections": lore_sections,
        },
    ]

    # Powers, maneuvers and weapons become individual browsable items.
    top_sections = power_entities + maneuver_entities + weapon_entities

    area_counts = {"cenarios_lore": 1}
    for s in top_sections:
        area_counts[s["area"]] = area_counts.get(s["area"], 0) + 1

    return {
        "version": 1,
        "status": "pilot_review",
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "source": SOURCE,
        "sourceFile": SOURCE_PATH.name,
        "sourcePath": str(SOURCE_PATH.relative_to(ROOT)),
        "title": TITLE,
        "summary": "Suplemento de lore sobre os Angélicos Sicários: assassinos divinos da Cidade de Prata. História completa da Ordem, poderes (Argúcias), manobras de combate, armas/artefatos e prisões secretas.",
        "areas": sorted(area_counts.keys()),
        "groups": groups,
        "sections": top_sections,
        "areaCounts": area_counts,
    }


def main() -> None:
    payload = build_pilot()
    write_json(OUT_PATH, payload)
    write_json(DOCS_OUT_PATH, payload)
    print(f"Groups (lore): {len(payload['groups'])} -> {len(payload['groups'][0]['sections'])} lore sections")
    print(f"Top-level individual items: {len(payload['sections'])}")
    from collections import Counter
    by_area = Counter(s['area'] for s in payload['sections'])
    for area, n in by_area.items():
        print(f"  {area}: {n}")
    print(f"areaCounts: {payload['areaCounts']}")


if __name__ == "__main__":
    main()
