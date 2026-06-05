# Fix Project Inconsistencies Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Corrigir 9 inconsistências confirmadas pelo code review: mismatch schema/script em overrides, perda silenciosa de dados da área fontes, guards de lock faltando em certify_kits, regex excessivamente ampla em certify_regras_base, subtype enum incompleto e índice desatualizado.

**Architecture:** Cada tarefa é independente e auto-contida. Ordem recomendada: schemas primeiro (Tasks 1-2), depois pipeline de dados (Tasks 3-4, 7), depois certificação (Tasks 5-6), por fim dados estáticos (Task 8). Tasks 1, 2, 5, 6 e 8 são edições pontuais de 1-3 linhas. Tasks 3, 4 e 7 exigem ler código antes de editar.

**Tech Stack:** Python 3.11+, jsonschema Draft 2020-12, JSON em data/ e schemas/.

---

### Task 1: Fix overrides.schema.json — action enum incompatível

**Files:**
- Modify: `schemas/overrides.schema.json`

O enum `action` no schema é `["publish", "quarantine", "rename", "merge", "hide", "update"]`.
O script `apply_editorial_overrides.py` linha 12 aceita `{"replace", "hide", "publish", "tag_review", "quarantine"}`.
Quatro valores diferem: schema aceita `rename/merge/update` (ignorados pelo script); script aceita `replace/tag_review` (rejeitados pelo validator).

- [ ] **Step 1: Substituir o enum action pelo conjunto real do script**

Em `schemas/overrides.schema.json` linha 23, trocar:

```json
"enum": ["publish", "quarantine", "rename", "merge", "hide", "update"]
```

por:

```json
"enum": ["replace", "hide", "publish", "tag_review", "quarantine"]
```

- [ ] **Step 2: Commit**

```bash
git add schemas/overrides.schema.json
git commit -m "fix: align overrides schema action enum with script ALLOWED_ACTIONS"
```

---

### Task 2: Fix overrides.schema.json — additionalProperties bloqueia campos reais

**Files:**
- Modify: `schemas/overrides.schema.json`

O schema declara `additionalProperties: false` mas o script `apply_editorial_overrides.py` lê campos não declarados: `area`, `itemType`, `note` (linhas 65-66, 90-92) e ~18 chaves de substituição direta de campo (linhas 57-63: `name`, `summary`, `entries`, `tags`, `category`, `subtype`, `contentKind`, `contentKindLabel`, `sourceFamily`, `sourceFamilyLabel`, `page`, `pages`, `entityRefs`, `costText`, `requirements`, `skillsText`, `aprimoramentosText`, `attributesText`, `advantagesText`, `disadvantagesText`).

Qualquer override real com escopo de área ou substituição de campo vai falhar na validação.

- [ ] **Step 1: Substituir o bloco "items" do schema com todos os campos declarados**

Em `schemas/overrides.schema.json`, substituir o objeto `items` (linhas 17-43) por:

```json
{
  "type": "object",
  "required": ["action", "id"],
  "properties": {
    "action": {
      "type": "string",
      "enum": ["replace", "hide", "publish", "tag_review", "quarantine"]
    },
    "id": {
      "type": "string",
      "description": "ID da entidade ou sourcePart alvo"
    },
    "area": {
      "type": "string",
      "description": "Área para escopo do override (opcional)"
    },
    "itemType": {
      "type": "string",
      "enum": ["entity", "sourcePart"],
      "description": "Tipo do item para escopo (opcional)"
    },
    "reason": {
      "type": "string",
      "description": "Justificativa editorial legível"
    },
    "note": {
      "type": "string",
      "description": "Nota interna exibida no catálogo"
    },
    "name": { "type": "string" },
    "summary": { "type": "string" },
    "entries": { "type": "array" },
    "tags": { "type": "array", "items": { "type": "string" } },
    "category": { "type": "string" },
    "subtype": { "type": "string" },
    "contentKind": { "type": "string" },
    "contentKindLabel": { "type": "string" },
    "sourceFamily": { "type": "string" },
    "sourceFamilyLabel": { "type": "string" },
    "page": { "type": "integer" },
    "pages": { "type": "array" },
    "entityRefs": { "type": "array" },
    "costText": { "type": "string" },
    "requirements": { "type": "string" },
    "skillsText": { "type": "string" },
    "aprimoramentosText": { "type": "string" },
    "attributesText": { "type": "string" },
    "advantagesText": { "type": "string" },
    "disadvantagesText": { "type": "string" }
  },
  "additionalProperties": false
}
```

