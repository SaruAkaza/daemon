# Daemon Tools — Version 2 Design Specification
# Relations V2: Ontologia Semântica, Contratos de Coleção e Governança de Relações

## 1. Contexto e Declaração do Problema

Durante a execução real do **Real Pilot 005 (animalidade — RELATIONS Stage — Attempt 1)**, a auditoria técnica e semântica revelou duas lacunas independentes e fundamentais na arquitetura de relações:

### 1.1 Technical Contract Gap (Lacuna Técnica de Contrato)

O estágio `relations` produziu o arquivo `data/entities/relations.json` contendo um **JSON ARRAY** com 108 objetos de relação.
Contudo, o schema configurado na `ExecutionRequest` e materializado no `output-contract.json` foi:
```json
{
  "filePattern": "data/entities/relations.json",
  "outputSchemaName": "relation.schema.json"
}
```

O schema `schemas/relation.schema.json` define estritamente um **único objeto de relação**:
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Daemon Relation",
  "type": "object",
  "additionalProperties": false,
  ...
}
```

Durante a aceitação técnica pelo `ExecutionResultValidator`:
1. O validador resolveu o schema do arquivo para `relation.schema.json`.
2. Em `contracts.py:validate_payload`, o validador exigiu que a carga fosse um dicionário (`isinstance(payload, dict)`), gerando imediatamente:
   ```
   ContractValidationError: Payload for relation.schema.json must be a dict, got list
   Verdict: FAIL (ERR_SCHEMA_VALIDATION)
   ```

#### Classificação de Causa Raiz
A falha técnica **não** foi um erro de codificação acidental do Relations Agent nem uma corrupção do validador. Trata-se de uma **lacuna de contrato de schema**: inexistia um schema formal para representar uma **coleção de relações** (`relation-collection.schema.json`), forçando o agente a tentar validar um array contra um schema de item individual.

#### Causa da Omissão nos Testes Sintéticos V2.2
A suíte sintética de testes E2E do V2.2 (`tests/agents/test_pilot_pipeline_e2e.py`) testou as fases de `extraction`, `editorial` e `entities` com payloads completos, mas em relação ao estágio de relações, os testes cobriram apenas validação unitária de instâncias isoladas ou mockaram a aceitação técnica sem exercitar a validação de schema real de um arquivo de coleção `relations.json` contra `ExecutionResultValidator`.

### 1.2 Semantic Ontology Gap (Lacuna Semântica na Ontologia)

O Result Bundle do Attempt 1 produziu 108 relações, todas com o predicado `HAS_POWER`, ligando as 17 criaturas (`category: "creature_npc"`) aos aprimoramentos e poderes descritos na seção "Poderes Possíveis" de cada Fera.

A auditoria semântica minuciosa do texto original de *Animalidade* (p. 10-12) revelou uma contradição de modelagem fundamental:

1. **A Linguagem Canônica da Fonte**:
   - A fonte em *Animalidade* estrutura cada Fera com um cabeçalho explícito: **"Poderes Possíveis:"**.
   - O texto descritivo do suplemento estabelece uma economia de pontos para criação/construção do personagem Fera:
     > *"O jogador tem 5 pontos de aprimoramentos para gastar na criação do personagem, mais 1 ponto de poder animal..."*
   - Cada Fera tem uma lista permitida de opções (ex: *Lobisomem* pode escolher Garras, Faro, Mordida, Regeneração, etc.), mas **não** possui todos eles simultaneamente no estado ativo inicial de jogo.
2. **O Significado Ontológico de `HAS_POWER`**:
   - No modelo de ontologia do Daemon Tools, `HAS_POWER` denota **posse ativa e inata confirmada** no bloco de atributos/habilidades da entidade (ex: um monstro que possui intrinsecamente Visão Noturna).
   - Atribuir `HAS_POWER` a todas as opções da lista de "Poderes Possíveis" expressa falsamente que a entidade possui todos os poderes da lista ao mesmo tempo, ignorando o limite canônico de pontos de construção.
3. **Lacunas Adicionais Descobertas**:
   - **Fraquezas omitidas**: Fraquezas canônicas declaradas na fonte (ex: vulnerabilidade a prata, dano agravado) não tinham relação tipada. O modelo carece de `HAS_WEAKNESS`.
   - **Referências externas não resolvidas**: A Fera *Garras de Sharikan* cita o poder *"Rapidez"*. A auditoria léxica completa do suplemento *Animalidade* confirmou que *"Rapidez"* não existe em *Animalidade* — trata-se de um poder importado do livro básico *Vampiros: Os Teurgos* ou *Inquisição*. Injetar cegamente essa relação quebra a integridade referencial se a entidade de destino não existe no contexto do livro.

---

## 2. Goals e Non-Goals

### 2.1 Goals

1. **Definir Contrato Estrutural de Coleção**: Criar `schemas/relation-collection.schema.json` que valida formalmente arrays de relações sem recorrer a heurísticas de detecção no validador.
2. **Atualizar Resolução no Validador**: Garantir que o `ExecutionResultValidator` resolva contratos de arquivo declarados explicitamente na `ExecutionRequest`.
3. **Refinar a Ontologia Semântica de Relações**:
   - Redefinir e restringir `HAS_POWER` estritamente a posse ativa confirmada na fonte.
   - Introduzir `CAN_CHOOSE_POWER` para opções de criação/progressão de personagem.
   - Introduzir `HAS_WEAKNESS` para fraquezas e vulnerabilidades explícitas.
4. **Governança de Referências Não Resolvidas**: Estabelecer formato e isolamento estrito para relações com alvos externos ou ausentes no livro (`unresolved-relations.json`), impedindo sua inclusão no grafo canônico.
5. **Matriz Declarativa de Compatibilidade**: Fornecer matriz de compatibilidade semântica legível por máquina (`relations-compatibility-matrix.json`) e sua documentação espelho.
6. **Estratégia de Migração Segura**: Definir protocolo de migração em duas fases (Audit-Only seguido de Human Approval Gate e Migration Apply).
7. **Imutabilidade Histórica**: Preservar o bundle `RB-ANIM-RELATIONS-att1-8317e31e` intacto como evidência forense.

### 2.2 Non-Goals

- **Não modificar código ou schemas existentes nesta etapa de especificação**: Este documento é puramente de design arquitetural.
- **Não criar `CAN_CHOOSE_WEAKNESS`**: Rejeitado por YAGNI. A fonte não possui menus de seleção de fraquezas opcionais.
- **Não inventar entidades placeholder**: Não criar registros fictícios para poderes externos ausentes (como *Rapidez*).
- **Não reexecutar o estágio de relações agora**: A reexecução de *Animalidade* (Attempt 2) somente ocorrerá após implementação, testes e aprovação desta arquitetura.
- **Não alterar dados nem publicar conteúdo**: Manter estritamente o isolamento da worktree principal.

---

## 3. Ontologia de Relações V2 (Relations V2 Ontology)

A ontologia de relações passa a ser governada por semântica estrita de proveniência e estado de jogo:

### 3.1 `HAS_POWER` (Restrição Semântica)
- **Definição**: A entidade de origem **possui ativamente e de forma inata/confirmada** o poder ou aprimoramento no seu estado de jogo padrão, sem necessidade de escolha prévia, alocação condicional de pontos ou decisão do jogador.
- **Exemplos Canônicos**: Traços inatos de monstros com ficha pronta, poderes fixos de NPCs, habilidades raciais automáticas.
- **Critério de Proveniência**: O texto da fonte deve afirmar categoricamente a posse direta (ex: *"Esta criatura possui Regeneração rápida"*, *"Poderes inatos: Garras"*). Se houver menção a lista de opções ou custo de pontos a escolher, `HAS_POWER` é expressamente proibido.

### 3.2 `CAN_CHOOSE_POWER` (Novo Tipo Canônico)
- **Definição**: O poder ou aprimoramento está disponível como **opção de seleção** na criação de personagem, evolução ou construção de ficha para a entidade, respeitando a economia de pontos ou regras do sistema.
- **Exemplos Canônicos**: Listas de "Poderes Possíveis" de cada Fera em *Animalidade*, listas de magias selecionáveis por círculo, aprimoramentos permitidos por kit/classe.
- **Critério de Proveniência**: Presença de listas de seleção de poderes, regras de alocação de pontos de personagem (ex: "5 pontos para gastar"), títulos como "Poderes Possíveis", "Opções Permitidas".
- **Semântica no Grafo**: Permite ao motor de regras e à UI orientar a construção de ficha, sem assumir falsamente que a entidade possui todas as habilidades listadas.

### 3.3 `HAS_WEAKNESS` (Novo Tipo Canônico)
- **Definição**: A entidade possui uma **fraqueza, vulnerabilidade, desvantagem ou restrição inata explícita** documentada na fonte.
- **Exemplos Canônicos**: *Vulnerabilidade a Prata*, *Dano Agravado por Fogo*, *Dependência Sanguínea*, *Fobia*.
- **Critério de Proveniência**: Menção explícita no texto da fonte de fraquezas, desvantagens automáticas ou restrições inerentes à criatura ou linhagem.

### 3.4 Decisão sobre `CAN_CHOOSE_WEAKNESS`
- **Veredito**: **REJEITADO (YAGNI / Ausência de Lastro Canônico)**.
- **Justificativa**: Nenhuma fonte analisada no piloto (e nem as regras canônicas de criação de Feras em *Animalidade*) apresenta menus de escolha livre de fraquezas. As fraquezas ou são fixas/inatas (`HAS_WEAKNESS`) ou são aprimoramentos negativos gerais adquiridos livremente pelo sistema Daemon comum. Criar este predicado violaria o princípio de *Não Invenção*.

---

## 4. Modelo de Versionamento (Versioning Model)

Para garantir evolução controlada e interoperabilidade entre livros e componentes do sistema, a governança de relações adota versionamento semântico explícito:

| Versão | Descrição | Status | Regras de Predicados |
|---|---|---|---|
| **V1** | Ontologia inicial permissiva | **DEPRECATED** | `HAS_POWER` sobrecarregado para posse e opções; ausência de `CAN_CHOOSE_POWER` e `HAS_WEAKNESS`. |
| **V2** | Ontologia formal com contratos explícitos | **ACTIVE (APPROVED SPEC)** | `HAS_POWER` estrito; inclusão de `CAN_CHOOSE_POWER` e `HAS_WEAKNESS`; suporte a `unresolved-relations.json`. |

### Regras de Transição
1. **Rejeição em Novos Executables**: A partir da ativação do V2, nenhuma `ExecutionRequest` ou pipeline de execução poderá produzir relações V1.
2. **Coexistência Temporária na Leitura**: Ferramentas de exportação e visualização aceitam V1 para compatibilidade regressiva de dados legados previamente congelados, mas emitem aviso de obsolescência (`DEPRECATION_WARNING`).
3. **Não Mistura**: Um arquivo `relations.json` deve pertencer integralmente à especificação V1 ou à especificação V2. É proibido mesclar convenções em um mesmo bundle.

---

## 5. Contrato de Coleção de Relações (Relation Collection Contract)

### 5.1 `relation.schema.json` (Item Contract)
Permanece como o contrato canônico para a validação de **uma instância individual de relação**. Ele valida tipos de dados, enums de predicado (`relationType`), referências a IDs (`sourceId`, `targetId`) e metadados de proveniência (`sourcePage`, `confidence`).

### 5.2 `relation-collection.schema.json` (Collection Contract)
Novo schema introduzido na raiz de `schemas/`:
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "relation-collection.schema.json",
  "title": "Daemon Relation Collection",
  "description": "Schema canônico para validação de coleções de relações (array de relações)",
  "type": "array",
  "items": {
    "$ref": "relation.schema.json"
  },
  "uniqueItems": true
}
```

