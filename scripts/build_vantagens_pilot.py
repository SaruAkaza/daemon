from __future__ import annotations

import re
from collections import Counter
from datetime import UTC, datetime

from docx import Document

from common import ROOT, slugify, write_json


SOURCE = "vantagens"
TITLE = "Vantagens"
SOURCE_CANDIDATES = [
    ROOT / "Livros" / "word" / "Vantagens.docx",
    ROOT / "Livros" / "word" / "feito" / "Vantagens.docx",
]
SOURCE_PATH = next((path for path in SOURCE_CANDIDATES if path.exists()), SOURCE_CANDIDATES[0])
OUT_PATH = ROOT / "data" / "pilot" / f"{SOURCE}.json"
DOCS_OUT_PATH = ROOT / "docs" / "assets" / "data" / "pilot" / f"{SOURCE}.json"


TEXT_FIXES = {
    "Artifice": "Artífice",
    "personagempode": "personagem pode",
    "caracteristicas": "características",
    "numero": "número",
    "resistencia": "resistência",
    "equilantes": "equivalentes",
    "disconsiderada": "desconsiderada",
    "tres": "três",
    "Concerteza": "Com certeza",
    "usa honra": "sua honra",
    "espacialização": "especialização",
    "vulneravel": "vulnerável",
    "insubstâncial": "insubstancial",
    "igualou": "igual ou",
    "Continua": "Contínuo",
    "concertá-lo": "consertá-lo",
    "freqüentemente": "frequentemente",
    "Tecnoligia": "Tecnologia",
    "deciborgues": "de ciborgues",
    "inicia a contagem": "iniciar a contagem",
    "prar cada": "para cada",
    "resistenca": "resistência",
    "proprio": "próprio",
    "seguranca": "segurança",
    "duraçao": "duração",
    "arremessa-las": "arremessá-las",
    "segura-la": "segurá-la",
    "a custo 4 PMs": "ao custo de 4 PMs",
    "0substituí-lo": "substituí-lo",
    "convicente": "convincente",
    "bonus": "bônus",
    "nã sofrem": "não sofrem",
    "Tambem": "Também",
    "a asfixia": "asfixia",
    "fazer nada naquele turno": "fazer mais nada naquele turno",
}

RACE_TITLES = {
    "Anão",
    "Centauro",
    "Centauro élfico",
    "Ceratop",
    "Dragoas Caçadoras",
    "Elfo",
    "Gnomos",
    "Halfling",
    "Hobgoblin",
    "Orda",
    "Ptero",
    "Tauro",
    "Troglodita",
    "Velocis",
}

KIT_TITLES = {
    "Bardo",
    "Bárbaros",
    "Caçador de Dragões",
    "Capitão",
    "Cavaleiro",
    "Domador de Feras",
    "Gladiador",
    "Marujo",
    "Necromante",
    "Ninja",
    "Patrulheiros Selvagens",
    "Samurais",
    "Tecnauta",
    "Wu Jen",
}

SUBOPTION_PARENTS = {
    "Arma Especial": {"Ataque Especial", "Sagrada", "Retornável", "Veloz", "Vorpal", "Maldita"},
    "Ataque Especial": {"Área", "Lento", "Paralisante", "Perto da Morte", "Preciso", "Teleguiado"},
    "Familiar": {"PMs Extra", "Sentidos", "Toque", "Ferramentas"},
    "Implantes": {"Comunicador", "Espionagem", "Hacker", "Infiltrador", "Suporte de Vida"},
}


def normalize_text(text: str) -> str:
    text = text.replace("\u00a0", " ")
    for old, new in TEXT_FIXES.items():
        text = text.replace(old, new)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"\b1d", "1D", text, flags=re.I)
    text = text.replace("Pdf", "PdF")
    return text


def raw_text() -> str:
    return normalize_text(" ".join(p.text.strip() for p in Document(SOURCE_PATH).paragraphs if p.text.strip()))


def cost_label(cost: str) -> str:
    cleaned = re.sub(r"\s+", " ", cost).strip()
    if cleaned.lower() == "igual o custo em focus":
        return "Igual ao custo em Focus"
    if "-" in cleaned and not cleaned.strip().startswith("-"):
        return f"{cleaned} Pontos"
    value = int(cleaned)
    return f"{value} Ponto" if abs(value) == 1 else f"{value} Pontos"


