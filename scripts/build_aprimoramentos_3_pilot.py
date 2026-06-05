from __future__ import annotations

import re
from datetime import datetime
from typing import Iterable

from docx import Document

from common import ROOT, slugify, write_json


SOURCE = "aprimoramentos-3"
TITLE = "Aprimoramentos 3"
SOURCE_PATH = ROOT / "Livros" / "word" / "Aprimoramentos_3_OCR_alta_qualidade.docx"
if not SOURCE_PATH.exists():
    SOURCE_PATH = ROOT / "Livros" / "word" / "feito" / "Aprimoramentos_3_OCR_alta_qualidade.docx"
OUT_PATH = ROOT / "data" / "pilot" / f"{SOURCE}.json"
DOCS_OUT_PATH = ROOT / "docs" / "assets" / "data" / "pilot" / f"{SOURCE}.json"

COST_RE = re.compile(r"^([+-]?\d+\+?)\s+pontos?(?:\s+cada|\s+para cada sentido)?\s*[:.]?\s*(.*)$", re.IGNORECASE)
INLINE_COST_RE = re.compile(r"\s([+-]?\d+\+?\s+pontos?(?:\s+cada|\s+para cada sentido)?\s*:)", re.IGNORECASE)
TOPIC_LABEL_RE = re.compile(r"^[A-ZÁÉÍÓÚÂÊÔÃÕÇ][A-Za-zÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç ]{2,42}:\s+")

DROP_EXACT = {
    "Aprimoramentos 3",
    "Texto extraido por OCR/camada de texto e normalizado para leitura em DOCX.",
}

CATEGORY_HEADINGS = {
    "APRIMORAMENTOS",
    "CONCEITUAIS",
    "FISICOS",
    "MENTAIS",
    "MAGICOS",
    "PSIQUICOS",
    "SOCIAIS",
    "SOBRENATURAIS",
    "NEGATIVOS",
}

TEXT_FIXES = {
    "não podem simplesmente serem": "não podem simplesmente ser",
    "faezr": "fazer",
    "caçálos": "caçá-los",
    "exconjurá-lo": "excomungá-lo",
    "à um": "a um",
    "à esse": "a esse",
    "à receber": "a receber",
    "ameaça algum": "ameaça alguma",
    "criticas": "críticas",
    "improvi sação": "improvisação",
    "paRede": "parede",
    "Divida de Gratidão": "Dívida de Gratidão",
    "tem seus próprios problemas": "têm seus próprios problemas",
    "à disposição": "à disposição",
    "secretárias, vereadores": "secretários, vereadores",
    "metade deste valor em": "metade deste valor em",
    "apocaliptico": "apocalíptico",
    "vôo": "voo",
    "espirito": "espírito",
    "magicas": "mágicas",
    "varias vitimas": "várias vítimas",
    "afastálas": "afastá-las",
    "freqüentemente": "frequentemente",
    "conseqüências": "consequências",
    "Eloqüente": "Eloquente",
    "2 Mana à menos": "2 Mana a menos",
    "deferentes": "diferentes",
    "11 ponto: 300": "5 pontos: 300",
    "11 ponto: 30 a 40 soldados": "5 pontos: 30 a 40 soldados",
    "11 ponto: renda de até US$ 32.000 mensais": "5 pontos: renda de até US$ 32.000 mensais",
    "11 ponto: O Mago pode ter Focus 7": "5 pontos: O Mago pode ter Focus 7",
    "custo de 11 ponto (3+1,5 arredondado para cima)": "custo de 5 pontos (3+1,5 arredondado para cima)",
    "12 pontos: 350": "6 pontos: 350",
    "612 pontos": "62 pontos",
    "312 pontos": "36 pontos",
    "COM ou AGI": "CON ou AGI",
    "1ponto": "1 ponto",
}

TITLE_MARKERS = [
    " O Personagem ",
    " o Personagem ",
    " Seu Personagem ",
    " seu Personagem ",
    " Você ",
    " você ",
    " Não importa ",
    " Lembre-se ",
    " Permite ",
    " Todo o ",
    " O mago ",
    " Em termos ",
    " Pontos Heroicos ",
    " Arquimago é ",
    " O personagem ",
    " Para mais ",
    " Escolha ",
    " Apenas ",
]

