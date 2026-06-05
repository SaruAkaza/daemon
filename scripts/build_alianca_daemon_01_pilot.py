"""
build_alianca_daemon_01_pilot.py
Piloto para o suplemento/fanzine "Aliança Daemon 01".

Estrutura do documento:
  - Apresentação / Introdução ao Sistema Daemon (lore/cenarios)
  - Resenha capítulo a capítulo do livro "Vampiros Mitológicos" (VM)
    * VAMPIROS MITOLÓGICOS, INTRODUÇÃO, VAMPIRISMO, LEIS VAMPÍRICAS,
      CONCEITOS BÁSICOS, CRIAÇÃO DE PERSONAGENS, RAÇAS (14 raças descritas
      em texto corrido), ATRIBUTOS, APRIMORAMENTOS, PERÍCIAS, EQUIPAMENTOS,
      PODERES VAMPÍRICOS, FRAQUEZAS, SANGUINUS, TIME LINE,
      WONDDERFUL KOPENHAGEN, VAMPIROS NOTÁVEIS, REGRAS E TESTES,
      DESENVOLVENDO A CAMPANHA, ENVELHECIMENTO, SIMULANDO 1D100 COM 3D6,
      ÚLTIMAS CONSIDERAÇÕES
  - Apêndice: raça Ghul (conteúdo novo, com H3 subsections e poderes detalhados)
  - Apêndice: regra alternativa de atributos com 1d10+8 (Pranayama)

Decisões de modelagem:
  - Os capítulos do VM são BLOCOS INTERNOS (coluna direita) de um grupo
    "alianca-resenha-vm" — não são entidades próprias, são uma resenha.
  - A raça Ghul é uma ENTIDADE PRÓPRIA (seção individual area=racas) porque
    tem ficha completa: história, características, organização, poderes, fraquezas.
  - As 14 raças citadas na seção RAÇAS do VM são blocos internos do grupo de
    cenário — descrições curtas sem ficha de jogo.
  - As regras de atributos via 1d10+8 formam uma seção própria em regras_base.
  - O grupo "alianca-cenario-vm" agrega as seções de lore do VM.
  - O grupo "alianca-resenha-vm" agrega as seções de regras/mecânicas do VM.
"""
from __future__ import annotations

import json
import re
import zipfile
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree

from common import ROOT, slugify, write_json


SOURCE_PATH = ROOT / "Livros" / "word" / "feito" / "Aliança Daemon 01.docx"
OUT_PATH = ROOT / "data" / "pilot" / "alianca-daemon-01.json"
DOCS_OUT_PATH = ROOT / "docs" / "assets" / "data" / "pilot" / "alianca-daemon-01.json"
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

# Mapeamento de seções H4 -> área temática
# "none" = descartar (ruído/duplicata)
H4_AREA_MAP: dict[str, str] = {
    "V A M P I R O S": "cenarios_lore",
    "INTRODUÇÃO": "cenarios_lore",
    "VAMPIRISMO": "cenarios_lore",
    "LEIS VAMPIRICAS": "cenarios_lore",
    "CONCEITOS BÁSICOS": "regras_base",
    "CRIAÇÃO DE PERSONAGENS": "regras_base",
    "RAÇAS": "racas",
    "ATRIBUTOS": "regras_base",
    "APRIMORAMENTOS": "aprimoramentos",
    "PERÍCIAS": "regras_base",
    "EQUIPAMENTOS": "itens_equipamentos",
    "PODERES VAMPÍRICOS": "poderes",
    "FRAQUEZAS": "cenarios_lore",
    "SANGUINUS": "regras_base",
    "TIME LINE": "cenarios_lore",
    "WONDDERFUL KOPENHAGEN": "cenarios_lore",
    "VAMPIROS NOTÁVEIS": "criaturas_npcs",
    "REGRAS E TESTES": "regras_base",
    "DESENVOLVENDO A CAMPANHA": "regras_base",
    "ENVELHECIMENTO": "regras_base",
    "SIMULANDO 1D100 COM 3D6": "regras_base",
    "ÚLTIMAS CONSIDERAÇÕES": "cenarios_lore",
}

