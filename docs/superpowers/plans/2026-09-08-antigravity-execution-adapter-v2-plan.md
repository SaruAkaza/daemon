# Antigravity Execution Adapter V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Construir a camada provider-neutral de execução controlada da V2 sem conceder autoridade direta de escrita ao LLM.

**Architecture:** A decisão permanece no OrchestratorStateSelector. A execução é separada em contratos, construção de request, materialização de contexto, renderização de prompt, adapter de execução, reparo determinístico e validação do resultado antes de qualquer persistência.

**Tech Stack:** Python 3.12, JSON Schema Draft 2020-12, jsonschema, pytest, Git/GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-08-antigravity-execution-adapter-v2-design.md`

---

## 1. Global Constraints & Architectural Rules

1. **Compatibilidade com a V1**: Todos os componentes da V1 (`JobStore`, `HandoffStore`, `ContextLoader`, `ContextPackBuilder`, `GateEngine`, `OrchestratorStateSelector` e suite completa de testes) permanecem 100% funcionais e inalterados em suas garantias essenciais.
2. **LLM Output is Untrusted Input**: Nenhuma resposta de modelo de linguagem tem autoridade direta de escrita sobre o repositório (`LLM output MUST NOT directly mutate the repository`).
3. **Sem Autoridade de Persistência no Adapter e Pipeline**: `ExecutionAdapter`, `PromptRenderer`, `ExecutionCoordinator` e o modelo de IA retornam apenas propostas estruturadas de alteração (`proposedArtifacts`) dentro do `Execution Result`.
4. **Persistência Exclusivamente Pós-Validação**: Alterações só podem ser aplicadas em disco por uma camada de aplicação autorizada após aprovação determinística pelo `ExecutionResultValidator`.
5. **Decisão Exclusiva no OrchestratorStateSelector**: O `OrchestratorStateSelector` continua sendo a única camada que decide o próximo passo seguro (`RUN_STAGE`, `WAIT`, `BLOCKED`, `HUMAN_REVIEW`, `READY_FOR_DONE`). Nenhum componente da V2 assume autoridade de orquestração ou transição.
6. **Construção de Request Desacoplada**: A criação da `ExecutionRequest` é responsabilidade de um construtor determinístico (`ExecutionRequestBuilder`), que recebe a seleção já aprovada e os parâmetros de escopo.
7. **Neutralidade de Provedor e Modelos**: `ExecutionRequest` e `ExecutionResult` são totalmente provider-neutral. A resolução de provedores e modelos (ex: Gemini 3.7 High, Gemini 2.5 Flash, Mock) é tratada externamente via `executionProfile`.
8. **Reparo Estrutural Estritamente Determinístico (Sem Provedor / Sem Semântica)**: A única tentativa de reparo permitida é **mecanicamente determinística** (ex: limpeza de blocos markdown ```json, normalização de casca sintática). O reparo **NUNCA chama LLM/provedor** e **NUNCA inventa regras, atributos, entidades, evidências ou conclusões**.
9. **Write-Scope Fail-Closed**: Violações de escopo de escrita (`allowedWriteScope`) rejeitam toda a proposta atômica em memória. Nenhuma escrita parcial é permitida.
10. **Testes 100% Offline e Determinísticos**: A suíte de testes padrão e o CI do GitHub Actions utilizam exclusivamente o `FakeExecutionAdapter`, sem necessidade de tokens, chaves de API ou chamadas de rede.
11. **Nenhuma Dependência Runtime Obrigatória de Gemini**: A arquitetura da V2 não acopla identidades lógicas de agentes a nenhum provedor proprietário.
12. **Condicionalidade Estrita da Task 24**: A integração Antigravity é auditada primeiro; se não houver API programática oficialmente suportada, o resultado é `DEFERRED_PENDING_RUNTIME_API`, sem placeholders, sem automação de browser (Selenium/Puppeteer) e sem automação de GUI.
13. **Upstream Intocado**: Todas as alterações são confinadas ao fork de desenvolvimento (`SaruAkaza/daemon`); `guraassessoria/daemon` permanece intacto.

---

## 2. Mapa Geral de Arquivos da V2

