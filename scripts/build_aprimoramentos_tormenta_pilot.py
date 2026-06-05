from __future__ import annotations

import re
from datetime import datetime
from typing import Iterable

from docx import Document

from common import ROOT, slugify, write_json


SOURCE = "aprimoramentos-tormenta"
TITLE = "Aprimoramentos Tormenta"
SOURCE_CANDIDATES = [
    ROOT / "Livros" / "word" / "Aprimoramentos_Tormenta_OCR_alta_qualidade.docx",
    ROOT / "Livros" / "word" / "feito" / "Aprimoramentos_Tormenta_OCR_alta_qualidade.docx",
]
SOURCE_PATH = next((path for path in SOURCE_CANDIDATES if path.exists()), SOURCE_CANDIDATES[0])
OUT_PATH = ROOT / "data" / "pilot" / f"{SOURCE}.json"
DOCS_OUT_PATH = ROOT / "docs" / "assets" / "data" / "pilot" / f"{SOURCE}.json"

COST_RE = re.compile(
    r"^([+-]?\d+)\s+pontos?(?:\s+por\s+n[ií]vel|\s+n[ií]vel)?\s*[:.\-]?\s*(.*)$",
    re.IGNORECASE,
)
INLINE_COST_RE = re.compile(
    r"^(.+?)\s+([+-]?\d+\s+pontos?(?:\s+por\s+n[ií]vel|\s+n[ií]vel)?\s*[:.\-]\s*.*)$",
    re.IGNORECASE,
)
REGIONAL_RE = re.compile(r"^(.+?)\s+\[regional:\s*(.+?)\]\s*:?\s*(.*)$", re.IGNORECASE)

DROP_EXACT = {
    "Aprimoramentos Tormenta",
    "Texto extraído por OCR/camada de texto e normalizado para leitura em DOCX.",
    "[Sem texto reconhecível nesta página.]",
}

REGIONAL_TITLES = {
    "Amigo das Armas",
    "Amigo das Árvores",
    "Amigo dos Cavalos",
    "Amigo do Oceano",
    "Amigo dos Rios",
    "Arma Dupla",
    "Arma de Família",
    "Arma de Madeira Tollon",
    "Ateu",
    "Autoconfiança",
    "Aventureiro Nato",
    "Bairrista",
    "Barbarismo",
    "Caminho para Doherimm",
    "Cavaleiro Nato",
    "Comerciante Nato",
    "Conhecimento de Itens Mágicos",
    "Conhecimento de Magia",
    "Conhecimento de Lendas",
    "Conquista da Magia",
    "Contador de Histórias",
    "Espírito de Equipe",
    "Faro para Magos",
    "Fúria Leal",
    "Furtividade das Fadas",
    "Hospitalidade",
    "Impostor",
    "Inimigo de Dragões",
    "Inimigo de Goblinóides",
    "Intolerância",
    "Leal aos Cavaleiros",
    "Lógica Labiríntica",
    "Mago Nato",
    "Médico Nato",
    "Olhos Aguçados",
    "Olhos Especiais",
    "Paciente",
    "Pacifismo",
    "Patriota",
    "Prece para os Mortos",
    "Prece para Valkaria",
    "Prosperidade",
    "Religioso",
    "Resistência a Doenças",
    "Resistência ao Frio",
    "Resistência à Tormenta",
    "Tatuagem Mística",
    "Trapaceiro Nato",
}

COMMON_TITLES = {
    "Aparência Inofensiva",
    "Caçador de Criatura",
    "Facilidade para Línguas",
    "Hierarquia Militar",
    "Intuição",
    "Noção Exata do Tempo",
    "Noção de Perigo",
    "Patrono",
    "Reflexos em Combate",
    "Status Social/Reputação",
    "Terreno Familiar",
    "Torcida",
}

METAMAGIC_TITLES = {
    "Aumentar Magia",
    "Elevar Magia",
    "Estender Magia",
    "Magia Sem Gestos",
    "Magia Silenciosa",
    "Maximizar Magia",
    "Potencializar Magia",
}

