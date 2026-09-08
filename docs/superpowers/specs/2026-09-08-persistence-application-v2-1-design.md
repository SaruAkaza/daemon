# Daemon Tools — Version 2.1 Design Specification
# Persistence & Application Layer (Safe Filesystem Mutation)

- **Status**: Draft / Aprovado para Implementação
- **Data**: 2026-09-08
- **Base Arquitetural**: Version 2 (`multiagent-execution-v2` — `27fe8704bf39868b0323adbc69aed3483f88a56d`)
- **Documentos Canônicos Relacionados**:
  - `docs/superpowers/specs/2026-09-08-antigravity-execution-adapter-v2-design.md` (V2 Architecture)
  - `docs/architecture/constitution.md` (Princípios Invioláveis)
  - `docs/architecture/pipeline.md` (Fases do Pipeline)
  - `docs/architecture/decision-policy.md` (Políticas de Decisão)

---

## 1. Contexto e Propósito

A **Version 2** consolidou a execução de agentes especialistas como um processo provider-neutral, auditável e estritamente em memória. Na V2, o `ExecutionCoordinator` encadeia a solicitação até a validação rigorosa pelo `ExecutionResultValidator`, que emite um veredito (`ACCEPT`, `HUMAN_REVIEW`, `BLOCKED`).

A **Version 2.1 (Persistence / Application Layer)** define a fronteira segura, determinística e transacional que traduz um resultado de execução aceito (`verdict == "ACCEPT"`) em mutações reais e atômicas no sistema de arquivos do repositório.

### Cláusulas Pétreas de Segurança da V2.1:
1. **LLM output never has direct filesystem write authority.** (A saída de modelos de linguagem é sempre tratada como proposta não confiável em memória).
2. **`ACCEPT` authorizes validation for application; it does not bypass application policy.** (O veredito de aceitação do validador de execução qualifica a proposta para avaliação de aplicação, mas não autoriza escrita cega).
3. **Every filesystem mutation must pass deterministic preconditions immediately before mutation.** (Verificação fail-closed de concorrência otimista via SHA256 base e integridade de caminho).
4. **No partial ChangeSet application is allowed.** (Aplicação atômica all-or-nothing com transações estagiadas e rollback compensatório).
5. **Destructive operations (DELETE, RENAME, MOVE) are strictly forbidden in V2.1.** (Apenas criação de novos arquivos e atualização de arquivos existentes são autorizadas).

---

## 2. Escopo: Goals e Non-Goals

### 2.1 Goals (Metas da V2.1)
- **ChangeSet Formal**: Definir modelo estruturado e tipado de `ChangeSet` e `ChangeOperation`.
- **ChangeSetBuilder Determinístico**: Transformar `ExecutionResult` aceito em manifesto de alterações determinístico.
- **ApplicationPolicy & Protected Paths**: Avaliar políticas de governança e proteger caminhos sensíveis do sistema (código, schemas, workflows de CI, arquitetura) exigindo revisão humana.
- **PreconditionValidator (Optimistic Concurrency)**: Validar existência, ausência e hash SHA256 do arquivo base antes de qualquer gravação física.
- **PatchApplier em Memória**: Gerar conteúdo candidato sem alterar arquivos vivos.
- **Staging & Aplicação Atômica**: Criar diretório isolado de staging e aplicar alterações via substituição atômica unitária com rollback compensatório em caso de falha.
- **ApplicationResult Auditável**: Registrar o resultado detalhado da aplicação com hashes resultantes e diagnósticos.

### 2.2 Non-Goals (Fora do Escopo da V2.1)
- **NÃO** suporta operações destrutivas (`DELETE`, `RENAME`, `MOVE`).
- **NÃO** executa commits git automáticos, push remoto ou abertura de Pull Requests.
- **NÃO** implementa concorrência distribuída ou múltiplos escritores concorrentes (assume escritor único controlado).
- **NÃO** faz chamadas a provedores ou LLMs para "resolver conflitos" ou "recuperar falhas".
- **NÃO** substitui arquivos silenciosamente sem verificação de hash base (`expectedBaseSha256`).
- **NÃO** aplica mutações parciais (se 1 arquivo de um ChangeSet de 5 falhar, 0 arquivos são alterados).

---