| Arquivo | Ação | Responsabilidade |
| :--- | :--- | :--- |
| `schemas/execution-request.schema.json` | Criar | Schema Draft 2020-12 para ordens de trabalho de execução |
| `schemas/execution-result.schema.json` | Criar | Schema Draft 2020-12 para respostas de execução com propostas |
| `scripts/agents/execution_request_builder.py` | Criar | Construtor determinístico de `ExecutionRequest` a partir de Job e Selection |
| `scripts/agents/context_materializer.py` | Criar | Materialização em memória de `ContextPack` validado via `ContextLoader` |
| `scripts/agents/prompt_renderer.py` | Criar | Montagem determinística de prompts por camadas a partir do contexto materializado |
| `scripts/agents/execution_profile.py` | Criar | Resolução e registro de perfis de execução provider-neutral (`executionProfile`) |
| `scripts/agents/execution_adapter.py` | Criar | Protocolo `ExecutionAdapter` e implementação `FakeExecutionAdapter` |
| `scripts/agents/repair_engine.py` | Criar | Parser e motor determinístico de reparo sintático (sem provider, max 1) |
| `scripts/agents/write_scope.py` | Criar | Validador fail-closed de caminhos de escrita autorizados (`allowedWriteScope`) |
| `scripts/agents/execution_validator.py` | Criar | Validador agregado de resultados (Schema, Escopo, Evidências, Políticas) |
| `scripts/agents/execution_coordinator.py` | Criar | Coordenador em memória da cadeia de execução da V2 (sem mutação no repo) |
| `scripts/agents/antigravity_adapter.py` | **Condicional** | Adapter Antigravity (apenas se houver API programática real; caso contrário DEFERRED) |
| `tests/agents/test_execution_contracts.py` | Criar | Testes dos schemas e do `ExecutionRequestBuilder` |
| `tests/agents/test_context_materializer.py` | Criar | Testes unitários do `ContextMaterializer` |
| `tests/agents/test_prompt_renderer.py` | Criar | Testes unitários do `PromptRenderer` |
| `tests/agents/test_execution_profile.py` | Criar | Testes de resolução de perfis de execução |
| `tests/agents/test_execution_adapter.py` | Criar | Testes do protocolo adapter e `FakeExecutionAdapter` |
| `tests/agents/test_repair_engine.py` | Criar | Testes de parsing e reparo puramente sintático sem chamadas de rede |
| `tests/agents/test_write_scope.py` | Criar | Testes de validação de escopo de escrita (traversal, absolute, glob) |
| `tests/agents/test_execution_validator.py` | Criar | Testes agregados de validação e códigos de erro da taxonomia |
| `tests/agents/test_execution_coordinator_e2e.py` | Criar | Teste E2E do coordenador de execução em memória |
| `tests/agents/test_antigravity_adapter.py` | **Condicional** | Testes de integração Antigravity (apenas se API programática existir) |

---

## 3. Sequência Detalhada de Implementação (Tarefas 15 a 24)

---

### Task 15 — Execution Contracts & Request Builder

**Goal:** Definir os contratos formais JSON Schema Draft 2020-12 para `ExecutionRequest` e `ExecutionResult`, e implementar o `ExecutionRequestBuilder` determinístico responsável por instanciar requisições de execução válidas a partir de um Job e da seleção aprovada do Orchestrator.

**Files:**
- Create: `schemas/execution-request.schema.json`
- Create: `schemas/execution-result.schema.json`
- Create: `scripts/agents/execution_request_builder.py`
- Create: `tests/agents/test_execution_contracts.py`

**Interfaces / Schemas / Assinaturas:**
- `schemas/execution-request.schema.json`:
  - `required`: `["schemaVersion", "requestId", "jobId", "bookId", "targetStage", "assignedAgent", "allowedWriteScope", "executionProfile", "contextPack", "taskInstruction", "outputSchemaName"]`
- `schemas/execution-result.schema.json`:
  - `required`: `["schemaVersion", "executionId", "requestId", "agent", "stage", "status", "proposedArtifacts", "evidence", "uncertainties"]`
- `scripts/agents/execution_request_builder.py`:
```python
class ExecutionRequestBuilderError(RuntimeError):
    pass

class ExecutionRequestBuilder:
    @staticmethod
    def build_request(
        job: dict[str, Any],
        selection: OrchestratorSelection,
        context_pack: dict[str, Any],
        *,
        execution_profile: str,
        allowed_write_scope: list[str],
        task_instruction: str,
        output_schema_name: str,
        request_id: str | None = None,
        timeout_seconds: int = 300,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Constructs and validates a schema-compliant ExecutionRequest from an approved Orchestrator selection."""
        ...
```

**Dependencies:** `scripts/agents/contracts.py` (V1), `scripts/agents/orchestrator_state.py` (V1).

**Non-goals:**
- NÃO escolhe o próximo estágio (responsabilidade exclusiva do `OrchestratorStateSelector`);
- NÃO altera o Job;
- NÃO consulta provedores de IA;
- NÃO persiste dados em disco;
- NÃO cria Handoffs.

**TDD Steps:**
- [ ] **Step 1: Escrever testes unitários em `tests/agents/test_execution_contracts.py`**
  Testar:
  - Validação positiva e negativa contra `schemas/execution-request.schema.json`;
  - Validação positiva e negativa contra `schemas/execution-result.schema.json`;
  - Construção de requisição via `ExecutionRequestBuilder.build_request()` com dados de Job e Selection;
  - Rejeição caso `selection.action != "RUN_STAGE"`;
  - Rejeição caso `context_pack` não seja conforme ao schema.
