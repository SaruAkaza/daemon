"""
build_anime_rpg_powers_pilot.py
Piloto para o suplemento "Anime RPG - Powers".

Estrutura do documento (headings DOCX):
  H5 = categorias temáticas (~32 total)
  H6 = itens individuais (~112 total): aprimoramentos, poderes, artefatos

Decisões de modelagem:
  - H6 dentro de "Aprimoramentos Gerais/Conceituais/Raciais"
    → sections individuais (area="aprimoramentos")
  - H6 dentro de "Exemplos de Poderes Sobrenaturais"
    → sections individuais (area="poderes")
  - H6 dentro de "Artefatos Mágicos"
    → sections individuais (area="itens_equipamentos")
  - H6 dentro de "Equipamentos Futuristas"
    → sections individuais (area="itens_equipamentos")
  - H5 de lore/cenário sem H6 (Mundos Místicos, O Futuro!, Academias etc.)
    → groups com sections internas (area="cenarios_lore")
  - H5 de regras sem H6 (Nível de Poder, Supers com Sobrenatural etc.)
    → groups com sections internas (area="regras_base")
  - H5 com H6 de lore (Temas, Eras Heroicas, Idéias para Aventuras etc.)
    → group, com cada H6 como section interna
"""
from __future__ import annotations

import json
import re
import zipfile
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree

from common import ROOT, slugify, write_json


SOURCE_PATH = ROOT / "Livros" / "word" / "feito" / "Anime RPG - Powers.docx"
OUT_PATH = ROOT / "data" / "pilot" / "anime-rpg-powers.json"
DOCS_OUT_PATH = ROOT / "docs" / "assets" / "data" / "pilot" / "anime-rpg-powers.json"
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

# ---------------------------------------------------------------------------
# Mapeamento H5 normalizado → área e tratamento
# ---------------------------------------------------------------------------

# H5 cujos H6 viram sections INDIVIDUAIS (entidades próprias)
H5_INDIVIDUAL_ITEMS: dict[str, str] = {
    "aprimoramentos gerais": "aprimoramentos",
    "aprimoramentos conceituais": "aprimoramentos",
    "aprimoramentos raciais": "racas",
    "exemplos de poderes sobrenaturais": "poderes",
    "artefatos magicos": "itens_equipamentos",
    "equipamentos futuristas": "itens_equipamentos",
}

# H5 cujos H6 ficam INTERNOS ao grupo (lore/cenário/regras)
H5_GROUP_AREA: dict[str, str] = {
    # regras_base
    "eras heroicas": "cenarios_lore",
    "natureza dos superpoderes": "regras_base",
    "nivel de poder (np)": "regras_base",
    "aprimoramentos": "regras_base",
    "supers com sobrenatural?": "regras_base",
    "o preco da magia": "regras_base",
    "magia em supers": "regras_base",
    "regras para aulas": "regras_base",
    "pirataria": "cenarios_lore",
    # cenarios_lore
    "ideias para aventuras": "cenarios_lore",
    "mundos misticos": "cenarios_lore",
    "historia sobrenatural": "cenarios_lore",
    "seres sobrenaturais": "cenarios_lore",
    "temas": "cenarios_lore",
    "o futuro!": "cenarios_lore",
    "transhumanismo": "cenarios_lore",
    "planetas": "cenarios_lore",
    "naves": "cenarios_lore",
    "sistemas de governo galactico": "cenarios_lore",
    "alienigenas": "cenarios_lore",
    "academias de super-herois": "cenarios_lore",
    "materias": "cenarios_lore",
    "panelinhas": "cenarios_lore",
    "professores": "cenarios_lore",
    "punicoes": "cenarios_lore",
    "paqueras e ficas": "cenarios_lore",
}

