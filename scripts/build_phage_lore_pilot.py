from __future__ import annotations

import re
from collections import Counter
from datetime import UTC, datetime
from typing import Iterable

from docx import Document

from common import ROOT, slugify, write_json


SOURCE = "phage"
TITLE = "Phage"
SOURCE_CANDIDATES = [
    ROOT / "Livros" / "word" / "Phage.docx",
    ROOT / "Livros" / "word" / "feito" / "Phage.docx",
]
SOURCE_PATH = next((path for path in SOURCE_CANDIDATES if path.exists()), SOURCE_CANDIDATES[0])
OUT_PATH = ROOT / "data" / "pilot" / f"{SOURCE}.json"
DOCS_OUT_PATH = ROOT / "docs" / "assets" / "data" / "pilot" / f"{SOURCE}.json"


TEXT_FIXES = {
    "Phage, era": "Phage era",
    "sobre influência": "sob influência",
    "sobre os cuidados": "sob os cuidados",
    "ao invés": "em vez",
    "Ao invés": "Em vez",
    "a Cabala agora": "à Cabala agora",
    "a luz": "à luz",
    "platéia": "plateia",
    "criaram a o lendário": "criaram o lendário",
    "foice do Patriarca": "da foice do Patriarca",
    "se seguia": "seguia",
    "surpreendidos": "surpreendidas",
    "ele conseguiram": "eles conseguiram",
    "os, antes unidos, exércitos": "os exércitos antes unidos",
    "seus novo destino": "seu novo destino",
    "porque da viúva": "porquê da viúva",
    "por que eu carrego": "porque eu carrego",
    "ainda sim": "ainda assim",
    "varias": "várias",
    "a muito morto": "há muito morto",
    "mágica que se tornou Karona": "magia que se tornou Karona",
    "do a muito morto": "do há muito morto",
    "iria da a luz": "iria dar à luz",
    "iria da à luz": "iria dar à luz",
    "Otaria": "Otária",
    "Sanctum-": "Sanctum - ",
    "ferimento-": "ferimento - ",
    "artes de dos mares": "artes dos mares",
    "a um tempo atrás": "há algum tempo",
    "nêmese": "nêmesis",
    "nemesis": "nêmesis",
    "maculas": "máculas",
    "Kuberr": "Kuberr",
}


DROP_PATTERNS = [
    re.compile(r"^\d{2}/\d{2}/\d{2}$"),
    re.compile(r"^El Gato$", re.I),
]


def normalize_text(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = text.replace("“", '"').replace("”", '"')
    text = text.replace("–", "-").replace("—", "-")
    for old, new in TEXT_FIXES.items():
        text = text.replace(old, new)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"\s+-\s+", " - ", text)
    return text


def raw_paragraphs() -> list[str]:
    values: list[str] = []
    for paragraph in Document(SOURCE_PATH).paragraphs:
        text = paragraph.text.strip()
        if not text:
            continue
        values.extend(line.strip() for line in text.splitlines() if line.strip())
    return values


def clean(values: Iterable[str]) -> list[str]:
    paragraphs: list[str] = []
    for value in values:
        text = normalize_text(value)
        if not text:
            continue
        if any(pattern.search(text) for pattern in DROP_PATTERNS):
            continue
        paragraphs.append(text)
    return paragraphs


def block(block_id: str, title: str, area: str, paragraphs: list[str]) -> dict:
    return {"id": slugify(block_id), "title": title, "area": area, "paragraphs": paragraphs}


def item(title: str, area: str, kind: str, paragraphs: list[str], sections: list[dict]) -> dict:
    return {
        "id": slugify(title),
        "title": title,
        "area": area,
        "kind": kind,
        "sectionId": "cenario",
        "sectionTitle": "Cenário",
        "paragraphs": paragraphs,
        "sections": sections,
    }


def build_payload() -> dict:
    paragraphs = clean(raw_paragraphs())

    sections = [
        block(
            "origem-e-transformacao",
            "Origem e Transformação",
            "cenarios_lore",
            paragraphs[0:3],
        ),
        block(
            "kamahl-coliseu-akroma",
            "Kamahl, o Coliseu e Akroma",
            "cenarios_lore",
            paragraphs[3:10],
        ),
        block(
            "vermes-da-morte",
            "Vormes da Morte",
            "cenarios_lore",
            paragraphs[10:12],
        ),
        block(
            "sanctum-e-kuberr",
            "Sanctum e Kuberr",
            "cenarios_lore",
            paragraphs[12:25],
        ),
        block(
            "queda-do-patriarca",
            "Queda do Patriarca",
            "cenarios_lore",
            paragraphs[25:31],
        ),
        block(
            "batalha-final",
            "Batalha Final",
            "cenarios_lore",
            paragraphs[31:],
        ),
        block(
            "personagens-citados",
            "Personagens Citados",
            "cenarios_lore",
            [
                "Phage/Jeska: protagonista da narrativa, transformada pela Cabala e marcada por toque mortal.",
                "Kamahl: irmão de Jeska, envolvido nas tentativas de salvar ou deter Phage.",
                "Patriarca da Cabala: líder da organização, ligado à criação de Phage e ao nascimento de Kuberr.",
                "Braids: assecla da Cabala e agente importante nas tramas contra Phage e Akroma.",
                "Akroma: adversária principal de Phage, criada por Ixidor.",
                "Kuberr: deus/numena ligado à Cabala, destinado a nascer por meio de Phage.",
            ],
        ),
    ]
    lore = item(
        "Cenários/Lore - Phage",
        "cenarios_lore",
        "setting",
        [paragraph for section in sections for paragraph in section["paragraphs"]],
        sections,
    )
    counts = Counter(section["area"] for section in [lore])
    return {
        "version": 1,
        "source": SOURCE,
        "title": TITLE,
        "sourceFile": SOURCE_PATH.name,
        "sourcePath": str(SOURCE_PATH.relative_to(ROOT)),
        "status": "pilot_review",
        "summary": "Narrativa biográfica de Phage/Jeska, sua transformação pela Cabala, rivalidade com Akroma e ligação com Kuberr.",
        "areas": ["cenarios_lore"],
        "groups": [],
        "sections": [lore],
        "counts": dict(counts),
        "reviewNotes": [
            "Documento é lore narrativo contínuo; não contém ficha mecânica para criar NPC.",
            "Blocos foram divididos cronologicamente para facilitar leitura sem fragmentar a personagem em entidades artificiais.",
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
