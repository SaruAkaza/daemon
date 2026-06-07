"""Build pilot JSON for 'Daemon Medieval' (core Daemon, medieval-fantasy setting).

Categories (decided with the user, see coordination/books/daemon-medieval.md):
  - racas               (races w/ explicit Custo)                  Cap 4, pg 10-12
  - kits                (professions: Custo/Restrições/Perícias)   Cap 5, pg 13-21
  - aprimoramentos      (advantages/disadvantages, 'N pontos:')    Cap 6, pg 22-31
  - itens_equipamentos  (named gear: 'Nome: descrição')           Cap 8, pg 41-54
  - group 'regras'      (character creation, attributes, magic system, combat)

Magic (Cap 9) is a generative system (Formas × Caminhos), NOT a spell list, so it
is rules (in the group), not a 'magias' category — confirmed by deep reinspection.

OCR is good (6.3% unknown words) but fragmented. We reuse requiem_clean: fix_ocr()
(light, opt-in) + join_body() to rejoin fragments. The page footer is stripped.

Output: data/pilot/daemon-medieval.json  (schema mirrors aprimoramentos-tormenta).
"""
from __future__ import annotations

import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from docx import Document  # noqa: E402
from requiem_clean import fix_ocr, join_body  # noqa: E402

DOCX = ROOT / "Livros" / "word" / "Daemon_Medieval_OCR_alta_qualidade.docx"
OUT = ROOT / "data" / "pilot" / "daemon-medieval.json"
PG = re.compile(r"^Página (\d+)")
FOOTER = "Daemon Medieval"  # repeated page header

# Page ranges per category (inclusive), from the chapter map.
RANGES = {
    "racas": (10, 12),
    "kits": (13, 21),
    "aprimoramentos": (22, 31),
    "itens_equipamentos": (41, 54),
}


# --------------------------------------------------------------------------- #
# Loading / footer removal
# --------------------------------------------------------------------------- #
def load_lines() -> list[tuple[int, str]]:
    doc = Document(str(DOCX))
    cur = 0
    out: list[tuple[int, str]] = []
    for p in doc.paragraphs:
        t = p.text.strip()
        if not t:
            continue
        m = PG.match(t)
        if m:
            cur = int(m.group(1))
            continue
        t = strip_footer(t)
        if t:
            out.append((cur, fix_ocr(t)))
    return out


def strip_footer(text: str) -> str:
    """Remove the repeated page footer, even when concatenated to real text."""
    if FOOTER in text:
        text = text.replace(FOOTER, " ").strip()
    return text


def page_lines(lines, lo, hi) -> list[str]:
    return [t for p, t in lines if lo <= p <= hi]


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "item"


def clean_body(raw: list[str]) -> list[str]:
    """Rejoin fragmented sentences into coherent paragraphs."""
    return join_body(raw)


def make_section(sid, title, area, paragraphs):
    return {"id": sid, "title": title, "area": area, "paragraphs": paragraphs}


# --------------------------------------------------------------------------- #
# RAÇAS  (Nome / Custo: / Idade Inicial: / Atributos: / Vantagens: /
#         Desvantagens: / Idiomas: / descrição)
# --------------------------------------------------------------------------- #
RACE_FIELDS = ["Custo", "Idade Inicial", "Atributos", "Vantagens", "Desvantagens",
               "Idiomas Básicos", "Idiomas"]


# Race names in Daemon Medieval (Cap 4). Closed set — only 6, so a whitelist is
# safer than a heuristic against OCR description fragments.
RACE_NAMES = {"Humanos", "Anões", "Elfos", "Gnomos", "Meio-Elfos", "Halflings"}


def _is_race_name(line: str) -> bool:
    return line.strip() in RACE_NAMES


def parse_racas(lines) -> list[dict]:
    body = page_lines(lines, *RANGES["racas"])
    # Structure: <Name> / description... / 'Custo:' / 'Atributos:' / ...
    # Anchor on 'Custo:' and walk back to the nearest race-name line; the race
    # block starts at that name.
    cost_idx = [i for i, t in enumerate(body) if t.startswith("Custo:")]
    starts = []
    for ci in cost_idx:
        name_idx = None
        for j in range(ci - 1, max(0, ci - 25), -1):
            if _is_race_name(body[j]):
                name_idx = j
                break
        if name_idx is not None and (not starts or name_idx > starts[-1][0]):
            starts.append((name_idx, body[name_idx]))
    sections = []
    for k, (idx, name) in enumerate(starts):
        end = starts[k + 1][0] if k + 1 < len(starts) else len(body)
        block = body[idx + 1:end]
        sections.append(build_race(name, block))
    return sections