- [ ] **Step 2: Executar testes para confirmar RED**
  Executar: `python -m pytest tests/agents/test_execution_contracts.py -q`  
  *Expected RED:* `ContractValidationError: Schema file not found: execution-request`.
- [ ] **Step 3: Implementar schemas e `ExecutionRequestBuilder`**
  Criar `schemas/execution-request.schema.json`, `schemas/execution-result.schema.json` e `scripts/agents/execution_request_builder.py`.
- [ ] **Step 4: Executar testes para confirmar GREEN**
  Executar: `python -m pytest tests/agents/test_execution_contracts.py -q`  
  *Expected GREEN:* todos os testes passam.
- [ ] **Step 5: Rodar gates de regressão completos**
  Executar suíte completa de agentes e scripts de validação.

**Commit Message:** `feat: define v2 execution contracts and request builder`  
**Stop Condition:** Schemas e construtor de request implementados, testados, zero regressões.

---

### Task 16 — ContextMaterializer

**Goal:** Implementar o componente determinístico responsável por receber um `ContextPack` já validado e carregar o texto UTF-8 de cada caminho utilizando o `ContextLoader` da V1.

**Files:**
- Create: `scripts/agents/context_materializer.py`
- Create: `tests/agents/test_context_materializer.py`

**Interfaces / Assinaturas:**
```python
@dataclass(frozen=True)
class MaterializedContext:
    layers: dict[str, tuple[dict[str, str], ...]]  # layer_name -> tuple of {"path": str, "content": str}
    metadata: dict[str, Any]

class ContextMaterializationError(RuntimeError):
    pass

class ContextMaterializer:
    def __init__(self, loader: ContextLoader | None = None) -> None:
        self.loader = loader or ContextLoader()

    def materialize(self, context_pack: dict[str, Any]) -> MaterializedContext:
        """Dereferences file paths from a validated Context Pack into in-memory contents."""
        ...
```

**Dependencies:** Task 15, `scripts/agents/context_loader.py` (V1), `scripts/agents/contracts.py` (V1).

**Non-goals:**
- NÃO seleciona arquivos ou diretórios;
- NÃO realiza busca ou descoberta heurística;
- NÃO chama o `ContextPackBuilder` para reconstrução;
- NÃO interpreta seções de contratos Markdown dos agentes.

**TDD Steps:**
- [ ] **Step 1: Escrever testes unitários em `tests/agents/test_context_materializer.py`**
  Testar:
  - Materialização ordenada com arquivos reais em `tmp_path`;
  - Proveniência preservada em cada camada (`mandatory`, `domain`, `bookContext`, etc.);
  - Imutabilidade do `MaterializedContext`;
  - Erro ao receber Context Pack que não valida contra schema (`validate_payload`);
  - Erro ao encontrar arquivo inexistente (`ContextMaterializationError`);
  - Proteção contra travessia de diretório delegada ao `ContextLoader`.
- [ ] **Step 2: Executar testes para confirmar RED**
  Executar: `python -m pytest tests/agents/test_context_materializer.py -q`  
  *Expected RED:* `ModuleNotFoundError: No module named 'scripts.agents.context_materializer'`.
- [ ] **Step 3: Implementar `ContextMaterializer`**
  Criar `scripts/agents/context_materializer.py` com carregamento estrito via `loader.load_text()`.
- [ ] **Step 4: Executar testes para confirmar GREEN**
  Executar: `python -m pytest tests/agents/test_context_materializer.py -q`  
  *Expected GREEN:* todos os testes passam.
- [ ] **Step 5: Rodar gates de regressão completos**

**Commit Message:** `feat: implement deterministic context materializer`  
**Stop Condition:** `ContextMaterializer` implementado, coberto por testes unitários, zero regressões.

---

### Task 17 — PromptRenderer

**Goal:** Implementar o montador determinístico de prompts que compõe o texto final entregue ao adapter a partir do `MaterializedContext` e da `ExecutionRequest`.

**Files:**
- Create: `scripts/agents/prompt_renderer.py`
- Create: `tests/agents/test_prompt_renderer.py`

**Interfaces / Assinaturas:**
```python
@dataclass(frozen=True)
class RenderedPrompt:
    system_instruction: str
    user_content: str
    metadata: dict[str, Any]

class PromptRendererError(RuntimeError):
    pass

class PromptRenderer:
    def __init__(self) -> None:
        pass

    def render(
        self,
        request: dict[str, Any],
        materialized: MaterializedContext,
        agent_contract_text: str | None = None,
    ) -> RenderedPrompt:
        """Deterministically renders layered prompt ready for model execution."""
        ...
```

**Dependencies:** Task 15, Task 16.

**Non-goals:**
- NÃO faz chamadas de rede ou invocação de LLM;
- NÃO lê caminhos arbitrários do sistema de arquivos;
- NÃO seleciona perfis ou modelos;
- NÃO persiste prompts em disco.

