# Antigravity Execution Adapter V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Construir a camada provider-neutral de execução controlada da V2 sem conceder autoridade direta de escrita ao LLM.

**Architecture:** A decisão permanece no OrchestratorStateSelector. A execução é separada em contratos, materialização de contexto, renderização de prompt, adapter de execução e validação determinística do resultado antes de qualquer persistência.

**Tech Stack:** Python 3.12, JSON Schema Draft 2020-12, jsonschema, pytest, Git/GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-08-antigravity-execution-adapter-v2-design.md`

---

## 1. Global Constraints & Architectural Rules

1. **Compatibilidade com a V1**: Todos os componentes da V1 (`JobStore`, `HandoffStore`, `ContextLoader`, `ContextPackBuilder`, `GateEngine`, `OrchestratorStateSelector` e suite completa de testes) permanecem 100% funcionais e inalterados em suas garantias essenciais.
2. **LLM Output is Untrusted Input**: Nenhuma resposta de modelo de linguagem tem autoridade direta de escrita sobre o repositório (`LLM output MUST NOT directly mutate the repository`).
3. **Sem Autoridade de Persistência no Adapter**: `ExecutionAdapter`, `PromptRenderer` e o modelo de IA retornam apenas propostas estruturadas de alteração (`proposedArtifacts`) dentro do `Execution Result`.
4. **Persistência Exclusivamente Pós-Validação**: Alterações só podem ser aplicadas em disco por uma camada autorizada após aprovação determinística pelo `ExecutionResultValidator`.
5. **Neutralidade de Provedor e Modelos**: `ExecutionRequest` e `ExecutionResult` são totalmente provider-neutral. A resolução de provedores e modelos (ex: Gemini 3.7 High, Gemini 2.5 Flash, Mock) é tratada externamente via `executionProfile`.
6. **Política Estrita de Reparo Estrutural**: É permitida exatamente 1 (uma) tentativa de reparo estrutural/sintático. O reparo **nunca** pode inventar conteúdo semântico, regras, fatos ou atributos.
7. **Write-Scope Fail-Closed**: Violações de escopo de escrita (`allowedWriteScope`) rejeitam toda a proposta atômica em memória. Nenhuma escrita parcial é permitida.
8. **Testes 100% Offline e Determinísticos**: A suíte de testes padrão e o CI do GitHub Actions utilizam exclusivamente o `FakeExecutionAdapter`, sem necessidade de tokens, chaves de API ou chamadas de rede.
9. **Nenhuma Dependência Runtime Obrigatória de Gemini**: A arquitetura da V2 não acopla identidades lógicas de agentes a nenhum provedor proprietário.
10. **Upstream Intocado**: Todas as alterações são confinadas ao fork de desenvolvimento (`SaruAkaza/daemon`); `guraassessoria/daemon` permanece intacto.

---

## 2. Mapa Geral de Arquivos da V2

| Arquivo | Ação | Responsabilidade |
| :--- | :--- | :--- |
| `schemas/execution-request.schema.json` | Criar | Schema Draft 2020-12 para ordens de trabalho de execução |
| `schemas/execution-result.schema.json` | Criar | Schema Draft 2020-12 para respostas de execução com propostas |
| `scripts/agents/context_materializer.py` | Criar | Materialização em memória de `ContextPack` validado via `ContextLoader` |
| `scripts/agents/prompt_renderer.py` | Criar | Montagem determinística de prompts por camadas a partir do contexto materializado |
| `scripts/agents/execution_profile.py` | Criar | Resolução e registro de perfis de execução provider-neutral (`executionProfile`) |
| `scripts/agents/execution_adapter.py` | Criar | Protocolo `ExecutionAdapter` e implementação `FakeExecutionAdapter` |
| `scripts/agents/repair_engine.py` | Criar | Parser de resposta bruta e motor de reparo sintático (max 1 tentativa) |
| `scripts/agents/write_scope.py` | Criar | Validador fail-closed de caminhos de escrita autorizados (`allowedWriteScope`) |
| `scripts/agents/execution_validator.py` | Criar | Validador agregado de resultados (Schema, Escopo, Evidências, Políticas) |
| `scripts/agents/orchestration_runner_v2.py` | Criar | Executor integrado da V2 conectando Orchestrator, Adapter, Validador e Stores |
| `scripts/agents/antigravity_adapter.py` | Criar | Fronteira de integração programática com o runtime Antigravity |
| `tests/agents/test_execution_contracts.py` | Criar | Testes dos schemas `execution-request` e `execution-result` |
| `tests/agents/test_context_materializer.py` | Criar | Testes unitários do `ContextMaterializer` |
| `tests/agents/test_prompt_renderer.py` | Criar | Testes unitários do `PromptRenderer` |
| `tests/agents/test_execution_profile.py` | Criar | Testes de resolução de perfis de execução |
| `tests/agents/test_execution_adapter.py` | Criar | Testes do protocolo adapter e `FakeExecutionAdapter` |
| `tests/agents/test_repair_engine.py` | Criar | Testes de parsing e política de reparo estrutural único |
| `tests/agents/test_write_scope.py` | Criar | Testes de validação de escopo de escrita (traversal, absolute, glob) |
| `tests/agents/test_execution_validator.py` | Criar | Testes agregados de validação e códigos de erro da taxonomia |
| `tests/agents/test_orchestration_v2_e2e.py` | Criar | Teste de integração end-to-end do pipeline V2 |
| `tests/agents/test_antigravity_adapter.py` | Criar | Testes da fronteira de integração com Antigravity |

---

## 3. Sequência Detalhada de Implementação (Tarefas 15 a 24)

---

### Task 15 — Execution Contracts (Schemas & Fixtures)

**Goal:** Definir os contratos formais JSON Schema Draft 2020-12 para `ExecutionRequest` e `ExecutionResult`, garantindo validação tipada através de `scripts/agents/contracts.py`.

**Files:**
- Create: `schemas/execution-request.schema.json`
- Create: `schemas/execution-result.schema.json`
- Create: `tests/agents/test_execution_contracts.py`

**Interfaces / Schemas:**
- `schemas/execution-request.schema.json`:
  - `required`: `["schemaVersion", "requestId", "jobId", "bookId", "targetStage", "assignedAgent", "allowedWriteScope", "executionProfile", "contextPack", "taskInstruction", "outputSchemaName"]`
  - `properties`:
    - `schemaVersion`: string (`"1.0"`)
    - `requestId`: string (`^REQ-[A-Z0-9_-]+$`)
    - `jobId`: string (`minLength: 1`)
    - `bookId`: string (`minLength: 1`)
    - `targetStage`: enum (`["source", "extraction", "editorial", "entities", "relations", "frontend", "qa", "release"]`)
    - `assignedAgent`: enum (`["source-agent", "extraction-agent", "editorial-agent", "entity-agent", "relations-agent", "frontend-agent", "qa-release-agent"]`)
    - `allowedWriteScope`: array de strings relativas
    - `executionProfile`: string (`minLength: 1`)
    - `contextPack`: object validado contra `context-pack.schema.json`
    - `taskInstruction`: string (`minLength: 1`)
    - `outputSchemaName`: string (`minLength: 1`)
    - `timeoutSeconds`: integer (`minimum: 1`, default: 300)
    - `metadata`: object (`additionalProperties: true`)
- `schemas/execution-result.schema.json`:
  - `required`: `["schemaVersion", "executionId", "requestId", "agent", "stage", "status", "proposedArtifacts", "evidence", "uncertainties"]`
  - `properties`:
    - `schemaVersion`: string (`"1.0"`)
    - `executionId`: string (`^EXEC-[A-Z0-9_-]+$`)
    - `requestId`: string (`minLength: 1`)
    - `agent`: string (`minLength: 1`)
    - `stage`: enum (`["source", "extraction", "editorial", "entities", "relations", "frontend", "qa", "release"]`)
    - `status`: enum (`["SUCCESS", "VALIDATION_FAILED", "REPAIR_FAILED", "TIMEOUT", "ERROR"]`)
    - `proposedArtifacts`: object de chave=caminho_relativo, valor=conteudo_string
    - `evidence`: array de objetos `{"bookId": string, "page": integer, "section": string, "quote": string}`
    - `uncertainties`: array de strings
    - `rawResponse`: string opcional
    - `metadata`: object opcional

**Dependencies:** `scripts/agents/contracts.py` (V1).

**Non-goals:** Não criar classes Python de parsing nem invocar adapters nesta task.

**TDD Steps:**
- [ ] **Step 1: Escrever testes unitários com fixtures positivas e negativas**
  Criar `tests/agents/test_execution_contracts.py` testando `validate_payload("execution-request", payload)` e `validate_payload("execution-result", payload)`.
- [ ] **Step 2: Executar testes para confirmar RED**
  Executar: `python -m pytest tests/agents/test_execution_contracts.py -q`  
  *Expected RED:* `ContractValidationError: Schema file not found: execution-request`.
- [ ] **Step 3: Implementar os esquemas JSON**
  Criar `schemas/execution-request.schema.json` e `schemas/execution-result.schema.json`.
- [ ] **Step 4: Executar testes para confirmar GREEN**
  Executar: `python -m pytest tests/agents/test_execution_contracts.py -q`  
  *Expected GREEN:* todos os testes passam.
- [ ] **Step 5: Rodar gates de regressão completos**
  Executar suíte completa de agentes e scripts de validação.

**Commit Message:** `feat: define v2 execution request and result schemas`  
**Stop Condition:** Schemas criados, testes de contrato passando, zero regressões.

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

### Task 20 — Structural Result Parsing & Repair Engine

**Goal:** Implementar o parser de respostas brutas em `ExecutionResult` com suporte a exatamente 1 tentativa de reparo estrutural em caso de JSON inválido ou malformado.

**Files:**
- Create: `scripts/agents/repair_engine.py`
- Create: `tests/agents/test_repair_engine.py`

**Interfaces / Assinaturas:**
```python
class RepairExhaustedError(RuntimeError):
    pass

