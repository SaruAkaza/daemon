from __future__ import annotations

import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BOOKS_DIR = ROOT / "Livros"
DATA_DIR = ROOT / "data"
INDEX_DIR = DATA_DIR / "index"
TEXT_DIR = DATA_DIR / "text"


def ensure_dirs() -> None:
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    TEXT_DIR.mkdir(parents=True, exist_ok=True)


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value).strip("-").lower()
    return slug or "untitled"


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    # Individual legacy book builders also write directly to public assets.
    # Keep their canonical/local outputs available, but apply the same rights
    # preflight before a public destination or its parent is created.
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from scripts.legacy_publication import validate_public_write

    validate_public_write(path, payload, repo_root=ROOT)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


KEYWORDS_BY_CATEGORY = {
    "core_rule": [
        "regra", "regras", "modulo", "sistema", "daemon", "teste", "testes",
        "dificuldade", "dano", "resistencia", "evolucao", "experiencia",
    ],
    "attribute_skill": [
        "atributo", "atributos", "pericia", "pericias", "especializacao",
        "especializacoes", "forca", "constituicao", "destreza", "agilidade",
        "inteligencia", "vontade", "carisma", "percepcao",
    ],
    "combat": [
        "combate", "iniciativa", "ataque", "defesa", "armadura", "dano",
        "manobra", "manobras", "arma", "armas", "escudo", "ferimento",
    ],
    "character_option": [
        "aprimoramento", "aprimoramentos", "vantagem", "vantagens",
        "desvantagem", "desvantagens", "talento", "talentos", "poderes",
        "heroismo",
    ],
    "kit_class": [
        "classe", "classes", "kit", "kits", "caminho", "caminhos", "guerreiro",
        "monge", "mago", "samurai", "ninja", "ocupacao", "arquetipo",
    ],
    "race_lineage": [
        "raca", "racas", "linhagem", "linhagens", "anoes", "elf", "youkai",
        "vampiro", "vampiros", "lobisomem", "lobisomens", "fada", "fadas",
    ],
    "power_magic": [
        "magia", "magias", "caminho", "caminhos", "poder", "poderes",
        "cabalistico", "misticismo", "mistica", "fe", "psiquismo", "vodu",
        "kidous", "energia mistica",
    ],
    "ritual_spell": [
        "grimorio", "ritual", "rituais", "encantamento", "magia negra",
        "invocacao", "circulo", "circulos", "efeito", "efeitos",
    ],
    "item_equipment": [
        "item", "itens", "arma", "armas", "armadura", "equipamento", "equip",
        "veiculo", "veiculos", "escudo", "objeto", "objetos",
    ],
    "creature_npc": [
        "monstro", "monstros", "criatura", "criaturas", "demonio", "demonios",
        "anjo", "anjos", "morto vivo", "mortos vivos", "zoologico", "dragao",
        "dragoes", "npc", "entidade", "entidades",
    ],
    "setting_lore": [
        "trevas", "arkanun", "vaticano", "mitologia", "religiao", "judaismo",
        "inquisicao", "nordica", "celta", "egipcia", "oriente", "cronologia",
        "organizacao", "organizacoes",
    ],
    "adventure": [
        "aventura", "campanha", "quick-start", "modulo", "cenario", "segredo",
        "sussurro",
    ],
    "table_generator": [
        "tabela", "tabelas", "gerador", "geradores", "aleatorio", "sorteio",
    ],
}


def infer_category_hints(text: str) -> list[str]:
    normalized = slugify(text).replace("-", " ")
    scores: dict[str, int] = {}
    for category, keywords in KEYWORDS_BY_CATEGORY.items():
        scores[category] = sum(
            1
            for keyword in keywords
            if re.search(rf"\b{re.escape(slugify(keyword).replace('-', ' '))}\b", normalized)
        )
    ranked = [category for category, score in sorted(scores.items(), key=lambda item: item[1], reverse=True) if score]
    return ranked[:4] or ["source"]
