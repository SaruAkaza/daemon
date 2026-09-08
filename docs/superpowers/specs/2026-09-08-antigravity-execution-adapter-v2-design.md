# Daemon Tools — Version 2: Antigravity Execution Adapter Design Spec

**Data:** 2026-09-08  
**Status:** DRAFT (Post-Review 001 — Ready for Human Review)  
**Baseline Base:** Version 1 (`multiagent-context-v1` — `38046b192fb8e98108800a82a45274b780811c27`)  
**Branch:** `feat/antigravity-execution-adapter-v2`  

---

## 1. Visão Geral e Objetivo da Versão 2

### 1.1 Contexto
A **Versão 1** do Daemon Tools estabeleceu com rigor determinístico toda a fundação estrutural, de contexto e governança do sistema multiagente:
- Contratos tipados e esquemas JSON Draft 2020-12 (`schemas/`);
- Contratos provider-neutral para 8 papéis especialistas (`docs/agents/`);
- Armazenamento atômico e imutável de estado (`JobStore`, `HandoffStore`);
- Carregamento seguro e restrito de arquivos de repositório (`ContextLoader`);
- Montagem determinística de contexto mínimo suficiente por camadas (`ContextPackBuilder`);
- Validação estrita e fail-closed de transições e direitos autorais (`GateEngine`);
- Seleção determinística de estado sem efeitos colaterais (`OrchestratorStateSelector`);
- Prova de integração ponta a ponta e CI automatizado no GitHub Actions.

A **Versão 1** deliberadamente não executava agentes reais.

### 1.2 Objetivo da Versão 2
O objetivo da **Versão 2 (Antigravity Execution Adapter)** é construir a camada de execução desacoplada, segura e controlada que permite materializar o contexto pré-construído, renderizar prompts, invocar agentes especialistas via adaptadores de execução provider-neutral, capturar propostas de alteração em um resultado padronizado, validar exaustivamente artefatos, evidências e escopo de escrita, e aplicar políticas estritas de reparo e escalonamento humano antes que qualquer alteração seja persistida no repositório por camadas autorizadas.

---

## 2. Limites, Fora de Escopo e Regras Fundamentais

### 2.1 Regra Arquitetural de Não-Mutação Direta pelo Modelo
> [!IMPORTANT]
> **LLM output MUST NOT directly mutate the repository.**  
> O modelo/provedor de IA e a camada de execução **nunca** recebem autoridade para alterar arquivos diretamente no sistema de arquivos, disparar commits ou gravar no repositório. O adapter retorna estritamente **propostas estruturadas de alteração** dentro do `Execution Result`. Somente após validação completa e aprovação por todos os gates técnicos e de segurança é que uma futura camada de persistência/aplicação poderá aplicar as alterações.

### 2.2 O que NÃO faz parte da Versão 2:
1. **Alteração do runtime determinístico da V1**: Os componentes `JobStore`, `HandoffStore`, `ContextLoader`, `ContextPackBuilder`, `GateEngine` e `OrchestratorStateSelector` mantêm seus contratos e garantias estabelecidas.
2. **Execução direta/autônoma pelo Orchestrator**: O Orchestrator continua estritamente limitado à decisão do próximo passo seguro; ele **nunca** executa agentes diretamente, não chama LLMs e não muta artefatos de domínio.
3. **Acoplamento de identidade aos modelos**: Modelos de linguagem são parâmetros de infraestrutura/configuração externa resolvidos via `executionProfile`, **nunca** identidades lógicas dos agentes especialistas.
4. **Mutação direta pelo modelo ou adapter**: `ExecutionAdapter`, `PromptRenderer` e o modelo subjacente são estritamente isolados da gravação de arquivos de domínio.
5. **Scheduler distribuído ou filas de mensageria complexas**: A execução permanece orientada a jobs determinísticos locais, com execução síncrona ou cooperativa simples.
6. **Automação de push/merge no upstream (`guraassessoria/daemon`)**: Todas as alterações continuam confinadas ao ambiente de trabalho local e ao fork de desenvolvimento (`SaruAkaza/daemon`), exigindo revisão humana explícita para upstream.

---

## 3. Arquitetura e Fluxo Completo de Execução