# Títulos legíveis das seções H4
H4_PRETTY: dict[str, str] = {
    "V A M P I R O S": "Vampiros Mitológicos",
    "INTRODUÇÃO": "Introdução",
    "VAMPIRISMO": "Vampirismo",
    "LEIS VAMPIRICAS": "Leis Vampíricas",
    "CONCEITOS BÁSICOS": "Conceitos Básicos",
    "CRIAÇÃO DE PERSONAGENS": "Criação de Personagens",
    "RAÇAS": "Raças Vampíricas",
    "ATRIBUTOS": "Atributos",
    "APRIMORAMENTOS": "Aprimoramentos",
    "PERÍCIAS": "Perícias",
    "EQUIPAMENTOS": "Equipamentos",
    "PODERES VAMPÍRICOS": "Poderes Vampíricos",
    "FRAQUEZAS": "Fraquezas",
    "SANGUINUS": "Sanguinus",
    "TIME LINE": "Time Line",
    "WONDDERFUL KOPENHAGEN": "Wondderful Kopenhagen",
    "VAMPIROS NOTÁVEIS": "Vampiros Notáveis",
    "REGRAS E TESTES": "Regras e Testes",
    "DESENVOLVENDO A CAMPANHA": "Desenvolvendo a Campanha",
    "ENVELHECIMENTO": "Envelhecimento",
    "SIMULANDO 1D100 COM 3D6": "Simulando 1d100 com 3d6",
    "ÚLTIMAS CONSIDERAÇÕES": "Últimas Considerações",
}

# Seções VM que compõem o grupo de lore/cenário
VM_LORE_SECTIONS = {
    "V A M P I R O S",
    "INTRODUÇÃO",
    "VAMPIRISMO",
    "LEIS VAMPIRICAS",
    "RAÇAS",
    "TIME LINE",
    "WONDDERFUL KOPENHAGEN",
    "VAMPIROS NOTÁVEIS",
    "ÚLTIMAS CONSIDERAÇÕES",
    "FRAQUEZAS",
}

# Seções VM que compõem o grupo de regras/mecânicas
VM_RULES_SECTIONS = {
    "CONCEITOS BÁSICOS",
    "CRIAÇÃO DE PERSONAGENS",
    "ATRIBUTOS",
    "APRIMORAMENTOS",
    "PERÍCIAS",
    "EQUIPAMENTOS",
    "PODERES VAMPÍRICOS",
    "SANGUINUS",
    "REGRAS E TESTES",
    "DESENVOLVENDO A CAMPANHA",
    "ENVELHECIMENTO",
    "SIMULANDO 1D100 COM 3D6",
}

# Subseções H3 da raça Ghul (dentro de ÚLTIMAS CONSIDERAÇÕES)
GHUL_H3_SECTIONS = {
    "Idade Média",
    "Idade Moderna",
    "Características",
    "Organização e Modo de Vida",
    "Principais Áreas de Influência",
    "Relações com outras Raças",
    "Poderes Possíveis",
    "Fraquezas",
    "Cascos",
    "Cânticos Religiosos",
    "Poderes Exclusivos",
    "Controle Mental",
    "Transformação em Névoas",
    "Transformação em Animais",
    "Transformação em Humanos",
    "Sentir Criaturas",
}

DROP_PATTERNS = [
    re.compile(r"^\s*$"),
    re.compile(r"^Aliança Daemon\s*$", re.IGNORECASE),
]


def fix_spaced_letters(text: str) -> str:
    """Collapse OCR-spaced letters: 'A p a r ê n c i a' → 'Aparência'.

    Handles two tricky cases from the source DOCX:
    1. Tab between spaced-word sequences ('Aparência\tHorrenda') — normalized to space.
    2. Accented letter clusters glued to adjacent letter ('ên' as '\xean', 'aH' for
       two words with no separator) — TOKEN allows 1-2 letter chars so these are
       captured, then lowercase→uppercase boundaries reintroduce word spaces.
    """
    # Normalize tabs to spaces first
    text = text.replace('\t', ' ')
    # TOKEN: 1 or 2 letter chars (handles accented clusters like 'ên' stored as '\xean')
    token = r'[A-Za-z\xc0-\xff]{1,2}'
    # Match spaced-letter sequences: (TOKEN space){2+} TOKEN, not adjacent to \w
    pat = rf'(?<!\w)((?:{token} ){{2,}}{token})(?!\w)'

    def _collapse(m: re.Match) -> str:
        collapsed = m.group(0).replace(' ', '')
        # Re-insert word boundary at lowercase→uppercase transitions
        # ('AparênciaHorrenda' → 'Aparência Horrenda')
        collapsed = re.sub(
            r'([a-z\xdf-\xf6\xf8-\xff])([A-Z\xc0-\xde])',
            r'\1 \2',
            collapsed,
        )
        return collapsed

    return re.sub(pat, _collapse, text)