class StructuralRepairEngine:
    def __init__(self, adapter: ExecutionAdapter | None = None) -> None:
        self.adapter = adapter

    def parse_and_repair(
        self,
        raw_response: RawExecutionResponse,
        request: dict[str, Any],
        prompt: RenderedPrompt,
        profile: ExecutionProfile,
    ) -> dict[str, Any]:
        """Parses raw text to ExecutionResult dict, attempting exactly 1 structural repair if malformed."""
        ...
```

**Dependencies:** Task 15, Task 17, Task 18, Task 19.

**Non-goals:**
- O reparo **NUNCA** inventa regras, atributos, entidades ou fatos semânticos;
- **NUNCA** permite mais de uma tentativa de reparo (se falhar, emite `status="REPAIR_FAILED"` ou levanta `RepairExhaustedError`).

**TDD Steps:**
- [ ] **Step 1: Escrever testes unitários em `tests/agents/test_repair_engine.py`**
  Testar:
  - Resposta com JSON válido: parse imediato sem chamada de reparo;
  - Resposta com markdown/JSON malformado (ex: aspas não fechadas): aciona 1ª tentativa de reparo com sucesso -> resultado parseado;
  - Resposta com JSON malformado onde o reparo também falha: falha registrada e garantia de que uma 2ª tentativa NÃO ocorre;
  - Extração limpa de blocos ```json ... ```;
  - Validação estrita de que o resultado gerado valida contra `execution-result.schema.json`.
- [ ] **Step 2: Executar testes para confirmar RED**
  Executar: `python -m pytest tests/agents/test_repair_engine.py -q`  
  *Expected RED:* `ModuleNotFoundError: No module named 'scripts.agents.repair_engine'`.
- [ ] **Step 3: Implementar `StructuralRepairEngine`**
  Criar `scripts/agents/repair_engine.py`.
- [ ] **Step 4: Executar testes para confirmar GREEN**
  Executar: `python -m pytest tests/agents/test_repair_engine.py -q`  
  *Expected GREEN:* todos os testes passam.
- [ ] **Step 5: Rodar gates de regressão completos**

**Commit Message:** `feat: implement structural result parsing and single-attempt repair engine`  
**Stop Condition:** Motor de parsing e reparo estrutural único implementado com garantias anti-invenção.

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

### Task 23 — Handoff Preparation & V2 End-to-End Orchestration Runner

**Goal:** Integrar todos os componentes da V2 em um executor de passos determinístico e criar a suite de testes ponta a ponta (E2E) simulando ciclos completos de execução com `FakeExecutionAdapter`.

**Files:**
- Create: `scripts/agents/orchestration_runner_v2.py`
- Create: `tests/agents/test_orchestration_v2_e2e.py`

**Interfaces / Assinaturas:**
```python
@dataclass(frozen=True)
class OrchestrationStepResult:
    action: str  # "STEP_COMPLETED", "HUMAN_REVIEW_REQUIRED", "BLOCKED", "NO_ACTION"
    job_id: str
    stage: str | None
    verdict: str | None
    handoff_id: str | None
    reasons: tuple[str, ...]