- [ ] **Step 2: Commit**

```bash
git add schemas/overrides.schema.json
git commit -m "fix: declare all override record fields to satisfy additionalProperties: false"
```

---

### Task 3: Fix entity.schema.json — adicionar "race" e "lineage" ao enum de subtype

**Files:**
- Modify: `schemas/entity.schema.json`

`catalog_processor.py` linha 267 verifica `subtype in {"raca", "race"}` e linha 269 verifica `subtype in {"linhagem", "lineage"}`. O schema `entity.schema.json` linha 33 só enumera `"raca"` e `"linhagem"` — sem `"race"` nem `"lineage"`. Entidades com esses subtypes seriam processadas corretamente mas rejeitadas pelo validator.

- [ ] **Step 1: Adicionar os valores faltantes ao enum**

Em `schemas/entity.schema.json` linha 33, trocar:

```json
"enum": ["aprimoramento", "class", "kit", "lineage", "linhagem", "magia", "poder", "raca", "ritual"]
```

por:

```json
"enum": ["aprimoramento", "class", "kit", "lineage", "linhagem", "magia", "poder", "race", "raca", "ritual"]
```

(Nota: `"lineage"` já está no enum atual. Apenas `"race"` está faltando.)

- [ ] **Step 2: Commit**

```bash
git add schemas/entity.schema.json
git commit -m "fix: add 'race' to entity schema subtype enum to match catalog_processor usage"
```

---

### Task 4: Fix fontes área — adicionar a AREA_LABELS e chamar build_source_entities

**Files:**
- Modify: `scripts/catalog_loader.py`
- Modify: `scripts/build_area_catalog.py`

Dois problemas relacionados:
1. `"fontes"` não está em `AREA_LABELS` (catalog_loader.py linha 20-35), então `write_area_files` nunca escreve `fontes.json`
2. `build_source_entities` em catalog_processor.py linha 489 está definida mas nunca é importada ou chamada — a área fontes sempre fica com `entities: []`

- [ ] **Step 1: Adicionar "fontes" a AREA_LABELS em catalog_loader.py**

Em `scripts/catalog_loader.py`, após linha 34 (`"tabelas": "Tabelas e Geradores",`), adicionar:

```python
    "fontes": "Fontes",
```

O dict `AREA_LABELS` deve terminar em:
```python
    "tabelas": "Tabelas e Geradores",
    "fontes": "Fontes",
}
```

- [ ] **Step 2: Importar build_source_entities em build_area_catalog.py**

Em `scripts/build_area_catalog.py` linhas 20-26, adicionar `build_source_entities` ao import de `catalog_processor`:

```python
from catalog_processor import (
    build_entity_items,
    build_source_entities,
    build_source_part_items,
    catalog_sort_key,
    enrich_display_quality,
    facet_records,
)
```

- [ ] **Step 3: Chamar build_source_entities em main() e mesclar resultado**

Em `scripts/build_area_catalog.py` na função `main()` (linhas 130-146), trocar:

```python
    entity_items = build_entity_items(set(source_ids), source_lookup, classifications)
    summary = write_area_files(source_ids, part_items, entity_items)
```

por:

```python
    entity_items = build_entity_items(set(source_ids), source_lookup, classifications)
    source_entity_items = build_source_entities(source_ids, source_lookup)
    summary = write_area_files(source_ids, part_items, [*entity_items, *source_entity_items])
```

`build_source_entities` já popula `area: "fontes"` em cada item, então `write_area_files` os colocará automaticamente no bucket correto.

- [ ] **Step 4: Commit**

```bash
git add scripts/catalog_loader.py scripts/build_area_catalog.py
git commit -m "fix: add fontes to AREA_LABELS and call build_source_entities to populate area"
```

---

### Task 5: Fix certify_kits.py — adicionar guards de lock faltantes

**Files:**
- Modify: `scripts/certify_kits.py`

`certify_kits.py` linha 180 chama `locked_names_for_areas(["aprimoramentos"])` — apenas um lock.
Entidades já certificadas como `racas`, `linhagens`, `classes`, `poderes`, `magias`, `rituais` ou `regras_base` podem ser duplo-certificadas como kits.
`certify_poderes_magias.py` e `certify_rituais.py` verificam todas as áreas anteriores.
`lock_manager.py` linha 19-29 confirma que todos esses nomes têm arquivos de lock correspondentes.