def fix_missing_spaces(text: str) -> str:
    """Insert space before uppercase siglas that got glued: 'queVM' → 'que VM'."""
    # Lowercase char immediately followed by 2+ uppercase chars (a sigla/acronym)
    text = re.sub(r"([a-záàãâéêíóôõúüç])([A-ZÁÀÃÂÉÊÍÓÔÕÚÜÇ]{2,})", r"\1 \2", text)
    return text


def join_hyphen_paragraphs(paras: list[str]) -> list[str]:
    """Join a paragraph that ends with a hyphen to the next one (word was cut).

    'influên-'  +  'cia dos vampiros'  →  'influência dos vampiros'
    Only joins when the next paragraph starts with a lowercase letter (i.e. it
    really is a continuation, not a deliberate dash at end of heading).
    """
    result: list[str] = []
    i = 0
    while i < len(paras):
        current = paras[i].rstrip()
        if current.endswith("-") and i + 1 < len(paras):
            next_para = paras[i + 1].lstrip()
            if next_para and next_para[0].islower():
                # Remove the hyphen and join directly (no space)
                current = current[:-1] + next_para
                i += 2
                result.append(current)
                continue
        result.append(current)
        i += 1
    return result


def join_lowercase_paragraphs(paras: list[str]) -> list[str]:
    """Merge a paragraph that starts with a lowercase letter into the previous one.

    Paragraphs starting with a lowercase letter are continuations of the
    previous paragraph that was split by the OCR/extraction process.
    """
    result: list[str] = []
    for para in paras:
        if not para.strip():
            continue
        if result and para.strip()[0].islower():
            result[-1] = result[-1].rstrip() + " " + para.strip()
        else:
            result.append(para)
    return result


_DANGLING_WORDS = frozenset({
    'ao', 'à', 'a', 'o', 'os', 'as',
    'de', 'do', 'da', 'dos', 'das',
    'em', 'no', 'na', 'nos', 'nas',
    'por', 'para', 'com', 'que', 'se',
    'e', 'ou', 'mas', 'nem', 'pois',
    'pelo', 'pela', 'pelos', 'pelas',
    'um', 'uma', 'uns', 'umas',
    'seu', 'sua', 'seus', 'suas',
})


def join_dangling_prepositions(paras: list[str]) -> list[str]:
    """Join paragraph to previous when previous ends with a dangling word.

    Handles cases like 'Vulnerabilidade ao' + 'Sol, Necrofagia.' where the
    next paragraph starts with an uppercase letter but is clearly a
    continuation (previous line ends with a preposition/article/conjunction).
    """
    result: list[str] = []
    for para in paras:
        stripped = para.strip()
        if not stripped:
            continue
        if result:
            last = result[-1].rstrip()
            last_tokens = last.split()
            last_word = last_tokens[-1].lower().rstrip('.,;:()') if last_tokens else ''
            if last_word in _DANGLING_WORDS:
                result[-1] = last + ' ' + stripped
                continue
        result.append(para)
    return result


def clean_paragraphs(paras: list[str]) -> list[str]:
    """Apply all paragraph-level fixes in the correct order."""
    paras = join_hyphen_paragraphs(paras)
    paras = join_dangling_prepositions(paras)
    paras = join_lowercase_paragraphs(paras)
    return paras


def normalize_text(text: str) -> str:
    """Normaliza whitespace e remove artefatos de OCR comuns."""
    # Normalizar espaços múltiplos e controles
    text = re.sub(r"[ \t]+", " ", text)
    # Juntar hifenização tipográfica de sílabas (qualquer char-letra_minúscula)
    # Padrão: 'caracte-r' → 'caracte r' mas 'atormentan-do' → 'atormentando'
    # O DOCX usa hifenização de sílabas em fim de linha; ao extrair, ficam como 'sílaba-continuação'
    text = re.sub(r"(\w)-(\w)", _dehyphen_replace, text)
    text = text.strip()
    return text