class OrchestrationRunnerV2:
    def __init__(
        self,
        job_store: JobStore,
        handoff_store: HandoffStore,
        adapter: ExecutionAdapter,
        profile_registry: ProfileRegistry | None = None,
        materializer: ContextMaterializer | None = None,
        renderer: PromptRenderer | None = None,
        repair_engine: StructuralRepairEngine | None = None,
        validator: ExecutionResultValidator | None = None,
        state_selector: OrchestratorStateSelector | None = None,
    ) -> None:
        ...

    def run_stage_step(
        self,
        job_id: str,
        *,
        human_validated: bool = False,
        source_manifest: dict[str, Any] | None = None,
    ) -> OrchestrationStepResult:
        """Executes a full cycle: state check -> request -> materialize -> prompt -> adapter -> validate -> persist/handoff."""
        ...
```

**Dependencies:** Tasks 15 a 22, `scripts/agents/job_store.py`, `scripts/agents/handoff_store.py`, `scripts/agents/orchestrator_state.py`.

**Non-goals:**
- NÃO faz chamadas reais a APIs de modelos;
- NÃO implementa loops infinitos sem controle de parada.

**TDD Steps:**
- [ ] **Step 1: Escrever testes E2E em `tests/agents/test_orchestration_v2_e2e.py`**
  Testar:
  - Fluxo feliz: `Job` em estágio `extraction` -> `RUN_STAGE` -> executa com `FakeExecutionAdapter` -> valida -> cria `Agent Handoff` no `HandoffStore` -> atualiza `JobStore` para estágio passado;
  - Fluxo de erro estrutural com reparo bem-sucedido na 1ª tentativa;
  - Fluxo com violação de write-scope: bloqueado, nenhum arquivo escrito, nenhum handoff criado;
  - Fluxo com incerteza semântica: transiciona para `human_review`, cria `ReviewRequest` e para;
  - Fluxo final de conclusão `done`: requer `human_validated=True`.
- [ ] **Step 2: Executar testes para confirmar RED**
  Executar: `python -m pytest tests/agents/test_orchestration_v2_e2e.py -q`  
  *Expected RED:* `ModuleNotFoundError: No module named 'scripts.agents.orchestration_runner_v2'`.
- [ ] **Step 3: Implementar `OrchestrationRunnerV2`**
  Criar `scripts/agents/orchestration_runner_v2.py`.
- [ ] **Step 4: Executar testes para confirmar GREEN**
  Executar: `python -m pytest tests/agents/test_orchestration_v2_e2e.py -q`  
  *Expected GREEN:* todos os testes passam.
- [ ] **Step 5: Rodar gates de regressão completos**

**Commit Message:** `test: add v2 end-to-end orchestration runner and integration fixture`  
**Stop Condition:** Ciclo E2E completo da V2 funcionando deterministamente em testes offline.

---

### Task 24 — Antigravity Adapter Integration Boundary Audit & Specification

**Goal:** Auditar a superfície real de integração do runtime Antigravity no ambiente de execução. Se houver uma interface programática officially supported, implementar o wrapper `AntigravityExecutionAdapter`; caso contrário, documentar formalmente o status `DEFERRED_PENDING_RUNTIME_API` mantendo a arquitetura 100% funcional com `FakeExecutionAdapter`.

**Files:**
- Create: `scripts/agents/antigravity_adapter.py`
- Create: `tests/agents/test_antigravity_adapter.py`

**Interfaces / Assinaturas:**
```python
class AntigravityExecutionAdapter(ExecutionAdapter):
    def __init__(self, client: Any = None) -> None:
        self.client = client

    def execute(
        self,
        request: dict[str, Any],
        prompt: RenderedPrompt,
        profile: ExecutionProfile,
    ) -> RawExecutionResponse:
        """Executes prompt via Antigravity runtime if available, or returns controlled runtime status."""
        ...
