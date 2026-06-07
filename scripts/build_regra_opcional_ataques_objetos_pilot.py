from __future__ import annotations

import re
from collections import Counter
from datetime import UTC, datetime
from typing import Iterable

from docx import Document

from common import ROOT, slugify, write_json


SOURCE = "regra-opcional-ataques-a-objetos"
TITLE = "Regra Opcional: Ataques a Objetos"
SOURCE_CANDIDATES = [
    ROOT / "Livros" / "word" / "Regra Opcional Ataques a Objetos.docx",
    ROOT / "Livros" / "word" / "feito" / "Regra Opcional Ataques a Objetos.docx",
]
SOURCE_PATH = next((path for path in SOURCE_CANDIDATES if path.exists()), SOURCE_CANDIDATES[0])
OUT_PATH = ROOT / "data" / "pilot" / f"{SOURCE}.json"
DOCS_OUT_PATH = ROOT / "docs" / "assets" / "data" / "pilot" / f"{SOURCE}.json"


TEXT_FIXES = {
    "Regra Opcional:Ataques a objetos": TITLE,
    "ospersonagens": "os personagens",
    "precisaram": "precisarão",
    "quandoquiserem": "quando quiserem",
    "geralmentesão": "geralmente são",
    "lugar.Entretanto": "lugar. Entretanto",
    "Nestecaso": "Neste caso",
    "umequivalente": "um equivalente",
    "teste deAtaque": "teste de Ataque",
    "obteresses": "obter esses",
    "12,6km/h": "12,6 km/h",
    "namaioria": "na maioria",
    "dedano": "de dano",
    "seutamanho": "seu tamanho",
    "Pontosde Vida": "Pontos de Vida",
    "terbem": "ter bom",
    "deum": "de um",
    "atéque": "até que",
    "aotentar": "ao tentar",
    "forteque": "forte que",
    "iriaderrubá-la": "iria derrubá-la",
    "Via deregra": "Via de regra",
    " objetodobram": " objeto dobram",
    "testeFácil": "teste Fácil",
    "sercortado": "ser cortado",
    "algunsmateriais": "alguns materiais",
    "Nãoperfurante": "Não perfurante",
    "deMadeira": "de Madeira",
    "nãodura": "não dura",
    "regraopcional": "regra opcional",
    "nosPontos": "nos Pontos",
    "específicospara": "específicos para",
    "haste demadeira": "haste de madeira",
    "IP doescudo": "IP do escudo",
    "doobjeto": "do objeto",
    "armautilizado": "arma utilizado",
    "serãodobrados": "serão dobrados",
    "odefensor": "o defensor",
    "regrasutilizadas": "regras utilizadas",
    "muitolentos": "muito lentos",
}


def normalize_text(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = text.replace("“", '"').replace("”", '"')
    for old, new in TEXT_FIXES.items():
        text = text.replace(old, new)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"\((\d+(?:,\d+)?)cm\)", r"(\1 cm)", text)
    text = re.sub(r"\((\d+(?:,\d+)?) cm\)", r"(\1 cm)", text)
    text = text.replace("Machado/ Martelo", "Machado/Martelo")
    text = text.replace("Martelo/Clava", "Martelo/Clava")
    return text


def raw_paragraphs() -> list[str]:
    return [paragraph.text.strip() for paragraph in Document(SOURCE_PATH).paragraphs if paragraph.text.strip()]


def clean(values: Iterable[str]) -> list[str]:
    return [text for value in values if (text := normalize_text(value))]


def block(block_id: str, title: str, area: str, paragraphs: list[str]) -> dict:
    return {"id": slugify(block_id), "title": title, "area": area, "paragraphs": paragraphs}


def item(title: str, area: str, kind: str, paragraphs: list[str], sections: list[dict]) -> dict:
    return {
        "id": slugify(title),
        "title": title,
        "area": area,
        "kind": kind,
        "sectionId": "regra-base",
        "sectionTitle": "Regra Base",
        "paragraphs": paragraphs,
        "sections": sections,
    }


def parse_table_row(text: str) -> str:
    text = normalize_text(text)
    if text == "Objeto IP PVs Arma":
        return "Objeto | IP | PVs | Arma"
    match = re.match(r"^(.*?)\s+(\d+)\s+(\d+)\s+(.+)$", text)
    if not match:
        return text
    obj, ip, pvs, weapon = match.groups()
    return f"{obj.strip()} | IP {ip} | PVs {pvs} | {weapon.strip()}"


def build_payload() -> dict:
    paragraphs = raw_paragraphs()
    cleaned = clean(paragraphs)

    intro = cleaned[1:5]
    weapon_start = next(
        index for index, paragraph in enumerate(cleaned)
        if paragraph.startswith("Com essa regra é possível")
    )
    table_lines = [parse_table_row(line) for line in cleaned[5:weapon_start] if line != "Objeto IP PVs Arma"]
    weapon_damage = cleaned[weapon_start:]

    sections = [
        block("funcionamento", "Funcionamento", "regras_base", intro),
        block("materiais-ip-pvs", "Materiais, IP e PVs", "regras_base", table_lines),
        block("dano-em-armas-e-armaduras", "Dano em Armas e Armaduras", "regras_base", weapon_damage),
    ]
    rule = item(
        "Regra base - Ataques a Objetos",
        "regras_base",
        "ruleset",
        [paragraph for section in sections for paragraph in section["paragraphs"]],
        sections,
    )
    counts = Counter(section["area"] for section in [rule])
    return {
        "version": 1,
        "source": SOURCE,
        "title": TITLE,
        "sourceFile": SOURCE_PATH.name,
        "sourcePath": str(SOURCE_PATH.relative_to(ROOT)),
        "status": "pilot_review",
        "summary": "Regra opcional para atacar, quebrar e danificar objetos, incluindo IP/PVs por material e dano em armas, escudos e armaduras.",
        "areas": ["regras_base"],
        "groups": [],
        "sections": [rule],
        "counts": dict(counts),
        "reviewNotes": [
            "Documento sem OCR pesado; limpeza concentrou-se em palavras coladas pela extração do DOCX.",
            "Tabela preservada como linhas estruturadas no bloco de regra, sem criar itens individuais.",
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
