"""catalog_loader — shared constants and I/O lookup functions.

All path constants, area/category mappings, normalization utilities, and
source-level lookups live here so catalog_processor and build_area_catalog
can import them without pulling in heavy processing logic.
"""
from __future__ import annotations

import re
from typing import Any

from common import DATA_DIR, INDEX_DIR, slugify, read_json


BOOKS_DATA_DIR = DATA_DIR / "books"
ENTITIES_DIR = DATA_DIR / "entities"
AREAS_DIR = DATA_DIR / "areas"
WORK_DIR = DATA_DIR / "work"

AREA_LABELS = {
    "regras_base": "Regras Base",
    "aprimoramentos": "Aprimoramentos",
    "kits": "Kits",
    "classes": "Classes",
    "racas": "Racas",
    "linhagens": "Linhagens",
    "poderes": "Poderes",
    "magias": "Magias",
    "rituais": "Rituais",
    "itens_equipamentos": "Itens e Equipamentos",
    "criaturas_npcs": "Criaturas e NPCs",
    "cenarios_lore": "Cenarios e Lore",
    "aventuras": "Aventuras",
    "tabelas": "Tabelas e Geradores",
}

CATEGORY_TO_AREA = {
    "source": "regras_base",
    "core_rule": "regras_base",
    "attribute_skill": "regras_base",
    "combat": "regras_base",
    "character_option": "aprimoramentos",
    "character_class": "classes",
    "kit_class": "kits",
    "race_lineage": "racas",
    "power_magic": "poderes",
    "ritual_spell": "rituais",
    "item_equipment": "itens_equipamentos",
    "creature_npc": "criaturas_npcs",
    "setting_lore": "cenarios_lore",
    "adventure": "aventuras",
    "table_generator": "tabelas",
}

AREA_KEYWORDS = [
    ("regras_base", ("regra", "regras", "sistema", "modulo", "daemon", "atributo", "atributos", "pericia", "pericias", "especializacao", "especializacoes", "combate", "manobra", "manobras", "ataque", "defesa", "dano")),
    ("aprimoramentos", ("aprimoramento", "aprimoramentos", "vantagem", "desvantagem", "talento", "talentos")),
    ("classes", ("classe", "classes", "classe de prestigio", "profissao", "profissoes", "ocupacao", "ocupacoes")),
    ("kits", ("kit", "kits", "arquetipo", "arquetipos")),
    ("racas", ("raca", "racas", "elfo", "elfos", "anao", "anoes", "sprite", "sereia", "orc", "goblin", "ogre")),
    ("linhagens", ("linhagem", "linhagens", "vampiro", "vampiros", "youkai", "youkais", "imortal", "imortais", "fera", "feras")),
    ("rituais", ("ritual", "rituais", "grimorio", "invocacao", "encantamento", "circulo", "circulos")),
    ("poderes", ("poder", "poderes", "superpoder", "superpoderes", "psiquismo", "psionico", "milagre", "reiatsu")),
    ("magias", ("magia", "magias", "caminho", "caminhos", "kidou", "kidous", "focus", "feitico", "feiticos")),
    ("itens_equipamentos", ("item", "itens", "equipamento", "equipamentos", "arma", "armas", "armadura", "veiculo", "veiculos")),
    ("criaturas_npcs", ("criatura", "criaturas", "monstro", "monstros", "npc", "npcs", "demonio", "anjos", "dragao", "dragoes")),
    ("aventuras", ("aventura", "aventuras", "campanha", "campanhas", "cenario pronto", "quick start")),
    ("tabelas", ("tabela", "tabelas", "gerador", "geradores", "aleatorio", "aleatorios")),
]

SOURCE_FAMILY_LABELS = {
    "official_core": "Oficiais / linha principal",
    "rules_system": "Regras e sistema",
    "equipment_items": "Equipamentos, armas e itens",
    "creatures_bestiary": "Criaturas, monstros e NPCs",
    "powers_magic": "Poderes, magia e rituais",
    "races_options": "Raças, kits e opções de personagem",
    "campaign_adventure": "Campanhas e aventuras",
    "setting_lore": "Cenários, lore e organizações",
    "myth_history": "Mitologia, história e religião",
    "adaptation_pop": "Adaptações, anime, supers e cultura pop",
    "supplement_misc": "Suplementos gerais",
}