### 5.3 Validação Explícita no `ExecutionResultValidator`
- A configuração da tarefa em `ExecutionRequest` deve declarar com precisão o schema esperado:
  ```json
  {
    "filePattern": "data/entities/relations.json",
    "outputSchemaName": "relation-collection.schema.json"
  }
  ```
- O `ExecutionResultValidator` resolve o schema correspondente a `outputSchemaName`. Como `relation-collection.schema.json` tem `type: "array"`, o validador aceita diretamente a lista de dicionários (`isinstance(payload, list)`), validando cada elemento contra a referência `$ref: "relation.schema.json"`.
- **Proibição de Heurísticas**: O validador **não** deve inspecionar o payload para adivinhar se deve envelopar listas automaticamente. O contrato deve ser explicitado formalmente na `ExecutionRequest`.

---

## 6. Matriz de Compatibilidade Declarativa (Machine-Readable Compatibility Matrix)

Para governar quais relações são semanticamente válidas entre as categorias de entidades do Daemon Tools, a especificação institui a Matriz de Compatibilidade Declarativa.

### 6.1 Arquivos Canônicos
1. **Definição de Dados**: `schemas/relations-compatibility-matrix.json` (consumível por validadores automatizados e scripts).
2. **Documentação Espelho**: `docs/reference/relations-compatibility-matrix.md` (leitura humana e consulta de desenvolvedores).

