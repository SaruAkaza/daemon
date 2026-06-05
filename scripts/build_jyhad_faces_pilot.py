#!/usr/bin/env python3
"""
Build pilot JSON for 'Anjos Jyhad - Faces da Fé' (classic Daemon d% system).

Categorisation (per user review):
  - cenarios_lore : mundane/magic orders (Cap 1, 3), antagonists (Cap 4, no
                    stat block) and the cost-less angelic overviews (Cap 2)
  - kits          : angelic orders that cost 'N Pontos de Aprimoramento' (Cap 2)
  - criaturas_npcs: every stat-blocked ficha (Cap 5 archetypes + Garanhão)
"""
from __future__ import annotations
import re
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent))
from requiem_clean import dehyphenate, join_body, normalize  # noqa: E402
from common import ROOT, slugify, write_json  # noqa: E402
from docx import Document  # noqa: E402

SOURCE = "anjos-jyhad-faces-da-fe"
TITLE = "Anjos Jyhad - Faces da Fé"
SOURCE_PATH = ROOT / "Livros" / "word" / "Anjos Jyhad - Faces da Fé.docx"
OUT_PATH = ROOT / "data" / "pilot" / f"{SOURCE}.json"
DOCS_OUT_PATH = ROOT / "docs" / "assets" / "data" / "pilot" / f"{SOURCE}.json"

SKIP_TITLES = {"Índice", "Índice das Imagens", "Errata Jyhad: Guerra Santa",
               "Bibliografia"}
CON_RE = re.compile(r"\bCON\s+\d+")
COST_RE = re.compile(r"(\d+)\s+Pontos?\s+de\s+Aprimoramento", re.I)
ATTR_KEYS = ["CON", "FR", "DEX", "AGI", "INT", "WILL", "PER", "CAR"]


# ------------------------------------------------------------ extraction
def extract_blocks():
    """(level, chapter, parent_h3, title, body[], raw[]) for Heading 1-5."""
    doc = Document(SOURCE_PATH)
    blocks = []
    cl = ct = None
    craw = []
    chapter = None
    parent_h3 = None

    def push():
        if ct is not None or craw:
            raw = [dehyphenate(normalize(x)) for x in craw if x.strip()]
            blocks.append((cl, chapter, parent_h3, ct, join_body(craw), raw))

    for p in doc.paragraphs:
        t = p.text.strip()
        if not t:
            continue
        st = p.style.name if p.style else ""
        if st.startswith("Heading") and st[-1] in "12345":
            if re.fullmatch(r"\d+", t):
                craw.append(t)
                continue
            push()
            cl = int(st[-1])
            ct = dehyphenate(normalize(t))
            craw = []
            if cl == 1:
                chapter = ct
                parent_h3 = None
            elif cl == 3:
                parent_h3 = ct
        else:
            craw.append(t)
    push()
    return blocks


# ------------------------------------------------------------ builders
def sec(id_, title, area, paras):
    return {"id": id_, "title": title, "area": area,
            "paragraphs": [p for p in paras if p and p.strip()]}


DANGLING = re.compile(r"\b(das|dos|de|da|do)$", re.I)
FALANGE_NAME = re.compile(r"^\S+\s+Falange\s+Orbis\b", re.I)
PATRON_RE = re.compile(r"Sant[oa]:\s*(Sant[oa]\s+[A-ZÀ-Ý][\wáéíóúâêôãõç]+)")


def canonical_name(heading, raw):
    """Reconstruct a complete entity name from the (un-joined) raw lines.
    Headings are often truncated and the real name (or its tail) is the first
    body line (e.g. 'Observadores das' + '95 Teses')."""
    body0 = raw[0].strip() if raw else ""
    short_name = bool(body0) and len(body0.split()) <= 7 \
        and not body0.rstrip().endswith((".", "!", "?")) and ":" not in body0
    if short_name and (DANGLING.search(heading) or heading.endswith(("Santo", "Santa"))
                       or len(heading.split()) <= 2):
        return f"{heading} {body0}".strip()
    if heading.startswith("Ordem"):
        for l in raw[:6]:
            m = PATRON_RE.search(l)
            if m:
                patron = m.group(1).strip()
                if patron.split()[-1].lower() not in heading.lower():
                    return f"{heading} de {patron}"
                break
    return heading