def title_from_prefix(prefix: str) -> str:
    prefix = re.sub(r"^[:;,) \t]+", "", prefix.strip())
    title_fixes = {
        "Mas, se quiser, você pode pagar mais pontos para ter uma arma mais poderosa, com habilidade extras Ataque Especial": "Ataque Especial",
        "osão; Calor/Fogo; Frio/Gelo; Luz; Eletricidade; Vento/Som; Químico (Água, Ácido, Venenos) (2 ptos cada) Ataque Especial": "Ataque Especial",
        "Por mais pontos, é possível dar poderes extras ao ataque: Área": "Área",
        "Caso o atacante esteja dentro da área de efeito, ele TAMBÉM sofrerá dano Lento": "Lento",
        "Outras habilidades podem ser concedidas ao seu Familiar: PMs Extra": "PMs Extra",
        "l): São aprimoramentos tecnológicos na forma de equipamentos sofisticados inclusos na estrutura de ciborgues Comunicador": "Comunicador",
    }
    if prefix in title_fixes:
        return title_fixes[prefix]
    if prefix == "Especial" or prefix.endswith(" Ataque Especial"):
        return "Ataque Especial"
    if len(prefix) > 70 and " " in prefix:
        return prefix.rsplit(" ", 1)[-1]
    return prefix


def marker_entries(text: str) -> list[dict]:
    marker = re.compile(r"\(([-+]?\d+(?:\s*-\s*\d+)?|igual o custo em focus)\s*p(?:ontos?|tos?|ts?)\)\s*:")
    matches = list(marker.finditer(text))
    headers: list[dict] = []
    for match in matches:
        prefix = text[max(0, match.start() - 140) : match.start()]
        separator = max(prefix.rfind("."), prefix.rfind("!"), prefix.rfind("?"), prefix.rfind("]"))
        raw_title = re.sub(r"^[:;,) \t]+", "", prefix[separator + 1 :].strip())
        title = title_from_prefix(raw_title)
        local_title_start = prefix.rfind(raw_title)
        title_start = max(0, match.start() - len(raw_title))
        if local_title_start >= 0:
            title_start = max(0, match.start() - len(prefix) + local_title_start)
        headers.append({"match": match, "title": title, "titleStart": title_start})

    entries: list[dict] = []
    for idx, header in enumerate(headers):
        match = header["match"]
        start = match.end()
        end = headers[idx + 1]["titleStart"] if idx + 1 < len(headers) else len(text)
        entries.append(
            {
                "title": normalize_text(header["title"]),
                "cost": cost_label(match.group(1)),
                "description": normalize_text(text[start:end]),
            }
        )
    return entries


def paragraph_chunks(text: str, limit: int = 900) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", normalize_text(text))
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if not sentence:
            continue
        if current and len(current) + len(sentence) + 1 > limit:
            chunks.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        chunks.append(current)
    return chunks or [normalize_text(text)]


def block(block_id: str, title: str, area: str, paragraphs: list[str]) -> dict:
    return {"id": slugify(block_id), "title": title, "area": area, "paragraphs": paragraphs}


def classify(title: str) -> tuple[str, str, str]:
    if title in RACE_TITLES:
        return "racas", "race", "Raças"
    if title in KIT_TITLES:
        return "kits", "kit", "Kits"
    return "aprimoramentos", "enhancement", "Aprimoramento"


def enhancement_type(cost_lines: list[str]) -> str:
    if all(line.strip().startswith("-") for line in cost_lines):
        return "Aprimoramento Negativo"
    if any(line.strip().startswith("-") for line in cost_lines):
        return "Aprimoramento Variável"
    return "Aprimoramento Positivo"