### 6.2 Estrutura da Matriz
A matriz valida a tripla:
`Source Entity Category` + `Relation Type` + `Target Entity Category`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Daemon Relations Compatibility Matrix",
  "version": "2.0.0",
  "rules": [
    {
      "relationType": "HAS_POWER",
      "allowedSourceCategories": ["creature_npc", "character_option"],
      "allowedTargetCategories": ["character_option"],
      "allowedTargetSubtypes": ["aprimoramento", "poder", "magia"],
      "semanticMeaning": "Active confirmed possession of power"
    },
    {
      "relationType": "CAN_CHOOSE_POWER",
      "allowedSourceCategories": ["creature_npc", "character_option"],
      "allowedTargetCategories": ["character_option"],
      "allowedTargetSubtypes": ["aprimoramento", "poder", "magia"],
      "semanticMeaning": "Selectable power option during character creation or progression"
    },
    {
      "relationType": "HAS_WEAKNESS",
      "allowedSourceCategories": ["creature_npc", "character_option"],
      "allowedTargetCategories": ["character_option"],
      "allowedTargetSubtypes": ["aprimoramento", "fraqueza", "desvantagem"],
      "semanticMeaning": "Innate weakness, vulnerability, or limitation"
    }
  ]
}
```

### 6.3 Especificação dos Tipos Principais na V2

| Relação | Origem Permitida | Destino Permitido | Cardinalidade | Semântica |
|---|---|---|---|---|
| `HAS_POWER` | `creature_npc`, `character_option` | `character_option` (poder, aprimoramento) | N:M | Posse ativa e inata confirmada. |
| `CAN_CHOOSE_POWER` | `creature_npc`, `character_option` | `character_option` (poder, aprimoramento) | N:M | Opção disponível para compra/seleção. |
| `HAS_WEAKNESS` | `creature_npc`, `character_option` | `character_option` (fraqueza, aprimoramento) | N:M | Fraqueza ou restrição intrínseca. |
| `MODIFIES` | `character_option` | `character_option` | N:M | Modificador mecânico de outra opção. |
| `REQUIRES` | `character_option` | `character_option` | N:M | Pré-requisito de compra ou ativação. |

---

## 7. Divisão de Responsabilidades e Semântica Fail-Closed

O pipeline estabelece uma barreira estrita e complementar entre validação técnica e semântica:

```
+-------------------------------------------------------------------------------+
|                             FASE 1: VALIDAÇÃO TÉCNICA                         |
|                    (Authority: ExecutionResultValidator)                      |
|                                                                               |
|  - Valida sintaxe JSON e integridade de arquivo                              |
|  - Valida payload contra relation-collection.schema.json                      |
|  - Valida itens contra relation.schema.json                                   |
|  - Rejeita campos extras (additionalProperties: false)                       |
|  - Rejeita tipos inválidos de atributos                                       |
+---------------------------------------+---------------------------------------+
                                        | PASS
                                        v
