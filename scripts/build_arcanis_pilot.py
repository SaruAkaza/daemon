from __future__ import annotations

import re
from datetime import datetime
from typing import Iterable

from docx import Document

from common import ROOT, slugify, write_json


SOURCE = "arcanis"
TITLE = "Arcanis"
SOURCE_CANDIDATES = [
    ROOT / "Livros" / "word" / "Arcanis_OCR_alta_qualidade.docx",
    ROOT / "Livros" / "word" / "feito" / "Arcanis_OCR_alta_qualidade.docx",
]
SOURCE_PATH = next((path for path in SOURCE_CANDIDATES if path.exists()), SOURCE_CANDIDATES[0])
OUT_PATH = ROOT / "data" / "pilot" / f"{SOURCE}.json"
DOCS_OUT_PATH = ROOT / "docs" / "assets" / "data" / "pilot" / f"{SOURCE}.json"


DROP_EXACT = {
    TITLE,
    "Texto extraído por OCR / camada textual, com limpeza de quebras de linha e caracteres indevidos.",
    "YOSHIRO",
    "Role Playing Game",
    "SUPLEMENTO",
    "Guia Completo dos",
    "Equipe",
    "RPG Anime Brasil",
    "Página 1",
    "Página 2",
    "Página 3",
    "Página 4",
    "Página 5",
    "Página 6",
    "Página 7",
    "Página 8",
    "Página 9",
    "Página 10",
    "Página 11",
    "Página 12",
}

TEXT_FIXES = {
    "redejovem. net": "redejovem.net",
    "hotmail. com": "hotmail.com",
    "YOSHIRO ROLE PLAYING GAME- módulo": "YOSHIRO ROLE PLAYING GAME - módulo",
    "usa uma magia": "usar uma magia",
    "chronologia": "cronologia",
    "magica": "mágica",
    "Mágica": "Mágica",
    "canditados": "candidatos",
    "captura-las": "capturá-las",
    "furação": "furacão",
    "têm duração": "tem duração",
    "reconstituíção": "reconstituição",
    "suites": "suítes",
    "Horna": "Honra",
    "corresponde o lado": "correspondem ao lado",
    "tempode": "tempo de",
    "devolta": "de volta",
    "apretechos": "apetrechos",
    "contruir": "construir",
    "contratalo": "contratá-lo",
    "tirá o pó": "tirar o pó",
    "Andídoto": "Antídoto",
    "necta": "néctar",
    "isnpiração": "inspiração",
    "trexo": "trecho",
    "séria Guia": "série Guia",
    "imprimido": "imprimido",
    "entre em coma": "entra em coma",
    "ta tão": "está tão",
    "PSIOCINISTAS.": "PSIOCINISTAS.",
    "Ética Moral Honra": "Ética Moral Honra",
    "Etica Moral": "Ética Moral",
    "estrovertidas": "extrovertidas",
    "concerteza": "com certeza",
    "destruíção": "destruição",
    "ajudal-os": "ajudá-los",
    "adversário": "adversários",
    "arcanisa": "arcanis",
    "guerília": "guerrilha",
    "Faérie": "Faérie",
    "arqueeria": "arquearia",
    "abandoram": "abandonaram",
    "rospo": "rosto",
    "ofença": "ofensa",
    "Dedectar": "Detectar",
    "psiquícos": "psíquicos",
    "psiocinista": "psiocinista",
    "correspondento": "correspondendo",
    "Pontos Heróicos": "Pontos Heroicos",
    "humanóide": "humanoide",
    "kansarianosmagos": "kansarianos-magos",
    "kansarianos-magos": "kansarianos-magos",
    "Gks": "GKs",
    "GKs/tegicnistas": "GKs/tegicnistas",
    "tegicnistas": "tegicnistas",
    "Kansarianas": "Kansarianas",
    "proibída": "proibida",
    "varios": "vários",
    "Págs 78 à 83": "págs. 78 a 83",
    "3D turnos": "3d6 turnos",
    "2d10-5": "2d10-5",
}


