#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix_anjos_aprimoramentos_rebuild.py

Rebuilds the 24 aprimoramentos in anjos-a-cidade-de-prata.json from scratch.
Problem: existing JSON has each entry containing the content of the NEXT aprimoramento.
Solution: replace all 24 with correctly parsed content from data/text/.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

BASE      = Path(__file__).resolve().parents[1]
TEXT_PATH = BASE / "data" / "text" / "anjos-a-cidade-de-prata.txt"
JSON_PATH = BASE / "data" / "pilot" / "anjos-a-cidade-de-prata.json"
DOCS_PATH = BASE / "docs" / "assets" / "data" / "pilot" / "anjos-a-cidade-de-prata.json"

EXPECTED_COUNT = 24
EXPECTED_IDS = [
    "afinidade-com-fadas", "alma-dupla", "ambidestria", "biblioteca-arcana",
    "clero", "contatos", "deteccao-de-magia", "gargula",
    "guardiao-de-um-artefato-importante", "local-de-controle",
    "objetos-magicos", "pactos", "palavra-de-deus",
    "pertencer-a-uma-escola-de-magia", "pertencer-ou-comandar-uma-seita",
    "poderes-magicos", "sensitivo", "senso-de-direcao", "senso",
    "sentidos-agucados", "sortudo", "talento", "tutor", "pontos-de-fe",
]

OCR_FIXES = [
    (re.compile(r"AGI \[2D\] INT"),         "AGI [2D], INT"),
    (re.compile(r"\bSpiri[íi]um\b"),        "Spiritum"),
    (re.compile(r"INT\s*\[ID\+ó\)"),       "INT [1D+6]"),
    (re.compile(r"\bambidesíria\b"),        "ambidestria"),
    (re.compile(r"\bnfvel\b"),              "nível"),
    (re.compile(r"pode possui\b"),          "pode possuir"),
    (re.compile(r"\bDemónios\b"),           "Demônios"),
    (re.compile(r"\bgémeos\b"),             "gêmeos"),
    (re.compile(r"\bfenómenos\b"),          "fenômenos"),
    (re.compile(r"\brefugio\b"),            "refúgio"),
    (re.compile(r"\b1-1\s+pontos"),         "11 pontos"),
    (re.compile(r"\(l\s+dia\)"),            "(1 dia)"),
    (re.compile(r"\bl\s+ou\s+2\b"),        "1 ou 2"),
    (re.compile(r"^\\\s+ponto"),            "1 ponto"),
    (re.compile(r"\b3dó\b"),                "3d6"),
    (re.compile(r"\b2dó\b"),                "2d6"),
    (re.compile(r"\bdó\b"),                 "d6"),
    (re.compile(r"\bld6\b"),               "1d6"),
    (re.compile(r"\.\s+\."),               "."),
    (re.compile(r"exatamente o a\b"),       "exatamente a"),
]

NOISE_RE = re.compile(
    r"^---\s*page\s+\d+\s*---"
    r"|^[\s\^\-\.\|\\]*$"
    r"|^\d{1,2}\s*$"
    r"|^_+\s*$"
)

COST_TIER_RE = re.compile(
    r"^(?:\\ )?\d+\s+[Pp]onto"
    r"|^variável:"
    r"|\\\s+[Pp]onto"
)

def apply_ocr_fixes(text: str) -> str:
    for pattern, replacement in OCR_FIXES:
        text = pattern.sub(replacement, text)
    return text

def is_noise(line: str) -> bool:
    return bool(NOISE_RE.match(line.strip()))

def normalize_for_detection(line: str) -> str:
    line = re.sub(r"^\\\s+", "1 ", line)
    line = re.sub(r"^l\s+(?=ponto)", "1 ", line)
    return line

def is_new_cost_tier(line: str) -> bool:
    return bool(COST_TIER_RE.match(normalize_for_detection(line.strip())))

def join_soft_wrap(lines: list[str]) -> str:
    result = ""
    for line in lines:
        s = line.strip()
        if not s:
            continue
        if result.endswith("-") and not result.endswith("--"):
            result = result[:-1] + s
        elif result:
            result = result + " " + s
        else:
            result = s
    return result

