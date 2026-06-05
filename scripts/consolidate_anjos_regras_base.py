#!/usr/bin/env python3
"""Consolidate regras_base entries in anjos-a-cidade-de-prata.json."""

import copy
import json
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = ROOT / "data" / "pilot" / "anjos-a-cidade-de-prata.json"
DOCS_PATH = ROOT / "docs" / "assets" / "data" / "pilot" / "anjos-a-cidade-de-prata.json"

SOURCE_GROUP_ID = "regra-base-anjos-cidade-prata"
USOS_GROUP_ID = "usos-de-pontos-de-fe"

HEADING_CORRECTIONS = {
    "BÊNÇÃO": "Bênção",
    "CONTROLAR HIORTOS-Vivos": "Controlar Mortos-Vivos",
    "CONVERSAR com PÁSSAROS E ANIMAIS": "Conversar com Pássaros e Animais",
    "CURA": "Cura",
    "CRIAÇÃO DE ÁGUA BENTA": "Criação de Água Benta",
    "ENCANTAR": "Encantar",
}

CONCATENATED_PREFIXES = {
    "Ativação de Itens Mágicos ": "Ativação de Itens Mágicos",
    "OUTRS PDfiRfiS ": "Outros Poderes",
}

BODY_FIXES = [
    ("l Ponto de Fé", "1 Ponto de Fé"),
    ("urna rodada", "uma rodada"),
    ("animaldurante", "animal durante"),
]

BLEED_SENTINELS = (
    "Regras e Testes",
    "TESTES",
    "Por mais cautelosos",
    "As regras são simples",
)

COST_OVERRIDES = {
    "Bênção": "1 Ponto de Fé",
    "Controlar Mortos-Vivos": "1 Ponto de Fé",
    "Conversar com Pássaros e Animais": "1 Ponto de Fé",
    "Cura": "1-2 Pontos de Fé",
    "Criação de Água Benta": "1 Ponto de Fé por frasco",
    "Encantar": "Variável",
}

EFFECT_MAP = {
    "Ativação de Itens Mágicos": "Ativa artefatos que requerem Pontos de Fé; apenas personagens com Fé podem usá-los",
    "Bênção": "+5% na Defesa para até 6 pessoas por PF durante uma cena",
    "Controlar Mortos-Vivos": "Comandar criaturas mortas-vivas durante uma cena",
    "Conversar com Pássaros e Animais": "Comunicar-se com um animal durante um curto período de tempo",
    "Cura": "1d6 PVs em si mesmo (1 PF/dia) ou em outra pessoa (2 PF, via toque)",
    "Criação de Água Benta": "1 frasco de água benta por Ponto de Fé gasto",
    "Encantar": "Arma torna-se +1 durante uma cena (3d6 rodadas)",
    "Outros Poderes": "Imita qualquer milagre de santo; o Personagem deve merecê-lo",
}

def slugify(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_val = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-zA-Z0-9]+", "-", ascii_val).strip("-").lower() or "untitled"

def apply_body_fixes(text: str) -> str:
    for bad, good in BODY_FIXES:
        text = text.replace(bad, good)
    return text

def is_bleed(para: str) -> bool:
    return any(para == s or para.startswith(s) for s in BLEED_SENTINELS)

def extract_cost(body: str) -> str | None:
    hits = re.findall(r"(\d+)\s+Pont[oa]s?\s+de\s+F[ée]", body, re.IGNORECASE)
    if len(hits) >= 2:
        nums = sorted({int(h) for h in hits})
        if len(nums) == 2:
            return f"{nums[0]}-{nums[1]} Pontos de Fé"
        n = nums[0]
        return f"{n} {'Ponto' if n == 1 else 'Pontos'} de Fé"
    if len(hits) == 1:
        n = int(hits[0])
        return f"{n} {'Ponto' if n == 1 else 'Pontos'} de Fé"
    if re.search(r"\bum\s+[Pp]onto\s+de\s+F[ée]\b", body):
        return "1 Ponto de Fé"
    if re.search(r"\bcada\s+ponto\s+gasto\b", body, re.IGNORECASE):
        return "1 Ponto de Fé por frasco"
    return None

