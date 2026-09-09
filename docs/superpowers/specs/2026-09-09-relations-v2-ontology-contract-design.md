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
   - No modelo de ontologia do Daemon Tools, `HAS_POWER` expressa: **the source entity actually possesses the target power** (a entidade de origem efetivamente possui o poder alvo).
   - **Posse efetiva é distinta de opção disponível/selecionável** (`actual possession != selectable/available option`).
   - Atribuir `HAS_POWER` a todas as opções da lista de "Poderes Possíveis" expressa falsamente que a entidade efetivamente possui todos os poderes da lista ao mesmo tempo, ignorando o limite canônico de pontos de construção e a natureza de menu de opções.
3. **Lacunas Adicionais Descobertas**:
   - **Fraquezas omitidas**: Fraquezas canônicas declaradas na fonte (ex: vulnerabilidade a prata, dano agravado) não tinham relação tipada. O modelo carece de `HAS_WEAKNESS`.
   - **Referências externas não resolvidas**: A Fera *Garras de Sharikan* cita o poder *"Rapidez"*. A auditoria léxica completa do suplemento *Animalidade* confirmou que *"Rapidez"* não existe em *Animalidade* — trata-se de um poder de outro livro do sistema Daemon. Injetar cegamente essa relação quebra a integridade referencial se a entidade de destino não existe no contexto do livro.

---

## 2. Goals e Non-Goals

### 2.1 Goals

1. **Definir Contrato Estrutural de Coleção**: Criar `schemas/relation-collection.schema.json` que valida formalmente arrays de relações sem recorrer a heurísticas de detecção no validador.
2. **Atualizar Resolução no Validador**: Garantir que o `ExecutionResultValidator` resolva contratos de arquivo declarados explicitamente na `ExecutionRequest`.
3. **Refinar a Ontologia Semântica de Relações**:
   - Redefinir `HAS_POWER` de forma exata: a entidade de origem efetivamente possui o poder alvo (`the source entity actually possesses the target power`), distinguindo posse efetiva de opções selecionáveis.
   - Introduzir `CAN_CHOOSE_POWER`: a entidade de origem possui o poder alvo disponível como opção de seleção durante criação ou progressão de personagem (`the source entity has the target power available as a selectable option during character creation or progression`).
   - Introduzir `HAS_WEAKNESS`: a entidade de origem possui a fraqueza, vulnerabilidade ou limitação alvo (`the source entity possesses the target weakness, vulnerability, or limitation`).
4. **Governança de Referências Não Resolvidas**: Estabelecer formato e isolamento estrito para relações com alvos externos ou ausentes no livro através do artifact lógico `unresolved-relations.json`, mantendo referências não resolvidas fora do grafo canônico de relações (`relations.json`).
5. **Matriz Declarativa de Compatibilidade**:
   - Fonte de autoridade canônica legível por máquina: `schemas/relation-compatibility-v2.json`.
   - Schema validador da matriz: `schemas/relation-compatibility.schema.json`.
   - Documentação humana explicativa (`markdown = explanatory only`), linkando para a matriz canônica sem duplicar triplets ou regras propensas a divergência.
6. **Estratégia de Migração Segura**: Definir protocolo de migração em duas fases (Audit-Only seguido de Human Approval Gate e Migration Apply).
7. **Imutabilidade Histórica**: Preservar o bundle `RB-ANIM-RELATIONS-att1-8317e31e` intacto como evidência forense (status `NEEDS_REWORK`).
8. **Isolamento de Conteúdo Restrito**: Preservar a invariante de que dados de livros com direitos restritos ou não certificados (como *Animalidade*, classificado como `UNKNOWN`, `NOT_PUBLIC`, `LOCAL_RESTRICTED`) **nunca entram no main worktree do Git** e operam estritamente no workspace restrito de runtime.

### 2.2 Non-Goals