ALL_TITLES = REGIONAL_TITLES | COMMON_TITLES | METAMAGIC_TITLES

TEXT_FIXES = {
    "O Tormenta D20 faz um mesmo": "Tormenta D20 faz o mesmo",
    "esta a lista": "está a lista",
    "hambientes": "ambientes",
    "Terremo Familiar": "Terreno Familiar",
    "Kubar": "Khubar",
    "espécieis": "especiais",
    "Personagem com esse": "Personagens com esse",
    "a cima": "acima",
    "secredo": "secreto",
    "encinados": "ensinados",
    "converncer": "convencer",
    "não às possui": "não as possui",
    "Tyrandir": "Tyrondir",
    "nõ são": "não são",
    "proibe": "proíbe",
    "abituados": "habituados",
    "resistir à qualquer": "resistir a qualquer",
    "protegêlos": "protegê-los",
    "antre": "entre",
    "Persongem": "Personagem",
    "influencia": "influência",
    "genêro": "gênero",
    "fonecido": "fornecido",
    "Exécito": "Exército",
    "1 pontos": "1 ponto",
    "-1 pontos": "-1 ponto",
    "-2 pontos": "-2 pontos",
    "1ponto": "1 ponto",
    "PM ́s": "PMs",
    "paracima": "para cima",
    "Coolen": "Collen",
    "Ironfst": "Ironfist",
    "custume": "costume",
    "sumosacerdotes": "sumo-sacerdotes",
    "lagartoelefante": "lagarto-elefante",
    "diante a sociedade": "diante da sociedade",
    "Além disto": "Além disso",
    "vantagens, e desvantagens": "vantagens e desvantagens",
    "será necessário uma": "será necessária uma",
}