**TDD Steps:**
- [ ] **Step 1: Escrever testes unitários em `tests/agents/test_prompt_renderer.py`**
  Testar:
  - Composição correta de seções: Identidade do Agente, Regras Invioláveis, Contexto de Domínio, Contexto do Livro, Tarefa Específica e Write-Scope delimitado;
  - Preservação exata de delimitadores markdown;
  - Rejeição de requisição inválida sem schema;
  - Determinismo estrito (mesma entrada gera string idêntica byte a byte).
- [ ] **Step 2: Executar testes para confirmar RED**
  Executar: `python -m pytest tests/agents/test_prompt_renderer.py -q`  
  *Expected RED:* `ModuleNotFoundError: No module named 'scripts.agents.prompt_renderer'`.
- [ ] **Step 3: Implementar `PromptRenderer`**
  Criar `scripts/agents/prompt_renderer.py`.
- [ ] **Step 4: Executar testes para confirmar GREEN**
  Executar: `python -m pytest tests/agents/test_prompt_renderer.py -q`  
  *Expected GREEN:* todos os testes passam.
- [ ] **Step 5: Rodar gates de regressão completos**

**Commit Message:** `feat: implement deterministic prompt renderer`  
**Stop Condition:** `PromptRenderer` funcional, 100% determinístico e auditado por testes.

---

### Task 18 — Execution Profiles Configuration

**Goal:** Implementar o registro e a resolução desacoplada de perfis de execução provider-neutral (`executionProfile`), garantindo que modelos (ex: Gemini 3.7 High) sejam configurados externamente sem acoplar os contratos de agentes ou jobs.

**Files:**
- Create: `scripts/agents/execution_profile.py`
- Create: `tests/agents/test_execution_profile.py`

**Interfaces / Assinaturas:**
```python
@dataclass(frozen=True)
class ExecutionProfile:
    profile_id: str
    provider: str  # "fake", "antigravity", "mock"
    model: str     # "gemini-3.7-high", "gemini-2.5-flash", "test-fixture"
    timeout_seconds: int = 300
    parameters: dict[str, Any] = field(default_factory=dict)

class UnknownProfileError(KeyError):
    pass

class ProfileRegistry:
    def __init__(self, profiles: dict[str, ExecutionProfile] | None = None) -> None:
        ...

    def get_profile(self, profile_id: str) -> ExecutionProfile:
        ...

    def register(self, profile: ExecutionProfile) -> None:
        ...

    def list_profiles(self) -> list[str]:
        ...
```

**Dependencies:** Task 15.

**Non-goals:**
- NÃO hardcodeia nomes de modelos dentro de `docs/agents/*.md` ou nos esquemas de Job;
- NÃO faz chamadas a provedores externos.

**TDD Steps:**
- [ ] **Step 1: Escrever testes unitários em `tests/agents/test_execution_profile.py`**
  Testar:
  - Registro e recuperação de perfis padrão (`default-high`, `default-fast`, `offline-test`);
  - `UnknownProfileError` para perfis não registrados;
  - Imutabilidade do `ExecutionProfile`;
  - Resolução por injeção de configuração.
- [ ] **Step 2: Executar testes para confirmar RED**
  Executar: `python -m pytest tests/agents/test_execution_profile.py -q`  
  *Expected RED:* `ModuleNotFoundError: No module named 'scripts.agents.execution_profile'`.
- [ ] **Step 3: Implementar `ProfileRegistry` e perfis padrão**
  Criar `scripts/agents/execution_profile.py`.
- [ ] **Step 4: Executar testes para confirmar GREEN**
  Executar: `python -m pytest tests/agents/test_execution_profile.py -q`  
  *Expected GREEN:* todos os testes passam.
- [ ] **Step 5: Rodar gates de regressão completos**

**Commit Message:** `feat: implement execution profiles configuration`  
**Stop Condition:** Gerenciamento de perfis provider-neutral implementado e testado.

---

### Task 19 — ExecutionAdapter Interface & FakeExecutionAdapter

**Goal:** Definir a interface abstrata provider-neutral para adaptadores de execução e implementar o `FakeExecutionAdapter` para testes unitários e CI 100% offline.

**Files:**
- Create: `scripts/agents/execution_adapter.py`
- Create: `tests/agents/test_execution_adapter.py`

**Interfaces / Assinaturas:**
```python
@dataclass(frozen=True)
class RawExecutionResponse:
    content: str
    status_code: str  # "OK", "TIMEOUT", "ERROR"
    duration_seconds: float
    raw_metadata: dict[str, Any] = field(default_factory=dict)

class ExecutionAdapterError(RuntimeError):
    pass

class ExecutionAdapter(ABC):
    @abstractmethod
    def execute(
        self,
        request: dict[str, Any],
        prompt: RenderedPrompt,
        profile: ExecutionProfile,
    ) -> RawExecutionResponse:
        """Execute the prompt against the designated provider/model."""
        pass

class FakeExecutionAdapter(ExecutionAdapter):
    def __init__(
        self,
        scripted_responses: dict[str, RawExecutionResponse] | None = None,
        default_response: RawExecutionResponse | None = None,
    ) -> None:
        ...
```