# Títulos legíveis para H5 (normalização → display)
H5_DISPLAY: dict[str, str] = {
    "eras heroicas": "Eras Heroicas",
    "natureza dos superpoderes": "Natureza dos Superpoderes",
    "nivel de poder (np)": "Nível de Poder (NP)",
    "aprimoramentos": "Aprimoramentos — Introdução",
    "ideias para aventuras": "Idéias para Aventuras",
    "aprimoramentos gerais": "Aprimoramentos Gerais",
    "aprimoramentos conceituais": "Aprimoramentos Conceituais",
    "aprimoramentos raciais": "Aprimoramentos Raciais",
    "supers com sobrenatural?": "Supers com Sobrenatural?",
    "mundos misticos": "Mundos Místicos",
    "historia sobrenatural": "História Sobrenatural",
    "seres sobrenaturais": "Seres Sobrenaturais",
    "o preco da magia": "O Preço da Magia",
    "temas": "Temas",
    "magia em supers": "Magia em SUPERS",
    "artefatos magicos": "Artefatos Mágicos",
    "exemplos de poderes sobrenaturais": "Exemplos de Poderes Sobrenaturais",
    "o futuro!": "O Futuro!",
    "transhumanismo": "Transhumanismo",
    "planetas": "Planetas",
    "naves": "Naves",
    "sistemas de governo galactico": "Sistemas de Governo Galáctico",
    "alienigenas": "Alienígenas",
    "pirataria": "Pirataria",
    "equipamentos futuristas": "Equipamentos Futuristas",
    "academias de super-herois": "Academias de Super-Heróis",
    "regras para aulas": "Regras para Aulas",
    "materias": "Matérias",
    "panelinhas": "Panelinhas",
    "professores": "Professores",
    "punicoes": "Punições",
    "paqueras e ficas": "Paqueras e Ficas",
}

# H5 que geram grupos: id do grupo e kind
H5_GROUP_META: dict[str, dict] = {
    "eras heroicas": {"id": "anime-eras-heroicas", "kind": "setting", "sectionTitle": "Lore"},
    "natureza dos superpoderes": {"id": "anime-natureza-superpoderes", "kind": "ruleset", "sectionTitle": "Regra Base"},
    "nivel de poder (np)": {"id": "anime-nivel-poder", "kind": "ruleset", "sectionTitle": "Regra Base"},
    "aprimoramentos": {"id": "anime-aprimoramentos-intro", "kind": "ruleset", "sectionTitle": "Regra Base"},
    "ideias para aventuras": {"id": "anime-ideias-aventuras", "kind": "setting", "sectionTitle": "Cenário"},
    "supers com sobrenatural?": {"id": "anime-supers-sobrenatural", "kind": "ruleset", "sectionTitle": "Regra Base"},
    "mundos misticos": {"id": "anime-mundos-misticos", "kind": "setting", "sectionTitle": "Cenário"},
    "historia sobrenatural": {"id": "anime-historia-sobrenatural", "kind": "setting", "sectionTitle": "Cenário"},
    "seres sobrenaturais": {"id": "anime-seres-sobrenaturais", "kind": "setting", "sectionTitle": "Cenário"},
    "o preco da magia": {"id": "anime-preco-magia", "kind": "ruleset", "sectionTitle": "Regra Base"},
    "temas": {"id": "anime-temas", "kind": "setting", "sectionTitle": "Cenário"},
    "magia em supers": {"id": "anime-magia-supers", "kind": "ruleset", "sectionTitle": "Regra Base"},
    "o futuro!": {"id": "anime-o-futuro", "kind": "setting", "sectionTitle": "Cenário"},
    "transhumanismo": {"id": "anime-transhumanismo", "kind": "setting", "sectionTitle": "Cenário"},
    "planetas": {"id": "anime-planetas", "kind": "setting", "sectionTitle": "Cenário"},
    "naves": {"id": "anime-naves", "kind": "setting", "sectionTitle": "Cenário"},
    "sistemas de governo galactico": {"id": "anime-gov-galactico", "kind": "setting", "sectionTitle": "Cenário"},
    "alienigenas": {"id": "anime-alienigenas", "kind": "setting", "sectionTitle": "Cenário"},
    "pirataria": {"id": "anime-pirataria", "kind": "setting", "sectionTitle": "Cenário"},
    "academias de super-herois": {"id": "anime-academias", "kind": "setting", "sectionTitle": "Cenário"},
    "regras para aulas": {"id": "anime-regras-aulas", "kind": "ruleset", "sectionTitle": "Regra Base"},
    "materias": {"id": "anime-materias", "kind": "setting", "sectionTitle": "Cenário"},
    "panelinhas": {"id": "anime-panelinhas", "kind": "setting", "sectionTitle": "Cenário"},
    "professores": {"id": "anime-professores", "kind": "setting", "sectionTitle": "Cenário"},
    "punicoes": {"id": "anime-punicoes", "kind": "setting", "sectionTitle": "Cenário"},
    "paqueras e ficas": {"id": "anime-paqueras-ficas", "kind": "setting", "sectionTitle": "Cenário"},
}