def normalize_text(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = text.replace("“", '"').replace("”", '"')
    text = text.replace("–", "-").replace("—", "-")
    for old, new in TEXT_FIXES.items():
        text = text.replace(old, new)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return text


def is_page_noise(text: str) -> bool:
    return bool(re.fullmatch(r"Página \d+", text, flags=re.IGNORECASE))


def raw_paragraphs() -> list[str]:
    return [paragraph.text for paragraph in Document(SOURCE_PATH).paragraphs]


def title_case(title: str) -> str:
    exact = {slugify(item): item for item in ALL_TITLES}
    return exact.get(slugify(title), title.strip())


def starts_title(text: str) -> bool:
    if text in {"NOVOS", "APRIMORAMENTOS METAMÁGICOS Eles tornam as Magias mais fortes, mas também exigem que seja conjurada como uma Magia superior."}:
        return True
    if REGIONAL_RE.match(text):
        return True
    if split_known_inline(text) is not None:
        return True
    if text in ALL_TITLES:
        return True
    return False


def should_join(previous: str, current: str) -> bool:
    if not previous or not current:
        return False
    if previous.count("[") > previous.count("]"):
        return True
    if previous.endswith((",", ":", "-", "/", "\\")):
        return True
    if current in {"APRIMORAMENTOS", "Regional", "Nativo (qualquer),", "Terreno", "Familiar (montanhas ou pradarias)."}:
        return True
    if previous in {"NOVOS", "LISTA DE"}:
        return True
    if previous.endswith("Status Social/Reputação 1 Ponto nível: Indica a reputação e o status diante a sociedade."):
        return False
    last_word = previous.split()[-1].lower().strip(".,;:!?")
    if last_word in {"de", "do", "da", "dos", "das", "em", "por", "com", "para", "que", "o", "os", "as", "um", "uma", "no", "na", "e", "ou", "se", "ao", "à", "consumirá", "seu"}:
        return True
    if current[:1].islower() and not previous.endswith((".", "!", "?", ":", ";", ")")):
        return True
    return False


def clean(values: Iterable[str]) -> list[str]:
    output: list[str] = []
    for raw in values:
        text = normalize_text(raw)
        if not text or text in DROP_EXACT or is_page_noise(text):
            continue
        if output and not starts_title(text) and should_join(output[-1], text):
            output[-1] = normalize_text(f"{output[-1]} {text}")
        else:
            output.append(text)
    return split_embedded_titles(output)


def split_known_inline(text: str) -> tuple[str, str] | None:
    for title in sorted(ALL_TITLES, key=len, reverse=True):
        if text == title:
            return title, ""
        if text.startswith(f"{title} "):
            return title, text[len(title) :].strip()
    return None


def split_embedded_titles(paragraphs: list[str]) -> list[str]:
    output: list[str] = []
    for text in paragraphs:
        if text.startswith("APRIMORAMENTOS Aqui estão"):
            output.append("NOVOS APRIMORAMENTOS")
            output.append(text.removeprefix("APRIMORAMENTOS ").strip())
            continue
        inline = split_known_inline(text)
        if inline and inline[1]:
            title, rest = inline
            regional = REGIONAL_RE.match(text)
            cost_inline = INLINE_COST_RE.match(text)
            if regional:
                output.append(text)
            elif cost_inline:
                output.append(title)
                output.append(rest)
            elif title in COMMON_TITLES | METAMAGIC_TITLES:
                output.append(title)
                output.append(rest)
            else:
                output.append(text)
            continue
        output.append(text)
    return output


def section(section_id: str, title: str, area: str, paragraphs: list[str]) -> dict:
    return {"id": section_id, "title": title, "area": area, "paragraphs": paragraphs}


def cost_label(text: str) -> str:
    match = COST_RE.match(text)
    if not match:
        return text
    value = int(match.group(1))
    unit = "Ponto" if abs(value) == 1 else "Pontos"
    suffix = " por nível" if re.search(r"(por\s+nível|nível)", text, flags=re.IGNORECASE) else ""
    return f"{value} {unit}{suffix}"


def split_costs(parts: list[str]) -> tuple[list[str], list[str]]:
    intro: list[str] = []
    cost_segments: list[list[str]] = []
    current: list[str] | None = None
    for part in parts:
        if COST_RE.match(part):
            current = [part]
            cost_segments.append(current)
        elif current is not None:
            current.append(part)
        else:
            intro.append(part)
    if not cost_segments:
        return [], intro
    if len(cost_segments) == 1:
        label = cost_label(cost_segments[0][0])
        detail = COST_RE.match(cost_segments[0][0]).group(2).strip()
        return [label], [*intro, *([detail] if detail else []), *cost_segments[0][1:]]
    costs: list[str] = []
    for segment in cost_segments:
        match = COST_RE.match(segment[0])
        label = cost_label(segment[0])
        detail = match.group(2).strip()
        costs.append(normalize_text(" ".join([f"{label}: {detail}".strip(), *segment[1:]])))
    return costs, intro


def build_item(title: str, area: str, kind: str, subtype: str, parts: list[str], regions: str = "") -> dict:
    title = title_case(normalize_text(title))
    parts = [normalize_text(part) for part in parts if normalize_text(part)]
    if title == "Status Social/Reputação" and parts and COST_RE.match(parts[0]):
        costs = [cost_label(parts[0])]
        first_detail = COST_RE.match(parts[0]).group(2).strip()
        description = [text for text in [first_detail, *parts[1:]] if text]
    else:
        costs, description = split_costs(parts)
    sections = []
    if costs:
        sections.append(section("custo", "Custo", "aprimoramentos", costs))
    sections.append(section("descricao", "Descrição", "aprimoramentos", description))
    metadata = {"subtipo": subtype}
    if regions:
        metadata["regional"] = regions
    return {
        "id": slugify(title),
        "title": title,
        "area": area,
        "kind": kind,
        "sectionId": subtype,
        "sectionTitle": "Aprimoramento Regional" if subtype == "regional" else "Aprimoramento",
        "metadata": metadata,
        "paragraphs": costs + description,
        "sections": sections,
    }


def parse_items(content: list[str]) -> tuple[list[dict], list[str], list[str]]:
    intro: list[str] = []
    kingdom_list: list[str] = []
    items: list[dict] = []
    current_title = ""
    current_parts: list[str] = []
    current_regions = ""
    mode = "intro"

    def flush() -> None:
        nonlocal current_title, current_parts, current_regions
        if not current_title:
            return
        subtype = "regional" if mode == "regional" else "metamagico" if mode == "metamagic" else "comum"
        items.append(build_item(current_title, "aprimoramentos", "enhancement", subtype, current_parts, current_regions))
        current_title = ""
        current_parts = []
        current_regions = ""

    for text in content:
        if text == "APRIMORAMENTOS REGIONAIS Os livros de O Reinado apresentam regras para personagens nativos de cada reino artoniano em 3D&T. Tormenta D20 faz o mesmo mas com regras para D&D; o suplemento O Reinado D20 aumenta ainda mais este aspecto.":
            intro.append(text)
            continue
        if text.startswith("Aprimoramentos Regionais por Reino"):
            mode = "kingdoms"
            kingdom_list.append(text)
            continue
        if text == "LISTA DE APRIMORAMENTOS REGIONAIS":
            mode = "regional"
            continue
        if text.startswith("NOVOS APRIMORAMENTOS"):
            flush()
            mode = "common"
            remainder = text.removeprefix("NOVOS APRIMORAMENTOS").strip()
            if remainder:
                intro.append(remainder)
            continue
        if text.startswith("APRIMORAMENTOS METAMÁGICOS"):
            flush()
            mode = "metamagic"
            intro.append(text)
            continue

        if mode == "intro":
            intro.append(text)
            continue
        if mode == "kingdoms":
            if REGIONAL_RE.match(text) or split_known_inline(text) in [(title, "") for title in REGIONAL_TITLES]:
                mode = "regional"
            else:
                kingdom_list.append(text)
                continue

        regional = REGIONAL_RE.match(text)
        if regional and mode == "regional":
            flush()
            current_title = regional.group(1).strip()
            current_regions = regional.group(2).strip()
            first = regional.group(3).strip()
            current_parts = [first] if first else []
            continue

        inline = split_known_inline(text)
        if inline and inline[0] in ALL_TITLES:
            title, rest = inline
            if text in ALL_TITLES or title in COMMON_TITLES | METAMAGIC_TITLES:
                flush()
                current_title = title
                current_parts = [rest] if rest else []
                current_regions = ""
                continue

        if current_title:
            current_parts.append(text)
    flush()
    return items, intro, kingdom_list


def build_payload() -> dict:
    content = clean(raw_paragraphs())
    items, intro, kingdom_list = parse_items(content)
    regional_count = sum(1 for item in items if item["metadata"].get("subtipo") == "regional")
    common_count = sum(1 for item in items if item["metadata"].get("subtipo") == "comum")
    metamagic_count = sum(1 for item in items if item["metadata"].get("subtipo") == "metamagico")
    groups = [
        {
            "id": "regra-base-aprimoramentos-tormenta",
            "title": f"Regra base - {TITLE}",
            "kind": "ruleset",
            "area": "regras_base",
            "sectionTitle": "Regra Base",
            "sections": [
                section("introducao", "Introdução", "regras_base", intro),
                section("por-reino", "Aprimoramentos por Reino", "regras_base", kingdom_list),
            ],
        }
    ]
    return {
        "version": 1,
        "source": SOURCE,
        "title": TITLE,
        "sourceFile": SOURCE_PATH.name,
        "status": "pilot_review",
        "summary": "Aprimoramentos regionais, gerais e metamágicos de Tormenta para Sistema Daemon.",
        "areas": ["regras_base", "aprimoramentos"],
        "groups": groups,
        "sections": items,
        "counts": {
            "aprimoramentos": len(items),
            "aprimoramentos_regionais": regional_count,
            "aprimoramentos_comuns": common_count,
            "aprimoramentos_metamagicos": metamagic_count,
        },
        "reviewNotes": [
            "Quebras de página e títulos quebrados por OCR foram recompostos antes da catalogação.",
            "Aprimoramentos regionais sem custo explícito foram mantidos sem bloco de custo.",
            "Escalas como Status Social/Reputação foram mantidas dentro do mesmo item, preservando os níveis.",
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