TITLE_LOWERCASE_WORDS = {"a", "as", "ao", "aos", "com", "da", "das", "de", "do", "dos", "e", "em", "na", "nas", "no", "nos", "para", "por"}
TEXT_ACRONYMS = {
    "agi": "AGI",
    "car": "CAR",
    "con": "CON",
    "dex": "DEX",
    "fbi": "FBI",
    "fr": "FR",
    "int": "INT",
    "ip": "IP",
    "npc": "NPC",
    "npcs": "NPCs",
    "per": "PER",
    "pm": "PM",
    "pms": "PMs",
    "pv": "PV",
    "pvs": "PVs",
    "will": "WILL",
}


def normalize_for_search(value: str) -> str:
    return slugify(value).replace("-", " ")


def uppercase_ratio(value: str) -> float:
    letters = [char for char in value if char.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for char in letters if char.isupper()) / len(letters)


def is_mostly_uppercase(value: str, minimum_letters: int = 8, threshold: float = 0.78) -> bool:
    letters = [char for char in value if char.isalpha()]
    return len(letters) >= minimum_letters and uppercase_ratio(value) >= threshold


def normalize_uppercase_name(value: str) -> str:
    if not is_mostly_uppercase(value, minimum_letters=4):
        return value
    words = value.lower().split()
    normalized: list[str] = []
    for index, word in enumerate(words):
        if index > 0 and word in TITLE_LOWERCASE_WORDS:
            normalized.append(word)
        else:
            normalized.append(word[:1].upper() + word[1:])
    return " ".join(normalized)


def normalize_uppercase_text(value: str) -> str:
    if not is_mostly_uppercase(value, minimum_letters=20):
        return value
    text = value.lower()
    for source, replacement in TEXT_ACRONYMS.items():
        text = re.sub(rf"\b{re.escape(source)}\b", replacement, text, flags=re.IGNORECASE)

    def capitalize_match(match: re.Match[str]) -> str:
        return f"{match.group(1)}{match.group(2).upper()}"

    return re.sub(r"(^|[.!?]\s+)([a-zà-ÿ])", capitalize_match, text)


def normalize_display_entries(entries: list[Any]) -> list[Any]:
    return [normalize_uppercase_text(entry) if isinstance(entry, str) else entry for entry in entries]


def duplicate_map() -> dict[str, str]:
    report = read_json(INDEX_DIR / "deleted-duplicates-report.json", {})
    return {
        record["duplicate"]: record["canonical"]
        for record in report.get("records", [])
        if record.get("duplicate") and record.get("canonical")
    }


def current_source_lookup() -> dict[str, dict[str, Any]]:
    payload = read_json(INDEX_DIR / "sources.json", {"sources": []})
    return {source["id"]: source for source in payload.get("sources", [])}


def source_classification_lookup() -> dict[str, dict[str, Any]]:
    payload = read_json(INDEX_DIR / "source-classification.json", {"sources": {}})
    sources = payload.get("sources", {}) if isinstance(payload, dict) else {}
    return sources if isinstance(sources, dict) else {}