O fluxo de processamento opera como uma cadeia sequencial com separação estrita de responsabilidades:

```text
┌─────────────────────────────────────────────────────────────┐
│                 OrchestratorStateSelector                   │  (Analisa Job e seleciona ação: RUN_STAGE)
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                     Execution Request                       │  (Contrato com jobId, targetStage, assignedAgent,
│          (contendo Context Pack validado pela V1)           │   allowedWriteScope, executionProfile e contextPack)
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    ContextMaterializer                      │  (validated Context Pack → ContextLoader
│               (Dereferenciação pura sem I/O de busca)       │   → Materialized Context em memória)
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                       PromptRenderer                        │  (Monta o prompt final estruturado e inspecionável
│                  (Composição determinística)                │   a partir do Materialized Context e Request)
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                      ExecutionAdapter                       │  (FakeExecutionAdapter ou
│              (Invoca adapter provider-neutral)              │   AntigravityExecutionAdapter resolvido por profile)
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                      Execution Result                       │  (Estrutura de saída provider-neutral contendo apenas
│             (Propostas de alteração em memória)             │   proposedArtifacts, evidence, uncertainties)
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                  ExecutionResultValidator                   │  (Validações em cadeia fail-closed:
│                 (Portão de Contenção Estrito)               │   1. Schema validation
└──────────────┬──────────────────────────────┬───────────────┘   2. Evidence validation
               │                              │                   3. Uncertainty validation
               │ (Aprovado)                   │ (Falha estrutural)4. Write-scope validation [FAIL-CLOSED]
               │                              │                   5. Policy & GateEngine validation)
               ▼                              ▼
┌──────────────────────────────┐   ┌──────────────────────────────┐
│  Futura Camada de Aplicação  │   │        Repair Policy         │
│  e Persistência Controlada   │   │  (Max 1 tentativa sintática; │
│   (Write-Scope Autorizado)   │   │   proibido inventar semântica│
└──────────────┬───────────────┘   └──────────────┬───────────────┘
               │                                  │
               ▼                                  ├───────────┬───────────┐
┌──────────────────────────────┐                  │ (Sucesso) │ (Falha)   │ (Violação de Escopo)
│        HandoffStore          │                  ▼           ▼           ▼
│ (Somente em transferência    │           [Revalidação] ┌───────────────────────────┐
│ real e validada entre fases) │                         │   HUMAN_REVIEW / BLOCKED  │
└──────────────────────────────┘                         └───────────────────────────┘
```

---

## 4. Detalhamento dos Componentes e Responsabilidades

### 4.1 `OrchestratorStateSelector`
- **Responsabilidade**: Analisa deterministamente o estado do Job e retorna `OrchestratorSelection`.
- **Comportamento na V2**: Quando a seleção for `RUN_STAGE`, emite os dados necessários para gerar a `Execution Request`. Não executa adapters, não chama LLMs e não carrega arquivos.

### 4.2 `Execution Request`
Estrutura de dados imutável e tipada que formaliza uma ordem de trabalho provider-neutral.
- **Campos Principais**:
  - `requestId`: Identificador único da solicitação (ex: `REQ-TREVAS-001-EXTRACTION-01`).
  - `jobId`: Identificador do Job pai (ex: `JOB-TREVAS-001`).
  - `bookId`: Identificador da obra (ex: `trevas-3-0`).
  - `targetStage`: Estágio alvo do pipeline (`source`, `extraction`, `editorial`, `entities`, `relations`, `frontend`, `qa`, `release`).
  - `assignedAgent`: Identificador do agente especialista associado (ex: `extraction-agent`).
  - `allowedWriteScope`: Lista explícita de padrões/caminhos relativos permitidos para escrita (ex: `["data/text/trevas-3-0.txt"]`).
  - `executionProfile`: Perfil de execução abstrato configurado externamente (ex: `"default-high"`, `"default-fast"`, `"offline-test"`).
  - `contextPack`: Objeto `Context Pack` completo, pré-construído pelo `ContextPackBuilder` e validado contra `schemas/context-pack.schema.json`.
  - `taskInstruction`: Instrução explícita da tarefa técnica do estágio.
  - `outputSchemaName`: Nome do schema JSON ou contrato de saída esperado para validação.
  - `timeoutSeconds`: Limite de tempo de execução.
  - `metadata`: Metadados operacionais (timestamps, solicitante).

