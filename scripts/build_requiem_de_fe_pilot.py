#!/usr/bin/env python3
"""
Build pilot JSON for 'Anjos - Réquiem de Fé' (Storytelling-system rebuild).

Uses heading styles (requiem_clean.extract_blocks) for the structural spine and
field anchors for powers (– sub-powers) and magic rituals (Caminhos:/Círculo).
"""
from __future__ import annotations
import re
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent))
from requiem_clean import extract_blocks  # noqa: E402
from common import ROOT, slugify, write_json  # noqa: E402

SOURCE = "anjos-requiem-de-fe"
TITLE = "Anjos - Réquiem de Fé"
SOURCE_PATH = ROOT / "Livros" / "word" / "Anjos - Réquiem de Fé.docx"
OUT_PATH = ROOT / "data" / "pilot" / f"{SOURCE}.json"
DOCS_OUT_PATH = ROOT / "docs" / "assets" / "data" / "pilot" / f"{SOURCE}.json"

CAMINHOS = ["Água", "Animal", "Ar", "Arkanun", "Fogo", "Humanos", "Luz",
            "Metamagia", "Plantas", "Spiritum", "Terra", "Trevas"]
CIRCULOS = {
    "Primeiro Círculo": 1, "Segundo Círculo": 2, "Terceiro Círculo": 3,
    "Quarto Círculo": 4, "Quinto Círculo": 5,
}
CREATURE_NAMES = ["Gárgula", "Sombra"]


# ---------------------------------------------------------------- helpers
def sec(id_, title, area, paras):
    return {"id": id_, "title": title, "area": area,
            "paragraphs": [p for p in paras if p and p.strip()]}


def entity(name, area, kind, section_title, paras, subsections=None):
    return {
        "id": slugify(name), "title": name, "area": area, "kind": kind,
        "sectionId": slugify(section_title), "sectionTitle": section_title,
        "paragraphs": [p for p in paras if p and p.strip()],
        "sections": subsections or [],
    }


# ---------------------------------------------------------------- powers
FIELD_LABELS = ["Custo", "Parada de dados", "Ação", "Falha dramática",
                "Falha", "Êxito"]


def parse_power_fields(text_paras):
    """Split a sub-power's paragraphs into description + labelled fields."""
    joined = "\n".join(text_paras)
    # Insert split points before each known label
    pattern = re.compile(r"(?=(?:%s):)" % "|".join(re.escape(l) for l in FIELD_LABELS))
    parts = [p.strip() for p in pattern.split(joined) if p.strip()]
    desc, subs = [], []
    for part in parts:
        m = re.match(r"(%s):\s*(.*)" % "|".join(re.escape(l) for l in FIELD_LABELS),
                     part, re.DOTALL)
        if m:
            label, val = m.group(1), m.group(2).strip()
            subs.append({"id": slugify(label), "title": label,
                         "area": "poderes", "paragraphs": [val]})
        else:
            desc.append(part)
    return desc, subs


def build_powers(block_body, group_name):
    """One power-group block -> list of individual power entities."""
    # Split into group-intro and sub-powers (lines starting with '–')
    entities = []
    # Find sub-power boundaries
    idxs = [i for i, p in enumerate(block_body) if p.lstrip().startswith("–")]
    if not idxs:
        # Single power == the group itself
        desc, subs = parse_power_fields(block_body)
        entities.append(entity(group_name, "poderes", "power", "Poder", desc,
                               subsections=subs))
        return entities
    for n, start in enumerate(idxs):
        end = idxs[n + 1] if n + 1 < len(idxs) else len(block_body)
        chunk = block_body[start:end]
        name = chunk[0].lstrip("– ").strip()
        desc, subs = parse_power_fields(chunk[1:])
        ent = entity(name, "poderes", "power", "Poder", desc, subsections=subs)
        ent["group"] = group_name
        entities.append(ent)
    return entities


# ---------------------------------------------------------------- rituals & creatures
CREATURE_RE = re.compile(
    r"(Gárgula|Sombra)\s+(Força\s+\d+,.*?Deslocamento:\s*\d+)", re.DOTALL)


def extract_creatures(text):
    """Pull Gárgula/Sombra stat blocks out of the magic text.
    Returns (clean_text, [creature_entities])."""
    creatures = []
    def repl(m):
        name, block = m.group(1), m.group(2)
        ficha = re.sub(r"\s+", " ", block).strip()
        creatures.append(entity(
            name, "criaturas_npcs", "npc", "Ficha", [ficha],
            subsections=[sec("ficha", "Perícias e Combate", "criaturas_npcs", [ficha])]))
        return name + " "  # keep the summon-ritual name, drop the stat block
    clean = CREATURE_RE.sub(repl, text)
    return clean, creatures