- [ ] **Step 1: Expandir a lista de áreas verificadas**

Em `scripts/certify_kits.py` linha 180, trocar:

```python
    locked_names = locked_names_for_areas(["aprimoramentos"])
```

por:

```python
    locked_names = locked_names_for_areas([
        "aprimoramentos", "racas", "linhagens", "classes",
        "poderes", "magias", "rituais", "regras_base",
    ])
```

- [ ] **Step 2: Commit**

```bash
git add scripts/certify_kits.py
git commit -m "fix: certify_kits now guards against all certified areas, not only aprimoramentos"
```

---

### Task 6: Fix certify_regras_base.py — narrowing CHARACTER_OPTION_RE e ampliando POWER_MAGIC_RE exemption

**Files:**
- Modify: `scripts/certify_regras_base.py`

Dois bugs de regex em `certify_regras_base.py`:

**Bug A:** `CHARACTER_OPTION_RE` linha 49 usa `re.DOTALL`, fazendo `.*` atravessar parágrafos inteiros. Uma regra de combate que menciona "classes de combate" num parágrafo e "gastar 3 pontos" três parágrafos depois é rejeitada incorretamente como `looks_like_character_option`.

**Bug B:** `POWER_MAGIC_RE` linha 99 só isenta `category == "core_rule"`. Entradas `combat` e `attribute_skill` que referenciam seções de poderes são rejeitadas indevidamente como `looks_like_power_magic_or_ritual`.

- [ ] **Step 1: Remover re.DOTALL e limitar span do .*  em CHARACTER_OPTION_RE**

Em `scripts/certify_regras_base.py` linhas 46-50, trocar:

```python
CHARACTER_OPTION_RE = re.compile(
    r"\b(?:aprimoramentos?|kits?|classes?|ra[cç]as?|linhagens?)\b.*\b(?:pontos?|pts?\.?)\b|"
    r"\b(?:per[ií]cias?|aprimoramentos?)\s*:.*\b(?:pontos? her[oó]icos|pontos? de per[ií]cia|pts?\.?)\b",
    re.IGNORECASE | re.DOTALL,
)
```

por:

```python
CHARACTER_OPTION_RE = re.compile(
    r"\b(?:aprimoramentos?|kits?|classes?|ra[cç]as?|linhagens?)\b.{0,120}\b(?:pontos?|pts?\.?)\b|"
    r"\b(?:per[ií]cias?|aprimoramentos?)\s*:.{0,200}\b(?:pontos? her[oó]icos|pontos? de per[ií]cia|pts?\.?)\b",
    re.IGNORECASE,
)
```

O `{0,120}` e `{0,200}` limitam o match a uma mesma frase/cláusula, evitando matches entre parágrafos distantes.

- [ ] **Step 2: Ampliar isenção do POWER_MAGIC_RE**

Em `scripts/certify_regras_base.py` linha 99, trocar:

```python
    if POWER_MAGIC_RE.search(body[:1000]) and category != "core_rule":
```

por:

```python
    if POWER_MAGIC_RE.search(body[:1000]) and category not in {"core_rule", "combat", "attribute_skill"}:
```

- [ ] **Step 3: Commit**

```bash
git add scripts/certify_regras_base.py
git commit -m "fix: narrow CHARACTER_OPTION_RE span and broaden POWER_MAGIC_RE exemption to combat/attribute_skill"
```

---

### Task 7: Fix subgroups para kits, poderes, magias e racas

**Files:**
- Modify: `scripts/catalog_processor.py`

`build_entity_items` só popula `subgroup`/`subgroupLabel` para `area == "aprimoramentos"` (linha 409-411). Kits, poderes, magias e racas sempre têm `subgroups: []`.

O schema `entity.schema.json` declara `kitContext` (linha 110) e `powerMagicContext` (linha 106) — esses campos são os agrupamentos naturais para kits e poderes/magias respectivamente.

- [ ] **Step 1: Verificar campos disponíveis nas entidades certificadas**

```bash
cd c:\Projetos\Daemon Trevas\livros\Repositorio\daemon
python -c "
import json
from pathlib import Path
for fname in ['kit_class_granular.json', 'poderes_magias_granular.json', 'racas_granular.json']:
    p = Path('data/entities') / fname
    if p.exists():
        data = json.loads(p.read_text(encoding='utf-8'))
        if data:
            print(fname, list(data[0].keys())[:15])
"
```