# Known languages (Arton). Used to trim 'Idiomas' when OCR dropped the period
# and the description ran on (e.g. Humanos: 'Valkar Os humanos são ...').
_IDIOMAS = {"valkar", "anão", "anao", "élfico", "elfico", "halfling", "orc",
            "comum", "básico", "basico", "draconico", "dracônico"}
_IDIOMA_CONN = {"e", "ou", "de", "do", "da", ","}


def _trim_idiomas(val: str):
    """Return (idiomas, spill_description). Cut right after the language list:
    stop at the first token that is neither a known language nor a connector
    (that token starts the run-on description)."""
    val = val.rstrip()
    tokens = val.split()
    keep = []
    for i, tok in enumerate(tokens):
        bare = tok.strip(",.").lower()
        if bare in _IDIOMAS or bare in _IDIOMA_CONN:
            keep.append(tok)
            if tok.endswith("."):  # explicit terminator ends the list cleanly
                return " ".join(keep).strip(), " ".join(tokens[i + 1:]).strip()
        else:
            # first non-language token -> description begins here
            if keep:
                idiomas = " ".join(keep).rstrip(" ,")
                if not idiomas.endswith("."):
                    idiomas += "."
                return idiomas, " ".join(tokens[i:]).strip()
            break
    return " ".join(keep).strip() or val, ""


def build_race(name: str, block: list[str]) -> dict:
    fields, desc = split_fields(block, RACE_FIELDS, tail_splits_desc=True)
    sub = []
    cost = fields.get("Custo", "").strip()
    if cost:
        sub.append(make_section("custo", "Custo", "racas", [normalize_cost(cost)]))
    for label in ("Idade Inicial", "Atributos", "Vantagens", "Desvantagens",
                  "Idiomas Básicos", "Idiomas"):
        val = fields.get(label, "").strip()
        if val:
            display = "Idiomas" if label.startswith("Idiomas") else label
            if display == "Idiomas":
                val, spill = _trim_idiomas(val)
                if spill:
                    desc.insert(0, spill)
            sub.append(make_section(slugify(display), display, "racas", [val]))
    if desc:
        sub.append(make_section("descricao", "Descrição", "racas", desc))
    return {
        "id": slugify(name), "title": name, "area": "racas", "kind": "race",
        "sectionId": "racas", "sectionTitle": "Raça",
        "paragraphs": desc[:1] if desc else [],
        "sections": sub,
    }


def normalize_cost(cost: str) -> str:
    """'0 pontos' / '1 ponto' -> kept; trim trailing period."""
    return cost.rstrip(". ").strip()


def split_fields(block: list[str], field_labels: list[str], tail_splits_desc: bool = False):
    """Split a block into ({label: value}, [description]).

    Handles labels that appear INLINE (join_body fuses several 'Label: value'
    onto one line, e.g. 'Aprimoramentos: nenhum Perícias: Montaria 20% ...').
    We tokenise the whole joined text on every known label, in order.

    tail_splits_desc: when True (races, which have no 'História:' marker and let
    the narrative follow the last short field directly), the LAST field's value
    is cut at its first sentence terminator and the remainder becomes description.
    """
    joined = clean_body(block)
    text = " ".join(joined)
    # Build a finder for 'Label:' occurrences anywhere in the text.
    label_alt = "|".join(map(re.escape, field_labels))
    finder = re.compile(r"(?:^|\s)(" + label_alt + r")\s*:\s*")
    matches = list(finder.finditer(text))
    fields: dict[str, str] = {}
    desc: list[str] = []
    if not matches:
        return fields, [d for d in joined if d]
    # Anything before the first label is leading description.
    lead = text[: matches[0].start()].strip()
    last_label = None
    for k, m in enumerate(matches):
        label = m.group(1)
        val_start = m.end()
        val_end = matches[k + 1].start() if k + 1 < len(matches) else len(text)
        value = text[val_start:val_end].strip()
        if label in fields:
            fields[label] = (fields[label] + " " + value).strip()
        else:
            fields[label] = value
        last_label = label
    # 'História' content is the descriptive narrative.
    narrative = fields.pop("História", "")
    if lead:
        desc.append(lead)
    if narrative:
        desc.extend(_resplit(narrative))
    # Races: split the trailing narrative off the last short field.
    if tail_splits_desc and last_label and last_label in fields and not narrative:
        val = fields[last_label]
        cut = _first_sentence_cut(val)
        if cut is not None:
            fields[last_label] = val[:cut].strip()
            tail = val[cut:].strip()
            if tail:
                desc.extend(_resplit(tail))
    return fields, [d for d in desc if d]


