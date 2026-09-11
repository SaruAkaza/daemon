from __future__ import annotations

from scripts.agents.site_view_model import ProjectionError

RELATION_LABELS: dict[str, tuple[str, str]] = {
    "CAN_CHOOSE_POWER": ("Pode escolher poder", "Pode ser escolhido por"),
    "HAS_POWER": ("Possui poder", "É possuído por"),
    "HAS_WEAKNESS": ("Possui fraqueza", "É fraqueza de"),
    "REQUIRES": ("Requer", "É requerido por"),
    "GRANTS": ("Concede", "É concedido por"),
    "BELONGS_TO": ("Pertence a", "Inclui"),
    "DERIVED_FROM": ("Deriva de", "Origina"),
    "APPEARS_IN": ("Aparece em", "Contém referência a"),
    "MODIFIES": ("Modifica", "É modificado por"),
    "REPLACES": ("Substitui", "É substituído por"),
    "ALTERNATIVE_TO": ("É alternativa a", "É alternativa a"),
    "HAS_SKILL": ("Possui perícia", "É perícia de"),
    "USES_RULE": ("Usa regra", "É usada por"),
}

ENTITY_CATEGORY_LABELS: dict[str, str] = {
    "core_rule": "Regra Básica",
    "attribute_skill": "Atributo / Perícia",
    "combat": "Combate",
    "character_option": "Opção de Personagem",
    "character_class": "Classe",
    "kit_class": "Kit",
    "race_lineage": "Raça / Linhagem",
    "power_magic": "Poder / Magia",
    "ritual_spell": "Ritual / Magia",
    "item_equipment": "Item / Equipamento",
    "item": "Item",
    "creature_npc": "Criatura",
    "setting_lore": "Cenário / Ambientação",
    "faction_organization": "Facção / Organização",
    "lore_world": "Cenário / Mundo",
    "rules_mechanics": "Regras / Mecânicas",
    "magic": "Magia",
    "adventure": "Aventura",
    "table_generator": "Tabela",
    "source": "Fonte",
}

ENTITY_SUBTYPE_REFINEMENTS: dict[str, dict[str, str]] = {
    "power_magic": {
        "poder": "Poder",
        "magia": "Magia",
        "poder_sobrenatural": "Poder Sobrenatural",
    },
    "character_option": {
        "aprimoramento": "Aprimoramento",
        "fraqueza": "Fraqueza",
        "desvantagem": "Desvantagem",
        "pericia": "Perícia",
        "poder": "Poder",
    },
    "race_lineage": {
        "race": "Raça",
        "raca": "Raça",
        "lineage": "Linhagem",
        "linhagem": "Linhagem",
    },
    "character_class": {
        "class": "Classe",
    },
    "kit_class": {
        "kit": "Kit",
    },
    "ritual_spell": {
        "ritual": "Ritual",
        "magia": "Magia",
    },
}


def relation_labels(predicate: str) -> tuple[str, str]:
    """Return outgoing and incoming human-readable labels for a relation predicate.

    Raises ProjectionError if predicate is unknown.
    """
    try:
        return RELATION_LABELS[predicate]
    except KeyError as exc:
        raise ProjectionError(f"Unknown predicate: '{predicate}'") from exc


def entity_label(category: str, subtype: str | None = None) -> str:
    """Return human-readable display label for an entity category and optional subtype.

    Raises ProjectionError if category is unknown.
    """
    if category not in ENTITY_CATEGORY_LABELS:
        raise ProjectionError(f"Unknown entity category: '{category}'")

    if subtype:
        refined = ENTITY_SUBTYPE_REFINEMENTS.get(category, {}).get(subtype.lower())
        if refined:
            return refined

    return ENTITY_CATEGORY_LABELS[category]