**Dependencies:** Task 15, Task 17, Task 18.

**Non-goals:**
- NÃO faz chamadas reais a APIs de LLM;
- NÃO consome tokens ou chaves de API;
- NÃO grava arquivos em disco.

**TDD Steps:**
- [ ] **Step 1: Escrever testes unitários em `tests/agents/test_execution_adapter.py`**
  Testar:
  - Execução bem-sucedida retornando `RawExecutionResponse` pré-configurada;
  - Resposta padrão quando `requestId` não está mapeado;
  - Simulação de timeout (`status_code="TIMEOUT"`) e erro de serviço (`status_code="ERROR"`);
  - Conformidade com a interface abstrata `ExecutionAdapter`.
- [ ] **Step 2: Executar testes para confirmar RED**
  Executar: `python -m pytest tests/agents/test_execution_adapter.py -q`  
  *Expected RED:* `ModuleNotFoundError: No module named 'scripts.agents.execution_adapter'`.
- [ ] **Step 3: Implementar `ExecutionAdapter` e `FakeExecutionAdapter`**
  Criar `scripts/agents/execution_adapter.py`.
- [ ] **Step 4: Executar testes para confirmar GREEN**
  Executar: `python -m pytest tests/agents/test_execution_adapter.py -q`  
  *Expected GREEN:* todos os testes passam.
- [ ] **Step 5: Rodar gates de regressão completos**

**Commit Message:** `feat: implement execution adapter interface and fake adapter`  
**Stop Condition:** Interface base e FakeAdapter determinístico implementados e testados.

---

### Task 20 — Deterministic Non-Semantic Structural Repair Engine

**Goal:** Implementar o parser determinístico de respostas brutas em `ExecutionResult` com suporte a exatamente 1 tentativa de reparo mecânico/estrutural em caso de JSON malformatado, **sem jamais chamar provedores/LLMs e sem inventar conteúdo semântico**.

**Files:**
- Create: `scripts/agents/repair_engine.py`
- Create: `tests/agents/test_repair_engine.py`

**Interfaces / Assinaturas:**
```python
class RepairExhaustedError(RuntimeError):
    pass

class StructuralRepairEngine:
    def __init__(self) -> None:
        pass

    def parse_and_repair(
        self,
        raw_response: RawExecutionResponse,
        request: dict[str, Any],
    ) -> dict[str, Any]:
        """Deterministically parses raw text to ExecutionResult, applying at most 1 mechanical structural repair (no LLM, no semantic creation)."""
        ...
```

**Mecanismos Permitidos de Reparo Estrutural Determinístico:**
1. Remoção de cercas markdown (` ```json ... ``` ` ou ` ``` ... ``` `) preservando o payload interno íntegro;
2. Remoção de texto conversacional antes/depois do bloco JSON identificável;
3. Normalização determinística de quebras de linha e escape de caracteres sintáticos em strings JSON;
4. Preenchimento mecânico de metadados (`schemaVersion="1.0"`, `requestId=request["requestId"]`) caso estejam ausentes na casca externa da resposta.

**Proibições Absolutas de Reparo:**
- **NÃO chama LLM/provedor** durante o processo de reparo;
- **NUNCA inventa regras, descrições, fatos, evidências, entidades, valores ou conclusões**;
- Se a resposta não for estruturalmente recuperável, retorna status `REPAIR_FAILED` ou levanta `RepairExhaustedError`.

**Dependencies:** Task 15, Task 19.

**TDD Steps:**
- [ ] **Step 1: Escrever testes unitários em `tests/agents/test_repair_engine.py`**
  Testar:
  - Resposta com JSON puro: parse direto sem alteração;
  - Resposta envolta em cercas markdown: strip mecânico limpo e parse bem-sucedido;
  - Resposta com texto preliminar conversacional: isolamento determinístico do JSON;
  - Resposta com JSON semanticamente vazio ou corrompido: falha registrada e garantia de que nenhum dado semântico foi inventado;
  - Garantia de que zero chamadas a adapters/provedores são feitas;
  - Garantia de no máximo 1 tentativa mecânica.
- [ ] **Step 2: Executar testes para confirmar RED**
  Executar: `python -m pytest tests/agents/test_repair_engine.py -q`  
  *Expected RED:* `ModuleNotFoundError: No module named 'scripts.agents.repair_engine'`.
- [ ] **Step 3: Implementar `StructuralRepairEngine`**
  Criar `scripts/agents/repair_engine.py`.
