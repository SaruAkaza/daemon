# Tipos de Relações Semânticas (Relation Types)

Este documento define o vocabulário canônico de relações semânticas e dependências de regras do **Daemon Tools**. Este vocabulário formaliza os vínculos entre entidades, permitindo a construção de grafos de regras, validação de pré-requisitos e navegação hipertextual rica.

---

## 1. Vocabulário Canônico de Relações

### 1. `REQUIRES`
- **Significado**: A entidade de origem exige a entidade de destino como pré-requisito obrigatório para compra, escolha ou evolução.
- **Origem Esperada**: `kit_class`, `character_option`, `power_magic`, `ritual_spell`, `combat`.
- **Destino Esperado**: `attribute_skill`, `character_option`, `race_lineage`, `power_magic`, `core_rule`.
- **Exemplo**: `kit:cacador-de-bruxas` ──`REQUIRES`──> `skill:teologia`.

---

### 2. `GRANTS`
- **Significado**: A escolha da entidade de origem concede automaticamente a entidade de destino (bônus, poder, perícia ou aprimoramento gratuito).
- **Origem Esperada**: `kit_class`, `race_lineage`, `character_option`.
- **Destino Esperado**: `character_option`, `power_magic`, `attribute_skill`.
- **Exemplo**: `race:elfo` ──`GRANTS`──> `enhancement:visao-agucada`.

---

### 3. `BELONGS_TO`
- **Significado**: A entidade pertence organicamente a um agrupamento maior, caminho místico, panteão ou organização de cenário.
- **Origem Esperada**: `ritual_spell`, `creature_npc`, `item_equipment`, `kit_class`.
- **Destino Esperado**: `power_magic` (Caminho), `setting_lore` (Organização/Cenário).
- **Exemplo**: `spell:bola-de-fogo` ──`BELONGS_TO`──> `path:caminho-do-fogo`.

---

### 4. `DERIVED_FROM`
- **Significado**: A entidade é uma evolução, especialização ou variante direta de outra entidade base.
- **Origem Esperada**: `race_lineage`, `kit_class`, `power_magic`.
- **Destino Esperado**: `race_lineage`, `kit_class`, `power_magic`.
- **Exemplo**: `race:meio-elfo` ──`DERIVED_FROM`──> `race:elfo`.

---

### 5. `APPEARS_IN`
- **Significado**: A entidade é citada, reimpressa ou utilizada em múltiplos suplementos e módulos do universo.
- **Origem Esperada**: Qualquer entidade.
- **Destino Esperado**: `source`.
- **Exemplo**: `enhancement:bruto-insano` ──`APPEARS_IN`──> `source:anime-rpg-powers`.

---

### 6. `MODIFIES`
- **Significado**: A entidade ou suplemento altera, estende ou ajusta as regras ou atributos de uma entidade preexistente.
- **Origem Esperada**: `source`, `character_option`, `kit_class`, `core_rule`.
- **Destino Esperado**: `core_rule`, `attribute_skill`, `combat`, `character_option`.
- **Exemplo**: `rule:combate-avancado` ──`MODIFIES`──> `rule:iniciativa-basica`.

---

### 7. `REPLACES`
- **Significado**: A entidade ou suplemento substitui formalmente uma regra ou versão anterior em edições mais recentes.
- **Origem Esperada**: `core_rule`, `source`, `character_option`.
- **Destino Esperado**: `core_rule`, `character_option`.
- **Exemplo**: `rule:regras-daemon-3-0` ──`REPLACES`──> `rule:regras-daemon-2-x`.

---

### 8. `ALTERNATIVE_TO`
- **Significado**: A entidade representa uma variante mecânica ou opção temática equivalente a outra entidade.
- **Origem Esperada**: Qualquer entidade.
- **Destino Esperado**: Entidade da mesma categoria.
- **Exemplo**: `enhancement:imortal-centelha` ──`ALTERNATIVE_TO`──> `enhancement:imortal-classico`.

---

### 9. `HAS_POWER`
- **Significado**: A entidade (como raça, kit ou NPC) possui acesso nativo ou lista estruturada de poderes.
- **Origem Esperada**: `race_lineage`, `kit_class`, `creature_npc`.
- **Destino Esperado**: `power_magic`.
- **Exemplo**: `race:alastor` ──`HAS_POWER`──> `power:pirocinese`.

---

### 10. `HAS_SKILL`
- **Significado**: A entidade possui um pacote ou requisito específico de perícias operacionais.
- **Origem Esperada**: `kit_class`, `creature_npc`.
- **Destino Esperado**: `attribute_skill`.
- **Exemplo**: `kit:ferreiro-anao` ──`HAS_SKILL`──> `skill:metalurgia`.

---

### 11. `USES_RULE`
- **Significado**: A entidade opera com base em uma mecânica específica descrita em uma regra base do sistema.
- **Origem Esperada**: `combat`, `ritual_spell`, `power_magic`.
- **Destino Esperado**: `core_rule`.
- **Exemplo**: `combat:manobra-desarme` ──`USES_RULE`──> `rule:teste-de-destreza-resistido`.

---

## 2. Política de Evolução de Relações

> [!NOTE]
> A inclusão de qualquer novo tipo de relação semântica no futuro exige alteração conjunta neste documento de domínio e no correspondente JSON Schema em `schemas/`.
