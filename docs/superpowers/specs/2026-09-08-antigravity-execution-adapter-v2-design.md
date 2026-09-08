# Daemon Tools — Version 2: Antigravity Execution Adapter Design Spec

**Data:** 2026-09-08  
**Status:** DRAFT (Ready for Human Review)  
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
O objetivo da **Versão 2 (Antigravity Execution Adapter)** é construir a camada de execução desacoplada, segura e controlada que permite materializar o contexto, renderizar prompts, invocar agentes especialistas via adaptadores de modelo (com foco no ambiente Antigravity / Gemini), capturar respostas em um resultado provider-neutral, validar exaustivamente artefatos, evidências e escopo de escrita, e aplicar políticas estritas de reparo e escalonamento humano antes de qualquer persistência no repositório.

---

## 2. Limites e Fora de Escopo

### O que NÃO faz parte da Versão 2:
1. **Alteração do runtime determinístico da V1**: Os componentes `JobStore`, `HandoffStore`, `ContextLoader`, `ContextPackBuilder`, `GateEngine` e `OrchestratorStateSelector` mantêm seus contratos e garantias estabelecidas.
2. **Execução direta/autônoma pelo Orchestrator**: O Orchestrator continua estritamente limitado à decisão do próximo passo seguro; ele **nunca** executa agentes diretamente, não chama LLMs e não muta artefatos de domínio.
3. **Acoplamento de identidade aos modelos**: Modelos de linguagem (ex: Gemini 1.5 Pro, Flash, Claude, GPT) são parâmetros de infraestrutura/configuração de execução, nunca identidades lógicas dos agentes especialistas.
4. **Permissão de escrita direta pelo modelo**: Modelos nunca recebem acesso irrestrito para gravar no sistema de arquivos ou disparar comandos arbitrários sem validação prévia.
5. **Scheduler distribuído ou filas de mensageria complexas**: A execução permanece orientada a jobs determinísticos locais, com execução síncrona ou cooperativa simples.
6. **Automação de push/merge no upstream (`guraassessoria/daemon`)**: Todas as alterações continuam confinadas ao ambiente de trabalho local e ao fork de desenvolvimento (`SaruAkaza/daemon`), exigindo revisão humana explícita para upstream.

---

## 3. Arquitetura e Fluxo Completo de Execução

O fluxo de processamento de cada estágio segue uma sequência unidirecional, com gates de contenção e validação estritos:

```text
┌──────────────────────────────┐
│  OrchestratorStateSelector   │  (Analisa Job e seleciona: RUN_STAGE)
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│      Execution Request       │  (Contrato provider-neutral com write-scope e metadados)
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│     ContextMaterializer      │  (Invoca ContextPackBuilder + ContextLoader)
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│        PromptRenderer        │  (Monta o prompt final estruturado a partir do Context Pack)
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│       ExecutionAdapter       │  (FakeExecutionAdapter ou AntigravityExecutionAdapter)
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│       Execution Result       │  (Estrutura de saída padronizada provider-neutral)
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│   ExecutionResultValidator   │  (Valida Schema, Write-Scope, Evidências e Direitos)
└──────────────┬───────────────┘
               │
         ┌─────┴─────────────────────────┐
         │                               │
         ▼ (Válido)                      ▼ (Inválido)
┌──────────────────────────────┐   ┌──────────────────────────────┐
│ Persistência / HandoffStore  │   │        Repair Policy         │
│  (Atualização de JobState)   │   │  (Max 1 tentativa sintática) │
└──────────────────────────────┘   └──────────────┬───────────────┘
                                                  │
                                         ┌────────┴────────┐
                                         ▼ (Sucesso)       ▼ (Falha)
                                  [Revalidação]      ┌──────────────────┐
                                                     │  HUMAN_REVIEW /  │
                                                     │     BLOCKED      │
                                                     └──────────────────┘
```

---

## 4. Detalhamento dos Componentes

### 4.1 `OrchestratorStateSelector`
- **Função**: Avalia o estado do Job e retorna `OrchestratorSelection`.
- **Ação V2**: Quando a ação for `RUN_STAGE`, o orquestrador despacha a criação de uma `Execution Request`.