- **Não modificar código ou schemas existentes nesta etapa de especificação**: Este documento é puramente de design arquitetural.
- **Não criar `CAN_CHOOSE_WEAKNESS`**: Rejeitado por YAGNI. A fonte não possui menus de seleção de fraquezas opcionais.
- **Não inventar entidades placeholder**: Não criar registros fictícios para poderes externos ausentes (como *Rapidez*).
- **Não reexecutar o estágio de relações agora**: A reexecução de *Animalidade* (Attempt 2) somente ocorrerá após implementação completa de V2, migração e verificação global.
- **Não autorizar conteúdo restrito no main worktree**: O artifact conceitual `unresolved-relations.json` não autoriza commit de dados restritos no Git.
- **Não criar Implementation Plan prematuramente**: Esta etapa encerra-se com a entrega e revisão da especificação de design.

---

## 3. Ontologia de Relações V2 (Relations V2 Ontology)

A ontologia de relações passa a ser governada por semântica estrita de proveniência e estado de jogo:

### 3.1 `HAS_POWER` (Definição Canônica)
- **Definição**: **The source entity actually possesses the target power.** (A entidade de origem efetivamente possui o poder alvo).
- **Distinção Essencial**: Posse efetiva é estritamente distinta de opção selecionável ou disponível (`actual possession != selectable/available option`).
- **Escopo**: Não restringir posse a suposições restritivas como "innate", "native", "standard stat block" ou "starting character" a menos que uma decisão arquitetural futura faça isso explicitamente. A exigência canônica é que a fonte confirme a posse efetiva daquele poder pela entidade.
- **Critério de Proveniência**: O texto da fonte deve afirmar a posse efetiva (ex: afirmação direta de que a criatura possui o poder ou habilidade). Se a fonte indicar uma lista de opções ou custo de pontos a gastar/escolher, `HAS_POWER` é proibido e deve ser utilizado `CAN_CHOOSE_POWER`.

### 3.2 `CAN_CHOOSE_POWER` (Novo Tipo Canônico)
- **Definição**: **The source entity has the target power available as a selectable option during character creation or progression.** (A entidade de origem possui o poder alvo disponível como opção de seleção durante criação ou progressão de personagem).
- **Exemplos Canônicos**: Listas de "Poderes Possíveis" de cada Fera em *Animalidade*, listas de opções permitidas por classe/kit, magias selecionáveis por círculo.
- **Critério de Proveniência**: Presença de listas de seleção de poderes, regras de alocação de pontos de personagem (ex: "5 pontos para gastar"), cabeçalhos como "Poderes Possíveis", "Opções Permitidas".
- **Semântica no Grafo**: Permite ao motor de regras e à UI orientar a construção de ficha, sem assumir falsamente que a entidade possui todas as habilidades listadas.

### 3.3 `HAS_WEAKNESS` (Novo Tipo Canônico)
- **Definição**: **The source entity possesses the target weakness, vulnerability, or limitation.** (A entidade de origem possui a fraqueza, vulnerabilidade ou limitação alvo).
- **Exemplos Canônicos**: *Vulnerabilidade a Prata*, *Dano Agravado por Fogo*, *Dependência Sanguínea*, *Fobia*.
- **Critério de Proveniência**: Menção na fonte de fraquezas, desvantagens automáticas ou restrições inerentes à entidade.

### 3.4 Decisão sobre `CAN_CHOOSE_WEAKNESS`
- **Veredito**: **REJEITADO (YAGNI / Ausência de Lastro Canônico)**.
- **Justificativa**: Nenhuma fonte analisada no piloto (e nem as regras canônicas de criação de Feras em *Animalidade*) apresenta menus de escolha de fraquezas opcionais. As fraquezas documentadas são efetivamente possuídas pela criatura (`HAS_WEAKNESS`) ou são aprimoramentos negativos gerais adquiridos pelo sistema Daemon comum. Criar este predicado agora violaria o princípio de *Não Invenção* e YAGNI.

---

## 4. Modelo de Versionamento (Versioning Model)

Para garantir evolução controlada e integridade entre livros e componentes do sistema, a governança de relações adota versionamento semântico explícito:

| Versão | Descrição | Status | Regras de Predicados |
|---|---|---|---|
| **V1** | Ontologia inicial permissiva | **HISTORICAL / READ-ONLY** | `HAS_POWER` sobrecarregado para posse e opções; ausência de `CAN_CHOOSE_POWER` e `HAS_WEAKNESS`. |
| **V2** | Ontologia formal com contratos explícitos | **MANDATORY FOR NEW EXECUTION** | `HAS_POWER` canônico (posse efetiva); inclusão de `CAN_CHOOSE_POWER` e `HAS_WEAKNESS`; suporte a `unresolved-relations.json`. |

### Regras de Transição
1. **Rejeição em Novos Executables**: A partir da ativação do V2, nenhuma `ExecutionRequest` ou pipeline de execução poderá produzir relações V1.
2. **Coexistência na Leitura Histórica**: Ferramentas de exportação e visualização aceitam V1 como somente-leitura (`read-only`) para fins de auditoria e compatibilidade regressiva de dados históricos congelados.
3. **Não Mistura**: Um arquivo `relations.json` deve pertencer integralmente à especificação V1 ou à especificação V2. É proibido mesclar convenções em um mesmo bundle.

---

## 5. Contrato de Coleção de Relações (Relation Collection Contract)

### 5.1 `relation.schema.json` (Item Contract)
Permanece como o contrato canônico para a validação de **uma instância individual de relação**. Ele valida tipos de dados, enums de predicado (`relationType`), referências a IDs (`sourceId`, `targetId`) e metadados de proveniência (`sourcePage`, `confidence`).

### 5.2 `relation-collection.schema.json` (Collection Contract)
Novo schema canônico para validação estrutural de coleções de relações:
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
- O `ExecutionResultValidator` resolve o schema correspondente a `outputSchemaName`. Como `relation-collection.schema.json` define `type: "array"`, o validador aceita diretamente a lista de instâncias (`isinstance(payload, list)`), validando cada elemento contra a referência `$ref: "relation.schema.json"`.
- **Proibição de Heurísticas**: O validador **não** deve inspecionar o payload para adivinhar se deve envelopar listas automaticamente. O contrato deve ser explicitado formalmente na `ExecutionRequest`.

---

## 6. Matriz de Compatibilidade Declarativa (Machine-Readable Compatibility Matrix)

Para governar quais relações são semanticamente válidas entre as categorias de entidades do Daemon Tools, a especificação institui a Matriz de Compatibilidade Declarativa.

### 6.1 Arquivos e Autoridade Canônica
1. **Autoridade Canônica da Matriz (Machine-Readable JSON)**:
   - Arquivo de dados da matriz: `schemas/relation-compatibility-v2.json`.
   - **Regra de Autoridade**: `machine-readable JSON = canonical authority`.
2. **Schema Validador da Matriz**:
   - Arquivo de schema: `schemas/relation-compatibility.schema.json`.
   - Valida a estrutura, integridade e integridade dos tipos da matriz V2.
3. **Documentação Humana (Markdown)**:
   - Arquivo documental: `docs/reference/relation-compatibility-v2.md`.
   - **Regra de Documentação**: `markdown = explanatory only`. A documentação explica as regras e referencia a matriz JSON canônica, sem duplicar manualmente listas completas de triplets sujeitas a divergência acidental.

### 6.2 Estrutura da Matriz Canônica (`schemas/relation-compatibility-v2.json`)
A matriz valida a tripla:
`Source Entity Category` + `Relation Type` + `Target Entity Category`

```json
{
  "$schema": "relation-compatibility.schema.json",
  "version": "2.0.0",
  "rules": [
    {
      "relationType": "HAS_POWER",
      "allowedSourceCategories": ["creature_npc", "character_option"],
      "allowedTargetCategories": ["character_option"],
      "allowedTargetSubtypes": ["aprimoramento", "poder", "magia"],
      "semanticMeaning": "Actual possession of power by the source entity"
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
      "semanticMeaning": "Possession of weakness, vulnerability, or limitation"
    }
  ]
}
```