```

**Regras de Integração:**
1. **NÃO inventar SDK, CLI ou API não existente**.
2. **NÃO utilizar automação de browser (Puppeteer/Playwright)** para simular API.
3. **NÃO utilizar automação de interface gráfica (GUI)**.
4. Testes do CI normal do GitHub Actions **NUNCA** dependem de credenciais Antigravity ou chamadas externas de rede.

**TDD Steps:**
- [ ] **Step 1: Escrever testes unitários em `tests/agents/test_antigravity_adapter.py`**
  Testar:
  - Inicialização e conformidade com o protocolo `ExecutionAdapter`;
  - Tratamento de ausência de credenciais/runtime retornando status controlado sem falhar o processo;
  - Encapsulamento de resposta em `RawExecutionResponse`.
- [ ] **Step 2: Executar testes para confirmar RED**
  Executar: `python -m pytest tests/agents/test_antigravity_adapter.py -q`  
  *Expected RED:* `ModuleNotFoundError: No module named 'scripts.agents.antigravity_adapter'`.
- [ ] **Step 3: Implementar `AntigravityExecutionAdapter`**
  Criar `scripts/agents/antigravity_adapter.py`.
- [ ] **Step 4: Executar testes para confirmar GREEN**
  Executar: `python -m pytest tests/agents/test_antigravity_adapter.py -q`  
  *Expected GREEN:* todos os testes passam.
- [ ] **Step 5: Rodar gates de regressão completos**

**Commit Message:** `feat: establish antigravity execution adapter integration boundary`  
**Stop Condition:** Fronteira com Antigravity implementada com isolamento estrito e sem quebrar o CI offline.

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
4. **Dependency-Order Validation**: Nenhuma tarefa depende de classes ou schemas criados em tarefas posteriores.
5. **Provider-Neutrality**: `executionProfile` isola provedores; nenhum modelo é hardcodeado nos agentes.
6. **Write-Authority Bypass Scan**: `LLM output MUST NOT directly mutate the repository` garantido pela separação entre `proposedArtifacts` e validação.
7. **Test Isolation**: Todos os testes normais usam mocks ou `FakeExecutionAdapter` sem rede.