def normalize_text(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = text.replace("â€œ", '"').replace("â€", '"').replace("â€™", "'")
    text = text.replace("–", "-").replace("—", "-")
    for old, new in TEXT_FIXES.items():
        text = text.replace(old, new)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"(\d+)\.\s+(\d+)", r"\1.\2", text)
    text = re.sub(r"\b([0-9]+)\s+\$Sht\b", r"\1$Sht", text)
    return text


def is_page_noise(text: str) -> bool:
    return bool(re.fullmatch(r"Página \d+", text, flags=re.IGNORECASE))


def should_join(previous: str, current: str) -> bool:
    if not previous or not current:
        return False
    if current.startswith((
        "Custo:",
        "Perícias:",
        "Aprimoramentos:",
        "Caminhos da Magia:",
        "Pontos Heroicos:",
        "OBS:",
        "*OBS:",
        "Capítulo",
        "Cabala ",
    )):
        return False
    if previous.endswith((",", ":", "-", "/", "\\")):
        return True
    if current[:1].islower() and not previous.endswith((".", "!", "?", ":", ";", ")")):
        return True
    last_word = previous.split()[-1].lower().strip(".,;:!?")
    if last_word in {"de", "do", "da", "dos", "das", "em", "por", "com", "para", "que", "o", "os", "as", "um", "uma", "no", "na", "e", "ou", "se", "ao", "à", "dos", "arcanis", "cômico", "nome", "grande"}:
        return True
    return False


def clean(values: Iterable[str]) -> list[str]:
    paragraphs: list[str] = []
    for raw in values:
        text = normalize_text(raw)
        if not text or text in DROP_EXACT or is_page_noise(text):
            continue
        if paragraphs and should_join(paragraphs[-1], text):
            paragraphs[-1] = normalize_text(f"{paragraphs[-1]} {text}")
        else:
            paragraphs.append(text)
    return paragraphs


def raw_paragraphs() -> list[str]:
    return [paragraph.text for paragraph in Document(SOURCE_PATH).paragraphs if paragraph.text.strip()]


def collect(paragraphs: list[str], start: int, end: int) -> list[str]:
    return clean(paragraphs[start:end])


def collect_body(paragraphs: list[str], start: int, end: int, *headings: str) -> list[str]:
    skipped = {normalize_text(heading) for heading in headings}
    values: list[str] = []
    for paragraph in collect(paragraphs, start, end):
        value = paragraph
        changed = True
        while changed:
            changed = False
            for heading in sorted(skipped, key=len, reverse=True):
                if value == heading:
                    value = ""
                    changed = True
                    break
                if value.startswith(f"{heading} "):
                    value = normalize_text(value.removeprefix(heading))
                    changed = True
                    break
        if value:
            values.append(value)
    return values


def section(section_id: str, title: str, area: str, paragraphs: list[str]) -> dict:
    return {"id": section_id, "title": title, "area": area, "paragraphs": paragraphs}


def typed_item(
    title: str,
    area: str,
    kind: str,
    section_title: str,
    paragraphs: list[str],
    sections: list[dict] | None = None,
) -> dict:
    return {
        "id": slugify(title),
        "title": title,
        "area": area,
        "kind": kind,
        "sectionId": slugify(section_title),
        "sectionTitle": section_title,
        "paragraphs": paragraphs,
        "sections": sections or [section("descricao", "Descrição", area, paragraphs)],
    }


def split_inline_markers(text: str, markers: list[str]) -> list[tuple[str, str]]:
    positions: list[tuple[int, str]] = []
    for marker in markers:
        match = re.search(rf"\b{re.escape(marker)}:\s*", text)
        if match:
            positions.append((match.start(), marker))
    positions.sort()
    parts: list[tuple[str, str]] = []
    for index, (start, marker) in enumerate(positions):
        value_start = start + len(marker) + 1
        value_end = positions[index + 1][0] if index + 1 < len(positions) else len(text)
        parts.append((marker, normalize_text(text[value_start:value_end])))
    return parts