+-------------------------------------------------------------------------------+
|                             FASE 2: VALIDAÇÃO SEMÂNTICA                       |
|                 (Authority: PilotQAValidator / Semantic Validator)            |
|                                                                               |
|  - Verifica existência dos IDs de source e target no dataset de entidades     |
|  - Valida tripla contra schemas/relations-compatibility-matrix.json           |
|  - Verifica correspondência entre proveniência textual e tipo de relação      |
|  - Isola referências pendentes em unresolved-relations.json                   |
+-------------------------------------------------------------------------------+
```

### 7.1 Divisão de Responsabilidades
- **`ExecutionResultValidator`**: Responsável exclusivo pela conformidade técnica de schema e integridade de arquivos do bundle. Não avalia semântica narrativa ou regras de RPG.
- **`PilotQAValidator` / Validação Semântica**: Responsável exclusivo pela consistência do grafo, integridade referencial dos identificadores e adesão à Matriz de Compatibilidade Declarativa.

### 7.2 Semântica Fail-Closed
O pipeline opera sob regime **Fail-Closed** absoluto:
1. Se qualquer relação possuir um `relationType` não registrado na Matriz, a validação **falha imediatamente** (`ERR_INVALID_RELATION_TYPE`).
2. Se a categoria de origem ou destino violar as regras da Matriz, a validação **falha imediatamente** (`ERR_INCOMPATIBLE_RELATION_PAIR`).
3. Se um `targetId` não existir no banco de entidades aprovadas do livro e a relação estiver no `relations.json` canônico, a validação **falha imediatamente** (`ERR_DANGLING_RELATION_TARGET`).

---

## 8. Tratamento de Referências Não Resolvidas (Unresolved Relations)

Durante a extração de suplementos, é frequente encontrar menções a poderes, magias ou aprimoramentos descritos em outros livros do universo Daemon (ex: o poder *"Rapidez"* citado em *Garras de Sharikan* no suplemento *Animalidade*).

### 8.1 Princípios de Isolamento
1. **Proibição de Poluição Canônica**: Relações com alvos inexistentes no contexto do livro processado **nunca** devem ser inseridas no arquivo `data/entities/relations.json`.
2. **Proibição de Fabricação de Entidades**: É expressamente proibido fabricar entidades "fictícias" ou "placeholders" no arquivo de entidades para satisfazer uma chave estrangeira.
3. **Isolamento de Proveniência**: Toda referência a conceito externo ou ambíguo deve ser extraída para um arquivo auxiliar isolado: `data/entities/unresolved-relations.json`.

### 8.2 Contratos para Referências Não Resolvidas
- **Arquivo**: `data/entities/unresolved-relations.json`
- **Schema**: `schemas/unresolved-relation-collection.schema.json`

### 8.3 Modelo de Dados da Referência Não Resolvida
Cada entrada em `unresolved-relations.json` deve conter:
```json
{
  "sourceEntityId": "anim-creature-garras-de-sharikan",
  "candidateRelationType": "CAN_CHOOSE_POWER",
  "rawReferenceText": "Rapidez",
  "sourcePage": 10,
  "sourceParagraph": "Poderes Possíveis: Garras de Ferro, Rapidez, Faro Aguçado.",
  "reason": "EXTERNAL_SYSTEM_REFERENCE",
  "externalBookHint": "Vampiros: Os Teurgos / Livro Básico",
  "status": "UNRESOLVED_PENDING_CROSS_BOOK_LINK"
}
```

### 8.4 Extensão Futura: `UnresolvedRelationResolver`
A arquitetura reserva um componente futuro (`UnresolvedRelationResolver`) que, em estágios de publicação entre livros ou consolidação global de compêndio, poderá tentar resolver esses ponteiros pendentes contra índices globais do universo Daemon. No escopo do livro isolado, o arquivo permanece como registro de proveniência não resolvido.

---

## 9. Estratégia de Migração de Dados Históricos (Historical Migration Strategy)

Para livros ou dados pré-existentes que foram catalogados sob o modelo V1, a transição para V2 deve ser rigorosamente auditada:

### 9.1 Fase 1 — Audit Only (Somente Auditoria)
1. O script de migração analisa os arquivos `relations.json` legados sem aplicar alterações no disco.
2. Cada relação `HAS_POWER` é avaliada contra as regras e textos de proveniência de entidades do tipo `creature_npc` ou opções de personagem.
3. É gerado um relatório de auditoria (`migration-relations-v2-audit-report.json`) categorizando cada relação:
   - `KEEP_HAS_POWER`: Posse confirmada no texto.
   - `CONVERT_TO_CAN_CHOOSE_POWER`: Menção em lista de seleção ou poderes possíveis.
   - `CONVERT_TO_HAS_WEAKNESS`: Menção a fraquezas ou desvantagens.
   - `FLAG_UNRESOLVED`: Alvo não localizado no contexto do livro.

### 9.2 Gate de Aprovação Humana (Human Migration Gate)
Nenhuma migração pode ser escrita ou aplicada sem a revisão e aprovação explícita do operador humano sobre o relatório da Fase 1. A aprovação é registrada criptograficamente via `ReviewDecision`.

### 9.3 Fase 2 — Migration Apply (Aplicação de Migração)
Após o gate humano:
1. O script aplica deterministicamente as conversões aprovadas.
2. O arquivo `relations.json` é revalidado contra `relation-collection.schema.json` e a Matriz de Compatibilidade V2.
3. Relações não resolvidas são extraídas para `unresolved-relations.json`.

---

## 10. Status do Piloto Atual e Requisitos para Relations Attempt 2

### 10.1 Status Arquitetural de Animalidade Attempt 1
- O bundle `RB-ANIM-RELATIONS-att1-8317e31e` com manifesto hash `abd2f243d4936101d229ef96cdfdc044f7d75729dc67dfdc18675178dcc16ad2` é um **registro histórico congelado e imutável**.
- Ele atestou a existência de duas anomalias (técnica de validação e semântica de ontologia).
- **Decisão**: O Attempt 1 permanece classificado tecnicamente como `FAIL` (devido à incompatibilidade de schema da coleção) e semânticamente insatisfatório (pelo uso indevido de `HAS_POWER`). Ele **não** será alterado.

### 10.2 Pré-requisitos para Iniciar Animalidade Relations Attempt 2
Antes de emitir qualquer nova requisição de execução (`ExecutionRequest`) para o estágio de relações do livro *Animalidade*, os seguintes pré-requisitos devem ser atendidos e validados:
1. Implementação e teste dos schemas `relation-collection.schema.json` e `unresolved-relation-collection.schema.json`.
2. Atualização e teste do `ExecutionResultValidator` para suporte formal a schemas de coleção.
3. Implementação da Matriz de Compatibilidade V2 (`relations-compatibility-matrix.json`).
4. Atualização do `Relations Agent` para respeitar a distinção entre `HAS_POWER`, `CAN_CHOOSE_POWER` e isolar pendências em `unresolved-relations.json`.
5. Validação da suíte de regressão automatizada cobrindo todas as novas regras.
6. Criação de nova `ExecutionRequest` (`REQ-ANIM-001-RELATIONS-02`) e bundle de execução correspondente (`EB-ANIM-RELATIONS-att2-*`).

### 10.3 Resultado Semântico Esperado para Animalidade Attempt 2
A reexecução de *Animalidade* sob a ontologia V2 deverá gerar:
- **`HAS_POWER`**: **0 relações** (pois as 17 criaturas possuem apenas menus de "Poderes Possíveis", sem ficha pronta com poderes inatos fixos documentados).
- **`CAN_CHOOSE_POWER`**: **107 relações** (as combinações válidas de opções selecionáveis pelas 17 Feras dentro dos poderes locais de *Animalidade*).
- **`HAS_WEAKNESS`**: Relações mapeando fraquezas canônicas declaradas das Feras para entidades de fraqueza/aprimoramento negativo.
- **`unresolved-relations.json`**: **1 registro** contendo a menção a *"Rapidez"* em *Garras de Sharikan*, isolada como dependência externa pendente.

---

## 11. Requisitos de Validação e Testes de Regressão

Para garantir a estabilidade do sistema, os testes da versão 2 devem cobrir rigorosamente os seguintes cenários:

### 11.1 Testes de Contrato Estrutural
- `test_relation_collection_schema_valid`: Valida que arrays válidos de relações passam pelo schema `relation-collection.schema.json`.
- `test_relation_collection_schema_rejects_object`: Garante que um objeto único passado para o schema de coleção falha na validação.
- `test_relation_schema_rejects_array`: Garante que um array passado para `relation.schema.json` falha na validação com mensagem explícita.
- `test_relation_collection_unique_items`: Garante que relações duplicadas no array são rejeitadas.

### 11.2 Testes de Compatibilidade Semântica
- `test_compatibility_matrix_accepts_valid_triplets`: Valida que pares canônicos (`creature_npc` -> `CAN_CHOOSE_POWER` -> `character_option`) passam.
- `test_compatibility_matrix_rejects_invalid_relation`: Garante que predicados não autorizados falham na validação semântica.
- `test_compatibility_matrix_rejects_invalid_categories`: Garante que relações aplicadas a categorias inadequadas falham.

### 11.3 Testes de Referências Não Resolvidas
- `test_unresolved_relations_schema`: Valida a estrutura de `unresolved-relations.json`.
- `test_canonical_relations_rejects_dangling_targets`: Garante que nenhuma relação no `relations.json` canônico aponta para ID inexistente.

### 11.4 Teste de Regressão Obrigatório para o Bug Descoberto
Deve ser criado um teste de regressão específico reproduzindo exatamente o cenário do Attempt 1:
```python
def test_regression_relations_attempt_1_schema_contract():
    # 1. Payload de array com 108 relações
    # 2. Se validado contra relation.schema.json -> Deve falhar com ContractValidationError (comportamento documentado do bug)
    # 3. Se validado contra relation-collection.schema.json -> Deve passar com sucesso (comportamento corrigido)
