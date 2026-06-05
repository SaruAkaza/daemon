from __future__ import annotations

import re
from datetime import datetime
from typing import Iterable

from docx import Document

from common import ROOT, slugify, write_json


SOURCE = "aprimoramentos-4"
TITLE = "Aprimoramentos 4"
SOURCE_CANDIDATES = [
    ROOT / "Livros" / "word" / "Aprimoramentos_4_OCR_alta_qualidade.docx",
    ROOT / "Livros" / "word" / "feito" / "Aprimoramentos_4_OCR_alta_qualidade.docx",
]
SOURCE_PATH = next((path for path in SOURCE_CANDIDATES if path.exists()), SOURCE_CANDIDATES[0])
OUT_PATH = ROOT / "data" / "pilot" / f"{SOURCE}.json"
DOCS_OUT_PATH = ROOT / "docs" / "assets" / "data" / "pilot" / f"{SOURCE}.json"

COST_RE = re.compile(
    r"^([+-]?\d+(?:\s+a\s+\d+)?|\d+)\s+pontos?(?:\s+por\s+n[ií]vel)?\s*[:.\-]?\s*(.*)$",
    re.IGNORECASE,
)
LOOSE_COST_RE = re.compile(r"^[+-]?\d+(?:\s+a\s+\d+)?\s+pontos?\b", re.IGNORECASE)
RANGE_TITLE_RE = re.compile(r"^(.+?)\s*\((\d+\s+a\s+\d+\s+pontos?)\)$", re.IGNORECASE)
INLINE_COST_TITLE_RE = re.compile(r"^(.+?)\s+(\d+\s+pontos?\s+por\s+n[ií]vel)$", re.IGNORECASE)

DROP_EXACT = {
    "Aprimoramentos 4",
    "Texto extraído por OCR/camada de texto e normalizado para leitura em DOCX.",
    "[Sem texto reconhecível nesta página.]",
}

CATEGORY_HEADINGS = {
    "Aprimoramentos Positivos",
    "Aprimoramentos Negativos",
}

TEXT_FIXES = {
    "Pra cada": "Para cada",
    "distancia": "distância",
    "pericia": "perícia",
    "difíceis).": "difíceis).",
    "1 pontos": "1 ponto",
    "2 ponto:": "2 pontos:",
    "vêem": "veem",
    "ítem": "item",
    "bebe": "bebê",
    "bebes": "bebês",
    "É possivel": "É possível",
    "à um": "a um",
    "à uma": "a uma",
    "à um n": "a um n",
    "as Sombras": "às Sombras",
    "Mesclar-se as Sombras": "Mesclar-se às Sombras",
    "dificeis": "difíceis",
    "inicio": "início",
    "elas sempre agem": "ele sempre age",
    "a iniciativa e rolada": "a iniciativa é rolada",
    "Você e mais poderoso": "Você é mais poderoso",
    "E como se": "É como se",
    "o aprim": "o aprim",
    "2 pontos: cada Você": "2 pontos: Você",
    "Sensibilidade a Luz": "Sensibilidade à Luz",
    "Vôo": "Voo",
    "podendo ate ultrapassar": "podendo até ultrapassar",
    "restrição e que": "restrição é que",
    "em uma único Atributo": "em um único Atributo",
    "com a aprimoramento": "com o aprimoramento",
    "saúdes perfeitos": "saúde perfeitas",
    "critico": "crítico",
    "sensível a luz": "sensível à luz",
}