def kit(title: str, description: list[str], details: list[str], notes: list[str]) -> dict:
    sections: list[dict] = [section("descricao", "Descrição", "kits", description)]
    detail_text = normalize_text(" ".join(details))
    prereqs: list[str] = []
    if detail_text.startswith("(OBS:"):
        match = re.match(r"^\((OBS:\s*[^)]+)\)\s*(.+)$", detail_text)
        if match:
            prereqs.append(normalize_text(match.group(1).removeprefix("OBS:")))
            detail_text = normalize_text(match.group(2))
    for marker, value in split_inline_markers(
        detail_text,
        ["Custo", "Perícias", "Aprimoramentos", "Caminhos da Magia", "Pontos Heroicos"],
    ):
        if marker == "Custo":
            parts = [part.strip() for part in value.split(",", 1)]
            sections.append(section("custo", "Custo", "kits", [parts[0]]))
            if len(parts) > 1:
                sections.append(section("custo-de-pericia", "Custo de Perícia", "kits", [parts[1]]))
            continue
        sections.append(section(slugify(marker), marker, "kits", [value]))
    if prereqs:
        sections.insert(1, section("pre-requisito", "Pré-requisito", "kits", prereqs))
    if notes:
        sections.append(section("observacoes", "Observações", "kits", notes))
    return typed_item(title, "kits", "kit", "Kit", [paragraph for block in sections for paragraph in block["paragraphs"]], sections)


def build_kits(paragraphs: list[str]) -> list[dict]:
    specs = [
        ("Cabala de Nísona", [100], [102], []),
        ("Cabala dos Meta-Mágicos", [104], [106], [107]),
        ("Cabala dos Justiceiros Místicos", [110], [112], []),
        ("Cabala dos Guerreiros Mágicos", [114], [116], [117]),
        ("Cabala dos Gatunos", [119], [121], []),
        ("Cabala dos Faérie", [123], [125, 126], [127, 129]),
        ("Cabala dos Aqua", [131], [133], [134]),
        ("Cabala dos Arqueiros Mágicos", [136], [138], [139, 140]),
        ("Cabala dos Pistoleiros Mágicos", [142], [144], [145, 146]),
        ("Cabala das Kitanas", [148, 150], [152, 153, 154], []),
        ("Cabala dos Glacius", [156], [158, 159, 160], [161]),
        ("Cabala das Folha-Das-Florestas", [163], [165], [166]),
        ("Cabala dos Olharis", [168], [170], [172, 173]),
        ("Cabala dos DragonMage", [175], [177, 178, 179], []),
        ("Cabala dos Gatosinej", [181], [183, 184, 185], [186]),
    ]
    items: list[dict] = []
    for title, desc_indexes, detail_indexes, note_indexes in specs:
        description = clean(paragraphs[index] for index in desc_indexes)
        details = clean(paragraphs[index] for index in detail_indexes)
        notes = clean(paragraphs[index] for index in note_indexes)
        items.append(kit(title, description, details, notes))
    return items