KNOWN_INLINE_TITLES = [
    "Afinidade com Almas",
    "Afinidade com Fadas",
    "Afinidade com Magia",
    "Ambiente Favorável",
    "Amigo Espírito",
    "Amigo Fantasma",
    "Anjo da Guarda",
    "Armas de Fogo",
    "Arquimago",
    "Biblioteca",
    "Biocinético",
    "Canalizador",
    "Clarividente",
    "Contatos e Aliados",
    "Dependência",
    "Defeito Físico",
    "Dívida de Gratidão",
    "Divida de Gratidão",
    "Familiares",
    "Fama",
    "Forças Militares",
    "Grimório",
    "Heroísmo",
    "Homúnculo",
    "Mago de Combate",
    "Magia Duradoura",
    "Magia Máxima",
    "Magia Sem Gestos",
    "Magia Silenciosa",
    "Mestre em Caminho",
    "Médium",
    "Conjuração",
    "Crânio do Conhecimento",
    "Homúnculo",
    "Pacto",
    "Pactos",
    "Poderes Mágicos",
    "Poderes Sobrenaturais",
    "Portal Natural",
    "Presença Invisível",
    "Recurso e Dinheiro",
    "Resistência à Magia",
    "Sensitivo",
    "Sociedade Secreta",
    "Sortudo",
    "Status",
    "Talento",
    "Telecinético",
    "Telepata",
    "Teleportador",
    "Tiro Certeiro",
    "Tutor",
    "Superpoderes",
    "Poderes Angelicais",
    "Poderes Demoníacos",
    "Poderes Dracônicos",
    "Poderes Feéricos",
]


def strip_accents(value: str) -> str:
    return slugify(value).replace("-", " ").upper()


KNOWN_INLINE_BY_NORMALIZED = {strip_accents(title): title for title in KNOWN_INLINE_TITLES}


def normalize_text(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = text.replace("–", "-")
    text = text.replace("—", "-")
    text = text.replace("“", '"').replace("”", '"')
    for old, new in TEXT_FIXES.items():
        text = text.replace(old, new)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"^([+-]?\d+)\s+ponto\s+o\b", r"\1 ponto: o", text, flags=re.IGNORECASE)
    text = re.sub(r"^([+-]?\d+)\s+pontos?\s*-\s*", r"\1 pontos: ", text, flags=re.IGNORECASE)
    return text.strip()


def should_join(previous: str, current: str) -> bool:
    if not previous or not current:
        return False
    if previous.endswith("-") and current[:1].islower():
        return True
    if current.startswith("-") and re.match(r"^-\d+%", current):
        return True
    if current in {"PM.", "PMs.", "Pontos de Magia."} and not previous.endswith((".", "!", "?", ":", ";", '"')):
        return True
    last_word = previous.split()[-1].lower().strip(".,;:!?")
    if last_word in {"de", "do", "da", "dos", "das", "em", "por", "com", "para", "que", "o", "os", "as", "um", "uma", "no", "na", "e", "seu", "sua", "seus", "suas", "este", "esta", "esse", "essa", "desse", "dessa", "deste", "desta"}:
        return True
    if current[:1].islower() and not previous.endswith((".", "!", "?", ":", ";", '"')):
        return True
    return False


def clean(values: Iterable[str]) -> list[str]:
    paragraphs: list[str] = []
    for raw in values:
        text = normalize_text(raw)
        if not text:
            continue
        if strip_accents(text) in {strip_accents(value) for value in DROP_EXACT}:
            continue
        if re.fullmatch(r"PAGINA \d+", strip_accents(text)):
            continue
        if paragraphs and should_join(paragraphs[-1], text):
            previous = paragraphs.pop()
            if previous.endswith("-") and text[:1].islower():
                paragraphs.append(normalize_text(previous[:-1] + text))
            else:
                paragraphs.append(normalize_text(f"{previous} {text}"))
            continue
        paragraphs.append(text)
    return paragraphs


def docx_paragraphs() -> list[str]:
    return [paragraph.text for paragraph in Document(SOURCE_PATH).paragraphs]


def is_cost(text: str) -> bool:
    return bool(COST_RE.match(text))


