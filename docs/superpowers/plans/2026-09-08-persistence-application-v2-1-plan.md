# Persistence/Application Layer V2.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Aplicar de forma determinística e segura ChangeSets CREATE/UPDATE já aceitos pela V2, sem conceder autoridade direta de filesystem ao LLM.

**Architecture:** Um Execution Result aceito é convertido em ChangeSet estruturado, submetido a ApplicationPolicy, validações de path/preconditions, construção de candidates e staging runtime-owned. A aplicação usa semântica all-or-nothing por prevalidation, journal e rollback compensatório.

**Tech Stack:** Python, JSON Schema Draft 2020-12, jsonschema, pathlib/os, hashlib, pytest, Git/GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-08-persistence-application-v2-1-design.md`

---

## Global Constraints

1. **LLM output never has filesystem write authority.** O modelo apenas propõe artefatos em memória (`proposedArtifacts`).
2. **`ACCEPT` does not bypass ApplicationPolicy.** O veredito do `ExecutionResultValidator` apenas habilita a avaliação de persistência.
3. **CREATE and UPDATE only.** Mutações autorizadas restringem-se estritamente à criação e atualização de arquivos.
4. **DELETE/RENAME/MOVE are not expressible operations.** O runtime e os schemas rejeitam expressamente qualquer uma dessas operações na entrada.
5. **Auto-apply is allowlist-based, default HUMAN_REVIEW.** Qualquer caminho não contido em `AutoApplyRoots` exige revisão humana.
6. **Requested write scope can only restrict authority, never expand it.** A autoridade efetiva é: $\text{Scope} = \text{requested\_write\_scope} \cap \text{AutoApplyRoots} \cap \text{ApplicationPolicy}$.
7. **.git and runtime/staging targets are hard-blocked.** Qualquer tentativa de mutação em `.git/`, staging ou audit storage é rejeitada com `BLOCKED`.
8. **UPDATE requires expected_base_sha256.** Concorrência otimista estrita; se o hash do arquivo em disco divergir $\rightarrow$ `ERR_STALE_BASE` $\rightarrow$ `HUMAN_REVIEW`.
9. **CREATE must never overwrite existing files.** Criação exclusiva via `os.O_CREAT | os.O_EXCL` (modo `"x"`); se o arquivo existir $\rightarrow$ `ERR_CREATE_CONFLICT` $\rightarrow$ `HUMAN_REVIEW`.
10. **UTF-8 text domain only for automatic application.** Conteúdo candidato deve ser decodificável como UTF-8 estrito sem BOM. Arquivos binários $\rightarrow$ `HUMAN_REVIEW`.
11. **JSON candidates must parse before apply.** Arquivos `.json` passam por validação sintática estrita antes do estagiamento.
12. **Symlink/junction/reparse-point ancestors deny auto-apply.** Qualquer componente ancestral que seja link, junção ou reparse point $\rightarrow$ fail-closed com `ERR_SYMLINK_REPARSE_POINT_DETECTED` $\rightarrow$ `HUMAN_REVIEW`.
13. **TOCTOU preconditions are rechecked immediately before mutation.** Na Fase 4, antes da primeira mutação física, todos os hashes, contenção canônica e ausência de symlinks são revalidados ao vivo no disco.
14. **Staging/audit roots are runtime-owned and LLM-independent.** As raízes de execução provêm exclusivamente da configuração local confiável do sistema.
15. **Staging must be same-filesystem with repository targets.** O staging e o repositório devem residir no mesmo volume para garantir atomicidade de renomeação (`os.replace`).
16. **Cross-volume staging fails closed.** Se a equivalência de volume não for confirmada $\rightarrow$ `ERR_CROSS_VOLUME_STAGING` $\rightarrow$ `HUMAN_REVIEW`.
17. **Multi-file ACID is NOT claimed.** A garantia multi-arquivo é all-or-nothing baseada em pré-validação, journal transacional e rollback compensatório.
18. **All-or-nothing semantics use journal + compensating rollback.** Em caso de falha durante a aplicação sequencial, operações anteriores são desfeitas em ordem reversa.
19. **Rollback cannot overwrite an external concurrent mutation.** Se um arquivo foi modificado por processo externo entre a aplicação e o rollback, a reversão aborta com `ROLLBACK_FAILED` (`ERR_CRITICAL_ROLLBACK_FAILED` $\rightarrow$ `BLOCKED` + `HUMAN_REVIEW`).
20. **Resource limits come from trusted local configuration.** Limites de tamanho de arquivo, lote e contagem são definidos no runtime e não podem ser alterados pela requisição.
21. **Tests never mutate the real repository.** Todos os testes de filesystem utilizam exclusivamente fixtures `tmp_path`.
22. **V1/V2 public contracts remain compatible.** Nenhuma interface pública de jobs, handoffs ou execution coordinator é quebrada pela V2.1.

---

## Proposed File Structure

```text
schemas/
├── change-set.schema.json
└── application-result.schema.json

scripts/agents/
├── change_set.py
├── application_runtime.py
├── application_policy.py
├── content_validator.py
├── precondition_validator.py
├── patch_applier.py
├── transaction_journal.py
├── staging_manager.py
├── filesystem_primitives.py
├── change_set_applier.py
├── application_result.py
└── application_coordinator.py

