from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Iterable

from docx import Document

from common import ROOT, slugify, write_json


SOURCE = "aprimoramentos-1"
TITLE = "Aprimoramentos 1"
SOURCE_CANDIDATES = [
    ROOT / "Livros" / "word" / "Aprimoramentos_1_OCR_alta_qualidade.docx",
    ROOT / "Livros" / "word" / "feito" / "Aprimoramentos_1_OCR_alta_qualidade.docx",
]
SOURCE_PATH = next(path for path in SOURCE_CANDIDATES if path.exists())
OUT_PATH = ROOT / "data" / "pilot" / f"{SOURCE}.json"
DOCS_OUT_PATH = ROOT / "docs" / "assets" / "data" / "pilot" / f"{SOURCE}.json"

TITLE_MARKERS = [
    " Apenas ",
    " Não importa ",
    " Possuir ",
    " O personagem ",
    " O Personagem ",
    " Seu Personagem ",
    " Trata-se ",
    " Você ",
    " Através ",
    " Durante ",
    " Em termos ",
    " Lembre-se ",
    " Por algum ",
    " Você foi ",
    " Existe ",
    " Existem ",
    " Funciona ",
    " Quando ",
    " Assim como ",
    " Em determinadas ",
    " Todo o ",
    " É quanto ",
    " Obrigatório ",
    " Como ",
    " Alguém ",
    " Este ",
    " Esta ",
    " É ",
]

KNOWN_INLINE_TITLES = [
    "Ambiente Favorável",
    "Caçador de Demônios ou Anjos",
    "Pontos Heróicos",
    "Recursos e Dinheiro",
    "Sociedade Secreta",
]

TEXT_FIXES = {
    "à desenvolverem": "a desenvolverem",
    "não devem simplesmente serem": "não devem simplesmente ser",
    "PO- DEM": "podem",
    "Conciência": "Consciência",
    "especifico": "específico",
    "criticas": "críticas",
    "seção de jogo": "sessão de jogo",
    "falha critica": "falha crítica",
    "está é voltada": "esta é voltada",
    "possuí": "possui",
    "varias": "várias",
    "loca e cumprir": "local e cumprir",
    "Não Precisar Beber ou Comer": "Não Precisar Beber ou Comer",
    "desejo, gaste seu pontos": "desejo, gaste seus pontos",
    "estrema facilidade": "extrema facilidade",
    "levanto em conta": "levando em conta",
    "convecê-lo": "convencê-lo",
    "língua preza": "língua presa",
    "problemas de dicção": "problema de dicção",
    "descriminado": "discriminado",
    "magicas": "mágicas",
    "intimas": "íntimas",
    "fotograr": "fotografar",
    "crimonosas": "criminosas",
    "espirito": "espírito",
    "destroi": "destrói",
    "cometido, sempre": "cometido, sempre",
    "a policia": "a polícia",
}

DROP_EXACT = {
    "Aprimoramentos",
    "Positivos",
    "Aprimoramentos Positivos",
    "Aprimoramentos Negativos",
    "Texto extraído por OCR/camada de texto e normalizado para leitura em DOCX.",
    "By Anderson “Anúbis” e Lamazuus",
}

COST_RE = re.compile(r"^[+-]?\d+\s+pontos?(?:\s+(?:cada|por|para)\b[^:]*)?\s*:", re.IGNORECASE)
INLINE_COST_RE = re.compile(r"\s([+-]?\d+\s+pontos?(?:\s+(?:cada|por|para)\b[^:]*)?\s*:)", re.IGNORECASE)


def normalize_text(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = text.replace("Š", "-")
    text = text.replace("– ", "-")
    text = text.replace(" - ", " - ")
    text = text.replace("Bio- grafias", "Biografias")
    text = text.replace("colocála", "colocá-la")
    text = text.replace("ajudá lo", "ajudá-lo")
    text = text.replace("protegêlo", "protegê-lo")
    text = text.replace("incomodálo", "incomodá-lo")
    text = text.replace("viceversa", "vice-versa")
    for old, new in TEXT_FIXES.items():
        text = text.replace(old, new)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"^([+-]?\d+)\s+ponto\s+o\b", r"\1 ponto: o", text, flags=re.IGNORECASE)
    text = re.sub(r"([+-]?\d+)\s+Ponto:", r"\1 pontos:", text)
    text = re.sub(r"([+-]?\d+)\s+ponto:", r"\1 ponto:", text)
    return text


def should_join(previous: str, current: str) -> bool:
    if not previous or not current:
        return False
    if previous.endswith("-") and current[:1].islower():
        return True
    last_word = previous.split()[-1].lower().strip(".,;:!?")
    if last_word in {"de", "do", "da", "dos", "das", "em", "por", "com", "para", "e"} or previous.endswith("Bio-"):
        return True
    if current[:1].islower() and not previous.endswith((".", "!", "?", ":", ";", '"')):
        return True
    return False


def clean(values: Iterable[str]) -> list[str]:
    paragraphs: list[str] = []
    for raw in values:
        text = normalize_text(raw)
        if not text or text in DROP_EXACT:
            continue
        if re.fullmatch(r"Página \d+", text):
            continue
        if re.fullmatch(r"\d+\s+\d+", text):
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