def build_sections(entries: list[dict], text: str) -> list[dict]:
    sections: list[dict] = []
    current: dict | None = None
    options: list[str] = []
    skip_next = False

    for entry in entries:
        title = entry["title"]
        if skip_next:
            skip_next = False
            continue

        if current and title in SUBOPTION_PARENTS.get(current["title"], set()):
            options.append(f"{title} ({entry['cost']}): {entry['description']}")
            continue

        if current:
            sections.append(make_item(current, options))
            options = []

        current = entry

        if title == "Idade Imutável":
            implantes_match = re.search(r"Implantes \(variável\):", text)
            if implantes_match and "Implantes" not in [item["title"] for item in entries]:
                pass

    if current:
        sections.append(make_item(current, options))

    sections = insert_implantes(sections, entries, text)
    return sections


def make_item(entry: dict, options: list[str]) -> dict:
    title = entry["title"]
    area, kind, section_title = classify(title)
    cost_lines = [entry["cost"]]
    detail_sections = [block(f"{title}-custo", "Custo", area, cost_lines)]
    if options:
        detail_sections.append(block(f"{title}-opcoes", "Opções", area, options))
    detail_sections.append(block(f"{title}-descricao", "Descrição", area, paragraph_chunks(entry["description"])))
    payload = {
        "id": slugify(title),
        "title": title,
        "area": area,
        "kind": kind,
        "sectionTitle": section_title,
        "cost": None,
        "type": enhancement_type(cost_lines) if area == "aprimoramentos" else None,
        "paragraphs": [paragraph for section in detail_sections for paragraph in section["paragraphs"]],
        "sections": detail_sections,
    }
    return payload


def insert_implantes(sections: list[dict], entries: list[dict], text: str) -> list[dict]:
    option_titles = SUBOPTION_PARENTS["Implantes"]
    option_entries = [entry for entry in entries if entry["title"] in option_titles]
    if not option_entries:
        return sections
    options = [f"{entry['title']} ({entry['cost']}): {entry['description']}" for entry in option_entries]
    description = ""
    match = re.search(r"Implantes \(variável\):(.+?)Comunicador\s*\(", text)
    if match:
        description = normalize_text(match.group(1))
    implantes = {
        "id": "implantes",
        "title": "Implantes",
        "area": "aprimoramentos",
        "kind": "enhancement",
        "sectionTitle": "Aprimoramento",
        "cost": None,
        "type": "Aprimoramento Variável",
        "paragraphs": ["Variável", *options, *paragraph_chunks(description)],
        "sections": [
            block("implantes-custo", "Custo", "aprimoramentos", ["Variável"]),
            block("implantes-opcoes", "Opções", "aprimoramentos", options),
            block("implantes-descricao", "Descrição", "aprimoramentos", paragraph_chunks(description)),
        ],
    }
    without_options = [section for section in sections if section["title"] not in option_titles]
    for idx, section in enumerate(without_options):
        if section["title"] == "Idade Imutável":
            without_options.insert(idx + 1, implantes)
            return without_options
    without_options.append(implantes)
    return without_options


def build_payload() -> dict:
    text = raw_text()
    entries = marker_entries(text)
    sections = build_sections(entries, text)
    counts = Counter(section["area"] for section in sections)
    return {
        "version": 1,
        "source": SOURCE,
        "title": TITLE,
        "sourceFile": SOURCE_PATH.name,
        "sourcePath": str(SOURCE_PATH.relative_to(ROOT)),
        "status": "pilot_review",
        "summary": "Lista de vantagens, raças e kits derivados de um DOCX sem quebras de parágrafo, normalizada por entradas no padrão nome/custo.",
        "areas": sorted(counts),
        "groups": [],
        "sections": sorted(sections, key=lambda item: (item["area"], item["title"].casefold())),
        "counts": dict(counts),
        "reviewNotes": [
            "O DOCX original possui todo o conteúdo em um único parágrafo; a divisão foi reconstruída pelo padrão Nome (custo): descrição.",
            "Subopções de Arma Especial, Ataque Especial, Familiar e Implantes foram mantidas dentro do item pai.",
            "Raças e kits explícitos foram separados de aprimoramentos para manter coerência semântica.",
        ],
        "generatedAt": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }


def main() -> None:
    payload = build_payload()
    write_json(OUT_PATH, payload)
    write_json(DOCS_OUT_PATH, payload)
    print(f"Wrote {OUT_PATH}")
    print(f"Wrote {DOCS_OUT_PATH}")
    print(f"Sections: {len(payload['sections'])}")


if __name__ == "__main__":
    main()