def _dehyphen_replace(match: re.Match) -> str:
    """Remove hifenização tipográfica de sílabas, preservando hifens legítimos."""
    before = match.group(1)
    after = match.group(2)
    # Palavras compostas legítimas geralmente têm letra maiúscula após o hífen
    # ou são expressões conhecidas. Se ambos os lados são minúsculos, é hifenização tipográfica.
    if before[-1].islower() and after[0].islower():
        return f"{before}{after}"
    return f"{before}-{after}"


def normalize_h4_key(raw: str) -> str:
    """Normaliza um heading H4 para comparar com H4_AREA_MAP."""
    cleaned = re.sub(r"\s+", " ", raw).strip().upper()
    # Converter variações tipográficas
    cleaned = cleaned.replace("RAÇAS", "RAÇAS")
    cleaned = cleaned.replace("PERÍCIAS", "PERÍCIAS")
    cleaned = cleaned.replace("CRIAÇÃO DE PERSONAGENS", "CRIAÇÃO DE PERSONAGENS")
    cleaned = cleaned.replace("ÚLTIMAS CONSIDERAÇÕES", "ÚLTIMAS CONSIDERAÇÕES")
    cleaned = cleaned.replace("LEIS VAMPÍRICAS", "LEIS VAMPIRICAS")
    cleaned = cleaned.replace("DESENVOLVENDO A CAMAPANHA", "DESENVOLVENDO A CAMPANHA")
    # Tratar títulos com espaços decorativos
    if re.match(r"^V\s+A\s+M\s+P\s+I\s+R\s+O\s+S", cleaned):
        return "V A M P I R O S"
    if re.match(r"^D\s+E\s+S\s+E\s+N", cleaned):
        return "DESENVOLVENDO A CAMPANHA"
    return cleaned


def normalize_h3_key(raw: str) -> str:
    """Normaliza um heading H3."""
    return re.sub(r"\s+", " ", raw).strip()


def is_noise(text: str) -> bool:
    return any(p.search(text) for p in DROP_PATTERNS)


def raw_paragraphs(path: Path) -> list[tuple[str, str]]:
    """
    Extrai (style_name, text) de todos os parágrafos do DOCX.
    Usa zipfile + ElementTree para acesso direto ao XML, igual ao padrão dos outros pilots.
    """
    with zipfile.ZipFile(path) as archive:
        doc_xml = archive.read("word/document.xml")
        styles_xml = archive.read("word/styles.xml") if "word/styles.xml" in archive.namelist() else b""

    root = ElementTree.fromstring(doc_xml)

    # Mapeamento de style IDs para nomes legíveis via styles.xml
    style_id_to_name: dict[str, str] = {}
    if styles_xml:
        styles_root = ElementTree.fromstring(styles_xml)
        for style_el in styles_root.findall(".//w:style", NS):
            style_id = style_el.get(f"{{{NS['w']}}}styleId", "")
            name_el = style_el.find("w:name", NS)
            if name_el is not None:
                val = name_el.get(f"{{{NS['w']}}}val", "")
                style_id_to_name[style_id] = val

    result: list[tuple[str, str]] = []
    for para in root.findall(".//w:body/w:p", NS):
        ppr = para.find("w:pPr", NS)
        style_id = ""
        if ppr is not None:
            ps = ppr.find("w:pStyle", NS)
            if ps is not None:
                style_id = ps.get(f"{{{NS['w']}}}val", "")
        style_name = style_id_to_name.get(style_id, style_id or "Normal")
        text = "".join(node.text or "" for node in para.findall(".//w:t", NS))
        # fix_spaced_letters must run before normalize_text so we see real words
        text = fix_spaced_letters(text)
        text = normalize_text(text)
        text = fix_missing_spaces(text)
        if text and not is_noise(text):
            result.append((style_name, text))
    return result


def classify_style(style_name: str) -> str:
    """Classifica o estilo em: heading1, heading2, heading3, heading4, body."""
    sn = style_name.lower().replace(" ", "").replace("-", "")
    if sn in ("heading1", "1"):
        return "h1"
    if sn in ("heading2", "2"):
        return "h2"
    if sn in ("heading3", "3"):
        return "h3"
    if sn in ("heading4", "4"):
        return "h4"
    return "body"