def parse_magic(magic_paras):
    """Parse the whole magic chapter -> (path_descriptions, rituals, creatures)."""
    text = re.sub(r"\s+", " ", "\n".join(magic_paras))
    text, creatures = extract_creatures(text)

    atrib = [m.start() for m in re.finditer(r"Atributo:", text)]
    cam_anchor = re.compile(r"Caminhos:\s*(%s)\s*(\d)" %
                            "|".join(map(re.escape, CAMINHOS)))
    circ_markers = list(CIRCULOS.keys())

    def name_before(i):
        start = atrib[i - 1] if i > 0 else 0
        pre = text[start:atrib[i]]
        cut = 0
        for mk in [". ", "! ", "? "] + circ_markers + ["Rituais", "Deformações:", "Efeito:"]:
            p = pre.rfind(mk)
            if p >= 0:
                cut = max(cut, p + len(mk))
        return pre[cut:].strip(" .–-"), start + cut

    # Field grabber within a ritual segment
    def grab(seg, label, nxt):
        pat = r"%s:\s*(.*?)(?=\s*(?:%s):|$)" % (label, "|".join(nxt)) if nxt else r"%s:\s*(.*)$" % label
        m = re.search(pat, seg)
        return m.group(1).strip() if m else ""

    rituals = []
    name_spans = [name_before(i) for i in range(len(atrib))]
    for i, A in enumerate(atrib):
        name = name_spans[i][0]
        # segment of fields = from A to the start of next ritual's name
        seg_end = name_spans[i + 1][1] if i + 1 < len(atrib) else len(text)
        seg = text[A:seg_end]
        m = cam_anchor.search(seg)
        if not m:
            continue
        caminho, circ = m.group(1), int(m.group(2))
        atributo = grab(seg, "Atributo", ["Caminhos", "Custo", "Duração", "Efeito"])
        custo = grab(seg, "Custo", ["Duração", "Efeito"])
        duracao = grab(seg, "Duração", ["Efeito"])
        efeito = grab(seg, "Efeito", [])
        subs = [sec("caminho", "Caminho", "magias", [caminho]),
                sec("circulo", "Círculo", "magias", [str(circ)])]
        if atributo:
            subs.append(sec("atributo", "Atributo", "magias", [atributo]))
        if custo:
            subs.append(sec("custo", "Custo", "magias", [custo]))
        if duracao:
            subs.append(sec("duracao", "Duração", "magias", [duracao]))
        subs.append(sec("efeito", "Efeito", "magias", [efeito or seg]))
        ent = entity(name, "magias", "magia", "Magia", [efeito or seg], subsections=subs)
        ent["id"] = slugify(f"magia-{caminho}-{name}")
        ent["group"] = caminho
        ent["circulo"] = circ
        rituals.append(ent)

    # Path descriptions: text before each path's first ritual, split desc/deformações
    path_descs = {}
    first_idx = {}
    for i, ent in enumerate(rituals):
        cam = ent["group"]
        if cam not in first_idx:
            first_idx[cam] = i
    return path_descs, rituals, creatures