def build_paragraphs_custo(raw_lines: list[str]) -> list[str]:
    paragraphs = []
    current = []

    for line in raw_lines:
        if is_noise(line):
            continue
        stripped = line.strip()
        if not stripped:
            continue
        if is_new_cost_tier(stripped) and current:
            para = join_soft_wrap(current)
            if para:
                paragraphs.append(apply_ocr_fixes(para))
            current = [stripped]
        else:
            current.append(stripped)

    if current:
        para = join_soft_wrap(current)
        if para:
            paragraphs.append(apply_ocr_fixes(para))

    return paragraphs

def build_paragraphs_descricao(ranges, all_lines) -> list[str]:
    paragraphs = []
    for start_1, end_1 in ranges:
        chunk = [
            l.strip()
            for l in all_lines[start_1 - 1 : end_1]
            if not is_noise(l) and l.strip()
        ]
        para = join_soft_wrap(chunk)
        if para:
            paragraphs.append(apply_ocr_fixes(para))
    return paragraphs

def build_entity(spec_id, spec_title, section_specs, all_lines):
    sections_out = []

    for sec_type, ranges in section_specs:
        if sec_type == "custo":
            raw = []
            for start_1, end_1 in ranges:
                raw.extend(all_lines[start_1 - 1 : end_1])
            paras = build_paragraphs_custo(raw)
            sections_out.append({
                "id": "custo",
                "title": "Custo",
                "area": "aprimoramentos",
                "paragraphs": paras,
            })
        else:
            paras = build_paragraphs_descricao(ranges, all_lines)
            sections_out.append({
                "id": "descricao",
                "title": "Descrição",
                "area": "aprimoramentos",
                "paragraphs": paras,
            })

    has_descricao = any(s["id"] == "descricao" for s in sections_out)
    section_id = "descricao" if has_descricao else "custo"

    custo_paras = next((s["paragraphs"] for s in sections_out if s["id"] == "custo"), [])
    desc_paras = []
    for s in sections_out:
        if s["id"] == "descricao":
            desc_paras.extend(s["paragraphs"])
    flat_paragraphs = custo_paras + desc_paras

    return {
        "id": spec_id,
        "title": spec_title,
        "area": "aprimoramentos",
        "kind": "enhancement",
        "sectionId": section_id,
        "sectionTitle": "Aprimoramento",
        "paragraphs": flat_paragraphs,
        "sections": sections_out,
    }

SPECS = [
    ("afinidade-com-fadas", "Afinidade com Fadas", [("custo", [(3328, 3344)])]),
    ("alma-dupla", "Alma Dupla", [("custo", [(3346, 3358)])]),
    ("ambidestria", "Ambidestria", [("custo", [(3360, 3368)])]),
    ("biblioteca-arcana", "Biblioteca Arcana", [("descricao", [(3370, 3378)]), ("custo", [(3379, 3387)])]),
    ("clero", "Clero", [("descricao", [(3389, 3395), (3396, 3397)]), ("custo", [(3398, 3424)])]),
    ("contatos", "Contatos", [("custo", [(3426, 3436)])]),
    ("deteccao-de-magia", "Detecção de Magia", [("custo", [(3438, 3443)])]),
    ("gargula", "Gárgula", [("custo", [(3447, 3452)]), ("descricao", [(3453, 3456)])]),
    ("guardiao-de-um-artefato-importante", "Guardião de um Artefato Importante", [("custo", [(3458, 3467)]), ("descricao", [(3468, 3474)])]),
    ("local-de-controle", "Local de Controle", [("custo", [(3476, 3483)])]),
    ("objetos-magicos", "Objetos Mágicos", [("descricao", [(3485, 3487)]), ("custo", [(3488, 3492)])]),
    ("pactos", "Pactos", [("custo", [(3494, 3500)]), ("descricao", [(3501, 3505)])]),
    ("palavra-de-deus", "Palavra de Deus", [("custo", [(3507, 3511)])]),
    ("pertencer-a-uma-escola-de-magia", "Pertencer a uma Escola de Magia", [("custo", [(3513, 3522)])]),
    ("pertencer-ou-comandar-uma-seita", "Pertencer ou Comandar uma Seita", [("custo", [(3528, 3535)])]),
    ("poderes-magicos", "Poderes Mágicos", [("descricao", [(3537, 3537)]), ("custo", [(3538, 3554)])]),
    ("sensitivo", "Sensitivo", [("descricao", [(3556, 3558)]), ("custo", [(3559, 3571)])]),
    ("senso-de-direcao", "Senso de Direção", [("custo", [(3573, 3577)])]),
    ("senso", "Senso", [("custo", [(3579, 3582)])]),
    ("sentidos-agucados", "Sentidos Aguçados", [("custo", [(3584, 3590)])]),
    ("sortudo", "Sortudo", [("custo", [(3592, 3596)])]),
    ("talento", "Talento", [("custo", [(3598, 3600)])]),
    ("tutor", "Tutor", [("descricao", [(3602, 3611)]), ("custo", [(3612, 3627)])]),
    ("pontos-de-fe", "Pontos de Fé", [("custo", [(4996, 5000)]), ("descricao", [(4977, 4980), (4981, 4988), (4989, 4995), (5001, 5006), (5007, 5009), (5010, 5012), (5013, 5017), (5018, 5020), (5021, 5024)])]),
]