def parse_sections(paragraphs: list[tuple[str, str]]) -> dict:
    """
    Percorre os parágrafos e agrupa em seções por heading.
    Retorna dict com:
      - intro: parágrafos antes do primeiro H4
      - h4_sections: list de {key, title, area, body, h3_subsections}
      - pranayama_section: parágrafos após o H2 Pranayama
    """
    intro: list[str] = []
    h4_sections: list[dict] = []
    pranayama_body: list[str] = []

    current_h4_key: str | None = None
    current_h4_raw: str = ""
    current_h4_body: list[str] = []
    current_h3_key: str | None = None
    current_h3_body: list[str] = []
    current_h3_subs: list[dict] = []
    in_pranayama = False

    def flush_h3() -> None:
        nonlocal current_h3_key, current_h3_body
        if current_h3_key and current_h3_body:
            current_h3_subs.append({
                "id": slugify(current_h3_key),
                "title": current_h3_key,
                "paragraphs": clean_paragraphs(list(current_h3_body)),
            })
        current_h3_key = None
        current_h3_body = []

    def flush_h4() -> None:
        nonlocal current_h4_key, current_h4_raw, current_h4_body, current_h3_subs
        flush_h3()
        if current_h4_key is None:
            return
        area = H4_AREA_MAP.get(current_h4_key, "cenarios_lore")
        title = H4_PRETTY.get(current_h4_key, current_h4_raw)
        h4_sections.append({
            "key": current_h4_key,
            "title": title,
            "area": area,
            "body": clean_paragraphs(list(current_h4_body)),
            "h3_subsections": list(current_h3_subs),
        })
        current_h4_key = None
        current_h4_raw = ""
        current_h4_body = []
        current_h3_subs = []

    for style_name, text in paragraphs:
        cls = classify_style(style_name)

        # H2 especial: Pranayama (regra de atributos)
        if cls == "h2" and "pranayama" in text.lower():
            flush_h4()
            in_pranayama = True
            continue

        if in_pranayama:
            pranayama_body.append(text)
            continue

        if cls == "h4":
            flush_h4()
            current_h4_key = normalize_h4_key(text)
            current_h4_raw = text
            current_h3_key = None
            current_h3_body = []
            current_h3_subs = []
            continue

        if cls in ("h1", "h3"):
            # H1 dentro de ÚLTIMAS CONSIDERAÇÕES: "Poderes Exclusivos" → trata como H3
            flush_h3()
            current_h3_key = normalize_h3_key(text)
            current_h3_body = []
            continue

        # Body text
        if current_h4_key is None:
            intro.append(text)
        elif current_h3_key is not None:
            current_h3_body.append(text)
        else:
            current_h4_body.append(text)

    flush_h4()

    return {
        "intro": clean_paragraphs(intro),
        "h4_sections": h4_sections,
        "pranayama_body": clean_paragraphs(pranayama_body),
    }


def build_ghul_race_section(ultimas_consideracoes: dict) -> dict:
    """
    Extrai a raça Ghul da seção ÚLTIMAS CONSIDERAÇÕES (que começa com um
    comentário sobre o VM e depois apresenta o Ghul como raça nova).
    Retorna uma seção individual com as subseções.
    """
    # Corpo da seção ÚLTIMAS CONSIDERAÇÕES: primeiros parágrafos = comentário editorial,
    # depois segue com H3 subsections = conteúdo do Ghul
    intro_body = ultimas_consideracoes.get("body", [])
    h3_subs = ultimas_consideracoes.get("h3_subsections", [])

    # Separar: primeiro parágrafo do corpo é editorial, segundo (com 'Ghul') inicia a raça
    editorial_paras: list[str] = []
    ghul_intro_paras: list[str] = []
    for p in intro_body:
        if "ghul" in p.lower() or "djin" in p.lower() or "árabe" in p.lower() or "cadáver" in p.lower():
            ghul_intro_paras.append(p)
        else:
            editorial_paras.append(p)

    # Subseções H3 originais
    sections: list[dict] = []
    for sub in h3_subs:
        sections.append({
            "id": f"ghul-{sub['id']}",
            "title": sub["title"],
            "paragraphs": sub["paragraphs"],
        })

    return {
        "id": "ghul",
        "title": "Ghul",
        "area": "racas",
        "kind": "race",
        "description": (
            "Raça vampírica de origem árabe, baseada nas lendas dos Ghuls das 1001 Noites. "
            "Possuem capacidade metamórfica e podem caminhar durante o dia, ao contrário de outras raças. "
            "Conteúdo original do fanzine Aliança Daemon 01."
        ),
        "paragraphs": ghul_intro_paras,
        "editorial_notes": editorial_paras,
        "sections": sections,
    }