def split_falanges(raw):
    """An 'As Falanges*' block lists named falanges in its body; yield
    (name, lines) per falange (names come from the body, not the heading)."""
    idxs = [i for i, l in enumerate(raw) if FALANGE_NAME.match(l)]
    if not idxs:
        return [(raw[0].rstrip(":").strip(), raw)] if raw else []
    out = []
    for j, start in enumerate(idxs):
        end = idxs[j + 1] if j + 1 < len(idxs) else len(raw)
        out.append((raw[start].strip(), raw[start:end]))
    return out


def build_kit(title, body):
    custo = ""
    for p in body:
        m = COST_RE.search(p)
        if m:
            n = m.group(1)
            custo = f"{n} ponto" if n == "1" else f"{n} pontos"
            break
    subs = []
    if custo:
        subs.append(sec("custo", "Custo", "kits", [custo]))
    subs.append(sec("descricao", "Descrição", "kits", body))
    return {
        "id": slugify("kit-" + title), "title": title, "area": "kits",
        "kind": "kit", "sectionId": "descricao", "sectionTitle": "Kit",
        "paragraphs": body, "sections": subs,
    }


HAB_TRIGGER = ("Poderes:", "Poderes ", "Magia:", "-")
NARRATIVE = re.compile(
    r"\b(foi|era|é|são|tem|possui|tinha|estava|nasceu|viveu|criou|lutou|"
    r"aliada|aliado|responsável|começa|conhecido|conhecida|durante|após|"
    r"quando|onde|porém|apesar)\b")


def build_character(name, raw):
    attr_idx = next((i for i, l in enumerate(raw) if CON_RE.search(l)), None)
    role = " ".join(raw[:attr_idx]).strip() if attr_idx else ""
    body = raw[attr_idx:] if attr_idx is not None else raw
    text = " ".join(body)

    attributes = {}
    for k in ATTR_KEYS:
        m = re.search(rf"\b{k}\s+(\d+)", text)
        if m:
            attributes[k] = int(m.group(1))
    vitals = {}
    m = re.search(r"PVs?\s*([\d+]+)", text)
    if m:
        vitals["PV"] = m.group(1)
    m = re.search(r"\bIP\s*:?\s*([\d/]+)", text)
    if m:
        vitals["IP"] = m.group(1)
    m = re.search(r"#?\s*Ataques\s*\[?(\d+)\]?", text)
    if m:
        vitals["Ataques"] = m.group(1)
    attr_text = " ".join(f"{k} {v}" for k, v in attributes.items())

    def is_narrative(l):
        return len(l) > 60 and bool(NARRATIVE.search(l))

    skills, hab, desc = [], [], []
    phase = "skills"
    for l in body:
        if CON_RE.search(l) or re.match(r"^\s*INT\b", l) or re.match(r"^#?\s*Ataques", l):
            # attribute / second attribute line / vitals -> statBlock only
            if re.match(r"^#?\s*Ataques", l) and "/" in l:
                pass  # attack+vitals combined line still useful as skill? keep simple: skip
            continue
        if phase == "desc":
            desc.append(l)
        elif phase == "skills":
            if l.startswith(("Poderes:", "Poderes ", "Magia")) or l.startswith("-"):
                phase = "hab"
                hab.append(l)
            elif is_narrative(l) and "(" not in l and l.count(",") < 3:
                phase = "desc"
                desc.append(l)
            else:
                skills.append(l)
        else:
            if l.startswith("-") or not is_narrative(l):
                hab.append(l)
            else:
                phase = "desc"
                desc.append(l)

    sections = [sec("ficha", "Ficha", "criaturas_npcs", ([role] + body) if role else body)]
    if hab:
        sections.append(sec("habilidades", "Habilidades", "criaturas_npcs", hab))
    if desc:
        sections.append(sec("descricao", "Descrição", "criaturas_npcs", desc))

    return {
        "id": slugify(name), "name": name, "type": "character_npc", "role": role,
        "classifications": [{"area": "criaturas_npcs", "confidence": 1.0,
                             "reason": "Ficha de NPC/arquétipo com atributos Daemon"}],
        "statBlock": {"attributes": attributes, "vitals": vitals,
                      "attributesText": attr_text, "skills": "\n".join(skills),
                      "special": []},
        "sections": sections,
    }


