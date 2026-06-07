from __future__ import annotations

import re
from collections import Counter
from datetime import UTC, datetime
from typing import Iterable

from docx import Document

from common import ROOT, slugify, write_json


SOURCE = "cabala-forum"
TITLE = "Cabala"
SOURCE_CANDIDATES = [
    ROOT / "Livros" / "word" / "cabala.docx",
    ROOT / "Livros" / "word" / "feito" / "cabala.docx",
]
SOURCE_PATH = next((path for path in SOURCE_CANDIDATES if path.exists()), SOURCE_CANDIDATES[0])
OUT_PATH = ROOT / "data" / "pilot" / f"{SOURCE}.json"
DOCS_OUT_PATH = ROOT / "docs" / "assets" / "data" / "pilot" / f"{SOURCE}.json"


TEXT_FIXES = {
    "Ae": "Aí",
    "posta..": "poste.",
    "posta aqui !!!": "poste aqui.",
    "Otaria": "Otária",
    "politicamente corretos...como": "politicamente corretos, como",
    "poderosissíma": "poderosíssima",
    "olhando pra": "olhando para",
    "oq": "o que",
    "vc": "você",
    "mi diz ond c viu isso??!!": "me diz onde você viu isso?",
    "c for verdade dahora + axo q eh viagem": "se for verdade é interessante, mas acho que é viagem",
    "liças": "liças",
    "dicionario": "dicionário",
    "nao": "não",
    "so lugar": "só lugar",
    "involvida": "envolvida",
    "richas": "rixas",
    "frequêntemente": "frequentemente",
    "certim": "certinho",
    "entao": "então",
    "pelo q": "pelo que",
    "nao!a": "não! A",
    "eh": "é",
    "c fosse": "se fosse",
    "naçao": "nação",
    "propria": "própria",
    "cefálidas": "cefálidas",
    "barbaros": "bárbaros",
    "nomades": "nômades",
    "d todo": "de todo",
    "construçao": "construção",
    "ilustracao": "ilustração",
    "predios": "prédios",
    "muros esternos": "muros externos",
    "nao fica": "não fica",
    "mtttooo": "muito",
    "qanto": "quanto",
    "intende": "entende",
    "voce": "você",
    "aonde vocês pegaram essas informções": "onde vocês pegaram essas informações",
    "historia": "história",
    "ja": "já",
}


DROP_PATTERNS = [
    re.compile(r"^\d{2}/\d{2}/\d{2}$"),
    re.compile(r"^(Enhvriwnl|thallis -|Luciano|\[F\.N\.T\.D\] #joao#)$", re.I),
    re.compile(r"^(mais ou menos isso:|então|Ênfase no reply do João\.)$", re.I),
    re.compile(r"^\*+"),
    re.compile(r"\bmsn\b", re.I),
]


def normalize_text(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = text.replace("...nada", ", nada")
    text = text.replace("...se", ", se")
    text = text.replace("...um", ", um")
    for old, new in TEXT_FIXES.items():
        text = text.replace(old, new)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
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
    cleaned = clean(raw_paragraphs())
    overview = [
        "A Cabala foi uma organização criada depois do Apocalipse, no continente de Otária. Seu líder era o Patriarca da Cabala.",
        "A organização buscava controlar o continente e disputava influência com a Ordem, descrita como formada por nômades e soldados brancos de Odisseia.",
        "Seus métodos incluíam tortura, necromancia e poderes mentais para controlar regiões, comércio e redes de influência.",
    ]
    members = [
        "Patriarca da Cabala: chefe da organização.",
        "Braids: invocadora de demência e assecla poderosa, associada à loucura.",
        "Chainer: membro capaz de trazer seus pesadelos para o mundo real.",
        "Phage, a Intocável: identificada como Jeska, irmã de Kamal, transformada pela Cabala.",
    ]
    places = [
        "Aphetto é descrita como uma região de pântanos e ilhas, usada como base de operações da Cabala.",
        "As liças da Cabala aparecem como arenas de luta; o Grande Coliseu é citado como projeto maior, ligado a apostas e lucro de investidores do continente.",
        "A Cabala mantinha membros espalhados como rede de espionagem e controle regional.",
    ]
    conflicts = [
        "A Cabala disputava influência com a Ordem e possuía rixas com os Cefálidas.",
        "O conflito é descrito mais como uma Guerra Fria do que como guerra aberta constante.",
        "Com o surgimento de Karona, a Cabala perde membros para novas alianças e Otária passa por guerras e devastações.",
    ]
    open_questions = [
        "O material preserva perguntas sobre a localização da cidadela da Cabala, detalhes de Braids e diferenças exatas entre liças e Grande Coliseu.",
        "Como o documento é um recorte de conversa, essas perguntas foram mantidas como pendências de lore, não como fatos consolidados.",
    ]

    source_notes = [
        f"O DOCX original possui {len(cleaned)} linhas úteis extraídas de uma conversa de fórum.",
        "A conversa foi consolidada em tópicos de lore para evitar exibir abreviações, perguntas repetidas e ruído de chat na aplicação.",
    ]

    sections = [
        block("visao-geral", "Visão Geral", "cenarios_lore", overview),
        block("membros-citados", "Membros Citados", "cenarios_lore", members),
        block("locais-e-influencia", "Locais e Influência", "cenarios_lore", places),
        block("conflitos", "Conflitos", "cenarios_lore", conflicts),
        block("duvidas-abertas", "Dúvidas Abertas", "cenarios_lore", open_questions),
        block("notas-da-fonte", "Notas da Fonte", "cenarios_lore", source_notes),
    ]
    lore = item(
        "Cenários/Lore - Cabala",
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
        "summary": "Recorte de conversa sobre a organização Cabala, seu papel em Otária, membros citados, locais de influência e conflitos.",
        "areas": ["cenarios_lore"],
        "groups": [],
        "sections": [lore],
        "counts": dict(counts),
        "reviewNotes": [
            "Documento é uma conversa de fórum; foi tratado como lore consolidado com bloco de fonte, não como regra mecânica.",
            "Membros citados não possuem ficha própria, portanto não foram criados como NPCs.",
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
