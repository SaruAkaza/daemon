# ADR-0004: Relations V2 Ontology, Collection Contract, and Compatibility Governance

## Status
Accepted

## Context
Durante a execução do Real Pilot 005 (*Animalidade* — RELATIONS Stage — Attempt 1), a auditoria técnica e semântica revelou duas lacunas fundamentais na arquitetura de relações:

1. **Lacuna Técnica de Contrato (Contract Gap)**:
   O estágio de relações produziu o arquivo `data/entities/relations.json` contendo um array JSON de objetos de relação. O contrato configurado na requisição apontava para `relation.schema.json`, que valida estritamente um único objeto de relação. Como inexistia um schema formal para coleções de relações (`relation-collection.schema.json`), a validação de schema falhava deterministicamente ao receber uma lista (`list`).
2. **Lacuna Semântica de Ontologia (Ontology Gap)**:
   O predicado `HAS_POWER` vinha sendo utilizado de forma sobrecarregada para representar tanto a posse efetiva de um poder quanto opções de compra ou menus de escolha (ex.: listas de "Poderes Possíveis" em *Animalidade*). Adicionalmente, fraquezas declaradas não possuíam predicado correspondente, e referências a poderes externos não catalogados ameaçavam a integridade referencial do grafo.

## Decision

Fica estabelecida a arquitetura **Relations V2**, governada pelas seguintes definições e contratos canônicos:

### 1. Ontologia Semântica Canônica V2
- **`HAS_POWER`**: **the source entity actually possesses the target power.**
  - A posse efetiva é estritamente distinta de opções selecionáveis ou menus disponíveis (`actual possession != selectable/available option`).
  - Não devem ser adicionadas restrições não declaradas na fonte, tais como "innate", "native", "standard stat block" ou "starting character". O critério é que a fonte declare que a entidade efetivamente possui o poder.
- **`CAN_CHOOSE_POWER`**: **the source entity/template is explicitly allowed to select the target power as a build or configuration option.**
  - Exemplos de aplicação incluem criação de personagem, progressão de personagem, construção de templates ou configuração de criaturas/NPCs, sem que esses exemplos estreitem o significado canônico da relação.
  - Deve ser utilizado sempre que a fonte apresentar listas de "Poderes Possíveis", menus de opções, regras de alocação de pontos de compra ou escolhas permitidas.
- **`HAS_WEAKNESS`**: **the source entity possesses the target weakness, vulnerability, or limitation.**
  - Modela formalmente fraquezas, vulnerabilidades e limitações canônicas possuídas pela entidade (ex.: vulnerabilidade a prata, dano agravado por fogo).
- **Rejeição de `CAN_CHOOSE_WEAKNESS`**:
  - Formalmente rejeitado sob os princípios de YAGNI e ausência de precedente canônico. Fontes analisadas não contêm menus de opções de fraquezas opcionais.

### 2. Versionamento da Ontologia
- **`relations-v1`**: Classificado como **historical / read-only**. Mantido exclusivamente para auditoria e leitura retrospectiva de bundles anteriores.
- **`relations-v2`**: Classificado como **mandatory for new execution**. Todas as novas requisições de execução (`ExecutionRequest`) e pipelines devem operar obrigatoriamente sob V2.
- É proibido misturar convenções V1 e V2 em um mesmo bundle ou arquivo `relations.json`.

### 3. Contratos de Schema e Coleção
- Criação de `schemas/relation-collection.schema.json` para validação formal de coleções de relações (array com itens referenciando `relation.schema.json`, `uniqueItems: true`). Uma coleção vazia (`[]`) é estruturalmente válida.
- Criação de contratos dedicados (`schemas/unresolved-relation.schema.json` e `schemas/unresolved-relation-collection.schema.json`) para isolar relações não resolvidas ou externas em artefato próprio (`unresolved-relations.json`), mantendo o grafo canônico (`relations.json`) livre de referências órfãs.

### 4. Governança de Compatibilidade Semântica
- **Autoridade Canônica da Matriz**: `schemas/relation-compatibility-v2.json` é a única autoridade canônica legível por máquina (`machine-readable JSON = canonical authority`).
- **Documentação Humana**: A documentação markdown correspondente (`docs/reference/relation-compatibility-v2.md`) é estritamente explicativa (`markdown = explanatory only`), linkando para a matriz canônica com zero duplicação de triplets.

## Consequences

### Positivas
- Eliminação da ambiguidade semântica entre poderes efetivamente possuídos e opções de customização.
- Validação técnica determinística de coleções de relações sem heurísticas ad-hoc no validador.
- Isolamento estrito de referências não resolvidas fora do grafo canônico.
- Matriz de compatibilidade centralizada, com autoridade canônica única legível por máquina.

### Negativas / Custos
- Exige auditoria e migração controlada de dados históricos que utilizaram `HAS_POWER` para opções de escolha.
- Pipeline deve validar esquemas de coleção e matriz de compatibilidade de forma rigorosa e fail-closed.

## Supersedes
None