KNOWN_TITLES = {
    "Aceleração",
    "Adaptação",
    "Adaptador",
    "Adiar Magia",
    "Alergia",
    "Ambiente Especial",
    "Ampliar Magia",
    "Armas Naturais",
    "Ataque Especial",
    "Ataque Extra",
    "Atropelar",
    "Caçado",
    "Contra ataque",
    "Contra ataque aprimorado",
    "Corpo Flexível",
    "Dano Maciço",
    "Deslocamento Especial",
    "Deslocamento em velocidade",
    "Deslocamento em velocidade Aprimorado",
    "Dominado",
    "Elasticidade",
    "Empatia com Animais",
    "Energia Extra",
    "Expert",
    "Feitiçaria",
    "Foco em Caminho",
    "Forma Alternativa",
    "Fracote",
    "Gênio",
    "Hábil",
    "Ignorar componente",
    "Imortalidade Química",
    "Imunidade",
    "Inábil",
    "Iniciativa",
    "Invisibilidade",
    "Invocação Aprimorada",
    "Item Pessoal",
    "Ligação Natural",
    "Maestria em Caminho",
    "Magia Cooperativa",
    "Magia Sequencial",
    "Marcado a Ferro",
    "Memória Expandida",
    "Mente Repartilhada",
    "Mesclar-se às Sombras",
    "Paralisia",
    "Pele Metálica",
    "Poder Elevado",
    "Poder Oculto",
    "Ponto Fraco",
    "Pontos de Vida Extras",
    "Presença Invisível",
    "Reflexão",
    "Regeneração",
    "Resistência",
    "Ritualismo",
    "Saque rápido",
    "Saúde de Rato",
    "Sensibilidade a Luz",
    "Sensibilidade à Luz",
    "Sentido de Perigo",
    "Supremacia em Caminho",
    "Tamanho Especial",
    "Telepatia",
    "Teletransporte",
    "Vidas Gastas",
    "Vírus",
    "Vôo",
    "Vulnerabilidade",
}

SPECIAL_COSTS = {
    "Adaptação": "Variável",
    "Armas Naturais": "1 a 2 Pontos",
    "Ataque Especial": "1 Ponto por 1d6",
    "Deslocamento Especial": "Variável",
    "Hábil": "Variável",
}


def normalize_text(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = text.replace("“", '"').replace("”", '"')
    text = text.replace("–", "-").replace("—", "-")
    text = re.sub(r"^\-\s+(\d+\s+pontos?)", r"-\1", text, flags=re.IGNORECASE)
    for old, new in TEXT_FIXES.items():
        text = text.replace(old, new)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"^([+-]?\d+(?:\s+a\s+\d+)?)\s+pontos?\.\s+", r"\1 pontos: ", text, flags=re.IGNORECASE)
    text = re.sub(r"^([+-]?\d+)\s+ponto:\s+", r"\1 ponto: ", text, flags=re.IGNORECASE)
    text = re.sub(r"^([+-]?\d+)\s+pontos:\s+", r"\1 pontos: ", text, flags=re.IGNORECASE)
    return text


def is_page_noise(text: str) -> bool:
    return bool(re.fullmatch(r"Página \d+", text, flags=re.IGNORECASE))


def should_join(previous: str, current: str) -> bool:
    if not previous or not current:
        return False
    if current.startswith("("):
        return True
    if previous.endswith(("D$", "(1", "3")) and current[:1].islower() or current[:1].isdigit():
        return True
    if current in {"Ponto)", "Pontos de Magia;", "Pontos de Magia."}:
        return True
    last_word = previous.split()[-1].lower().strip(".,;:!?")
    if last_word in {"de", "do", "da", "dos", "das", "em", "por", "com", "para", "que", "o", "os", "as", "um", "uma", "no", "na", "e", "ou", "se", "ao", "à"}:
        return True
    if current[:1].islower() and not previous.endswith((".", "!", "?", ":", ";", ")")):
        return True
    return False


def starts_structured_line(text: str) -> bool:
    if text == "Variável" or LOOSE_COST_RE.match(text):
        return True
    if text in CATEGORY_HEADINGS or text in KNOWN_TITLES:
        return True
    if RANGE_TITLE_RE.match(text) or INLINE_COST_TITLE_RE.match(text):
        return True
    return split_known_inline_cost(text) is not None