def cost_label(text: str) -> str:
    match = COST_RE.match(text)
    if not match:
        return text
    raw_value = match.group(1)
    is_minimum = raw_value.endswith("+")
    numeric_value = raw_value.rstrip("+")
    value = int(numeric_value)
    sign = "+" if raw_value.startswith("+") else ""
    suffix = "+" if is_minimum else ""
    unit = "Ponto" if abs(value) == 1 else "Pontos"
    lower = text.lower()
    if "para cada sentido" in lower:
        return f"{sign}{value}{suffix} {unit} para cada sentido"
    if re.match(r"^[+-]?\d+\s+pontos?\s+cada\b", text, flags=re.IGNORECASE):
        return f"{sign}{value}{suffix} {unit} cada"
    return f"{sign}{value}{suffix} {unit}"


def format_cost_segment(text: str) -> str:
    match = COST_RE.match(text)
    if not match:
        return text
    detail = match.group(2).strip()
    return f"{cost_label(text)}: {detail}".strip()


def is_heading(text: str) -> bool:
    normalized = strip_accents(text)
    if normalized in CATEGORY_HEADINGS:
        return True
    if is_cost(text) or text.endswith((".", ":", ";")):
        return False
    if len(text) > 72:
        return False
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return False
    upper_ratio = sum(1 for char in letters if char.upper() == char) / len(letters)
    if upper_ratio > 0.82:
        return True
    words = text.split()
    if len(words) <= 5 and all(word[:1].isupper() or word.lower() in {"de", "da", "do", "e", "em", "a", "com", "para"} for word in words):
        return True
    return False


def split_title_description(text: str) -> tuple[str, str]:
    normalized_text = strip_accents(text)
    for title in sorted(KNOWN_INLINE_TITLES, key=len, reverse=True):
        prefix = f"{title} "
        if text.startswith(prefix):
            return title, text[len(prefix) :].strip()
        normalized_title = strip_accents(title)
        if normalized_text == normalized_title:
            return title, ""
        if normalized_text.startswith(f"{normalized_title} "):
            words = text.split()
            title_word_count = len(title.split())
            return title, " ".join(words[title_word_count:]).strip()
    for marker in TITLE_MARKERS:
        pos = text.find(marker)
        if pos > 1 and pos <= 44:
            return text[:pos].strip(), text[pos:].strip()
    return text, ""


def split_known_inline_title(text: str) -> tuple[str, str]:
    normalized_text = strip_accents(text)
    for normalized_title, title in sorted(KNOWN_INLINE_BY_NORMALIZED.items(), key=lambda item: len(item[0]), reverse=True):
        if normalized_text == normalized_title:
            return title, ""
        if normalized_text.startswith(f"{normalized_title} "):
            words = text.split()
            title_word_count = len(title.split())
            return title, " ".join(words[title_word_count:]).strip()
    return text, ""


def split_inline_cost(text: str) -> tuple[str, str] | None:
    match = INLINE_COST_RE.search(text)
    if not match:
        return None
    before = text[: match.start()].strip()
    after = text[match.start() :].strip()
    title, description = split_title_description(before)
    if description:
        after = f"{after} {description}"
    return title, after


def section(section_id: str, title: str, area: str, paragraphs: list[str]) -> dict:
    return {"id": section_id, "title": title, "area": area, "paragraphs": paragraphs}


def move_situational_negative_cost_to_description(item: dict) -> dict:
    if item.get("id") != "grimorio":
        return item

    cost_section = next((part for part in item["sections"] if part["id"] == "custo"), None)
    description_section = next((part for part in item["sections"] if part["id"] == "descricao"), None)
    if not cost_section or not description_section:
        return item

    costs = cost_section["paragraphs"]
    situational = [
        cost
        for cost in costs
        if cost.strip().startswith("-")
        and "desvantagem" in strip_accents(cost).lower()
    ]
    if not situational:
        return item

    regular_costs = [cost for cost in costs if cost not in situational]
    description = description_section["paragraphs"]
    cost_section["paragraphs"] = regular_costs
    description_section["paragraphs"] = description + situational
    item["paragraphs"] = regular_costs + description_section["paragraphs"]
    item["polarity"] = "positivo"
    return item


def title_case(title: str) -> str:
    if title.upper() == title:
        title = title.title()
    fixes = {
        "De": "de",
        "Da": "da",
        "Do": "do",
        "Das": "das",
        "Dos": "dos",
        "E": "e",
        "À": "à",
        "A": "a",
        "Em": "em",
    }
    words = [fixes.get(word, word) for word in title.split()]
    if words:
        words[0] = words[0][:1].upper() + words[0][1:]
    return " ".join(words)


