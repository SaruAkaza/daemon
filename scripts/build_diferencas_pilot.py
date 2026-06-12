from __future__ import annotations

import re
import shutil
from collections import Counter
from datetime import UTC, datetime
from typing import Iterable

from docx import Document

from common import ROOT, slugify, write_json


SOURCE = "diferencas"
TITLE = "Diferenças"
SOURCE_CANDIDATES = [
    ROOT / "Livros" / "word" / "Diferencas_OCR_alta_qualidade.docx",
    ROOT / "Livros" / "word" / "feito" / "Diferencas_OCR_alta_qualidade.docx",
]
SOURCE_PATH = next((path for path in SOURCE_CANDIDATES if path.exists()), SOURCE_CANDIDATES[0])
OUT_PATH = ROOT / "data" / "pilot" / f"{SOURCE}.json"
DOCS_OUT_PATH = ROOT / "docs" / "assets" / "data" / "pilot" / f"{SOURCE}.json"


TEXT_FIXES = {
    "Diferencas": TITLE,
    "MAYTRÉIA - AS DIFERENÇAS ENTRE OS DIVERSOS SERES DOS PLANOS": "Maytréia - As Diferenças entre os Diversos Seres dos Planos",
    "identifica-los": "identificá-los",
    "Não devemos no entanto": "Não devemos, no entanto,",
    "não se manifestar fisicamente": "não se manifestar fisicamente",
    "jogadores e Mestre esta flexibilidade": "jogadores e Mestre essa flexibilidade",
    "Não está preso a lei": "Não está preso à lei",
    "www.Daemon.com.br": "www.daemon.com.br",
    "www.universogerminante.net .": "www.universogerminante.net.",
}

PAGE_RE = re.compile(r"^Página\s+\d+$", flags=re.IGNORECASE)


def normalize_text(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = text.replace("\r", "\n")
    for old, new in TEXT_FIXES.items():
        text = text.replace(old, new)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return text.strip()


def raw_paragraphs() -> list[str]:
    return [paragraph.text.strip() for paragraph in Document(SOURCE_PATH).paragraphs if paragraph.text.strip()]


def clean(values: Iterable[str]) -> list[str]:
    return [text for value in values if (text := normalize_text(value))]


def content_paragraphs() -> list[str]:
    ignored = {
        TITLE,
        "Fonte: Diferencas.pdf | páginas processadas: 2",
        "Para maiores informações sobre o jogo Maytréia acesse os seguintes sites: www.daemon.com.br e www.universogerminante.net. Até a próxima.",
    }
    return [
        paragraph
        for paragraph in clean(raw_paragraphs())
        if paragraph not in ignored
        and not PAGE_RE.match(paragraph)
        and not paragraph.startswith("Fonte:")
    ]


def block(block_id: str, title: str, area: str, paragraphs: list[str]) -> dict:
    return {"id": slugify(block_id), "title": title, "area": area, "paragraphs": paragraphs}


def item(
    title: str,
    area: str,
    kind: str,
    section_title: str,
    paragraphs: list[str],
    sections: list[dict],
) -> dict:
    return {
        "id": slugify(title),
        "title": title,
        "area": area,
        "kind": kind,
        "sectionId": slugify(section_title),
        "sectionTitle": section_title,
        "paragraphs": paragraphs,
        "sections": sections,
    }


def comparison_lines() -> list[str]:
    return [
        "Natureza | Elemental: Faz parte da fauna do plano. | Elementar: Surge de pensamentos e/ou sentimentos simples de uma pessoa. | Conceito: Manifesta-se de planos superiores (Hierarquia Intuitiva). | Egrégora: É a resultante psíquica de 2 ou mais mentes.",
        "Vínculo | Elemental: Segue as leis do seu plano de origem. | Elementar: Tenta cumprir o objetivo pensado. | Conceito: Não está preso à lei do plano e já surge completo; pode ser vivido ou ignorado pela humanidade. | Egrégora: É criada com uma intenção e existe apenas para ela.",
        "Influência | Elemental: Afeta apenas o seu plano de origem. | Elementar: Afeta apenas o seu plano de origem. | Conceito: Pode afetar outros planos através da humanidade. | Egrégora: Afeta diretamente a humanidade em qualquer plano.",
        "Poder | Elemental: Poder mínimo. | Elementar: Poder mínimo, mas pode crescer conforme seu objetivo é repetido pelo invocador. | Conceito: Poder que pode afetar a Maya como um todo, mas pode precisar de humanos para sua defesa. | Egrégora: Grande capacidade de manipulação de massas e defesa impressionante.",
        "Relação com a humanidade | Elemental: Indiferente à existência humana. | Elementar: Depende completamente de quem pensa nele. | Conceito: Surge independentemente, mas depende da humanidade para sua manifestação. | Egrégora: Tem relação simbiótica com a humanidade, influenciando e sendo influenciada por ela.",
        "Manifestação | Elemental: Não sai de seu plano. | Elementar: Não sai de seu plano. | Conceito: Atua no plano mental, mas se origina do Intuitivo e influencia os planos mais densos. | Egrégora: Surge nos planos astral e mental ao mesmo tempo e influencia o físico e o etérico.",
    ]


def build_payload() -> dict:
    paragraphs = content_paragraphs()
    title = paragraphs[0]
    intro = paragraphs[:6]
    sections = [
        item(
            "Cenarios/Lore - Diferenças",
            "cenarios_lore",
            "setting",
            "Cenários/Lore",
            [*intro, *comparison_lines()],
            [
                block("introducao", "Introdução", "cenarios_lore", intro),
                block("classificacao-comparativa", "Classificação Comparativa", "cenarios_lore", comparison_lines()),
            ],
        )
    ]
    counts = Counter(section["area"] for section in sections)
    return {
        "version": 1,
        "source": SOURCE,
        "title": TITLE,
        "sourceFile": SOURCE_PATH.name,
        "sourcePath": str(SOURCE_PATH.relative_to(ROOT)),
        "status": "pilot_review",
        "summary": "Texto de Maytréia que diferencia Elementais, Elementares, Conceitos e Egrégoras nos planos.",
        "areas": sorted(counts),
        "groups": [],
        "sections": sections,
        "counts": dict(counts),
        "reviewNotes": [
            f"Título interno preservado no bloco de introdução: {title}.",
            "A tabela do OCR foi reconstruída como comparação textual por linhas, mantendo os quatro tipos e seus critérios.",
            "Não foram criadas criaturas/NPCs porque o texto não apresenta fichas, atributos ou estatísticas individuais.",
        ],
        "generatedAt": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }


def move_source_to_done() -> None:
    done_dir = ROOT / "Livros" / "word" / "feito"
    done_dir.mkdir(parents=True, exist_ok=True)
    source_in_word = ROOT / "Livros" / "word" / "Diferencas_OCR_alta_qualidade.docx"
    if source_in_word.exists():
        shutil.move(str(source_in_word), str(done_dir / source_in_word.name))


def main() -> None:
    payload = build_payload()
    write_json(OUT_PATH, payload)
    write_json(DOCS_OUT_PATH, payload)
    move_source_to_done()
    print(f"Wrote {OUT_PATH}")
    print(f"Wrote {DOCS_OUT_PATH}")
    print(f"Sections: {len(payload['sections'])}")


if __name__ == "__main__":
    main()