- [ ] **Step 4: Executar testes para confirmar GREEN**
  Executar: `python -m pytest tests/agents/test_repair_engine.py -q`  
  *Expected GREEN:* todos os testes passam.
- [ ] **Step 5: Rodar gates de regressão completos**

**Commit Message:** `feat: implement deterministic structural repair engine`  
**Stop Condition:** Motor de parsing e reparo mecânico implementado sem dependência de LLMs e com proibição de invenção.

---

### Task 21 — WriteScopeValidator

**Goal:** Implementar o validador independente e fail-closed de caminhos de escrita autorizados (`allowedWriteScope`), garantindo que propostas de alteração fora do escopo sejam totalmente rejeitadas.

**Files:**
- Create: `scripts/agents/write_scope.py`
- Create: `tests/agents/test_write_scope.py`

**Interfaces / Assinaturas:**
```python
@dataclass(frozen=True)
class WriteScopeDecision:
    allowed: bool
    code: str  # "ALLOW", "ERR_WRITE_SCOPE_VIOLATION", "INVALID_PATH"
    violations: tuple[str, ...]
    reasons: tuple[str, ...]

class WriteScopeValidator:
    def __init__(self) -> None:
        pass

    def validate(
        self,
        proposed_artifacts: dict[str, str],
        allowed_patterns: list[str],
    ) -> WriteScopeDecision:
        """Strictly check if all proposed artifact paths match allowed write scope patterns."""
        ...
```

**Dependencies:** Task 15.

**Non-goals:**
- NÃO grava arquivos em disco;
- NÃO aplica mutações parciais.

**TDD Steps:**
- [ ] **Step 1: Escrever testes unitários em `tests/agents/test_write_scope.py`**
  Testar:
  - Caminho relativo autorizado por correspondência exata ou glob (ex: `data/text/trevas.txt` dentro de `data/text/*`);
  - Tentativa de path traversal (`../schemas/evil.json`);
  - Caminho absoluto Unix (`/etc/passwd`) e Windows (`C:\Windows\System32`);
  - Caminho de outro estágio (ex: estágio `extraction` tentando alterar `data/entities/magias.json`);
  - Proposta com múltiplos arquivos onde 1 é inválido -> proposta inteira rejeitada (`allowed=False`, `violations=(...)`);
  - Confinamento estrito de caminhos.
- [ ] **Step 2: Executar testes para confirmar RED**
  Executar: `python -m pytest tests/agents/test_write_scope.py -q`  
  *Expected RED:* `ModuleNotFoundError: No module named 'scripts.agents.write_scope'`.
- [ ] **Step 3: Implementar `WriteScopeValidator`**
  Criar `scripts/agents/write_scope.py`.
- [ ] **Step 4: Executar testes para confirmar GREEN**
  Executar: `python -m pytest tests/agents/test_write_scope.py -q`  
  *Expected GREEN:* todos os testes passam.
- [ ] **Step 5: Rodar gates de regressão completos**

**Commit Message:** `feat: implement fail-closed write scope validator`  
**Stop Condition:** Validador de escopo de escrita implementado com rejeição atômica e fail-closed.

---

### Task 22 — ExecutionResultValidator

**Goal:** Implementar o validador agregado de resultados de execução que inspeciona Schemas, Escopo de Escrita, Evidências de Proveniência, Registro de Incertezas e Políticas de Governança.

**Files:**
- Create: `scripts/agents/execution_validator.py`
- Create: `tests/agents/test_execution_validator.py`

**Interfaces / Assinaturas:**
```python
@dataclass(frozen=True)
class ExecutionValidationVerdict:
    verdict: str  # "ACCEPT", "HUMAN_REVIEW", "BLOCKED"
    code: str
    reasons: tuple[str, ...]
    details: dict[str, Any] = field(default_factory=dict)

class ExecutionResultValidator:
    def __init__(
        self,
        write_scope_validator: WriteScopeValidator | None = None,
        gate_engine: GateEngine | None = None,
    ) -> None:
        self.write_scope_validator = write_scope_validator or WriteScopeValidator()
        self.gate_engine = gate_engine or GateEngine()

    def validate(
        self,
        result: dict[str, Any],
        request: dict[str, Any],
    ) -> ExecutionValidationVerdict:
        """Perform comprehensive deterministic audit on an ExecutionResult before persistence."""
        ...
```

**Dependencies:** Task 15, Task 21, `scripts/agents/gate_engine.py` (V1).

**Non-goals:**
- NÃO persiste arquivos em disco;
- NÃO atualiza o `JobStore` diretamente.