### 4.3 `ContextMaterializer`
Componente estritamente focado em dereferenciação e carregamento seguro de conteúdo.
- **Fronteira Exata de Responsabilidade**:
  ```text
  validated Context Pack → ContextLoader → Materialized Context
  ```
- **O que o ContextMaterializer FAZ**:
  - Recebe um `Context Pack` que **já foi construído** pelo `ContextPackBuilder` e **já foi validado** contra o schema.
  - Itera sobre as listas de caminhos relativos declarados em cada camada (`mandatory`, `domain`, `bookContext`, `jobContext`, `handoffContext`, `task`, `outputContract`).
  - Invoca o [`ContextLoader`](file:///c:/Users/TI%20Prevent/Documents/Painel%20de%20Impressoras/Daemon%20Tools/scripts/agents/context_loader.py) para carregar com segurança o texto UTF-8 de cada arquivo referenciado.
  - Retorna uma estrutura em memória `MaterializedContext` contendo os textos indexados por camada e proveniência de arquivo.
- **O que o ContextMaterializer NÃO FAZ**:
  - **NÃO** seleciona arquivos de contexto.
  - **NÃO** faz busca, discovery ou varredura de diretórios.
  - **NÃO** chama o `ContextPackBuilder` para decidir ou reconstruir o pack.
  - **NÃO** interpreta ou avalia seções de *Mandatory Context* ou *Optional Context* dos arquivos de documentação dos agentes.

### 4.4 `PromptRenderer`
Componente determinístico e puramente funcional que monta o prompt final estruturado.
- **Entrada**: `MaterializedContext` + `ExecutionRequest`.
- **Composição em Camadas**:
  1. *System Identity & Inviolable Constitution*: Identidade do papel especialista (`docs/agents/<assignedAgent>.md`) e cláusulas pétreas da Constituição.
  2. *Domain Rules & Reference*: Taxonomia e regras de catalogação mínimas da camada `domain`.
  3. *Operational & Book Context*: Metadados estruturais do livro, Job ativo e Handoff anterior.
  4. *Task Instructions & Scope Boundaries*: Instrução técnica da tarefa e delimitação explícita dos caminhos de escrita (`allowedWriteScope`).
  5. *Output Schema & Evidence Requirements*: Formato estruturado exigido para o resultado, obrigatoriedade de proveniência (livro/página) e exigência estrita de registrar incertezas em vez de inventar regras.
- **Garantia**: Saída 100% auditável, inspecionável e reproduzível.

### 4.5 Camada de `ExecutionAdapter` e Neutralidade de Provedor
Interface abstrata provider-neutral que encapsula a interação com o executor:

```python
class ExecutionAdapter(ABC):
    @abstractmethod
    def execute(
        self,
        request: ExecutionRequest,
        prompt: RenderedPrompt,
    ) -> ExecutionResult:
        """Executes the rendered prompt and returns a structured ExecutionResult."""
        pass
```

#### 4.5.1 Neutralidade de Provedor e Resolução de Modelos
Nenhum contrato, schema, agente, job ou orquestrador possui acoplamento rígido a nomes de modelos ou provedores proprietários.
A resolução segue a cadeia de configuração externa:

```text
Execution Request (executionProfile)
        ↓
Configuração Externa de Ambiente / Profiles
        ↓
Provider (ex: Antigravity, Fake, Subprocess)
        ↓
Model / Inference Engine (ex: Gemini 3.7 High, Gemini 2.5 Flash, Mock)
```

- Trocar o modelo subjacente (ex: alterar de um modelo High para um modelo Fast ou para outro provedor) é uma decisão de **configuração externa**, **sem exigir alteração** nos contratos de Job, nos contratos de Agente, no `ContextPack`, na `ExecutionRequest` ou no `OrchestratorStateSelector`.

#### 4.5.2 `FakeExecutionAdapter` (Testes Offline / CI)
- Implementação determinística sem rede e sem custo de tokens para testes unitários, testes de integração e CI do GitHub Actions.
- Responde com fixtures estáticas ou sintéticas controladas com base no `requestId` ou `targetStage`.

#### 4.5.3 `AntigravityExecutionAdapter` (Runtime Antigravity)
- Conecta o pipeline ao runtime Antigravity via perfil configurável (ex: profile `default-high` mapeado externamente para `Antigravity` com `Gemini 3.7 High`).
- O modelo atua exclusivamente como motor de inferência, sem jamais assumir a identidade lógica do especialista (que é definida pelo contrato do agente).
- Trata timeouts, rate limits e normaliza a resposta em um `ExecutionResult` provider-neutral.

---

## 5. Estrutura do `Execution Result`, Validação e Não-Mutação

### 5.1 Objeto `Execution Result` (Proposta em Memória)
A resposta do adapter é encapsulada em uma estrutura padronizada provider-neutral:
- `executionId`: Identificador único da execução.
- `requestId`: Referência à Execution Request correspondente.
- `agent`: Identificador do agente executor.
- `stage`: Estágio do pipeline executado.
- `status`: `SUCCESS`, `VALIDATION_FAILED`, `REPAIR_FAILED`, `TIMEOUT`, `ERROR`.
- `proposedArtifacts`: Dicionário `{ "caminho/relativo": "conteudo_proposto" }` contendo as propostas de alteração em memória.
- `evidence`: Lista de registros de proveniência (livro, página, seção, trecho original).
- `uncertainties`: Lista explícita de dúvidas, ambiguidades ou dados ausentes no material de origem.
- `rawResponse`: Resposta bruta para fins de auditoria e depuração.
- `metadata`: Duração da chamada, profile utilizado, data/hora.

### 5.2 `ExecutionResultValidator`
Camada de auditoria rigorosa e fail-closed executada antes de qualquer persistência:

1. **Validação de Write-Scope (Escopo de Escrita — Fail-Closed)**:
   - Checa se cada caminho presente em `proposedArtifacts` corresponde estritamente aos padrões autorizados em `allowedWriteScope`.
   - Se houver **qualquer** arquivo fora do escopo (ex: tentativa de criar/modificar arquivos em `schemas/`, `scripts/`, `docs/architecture/` ou pastas de outros estágios), a validação falha imediatamente com `ERR_WRITE_SCOPE_VIOLATION`.
   - **Nenhuma alteração parcial é aplicada** (comportamento estritamente atômico e seguro).

2. **Validação de Schema / Contrato de Saída**:
   - Validação formal do payload JSON proposto contra o schema Draft 2020-12 do estágio.
   - Para texto bruto (`extraction`), validação de limpeza, ausência de caracteres corrompidos/mojibake, integridade UTF-8 e cobertura de páginas.

3. **Validação de Evidência e Não-Invenção**:
   - Confirma a presença de proveniência (`book`, `page`) para todas as entidades e regras extraídas.
   - Checa se o agente registrou incertezas quando aplicável, em vez de inventar custos, alcances ou parâmetros omitidos no livro original.

4. **Validação de Direitos Autorais e Políticas**:
   - Confirma se o estágio e os artefatos respeitam as diretrizes de publicação e os gates do `GateEngine`.

### 5.3 Aplicação Controlada de Alterações
Somente quando o `ExecutionResultValidator` emitir veredito `ALLOW` em todas as checagens:
- A camada de persistência/aplicação autorizada grava os arquivos em disco de forma atômica.
- O `JobStore` atualiza o estado do Job para registrar o sucesso do estágio.
- Se houver transferência de responsabilidade para o próximo estágio, o `HandoffStore` persiste o respectivo `Agent Handoff`.

---

## 6. Política de Reparo Estrutural (Repair Policy)

Para corrigir falhas puramente sintáticas em LLMs sem comprometer o determinismo do sistema:

```text
[Resultado com Erro de Formatação/Schema]
                   │
                   ▼
       Tentativa de Reparo = 0?
        ├── SIM: Envia prompt de reparo estrutural (apenas sintaxe/schema)
        │        ├── Reparo Válido   ──→ Continua para revalidação
        │        └── Reparo Inválido ──→ Escala para HUMAN_REVIEW / BLOCKED
        └── NÃO: Escala imediatamente (Máximo de 1 tentativa permitida)
```

### Regras Invioláveis de Reparo:
1. **Máximo de 1 tentativa**: É permitida exatamente uma tentativa de ajuste estrutural.
2. **Estritamente sintático/estrutural**: O prompt de reparo restringe-se a corrigir JSON malformado, escape de aspas ou cascas estruturais ausentes.
3. **Proibição Absoluta de Invenção Semântica**: O reparo **nunca** pode fabricar conteúdo semântico novo, novas regras, novos atributos ou deduções inexistentes na resposta original.
4. **Erros Semânticos e de Write-Scope NÃO têm reparo automático**: Tentativas de escrita fora de escopo ou violações de domínio bloqueiam o pipeline imediatamente sem disparo de prompt de reparo.

---

## 7. Escalonamento Humano e Integração com Handoffs

### 7.1 Gatilhos de Revisão Humana (`human_review` / `needs_review`)
O fluxo é interrompido e requer revisão humana explícita nas seguintes circunstâncias:
- Falha na política de reparo estrutural (reparo esgotado ou falho);
- Violação de escopo de escrita (`ERR_WRITE_SCOPE_VIOLATION`);
- Registro de incertezas relevantes pelo especialista (conflito entre tabelas do livro, texto ilegível, regras contraditórias);
- Restrições de direitos autorais identificadas no `source_manifest`;
- Transição final para `done` (obrigatória conforme [ADR-0002](file:///c:/Users/TI%20Prevent/Documents/Painel%20de%20Impressoras/Daemon%20Tools/docs/context/decisions/ADR-0002-human-validation-required-for-done.md)).

### 7.2 Criação de Handoffs
- Um [`Agent Handoff`](file:///c:/Users/TI%20Prevent/Documents/Painel%20de%20Impressoras/Daemon%20Tools/schemas/agent-handoff.schema.json) só é persistido via `HandoffStore` quando a execução de um estágio for validada com sucesso pelo `ExecutionResultValidator` e houver uma **transferência real de responsabilidade** para o próximo agente do pipeline.
- Execuções intermediárias com falha, canceladas ou pendentes de reparo não geram poluição de handoffs na pasta de armazenamento.

---

## 8. Taxonomia de Falhas (Failure Taxonomy)

A Versão 2 estabelece códigos de erro determinísticos para diagnóstico e tratamento:

| Código de Erro | Categoria | Descrição | Comportamento do Pipeline |
| :--- | :--- | :--- | :--- |
| `ERR_EXEC_TIMEOUT` | Execução | Tempo limite de execução do adapter excedido | `BLOCKED` / Retry configurado |
| `ERR_PROVIDER_UNAVAILABLE` | Infraestrutura | Falha de conectividade ou serviço do provider indisponível | `BLOCKED` |
| `ERR_SCHEMA_VALIDATION` | Validação | O artefato retornado viola o schema JSON de saída | Aciona `Repair Policy` (max 1) |
| `ERR_WRITE_SCOPE_VIOLATION` | Segurança | O artefato proposto tenta escrever em caminho não autorizado | `BLOCKED` / `HUMAN_REVIEW` (Fail-Closed) |
| `ERR_EVIDENCE_MISSING` | Conteúdo | Falta de proveniência obrigatória (página/livro) | `HUMAN_REVIEW` |
| `ERR_SEMANTIC_UNCERTAINTY` | Conteúdo | O agente identificou ambiguidade que requer julgamento humano | `HUMAN_REVIEW` |
| `ERR_REPAIR_EXHAUSTED` | Validação | A tentativa única de reparo estrutural falhou | `HUMAN_REVIEW` |
| `ERR_GATE_DENIED` | Governança | Decisão do GateEngine rejeitou a operação (ex: direitos autorais) | `BLOCKED` |

---

## 9. Segurança e Governança

1. **Princípio do Menor Privilégio**: O modelo recebe apenas o contexto mínimo suficiente para seu estágio e tem escopo de escrita estritamente limitado à sua pasta de saída.
2. **Contenção e Imutabilidade do Repositório**: Toda leitura passa pelo `ContextLoader` com verificação estrita de caminhos relativos para impedir travessia maliciosa (`..`, links simbólicos externos). A escrita é sempre mediada e validada antes de atingir o disco.
3. **Fail-Closed e Atomicidade**: Violações de escopo de escrita ou erros de validação descartam imediatamente toda a proposta de alteração em memória, impedindo escritas parciais ou arquivos corrompidos.
4. **Auditabilidade Total**: Toda `Execution Request` e todo `Execution Result` geram registros rastreáveis com timestamps, hashes de integridade e metadados.

---

## 10. Estratégia de Testes

1. **Testes Unitários de Componentes**:
   - Testar `ContextMaterializer` dereferenciando Context Packs válidos via `ContextLoader`.
   - Testar `PromptRenderer` garantindo formatação idêntica e correta das camadas.
   - Testar `ExecutionResultValidator` com cenários de violação de write-scope, schemas inválidos e falta de evidências.
   - Testar `RepairPolicy` com cenários de sucesso na 1ª tentativa e escalonamento na 2ª tentativa.
2. **Testes com `FakeExecutionAdapter`**:
   - Simular o ciclo completo de orquestração com adapters determinísticos locais.
   - Garantir 100% de execução offline, sem dependência de internet ou chaves de API.
3. **Integração no CI (GitHub Actions)**:
   - Os testes da V2 serão integrados ao workflow [`Validate`](file:///c:/Users/TI%20Prevent/Documents/Painel%20de%20Impressoras/Daemon%20Tools/.github/workflows/validate.yml), executando todos os gates com `FakeExecutionAdapter` em segundos.

---

## 11. Compatibilidade com a Versão 1

- A base de código da Versão 1 permanece 100% funcional e intacta.
- Os schemas existentes (`agent-job`, `agent-handoff`, `context-pack`, `review-request`, `source-manifest`, `relation`) continuam sendo as fontes canônicas de dados.
- O pipeline segue os 8 estágios oficiais definidos em [`docs/architecture/pipeline.md`](file:///c:/Users/TI%20Prevent/Documents/Painel%20de%20Impressoras/Daemon%20Tools/docs/architecture/pipeline.md).
- Os testes da V1 continuam executando e passando como baseline de regressão.

---

## 12. Roteiro de Implementação Futura (Fases da V2)

A implementação da Versão 2 será dividida nas seguintes tarefas sequenciais e incrementais:

- **Tarefa 15 — Execution Request & Result Schemas**: Criação dos esquemas canônicos `schemas/execution-request.schema.json` e `schemas/execution-result.schema.json`.
- **Tarefa 16 — ContextMaterializer**: Implementação do materializador de contexto em `scripts/agents/context_materializer.py` e testes unitários.
- **Tarefa 17 — PromptRenderer**: Implementação do montador determinístico de prompts em `scripts/agents/prompt_renderer.py` e testes de camadas.
- **Tarefa 18 — ExecutionAdapter Interface & FakeExecutionAdapter**: Implementação da interface base e do adapter falso para testes em `scripts/agents/execution_adapter.py`.
- **Tarefa 19 — ExecutionResultValidator & Write-Scope**: Implementação do validador de resultados e do validador de escopo de escrita em `scripts/agents/execution_validator.py`.
- **Tarefa 20 — Structural Repair Engine**: Implementação do motor de reparo sintático (max 1 tentativa) em `scripts/agents/repair_engine.py`.
- **Tarefa 21 — Antigravity Execution Adapter**: Implementação do adapter de integração com o runtime Antigravity / Gemini via perfis configuráveis em `scripts/agents/antigravity_adapter.py`.
- **Tarefa 22 — V2 End-to-End Orchestration Runner**: Implementação do executor integrado de estágios conectando o Orchestrator, Adapter, Validador e Stores.
- **Tarefa 23 — CI Integration & Regression Verification**: Atualização dos workflows de CI e suítes completas de testes.
- **Tarefa 24 — Version 2 Final Verification**: Auditoria e congelamento da baseline da V2.

---

## 13. Conclusão

Esta especificação estabelece o design canônico e seguro para a execução de agentes no Daemon Tools. Ao desacoplar estritamente a decisão (Orchestrator), a preparação (ContextMaterializer/PromptRenderer), a execução (ExecutionAdapter) e a validação (ExecutionResultValidator), garantimos total determinismo, proteção contra alucinações ou escrita fora de escopo, neutralidade de provedor e conformidade absoluta com as regras do acervo Daemon/Trevas.