def _first_sentence_cut(value: str):
    """Index just after the first sentence terminator, if the remainder looks
    like narrative (a following capitalised word). Returns None if no good cut."""
    for m in re.finditer(r"[.!?]\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕ])", value):
        # avoid cutting right after a 1-2 char token (e.g. abbreviations)
        if m.start() >= 2:
            return m.end()
    return None


def _resplit(text: str) -> list[str]:
    """Split a long narrative back into paragraph-sized chunks at sentence ends."""
    parts = re.split(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕ])", text)
    out, buf = [], ""
    for p in parts:
        buf = (buf + " " + p).strip() if buf else p
        if len(buf) > 220:
            out.append(buf)
            buf = ""
    if buf:
        out.append(buf)
    return out


# --------------------------------------------------------------------------- #
# KITS  (Nome / descrição + Características/Religião/Alinhamento / Custo /
#        Restrições / Aprimoramentos / Perícias / Armas e Armaduras / Especial)
# --------------------------------------------------------------------------- #
KIT_FIELDS = [
    "História", "Características", "Religião", "Alinhamento", "Custo",
    "Obrigações e restrições", "Obrigações", "Restrições",
    "Aprimoramentos", "Perícias", "Armas e Armaduras", "Armaduras", "Especial",
    "Aventuras", "Aventura",
]


# Kit names in Daemon Medieval (Cap 5), closed set of 12. Whitelist keeps OCR
# description fragments ('Mesmo', 'Graças') from being mistaken for kit names.
KIT_NAMES = [
    "Bárbaro", "Bardo", "Clérigo", "Druida", "Feiticeiro", "Lutadores",
    "Arqueiros", "Ladrão", "Mago", "Monge", "Paladino", "Ranger",
]


def parse_kits(lines) -> list[dict]:
    """Structure: <Kit Name> / description... / 'Custo:' / 'Restrições:' /
    'Perícias:' / ... Each kit is anchored on its 'Custo:' line; the name is the
    nearest preceding whitelist title. Block = name line up to the next name."""
    body = page_lines(lines, *RANGES["kits"])
    # locate each kit name occurrence that is followed (within the block) by a Custo.
    name_positions = []  # (idx, name)
    for idx, t in enumerate(body):
        nm = _match_kit_name(t)
        if nm:
            # require a 'Custo:' within the next ~30 lines to confirm it's a kit head
            if any(body[j].startswith("Custo:") for j in range(idx + 1, min(idx + 30, len(body)))):
                if not name_positions or name_positions[-1][1] != nm:
                    name_positions.append((idx, nm))
    sections = []
    for k, (idx, name) in enumerate(name_positions):
        end = name_positions[k + 1][0] if k + 1 < len(name_positions) else len(body)
        block = body[idx + 1:end]
        sec = build_kit(name, block)
        if sec:
            sections.append(sec)
    return sections


def _match_kit_name(line: str):
    """Return canonical kit name if the line is exactly a kit title (sing/plural)."""
    s = line.strip()
    for nm in KIT_NAMES:
        if s == nm or s == nm + "s" or (nm.endswith("s") and s == nm[:-1]):
            return nm
    return None


# Manual cost overrides confirmed by the user where OCR dropped the leading
# digit (plural 'pontos' with unknown count). Keyed by kit slug -> leading count.
KIT_COST_OVERRIDE = {
    "invocador-arcano": "1",
    "clerigo-de-marah": "2",
    "clerigo-de-tanna-toh": "2",
}