**TDD Steps:**
- [ ] **Step 1: Escrever testes unitários em `tests/agents/test_execution_validator.py`**
  Testar:
  - Resultado válido com evidências e escopo correto -> `verdict="ACCEPT", code="ALLOW"`;
  - Violação de write-scope -> `verdict="BLOCKED", code="ERR_WRITE_SCOPE_VIOLATION"`;
  - Falha de schema no artefato de saída -> `verdict="HUMAN_REVIEW", code="ERR_SCHEMA_VALIDATION"`;
  - Ausência de evidências obrigatórias (`bookId`, `page`) em extração/editorial -> `verdict="HUMAN_REVIEW", code="ERR_EVIDENCE_MISSING"`;
  - Presença de incertezas listadas -> `verdict="HUMAN_REVIEW", code="ERR_SEMANTIC_UNCERTAINTY"`;
  - Status de erro do adapter (`TIMEOUT`, `ERROR`) -> `verdict="BLOCKED"`.
- [ ] **Step 2: Executar testes para confirmar RED**
  Executar: `python -m pytest tests/agents/test_execution_validator.py -q`  
  *Expected RED:* `ModuleNotFoundError: No module named 'scripts.agents.execution_validator'`.
- [ ] **Step 3: Implementar `ExecutionResultValidator`**
  Criar `scripts/agents/execution_validator.py`.
- [ ] **Step 4: Executar testes para confirmar GREEN**
  Executar: `python -m pytest tests/agents/test_execution_validator.py -q`  
  *Expected GREEN:* todos os testes passam.
- [ ] **Step 5: Rodar gates de regressão completos**

**Commit Message:** `feat: implement aggregated execution result validator`  
**Stop Condition:** Validador de resultados agregado implementado e alinhado com a taxonomia de falhas.

---

### Task 23 — In-Memory Execution Coordinator & V2 End-to-End Fixture

**Goal:** Implementar o `ExecutionCoordinator` responsável por encadear determinística e exclusivamente em memória os componentes da V2 (`Selection -> ExecutionRequestBuilder -> ContextMaterializer -> PromptRenderer -> FakeExecutionAdapter -> StructuralRepairEngine -> ExecutionResultValidator`), gerando propostas validadas de Handoff sem mutação direta de repositório ou JobStore.

**Files:**
- Create: `scripts/agents/execution_coordinator.py`
- Create: `tests/agents/test_execution_coordinator_e2e.py`

**Interfaces / Assinaturas:**
```python
@dataclass(frozen=True)
class ExecutionCoordinationResult:
    request: dict[str, Any]
    raw_response: RawExecutionResponse
    result: dict[str, Any]
    verdict: ExecutionValidationVerdict
    proposed_handoff: dict[str, Any] | None = None

class ExecutionCoordinator:
    def __init__(
        self,
        adapter: ExecutionAdapter,
        materializer: ContextMaterializer | None = None,
        renderer: PromptRenderer | None = None,
        repair_engine: StructuralRepairEngine | None = None,
        validator: ExecutionResultValidator | None = None,
    ) -> None:
        ...

    def coordinate_execution(
        self,
        request: dict[str, Any],
        profile: ExecutionProfile,
    ) -> ExecutionCoordinationResult:
        """Coordinates the in-memory execution cycle without mutating repository or Job state."""
        ...
```

**Dependencies:** Tasks 15 a 22.

**Non-goals:**
- **NÃO** substitui nem amplia a autoridade do `OrchestratorStateSelector`;
- **NÃO** executa transições de estado no `JobStore`;
- **NÃO** grava artefatos no repositório;
- **NÃO** chama `HandoffStore.create()` automaticamente como efeito colateral oculto;
- **NÃO** executa retries ou loops não supervisionados.

**TDD Steps:**
- [ ] **Step 1: Escrever testes de integração em `tests/agents/test_execution_coordinator_e2e.py`**
  Testar:
  - Fluxo completo em memória com `FakeExecutionAdapter` gerando resultado válido e proposta de Handoff com `verdict="ACCEPT"`;
  - Fluxo com reparo mecânico bem-sucedido na 1ª tentativa;
  - Fluxo com violação de write-scope resultando em `verdict="BLOCKED"` e `proposed_handoff=None`;
  - Fluxo com incertezas resultando em `verdict="HUMAN_REVIEW"`;
  - Confirmação de que nenhum arquivo em disco foi modificado durante toda a execução.
- [ ] **Step 2: Executar testes para confirmar RED**
  Executar: `python -m pytest tests/agents/test_execution_coordinator_e2e.py -q`  
  *Expected RED:* `ModuleNotFoundError: No module named 'scripts.agents.execution_coordinator'`.
- [ ] **Step 3: Implementar `ExecutionCoordinator`**
  Criar `scripts/agents/execution_coordinator.py`.
- [ ] **Step 4: Executar testes para confirmar GREEN**
  Executar: `python -m pytest tests/agents/test_execution_coordinator_e2e.py -q`  
  *Expected GREEN:* todos os testes passam.
- [ ] **Step 5: Rodar gates de regressão completos**

**Commit Message:** `feat: implement in-memory execution coordinator and e2e integration fixture`  
**Stop Condition:** Coordenador de execução em memória implementado e coberto por testes E2E offline.