def build_vm_lore_group(h4_sections: list[dict]) -> dict:
    """
    Agrupa as seções de lore/cenário do VM em um único grupo.
    """
    lore_secs = [s for s in h4_sections if s["key"] in VM_LORE_SECTIONS and s["key"] != "ÚLTIMAS CONSIDERAÇÕES"]
    inner_sections: list[dict] = []
    for s in lore_secs:
        sec: dict = {
            "id": slugify(s["title"]),
            "title": s["title"],
            "area": s["area"],
            "paragraphs": s["body"],
        }
        if s["h3_subsections"]:
            sec["subsections"] = s["h3_subsections"]
        inner_sections.append(sec)

    return {
        "id": "vm-cenario-lore",
        "title": "Vampiros Mitológicos — Cenário",
        "kind": "setting",
        "area": "cenarios_lore",
        "description": (
            "Resenha e síntese das seções de lore do livro Vampiros Mitológicos (VM): "
            "origem histórica dos vampiros, vampirismo, leis vampíricas, timeline de 4000 A.C. a 1980, "
            "14 raças vampíricas descritas e vampiros notáveis da literatura e mitologia."
        ),
        "sections": inner_sections,
    }


def build_vm_rules_group(h4_sections: list[dict]) -> dict:
    """
    Agrupa as seções de regras/mecânicas do VM em um único grupo.
    """
    rules_secs = [s for s in h4_sections if s["key"] in VM_RULES_SECTIONS]
    inner_sections: list[dict] = []
    for s in rules_secs:
        sec: dict = {
            "id": slugify(s["title"]),
            "title": s["title"],
            "area": s["area"],
            "paragraphs": s["body"],
        }
        if s["h3_subsections"]:
            sec["subsections"] = s["h3_subsections"]
        inner_sections.append(sec)

    return {
        "id": "vm-regras-mecanicas",
        "title": "Vampiros Mitológicos — Regras e Mecânicas",
        "kind": "ruleset",
        "area": "regras_base",
        "description": (
            "Resenha e síntese das seções de mecânica do livro Vampiros Mitológicos (VM): "
            "conceitos básicos do Sistema Daemon, criação de personagens vampiro, atributos, "
            "aprimoramentos, perícias, equipamentos, poderes vampíricos, Sanguinus e regras de campanha."
        ),
        "sections": inner_sections,
    }


def build_sistema_daemon_intro(intro: list[str]) -> dict:
    """
    A introdução do documento (antes do primeiro H4) apresenta o Sistema Daemon
    com análise matemática. Torna-se uma seção de lore/regras base.
    """
    return {
        "id": "sistema-daemon-introducao",
        "title": "Sistema Daemon — Introdução e Análise",
        "area": "cenarios_lore",
        "description": (
            "Apresentação do Sistema Daemon com histórico desde 1992, análise matemática "
            "da curva exponencial de atributos e contextualização do livro Vampiros Mitológicos."
        ),
        "paragraphs": intro,
    }


def build_pranayama_section(pranayama_body: list[str]) -> dict:
    """
    A seção de atributos via rolagem 1d10+8 (Pranayama).
    Conteúdo original do fanzine — regra alternativa de geração de atributos.
    """
    return {
        "id": "regra-atributos-1d10",
        "title": "Regra Alternativa: Atributos com 1d10+8",
        "area": "regras_base",
        "description": (
            "Regra original do fanzine Aliança Daemon 01 para geração aleatória de atributos "
            "usando 1d10+8 por atributo, com possibilidade de trocar dois valores ao final. "
            "Inspirada no conceito de Pranayama (controle da energia vital)."
        ),
        "paragraphs": pranayama_body,
    }