DROP_PATTERNS = [
    re.compile(r"^\d+$"),
    re.compile(r"^Anime RPG\s*[-–]?\s*Powers?", re.IGNORECASE),
    re.compile(r"^www\.", re.IGNORECASE),
    re.compile(r"^Este livro é inadequado", re.IGNORECASE),
]

# ---------------------------------------------------------------------------
# Utilitários de limpeza de texto
# (re-implementados do alianca_daemon para este piloto)
# ---------------------------------------------------------------------------

_DANGLING_WORDS = frozenset({
    "ao", "à", "a", "o", "os", "as",
    "de", "do", "da", "dos", "das",
    "em", "no", "na", "nos", "nas",
    "por", "para", "com", "que", "se",
    "e", "ou", "mas", "nem", "pois",
    "pelo", "pela", "pelos", "pelas",
    "um", "uma", "uns", "umas",
    "seu", "sua", "seus", "suas",
})


def fix_spaced_letters(text: str) -> str:
    """Colapsa letras OCR-espaçadas: 'A p a r ê n c i a' → 'Aparência'."""
    text = text.replace("\t", " ")
    token = r"[A-Za-z\xc0-\xff]{1,2}"
    pat = rf"(?<!\w)((?:{token} ){{2,}}{token})(?!\w)"

    def _collapse(m: re.Match) -> str:
        collapsed = m.group(0).replace(" ", "")
        collapsed = re.sub(
            r"([a-z\xdf-\xf6\xf8-\xff])([A-Z\xc0-\xde])",
            r"\1 \2",
            collapsed,
        )
        return collapsed

    return re.sub(pat, _collapse, text)


_OCR_SYLLABLE_FIXES = [
    # Ligadura 'ti' perdida: 'alterna va' → 'alternativa'
    (re.compile(r'\balterna vas\b', re.IGNORECASE), lambda m: 'Alternativas' if m.group(0)[0].isupper() else 'alternativas'),
    (re.compile(r'\balterna va\b', re.IGNORECASE), lambda m: 'Alternativa' if m.group(0)[0].isupper() else 'alternativa'),
    (re.compile(r'\bradioa va\b', re.IGNORECASE), lambda m: 'Radioativa' if m.group(0)[0].isupper() else 'radioativa'),
    (re.compile(r'\btenta va\b', re.IGNORECASE), lambda m: 'Tentativa' if m.group(0)[0].isupper() else 'tentativa'),
    # Sufixos -tica, -tico, -ética etc com ligadura perdida
    (re.compile(r'\bgalác cas\b', re.IGNORECASE), lambda m: 'Galácticas' if m.group(0)[0].isupper() else 'galácticas'),
    (re.compile(r'\bgalác ca\b', re.IGNORECASE), lambda m: 'Galáctica' if m.group(0)[0].isupper() else 'galáctica'),
    (re.compile(r'\bmís co\b', re.IGNORECASE), lambda m: 'Místico' if m.group(0)[0].isupper() else 'místico'),
    (re.compile(r'\bmís ca\b', re.IGNORECASE), lambda m: 'Mística' if m.group(0)[0].isupper() else 'mística'),
    (re.compile(r'\bmís cos\b', re.IGNORECASE), lambda m: 'Místicos' if m.group(0)[0].isupper() else 'místicos'),
    (re.compile(r'\bmís cas\b', re.IGNORECASE), lambda m: 'Místicas' if m.group(0)[0].isupper() else 'místicas'),
    (re.compile(r'\bsin[teé] ca\b|\bsintéca\b', re.IGNORECASE), lambda m: 'Sintética' if m.group(0)[0].isupper() else 'sintética'),
    (re.compile(r'\bdom[eé]s ca\b', re.IGNORECASE), lambda m: 'Doméstica' if m.group(0)[0].isupper() else 'doméstica'),
    (re.compile(r'\btelep[aá] ca\b', re.IGNORECASE), lambda m: 'Telepática' if m.group(0)[0].isupper() else 'telepática'),
    (re.compile(r'\bgené ca\b|\bgen[eé] ca\b', re.IGNORECASE), lambda m: 'Genética' if m.group(0)[0].isupper() else 'genética'),
    (re.compile(r'\bcr[ií] ca\b', re.IGNORECASE), lambda m: 'Crítica' if m.group(0)[0].isupper() else 'crítica'),
    (re.compile(r'\bcelerea na\b', re.IGNORECASE), lambda m: 'Celereana' if m.group(0)[0].isupper() else 'celereana'),
    (re.compile(r'\bsubme da\b', re.IGNORECASE), lambda m: 'Submetida' if m.group(0)[0].isupper() else 'submetida'),
]


