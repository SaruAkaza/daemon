# Matriz de Compatibilidade de Relações (Relations V2)

## 1. Princípio de Autoridade Canônica

Em conformidade com a arquitetura **Relations V2** definida no [ADR-0004](../context/decisions/ADR-0004-relations-v2-ontology-and-contracts.md) e na especificação de ontologia, a governança de compatibilidade semântica opera sob o seguinte princípio:

> **Regra de Autoridade**: `machine-readable JSON = canonical authority`  
> **Regra Documental**: `markdown = explanatory only`

A autoridade canônica única para validação semântica de triplets (`sourceCategory` + `relationType` + `targetCategory` + subtipos opcionais) reside exclusivamente no arquivo JSON legível por máquina:

- [`schemas/relation-compatibility-v2.json`](../../schemas/relation-compatibility-v2.json)
- Schema validador da matriz: [`schemas/relation-compatibility.schema.json`](../../schemas/relation-compatibility.schema.json)

Este documento markdown tem propósito estritamente explicativo e conceitual. Para evitar divergência acidental e garantir que o código e os testes mantenham uma única fonte da verdade, **não há duplicação manual de listas de triplets ou tabelas exaustivas de compatibilidade neste arquivo**.

---

## 2. Modelo de Compatibilidade e Semântica Fail-Closed

A matriz canônica valida deterministicamente se uma relação entre duas entidades é semanticamente válida dentro do universo Daemon Tools.

### 2.1 Elementos de uma Regra de Compatibilidade
Cada regra na matriz canônica define:
1. `relationType`: Um dos 13 predicados canônicos da ontologia Relations V2 (`REQUIRES`, `GRANTS`, `BELONGS_TO`, `DERIVED_FROM`, `APPEARS_IN`, `MODIFIES`, `REPLACES`, `ALTERNATIVE_TO`, `HAS_POWER`, `CAN_CHOOSE_POWER`, `HAS_WEAKNESS`, `HAS_SKILL`, `USES_RULE`).
2. `allowedSourceCategories`: Conjunto de categorias válidas para a entidade de origem (`source`).
3. `allowedTargetCategories`: Conjunto de categorias válidas para a entidade de destino (`target`).
4. `allowedTargetSubtypes` (opcional): Subtipos admitidos quando a categoria de destino exige restrição refinada (por exemplo, diferenciar poderes ou fraquezas dentro de `character_option`).
5. `allowedSourceSubtypes` (opcional): Subtipos admitidos para a entidade de origem quando aplicável.
6. `semanticMeaning`: Definição canônica do vínculo relacional.

### 2.2 Política Estrita Fail-Closed
O pipeline opera em regime estritamente **Fail-Closed**:
- **Predicado Desconhecido**: Qualquer relação cujo `relationType` não pertença aos 13 predicados canônicos é sumariamente rejeitada.
- **Par de Categorias Incompatível**: Se a categoria da entidade de origem ou de destino não constar explicitamente na regra correspondente da matriz, a relação é rejeitada com erro semântico.
- **Subtipo Inválido**: Quando a regra especifica subtipos permitidos, a presença de uma entidade com subtipo não listado resulta em rejeição imediata.
- **Entidade Ausente**: Se o identificador de destino não for encontrado no conjunto de entidades canônicas do livro, a aresta não pode ser inserida no grafo canônico (`relations.json`) e deve ser isolada como referência externa em `unresolved-relations.json`.

---

## 3. Decisões Ontológicas Negativas

- **Rejeição de `CAN_CHOOSE_WEAKNESS`**: O predicado foi expressamente rejeitado sob o princípio de YAGNI e ausência de precedente canônico no material original analisado. A matriz canônica não possui regra para este predicado. Fraquezas são representadas via `HAS_WEAKNESS` ou aprimoramentos gerais.

---

## 4. Consumo e Validação Programática

Os validadores do pipeline (tais como `RelationCompatibilityValidator`, `PilotQAValidator` e gates de execução) carregam diretamente [`schemas/relation-compatibility-v2.json`](../../schemas/relation-compatibility-v2.json). 

Para inspecionar as regras e categorias permitidas em detalhes, consulte diretamente a matriz canônica em formato JSON.