# ---------------------------------------------------------------- build
def build():
    blocks = extract_blocks(SOURCE_PATH)
    bt = {b[1]: (b[0], b[2]) for b in blocks if b[1]}  # title -> (level, body)
    titles_order = [b[1] for b in blocks]

    def block_in_range(title, after_title, before_title):
        """Resolve an ambiguous title to the block between two anchors."""
        try:
            lo = titles_order.index(after_title)
            hi = titles_order.index(before_title)
        except ValueError:
            return bt.get(title, (None, []))[1]
        for i in range(lo, hi):
            if blocks[i][1] == title:
                return blocks[i][2]
        return bt.get(title, (None, []))[1]

    groups, top_sections = [], []

    # -------- LORE (cenarios_lore) --------
    lore_sections = []
    # Cosmogony intro: block 0 + block 2 body minus the version/TOC first paragraph
    intro_paras = list(blocks[0][2])
    versoes_body = blocks[2][2][1:]  # drop "Versão 1.0 ... Sumário ... TOC" blob
    lore_sections.append(sec("apresentacao", "Apresentação", "cenarios_lore",
                             intro_paras + versoes_body))
    LORE_TITLES = ["Arkanun e outras sombras", "O Pacto com os Homens",
                   "Terra Prometida", "Os Reinos de Israel e Judá", "Inferno",
                   "Christos", "Senhor da Luz", "Império Dividido",
                   "O Profeta do Deserto", "A Cruz e a Espada", "Inquisição",
                   "Lutero", "O Novo Mundo", "Mãe África",
                   "O Atual Mundo de Trevas", "A Cidade de Prata", "Luna",
                   "Mercúrio", "Vênus", "Marte", "Júpiter", "Solarium"]
    for t in LORE_TITLES:
        if t in bt:
            lore_sections.append(sec(slugify(t), t, "cenarios_lore", bt[t][1]))
    groups.append({"id": "lore-requiem", "title": TITLE,
                   "kind": "setting", "area": "cenarios_lore",
                   "sectionTitle": "Cenário", "sections": lore_sections})

    # -------- REGRAS BASE --------
    regras_sections = []
    REGRAS_TITLES = ["Almas Humanas nos Céus", "Personalidade", "Castas",
                     "Efeitos da Iluminação", "Fé", "Gastando pontos de Fé",
                     "Recuperando pontos de Fé", "Devoção (Moralidade)", "Queda",
                     "Efeitos da Devoção", "Perdendo Devoção", "Fraquezas",
                     "Resumo de Criação de Personagem", "Escolha uma Virtude",
                     "Escolha um Vício", "Escolha a Casta", "Escolha os Atributos",
                     "Habilidades", "Atributo Favorecido", "Poderes", "Benefícios"]
    for t in REGRAS_TITLES:
        if t in bt:
            regras_sections.append(sec(slugify(t), t, "regras_base", bt[t][1]))
    groups.append({"id": "regras-requiem", "title": f"Regra base - {TITLE}",
                   "kind": "ruleset", "area": "regras_base",
                   "sectionTitle": "Regra Base", "sections": regras_sections})

    # -------- CASTAS (classes) --------
    for casta in ["Captare", "Corpore", "Nimbus", "Protetore", "Recípere"]:
        if casta in bt:
            top_sections.append(entity(casta, "classes", "class", "Casta", bt[casta][1]))

    # -------- COROS (classes) --------
    # "Potência" collides (Coro vs power group); resolve the Coro by region.
    coros = [
        ("Aspicientis", bt.get("Aspicientis", (None, []))[1]),
        ("Caçadores de Recompensas", bt.get("Caçadores de Recompensas", (None, []))[1]),
        ("Indomáveis", bt.get("Indomáveis", (None, []))[1]),
        ("Potestades", block_in_range("Potência", "Indomáveis", "Mysticum")),
        ("Mysticum", bt.get("Mysticum", (None, []))[1]),
    ]
    for display, body in coros:
        if body:
            ent = entity(display, "classes", "class", "Coro", body)
            ent["id"] = slugify("coro-" + display)
            top_sections.append(ent)

    # -------- POWERS (poderes) --------
    POWER_GROUPS = ["Abençoar", "Agilidade", "Asas", "Caçada", "Energia",
                    "Espírito", "Natureza", "Ocultamento", "Passagem",
                    "Pertinácia", "Proteção", "Potência", "Robustez", "Salvaguarda"]
    for g in POWER_GROUPS:
        # "Potência" power group lives after "Proteção"; disambiguate from the Coro.
        body = block_in_range("Potência", "Proteção", "Caminhos") if g == "Potência" else bt.get(g, (None, []))[1]
        if body:
            for ent in build_powers(body, g):
                ent["id"] = slugify(f"poder-{g}-{ent['title']}")
                top_sections.append(ent)

    # -------- MAGIC (rituais) + CREATURES --------
    magic_block = next(b[2] for b in blocks if b[1] == "Parada de Dados")
    _, rituals, creatures = parse_magic(magic_block)
    top_sections.extend(rituals)
    top_sections.extend(creatures)
    creatures_found = [c["title"] for c in creatures]

    area_counts = {}
    for g in groups:
        area_counts[g["area"]] = area_counts.get(g["area"], 0) + 1
    for s in top_sections:
        area_counts[s["area"]] = area_counts.get(s["area"], 0) + 1

    payload = {
        "version": 1, "status": "pilot_review",
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "source": SOURCE, "sourceFile": SOURCE_PATH.name,
        "sourcePath": str(SOURCE_PATH.relative_to(ROOT)), "title": TITLE,
        "summary": "Releitura de Anjos para sistema Storytelling. História/cenário, regras de criação (Fé, Devoção, Iluminação), Castas, Coros, Poderes e Magia (Caminhos e rituais).",
        "areas": sorted(area_counts.keys()),
        "groups": groups, "sections": top_sections, "areaCounts": area_counts,
    }
    return payload, creatures_found


def main():
    payload, creatures = build()
    write_json(OUT_PATH, payload)
    write_json(DOCS_OUT_PATH, payload)
    from collections import Counter
    print(f"Groups: {len(payload['groups'])}  Top-level items: {len(payload['sections'])}")
    by_area = Counter(s["area"] for s in payload["sections"])
    for a, n in by_area.items():
        print(f"  {a}: {n}")
    # power & ritual breakdown
    rituals = [s for s in payload["sections"] if s["area"] == "magias"]
    by_cam = Counter(s.get("group", "?") for s in rituals)
    print("  magias por caminho:", dict(by_cam))
    print("  criaturas detectadas:", creatures)


if __name__ == "__main__":
    main()