tests/agents/
├── test_change_set.py
├── test_application_policy.py
├── test_content_validator.py
├── test_precondition_validator.py
├── test_patch_applier.py
├── test_transaction_journal.py
├── test_staging_manager.py
├── test_filesystem_primitives.py
├── test_change_set_applier.py
├── test_application_result.py
├── test_application_coordinator.py
└── test_persistence_pipeline_e2e.py
```

---

## Failure Taxonomy Mapping

| Código de Erro | Componente Responsável | Teste Responsável | Status Resultante | Ação do Sistema |
|---|---|---|---|---|
| `ERR_CHANGESET_INVALID` | `ChangeSetBuilder` | `test_change_set.py` | `BLOCKED` | Rejeição imediata |
| `ERR_OPERATION_NOT_ALLOWED` | `ChangeSetBuilder` / `ApplicationPolicy` | `test_change_set.py` | `BLOCKED` | Rejeição de DELETE/RENAME/MOVE |
| `ERR_WRITE_SCOPE_VIOLATION` | `ApplicationPolicy` / `PreconditionValidator` | `test_application_policy.py` | `BLOCKED` | Rejeição de caminho fora do write-scope |
| `ERR_HARD_BLOCKED_PATH` | `ApplicationPolicy` | `test_application_policy.py` | `BLOCKED` | Rejeição de .git, staging, UNC, ADS, nomes reservados |
| `ERR_PATH_TRAVERSAL` | `ApplicationPolicy` | `test_application_policy.py` | `BLOCKED` | Rejeição de `..`, caminhos absolutos |
| `ERR_CONTAINMENT_VIOLATION` | `ApplicationPolicy` / `PreconditionValidator` | `test_application_policy.py` | `BLOCKED` | Rejeição de escape do repo_root |
| `ERR_SYMLINK_REPARSE_POINT_DETECTED` | `ApplicationPolicy` / `PreconditionValidator` | `test_application_policy.py` | `HUMAN_REVIEW` | Escalação por presença de symlink ancestral |
| `ERR_NON_ALLOWLISTED_PATH` | `ApplicationPolicy` | `test_application_policy.py` | `HUMAN_REVIEW` | Escalação default (fora de AutoApplyRoots) |
| `ERR_PROTECTED_PATH` | `ApplicationPolicy` | `test_application_policy.py` | `HUMAN_REVIEW` | Escalação por tocar scripts, schemas, docs vitais |
| `ERR_CROSS_VOLUME_STAGING` | `StagingManager` | `test_staging_manager.py` | `HUMAN_REVIEW` | Escalação fail-closed por volume divergente |
| `ERR_RESOURCE_BOUND_EXCEEDED` | `ContentValidator` / `PreconditionValidator` | `test_content_validator.py` | `BLOCKED` | Rejeição por estouro de limites |
| `ERR_UNSUPPORTED_CONTENT_DOMAIN` | `ContentValidator` | `test_content_validator.py` | `HUMAN_REVIEW` | Escalação por arquivo binário / não UTF-8 |
| `ERR_PATCH_INVALID` | `PatchApplier` | `test_patch_applier.py` | `BLOCKED` | Rejeição por falha de sintaxe JSON/UTF-8 |
| `ERR_STAGING_FAILED` | `StagingManager` | `test_staging_manager.py` | `BLOCKED` | Limpeza e rejeição por erro de I/O no staging |
| `ERR_STALE_BASE` | `PreconditionValidator` | `test_precondition_validator.py` | `HUMAN_REVIEW` | Escalação por conflito de hash em UPDATE (TOCTOU) |
| `ERR_CREATE_CONFLICT` | `PreconditionValidator` / `FileSystemPrimitives` | `test_precondition_validator.py` | `HUMAN_REVIEW` | Escalação por existência prévia em CREATE |
| `ERR_ATOMIC_COMMIT_FAILED` | `ChangeSetApplier` | `test_change_set_applier.py` | `ROLLED_BACK` | Rollback bem-sucedido $\rightarrow$ `HUMAN_REVIEW` |
| `ERR_CRITICAL_ROLLBACK_FAILED` | `ChangeSetApplier` | `test_change_set_applier.py` | `ROLLBACK_FAILED` | Falha no rollback $\rightarrow$ `BLOCKED` + `HUMAN_REVIEW` |
| `ERR_FILESYSTEM_PERMISSIONS` | `FileSystemPrimitives` | `test_filesystem_primitives.py` | `BLOCKED` | Rejeição por erro de permissão do SO |

---

## Tasks Breakdown

### Task 25 — ChangeSet Contracts & ChangeSetBuilder

- **Goal**: Definir o schema formal `change-set.schema.json`, as dataclasses imutáveis `ChangeSet` e `ChangeOperation`, e implementar o `ChangeSetBuilder` determinístico que consome um `ExecutionResult` aceito (status `ACCEPT`) e gera um `ChangeSet` em memória.
- **Files**:
  - `schemas/change-set.schema.json`
  - `scripts/agents/change_set.py`
  - `tests/agents/test_change_set.py`
- **Interfaces**:
  ```python
  @dataclass(frozen=True)
  class ChangeOperation:
      operation_id: str
      type: str  # "CREATE" | "UPDATE"
      target_path: str
      expected_base_sha256: str | None
      candidate_content: str
      encoding: str = "utf-8"
      format: str = "text"

  @dataclass(frozen=True)
  class ChangeSet:
      change_set_id: str
      request_id: str
      job_id: str
      book_id: str
      stage: str
      agent: str
      operations: tuple[ChangeOperation, ...]
      metadata: dict[str, Any]

  class ChangeSetBuilder:
      def __init__(self, repo_root: Path | str) -> None: ...
      def build(self, request: dict[str, Any], result: dict[str, Any]) -> ChangeSet: ...
  ```
- **Consumes**: `ExecutionRequest` dict, `ExecutionResult` dict (com veredito `ACCEPT`).
- **Produces**: Instância imutável de `ChangeSet`.
- **Dependencies**: `scripts/agents/contracts.py`.
- **Non-goals**: Não executa escritas no sistema de arquivos; não chama LLMs; não aceita operações destrutivas.
- **TDD Steps**:
  - [ ] Step 25.1: Criar teste falhando `tests/agents/test_change_set.py` cobrindo validação de schema JSON Draft 2020-12 para `change-set.schema.json`.
  - [ ] Step 25.2: Implementar `schemas/change-set.schema.json`.
  - [ ] Step 25.3: Criar teste falhando para `ChangeSetBuilder` com operações `CREATE` (arquivo não existe) e `UPDATE` (arquivo existente com cálculo de `expected_base_sha256`).
  - [ ] Step 25.4: Implementar `ChangeSetBuilder` em `scripts/agents/change_set.py`.
  - [ ] Step 25.5: Criar teste falhando verificando rejeição de `DELETE`/`RENAME`/`MOVE` ou entrada inválida com `ERR_CHANGESET_INVALID`.
- **Exact Tests**: `pytest tests/agents/test_change_set.py -v`.
- **Exact Commands**: `python -m pytest tests/agents/test_change_set.py -q`.
- **Expected RED**: `ImportError: cannot import name 'ChangeSetBuilder'`, `FileNotFoundError: change-set.schema.json`.
- **Minimal Implementation**: Criar o schema Draft 2020-12, definir dataclasses com `frozen=True` e implementar lógica determinística de classificação em `ChangeSetBuilder`.
- **Expected GREEN**: `tests/agents/test_change_set.py passed`.
- **Regression Gates**: `python -m pytest tests/agents -q`.
- **Commit Message**: `feat: implement change-set contract and builder`
- **Stop Condition**: Testes de `test_change_set.py` 100% verdes.

---

### Task 26 — Application Runtime Configuration & Path Policy

- **Goal**: Implementar `ApplicationRuntimeConfig` (configuração confiável fora do controle de LLM) e `ApplicationPolicy` (governança baseada em allowlist restritiva, proteção contra symlinks, detecção de reparse points e hardening de caminhos Windows).
- **Files**:
  - `scripts/agents/application_runtime.py`
  - `scripts/agents/application_policy.py`
  - `tests/agents/test_application_policy.py`
- **Interfaces**:
  ```python
  @dataclass(frozen=True)
  class ResourceBounds:
      max_file_size_bytes: int = 50 * 1024 * 1024
      max_changeset_size_bytes: int = 200 * 1024 * 1024
      max_operations_per_changeset: int = 100
      max_total_staging_bytes: int = 500 * 1024 * 1024

  @dataclass(frozen=True)
  class ApplicationRuntimeConfig:
      repository_root: Path
      staging_root: Path
      audit_root: Path
      auto_apply_roots: tuple[str, ...]
      protected_roots: tuple[str, ...]
      hard_blocked_roots: tuple[str, ...]
      resource_bounds: ResourceBounds

  @dataclass(frozen=True)
  class PolicyEvaluationResult:
      allowed: bool
      action: str  # "AUTO_APPLY_ELIGIBLE", "HUMAN_REVIEW", "BLOCKED"
      code: str | None
      reasons: tuple[str, ...]

  class ApplicationPolicy:
      def __init__(self, config: ApplicationRuntimeConfig) -> None: ...
      def evaluate_path(self, target_path: str, allowed_write_scope: list[str]) -> PolicyEvaluationResult: ...
      def evaluate_changeset(self, change_set: ChangeSet, allowed_write_scope: list[str]) -> PolicyEvaluationResult: ...
  ```
- **Consumes**: `ChangeSet`, `allowedWriteScope`, `ApplicationRuntimeConfig`.
- **Produces**: `PolicyEvaluationResult`.
- **Dependencies**: Task 25 (`ChangeSet`).
- **Non-goals**: Não altera arquivos; não aceita caminhos de raiz vindos da `ExecutionRequest`.
- **TDD Steps**:
  - [ ] Step 26.1: Criar teste falhando `tests/agents/test_application_policy.py` para allowlist restritiva (`AutoApplyRoots` $\rightarrow$ elegível; fora da allowlist $\rightarrow$ `HUMAN_REVIEW` com `ERR_NON_ALLOWLISTED_PATH`).
  - [ ] Step 26.2: Criar teste falhando para caminhos protegidos (`scripts/`, `schemas/`, `.github/`, etc. $\rightarrow$ `ERR_PROTECTED_PATH`).
  - [ ] Step 26.3: Criar teste falhando para bloqueio hard-blocked (`.git/`, UNC, Alternate Data Streams `:stream`, DOS reserved names `CON`, `NUL` $\rightarrow$ `ERR_HARD_BLOCKED_PATH`).
  - [ ] Step 26.4: Criar teste falhando para detecção de symlinks/junctions ancestrais $\rightarrow$ `ERR_SYMLINK_REPARSE_POINT_DETECTED` $\rightarrow$ `HUMAN_REVIEW`.
  - [ ] Step 26.5: Criar teste falhando para interseção estrita com `allowedWriteScope` (request não pode ampliar allowlist).
  - [ ] Step 26.6: Implementar `scripts/agents/application_runtime.py` e `scripts/agents/application_policy.py`.
- **Exact Tests**: `pytest tests/agents/test_application_policy.py -v`.
- **Exact Commands**: `python -m pytest tests/agents/test_application_policy.py -q`.
- **Expected RED**: `ModuleNotFoundError: No module named 'scripts.agents.application_policy'`.
- **Minimal Implementation**: Implementar normalização de casing (`normcase`), validação de regex/fnmatch para caminhos Windows/POSIX, checagem de symlinks ancestrais via `islink` e lógica de interseção de autoridade.
- **Expected GREEN**: `tests/agents/test_application_policy.py passed`.
- **Regression Gates**: `python -m pytest tests/agents -q`.
- **Commit Message**: `feat: implement application runtime config and allowlist policy`
- **Stop Condition**: Todos os testes de política de caminhos 100% verdes.

---

### Task 27 — Content Domain & Resource Bounds Validator

- **Goal**: Implementar validação determinística de domínio de conteúdo (estritamente texto UTF-8 sem BOM, parse de JSON para extensões `.json`, rejeição de arquivos binários) e imposição estrita de limites de recursos locais (`ResourceBounds`).
- **Files**:
  - `scripts/agents/content_validator.py`
  - `tests/agents/test_content_validator.py`
- **Interfaces**:
  ```python
  @dataclass(frozen=True)
  class ContentValidationResult:
      valid: bool
      code: str | None
      reasons: tuple[str, ...]

  class ContentValidator:
      def __init__(self, bounds: ResourceBounds) -> None: ...
      def validate_operation_content(self, op: ChangeOperation) -> ContentValidationResult: ...
      def validate_changeset_bounds(self, change_set: ChangeSet) -> ContentValidationResult: ...
  ```
- **Consumes**: `ChangeSet`, `ChangeOperation`, `ResourceBounds`.
- **Produces**: `ContentValidationResult`.
- **Dependencies**: Task 25, Task 26.
- **Non-goals**: Não adivinha encodings (sem fallback latin-1/windows-1252); não permite patches binários.
- **TDD Steps**:
  - [ ] Step 27.1: Criar teste falhando `tests/agents/test_content_validator.py` cobrindo rejeição de bytes não-UTF-8 e BOM UTF-8 $\rightarrow$ `ERR_UNSUPPORTED_CONTENT_DOMAIN`.
  - [ ] Step 27.2: Criar teste falhando cobrindo validação sintática de arquivos `.json` $\rightarrow$ `ERR_PATCH_INVALID` se o JSON for malformado.
  - [ ] Step 27.3: Criar teste falhando cobrindo estouro de `MAX_FILE_SIZE_BYTES`, `MAX_CHANGESET_SIZE_BYTES` e `MAX_OPERATIONS_PER_CHANGESET` $\rightarrow$ `ERR_RESOURCE_BOUND_EXCEEDED`.
  - [ ] Step 27.4: Implementar `scripts/agents/content_validator.py`.
- **Exact Tests**: `pytest tests/agents/test_content_validator.py -v`.
- **Exact Commands**: `python -m pytest tests/agents/test_content_validator.py -q`.
- **Expected RED**: `ModuleNotFoundError: No module named 'scripts.agents.content_validator'`.
- **Minimal Implementation**: Implementar decodificação UTF-8 estrita (`codecs.decode(..., 'utf-8')`), `json.loads` para `.json`, e soma de bytes contra os limites configurados.
- **Expected GREEN**: `tests/agents/test_content_validator.py passed`.
- **Regression Gates**: `python -m pytest tests/agents -q`.
- **Commit Message**: `feat: implement content domain and resource bounds validator`
- **Stop Condition**: Testes de `test_content_validator.py` 100% verdes.

---

### Task 28 — PreconditionValidator & Full TOCTOU Rechecker

- **Goal**: Implementar validador fail-closed de pré-condições em duas etapas: análise inicial (Fase 1) e revalidação completa TOCTOU (Fase 4, imediatamente pré-mutação física no disco), garantindo contenção canônica, ausência de symlinks e integridade de hashes base.
- **Files**:
  - `scripts/agents/precondition_validator.py`
  - `tests/agents/test_precondition_validator.py`
- **Interfaces**:
  ```python
  @dataclass(frozen=True)
  class PreconditionValidationResult:
      valid: bool
      code: str | None
      reasons: tuple[str, ...]

  class PreconditionValidator:
      def __init__(self, config: ApplicationRuntimeConfig, policy: ApplicationPolicy, content_validator: ContentValidator) -> None: ...
      def validate_initial(self, change_set: ChangeSet, allowed_write_scope: list[str]) -> PreconditionValidationResult: ...
      def validate_toctou_pre_mutation(self, change_set: ChangeSet, allowed_write_scope: list[str]) -> PreconditionValidationResult: ...
  ```
- **Consumes**: `ChangeSet`, `ApplicationRuntimeConfig`, filesystem real em disco (read-only).
- **Produces**: `PreconditionValidationResult`.
- **Dependencies**: Tasks 25, 26, 27.
- **Non-goals**: Não modifica arquivos em disco; não cria arquivos de staging.
- **TDD Steps**:
  - [ ] Step 28.1: Criar teste falhando `tests/agents/test_precondition_validator.py` para Fase 1 (validação inicial de scope, allowlist e existência).
  - [ ] Step 28.2: Criar teste falhando para Fase 4 TOCTOU `UPDATE`: alteração externa concorrente no arquivo alvo $\rightarrow$ aborta com `ERR_STALE_BASE`.
  - [ ] Step 28.3: Criar teste falhando para Fase 4 TOCTOU `CREATE`: surgimento externo concorrente de arquivo alvo $\rightarrow$ aborta com `ERR_CREATE_CONFLICT`.
  - [ ] Step 28.4: Criar teste falhando para Fase 4 TOCTOU Symlink: substituição de diretório pai por junction/symlink antes da mutação $\rightarrow$ aborta com `ERR_SYMLINK_REPARSE_POINT_DETECTED`.
  - [ ] Step 28.5: Implementar `scripts/agents/precondition_validator.py`.
- **Exact Tests**: `pytest tests/agents/test_precondition_validator.py -v`.
- **Exact Commands**: `python -m pytest tests/agents/test_precondition_validator.py -q`.
- **Expected RED**: `ModuleNotFoundError: No module named 'scripts.agents.precondition_validator'`.
- **Minimal Implementation**: Implementar leitura de bytes ao vivo, cálculo SHA256 e inspeção da árvore física de diretórios imediatamente pré-escrita.
- **Expected GREEN**: `tests/agents/test_precondition_validator.py passed`.
- **Regression Gates**: `python -m pytest tests/agents -q`.
- **Commit Message**: `feat: implement precondition validator and toctou rechecker`
- **Stop Condition**: Testes de pré-condições e TOCTOU 100% verdes.

---

### Task 29 — PatchApplier (In-Memory Candidate Builder)

- **Goal**: Implementar o `PatchApplier` que constrói representações em memória dos artefatos candidatos (`CandidateArtifact`), validando integridade de codificação UTF-8 e calculando o hash SHA256 do conteúdo candidato.
- **Files**:
  - `scripts/agents/patch_applier.py`
  - `tests/agents/test_patch_applier.py`
- **Interfaces**:
  ```python
  @dataclass(frozen=True)
  class CandidateArtifact:
      operation_id: str
      target_path: str
      content_bytes: bytes
      candidate_sha256: str
      encoding: str
      format: str

  class PatchApplier:
      def __init__(self) -> None: ...
      def construct_candidates(self, change_set: ChangeSet) -> tuple[CandidateArtifact, ...]: ...
  ```
- **Consumes**: `ChangeSet`.
- **Produces**: Tupla de `CandidateArtifact` em memória.
- **Dependencies**: Tasks 25, 27.
- **Non-goals**: Não grava em disco; não executa chamadas de rede ou LLM.
- **TDD Steps**:
  - [ ] Step 29.1: Criar teste falhando `tests/agents/test_patch_applier.py` cobrindo construção correta de `CandidateArtifact` para operações `CREATE` e `UPDATE`.
  - [ ] Step 29.2: Criar teste falhando cobrindo cálculo exato de SHA256 do conteúdo em bytes UTF-8.
  - [ ] Step 29.3: Criar teste falhando cobrindo rejeição com `ERR_PATCH_INVALID` em caso de formato inconsistente.
  - [ ] Step 29.4: Implementar `scripts/agents/patch_applier.py`.
- **Exact Tests**: `pytest tests/agents/test_patch_applier.py -v`.
- **Exact Commands**: `python -m pytest tests/agents/test_patch_applier.py -q`.
- **Expected RED**: `ModuleNotFoundError: No module named 'scripts.agents.patch_applier'`.
- **Minimal Implementation**: Implementar codificação UTF-8 de `candidate_content`, cálculo de `hashlib.sha256` e retorno de tupla imutável.
- **Expected GREEN**: `tests/agents/test_patch_applier.py passed`.
- **Regression Gates**: `python -m pytest tests/agents -q`.
- **Commit Message**: `feat: implement in-memory patch applier and candidate builder`
- **Stop Condition**: Testes de `test_patch_applier.py` 100% verdes.

---

### Task 30 — Transaction Journal & Same-Filesystem Staging Manager

- **Goal**: Implementar o `TransactionJournal` (fonte exclusiva de autoridade de compensação) e o `StagingManager` com verificação de invariância de mesmo volume/filesystem, gravação isolada de candidatos e ciclo de vida de limpeza.
- **Files**:
  - `scripts/agents/transaction_journal.py`
  - `scripts/agents/staging_manager.py`
  - `tests/agents/test_transaction_journal.py`
  - `tests/agents/test_staging_manager.py`
- **Interfaces**:
  ```python
  @dataclass(frozen=True)
  class JournalOperationEntry:
      operation_id: str
      type: str
      target_path: str
      original_exists: bool
      expected_base_sha256: str | None
      candidate_sha256: str
      applied_status: str  # "NOT_APPLIED", "APPLIED", "REVERTED", "REVERT_FAILED"
      observed_post_apply_sha256: str | None
      backup_path: str | None
      applied_at: str | None
      reverted_at: str | None
      rollback_attempted: bool
      rollback_result: str | None
      error_message: str | None

  @dataclass(frozen=True)
  class TransactionJournal:
      change_set_id: str
      request_id: str
      started_at: str
      staging_dir: str
      operations: tuple[JournalOperationEntry, ...]
      rollback_attempted: bool
      rollback_succeeded: bool
      filesystem_state: str

  class StagingManager:
      def __init__(self, config: ApplicationRuntimeConfig) -> None: ...
      def verify_same_filesystem(self) -> bool: ...
      def prepare_staging(self, change_set_id: str) -> Path: ...
      def stage_candidates(self, staging_dir: Path, candidates: tuple[CandidateArtifact, ...]) -> dict[str, Path]: ...
      def create_backup(self, staging_dir: Path, target_path: str, repo_root: Path) -> Path: ...
      def cleanup_staging(self, staging_dir: Path) -> None: ...
      def preserve_for_audit(self, staging_dir: Path, journal: TransactionJournal) -> Path: ...
  ```
- **Consumes**: `CandidateArtifact`, `ApplicationRuntimeConfig`.
- **Produces**: Arquivos estagiados em disco no staging isolado, snapshots de backup e instâncias de `TransactionJournal`.
- **Dependencies**: Tasks 25, 26, 29.
- **Non-goals**: Não altera arquivos alvos do repositório; não permite que a request configure o caminho de staging.
- **TDD Steps**:
  - [ ] Step 30.1: Criar teste falhando `tests/agents/test_staging_manager.py` para verificação de mesmo volume (`verify_same_filesystem()`). Se volumes distintos $\rightarrow$ `ERR_CROSS_VOLUME_STAGING` fail-closed.
  - [ ] Step 30.2: Criar teste falhando para gravação isolada de candidatos e snapshots em staging.
  - [ ] Step 30.3: Criar teste falhando `tests/agents/test_transaction_journal.py` para imutabilidade e transições de estado do journal.
  - [ ] Step 30.4: Criar teste falhando para política de limpeza: `cleanup_staging()` remove arquivos temporários em sucesso/reversão limpa; preserva tudo em `ROLLBACK_FAILED`.
  - [ ] Step 30.5: Implementar `scripts/agents/transaction_journal.py` e `scripts/agents/staging_manager.py`.
- **Exact Tests**: `pytest tests/agents/test_staging_manager.py tests/agents/test_transaction_journal.py -v`.
- **Exact Commands**: `python -m pytest tests/agents/test_staging_manager.py tests/agents/test_transaction_journal.py -q`.
- **Expected RED**: `ModuleNotFoundError: No module named 'scripts.agents.staging_manager'`.
- **Minimal Implementation**: Implementar verificação de `st_dev` / drive letter, gravação em subdiretório temporário e serialização de journal para `audit_root`.
- **Expected GREEN**: Ambos os arquivos de teste passam 100%.
- **Regression Gates**: `python -m pytest tests/agents -q`.
- **Commit Message**: `feat: implement transaction journal and same-filesystem staging manager`
- **Stop Condition**: Testes de staging e journal 100% verdes.

---

### Task 31 — Safe Single-Operation Filesystem Primitives

- **Goal**: Implementar primitivas unitárias atômicas e seguras de baixo nível no sistema de arquivos: criação exclusiva atômica (`O_CREAT | O_EXCL`), substituição atômica unitária (`os.replace`), remoção compensatória estrita para `CREATE` e restauração compensatória estrita para `UPDATE`.
- **Files**:
  - `scripts/agents/filesystem_primitives.py`
  - `tests/agents/test_filesystem_primitives.py`
- **Interfaces**:
  ```python
  class FileSystemPrimitives:
      @staticmethod
      def exclusive_create(target_path: Path, staged_source: Path) -> str: ...
      @staticmethod
      def atomic_replace(target_path: Path, staged_source: Path) -> str: ...
      @staticmethod
      def compensating_remove(target_path: Path, expected_candidate_sha256: str) -> bool: ...
      @staticmethod
      def compensating_restore(target_path: Path, backup_snapshot: Path, expected_post_apply_sha256: str) -> bool: ...
  ```
- **Consumes**: Caminhos de arquivos estagiados e alvos em `tmp_path`.
- **Produces**: Mutações físicas atômicas unitárias e hashes verificados.
- **Dependencies**: Nenhuma direta (utiliza biblioteca padrão Python `os`, `pathlib`, `hashlib`).
- **Non-goals**: Não expõe operação DELETE genérica; nunca toca no repositório de trabalho real nos testes.
- **TDD Steps**:
  - [ ] Step 31.1: Criar teste falhando `tests/agents/test_filesystem_primitives.py` para `exclusive_create`: cria com sucesso quando arquivo não existe; falha com `FileExistsError` sem sobrescrever se o arquivo já existir.
  - [ ] Step 31.2: Criar teste falhando para `atomic_replace`: substitui arquivo atomicamente no mesmo volume e retorna novo SHA256.
  - [ ] Step 31.3: Criar teste falhando para `compensating_remove`: remove arquivo se hash bate com o esperado; recusa e retorna `False` se hash divergir (mutação externa).
  - [ ] Step 31.4: Criar teste falhando para `compensating_restore`: restaura backup se hash atual bate com o pós-aplicação; recusa e retorna `False` se hash divergir.
  - [ ] Step 31.5: Implementar `scripts/agents/filesystem_primitives.py`.
- **Exact Tests**: `pytest tests/agents/test_filesystem_primitives.py -v`.
- **Exact Commands**: `python -m pytest tests/agents/test_filesystem_primitives.py -q`.
- **Expected RED**: `ModuleNotFoundError: No module named 'scripts.agents.filesystem_primitives'`.
- **Minimal Implementation**: Implementar uso de `open(..., 'xb')` / `os.open(..., os.O_CREAT | os.O_EXCL)` e `os.replace`.
- **Expected GREEN**: `tests/agents/test_filesystem_primitives.py passed`.
- **Regression Gates**: `python -m pytest tests/agents -q`.
- **Commit Message**: `feat: implement safe single-operation filesystem primitives`
- **Stop Condition**: Testes de primitivas 100% verdes em `tmp_path`.

---

### Task 32 — ChangeSet Application & Compensating Rollback Engine

- **Goal**: Implementar o `ChangeSetApplier`, orquestrando a execução em 6 fases: validação de pré-condições, montagem de candidatos, staging isolado, revalidação TOCTOU física, aplicação sequencial atômica com snapshots e rollback compensatório restrito e seguro em caso de falha.
- **Files**:
  - `scripts/agents/change_set_applier.py`
  - `tests/agents/test_change_set_applier.py`
- **Interfaces**:
  ```python
  @dataclass(frozen=True)
  class ChangeSetApplicationOutcome:
      status: str  # "APPLIED", "ROLLED_BACK", "ROLLBACK_FAILED", "NOT_APPLIED"
      journal: TransactionJournal
      applied_records: tuple[AppliedOperationRecord, ...]
      failure_code: str | None
      reasons: tuple[str, ...]

  class ChangeSetApplier:
      def __init__(
          self,
          config: ApplicationRuntimeConfig,
          precondition_validator: PreconditionValidator,
          patch_applier: PatchApplier,
          staging_manager: StagingManager,
          primitives: type[FileSystemPrimitives] = FileSystemPrimitives,
      ) -> None: ...
      def apply(self, change_set: ChangeSet, allowed_write_scope: list[str]) -> ChangeSetApplicationOutcome: ...
  ```
- **Consumes**: `ChangeSet`, `allowedWriteScope`, `ApplicationRuntimeConfig`.
- **Produces**: `ChangeSetApplicationOutcome`.
- **Dependencies**: Tasks 25, 26, 27, 28, 29, 30, 31.
- **Non-goals**: Não realiza git commits; não chama agentes externos.
- **TDD Steps**:
  - [ ] Step 32.1: Criar teste falhando `tests/agents/test_change_set_applier.py` para aplicação com sucesso de lote multi-arquivo $\rightarrow$ `status = "APPLIED"`.
  - [ ] Step 32.2: Criar teste falhando simulando falha no 2º arquivo de um lote de 3 $\rightarrow$ rollback compensatório bem-sucedido $\rightarrow$ `status = "ROLLED_BACK"` (`ERR_ATOMIC_COMMIT_FAILED`) e estado do disco 100% restaurado.
  - [ ] Step 32.3: Criar teste falhando simulando mutação concorrente externa antes do rollback $\rightarrow$ recusa de sobrescrita e status `ROLLBACK_FAILED` (`ERR_CRITICAL_ROLLBACK_FAILED`).
  - [ ] Step 32.4: Implementar `scripts/agents/change_set_applier.py`.
- **Exact Tests**: `pytest tests/agents/test_change_set_applier.py -v`.
- **Exact Commands**: `python -m pytest tests/agents/test_change_set_applier.py -q`.
- **Expected RED**: `ModuleNotFoundError: No module named 'scripts.agents.change_set_applier'`.
- **Minimal Implementation**: Implementar encadeamento das 6 fases e motor de rollback em ordem reversa estritamente guiado pelo `TransactionJournal`.
- **Expected GREEN**: `tests/agents/test_change_set_applier.py passed`.
- **Regression Gates**: `python -m pytest tests/agents -q`.
- **Commit Message**: `feat: implement changeset applier and compensating rollback engine`
- **Stop Condition**: Testes de aplicação e rollback 100% verdes.

---

### Task 33 — ApplicationResult Contract & ApplicationCoordinator

- **Goal**: Criar o schema formal `application-result.schema.json`, dataclass `ApplicationResult` e implementar o `ApplicationCoordinator` que conecta o resultado de execução aceito pela V2 (`verdict == "ACCEPT"`) até a entrega do veredito final de aplicação.
- **Files**:
  - `schemas/application-result.schema.json`
  - `scripts/agents/application_result.py`
  - `scripts/agents/application_coordinator.py`
  - `tests/agents/test_application_result.py`
  - `tests/agents/test_application_coordinator.py`
- **Interfaces**:
  ```python
  @dataclass(frozen=True)
  class ApplicationResult:
      change_set_id: str
      request_id: str
      status: str  # "APPLIED", "NOT_APPLIED", "ROLLED_BACK", "ROLLBACK_FAILED", "HUMAN_REVIEW", "BLOCKED"
      applied_operations: tuple[AppliedOperationRecord, ...]
      blocked_operations: tuple[dict[str, Any], ...]
      failure_code: str | None
      reasons: tuple[str, ...]
      applied_at: str | None
      duration_ms: float
      journal: TransactionJournal | None
      metadata: dict[str, Any]

  class ApplicationCoordinator:
      def __init__(
          self,
          config: ApplicationRuntimeConfig,
          builder: ChangeSetBuilder,
          policy: ApplicationPolicy,
          applier: ChangeSetApplier,
      ) -> None: ...
      def coordinate_application(
          self,
          request: dict[str, Any],
          result: dict[str, Any],
      ) -> ApplicationResult: ...
  ```
- **Consumes**: `ExecutionRequest` dict, `ExecutionResult` dict (com veredito `ACCEPT`).
- **Produces**: `ApplicationResult` validado contra schema.
- **Dependencies**: Tasks 25, 26, 32.
- **Non-goals**: Não modifica `OrchestratorStateSelector`; não avança estágios de jobs; não cria pull requests.
- **TDD Steps**:
  - [ ] Step 33.1: Criar teste falhando `tests/agents/test_application_result.py` validando conformidade de `ApplicationResult` com `application-result.schema.json`.
  - [ ] Step 33.2: Implementar `schemas/application-result.schema.json` e `scripts/agents/application_result.py`.
  - [ ] Step 33.3: Criar teste falhando `tests/agents/test_application_coordinator.py` cobrindo o fluxo: resultado ACCEPT $\rightarrow$ ChangeSet $\rightarrow$ Policy $\rightarrow$ Applier $\rightarrow$ ApplicationResult (`APPLIED`).
  - [ ] Step 33.4: Criar teste falhando cobrindo escalação para `HUMAN_REVIEW` quando a política rejeita auto-aplicação.
  - [ ] Step 33.5: Implementar `scripts/agents/application_coordinator.py`.
- **Exact Tests**: `pytest tests/agents/test_application_result.py tests/agents/test_application_coordinator.py -v`.
- **Exact Commands**: `python -m pytest tests/agents/test_application_result.py tests/agents/test_application_coordinator.py -q`.
- **Expected RED**: `ImportError: cannot import name 'ApplicationCoordinator'`.
- **Minimal Implementation**: Integrar builder, policy e applier produzindo dataclass tipada e validando contra JSON schema.
- **Expected GREEN**: Ambos os arquivos de teste passam 100%.
- **Regression Gates**: `python -m pytest tests/agents -q`.
- **Commit Message**: `feat: implement application result schema and coordinator`
- **Stop Condition**: Testes do coordinator e schema 100% verdes.

---

### Task 34 — V2.1 End-to-End Integration & CI Gates

- **Goal**: Implementar suite de testes de integração ponta a ponta hermética cobrindo o pipeline V2 $\rightarrow$ V2.1 completo dentro de ambiente isolado `tmp_path`, testando cenários felizes, conflitos, violações de segurança e rollback, e conectar a suite aos gates de qualidade.
- **Files**:
  - `tests/agents/test_persistence_pipeline_e2e.py`
- **Interfaces**:
  Testes de integração end-to-end conectando `ExecutionCoordinator` (com `FakeExecutionAdapter`) ao `ApplicationCoordinator`.
- **Consumes**: Cenários de teste representativos de agentes especialistas (`source-agent`, `extraction-agent`).
- **Produces**: Asserções determinísticas de aplicação física, reversão e integridade de repositório.
- **Dependencies**: Todas as Tasks 25 a 33.
- **Non-goals**: Não usa tokens, chaves de API nem chamadas externas de rede; não toca no repositório Git real.
- **TDD Steps**:
  - [ ] Step 34.1: Criar fixture de repositório hermético em `tmp_path` simulando estrutura do Daemon Tools (`data/text/`, `data/structured/`, etc.).
  - [ ] Step 34.2: Implementar teste E2E de sucesso: Execution Request $\rightarrow$ Fake Execution $\rightarrow$ Validator (ACCEPT) $\rightarrow$ ChangeSetBuilder $\rightarrow$ Policy $\rightarrow$ Staging $\rightarrow$ Apply $\rightarrow$ Arquivo físico criado/atualizado com sucesso no `tmp_path` e `status = "APPLIED"`.
  - [ ] Step 34.3: Implementar teste E2E de caminho protegido: proposta para `scripts/agents/foo.py` $\rightarrow$ `status = "HUMAN_REVIEW"` (`ERR_PROTECTED_PATH`), zero mutações físicas.
  - [ ] Step 34.4: Implementar teste E2E de caminho fora de allowlist $\rightarrow$ `status = "HUMAN_REVIEW"` (`ERR_NON_ALLOWLISTED_PATH`).
  - [ ] Step 34.5: Implementar teste E2E de escape hard-blocked (`.git/`, UNC, ADS) $\rightarrow$ `status = "BLOCKED"` (`ERR_HARD_BLOCKED_PATH`).
  - [ ] Step 34.6: Implementar teste E2E de TOCTOU conflict: arquivo alterado concorrentemente logo antes do commit $\rightarrow$ `status = "HUMAN_REVIEW"` (`ERR_STALE_BASE`), zero mutações.
  - [ ] Step 34.7: Implementar teste E2E de falha parcial durante commit com rollback compensatório bem-sucedido $\rightarrow$ `status = "ROLLED_BACK"`, disco restaurado ao estado inicial.
  - [ ] Step 34.8: Implementar teste E2E de mutação concorrente durante rollback $\rightarrow$ `status = "ROLLBACK_FAILED"` com journal e backups preservados em disco para inspeção.
  - [ ] Step 34.9: Executar suíte completa de testes e scripts de validação para confirmar conformidade total.
- **Exact Tests**: `pytest tests/agents/test_persistence_pipeline_e2e.py -v`.
- **Exact Commands**:
  - `python -m pytest tests/agents -q`
  - `python -m pytest -q`
  - `python scripts/validate_data.py`
  - `python scripts/check_book_coverage.py`
  - `node --check docs/assets/app.js`
- **Expected RED**: Testes E2E falhando antes da integração dos componentes.
- **Minimal Implementation**: Conectar o fluxo completo do pipeline garantindo que nenhuma exceção não tratada escape e que todas as saídas sejam schema-valid.
- **Expected GREEN**: Todos os testes E2E e testes de regressão 100% verdes.
- **Regression Gates**: `python -m pytest -q` (459+ testes passando).
- **Commit Message**: `test: add v2.1 persistence pipeline end-to-end integration tests`
- **Stop Condition**: 100% dos testes da V1, V2 e V2.1 passando em ambiente determinístico offline.