def _fix_kit_cost(cost: str, slug: str = "") -> str:
    """Repair OCR-dropped leading digit in kit cost.
    'ponto de aprimoramento ...'  -> '1 ponto ...' (singular implies 1).
    'pontos de aprimoramento ...' -> override (user-confirmed) or '[?] ...'."""
    if re.match(r"^ponto\b", cost):
        return "1 " + cost
    if re.match(r"^pontos\b", cost):
        n = KIT_COST_OVERRIDE.get(slug)
        if not n:
            return "[?] " + cost
        if n == "1":  # singular agreement: '1 ponto ...'
            return "1 " + re.sub(r"^pontos\b", "ponto", cost)
        return n + " " + cost
    return cost


def build_kit(name: str, block: list[str]) -> dict | None:
    fields, desc = split_fields(block, KIT_FIELDS)
    if "Custo" not in fields and "Perícias" not in fields:
        return None
    sub = []
    cost = _fix_kit_cost(fields.get("Custo", "").strip(), slugify(name))
    if cost:
        sub.append(make_section("custo", "Custo", "kits", [cost.rstrip(". ")]))
    for label in ("Obrigações e restrições", "Obrigações", "Restrições",
                  "Aprimoramentos", "Perícias", "Armas e Armaduras", "Armaduras",
                  "Especial", "Características", "Religião", "Alinhamento",
                  "Aventuras", "Aventura"):
        val = fields.get(label, "").strip()
        if val:
            sub.append(make_section(slugify(label), label, "kits", [val]))
    if desc:
        sub.append(make_section("descricao", "Descrição", "kits", desc))
    return {
        "id": slugify(name), "title": name, "area": "kits", "kind": "kit",
        "sectionId": "kits", "sectionTitle": "Kit / Profissão",
        "paragraphs": desc[:1] if desc else [],
        "sections": sub,
    }


# --------------------------------------------------------------------------- #
# APRIMORAMENTOS  (Nome / 'N pontos:' or 'Variável:' = custo + descrição)
#
# join_body() fuses the name with the cost+description into one line, e.g.
#   "Arcano 2 pontos: O Personagem possui ..."
#   "Ambiente Favorável O mago se torna ..."  (cost-less / cost elsewhere)
# So we detect an entry by an inline name + cost marker.
# --------------------------------------------------------------------------- #
COST_LINE = re.compile(r"^([+-]?\d+\s*pontos?|Variável|[+-]?\d+\s*ponto)\s*:\s*(.*)$", re.I)
# Name (1-4 Capitalised words) + cost marker, anywhere at line start.
ENTRY_INLINE = re.compile(
    r"^((?:[A-ZÁÉÍÓÚÂÊÔÃÕ][\wáéíóúâêôãõç-]*\.?(?:\s+(?:de|da|do|e|com|à|aos?)\b)?\s*){1,4}?)"
    r"\s+([+-]?\d+\s*pontos?(?:\s+cada)?|Variável)\s*:\s*(.*)$",
    re.I,
)


_ENH_COST = re.compile(r"^([+-]?\d+\s*pontos?(?:\s+cada)?|Variável|Variavel)\s*:\s*", re.I)


def parse_aprimoramentos(lines) -> list[dict]:
    """Work on RAW lines: an entry is a standalone name line, followed either by
    a cost line ('N pontos:') or directly by description (cost is variable/tabled
    and embedded in the text). We collect the description until the next name."""
    raw = page_lines(lines, *RANGES["aprimoramentos"])
    # locate entry-name indices
    idxs = [i for i, t in enumerate(raw) if _is_enh_name(raw, i)]
    entries = []
    for k, i in enumerate(idxs):
        end = idxs[k + 1] if k + 1 < len(idxs) else len(raw)
        name = raw[i].strip()
        rest = raw[i + 1:end]
        cost, desc = _extract_cost(rest)
        entries.append((name, cost, clean_body(desc)))
    return [build_enhancement(n, c, d) for n, c, d in entries]


# Chapter/section headings and known OCR fragments that must not become entities.
_ENH_REJECT = {"Aprimoramentos", "Detestáveis", "Mania", "Ódio"}