def clean(values: Iterable[str]) -> list[str]:
    paragraphs: list[str] = []
    for raw in values:
        text = normalize_text(raw)
        if not text or text in DROP_EXACT or is_page_noise(text):
            continue
        if text.startswith("Poder Elevado Por um motivo"):
            paragraphs.append("Poder Elevado")
            paragraphs.append(normalize_text(text.removeprefix("Poder Elevado ")))
            continue
        if paragraphs and not starts_structured_line(text) and should_join(paragraphs[-1], text):
            previous = paragraphs.pop()
            paragraphs.append(normalize_text(f"{previous} {text}"))
            continue
        paragraphs.append(text)
    return paragraphs


def docx_paragraphs() -> list[str]:
    return [paragraph.text for paragraph in Document(SOURCE_PATH).paragraphs]


def section(section_id: str, title: str, area: str, paragraphs: list[str]) -> dict:
    return {"id": section_id, "title": title, "area": area, "paragraphs": paragraphs}


def title_case(title: str) -> str:
    fixes = {"De": "de", "Da": "da", "Do": "do", "Das": "das", "Dos": "dos", "E": "e", "A": "a", "Em": "em"}
    if title.upper() == title:
        title = title.title()
    words = [fixes.get(word, word) for word in title.split()]
    if words:
        words[0] = words[0][:1].upper() + words[0][1:]
    return " ".join(words)


def is_cost(text: str) -> bool:
    return text == "Variável" or bool(COST_RE.match(text))


def cost_label(text: str) -> str:
    if text == "Variável":
        return text
    match = COST_RE.match(text)
    if not match:
        return text
    raw = re.sub(r"\s+", " ", match.group(1).strip())
    suffix = " por nível" if re.search(r"por\s+n[ií]vel", text, flags=re.IGNORECASE) else ""
    if " a " in raw:
        return f"{raw} Pontos{suffix}"
    value = int(raw)
    unit = "Ponto" if abs(value) == 1 else "Pontos"
    return f"{value} {unit}{suffix}"


def format_cost(text: str) -> tuple[str, str]:
    if text == "Variável":
        return text, ""
    match = COST_RE.match(text)
    if not match:
        return text, ""
    return cost_label(text), match.group(2).strip()


def is_heading(text: str) -> bool:
    if text in CATEGORY_HEADINGS:
        return True
    if text == "Variável":
        return False
    if text in KNOWN_TITLES:
        return True
    if RANGE_TITLE_RE.match(text) or INLINE_COST_TITLE_RE.match(text):
        return True
    if ":" in text or is_cost(text) or len(text) > 58:
        return False
    words = text.split()
    return 1 <= len(words) <= 5 and all(word[:1].isupper() or word.lower() in {"de", "da", "do", "e", "em", "a", "com", "para"} for word in words)


def split_heading(text: str) -> tuple[str, str | None]:
    inline = INLINE_COST_TITLE_RE.match(text)
    if inline:
        return inline.group(1).strip(), inline.group(2).strip()
    ranged = RANGE_TITLE_RE.match(text)
    if ranged:
        return ranged.group(1).strip(), ranged.group(2).strip()
    return text, None


def split_known_inline_cost(text: str) -> tuple[str, str] | None:
    for title in sorted(KNOWN_TITLES, key=len, reverse=True):
        if not text.startswith(f"{title} "):
            continue
        rest = text[len(title) :].strip()
        if rest == "Variável" or LOOSE_COST_RE.match(rest):
            return title, rest
    return None