### 4.2 `Execution Request`
Estrutura de dados imutável e tipada que formaliza a ordem de trabalho para um agente especialista.
- **Campos Principais**:
  - `requestId`: Identificador único (ex: `REQ-TREVAS-001-EXTRACTION-01`).
  - `jobId`: Identificador do Job pai (ex: `JOB-TREVAS-001`).
  - `bookId`: Identificador da obra (ex: `trevas-3-0`).
  - `targetStage`: Estágio alvo do pipeline (`source`, `extraction`, `editorial`, `entities`, `relations`, `frontend`, `qa`, `release`).
  - `assignedAgent`: Identificador do agente especialista associado (ex: `extraction-agent`).
  - `allowedWriteScope`: Lista declarativa de padrões de caminho permitidos para escrita (ex: `["data/text/trevas-3-0.txt"]`).
  - `contextManifest`: Lista de arquivos/camadas a serem materializadas pelo `ContextMaterializer`.
  - `taskInstruction`: Instrução clara, objetiva e específica da tarefa do estágio.
  - `outputSchemaName`: Nome do schema JSON ou formato esperado para o artefato de saída.
  - `timeoutSeconds`: Limite de tempo de execução.
  - `metadata`: Metadados operacionais adicionais (ex: timestamps, solicitante).

### 4.3 `ContextMaterializer`
Componente responsável por resolver determinística e seguramente todas as referências do `contextManifest` da `Execution Request`:
- Utiliza o `ContextPackBuilder` para validar a conformidade com `schemas/context-pack.schema.json`.
- Utiliza o `ContextLoader` para ler os conteúdos UTF-8 do repositório, garantindo contenção de caminho (path containment) e proteção contra travessia de diretórios.
- Produz uma estrutura em memória com todos os textos das camadas (`mandatory`, `domain`, `bookContext`, `jobContext`, `handoffContext`, `task`, `outputContract`).

### 4.4 `PromptRenderer`
Componente puramente funcional e determinístico que compõe o prompt final a ser entregue ao adapter:
- **Camadas Injetadas**:
  1. *System Identity & Constitution*: Identidade do especialista (`docs/agents/<agent>.md`) + regras invioláveis da Constituição.
  2. *Domain Knowledge*: Taxonomia e regras de catalogação mínimas.
  3. *Book & Operational Context*: Metadados do livro, Job atual e Handoff do estágio anterior.
  4. *Task Instructions & Scope*: Instrução da tarefa específica e limites estritos de escrita (`allowedWriteScope`).
  5. *Output Schema & Evidence Requirements*: Contrato de formato de resposta, exigência de proveniência (página/fonte) e obrigatoriedade de registrar incertezas.
- **Garantia**: Sem interpolação dinâmica opaca; o prompt é totalmente inspecionável e reprodutível.

### 4.5 Camada de `ExecutionAdapter`
Interface abstrata provider-neutral que desacopla a lógica de negócios da ferramenta de execução:

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

#### 4.5.1 `FakeExecutionAdapter` (Modo Offline / Testes / CI)
- Projetado para suítes de testes unitários, testes de integração e CI do GitHub Actions.
- Responde deterministamente a partir de fixtures pré-configuradas ou respostas sintéticas baseadas no `requestId` ou `targetStage`.
- Zero consumo de tokens, zero chamadas de rede e execução em milissegundos.

#### 4.5.2 `AntigravityExecutionAdapter` (Modo Real / Runtime Antigravity)
- Conecta o pipeline ao runtime de subagentes/modelos do Antigravity.
- O modelo subjacente (ex: Gemini 2.5 Pro / Flash) é configurado como provedor de inferência, **sem** assumir a identidade do agente especialista.
- Trata timeouts, limites de taxa de requisições e normalização da resposta bruta para o formato canônico `ExecutionResult`.

---

## 5. Estrutura do `Execution Result` e Validação

### 5.1 Objeto `Execution Result`
A resposta do modelo é imediatamente encapsulada em uma estrutura padronizada provider-neutral:
- `executionId`: Identificador único da execução.
- `requestId`: Referência à Execution Request correspondente.
- `agent`: Identificador do agente executor.
- `stage`: Estágio do pipeline executado.
- `status`: `SUCCESS`, `VALIDATION_FAILED`, `REPAIR_FAILED`, `TIMEOUT`, `ERROR`.
- `proposedArtifacts`: Dicionário contendo os caminhos relativos e o conteúdo gerado de cada arquivo proposto.
- `evidence`: Lista de registros de proveniência (livro, página, seção, trecho original).
- `uncertainties`: Lista explícita de dúvidas, ambiguidades ou dados ausentes no material de origem.
- `rawResponse`: Resposta bruta para fins de auditoria e depuração.
- `metadata`: Duração da chamada, modelo utilizado, data/hora.