Confirmar que `kitContext` e `powerMagicContext` estão presentes nos dados.

- [ ] **Step 2: Adicionar subgroup para kits em build_entity_items**

Em `scripts/catalog_processor.py`, após o bloco `if area == "aprimoramentos":` (linha 409-411), adicionar:

```python
            elif area == "kits" and entity.get("kitContext"):
                subgroup = slugify(str(entity["kitContext"]))
                subgroup_label = str(entity["kitContext"])
                subgroup_tag = f"kit-{subgroup}"
            elif area in {"poderes", "magias"} and entity.get("powerMagicContext"):
                subgroup = slugify(str(entity["powerMagicContext"]))
                subgroup_label = str(entity["powerMagicContext"])
                subgroup_tag = f"path-{subgroup}"
            elif area in {"racas", "linhagens"}:
                family_id = classification.get("family", {}).get("id") or ""
                if family_id:
                    subgroup = family_id
                    subgroup_label = classification.get("family", {}).get("label") or family_id
                    subgroup_tag = f"source-{family_id}"
```

Este bloco deve estar dentro do loop `for entity in category_entities:`, no mesmo nível do bloco aprimoramentos existente. A variável `classification` já está disponível nesse escopo (calculada algumas linhas antes).

- [ ] **Step 3: Commit**

```bash
git add scripts/catalog_processor.py
git commit -m "fix: populate subgroup for kits (kitContext), poderes/magias (powerMagicContext) and racas (sourceFamily)"
```

---

### Task 8: Fix entity-ref-integrity.json — entrada desatualizada de a-assassina

**Files:**
- Modify: `data/index/entity-ref-integrity.json` (ou regenerar via script)

O relatório declara `"a-assassina"` como ID duplicado em `adventure.json#0` e `source.json#1`. Mas `adventure.json[0]` agora tem `id: "a-assassina-aventura"` — o conflito foi resolvido. A entrada stale pode bloquear publicação da entidade source válida.

A forma mais confiável é regenerar o relatório com o script que o produz (`scripts/audit_entity_refs.py`).

- [ ] **Step 1: Regenerar o relatório rodando o script de auditoria**

```bash
cd c:\Projetos\Daemon Trevas\livros\Repositorio\daemon
python scripts/audit_entity_refs.py
```

Verificar que `data/index/entity-ref-integrity.json` agora mostra `"duplicateGlobalIdCount": 0` e `"duplicateGlobalIds": {}`.

- [ ] **Step 2: Se o script não existir como executável, editar manualmente**

Caso o script não aceite execução direta, editar `data/index/entity-ref-integrity.json` manualmente:

```json
"summary": {
  "entityIdCount": 1740,
  "duplicateGlobalIdCount": 0,
  ...
},
"duplicateGlobalIds": {}
```

- [ ] **Step 3: Commit**

```bash
git add data/index/entity-ref-integrity.json
git commit -m "fix: remove stale a-assassina duplicate entry from entity-ref-integrity report"
```

---

## Self-Review

**Cobertura das 9 inconsistências confirmadas:**
1. ✅ Task 1 — overrides schema action enum mismatch
2. ✅ Task 2 — overrides schema additionalProperties bloqueia campos reais
3. ✅ Task 3 — entity schema subtype enum sem "race"
4. ✅ Task 4 — fontes área nunca escrita (AREA_LABELS + build_source_entities não chamada)
5. ✅ Task 5 — certify_kits lock guards insuficientes
6. ✅ Task 6 — CHARACTER_OPTION_RE DOTALL e POWER_MAGIC_RE narrow
7. ✅ Task 7 — subgroups sempre [] para kits/poderes/magias/racas
8. ✅ Task 8 — entity-ref-integrity.json desatualizado
9. ✅ Task 4 (infer_area fallback) — resolvido ao adicionar "fontes" a AREA_LABELS

**Verificação de tipos e nomes:**
- `locked_names_for_areas` — importado de `granular_validation` em certify_kits.py linha 8 ✅
- `build_source_entities` — definida em catalog_processor.py linha 489, assinatura `(source_ids: list[str], source_lookup: dict) -> list[dict]` ✅
- Nomes de área em Task 5 (`aprimoramentos`, `racas`, etc.) — todos presentes em `LOCK_FILES` em lock_manager.py ✅
- `kitContext` e `powerMagicContext` — declarados em entity.schema.json linhas 106-112 ✅

**Placeholders:** Nenhum. Todos os steps têm código exato ou comandos concretos.