---

### Task 24 — Antigravity Adapter Integration Boundary Audit (Conditional)

**Goal:** Auditar rigorosamente a superfície programática real do runtime Antigravity. Se e somente se houver uma interface oficial programática suportada, implementar o `AntigravityExecutionAdapter`; caso contrário, documentar formalmente o status `DEFERRED_PENDING_RUNTIME_API`, preservando a V2 totalmente funcional e testável via `ExecutionAdapter` protocol + `FakeExecutionAdapter`.

**Files (Condicionais):**
- Conditional Create: `scripts/agents/antigravity_adapter.py`
- Conditional Create: `tests/agents/test_antigravity_adapter.py`

**Regras Invioláveis de Auditoria:**
1. **Auditoria Prévia Obrigatória**: Verificar se existe SDK, CLI ou API programática exposta no ambiente.
2. **Se NÃO existir API programática suportada**:
   - Registrar o resultado como `DEFERRED_PENDING_RUNTIME_API`;
   - **NÃO criar classes com `NotImplementedError`** apenas para preencher arquivo;
   - **NÃO criar testes fakes ou mocks vazios**;
   - **NÃO utilizar automação de browser (Selenium, Puppeteer, Playwright)**;
   - **NÃO utilizar automação de interface gráfica (GUI / PyAutoGUI)**;
   - **NÃO fingir que existe API**.
3. **Se existir API programática real**:
   - Implementar `AntigravityExecutionAdapter(ExecutionAdapter)` isolando chamadas de rede;
   - Criar testes específicos separados que rodam apenas em ambiente com credenciais ativas, sem nunca impactar o CI normal offline.

**TDD Steps (Condicionais):**
- [ ] **Step 1: Executar script de auditoria de runtime no ambiente local**
- [ ] **Step 2: Se API disponível -> Escrever testes em `tests/agents/test_antigravity_adapter.py`**
- [ ] **Step 3: Implementar `AntigravityExecutionAdapter` em `scripts/agents/antigravity_adapter.py`**
- [ ] **Step 4: Se API não disponível -> Registrar relatório de deferimento arquitetural sem criar arquivos fantasmas**
- [ ] **Step 5: Rodar gates de regressão completos**

**Commit Message:** `feat: establish antigravity execution adapter integration boundary`  
**Stop Condition:** Auditoria concluída, adapter implementado ou formalmente diferido, zero impacto no CI offline.

---

## 4. Estratégia de CI e Integração Contínua

O workflow existente [`.github/workflows/validate.yml`](file:///c:/Users/TI%20Prevent/Documents/Painel%20de%20Impressoras/Daemon%20Tools/.github/workflows/validate.yml) executará automaticamente:
1. `Agent tests`: `python -m pytest tests/agents -q` (cobrirá todos os testes unitários e E2E da V1 e V2 com `FakeExecutionAdapter`).
2. `Full test suite`: `python -m pytest -q`.
3. `Validate data`: `python scripts/validate_data.py`.
4. `Check book coverage`: `python scripts/check_book_coverage.py`.
5. `Check frontend syntax`: `node --check docs/assets/app.js`.

**Garantia**: O CI permanece 100% determinístico, offline, sem tokens e executando em segundos.

---

## 5. Self-Review de Conformidade do Plano

1. **Spec Coverage**: Todas as seções da especificação (`2026-09-08-antigravity-execution-adapter-v2-design.md`) foram mapeadas nas Tarefas 15 a 24.
2. **Placeholder Scan**: Não há `TODO`, `TBD`, "similar to previous task" ou etapas sem detalhamento.
3. **Type & Signature Consistency**: Assinaturas das dataclasses e métodos seguem tipos estritos do Python 3.12 (`dict[str, Any]`, `tuple[str, ...]`, `dataclass(frozen=True)`).
4. **Dependency-Order Validation**:
   $$\text{Task 15 (Contracts \& Builder)} \rightarrow \text{Task 16 (Materializer)} \rightarrow \text{Task 17 (Renderer)} \rightarrow \text{Task 18 (Profiles)} \rightarrow \text{Task 19 (Adapter)} \rightarrow \text{Task 20 (Repair)} \rightarrow \text{Task 21 (Scope)} \rightarrow \text{Task 22 (Validator)} \rightarrow \text{Task 23 (Coordinator)} \rightarrow \text{Task 24 (Antigravity Audit)}$$
5. **Provider-Neutrality**: `executionProfile` isola provedores; nenhum modelo é hardcodeado nos agentes.
6. **Write-Authority Bypass Scan**: `LLM output MUST NOT directly mutate the repository` garantido pela separação entre `proposedArtifacts` e validação. O `ExecutionCoordinator` opera estritamente em memória.
7. **Test Isolation**: Todos os testes normais usam mocks ou `FakeExecutionAdapter` sem rede.