### 5.2 `ExecutionResultValidator`
Camada de validação que inspeciona o `Execution Result` antes de qualquer persistência em disco ou transição de estado:

1. **Validação de Write-Scope (Escopo de Escrita)**:
   - Checa se todo arquivo em `proposedArtifacts` corresponde estritamente aos caminhos autorizados em `allowedWriteScope` da requisição.
   - Qualquer tentativa de criar ou alterar arquivos fora do escopo (ex: tentar editar `schemas/` ou arquivos de outro estágio) resulta em rejeição imediata com `WRITE_SCOPE_VIOLATION`.

2. **Validação de Schema / Contrato de Saída**:
   - Se o artefato proposto for estruturado (ex: JSON), valida contra o schema correspondente usando `Draft202012Validator`.
   - Se for texto bruto (`extraction`), valida regras de limpeza, ausência de mojibake, integridade UTF-8 e cobertura de páginas.

3. **Validação de Evidência e Não-Invenção**:
   - Confirma a presença de proveniência (`book`, `page`) para todas as regras e entidades.
   - Checa se o agente registrou incertezas quando aplicável, em vez de inventar custos, alcances ou parâmetros omitidos no livro original.

4. **Validação de Direitos Autorais e Políticas**:
   - Confirma se o estágio e os artefatos respeitam as diretrizes de publicação e os gates do `GateEngine`.

---

## 6. Política de Reparo Estrutural (Repair Policy)

Para lidar com falhas de formatação comuns em LLMs sem comprometer o determinismo do sistema:

```text
[Resultado com Erro Estrutural/JSON]
               │
               ▼
   Tentativa de Reparo = 0?
    ├── SIM: Envia prompt de reparo estrutural (apenas sintaxe/schema)
    │        ├── Reparo Válido   ──→ Continua fluxo
    │        └── Reparo Inválido ──→ Escala para HUMAN_REVIEW / BLOCKED
    └── NÃO: Escala imediatamente (Máximo de 1 tentativa)
```

### Regras Invioláveis de Reparo:
1. **Máximo de 1 tentativa**: É permitida exatamente 1 tentativa de correção estrutural.
2. **Estritamente sintático/estrutural**: O prompt de reparo instrui apenas o ajuste de sintaxe JSON, escape de caracteres ou campos ausentes da casca estrutural.
3. **Proibição de Invenção Semântica**: O reparo **nunca** pode fabricar conteúdo semântico novo, novas regras, novos atributos ou deduções inexistentes na resposta original.
4. **Erros Semânticos ou de Write-Scope não têm reparo automático**: Se o modelo tentar escrever fora do escopo ou violar regras de domínio, o job vai diretamente para `human_review` ou `blocked`.

---

## 7. Escalonamento Humano e Integração com Handoffs

### 7.1 Gatilhos de Revisão Humana (`human_review` / `needs_review`)
O fluxo é interrompido e requer revisão humana explícita nas seguintes circunstâncias:
- Falha na política de reparo estrutural (reparo esgotado ou falho);
- Violação de escopo de escrita (`WRITE_SCOPE_VIOLATION`);
- Registro de incertezas graves pelo especialista (conflito entre tabelas do livro, texto ilegível);
- Dúvidas ou restrições de direitos autorais identificadas no `source_manifest`;
- Transição final para `done` (obrigatória conforme ADR-0002).

### 7.2 Criação de Handoffs
- Um `Agent Handoff` só é persistido via `HandoffStore` quando a execução de um estágio for validada com sucesso pelo `ExecutionResultValidator` e houver uma **transferência real de responsabilidade** para o próximo agente do pipeline.
- Execuções intermediárias com falha ou pendentes de reparo não geram poluição de handoffs na pasta de armazenamento.

---

## 8. Taxonomia de Falhas (Failure Taxonomy)

A Versão 2 introduz uma taxonomia padronizada de códigos de erro para diagnóstico preciso:

| Código de Erro | Categoria | Descrição | Comportamento do Pipeline |
| :--- | :--- | :--- | :--- |
| `ERR_EXEC_TIMEOUT` | Execução | Tempo limite de execução do adapter excedido | `BLOCKED` / Retry configurado |
| `ERR_PROVIDER_UNAVAILABLE` | Infraestrutura | Falha de conectividade ou serviço do provider indisponível | `BLOCKED` |
| `ERR_SCHEMA_VALIDATION` | Validação | O artefato retornado viola o schema JSON de saída | Aciona `Repair Policy` (max 1) |
| `ERR_WRITE_SCOPE_VIOLATION` | Segurança | O artefato proposto tenta escrever em caminho não autorizado | `BLOCKED` / `HUMAN_REVIEW` |
| `ERR_EVIDENCE_MISSING` | Conteúdo | Falta de proveniência obrigatória (página/livro) | `HUMAN_REVIEW` |
| `ERR_SEMANTIC_UNCERTAINTY` | Conteúdo | O agente identificou ambiguidade que requer julgamento humano | `HUMAN_REVIEW` |
| `ERR_REPAIR_EXHAUSTED` | Validação | A tentativa única de reparo estrutural falhou | `HUMAN_REVIEW` |
| `ERR_GATE_DENIED` | Governança | Decisão do GateEngine rejeitou a operação (ex: direitos autorais) | `BLOCKED` |

---

## 9. Segurança e Governança

1. **Princípio do Menor Privilégio**: O modelo recebe apenas o contexto mínimo necessário para sua etapa e tem escopo de escrita estritamente limitado à sua pasta de saída.
2. **Contenção de Diretórios**: Todas as operações de leitura e escrita passam por validação de contenção de caminho relativo para impedir travessia maliciosa ou acidental (`..`, links simbólicos externos, caminhos absolutos fora do workspace).
3. **Fail-Closed**: Qualquer estado desconhecido, falha de validação ou exceção não tratada bloqueia a progressão e exige auditoria humana.
4. **Auditabilidade Total**: Toda `Execution Request` e todo `Execution Result` geram registros rastreáveis com timestamps, hashes de integridade e metadados.

---

## 10. Estratégia de Testes

1. **Testes Unitários de Componentes**:
   - Testar `ContextMaterializer` contra manifestos válidos e inválidos.
   - Testar `PromptRenderer` garantindo formatação idêntica e correta das camadas.
   - Testar `ExecutionResultValidator` com cenários de violação de write-scope, schemas inválidos e falta de evidências.
   - Testar `RepairPolicy` com cenários de sucesso na 1ª tentativa e escalonamento na 2ª tentativa.
2. **Testes com `FakeExecutionAdapter`**:
   - Simular o ciclo completo de orquestração com adapters determinísticos locais.
   - Garantir 100% de execução offline, sem dependência de internet ou chaves de API.
3. **Integração no CI (GitHub Actions)**:
   - Os testes da V2 serão integrados ao workflow `Validate`, executando todos os gates com `FakeExecutionAdapter` em segundos.

---

## 11. Compatibilidade com a Versão 1

- A base de código da Versão 1 permanece 100% funcional e intacta.
- Os schemas existentes (`agent-job`, `agent-handoff`, `context-pack`, `review-request`, `source-manifest`, `relation`) continuam sendo as fontes canônicas de dados.
- O pipeline segue os 8 estágios oficiais definidos em `docs/architecture/pipeline.md`.
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
- **Tarefa 21 — Antigravity Execution Adapter**: Implementação do adapter de integração com o runtime Antigravity / Gemini em `scripts/agents/antigravity_adapter.py`.
- **Tarefa 22 — V2 End-to-End Orchestration Runner**: Implementação do executor integrado de estágios conectando o Orchestrator, Adapter, Validador e Stores.
- **Tarefa 23 — CI Integration & Regression Verification**: Atualização dos workflows de CI e suítes completas de testes.
- **Tarefa 24 — Version 2 Final Verification**: Auditoria e congelamento da baseline da V2.

---

## 13. Conclusão

Esta especificação estabelece o design canônico e seguro para a execução de agentes no Daemon Tools. Ao desacoplar estritamente a decisão (Orchestrator), a preparação (ContextMaterializer/PromptRenderer), a execução (ExecutionAdapter) e a validação (ExecutionResultValidator), garantimos total determinismo, proteção contra alucinações ou escrita fora de escopo, neutralidade de provedor e conformidade absoluta com as regras do acervo Daemon/Trevas.