def build_block(title: str, body_parts: list[str]) -> dict:
    body = apply_body_fixes(" ".join(p.strip() for p in body_parts if p.strip()))
    details = {}

    cost = COST_OVERRIDES.get(title) or extract_cost(body)
    if cost:
        details["Custo"] = cost

    if re.search(r"Inquisidor", body):
        details["Quem"] = "Inquisidor"
    elif re.search(r"Necromântico|clérigo", body, re.IGNORECASE):
        details["Quem"] = "Necromântico / Clérigo"
    elif re.search(r"Personagem", body):
        details["Quem"] = "Personagem com Fé"

    if title in EFFECT_MAP:
        details["Efeito"] = EFFECT_MAP[title]

    block = {"id": slugify(title), "title": title}
    if details:
        block["details"] = details
    block["paragraphs"] = [body] if body else []
    return block

def parse_usos(paragraphs: list[str]) -> tuple[list[str], list[dict]]:
    intro = []
    blocks = []
    current_title = None
    current_body = []

    def flush():
        nonlocal current_title, current_body
        if current_title is not None:
            blocks.append(build_block(current_title, current_body))
        current_title = None
        current_body = []

    for raw in paragraphs:
        para = raw.strip()
        if not para:
            continue

        if is_bleed(para):
            flush()
            return intro, blocks

        matched_concat = False
        for prefix, corrected_title in CONCATENATED_PREFIXES.items():
            if para.startswith(prefix):
                flush()
                current_title = corrected_title
                body_text = para[len(prefix):].strip()
                current_body = [body_text] if body_text else []
                matched_concat = True
                break
        if matched_concat:
            continue

        corrected = HEADING_CORRECTIONS.get(para)
        if corrected is not None:
            flush()
            current_title = corrected
            current_body = []
            continue

        if current_title is None:
            intro.append(apply_body_fixes(para))
        else:
            current_body.append(para)

    flush()
    return intro, blocks

def build_usos_section(usos_group: dict) -> dict:
    raw_paragraphs = usos_group.get("paragraphs", [])
    intro_paragraphs, blocks = parse_usos(raw_paragraphs)
    return {
        "id": "usos-de-pontos-de-fe",
        "title": "Usos de Pontos de Fé",
        "area": "regras_base",
        "paragraphs": intro_paragraphs,
        "blocks": blocks,
    }

def consolidate(data: dict) -> dict:
    data = copy.deepcopy(data)
    groups = data.get("groups", [])
    sections = data.get("sections", [])

    source_group = None
    usos_group = None

    # Look for source group in groups
    for g in groups:
        gid = g.get("id")
        if gid == SOURCE_GROUP_ID:
            source_group = g
            break

    # Look for usos_group in both groups and sections
    for g in groups:
        if g.get("id") == USOS_GROUP_ID:
            usos_group = g
            break

    if usos_group is None:
        for s in sections:
            if s.get("id") == USOS_GROUP_ID:
                usos_group = s
                break

    if source_group is None:
        sys.exit(f"ERROR: group '{SOURCE_GROUP_ID}' not found.")
    if usos_group is None:
        sys.exit(f"ERROR: section/group '{USOS_GROUP_ID}' not found.")

    usos_section = build_usos_section(usos_group)
    sections_in_group = source_group.get("sections", [])
    sections_in_group = [s for s in sections_in_group if s.get("id") != "usos-de-pontos-de-fe"]
    sections_in_group.append(usos_section)
    source_group["sections"] = sections_in_group

    # Remove from top-level groups
    data["groups"] = [g for g in groups if g.get("id") != USOS_GROUP_ID]

    # Remove from top-level sections
    data["sections"] = [s for s in data.get("sections", []) if s.get("id") != USOS_GROUP_ID]

    area_counts = data.get("areaCounts", {})
    if area_counts.get("regras_base", 0) > 1:
        area_counts["regras_base"] -= 1
    data["areaCounts"] = area_counts

    data["generatedAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

    return data

def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))

def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"  Written: {path}")

def main() -> None:
    print(f"Loading {JSON_PATH}")
    data = load_json(JSON_PATH)
    result = consolidate(data)

    print("Writing output files...")
    write_json(JSON_PATH, result)
    write_json(DOCS_PATH, result)

    print("\nConsolidation complete!")
    rb_count = result.get("areaCounts", {}).get("regras_base", "?")
    main_group = next((g for g in result.get("groups", []) if g["id"] == SOURCE_GROUP_ID), None)
    n_sections = len(main_group["sections"]) if main_group else "?"
    print(f"  regras_base count: {rb_count}")
    print(f"  Sections in main group: {n_sections}")

if __name__ == "__main__":
    main()