def build_enhancement(title: str, parts: list[str], polarity: str) -> dict | None:
    title = title_case(normalize_text(title))
    if not title:
        return None

    intro: list[str] = []
    cost_segments: list[list[str]] = []
    current_cost: list[str] | None = None

    for part in parts:
        if is_cost(part):
            current_cost = [part]
            cost_segments.append(current_cost)
            continue
        if current_cost is not None:
            current_cost.append(part)
        else:
            intro.append(part)

    costs: list[str] = []
    description = list(intro)

    if cost_segments:
        if len(cost_segments) == 1:
            label, detail = format_cost(cost_segments[0][0])
            costs = [label]
            description.extend([text for text in [detail, *cost_segments[0][1:]] if text])
        else:
            for segment_parts in cost_segments:
                label, detail = format_cost(segment_parts[0])
                costs.append(normalize_text(" ".join([f"{label}: {detail}".strip(), *segment_parts[1:]])))
    elif title in SPECIAL_COSTS:
        costs = [SPECIAL_COSTS[title]]
        description = parts
    else:
        costs = ["Ver referência"]
        description = parts

    item = {
        "id": slugify(title),
        "title": title,
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
    return item


def parse_content(paragraphs: list[str]) -> list[dict]:
    content = clean(paragraphs)
    start = content.index("Aprimoramentos Positivos") + 1
    items: list[dict] = []
    current_title: str | None = None
    current_parts: list[str] = []
    polarity = "positivo"

    def flush() -> None:
        nonlocal current_title, current_parts
        if current_title and current_parts:
            item = build_enhancement(current_title, current_parts, polarity)
            if item:
                items.append(item)
        current_title = None
        current_parts = []

    for text in content[start:]:
        if text == "Aprimoramentos Negativos":
            flush()
            polarity = "negativo"
            continue
        if text == "Aprimoramentos Positivos":
            continue
        if current_title == "Vidas Gastas" and text == "Apenas para Gnomos":
            current_parts.append(text)
            continue
        inline = split_known_inline_cost(text)
        if inline:
            flush()
            current_title, first_cost = inline
            current_parts = [first_cost]
            continue
        if is_heading(text):
            flush()
            current_title, inline_cost = split_heading(text)
            current_parts = [inline_cost] if inline_cost else []
            continue
        if current_title:
            current_parts.append(text)
    flush()

    deduped: dict[str, dict] = {}
    for item in items:
        deduped[item["id"]] = item
    return list(deduped.values())


def build_payload() -> dict:
    items = parse_content(docx_paragraphs())
    positive_count = sum(1 for item in items if item["polarity"] == "positivo")
    negative_count = sum(1 for item in items if item["polarity"] == "negativo")
    return {
        "version": 1,
        "source": SOURCE,
        "title": TITLE,
        "sourceFile": SOURCE_PATH.name,
        "status": "pilot_review",
        "summary": "Lista dedicada de aprimoramentos positivos e negativos.",
        "areas": ["aprimoramentos"],
        "groups": [
            {
                "id": "regra-base-aprimoramentos-4",
                "title": f"Regra base - {TITLE}",
                "kind": "ruleset",
                "area": "regras_base",
                "sectionTitle": "Regra Base",
                "sections": [
                    section(
                        "orientacao",
                        f"Regra base - {TITLE}",
                        "regras_base",
                        [
                            "Aprimoramentos positivos representam vantagens compradas com pontos; aprimoramentos negativos representam limitações que concedem pontos ou impõem restrições.",
                            "Quando um aprimoramento possui variações de custo, cada custo mantém junto o efeito concedido por aquele valor.",
                        ],
                    )
                ],
            }
        ],
        "sections": items,
        "counts": {
            "aprimoramentos": len(items),
            "aprimoramentos_positivos": positive_count,
            "aprimoramentos_negativos": negative_count,
        },
        "reviewNotes": [
            "Quebras de página e linhas partidas foram removidas antes da segmentação.",
            "Modificadores negativos internos de Ataque Especial foram preservados na descrição do aprimoramento positivo, não como aprimoramentos negativos independentes.",
        ],
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
    }


def main() -> None:
    payload = build_payload()
    write_json(OUT_PATH, payload)
    write_json(DOCS_OUT_PATH, payload)
    print(f"Wrote {OUT_PATH}")
    print(f"Wrote {DOCS_OUT_PATH}")
    print(f"Sections: {len(payload['sections'])}; counts: {payload['counts']}")


if __name__ == "__main__":
    main()