def split_inline_cost(text: str) -> tuple[str, str] | None:
    match = INLINE_COST_RE.search(text)
    if not match:
        return None
    title_desc = text[: match.start()].strip()
    cost = text[match.start() :].strip()
    title, description = split_title_description(title_desc)
    merged_cost = f"{cost} {description}".strip() if description else cost
    return title, merged_cost


def split_title_description(text: str) -> tuple[str, str]:
    for title in KNOWN_INLINE_TITLES:
        prefix = f"{title} "
        if text.startswith(prefix):
            return title, text[len(prefix) :].strip()
    for marker in TITLE_MARKERS:
        pos = text.find(marker)
        if pos > 1:
            return text[:pos].strip(), text[pos:].strip()
    return text.strip(), ""


def looks_like_title(text: str, next_text: str | None) -> bool:
    if is_cost(text) or not text[:1].isupper():
        return False
    title, description = split_title_description(text)
    if description and len(title) <= 60:
        return True
    if next_text and is_cost(next_text):
        return True
    if len(text) <= 55 and not text.endswith((".", ",", ";", ":")):
        return True
    return False


def section(section_id: str, title: str, area: str, paragraphs: list[str]) -> dict:
    return {"id": section_id, "title": title, "area": area, "paragraphs": paragraphs}


def build_enhancement(title: str, polarity: str, raw_parts: list[str]) -> dict:
    costs: list[str] = []
    description: list[str] = []
    for part in raw_parts:
        if is_cost(part):
            costs.append(part)
        else:
            description.append(part)

    cost_values: list[str] = []
    if len(costs) == 1:
        match = COST_RE.match(costs[0])
        cost_values = [match.group(0).rstrip(":")] if match else costs
        cost_description = costs[0][match.end() :].strip() if match else ""
        if cost_description:
            description.insert(0, cost_description)
    else:
        cost_values = costs

    sections = [
        section("custo", "Custo", "aprimoramentos", cost_values),
        section("descricao", "Descrição", "aprimoramentos", description),
    ]
    paragraphs = cost_values + description
    return {
        "id": slugify(title),
        "title": title,
        "area": "aprimoramentos",
        "kind": "enhancement",
        "polarity": polarity,
        "sectionId": slugify("Aprimoramento"),
        "sectionTitle": "Aprimoramento",
        "paragraphs": paragraphs,
        "sections": sections,
    }


def parse_enhancements(paragraphs: list[str]) -> list[dict]:
    content = clean(paragraphs)
    start = next(i for i, text in enumerate(content) if text.startswith("Afinidade com Fadas"))
    content = content[start:]

    items: list[dict] = []
    current_title: str | None = None
    current_parts: list[str] = []
    current_polarity = "positivo"

    def flush() -> None:
        nonlocal current_title, current_parts
        if current_title and current_parts:
            items.append(build_enhancement(current_title, current_polarity, current_parts))
        current_title = None
        current_parts = []

    for index, text in enumerate(content):
        inline = split_inline_cost(text)
        next_text = content[index + 1] if index + 1 < len(content) else None
        if inline:
            flush()
            current_title, first_cost = inline
            current_polarity = "negativo" if first_cost.startswith("-") else "positivo"
            current_parts.append(first_cost)
            continue
        if looks_like_title(text, next_text):
            title, description = split_title_description(text)
            if current_title and len(title) > 70 and not description:
                current_parts.append(text)
                continue
            if current_title and not any(is_cost(part) for part in current_parts):
                current_parts.append(text if not description else f"{title} {description}".strip())
                continue
            flush()
            current_title = title
            if description:
                current_parts.append(description)
            continue
        if current_title is None:
            continue
        if is_cost(text) and text.startswith("-"):
            current_polarity = "negativo"
        current_parts.append(text)
    flush()
    return items


def build_pilot() -> dict:
    paragraphs = docx_paragraphs()
    enhancements = parse_enhancements(paragraphs)
    positive_count = len([item for item in enhancements if item["polarity"] == "positivo"])
    negative_count = len([item for item in enhancements if item["polarity"] == "negativo"])

    intro = section(
        "introducao",
        "Regra base - Aprimoramentos 1",
        "regras_base",
        clean(paragraphs[7:12]),
    )
    groups = [
        {
            "id": "regra-base-aprimoramentos-1",
            "title": "Regra base - Aprimoramentos 1",
            "kind": "ruleset",
            "area": "regras_base",
            "sectionTitle": "Regra Base",
            "sections": [intro],
        }
    ]
    sections = sorted(enhancements, key=lambda item: item["title"].casefold())
    areas = sorted({group["area"] for group in groups} | {item["area"] for item in sections})
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
        "summary": "Compilação de aprimoramentos positivos e negativos para personagens, com regra introdutória de uso de pontos de aprimoramento.",
        "areas": areas,
        "groups": groups,
        "sections": sections,
        "areaCounts": area_counts,
        "reviewNotes": [
            "Livro tratado individualmente após Anões.",
            "Texto revisado antes da catalogação; cabeçalhos de página, numeração solta e assinatura foram removidos.",
            "Aprimoramentos com várias opções de custo preservam cada opção de custo junto ao efeito correspondente.",
            "Aprimoramentos com custo único exibem o custo isolado e movem a explicação para Descrição.",
            f"Total de aprimoramentos catalogados: {len(enhancements)} ({positive_count} positivos, {negative_count} negativos).",
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