# ------------------------------------------------------------ build
def build():
    blocks = extract_blocks()

    lore_sections, kits, characters = [], [], []
    seen_char = {}

    for lvl, chapter, parent_h3, title, body, raw in blocks:
        if title is None or title in SKIP_TITLES:
            continue
        if title.startswith(("Capítulo", "Suplemento")):
            continue
        if title[:1].islower():
            continue  # back-matter fragment (e.g. 'um netbook da')
        if title in ("Introdução",):
            lore_sections.append(sec("introducao", "Introdução", "cenarios_lore", body))
            continue

        has_stats = any(CON_RE.search(l) for l in raw)
        has_cost = any(COST_RE.search(p) for p in body)

        if has_stats:
            # NPC ficha. Disambiguate variant names with their parent archetype.
            clean = title.rstrip(":").strip()
            name = clean
            if lvl >= 4 and parent_h3 and parent_h3.lower().startswith("anjo"):
                name = f"{parent_h3} — {clean}"
            base = name
            seen_char[base] = seen_char.get(base, 0) + 1
            if seen_char[base] > 1:
                name = f"{base} ({seen_char[base]})"
            characters.append(build_character(name, raw))
        elif chapter == "Capítulo 2" and title.startswith("As Falanges"):
            # Block lists several named falanges; each is its own kit (with cost)
            # or a lore section (without).
            for fname, flines in split_falanges(raw):
                flbody = join_body(flines)
                if any(COST_RE.search(p) for p in flbody):
                    kits.append(build_kit(fname, flbody))
                else:
                    lore_sections.append(sec(slugify(fname), fname, "cenarios_lore", flbody))
        elif chapter == "Capítulo 2" and has_cost:
            name = canonical_name(title, raw)
            kits.append(build_kit(name, body))
        else:
            # lore section (mundane/magic orders, antagonists, angelic overviews)
            name = canonical_name(title, raw)
            lore_sections.append(sec(slugify(name), name, "cenarios_lore", body))

    groups = [{
        "id": "lore-jyhad", "title": TITLE, "kind": "setting",
        "area": "cenarios_lore", "sectionTitle": "Cenário",
        "sections": lore_sections,
    }]
    top = kits

    area_counts = {"cenarios_lore": 1}
    for s in top:
        area_counts[s["area"]] = area_counts.get(s["area"], 0) + 1
    if characters:
        area_counts["criaturas_npcs"] = len(characters)

    return {
        "version": 1, "status": "pilot_review",
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "source": SOURCE, "sourceFile": SOURCE_PATH.name,
        "sourcePath": str(SOURCE_PATH.relative_to(ROOT)), "title": TITLE,
        "summary": "Faces da Fé: seitas, sociedades e ordens (mundanas, angelicais e de magia), antagonistas e arquétipos de NPC para Jyhad: Guerra Santa.",
        "areas": sorted(area_counts.keys()),
        "groups": groups, "sections": top, "characters": characters,
        "areaCounts": area_counts,
    }


def main():
    payload = build()
    write_json(OUT_PATH, payload)
    write_json(DOCS_OUT_PATH, payload)
    from collections import Counter
    print(f"Lore sections: {len(payload['groups'][0]['sections'])}")
    print(f"Kits: {len([s for s in payload['sections'] if s['area']=='kits'])}")
    print(f"NPCs (characters): {len(payload['characters'])}")
    ids = [c["id"] for c in payload["characters"]] + [s["id"] for s in payload["sections"]]
    dups = [i for i, c in Counter(ids).items() if c > 1]
    print(f"  duplicate ids: {dups}")
    print("  NPC names:", [c["name"] for c in payload["characters"]])


if __name__ == "__main__":
    main()