## 3. Arquitetura e Fluxo End-to-End da V2.1

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                   V2 Pipeline (In-Memory)                               │
│  OrchestratorSelection → ExecutionRequestBuilder → ContextMaterializer → PromptRenderer  │
│                     → ExecutionAdapter → RepairEngine → ExecutionResultValidator       │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │ (Verdict: ACCEPT)
                                            ▼
                           ┌─────────────────────────────────┐
                           │        ChangeSetBuilder         │
                           │  (Mapeia proposta em ChangeSet) │
                           └────────────────┬────────────────┘
                                            │
                                            ▼
                           ┌─────────────────────────────────┐
                           │        ApplicationPolicy        │
                           │ (Verifica protected paths/scope)│
                           └───────┬─────────────────┬───────┘
                     (ALLOW)       │                 │ (PROTECTED_PATH / UNCERTAIN)
                                   ▼                 ▼
                    ┌─────────────────────────┐ ┌───────────────────────────┐
                    │   PreconditionValidator │ │   HUMAN_REVIEW Escalation │
                    │(Verifica SHA base atual)│ └───────────────────────────┘
                    └──────────────┬──────────┘
                         (PASS)    │
                                   ▼
                    ┌─────────────────────────┐
                    │      PatchApplier       │
                    │ (Constrói candidatos)   │
                    └──────────────┬──────────┘
                                   │
                                   ▼
                    ┌─────────────────────────┐
                    │  Staging (Temp Dir)     │
                    │ (Grava em isolamento)   │
                    └──────────────┬──────────┘
                                   │
                                   ▼
                    ┌─────────────────────────┐
                    │ Atomic Filesystem Apply │
                    │ (Swap atômico + journal)│
                    └──────────────┬──────────┘
                                   │
                                   ▼
                    ┌─────────────────────────┐
                    │    ApplicationResult    │
                    │  (SUCCESS / ROLLED_BACK)│
                    └─────────────────────────┘
```

---

## 4. Detalhamento dos Componentes

### 4.1 Modelo de `ChangeSet` e `ChangeOperation`

Um `ChangeSet` é uma estrutura de dados imutável que formaliza exatamente quais mutações físicas devem ser realizadas:

```python
@dataclass(frozen=True)
class ChangeOperation:
    operation_id: str             # Ex: "OP-001"
    type: str                     # "CREATE" ou "UPDATE"
    target_path: str              # Caminho relativo POSIX normalizado (ex: "data/text/trevas-3-0.txt")
    expected_base_sha256: str | None  # None para CREATE; SHA256 hex de 64 caracteres para UPDATE
    candidate_content: str        # Conteúdo de texto UTF-8 a ser gravado
    encoding: str = "utf-8"
    format: str = "text"          # "text" ou "json"

@dataclass(frozen=True)
class ChangeSet:
    change_set_id: str            # Ex: "CS-REQ-JOB-TREVAS-001-EXTRACTION-01"
    request_id: str               # Correlação com a ExecutionRequest original
    job_id: str
    book_id: str
    stage: str
    agent: str
    operations: tuple[ChangeOperation, ...]
    metadata: dict[str, Any]