### 6.3 Especificação dos Tipos Principais na V2

| Relação | Origem Permitida | Destino Permitido | Cardinalidade | Semântica Canônica |
|---|---|---|---|---|
| `HAS_POWER` | `creature_npc`, `character_option` | `character_option` (poder, aprimoramento) | N:M | A entidade de origem efetivamente possui o poder alvo. |
| `CAN_CHOOSE_POWER` | `creature_npc`, `character_option` | `character_option` (poder, aprimoramento) | N:M | O poder alvo está disponível como opção selecionável. |
| `HAS_WEAKNESS` | `creature_npc`, `character_option` | `character_option` (fraqueza, aprimoramento) | N:M | A entidade de origem possui a fraqueza ou vulnerabilidade alvo. |
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
|  - Valida tripla contra schemas/relation-compatibility-v2.json                |
|  - Verifica correspondência entre proveniência textual e tipo de relação      |
|  - Isola referências pendentes no artifact lógico unresolved-relations.json   |
+-------------------------------------------------------------------------------+
```

### 7.1 Divisão de Responsabilidades
- **`ExecutionResultValidator`**: Responsável exclusivo pela conformidade técnica de schema e integridade de arquivos do bundle. Não avalia semântica narrativa ou regras de RPG.
- **`PilotQAValidator` / Validação Semântica**: Responsável exclusivo pela consistência do grafo, integridade referencial dos identificadores e adesão à Matriz de Compatibilidade Declarativa (`schemas/relation-compatibility-v2.json`).

### 7.2 Semântica Fail-Closed
O pipeline opera sob regime **Fail-Closed** absoluto:
1. Se qualquer relação possuir um `relationType` não registrado na Matriz Canônica, a validação **falha imediatamente** (`ERR_INVALID_RELATION_TYPE`).
2. Se a categoria de origem ou destino violar as regras da Matriz Canônica, a validação **falha imediatamente** (`ERR_INCOMPATIBLE_RELATION_PAIR`).
3. Se um `targetId` não existir no banco de entidades aprovadas do livro e a relação estiver no `relations.json` canônico, a validação **falha imediatamente** (`ERR_DANGLING_RELATION_TARGET`).

---

## 8. Tratamento de Referências Não Resolvidas (Unresolved Relations)

Durante a extração de suplementos, é frequente encontrar menções a poderes, magias ou aprimoramentos descritos em outros livros do universo Daemon (ex: o poder *"Rapidez"* citado em *Garras de Sharikan* no suplemento *Animalidade*).

### 8.1 Princípios de Isolamento e Não Proliferação
1. **Proibição de Poluição Canônica**: Relações com alvos inexistentes no contexto do livro processado **nunca** devem ser inseridas no grafo canônico de relações (`relations.json`). Referência não resolvida não é aresta canônica (`unresolved relation != canonical edge`).
2. **Proibição de Fabricação de Entidades**: É expressamente proibido fabricar entidades "fictícias" ou "placeholders" no arquivo de entidades para satisfazer uma chave estrangeira.
3. **Artifact Lógico Separado**: Toda referência a conceito externo ou ambíguo deve ser capturada no artifact lógico:
   `unresolved-relations.json`

### 8.2 Localização do Artifact e Isolamento de Conteúdo Restrito
- **Harmonização do Caminho Físico**: A especificação define o artifact lógico `unresolved-relations.json` separado de `relations.json`. O caminho físico final desse artifact deve ser harmonizado na fase de implementação com:
  1. O modelo de dados vigente (`docs/reference/data-model.md`).
  2. O escopo de escrita do Result Bundle (`allowedWriteScope`).
  3. O workspace isolado do piloto restrito (`.daemon_runtime/workspaces/pilot/<bookId>/`).
  4. A política de publicação e direitos autorais do repositório.
- **Política Estrita de Conteúdo Restrito**: Livros do piloto como *Animalidade* permanecem sob classificação:
  `UNKNOWN`, `NOT_PUBLIC`, `LOCAL_RESTRICTED`.
  **Invariante Absoluta**: Conteúdo restrito do piloto **NUNCA** entra na main worktree do Git (`data/`, `docs/assets/data/`, `Livros/`). A existência conceitual de um path canônico para dados certificados não autoriza a escrita de dados restritos no Git.

### 8.3 Modelo de Dados da Referência Não Resolvida
Cada entrada no artifact lógico `unresolved-relations.json` deve conter:
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
A arquitetura reserva um componente futuro (`UnresolvedRelationResolver`) que, em estágios de publicação entre livros ou consolidação global de compêndio, poderá tentar resolver esses ponteiros pendentes contra índices globais do universo Daemon. No escopo do livro isolado, o artifact permanece como registro de proveniência não resolvido.

---

## 9. Estratégia de Migração de Dados Históricos (Historical Migration Strategy)

Para livros ou dados pré-existentes que foram catalogados sob o modelo V1, a transição para V2 deve ser rigorosamente auditada:

### 9.1 Fase 1 — Audit Only (Somente Auditoria)
1. O script de migração analisa os arquivos `relations.json` legados sem aplicar alterações no disco.
2. Cada relação `HAS_POWER` é avaliada contra os textos de proveniência e regras de criação da entidade:
   - Se o texto indicar posse efetiva -> categorizado como `KEEP_HAS_POWER`.
   - Se o texto indicar menu de opções / poderes possíveis -> categorizado como `CONVERT_TO_CAN_CHOOSE_POWER`.
   - Se o texto indicar fraqueza ou vulnerabilidade -> categorizado como `CONVERT_TO_HAS_WEAKNESS`.
   - Se o alvo não existir no contexto local -> categorizado como `FLAG_UNRESOLVED`.
3. É gerado um relatório de auditoria (`migration-relations-v2-audit-report.json`) sem alterar os arquivos de dados.

### 9.2 Gate de Aprovação Humana (Human Migration Gate)
Nenhuma migração pode ser escrita ou aplicada sem a revisão e aprovação explícita do operador humano sobre o relatório da Fase 1. A aprovação é registrada criptograficamente via `ReviewDecision`.

### 9.3 Fase 2 — Migration Apply (Aplicação de Migração)
Após o gate humano:
1. O script aplica deterministicamente as conversões aprovadas.
2. O arquivo `relations.json` é revalidado contra `relation-collection.schema.json` e a Matriz Canônica V2 (`schemas/relation-compatibility-v2.json`).
3. Relações não resolvidas são isoladas no artifact `unresolved-relations.json`.

---

## 10. Status do Piloto Atual e Requisitos para Relations Attempt 2

### 10.1 Status Arquitetural de Animalidade Attempt 1
- O bundle `RB-ANIM-RELATIONS-att1-8317e31e` com manifesto hash `abd2f243d4936101d229ef96cdfdc044f7d75729dc67dfdc18675178dcc16ad2` é um **registro histórico congelado e imutável**.
- Ele atestou a existência de duas lacunas (técnica de validação de coleção e semântica de ontologia de poderes).
- **Decisão**: O Attempt 1 permanece imutável com status `NEEDS_REWORK`. Ele **não** será alterado nem sobrescrito.

### 10.2 Pré-requisitos para Iniciar Animalidade Relations Attempt 2
Nenhuma execução de Relations Attempt 2 será iniciada antes de cumpridos os seguintes pré-requisitos:
1. Implementação e aprovação dos schemas `relation-collection.schema.json`, `relation-compatibility.schema.json` e `schemas/relation-compatibility-v2.json`.
2. Atualização e teste do `ExecutionResultValidator` para suporte formal a schemas de coleção.
3. Atualização do `Relations Agent` para respeitar a distinção exata entre posse efetiva (`HAS_POWER`) e opções selecionáveis (`CAN_CHOOSE_POWER`), além de isolar pendências em `unresolved-relations.json`.
4. Execução da estratégia de migração em dados históricos (Fase 1 Audit + Human Gate + Fase 2 Apply).
5. Validação da suíte de testes de regressão automatizada cobrindo todas as novas regras.
6. Criação e selamento de nova `ExecutionRequest` (`REQ-ANIM-001-RELATIONS-02`) e bundle correspondente (`EB-ANIM-RELATIONS-att2-*`).

### 10.3 Resultado Semântico Esperado para Animalidade Attempt 2
A reexecução de *Animalidade* sob a ontologia V2 deverá gerar:
- **`HAS_POWER`**: **0 relações** (pois as 17 criaturas documentam apenas menus de "Poderes Possíveis" para escolha via pontos de criação, sem posse efetiva de poderes descrita).
- **`CAN_CHOOSE_POWER`**: **107 relações** (opções válidas disponíveis para escolha pelas 17 Feras dentro dos poderes locais de *Animalidade*).
- **`HAS_WEAKNESS`**: Relações mapeando fraquezas efetivamente possuídas pelas Feras para entidades correspondentes.
- **`unresolved-relations.json`**: **1 registro** contendo a menção a *"Rapidez"* em *Garras de Sharikan*, isolada fora do grafo canônico.

---

## 11. Requisitos de Validação e Testes de Regressão

Para garantir a estabilidade do sistema, os testes da versão 2 devem cobrir rigorosamente os seguintes cenários:

### 11.1 Testes de Contrato Estrutural
- `test_relation_collection_schema_valid`: Valida que arrays válidos de relações passam pelo schema `relation-collection.schema.json`.
- `test_relation_collection_schema_rejects_object`: Garante que um objeto único passado para o schema de coleção falha na validação.
- `test_relation_schema_rejects_array`: Garante que um array passado para `relation.schema.json` falha na validação com mensagem explícita.
- `test_relation_collection_unique_items`: Garante que relações duplicadas no array são rejeitadas.

### 11.2 Testes de Compatibilidade Semântica
- `test_compatibility_matrix_validates_against_schema`: Garante que `schemas/relation-compatibility-v2.json` valida 100% contra `schemas/relation-compatibility.schema.json`.
- `test_compatibility_matrix_accepts_valid_triplets`: Valida que pares canônicos (`creature_npc` -> `CAN_CHOOSE_POWER` -> `character_option`) passam.
- `test_compatibility_matrix_rejects_invalid_relation`: Garante que predicados não autorizados falham na validação semântica.
- `test_compatibility_matrix_rejects_invalid_categories`: Garante que relações aplicadas a categorias inadequadas falham.

### 11.3 Testes de Referências Não Resolvidas
- `test_unresolved_relations_schema`: Valida a estrutura do artifact `unresolved-relations.json`.
- `test_canonical_relations_rejects_dangling_targets`: Garante que nenhuma relação no `relations.json` canônico aponta para ID inexistente no contexto local.

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

### 12.1 Sequência de ADRs do Repositório
A inspeção determinística de `docs/context/decisions/` revelou a sequência existente:
- `ADR-0001-repository-context-is-agent-memory.md`
- `ADR-0002-human-validation-required-for-done.md`
- `ADR-0003-development-fork-and-upstream-release-model.md`

**Próximo ADR Verificado**: `verified next ADR = ADR-0004`.

### 12.2 Formalização do ADR-0004
O ADR-0004 deve ser registrado em:
`docs/context/decisions/ADR-0004-relations-v2-ontology-and-contracts.md`
- **Título**: *ADR-0004: Relations V2 Ontology, Collection Contract, and Compatibility Governance*
- **Status**: *Accepted*
- **Contexto**: Achados técnicos e semânticos do Piloto 005 (Attempt 1).
- **Decisão**:
  - Introdução de `relation-collection.schema.json` para validação de listas.
  - Definição canônica de `HAS_POWER` (posse efetiva).
  - Criação de `CAN_CHOOSE_POWER` (opções selecionáveis) e `HAS_WEAKNESS` (fraquezas efetivas).
  - Rejeição de `CAN_CHOOSE_WEAKNESS` por YAGNI.
  - Instituição de `schemas/relation-compatibility-v2.json` como autoridade única de compatibilidade, validada por `schemas/relation-compatibility.schema.json`.
  - Isolamento de referências externas no artifact lógico `unresolved-relations.json`.
  - Protocolo de migração histórica em duas fases com gate humano obrigatório.

---

## 13. Sequência de Implementação no Nível de Design

A futura implementação da arquitetura V2 deverá seguir estritamente a sequência ordenada abaixo:

1. **Criação do Schema de Coleção**: Criar `schemas/relation-collection.schema.json`.
2. **Atualização do Schema de Relação**: Atualizar `schemas/relation.schema.json` para suportar formalmente os predicados `CAN_CHOOSE_POWER` e `HAS_WEAKNESS`.
3. **Criação do Schema da Matriz de Compatibilidade**: Criar `schemas/relation-compatibility.schema.json`.
4. **Criação da Matriz de Compatibilidade Canônica**: Criar `schemas/relation-compatibility-v2.json` (autoridade canônica).
5. **Criação da Documentação da Matriz**: Criar `docs/reference/relation-compatibility-v2.md` (somente explicativa).
6. **Definição de Schema para Referências Não Resolvidas**: Criar schema validador para o artifact lógico `unresolved-relations.json`.
7. **Atualização do Validador de Resultados**: Atualizar `scripts/agents/contracts.py` e `ExecutionResultValidator` para suportar mapeamento explícito de schemas de coleção.
8. **Implementação de Testes Estruturais Unitários**: Criar `tests/agents/test_relation_schemas.py` cobrindo validação estrutural de item e coleção.
9. **Implementação de Testes de Regressão**: Adicionar teste de regressão do bug do Attempt 1 em `tests/agents/test_relation_contracts_regression.py`.
10. **Implementação do Validador Semântico de Relações**: Adicionar validação contra a Matriz Canônica no `PilotQAValidator`.
11. **Atualização do Relations Agent**: Implementar regras de distinção semântica (`HAS_POWER` vs `CAN_CHOOSE_POWER` vs `HAS_WEAKNESS` e isolamento de referências externas em `unresolved-relations.json`).
12. **Atualização do Pré-visualizador Local (Projector/Server)**: Ajustar `scripts/agents/preview_projector.py` e `docs/assets/app.js` para suportar os novos predicados e o isolamento de referências não resolvidas.
13. **Expansão da Suíte E2E**: Atualizar `tests/agents/test_pilot_pipeline_e2e.py` para exercitar o estágio de relações completo.
14. **Registro do ADR-0004**: Criar `docs/context/decisions/ADR-0004-relations-v2-ontology-and-contracts.md`.
15. **Atualização da Referência do Modelo de Dados**: Harmonizar `docs/reference/data-model.md` com a ontologia V2 e a governança de isolamento de conteúdo restrito.
16. **Emissão de Requisição para Relations Attempt 2**: Após conclusão dos passos anteriores e aprovação global, preparar `REQ-ANIM-001-RELATIONS-02` e bundle correspondente.

---

## 14. Critérios de Sucesso da Versão 2

A especificação e futura implementação da Versão 2 de Relações serão consideradas completas e bem-sucedidas quando:
1. O validador aceitar deterministicamente coleções de relações declaradas via `relation-collection.schema.json` sem falhas espúrias de tipo.
2. A ontologia distinguir com fidelidade canônica de 100% posse efetiva (`HAS_POWER`) de opções de construção de personagem (`CAN_CHOOSE_POWER`).
3. Nenhuma referência não resolvida (externa ou ambígua) contaminar o grafo canônico `relations.json`, sendo mantida no artifact lógico `unresolved-relations.json`.
4. Conteúdo restrito do piloto permanecer estritamente isolado do main worktree do Git.
5. A matriz `schemas/relation-compatibility-v2.json` atuar como autoridade canônica única de compatibilidade.
6. Todas as suítes de testes automatizados (unitários, compatibilidade, regressão e E2E) passarem com zero falhas.
7. O Attempt 1 permanecer intocado e devidamente registrado com status `NEEDS_REWORK`.