def build_enhancement(title: str, raw_parts: list[str], fallback_polarity: str) -> dict | None:
    title = normalize_text(title)
    if not title:
        return None

    if len(raw_parts) == 1 and re.match(r"^Vide\b", raw_parts[0], flags=re.IGNORECASE):
        costs = ["Ver referência"]
        description = raw_parts
        polarity = fallback_polarity
    else:
        intro: list[str] = []
        trailing_description: list[str] = []
        cost_segments: list[list[str]] = []
        current_cost: list[str] | None = None
        for part in raw_parts:
            if is_cost(part):
                current_cost = [part]
                cost_segments.append(current_cost)
                continue
            if trailing_description:
                trailing_description.append(part)
                continue
            if current_cost is not None and len(cost_segments) > 1 and TOPIC_LABEL_RE.match(part):
                current_cost = None
                trailing_description.append(part)
                continue
            if current_cost is not None:
                current_cost.append(part)
            else:
                intro.append(part)

        if not cost_segments:
            return None

        situational_negative_segments: list[list[str]] = []
        regular_cost_segments: list[list[str]] = []
        for segment_parts in cost_segments:
            first = strip_accents(segment_parts[0]).lower()
            segment_text = strip_accents(" ".join(segment_parts)).lower()
            if (
                first.lstrip().startswith("-")
                and len(cost_segments) > 1
                and ("desvantagem" in segment_text or "caso nao possa arcar" in segment_text)
            ):
                situational_negative_segments.append(segment_parts)
            else:
                regular_cost_segments.append(segment_parts)

        if not regular_cost_segments:
            regular_cost_segments = cost_segments
            situational_negative_segments = []

        polarity = (
            "negativo"
            if any(segment[0].lstrip().startswith("-") for segment in regular_cost_segments)
            else "positivo"
        )
        costs: list[str] = []
        description = list(intro)

        if len(regular_cost_segments) == 1:
            first = regular_cost_segments[0][0]
            match = COST_RE.match(first)
            costs = [cost_label(first)]
            detail = match.group(2).strip() if match else ""
            description.extend([text for text in [detail, *regular_cost_segments[0][1:]] if text])
        else:
            for segment_parts in regular_cost_segments:
                first = format_cost_segment(segment_parts[0])
                costs.append(normalize_text(" ".join([first, *segment_parts[1:]])))
            description.extend(trailing_description)

        for segment_parts in situational_negative_segments:
            first = format_cost_segment(segment_parts[0])
            description.append(normalize_text(" ".join([first, *segment_parts[1:]])))

    item = {
        "id": slugify(title),
        "title": title_case(title),
        "area": "aprimoramentos",
        "kind": "enhancement",
        "polarity": polarity,
        "sectionId": "aprimoramento",
        "sectionTitle": "Aprimoramento",
        "paragraphs": costs + description,
        "sections": [
            section("custo", "Custo", "aprimoramentos", costs),
            section("descricao", "Descrição", "aprimoramentos", description),
        ],
    }
    return move_situational_negative_cost_to_description(item)