def build_rules_base_section(h4_sections: list[dict], pranayama_body: list[str]) -> dict:
    """
    Une a síntese de regras/mecânicas do VM e a regra alternativa original
    em uma única entidade de Regras Base.
    """
    vm_rules = build_vm_rules_group(h4_sections)
    inner_sections = list(vm_rules["sections"])
    if pranayama_body:
        pranayama = build_pranayama_section(pranayama_body)
        inner_sections.append(
            {
                "id": pranayama["id"],
                "title": pranayama["title"],
                "area": "regras_base",
                "paragraphs": pranayama["paragraphs"],
            }
        )

    return {
        "id": "alianca-daemon-01-regras-base",
        "title": "Regra base - Aliança Daemon 01",
        "area": "regras_base",
        "kind": "ruleset",
        "description": (
            "Síntese das regras e mecânicas comentadas no fanzine, unificada com a regra alternativa "
            "de geração de atributos com 1d10+8."
        ),
        "paragraphs": [],
        "sections": inner_sections,
    }


def build_pilot() -> dict:
    paras = raw_paragraphs(SOURCE_PATH)
    parsed = parse_sections(paras)

    intro = parsed["intro"]
    h4_sections = parsed["h4_sections"]
    pranayama_body = parsed["pranayama_body"]

    # Encontrar seção ÚLTIMAS CONSIDERAÇÕES
    ultimas = next((s for s in h4_sections if s["key"] == "ÚLTIMAS CONSIDERAÇÕES"), None)

    # Construir grupos (entidades compostas)
    vm_lore_group = build_vm_lore_group(h4_sections)
    groups = [vm_lore_group]

    # Construir seções individuais (entidades próprias)
    sections: list[dict] = []

    # Seção: introdução ao Sistema Daemon (front matter)
    if intro:
        sections.append(build_sistema_daemon_intro(intro))

    # Seção: raça Ghul (entidade própria com ficha completa)
    if ultimas:
        ghul = build_ghul_race_section(ultimas)
        sections.append(ghul)

    # Seção: regras base unificadas
    sections.append(build_rules_base_section(h4_sections, pranayama_body))

    # Calcular áreas
    area_counts: dict[str, int] = {}
    for g in groups:
        area_counts[g["area"]] = area_counts.get(g["area"], 0) + 1
    for s in sections:
        area_counts[s["area"]] = area_counts.get(s["area"], 0) + 1

    return {
        "version": 1,
        "status": "pilot_review",
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "source": "alianca-daemon-01",
        "sourceFile": SOURCE_PATH.name,
        "sourcePath": str(SOURCE_PATH.relative_to(ROOT)).replace("\\", "/"),
        "title": "Aliança Daemon 01",
        "summary": (
            "Fanzine brasileiro de RPG dedicado ao Sistema Daemon. "
            "Contém análise matemática do sistema, resenha detalhada do livro "
            "Vampiros Mitológicos (VM) com suas 14 raças vampíricas, "
            "conteúdo original da raça Ghul com ficha completa de poderes e fraquezas, "
            "e regra alternativa de geração de atributos com 1d10+8."
        ),
        "areas": sorted(area_counts),
        "groups": groups,
        "sections": sections,
        "areaCounts": area_counts,
        "reviewNotes": [
            "Este piloto trata o documento como um fanzine/suplemento com duas camadas: "
            "resenha do VM (grupos) e conteúdo original (seções individuais).",
            "As 14 raças do VM são descrições em texto corrido na seção RAÇAS — sem fichas de jogo. "
            "Foram agrupadas no grupo vm-cenario-lore, não como entidades individuais.",
            "A raça Ghul é conteúdo original do fanzine, com subseções H3 detalhadas (poderes, fraquezas, etc.), "
            "por isso foi modelada como entidade própria (seção individual area=racas).",
            "A síntese das mecânicas de Vampiros Mitológicos e o bloco Pranayama/1d10+8 foram unificados em um único item de regras_base.",
            "Ainda precisa de revisão humana antes de virar entidade final da base.",
        ],
    }


def main() -> None:
    payload = build_pilot()
    write_json(OUT_PATH, payload)
    write_json(DOCS_OUT_PATH, payload)
    print(json.dumps(
        {
            "source": payload["source"],
            "groups": len(payload["groups"]),
            "sections": len(payload["sections"]),
            "areas": payload["areaCounts"],
        },
        ensure_ascii=False,
    ))


if __name__ == "__main__":
    main()