def main() -> None:
    print(f"Reading: {TEXT_PATH}")
    raw_text = TEXT_PATH.read_text(encoding="utf-8")
    all_lines = [l.rstrip("\n\r") for l in raw_text.splitlines(keepends=True)]
    print(f"  {len(all_lines)} lines in text file.")

    print("\nBuilding aprimoramentos...")
    new_entities = []
    for spec_id, spec_title, section_specs in SPECS:
        entity = build_entity(spec_id, spec_title, section_specs, all_lines)
        new_entities.append(entity)
        custo_sec = next((s for s in entity["sections"] if s["id"] == "custo"), None)
        desc_sec = next((s for s in entity["sections"] if s["id"] == "descricao"), None)
        n_c = len(custo_sec["paragraphs"]) if custo_sec else 0
        n_d = len(desc_sec["paragraphs"]) if desc_sec else 0
        print(f"  [{spec_id}] custo={n_c}, desc={n_d}")

    assert len(new_entities) == EXPECTED_COUNT
    produced_ids = [e["id"] for e in new_entities]
    assert produced_ids == EXPECTED_IDS

    for e in new_entities:
        custo = next((s for s in e["sections"] if s["id"] == "custo"), None)
        assert custo and custo["paragraphs"]

    print(f"\nValidation passed — {EXPECTED_COUNT} aprimoramentos rebuilt correctly.\n")

    print(f"Loading: {JSON_PATH}")
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    sections = data["sections"]

    old_count = sum(1 for e in sections if e.get("area") == "aprimoramentos")
    print(f"  Replacing {old_count} corrupted entries...")

    insert_idx = next((i for i, e in enumerate(sections) if e.get("area") == "aprimoramentos"), len(sections))
    before = [e for e in sections[:insert_idx] if e.get("area") != "aprimoramentos"]
    after = [e for e in sections[insert_idx:] if e.get("area") != "aprimoramentos"]
    data["sections"] = before + new_entities + after

    final_count = sum(1 for e in data["sections"] if e.get("area") == "aprimoramentos")
    assert final_count == EXPECTED_COUNT

    data["areaCounts"]["aprimoramentos"] = EXPECTED_COUNT
    data["generatedAt"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    json_str = json.dumps(data, ensure_ascii=False, indent=2)
    for path in (JSON_PATH, DOCS_PATH):
        path.write_text(json_str + "\n", encoding="utf-8")
        print(f"Saved: {path}")

    print(f"\nDone. {EXPECTED_COUNT} aprimoramentos rebuilt successfully.")

if __name__ == "__main__":
    main()