```

### 11.5 Expansão do Teste Sintético E2E
O arquivo `tests/agents/test_pilot_pipeline_e2e.py` deve ser expandido para que o estágio `relations` seja exercitado de ponta a ponta com a geração real de `relations.json` validada contra o `ExecutionResultValidator`, sem bypass ou mocks de schema.

---

## 12. Requisitos de Documentação e Registro de Decisão Arquitetural (ADR)

1. **ADR-0004**: Deve ser formalizado no repositório em:
   `docs/context/decisions/ADR-0004-relations-v2-ontology-and-contracts.md`
   - Título: *ADR-0004: Relations V2 Ontology, Collection Contract, and Compatibility Governance*
   - Status: *Accepted*
   - Contexto: Achados do Piloto 005 (Attempt 1).
   - Decisão: Introdução de `relation-collection.schema.json`, refinamento de `HAS_POWER`, criação de `CAN_CHOOSE_POWER` e `HAS_WEAKNESS`, isolamento de referências externas em `unresolved-relations.json`.
   - Consequências: Eliminação de ambiguidade técnica no validador e alinhamento com a semântica de regras de criação de personagens Daemon.

2. **Atualização da Referência do Modelo de Dados**:
   - `docs/reference/data-model.md` deve ser atualizado para incorporar a ontologia de relações V2 e o contrato de coleção.

---

## 13. Sequência de Implementação no Nível de Design

A implementação futura da arquitetura V2 deverá seguir estritamente a sequência ordenada abaixo:

1. **Criação do Schema de Coleção**: Criar `schemas/relation-collection.schema.json`.
2. **Atualização do Schema de Relação**: Atualizar `schemas/relation.schema.json` para suportar formalmente os predicados `CAN_CHOOSE_POWER` e `HAS_WEAKNESS`.
3. **Criação do Schema de Referências Não Resolvidas**: Criar `schemas/unresolved-relation-collection.schema.json`.
4. **Criação da Matriz de Compatibilidade Machine-Readable**: Criar `schemas/relations-compatibility-matrix.json`.
5. **Criação da Documentação da Matriz**: Criar `docs/reference/relations-compatibility-matrix.md`.
6. **Atualização do Validador de Resultados**: Atualizar `scripts/agents/contracts.py` e `ExecutionResultValidator` para suportar mapeamento explícito de schemas de coleção.
7. **Implementação de Testes Estruturais Unitários**: Criar `tests/agents/test_relation_schemas.py` cobrindo todos os casos de validação estrutural.
8. **Implementação de Testes de Regressão**: Adicionar teste de regressão do bug do Attempt 1 em `tests/agents/test_relation_contracts_regression.py`.
9. **Implementação do Validador Semântico de Relações**: Adicionar validação contra a Matriz de Compatibilidade no `PilotQAValidator`.
10. **Atualização do Relations Agent**: Implementar regras de distinção semântica (`HAS_POWER` vs `CAN_CHOOSE_POWER` vs `HAS_WEAKNESS` e isolamento de referências externas).
11. **Atualização do Pré-visualizador Local (Projector/Server)**: Ajustar `scripts/agents/preview_projector.py` e `docs/assets/app.js` para renderizar `CAN_CHOOSE_POWER` e `HAS_WEAKNESS`.
12. **Expansão da Suíte E2E**: Atualizar `tests/agents/test_pilot_pipeline_e2e.py` para exercitar o estágio de relações completo.
13. **Registro do ADR-0004**: Criar `docs/context/decisions/ADR-0004-relations-v2-ontology-and-contracts.md`.
14. **Atualização do Data Model Reference**: Atualizar `docs/reference/data-model.md`.
15. **Execução Completa da Suíte de Testes**: Garantir aprovação de 100% dos testes automatizados.
16. **Emissão de Requisição para Relations Attempt 2**: Preparar `REQ-ANIM-001-RELATIONS-02` e bundle correspondente para revisão humana.

---

## 14. Critérios de Sucesso da Versão 2

A especificação e futura implementação da Versão 2 de Relações serão consideradas completas e bem-sucedidas quando:
1. O validador aceitar deterministicamente coleções de relações declaradas via `relation-collection.schema.json` sem falhas espúrias de tipo.
2. A ontologia distinguir com fidelidade canônica de 100% o que é posse ativa versus o que são opções de construção de personagem.
3. Nenhuma referência não resolvida (externa ou ambígua) contaminar o arquivo canônico `relations.json`.
4. Todas as suítes de testes automatizados (unitários, compatibilidade, regressão e E2E) passarem com zero falhas.
5. O Attempt 1 permanecer intocado e devidamente registrado no histórico de auditoria.