def fix_ocr_syllables(text: str) -> str:
    """Fix OCR ligature artifacts where 'ti' was lost, splitting words."""
    for pattern, replacement in _OCR_SYLLABLE_FIXES:
        text = pattern.sub(replacement, text)
    return text


def normalize_text(text: str) -> str:
    """Normaliza whitespace e artefatos tipográficos comuns."""
    text = fix_spaced_letters(text)
    text = re.sub(r"[ \t]+", " ", text)
    # Ligaturas tipográficas que podem aparecer em PDFs/DOCXs
    text = text.replace("ﬁ", "fi")
    text = text.replace("ﬂ", "fl")
    text = text.replace("ﬃ", "ffi")
    text = text.replace("ﬄ", "ffl")
    # OCR artifacts: letras embaralhadas comuns
    text = text.replace("u!l", "util")
    text = text.replace("cien!sta", "cientista")
    text = text.replace("ﬁ", "fi")
    text = text.replace("ﬂ", "fl")
    text = fix_ocr_syllables(text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return text.strip()


def join_hyphen_paragraphs(paras: list[str]) -> list[str]:
    """Une parágrafo que termina com hífen ao próximo (palavra cortada)."""
    result: list[str] = []
    i = 0
    while i < len(paras):
        current = paras[i].rstrip()
        if current.endswith("-") and i + 1 < len(paras):
            next_para = paras[i + 1].lstrip()
            if next_para and next_para[0].islower():
                current = current[:-1] + next_para
                i += 2
                result.append(current)
                continue
        result.append(current)
        i += 1
    return result


def join_lowercase_paragraphs(paras: list[str]) -> list[str]:
    """Merge parágrafos que começam com minúscula no anterior."""
    result: list[str] = []
    for para in paras:
        if not para.strip():
            continue
        if result and para.strip()[0].islower():
            result[-1] = result[-1].rstrip() + " " + para.strip()
        else:
            result.append(para)
    return result


def join_dangling_prepositions(paras: list[str]) -> list[str]:
    """Une parágrafo ao anterior quando o anterior termina com preposição/artigo."""
    result: list[str] = []
    for para in paras:
        stripped = para.strip()
        if not stripped:
            continue
        if result:
            last = result[-1].rstrip()
            last_tokens = last.split()
            last_word = last_tokens[-1].lower().rstrip(".,;:()") if last_tokens else ""
            if last_word in _DANGLING_WORDS:
                result[-1] = last + " " + stripped
                continue
        result.append(para)
    return result


def clean_paragraphs(paras: list[str]) -> list[str]:
    """Aplica todas as correções de parágrafo na ordem correta."""
    paras = join_hyphen_paragraphs(paras)
    paras = join_dangling_prepositions(paras)
    paras = join_lowercase_paragraphs(paras)
    return [p for p in paras if len(p.strip()) > 2]


# ---------------------------------------------------------------------------
# Extração do DOCX via XML
# ---------------------------------------------------------------------------

def _normalize_h5_key(text: str) -> str:
    """Normaliza texto H5 para comparação com mapas de lookup."""
    import unicodedata
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_text = nfkd.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", ascii_text).strip().lower()


def _get_style_name(para: ElementTree.Element, style_id_to_name: dict[str, str]) -> str:
    ppr = para.find("w:pPr", NS)
    if ppr is None:
        return "Normal"
    ps = ppr.find("w:pStyle", NS)
    if ps is None:
        return "Normal"
    style_id = ps.get(f"{{{NS['w']}}}val", "")
    return style_id_to_name.get(style_id, style_id or "Normal")


def _extract_h6_parts(para: ElementTree.Element) -> tuple[str, str | None]:
    """
    Extrai nome e custo de um parágrafo H6 do DOCX.

    O custo é separado do nome por um elemento w:tab dentro de um w:r.
    O w:tab pode estar junto ao texto do custo no mesmo run:
      Caso A: <w:r><w:t>Deflexão</w:t></w:r><w:r><w:tab/><w:t>2</w:t></w:r><w:r> pontos</w:r>
      Caso B: <w:r><w:t>Nuada</w:t></w:r><w:r><w:tab/><w:t>92 </w:t></w:r><w:r>pontos</w:r>

    Quando o run com tab contém texto, esse texto é parte do CUSTO, não do nome.

    Também filtra prefixos numéricos de paginação OCR (ex: "2929Transformação").

    Retorna (nome, custo) onde custo pode ser None.
    """
    W = NS["w"]

    name_parts: list[str] = []
    cost_parts: list[str] = []
    after_tab = False

    for run in para.findall(f"{{{W}}}r"):
        has_tab = run.find(f"{{{W}}}tab") is not None
        run_text = "".join(
            node.text or ""
            for node in run.findall(f".//{{{W}}}t")
        )
        if has_tab:
            # O run com tab marca o início do custo
            # O texto deste run (se houver) é parte do custo
            after_tab = True
            if run_text.strip():
                cost_parts.append(run_text)
        elif after_tab:
            cost_parts.append(run_text)
        else:
            name_parts.append(run_text)

    name = normalize_text("".join(name_parts))
    # Remover prefixos numéricos de paginação OCR: "2929Transformação" → "Transformação"
    name = re.sub(r"^\d{2,}([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ])", r"\1", name).strip()
    # Truncar nomes que têm corpo embutido (autor colou tudo no H6):
    # "Novo Superpoder: Viagem no Tempo Características: NP..." → "Novo Superpoder: Viagem no Tempo"
    # Corta em "Características:", "NP:", ponto final seguido de maiúscula, etc.
    for sep in [r"\s+Caracter[íi]", r"\s+NP:", r"\.\s+[A-Z]"]:
        m = re.search(sep, name)
        if m:
            name = name[:m.start()].rstrip(" :")
            break
    cost = normalize_text("".join(cost_parts)) if cost_parts else None
    if not cost or cost.strip() == "":
        cost = None
    # Normalizar custo: garantir espaço entre número e "pontos"
    if cost:
        cost = re.sub(r"(\d+)\s*(pontos?|ptos?)", r"\1 \2", cost).strip()
    return name, cost


def raw_items(path: Path) -> list[dict]:
    """
    Extrai todos os itens do DOCX como lista de dicts:
      {style: "h5"|"h6"|"body", text: str, cost?: str}
    Para H6, separa nome e custo via w:tab.
    """
    with zipfile.ZipFile(path) as archive:
        doc_xml = archive.read("word/document.xml")
        styles_xml = archive.read("word/styles.xml") if "word/styles.xml" in archive.namelist() else b""

    root = ElementTree.fromstring(doc_xml)

    style_id_to_name: dict[str, str] = {}
    if styles_xml:
        styles_root = ElementTree.fromstring(styles_xml)
        for style_el in styles_root.findall(".//w:style", NS):
            style_id = style_el.get(f"{{{NS['w']}}}styleId", "")
            name_el = style_el.find("w:name", NS)
            if name_el is not None:
                val = name_el.get(f"{{{NS['w']}}}val", "")
                style_id_to_name[style_id] = val

    items: list[dict] = []
    for para in root.findall(".//w:body/w:p", NS):
        style_name = _get_style_name(para, style_id_to_name).lower()

        if "heading 5" in style_name or "heading 3" in style_name or style_name in ("5", "heading5", "3", "heading3"):
            text = normalize_text("".join(node.text or "" for node in para.findall(".//w:t", NS)))
            if not text or any(p.search(text) for p in DROP_PATTERNS):
                continue
            items.append({"style": "h5", "text": text})

        elif "heading 6" in style_name or "heading 4" in style_name or style_name in ("6", "heading6", "4", "heading4"):
            name, cost = _extract_h6_parts(para)
            if not name or any(p.search(name) for p in DROP_PATTERNS):
                continue
            item: dict = {"style": "h6", "text": name}
            if cost:
                item["cost"] = cost
            items.append(item)

        else:
            text = normalize_text("".join(node.text or "" for node in para.findall(".//w:t", NS)))
            if not text or any(p.search(text) for p in DROP_PATTERNS):
                continue
            # Descartar parágrafos que são apenas números (ruído de paginação)
            if re.fullmatch(r"\d+", text):
                continue
            # Remover prefixos numéricos de paginação OCR colados ao início do texto
            # Ex: "55A Era de Ferro" → "A Era de Ferro", "2828Características" → "Características"
            text = re.sub(r"^\d{2,}([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ])", r"\1", text)
            items.append({"style": "body", "text": text})

    return items


# ---------------------------------------------------------------------------
# Construção da estrutura de dados
# ---------------------------------------------------------------------------

def build_sections_and_groups(items: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Processa a lista de items extraídos e retorna:
      - individual_sections: list[dict] — cada aprimoramento/poder/artefato
      - groups: list[dict] — grupos de lore/regras com sections internas
    """
    individual_sections: list[dict] = []
    groups: list[dict] = []

    current_h5_key: str | None = None
    current_h5_raw: str = ""
    current_h6_title: str | None = None
    current_h6_cost: str | None = None
    current_body: list[str] = []
    group_buffer: list[dict] = []  # sections internas do grupo corrente

    def flush_h6() -> None:
        """Finaliza um item H6 e o coloca no destino correto."""
        nonlocal current_h6_title, current_h6_cost, current_body

        if current_h6_title is None:
            # Parágrafos sem H6 → vão para o grupo corrente como seção genérica
            if current_body and current_h5_key in H5_GROUP_AREA:
                group_buffer.append({
                    "id": f"{_h5_slug()}-body",
                    "title": H5_DISPLAY.get(current_h5_key, current_h5_raw),
                    "area": H5_GROUP_AREA[current_h5_key],
                    "paragraphs": clean_paragraphs(list(current_body)),
                })
            current_body = []
            return

        paras = clean_paragraphs(list(current_body))
        # current_h6_title já é o nome limpo (sem custo) — custo vem de current_h6_cost
        h6_name = current_h6_title
        # Truncar o nome para gerar ID razoável (máx 40 chars do nome)
        h6_name_for_id = h6_name[:40].rstrip()
        item_id = slugify(h6_name_for_id)
        # Evitar IDs duplicados adicionando prefixo de categoria
        if current_h5_key:
            item_id = f"anime-{slugify(current_h5_key[:20])}-{item_id}"

        item: dict = {
            "id": item_id,
            "title": h6_name,
            "area": "",  # será preenchido abaixo
            "paragraphs": paras,
        }
        if current_h6_cost:
            item["cost"] = current_h6_cost

        if current_h5_key in H5_INDIVIDUAL_ITEMS:
            item["area"] = H5_INDIVIDUAL_ITEMS[current_h5_key]
            individual_sections.append(item)
        elif current_h5_key in H5_GROUP_AREA:
            item["area"] = H5_GROUP_AREA[current_h5_key]
            group_buffer.append(item)
        else:
            # H5 desconhecido — coloca como section individual com área genérica
            item["area"] = "cenarios_lore"
            individual_sections.append(item)

        # Para aprimoramentos e raças: estruturar Custo e Descrição como sections
        if item["area"] in {"aprimoramentos", "racas"}:
            item_sections: list[dict] = []
            if current_h6_cost:
                item_sections.append({
                    "id": "custo",
                    "title": "Custo",
                    "area": item["area"],
                    "paragraphs": [current_h6_cost],
                })
            if paras:
                item_sections.append({
                    "id": "descricao",
                    "title": "Descrição",
                    "area": item["area"],
                    "paragraphs": paras,
                })
            item["sections"] = item_sections

        current_h6_title = None
        current_h6_cost = None
        current_body = []

    def flush_group() -> None:
        """Finaliza o grupo H5 corrente."""
        nonlocal group_buffer

        if current_h5_key is None:
            return

        flush_h6()

        # Parágrafos de corpo ainda acumulados (sem H6) para H5 de grupo
        if current_body and current_h5_key in H5_GROUP_AREA:
            group_buffer.append({
                "id": f"{_h5_slug()}-intro",
                "title": H5_DISPLAY.get(current_h5_key, current_h5_raw),
                "area": H5_GROUP_AREA[current_h5_key],
                "paragraphs": clean_paragraphs(list(current_body)),
            })

        if current_h5_key in H5_GROUP_AREA and group_buffer:
            meta = H5_GROUP_META.get(current_h5_key, {})
            group: dict = {
                "id": meta.get("id", f"anime-{_h5_slug()}"),
                "title": H5_DISPLAY.get(current_h5_key, current_h5_raw),
                "kind": meta.get("kind", "setting"),
                "area": H5_GROUP_AREA[current_h5_key],
                "sectionTitle": meta.get("sectionTitle", "Cenário"),
                "sections": [s for s in group_buffer if s.get("paragraphs")],
            }
            if group["sections"]:
                groups.append(group)

        group_buffer.clear()

    def _h5_slug() -> str:
        return slugify(current_h5_key or "desconhecido")[:30]

    for item in items:
        style = item["style"]
        text = item["text"]

        if style == "h5":
            flush_group()
            current_h5_raw = text
            current_h5_key = _normalize_h5_key(text)
            current_h6_title = None
            current_h6_cost = None
            current_body = []

        elif style == "h6":
            flush_h6()
            # text já é o nome limpo; cost vem do campo "cost" do item
            current_h6_title = text
            current_h6_cost = item.get("cost")
            current_body = []

        else:  # body
            current_body.append(text)

    # Finalizar último grupo
    flush_group()

    return individual_sections, groups


def merge_groups_by_area(
    groups: list[dict],
    area: str,
    merged_id: str,
    merged_title: str,
    merged_kind: str,
    merged_section_title: str,
) -> list[dict]:
    """Merge all groups of a given area into one single entity in the center column."""
    target_groups = [g for g in groups if g.get("area") == area]
    other_groups = [g for g in groups if g.get("area") != area]

    if len(target_groups) <= 1:
        return groups

    merged_sections: list[dict] = []
    for g in target_groups:
        for sec in g.get("sections", []):
            merged_sections.append(sec)

    merged: dict = {
        "id": merged_id,
        "title": merged_title,
        "kind": merged_kind,
        "area": area,
        "sectionTitle": merged_section_title,
        "sections": merged_sections,
    }
    return other_groups + [merged]


def build_pilot() -> dict:
    items = raw_items(SOURCE_PATH)
    individual_sections, groups = build_sections_and_groups(items)
    groups = merge_groups_by_area(
        groups,
        area="regras_base",
        merged_id="anime-regras-sistema",
        merged_title="Regra base - Anime RPG - Powers",
        merged_kind="ruleset",
        merged_section_title="Regra Base",
    )
    groups = merge_groups_by_area(
        groups,
        area="cenarios_lore",
        merged_id="anime-cenarios-lore",
        merged_title="Cenários e Lore",
        merged_kind="setting",
        merged_section_title="Cenário",
    )

    # Calcular areaCounts
    area_counts: dict[str, int] = {}
    for s in individual_sections:
        area = s.get("area", "desconhecido")
        area_counts[area] = area_counts.get(area, 0) + 1
    for g in groups:
        area = g.get("area", "desconhecido")
        area_counts[area] = area_counts.get(area, 0) + 1

    areas = sorted(area_counts.keys())

    return {
        "version": 1,
        "status": "pilot_review",
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "source": "anime-rpg-powers",
        "sourceFile": SOURCE_PATH.name,
        "sourcePath": str(SOURCE_PATH.relative_to(ROOT)).replace("\\", "/"),
        "title": "Anime RPG - Powers",
        "summary": (
            "Expansão de aprimoramentos e poderes para o Anime RPG (Sistema Daemon). "
            "Contém aprimoramentos gerais, conceituais e raciais; exemplos de poderes sobrenaturais; "
            "artefatos mágicos; equipamentos futuristas; e cenários de super-heróis, sobrenatural e sci-fi, "
            "incluindo regras para campanhas em academias de heróis."
        ),
        "areas": areas,
        "groups": groups,
        "sections": individual_sections,
        "areaCounts": area_counts,
        "reviewNotes": [
            "Cada aprimoramento H6 (Gerais/Conceituais/Raciais) foi modelado como section individual.",
            "Poderes sobrenaturais e artefatos mágicos também são sections individuais.",
            "Grupos de lore/cenário (Mundos Místicos, O Futuro!, Academias etc.) têm sections internas.",
            "Custo dos aprimoramentos/artefatos preservado no campo 'cost' quando disponível.",
            "Ligaduras tipográficas (fi/fl) e artefatos OCR foram normalizados.",
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