def infer_source_family(source_id: str, title: str, kind: str) -> dict[str, str]:
    text = normalize_for_search(f"{source_id} {title}")
    if kind == "official":
        return {"id": "official_core", "label": SOURCE_FAMILY_LABELS["official_core"]}
    rules_words = ("sistema", "modulo", "regras", "combate", "pericia", "atributo", "daemon 2", "daemon 3")
    equipment_words = ("arma", "armas", "item", "itens", "equipamento", "veiculo", "veneno")
    creature_words = ("monstro", "monstros", "inimigo", "inimigos", "criatura", "npc", "bestiario", "zoologico")
    power_words = ("grimorio", "magia", "magias", "ritual", "rituais", "poder", "poderes", "psi", "cabalistico", "fe", "vodu")
    option_words = ("raca", "racas", "linhagem", "vantagem", "vantagens", "aprimoramento", "talento", "kit", "classe")
    campaign_words = ("campanha", "aventura", "quick start", "quick-start", "cenario pronto", "segredo", "sussurro")
    lore_words = ("ark", "nun", "trevas", "vaticano", "ordem", "ordens", "seita", "seitas", "umbral", "metropolis")
    myth_words = ("mitologia", "egipcia", "celta", "nordica", "assirio", "babilonica", "viking", "vikings", "templario", "templarios", "revolucao francesa", "mitraismo")
    pop_words = ("anime", "naruto", "dragon ball", "yuyu", "yu yu", "samurai x", "samurai shodown", "mortal kombat", "watchmen", "spawn", "one punch", "tartarugas", "supers", "sda", "tagmar")
    checks = [
        ("adaptation_pop", pop_words),
        ("equipment_items", equipment_words),
        ("creatures_bestiary", creature_words),
        ("powers_magic", power_words),
        ("races_options", option_words),
        ("campaign_adventure", campaign_words),
        ("myth_history", myth_words),
        ("rules_system", rules_words),
        ("setting_lore", lore_words),
    ]
    for family_id, words in checks:
        if any(word in text for word in words):
            return {"id": family_id, "label": SOURCE_FAMILY_LABELS[family_id]}
    return {"id": "supplement_misc", "label": SOURCE_FAMILY_LABELS["supplement_misc"]}


def source_classification_for(source_id: str, classifications: dict[str, dict[str, Any]], title: str | None = None) -> dict[str, Any]:
    default_kind = "supplement"
    data = classifications.get(source_id) or {}
    kind = data.get("kind") or default_kind
    label = data.get("label") or ("Livro oficial" if kind == "official" else "Suplemento de jogo/campanha")
    family = data.get("family") if isinstance(data.get("family"), dict) else None
    if not family:
        family = infer_source_family(source_id, title or data.get("officialName") or source_id, kind)
    return {
        "kind": kind,
        "label": label,
        "officialName": data.get("officialName"),
        "classificationNote": data.get("note"),
        "family": family,
    }


def display_source_title(source_id: str, source_lookup: dict[str, dict[str, Any]], book: dict[str, Any] | None = None) -> str:
    raw = (book or {}).get("title") or source_lookup.get(source_id, {}).get("title") or source_id
    return normalize_uppercase_name(str(raw).replace("_", " "))


def all_entity_ids() -> set[str]:
    ids: set[str] = set()
    for path in sorted(ENTITIES_DIR.glob("*.json")):
        payload = read_json(path, [])
        if not isinstance(payload, list):
            continue
        for entity in payload:
            if isinstance(entity, dict) and entity.get("id"):
                ids.add(str(entity["id"]))
    return ids


def valid_entity_refs(refs: list[Any], known_entity_ids: set[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for ref in refs or []:
        ref_id = str(ref)
        if ref_id in known_entity_ids and ref_id not in seen:
            seen.add(ref_id)
            result.append(ref_id)
    return result


def ready_source_ids() -> list[str]:
    sources = current_source_lookup()
    books = {path.stem for path in BOOKS_DATA_DIR.glob("*.json")}
    duplicate_to_canonical = duplicate_map()

    good = read_json(INDEX_DIR / "good-sources-page-coherence.json", {"sources": []})
    usable = read_json(INDEX_DIR / "usable-sources-page-coherence-after-easy-cleanup.json", {"sources": []})

    selected: set[str] = set()
    for source in good.get("sources", []):
        if source.get("status") in {"ok", "notes_only"}:
            selected.add(source["id"])
    for source in usable.get("sources", []):
        if source.get("status") == "ok":
            selected.add(source["id"])

    extra = read_json(INDEX_DIR / "publishable-extra-sources.json", {"sources": []})
    for source in extra.get("sources", []):
        if source.get("publish") and source.get("extractionStatus") != "critical":
            selected.add(source["id"])

    resolved = {duplicate_to_canonical.get(source_id, source_id) for source_id in selected}
    return sorted(source_id for source_id in resolved if source_id in sources and source_id in books)