def _is_enh_name(raw, i) -> bool:
    t = raw[i].strip()
    if not (3 <= len(t) <= 32) or not t[0].isupper():
        return False
    if t in _ENH_REJECT:
        return False
    if _ENH_COST.match(t) or t.endswith((".", ",", ":", "?", "!", "%", '"')):
        return False
    if re.search(r"\b(é|são|que|para|você|seu|sua|este|esta|pode|deve|jogo|"
                 r"regras|jogador|Personagem|com|dos|das|uma|num|pelo)\b", t):
        return False
    # reject skill-sheet noise like 'Escudo o / 30 Ip 5' (slashes / inline digits)
    if "/" in t or re.search(r"\b(Ip|IP|FR|CON|PV)\b", t) or re.search(r"\d", t):
        return False
    # next line must be a cost line OR a descriptive sentence (len>40)
    nxt = raw[i + 1].strip() if i + 1 < len(raw) else ""
    return bool(_ENH_COST.match(nxt) or len(nxt) > 40)


def _extract_cost(rest: list[str]):
    """Pull the cost from the first line if it's 'N pontos:'; else mark Variável."""
    if rest and _ENH_COST.match(rest[0]):
        m = _ENH_COST.match(rest[0])
        cost = re.sub(r"\s+", " ", m.group(1)).strip()
        head = rest[0][m.end():].strip()
        body = ([head] if head else []) + rest[1:]
        return cost, body
    # cost-less inline: look for an embedded 'N pontos:' to label as variable
    return "Variável", rest


def build_enhancement(name: str, cost: str, desc: list[str]) -> dict:
    cost_norm = re.sub(r"\s+", " ", cost).strip()
    sub = [make_section("custo", "Custo", "aprimoramentos", [cost_norm])]
    if desc:
        sub.append(make_section("descricao", "Descrição", "aprimoramentos", desc))
    return {
        "id": slugify(name), "title": name, "area": "aprimoramentos",
        "kind": "enhancement", "sectionId": "aprimoramentos",
        "sectionTitle": "Aprimoramento",
        "paragraphs": desc[:1] if desc else [],
        "sections": sub,
    }


# --------------------------------------------------------------------------- #
# ITENS / EQUIPAMENTOS  (named descriptions: 'Nome: descrição ...')
#
# Cap 8 has both a price table (fragmented columns) and named gear descriptions
# ('Mochila: ...', 'Píton: ...'). We catalogue the NAMED DESCRIPTIONS as entities;
# the bare price table is left out (too fragmented for clean entities).
# --------------------------------------------------------------------------- #
EQUIP_LINE = re.compile(r"^([A-ZÁÉÍÓÚÂÊÔÃÕ][\wáéíóúâêôãõç ,()\-]{2,38}?):\s+(.+)$")


def parse_equipamentos(lines) -> list[dict]:
    body = page_lines(lines, *RANGES["itens_equipamentos"])
    joined = clean_body(body)
    entries = []  # (name, [desc])
    for para in joined:
        m = EQUIP_LINE.match(para)
        if m and _is_equip_name(m.group(1)):
            entries.append([m.group(1).strip(), [m.group(2).strip()]])
        elif entries and not _looks_like_table_noise(para):
            entries[-1][1].append(para)
    sections = []
    for name, desc in entries:
        sections.append({
            "id": slugify(name), "title": name, "area": "itens_equipamentos",
            "kind": "item", "sectionId": "itens_equipamentos",
            "sectionTitle": "Item / Equipamento",
            "paragraphs": desc[:1] if desc else [],
            "sections": [make_section("descricao", "Descrição", "itens_equipamentos", desc)]
            if desc else [],
        })
    return sections


def _is_equip_name(name: str) -> bool:
    name = name.strip()
    if not (3 <= len(name) <= 38):
        return False
    # reject sentence-like or rules-field leads
    if re.search(r"\b(é|são|que|para|você|seu|sua|pode|deve|Custo|Atributos|"
                 r"Restrições|Perícias|Vantagens|Desvantagens)\b", name):
        return False
    return True


def _looks_like_table_noise(para: str) -> bool:
    """Reject bare price-table fragments (numbers, 'Preço', units)."""
    p = para.strip()
    if re.fullmatch(r"[\d.,]+", p):
        return True
    if p in ("Preço", "Item", "Serviço", "Peso"):
        return True
    return False