def build_payload() -> dict:
    paragraphs = raw_paragraphs()

    lore_sections = [
        section("apresentacao", "Apresentação", "cenarios_lore", collect(paragraphs, 11, 12)),
        section("arcanis", "Arcanis", "cenarios_lore", collect_body(paragraphs, 19, 21, "Arcanis")),
        section("origem-da-linhagem", "O Início dos Arcanis", "cenarios_lore", collect_body(paragraphs, 30, 32, "O Início dos Arcanis")),
        section("academias-arcanis", "Como são as Academias Arcanis", "cenarios_lore", collect_body(paragraphs, 35, 37, "Como são as Academias Arcanis")),
        section("familias-arcanis", "Famílias Arcanis", "cenarios_lore", collect_body(paragraphs, 87, 94, "As Famílias Arcanis", "FAMÍLIAS ANTIGAS PERTENCENTES A LINHAGEM ARCANIS")),
        section("cabalas-dos-arcanis", "Cabalas dos Arcanis", "cenarios_lore", collect_body(paragraphs, 94, 98, "Capítulo 03- Cabalas dos Arcanis", "Cabalas de Arcanis")),
    ]
    lore_item = typed_item(
        "Arcanis",
        "cenarios_lore",
        "setting",
        "Cenário/Lore",
        [paragraph for block in lore_sections for paragraph in block["paragraphs"]],
        lore_sections,
    )

    rule_sections = [
        section("arma-kansariana", "Arma Kansariana", "regras_base", collect_body(paragraphs, 21, 26, "O que é Arma Kansariana?")),
        section("magica-luniana", "Mágica Luniana", "regras_base", collect_body(paragraphs, 26, 30, "A mágica Luniana")),
        section("se-tornando-um-arcanis", "Se tornando um Arcanis", "regras_base", collect_body(paragraphs, 32, 34, "Se tornando um Arcanis")),
        section("ritual-fada-dos-sete-ventos", "Ritual Fada dos Sete Ventos", "regras_base", collect_body(paragraphs, 34, 35, "O Ritual Fada dos Sete Ventos")),
        section("eticas-morais", "Éticas Morais dos Arcanis", "regras_base", collect_body(paragraphs, 38, 40, "Éticas Morais dos Arcanis")),
        section("lagrima-do-sangue-do-odio", "Lágrima do Sangue do Ódio", "regras_base", collect_body(paragraphs, 83, 87, "O QUE É LÁGRIMA DO SANGUE DO ÓDIO?")),
    ]
    rule_item = typed_item(
        "Regra base - Arcanis",
        "regras_base",
        "ruleset",
        "Regra Base",
        [paragraph for block in rule_sections for paragraph in block["paragraphs"]],
        rule_sections,
    )

    service_sections = [
        section("servicos-mercenarios", "Serviços Mercenários", "regras_base", collect_body(paragraphs, 40, 43, "Serviços Mercenários")),
        section("aprendendo-magicas", "Aprendendo Mágicas", "regras_base", collect_body(paragraphs, 43, 45, "Aprendendo Mágicas")),
        section("salario", "Recebendo Salário", "regras_base", collect_body(paragraphs, 48, 50, "Recebendo salário")),
        section("pocoes-cientificas", "Poções Científicas", "regras_base", collect_body(paragraphs, 51, 53, "Venda de Poções científicas")),
        section("pocoes-a-venda", "Poções à Venda", "regras_base", collect_body(paragraphs, 53, 68, "Poções a Venda", "Preço")),
        section("contratacao-de-servicos", "Contratação de Serviços Mercenários", "regras_base", collect_body(paragraphs, 69, 71, "Contratação de Serviços Mercenários")),
        section("ensinando-magias", "Ensinando Magias", "regras_base", collect_body(paragraphs, 71, 73, "Ensinando Magias")),
        section("servicos-domesticos", "Serviços Domésticos", "regras_base", collect_body(paragraphs, 73, 75, "Serviços Domésticos")),
        section("atendente", "Atendente", "regras_base", collect_body(paragraphs, 75, 77, "Atendente")),
        section("armas-kansarianas", "Construir Armas Kansarianas", "regras_base", collect_body(paragraphs, 78, 80, "Construir Armas Kansarianas")),
        section("ensinamentos-de-proezas", "Ensinamentos de Proezas", "regras_base", collect_body(paragraphs, 80, 82, "Ensinamentos de Proezas")),
    ]
    rule_item["sections"] = [*rule_item["sections"][:-1], *service_sections, rule_item["sections"][-1]]
    rule_item["paragraphs"] = [paragraph for block in rule_item["sections"] for paragraph in block["paragraphs"]]

    kits = build_kits(paragraphs)
    sections = [lore_item, rule_item, *kits]

    return {
        "version": 1,
        "source": SOURCE,
        "title": TITLE,
        "sourceFile": SOURCE_PATH.name,
        "status": "pilot_review",
        "summary": "Suplemento da linhagem Arcanis, com lore, regras, serviços de academia e cabalas em formato de kits.",
        "areas": ["cenarios_lore", "regras_base", "kits"],
        "groups": [],
        "sections": sections,
        "counts": {
            "cenarios_lore": 1,
            "regras_base": 1,
            "kits": len(kits),
            "itens": len(sections),
        },
        "reviewNotes": [
            "Texto revisado antes da catalogação, com correções de OCR e normalização de quebras indevidas.",
            "Cabalas foram catalogadas como kits por conterem custo de aprimoramento, custo de perícia, perícias e aprimoramentos.",
            "Serviços, poções e armas vendidas/construídas em academias foram mantidos em Regras Base por funcionarem como procedimentos econômicos e regras de uso das Academias Arcanis.",
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