def parse_content(paragraphs: list[str]) -> tuple[list[dict], list[dict]]:
    content = clean(paragraphs)
    start = next(index for index, text in enumerate(content) if strip_accents(text) == "APRIMORAMENTOS")
    first_item = next(index for index, text in enumerate(content) if text.startswith("Mago de Combate"))

    rules = [
        section("introducao", f"Regra base - {TITLE}", "regras_base", content[start:first_item])
    ]

    items: list[dict] = []
    current_title: str | None = None
    current_parts: list[str] = []
    current_polarity = "positivo"

    def flush() -> None:
        nonlocal current_title, current_parts
        if current_title and current_parts:
            item = build_enhancement(current_title, current_parts, current_polarity)
            if item:
                items.append(item)
        current_title = None
        current_parts = []

    index = first_item
    while index < len(content):
        text = content[index]
        normalized = strip_accents(text)

        if normalized == "NEGATIVOS":
            flush()
            current_polarity = "negativo"
            index += 1
            continue
        if normalized in CATEGORY_HEADINGS:
            index += 1
            continue

        inline = split_inline_cost(text)
        if inline:
            flush()
            current_title, first_cost = inline
            current_parts = [first_cost]
            index += 1
            continue

        if re.match(r"^(.+?)\s+Vide\s+(.+)$", text, flags=re.IGNORECASE):
            flush()
            title, ref = re.match(r"^(.+?)\s+(Vide\s+.+)$", text, flags=re.IGNORECASE).groups()
            current_title = title
            current_parts = [ref]
            flush()
            index += 1
            continue

        if current_title is not None:
            title, description = split_known_inline_title(text)
            if strip_accents(title) in KNOWN_INLINE_BY_NORMALIZED and title_case(title) != title_case(current_title):
                flush()
                current_title = title
                current_parts = [description] if description else []
                index += 1
                continue

        next_text = content[index + 1] if index + 1 < len(content) else ""
        next_next = content[index + 2] if index + 2 < len(content) else ""
        if (
            current_title
            and strip_accents(current_title) == "MESTRE EM CAMINHO"
            and strip_accents(text) == "FOCO EM CAMINHO"
            and is_cost(next_text)
        ):
            current_parts.append(text)
            index += 1
            continue
        if is_heading(text) and (is_cost(next_text) or is_cost(next_next) or not current_title):
            if normalized in CATEGORY_HEADINGS:
                index += 1
                continue
            flush()
            if is_heading(next_text) and is_cost(next_next):
                current_title = normalize_text(f"{text} {next_text}")
                index += 2
                continue
            current_title = text
            index += 1
            continue

        if current_title is None:
            title, description = split_title_description(text)
            if title != text:
                current_title = title
                current_parts = [description] if description else []
            index += 1
            continue

        current_parts.append(text)
        index += 1

    flush()
    deduped: dict[str, dict] = {}
    for item in items:
        key = item["id"]
        if key not in deduped:
            deduped[key] = item
    return list(deduped.values()), rules


def build_pilot() -> dict:
    enhancements, rule_sections = parse_content(docx_paragraphs())
    sections = sorted(enhancements, key=lambda item: item["title"].casefold())
    groups = [
        {
            "id": "regra-base-aprimoramentos-3",
            "title": "Regra base - Aprimoramentos 3",
            "kind": "ruleset",
            "area": "regras_base",
            "sectionTitle": "Regra Base",
            "sections": rule_sections,
        }
    ]
    areas = sorted({group["area"] for group in groups} | {item["area"] for item in sections})
    positive_count = len([item for item in sections if item["polarity"] == "positivo"])
    negative_count = len([item for item in sections if item["polarity"] == "negativo"])
    area_counts = {
        area: len([group for group in groups if group["area"] == area])
        + len([item for item in sections if item["area"] == area])
        for area in areas
    }
    return {
        "version": 1,
        "status": "pilot_review",
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "source": SOURCE,
        "sourceFile": SOURCE_PATH.name,
        "sourcePath": str(SOURCE_PATH.relative_to(ROOT)),
        "title": TITLE,
        "summary": "Compilacao de aprimoramentos conceituais, fisicos, mentais, sociais, sobrenaturais e negativos.",
        "areas": areas,
        "groups": groups,
        "sections": sections,
        "areaCounts": area_counts,
        "reviewNotes": [
            "Livro tratado individualmente apos Aprimoramentos 2.",
            "Texto revisado antes da catalogacao; paginas soltas e cabecalho OCR foram removidos.",
            "Entradas negativas foram separadas a partir da secao Negativos e/ou pelo sinal do custo.",
            "Entradas do tipo Vide Dependencia foram preservadas como referencias, sem inventar custo numerico.",
            f"Total de aprimoramentos catalogados: {len(sections)} ({positive_count} positivos, {negative_count} negativos).",
        ],
    }


def main() -> None:
    payload = build_pilot()
    write_json(OUT_PATH, payload)
    write_json(DOCS_OUT_PATH, payload)
    print(f"Wrote {OUT_PATH.relative_to(ROOT)}")
    print(f"Wrote {DOCS_OUT_PATH.relative_to(ROOT)}")
    print(f"Sections: {len(payload['sections'])}; groups: {len(payload['groups'])}; areas: {payload['areaCounts']}")


if __name__ == "__main__":
    main()