# --------------------------------------------------------------------------- #
# GROUP "Regras / Sistema"  (lore: thematic chapters, page-ranged)
#
# Coverage is honest, not exhaustive: we capture coherent, well-OCR'd chapter
# ranges and use short standalone lines as sub-headings. Heavily fragmented or
# example-laden stretches are summarised by range, not transcribed line by line.
# --------------------------------------------------------------------------- #
REGRAS_BLOCKS = [
    ("conceitos-basicos", "Conceitos Básicos", (3, 4)),
    ("criacao-personagem", "Criação de Personagem", (5, 7)),
    ("atributos", "Atributos", (8, 9)),
    ("pericias", "Perícias", (32, 40)),
    ("sistema-de-magia", "Sistema de Magia (Formas e Caminhos)", (55, 59)),
    ("regras-testes-combate", "Regras de Testes e Combate", (60, 74)),
]


def _is_subheading(line: str) -> bool:
    """Short, title-like standalone line that introduces a rules subtopic."""
    if not (4 <= len(line) <= 46) or not line[0].isupper():
        return False
    if line.endswith((".", ",", ";", "%", '"', ":")):
        return False
    # reject sentence-like fragments
    if re.search(r"\b(é|são|que|para|você|seu|sua|com|dos|das|uma|não|pode|deve|"
                 r"este|esta|pelo|como)\b", line):
        return False
    if re.search(r"\d", line) and not line.startswith("Passo"):
        return False
    return True


def build_regras_group(lines) -> dict:
    sub_sections = []
    for sid, title, (lo, hi) in REGRAS_BLOCKS:
        paras = clean_body(page_lines(lines, lo, hi))
        # keep substantial paragraphs; drop tiny noise fragments (< 25 chars)
        # unless they look like a clean sub-heading.
        cleaned = [p for p in paras if len(p) >= 25 or _is_subheading(p)]
        if cleaned:
            sub_sections.append(make_section(sid, title, "regras", cleaned))
    return {
        "id": "regras-daemon-medieval",
        "title": "Regras e Sistema — Daemon Medieval",
        "kind": "ruleset",
        "area": "regras_base",
        "sectionTitle": "Regras",
        "sections": sub_sections,
    }


# --------------------------------------------------------------------------- #
# Assembly
# --------------------------------------------------------------------------- #
def dedupe_ids(sections: list[dict]) -> list[dict]:
    seen: dict[str, int] = {}
    for s in sections:
        base = s["id"]
        if base in seen:
            seen[base] += 1
            s["id"] = f"{base}-{seen[base]}"
        else:
            seen[base] = 0
    return sections


def main() -> None:
    lines = load_lines()

    racas = parse_racas(lines)
    kits = parse_kits(lines)
    aprim = parse_aprimoramentos(lines)
    equip = parse_equipamentos(lines)

    all_sections = dedupe_ids(racas + kits + aprim + equip)
    regras_group = build_regras_group(lines)

    payload = {
        "version": 1,
        "source": "daemon-medieval",
        "title": "Daemon Medieval",
        "sourceFile": "Daemon_Medieval_OCR_alta_qualidade.docx",
        "status": "pilot_review",
        "summary": "Daemon Medieval (fantasia medieval, Sistema Daemon): regras, "
                   "raças, kits/profissões, aprimoramentos e itens/equipamentos.",
        "areas": ["regras_base", "racas", "kits", "aprimoramentos",
                  "itens_equipamentos"],
        "groups": [regras_group],
        "sections": all_sections,
        "counts": {
            "regras_blocos": len(regras_group["sections"]),
            "racas": len(racas),
            "kits": len(kits),
            "aprimoramentos": len(aprim),
            "itens_equipamentos": len(equip),
        },
        "reviewNotes": [
            "OCR bom (6.3% palavras desconhecidas) porém fragmentado; texto unido "
            "via join_body. Conferir descrições longas e campos de kit.",
            "Magia (Cap.9) é sistema gerativo (Formas × Caminhos), sem lista de "
            "feitiços — fica como regras no group, não como categoria 'magias'.",
            "Itens/Equipamentos: catalogadas as descrições nomeadas (Cap.8); a tabela "
            "de preços (colunas fragmentadas) não foi transformada em entidades.",
            "Group de regras: cobertura por blocos temáticos (conceitos, criação, "
            "atributos, perícias, magia, testes/combate). Não é transcrição exaustiva.",
        ],
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
    }

    import json
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)}")
    print("counts:", payload["counts"], "| total sections:", len(all_sections))


if __name__ == "__main__":
    main()