```

### 4.2 `ChangeSetBuilder`
- **Responsabilidade**: Recebe a `ExecutionRequest` e o `ExecutionResult` (com veredito `ACCEPT`) e monta o objeto `ChangeSet`.
- **Comportamento**:
  1. Itera sobre o mapa `proposedArtifacts` do `ExecutionResult`.
  2. Para cada caminho:
     - Se o arquivo já existe no filesystem (consultado de forma read-only): classifica a operação como `UPDATE` e calcula o SHA256 do arquivo atual como `expected_base_sha256`.
     - Se o arquivo não existe: classifica a operação como `CREATE` com `expected_base_sha256 = None`.
  3. Não executa gravações, não chama LLMs e não muta os parâmetros de entrada.

### 4.3 Semântica Estrita das Operações

#### 4.3.1 Semântica de `CREATE`
- **Condição Necessária**: O arquivo alvo **não pode existir** no disco no momento da pré-condição.
- **Falha**: Se o arquivo existir no momento da pré-condição $\rightarrow$ `ERR_CREATE_CONFLICT`. A operação não sobrescreve o arquivo e exige intervenção humana (`HUMAN_REVIEW`).

#### 4.3.2 Semântica de `UPDATE` (Optimistic Concurrency)
- **Condição Necessária**: O arquivo alvo **deve existir** no disco E seu hash SHA256 atual no disco deve ser rigorosamente igual a `expected_base_sha256`.
- **Falha**: Se o hash atual no disco diferir de `expected_base_sha256` (indicando mutação externa ou execução concorrente) $\rightarrow$ `ERR_STALE_BASE`. O patch é rejeitado e escalado para `HUMAN_REVIEW`.

### 4.4 `ApplicationPolicy` e Política de Caminhos Protegidos

O `ApplicationPolicy` avalia se o `ChangeSet` pode prosseguir para aplicação automática (`AUTO_APPLY_ALLOWED`), se exige revisão humana (`HUMAN_REVIEW`) ou se deve ser bloqueado (`BLOCKED`).

#### 4.4.1 Matriz de Caminhos Protegidos (Protected Paths)

| Padrão de Caminho | Categoria | Ação da Política | Justificativa |
|---|---|---|---|
| `scripts/agents/**` | Runtime de Agentes | `HUMAN_REVIEW` | Código do sistema; não pode ser auto-modificado |
| `schemas/**` | Contratos Formais | `HUMAN_REVIEW` | Schemas JSON Draft 2020-12 invioláveis |
| `.github/**` | CI/CD Workflows | `HUMAN_REVIEW` | Configurações de automação e validação remota |
| `docs/architecture/**` | Arquitetura / Constituição | `HUMAN_REVIEW` | Cláusulas constitucionais e pipeline |
| `docs/superpowers/**` | Specs e Planos | `HUMAN_REVIEW` | Especificações canônicas aprovadas |
| `scripts/*.py` | Scripts Centrais | `HUMAN_REVIEW` | Validadores centrais (`validate_data.py`, etc.) |
| `docs/reference/**` | Regras de Domínio | `HUMAN_REVIEW` | Regras canônicas de catalogação |
| `data/**` | Artefatos de Domínio | `AUTO_APPLY_ALLOWED` | Destino natural dos agentes (se dentro do write-scope) |
| `coordination/**` | Filas e Livros | `AUTO_APPLY_ALLOWED` | Metadados e filas de orquestração |

Se qualquer operação em um `ChangeSet` atingir um caminho protegido:
- O `ChangeSet` é classificado como `HUMAN_REVIEW` com código `ERR_PROTECTED_PATH`.
- Nenhuma gravação automática é executada.

### 4.5 `PreconditionValidator`
Executado imediatamente antes da fase de staging e commit, valida deterministicamente em modo fail-closed:
1. `PATH_SAFETY`: Caminho é estritamente relativo, normalizado, sem `..`, sem letras de unidade (Windows `C:`) e sem prefixos UNC (`\\`).
2. `WRITE_SCOPE`: Caminho está explicitamente autorizado no `allowedWriteScope` da requisição.
3. `EXISTENCE_FOR_CREATE`: Para `CREATE`, `os.path.exists(target_path) == False`.
4. `EXISTENCE_FOR_UPDATE`: Para `UPDATE`, `os.path.exists(target_path) == True`.
5. `BASE_HASH_INTEGRITY`: Para `UPDATE`, `sha256(current_file_bytes) == expected_base_sha256`.
6. `OPERATION_WHITELIST`: Tipo de operação pertence estritamente a `{"CREATE", "UPDATE"}`.

### 4.6 `PatchApplier` (Em Memória)
- Valida que o conteúdo candidato seja UTF-8 válido e atenda aos requisitos de formato (valida sintaxe JSON caso o arquivo seja `.json`).
- Gera uma representação em memória `CandidateArtifact(target_path=..., content_bytes=...)` pronta para ser estagiada.

### 4.7 Estratégia de Staging e Aplicação Atômica

Como sistemas de arquivos locais não fornecem transações ACID multi-arquivo nativas, a V2.1 implementa uma estratégia de **Staging em 2 Fases com Journal de Compensação**:

```text
[Fase 1: Preparação em Staging]
1. Cria diretório temporário isolado: `.daemon_staging/<changeSetId>/`.
2. Grava todos os arquivos candidatos no diretório de staging.
3. Valida integridade e hash de cada arquivo estagiado.

[Fase 2: Transação de Substituição Atômica]
4. Cria snapshot de backup dos arquivos existentes em `.daemon_staging/<changeSetId>/backups/`.
5. Registra journal de operações pendentes em memória e disco.
6. Aplica cada arquivo sequencialmente usando substituição atômica unitária do SO (`os.replace` / atomic rename).

[Fase 3: Tratamento de Falha e Rollback Compensatório]
- Se ocorrer QUALQUER falha de I/O durante o passo 6:
  a. Interrompe imediatamente novas gravações.
  b. Restaura todos os arquivos modificados a partir do snapshot de backup.
  c. Limpa o staging.
  d. Emite ApplicationResult com status `ROLLED_BACK` e código `ERR_ATOMIC_COMMIT_FAILED`.
- Se a restauração de backup também encontrar erro fatal de disco:
  a. Emite status `CRITICAL_ROLLBACK_FAILED` com journal completo para recuperação manual.
```

### 4.8 `ApplicationResult`

Estrutura formal do resultado de aplicação:

```python
@dataclass(frozen=True)
class AppliedOperationRecord:
    operation_id: str
    type: str
    target_path: str
    previous_sha256: str | None
    resulting_sha256: str
    bytes_written: int

@dataclass(frozen=True)
class ApplicationResult:
    change_set_id: str
    request_id: str
    status: str                   # "SUCCESS", "PRECONDITION_FAILED", "STAGING_FAILED", "COMMIT_FAILED", "ROLLED_BACK", "HUMAN_REVIEW_REQUIRED", "BLOCKED"
    applied_operations: tuple[AppliedOperationRecord, ...]
    blocked_operations: tuple[dict[str, Any], ...]
    failure_code: str | None      # Ex: "ERR_STALE_BASE", "ERR_PROTECTED_PATH"
    reasons: tuple[str, ...]
    applied_at: str | None        # ISO 8601 timestamp
    duration_ms: float
    metadata: dict[str, Any]
```

---

## 5. Taxonomia Completa de Falhas da V2.1

| Código de Erro | Severidade | Ação do Sistema | Descrição |
|---|---|---|---|
| `ERR_CHANGESET_INVALID` | BLOCKED | Rejeição imediata | Estrutura ou schema do ChangeSet corrompida |
| `ERR_OPERATION_NOT_ALLOWED` | BLOCKED | Rejeição imediata | Tentativa de DELETE, RENAME, MOVE ou operação desconhecida |
| `ERR_WRITE_SCOPE_VIOLATION` | BLOCKED | Rejeição imediata | Caminho fora do allowedWriteScope da ExecutionRequest |
| `ERR_PROTECTED_PATH` | HUMAN_REVIEW | Escalação | Tentativa de mutação em código, schemas ou arquitetura |
| `ERR_STALE_BASE` | HUMAN_REVIEW | Escalação | Hash do arquivo no disco difere da base esperada |
| `ERR_CREATE_CONFLICT` | HUMAN_REVIEW | Escalação | Arquivo marcado para CREATE já existe no disco |
| `ERR_PATCH_INVALID` | BLOCKED | Rejeição imediata | Conteúdo candidato não decodifica como UTF-8 ou JSON inválido |
| `ERR_STAGING_FAILED` | BLOCKED | Limpeza | Falha de I/O ao gravar no diretório de staging |
| `ERR_ATOMIC_COMMIT_FAILED` | ROLLED_BACK | Rollback total | Falha durante o commit de arquivos; estado original restaurado |
| `ERR_CRITICAL_ROLLBACK_FAILED`| CRITICAL | Alerta Urgente | Falha de hardware/disco ao restaurar backups; journal preservado |
| `ERR_FILESYSTEM_PERMISSIONS` | BLOCKED | Rejeição imediata | Falha de permissão de acesso/escrita no sistema operacional |

---

## 6. Políticas de Escalação para Revisão Humana (Human Review Policy)

Um `ChangeSet` NÃO pode ser aplicado automaticamente e DEVE ser escalado para `HUMAN_REVIEW` quando:
1. Contiver mutações em qualquer caminho da lista de **Caminhos Protegidos** (`scripts/`, `schemas/`, `.github/`, `docs/architecture/`).
2. Ocorrer **Stale Base** (`expected_base_sha256 != current_sha256`), indicando alteração concorrente ou descompasso de versão.
3. Ocorrer **Create Conflict** (arquivo já existe onde se pretendia criar novo).
4. O `ExecutionResult` de origem tiver gerado incertezas (`uncertainties` não vazias).
5. O estágio alvo for o estágio terminal `release` (exige validação humana conforme Constituição e V1).

---

## 7. Estratégia de Testes e Portões de Qualidade

### 7.1 Testabilidade Determinística e Offline
- **Zero Dependências Externas**: Nenhum teste utiliza rede, tokens, chaves de API ou serviços em nuvem.
- **Isolamento de Filesystem (`tmp_path`)**: Todos os testes de criação, substituição atômica, falha de pré-condição e rollback compensatório operam exclusivamente em diretórios temporários criados pelo `pytest` (`tmp_path`). O repositório de trabalho real nunca é tocado pelos testes.

### 7.2 Casos de Teste Essenciais
1. **ChangeSet Creation**:
   - Mapeamento correto de `proposedArtifacts` para `CREATE` (arquivo novo) e `UPDATE` (arquivo existente).
   - Cálculo determinístico de `expected_base_sha256`.
2. **Policy Enforcement**:
   - `AUTO_APPLY_ALLOWED` para caminhos em `data/` e `coordination/`.
   - `HUMAN_REVIEW` ao tocar em `scripts/agents/` ou `schemas/`.
   - `BLOCKED` para operações proibidas (`DELETE`).
3. **Precondition Validation**:
   - Rejeição de `CREATE` se arquivo já existe.
   - Rejeição de `UPDATE` se hash atual difere de `expected_base_sha256`.
   - Rejeição de path traversal (`..`) e caminhos absolutos.
4. **Atomic Application & Rollback**:
   - Aplicação de ChangeSet multi-arquivo bem-sucedida: todos os arquivos atualizados/criados com novos hashes registrados.
   - Simulação de erro de I/O no 2º arquivo de um lote de 3: restauração atômica do 1º arquivo ao estado original e estado final idêntico ao inicial (`ROLLED_BACK`).
5. **Imutabilidade e Segurança**:
   - Imutabilidade das dataclasses (`ChangeSet`, `ChangeOperation`, `ApplicationResult`).
   - Não-mutação dos objetos de entrada.

---

## 8. Sequência de Implementação Proposta (Tasks da V2.1)

1. **Task 25 — ChangeSet Contracts & ChangeSetBuilder**:
   - Schemas e dataclasses para `ChangeSet`, `ChangeOperation` e `ApplicationResult`.
   - Componente `ChangeSetBuilder`.
2. **Task 26 — ApplicationPolicy & ProtectedPaths**:
   - Validador de políticas de governança e detecção de caminhos protegidos.
3. **Task 27 — PreconditionValidator (Optimistic Concurrency)**:
   - Validador fail-closed de pré-condições, integridade de caminhos e SHA256 base.
4. **Task 28 — PatchApplier (Candidate Builder)**:
   - Montador de conteúdo candidato e validador sintático em memória.
5. **Task 29 — Staging & Atomic Filesystem Applier**:
   - Executor transacional em 2 fases com substituição atômica e journal de compensação (rollback).
6. **Task 30 — Persistence Pipeline Coordinator & E2E Integration Fixture**:
   - Encadeamento end-to-end do pipeline de persistência com `ExecutionCoordinator` da V2 em ambiente de teste.

---

## 9. Compatibilidade com as Versões Anteriores

- **Versão 1 (`multiagent-context-v1`)**: Todos os contratos (`agent-job`, `agent-handoff`, `context-pack`, `source-manifest`, `review-request`, `relation`), o `JobStore`, o `HandoffStore` e o `OrchestratorStateSelector` permanecem 100% inalterados e compatíveis.
- **Versão 2 (`multiagent-execution-v2`)**: O `ExecutionCoordinator`, o `ExecutionRequestBuilder`, o `ContextMaterializer`, o `PromptRenderer`, o `FakeExecutionAdapter` e o `ExecutionResultValidator` permanecem intactos. A V2.1 consome o `ExecutionResult` validado emitido pela V2 sem modificar suas interfaces.
