#!/usr/bin/env python3
"""
Build pilot JSON for 'Anjos - Caçadores Alados' (classic Daemon d% system).

Categorisation (per user review):
  - cenarios_lore : intro + história + Recompensas + Apostas + regra de seitas
  - racas         : 6 seitas (custo em pontos + perícias)
  - manobras_combate : combat-style techniques, individual, flat (no style grouping)
  - aprimoramentos: 13 archetypes + Kanaph Zayin
  - poderes       : 9 power trees (blocks per Nível)
  - criaturas_npcs: GOGHIEL, Astrid
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

SOURCE = "anjos-cacadores-alados"
TITLE = "Anjos - Caçadores Alados"
SOURCE_PATH = ROOT / "Livros" / "word" / "Anjos cacadores-alados.docx"
OUT_PATH = ROOT / "data" / "pilot" / f"{SOURCE}.json"
DOCS_OUT_PATH = ROOT / "docs" / "assets" / "data" / "pilot" / f"{SOURCE}.json"


# ------------------------------------------------------------ extraction
def extract_blocks():
    """(level, title, body[]) for Heading 1-4; pure-number headings are noise."""
    doc = Document(SOURCE_PATH)
    blocks = []
    cl, ct, craw = None, None, []

    def push():
        if ct is not None or craw:
            raw = [dehyphenate(normalize(x)) for x in craw if x.strip()]
            blocks.append((cl, ct, join_body(craw), raw))

    for p in doc.paragraphs:
        t = p.text.strip()
        if not t:
            continue
        st = p.style.name if p.style else ""
        if st.startswith("Heading") and st[-1] in "1234":
            if re.fullmatch(r"\d+", t):  # page-number heading
                craw.append(t)
                continue
            push()
            cl, ct, craw = int(st[-1]), normalize(t), []
        else:
            craw.append(t)
    push()
    return blocks


# ------------------------------------------------------------ builders
def sec(id_, title, area, paras):
    return {"id": id_, "title": title, "area": area,
            "paragraphs": [p for p in paras if p and p.strip()]}


def entity(name, area, kind, section_title, paras, subs=None, uid=None):
    return {
        "id": uid or slugify(name), "title": name, "area": area, "kind": kind,
        "sectionId": slugify(section_title), "sectionTitle": section_title,
        "paragraphs": [p for p in paras if p and p.strip()],
        "sections": subs or [],
    }


def build_raca(title, body):
    """Seita -> raça. Pull 'custa N ponto(s)' into a Custo subsection."""
    custo = ""
    for p in body:
        # Cost phrasing varies: "custa 1 ponto...", "gasta-se 2 pontos...",
        # "para se tornar um X, gasta-se N pontos de aprimoramento".
        m = re.search(r"(\d+)\s+pontos?\s+de\s+aprimoramento", p, re.I)
        if m:
            n = m.group(1)
            custo = f"{n} ponto" if n == "1" else f"{n} pontos"
            break
    subs = []
    if custo:
        subs.append(sec("custo", "Custo", "racas", [custo]))
    subs.append(sec("descricao", "Descrição", "racas", body))
    return entity(title, "racas", "race", "Raça", body, subs=subs)


TECH_RE = re.compile(r"^(.+?)\s*\((\+?\d+)\):\s*(.*)$")


def build_manobras(body):
    """Flat individual combat techniques from a style block (no grouping)."""
    out = []
    i = 0
    skip_headers = {"técnicas", "manobras de hikarukendo"}
    current = None
    while i < len(body):
        p = body[i]
        m = TECH_RE.match(p)
        if m and len(m.group(1)) < 45:
            name = m.group(1).strip()
            for hdr in ("Técnicas", "Manobras de Hikarukendo", "HIKARUKENDO,", "HIKARUKENDO"):
                if name.startswith(hdr):
                    name = name[len(hdr):].strip(" ,")
            cost, desc = m.group(2), m.group(3).strip()
            current = {"name": name, "cost": cost, "desc": [desc], "prereq": ""}
            out.append(current)
        elif current is not None:
            if p.lower().startswith("pré-requisito"):
                current["prereq"] = p.split(":", 1)[-1].strip()
            elif p[:1].islower():
                # true continuation of the description (wrapped fragment)
                current["desc"].append(p)
            else:
                # a new heading / style intro / noise: the technique is done
                current = None
        i += 1

    entities = []
    for t in out:
        subs = [sec("custo", "Custo", "manobras_combate", [t["cost"]])]
        if t["prereq"]:
            subs.append(sec("pre-requisito", "Pré-requisito", "manobras_combate", [t["prereq"]]))
        subs.append(sec("descricao", "Descrição", "manobras_combate", t["desc"]))
        entities.append(entity(t["name"], "manobras_combate", "maneuver", "Manobra",
                               t["desc"], subs=subs, uid=slugify("manobra-" + t["name"])))
    return entities


COST_RE = re.compile(r"(-?\d+)\s+pontos?\s*:", re.I)


def build_aprimoramento(title, body):
    """Archetype aprimoramento. Cost (signed) -> Custo subsection + polarity."""
    full = " ".join(body)
    costs = COST_RE.findall(full)
    subs = []
    polarity = "sem-marcacao"
    if costs:
        vals = [int(c) for c in costs]
        if len(set(vals)) == 1:
            custo_paras = [f"{vals[0]} ponto" if abs(vals[0]) == 1 else f"{vals[0]} pontos"]
        else:
            custo_paras = [f"{v} ponto" if abs(v) == 1 else f"{v} pontos" for v in vals]
        subs.append(sec("custo", "Custo", "aprimoramentos", custo_paras))
        if any(v < 0 for v in vals):
            polarity = "negativo"
        elif any(v > 0 for v in vals):
            polarity = "positivo"
    subs.append(sec("descricao", "Descrição", "aprimoramentos", body))
    ent = entity(title, "aprimoramentos", "enhancement", "Aprimoramento", body, subs=subs)
    ent["polarity"] = polarity
    return ent


LEVEL_RE = re.compile(r"(N[íi]vel\s+\d+\s*[:\-])")


def build_poder(title, body):
    """Power tree -> '(Casta)' descriptor block + one block per Nível.

    The app renders each subsection as a titled block; titles 'Nível N: Nome'
    also feed the Nível filter.
    """
    text = "\n".join(body)
    parts = LEVEL_RE.split(text)
    subs = []

    intro = re.sub(r"\s+", " ", parts[0]).strip()
    if intro:
        subs.append(sec("descricao", "Descrição", "poderes", [intro]))

    seen = {}
    i = 1
    while i < len(parts):
        marker = parts[i].strip()
        content = parts[i + 1].strip() if i + 1 < len(parts) else ""
        lvl = re.search(r"\d+", marker).group()
        m = re.match(r"([^.]{1,60}?)\.\s*(.*)", content, re.DOTALL)
        name = m.group(1).strip(" *") if m else ""
        # Treat the pre-period text as an ability NAME only if it is a short
        # noun phrase (not a full sentence like a damage clarification).
        if name and len(name) <= 35 and len(name.split()) <= 5:
            desc = m.group(2).strip() or content
            sectitle = f"Nível {lvl}: {name}"
        else:
            desc = content
            sectitle = f"Nível {lvl}"
        # de-duplicate ids when a level has several abilities
        base = slugify(sectitle)
        seen[base] = seen.get(base, 0) + 1
        sid = base if seen[base] == 1 else f"{base}-{seen[base]}"
        subs.append(sec(sid, sectitle, "poderes", [desc]))
        i += 2

    ent = entity(title, "poderes", "power", "Poder", body, subs=subs)
    return ent


ATTR_KEYS = ["CON", "FR", "DEX", "AGI", "INT", "WILL", "PER", "CAR"]
ATTR_LINE = re.compile(r"\bCON\b\s+\d+")
HAB_PREFIX = ("Principais Poderes", "Poderes:", "Magia:", "Manobras de Combate",
              "-Regenera", "Regenera", "Magia ")


def build_character(title, raw):
    """Parse a stat block into the standard NPC character object.

    renderNpcDetail shows: Atributos (statBlock.attributes+vitals),
    Perícias e Combate (skills+special) and the non-'ficha' sections
    (Habilidades, Descrição)."""
    attr_idx = next((i for i, l in enumerate(raw) if ATTR_LINE.search(l)), None)
    role = " ".join(raw[:attr_idx]).strip() if attr_idx is not None else ""
    body = raw[attr_idx:] if attr_idx is not None else raw
    text = " ".join(body)

    attributes = {}
    for k in ATTR_KEYS:
        m = re.search(rf"\b{k}\b\s+(\d+)", text)
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

    NARRATIVE = re.compile(
        r"\b(foi|era|é|são|tem|possui|tinha|estava|nasceu|viveu|criou|lutou|"
        r"aliada|aliado|responsável|começa|conhecido|conhecida|durante|após)\b")

    def is_narrative(l):
        return len(l) > 60 and bool(NARRATIVE.search(l))

    HAB_TRIGGER = ("-", "Principais Poderes", "Poderes Sephiróticos", "Poderes:", "Magia")
    skills, habilidades, descricao = [], [], []
    phase = "skills"  # skills -> hab -> desc (NPC blocks come in this order)
    for l in body:
        if ATTR_LINE.search(l) or re.match(r"^\s*CAR\b", l) or re.match(r"^#?\s*Ataques", l):
            continue  # folded into statBlock
        if phase == "desc":
            descricao.append(l)
        elif phase == "skills":
            if l.startswith(HAB_TRIGGER):
                phase = "hab"
                habilidades.append(l)
            elif is_narrative(l) and "(" not in l and l.count(",") < 3:
                # prose paragraph (not a parenthetical power/skill list)
                phase = "desc"
                descricao.append(l)
            else:
                skills.append(l)
        else:  # hab
            if l.startswith("-") or not is_narrative(l):
                habilidades.append(l)
            else:
                phase = "desc"
                descricao.append(l)

    sections = [sec("ficha", "Ficha", "criaturas_npcs",
                    [role] + body if role else body)]
    if habilidades:
        sections.append(sec("habilidades", "Habilidades", "criaturas_npcs", habilidades))
    if descricao:
        sections.append(sec("descricao", "Descrição", "criaturas_npcs", descricao))

    return {
        "id": slugify(title),
        "name": title,
        "type": "character_npc",
        "role": role,
        "classifications": [{"area": "criaturas_npcs", "confidence": 1.0,
                             "reason": "Ficha de NPC com atributos Daemon"}],
        "statBlock": {
            "attributes": attributes,
            "vitals": vitals,
            "attributesText": attr_text,
            "skills": "\n".join(skills),
            "special": [],
        },
        "sections": sections,
    }


# ------------------------------------------------------------ assembly
LORE_TITLES = [
    "Manipuladores dos Fachos de Luz", "Primeira Rebelião", "Tempos de Glória",
    "Segunda Rebelião, Gigantomaquia e os Firbolg", "Recompensas",
    "Guerras da Antiguidade", "Apostas", "Christos na Terra", "Guerras Internas",
    "Ameaças Externas", "Mistério do Gólgota, Espiritismo e a Fome de Akalicu",
    "Era de Ouro das Caçadas", "Orgulho  Ophanim", "Praga de Zarcattis",
    "Querelas de Kanaph", "É Possível Participar de Mais de uma Seita?",
]
SEITAS = ["Nyahbinghi", "Chalkydri", "Caçadores Exorcistas", "Algozes de Lilith",
          "Inquisição Celestial", "Meta-anjos"]
APRIMORAMENTOS = [
    "Kanaph Zayin", "Inquisidor Privilegiado", "Marca Furtiva",
    "Caçador do Sobrenatural", "Agente Ceifador", "Ex-Islâmico", "Ex-Cristão",
    "Ex-Judeu", "Máscara de Goghiel", "Aliado das Valkírias",
    "Aliado Firbolg Convertido", "Portal aos Campos de Caça", "Zarcantropo",
    "Centurião Invencível Destituído",
]
PODERES = ["Captare", "Telecinésia", "Calculismo", "Uevarib", "Akuna",
           "Kalkydra", "Exorcismo", "Inquisição", "Combo"]
NPCS = ["GOGHIEL", "Astrid"]
STYLE_BLOCK = "Estilo de Combate: NAFTTULIYM"


def build():
    blocks = extract_blocks()
    bt, braw = {}, {}
    for lvl, title, body, raw in blocks:
        if title:
            bt[title] = body
            braw[title] = raw

    groups, top = [], []

    # LORE
    lore_sections = [sec("apresentacao", "Apresentação", "cenarios_lore",
                         bt.get("Introdução", []))]
    for t in LORE_TITLES:
        if t in bt:
            lore_sections.append(sec(slugify(t), t, "cenarios_lore", bt[t]))
    groups.append({"id": "lore-cacadores", "title": TITLE, "kind": "setting",
                   "area": "cenarios_lore", "sectionTitle": "Cenário",
                   "sections": lore_sections})

    # RACAS (seitas)
    for s in SEITAS:
        if s in bt:
            top.append(build_raca(s, bt[s]))

    # MANOBRAS
    if STYLE_BLOCK in bt:
        top.extend(build_manobras(bt[STYLE_BLOCK]))

    # APRIMORAMENTOS
    for a in APRIMORAMENTOS:
        if a in bt:
            top.append(build_aprimoramento(a, bt[a]))

    # PODERES
    for p in PODERES:
        if p in bt:
            top.append(build_poder(p, bt[p]))

    # NPCS -> characters[] with statBlock (standard NPC structure).
    characters = []
    for n in NPCS:
        if n in braw:
            characters.append(build_character(n, braw[n]))

    area_counts = {g["area"]: 1 for g in groups}
    for s in top:
        area_counts[s["area"]] = area_counts.get(s["area"], 0) + 1
    if characters:
        area_counts["criaturas_npcs"] = area_counts.get("criaturas_npcs", 0) + len(characters)

    return {
        "version": 1, "status": "pilot_review",
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "source": SOURCE, "sourceFile": SOURCE_PATH.name,
        "sourcePath": str(SOURCE_PATH.relative_to(ROOT)), "title": TITLE,
        "summary": "Caçadores Alados: a casta dos anjos caçadores. História, seitas (raças), estilos de combate, aprimoramentos, poderes e NPCs.",
        "areas": sorted(area_counts.keys()),
        "groups": groups, "sections": top, "characters": characters,
        "areaCounts": area_counts,
    }


def main():
    payload = build()
    write_json(OUT_PATH, payload)
    write_json(DOCS_OUT_PATH, payload)
    from collections import Counter
    print(f"Groups: {len(payload['groups'])} (lore {len(payload['groups'][0]['sections'])} sec)")
    print(f"Top-level items: {len(payload['sections'])}")
    for a, n in Counter(s["area"] for s in payload["sections"]).items():
        print(f"  {a}: {n}")
    ids = [s["id"] for s in payload["sections"]]
    dups = [i for i, c in Counter(ids).items() if c > 1]
    print(f"  duplicate ids: {dups}")


if __name__ == "__main__":
    main()
