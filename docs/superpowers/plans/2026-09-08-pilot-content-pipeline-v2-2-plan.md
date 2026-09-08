# Daemon Tools V2.2 Pilot Content Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the safe, deterministic V2.2 pilot content pipeline that transports execution through manual bundles, validates all returned artifacts, persists restricted candidate content through V2.1 into an isolated runtime workspace, records trusted human governance evidence, and exposes a local-only navigable/searchable/relational preview.

**Architecture:** A multi-stage pipeline where execution requests are exported as self-contained immutable `ExecutionBundles` with explicit instructions for manual transport. Imported `ResultBundles` are checked by a strict `BundleIntegrityValidator`, evaluated deterministically against legacy data without LLMs, and subjected to hash-bound human review. Approved candidate data is persisted exclusively via the V2.1 `ApplicationCoordinator` into an untracked, runtime-owned `RestrictedPilotWorkspace`, validated by segregated QA dataset gates, and projected to a local-only preview environment without modifying the main Git repository.

**Tech Stack:** Python 3.10+, JSON Schema Draft 2020-12 (jsonschema), pytest, hashlib/pathlib/os, vanilla ES6 JavaScript/HTML5, existing V1/V2/V2.1 agent infrastructure.

**Spec:** `docs/superpowers/specs/2026-09-08-pilot-content-pipeline-v2-2-design.md`
---

## Global Constraints

1. **`RESTRICTED_CONTENT_NEVER_ENTERS_MAIN_WORKTREE`:** Derived content from sources with `rightsStatus in (UNKNOWN, PRIVATE)` or `publicationMode == NOT_PUBLIC` (including the pilot book `animalidade`) must NEVER enter the Git repository working tree (`data/books/`, `data/entities/`, `data/pilot/`, `docs/assets/data/`, etc.).
2. **Single Persistence Engine:** Persistence is performed exclusively via the V2.1 `ApplicationCoordinator` / `ChangeSetApplier`. Zero duplicate disk writing engines.
3. **Restricted Workspace Isolation:** Restricted candidate content lives strictly in `<repository-parent>/.daemon_runtime/workspaces/pilot/<bookId>/repository/`.
4. **Trusted Runtime Root Authority:** All runtime roots (`workspaces/`, `bundles/`, `audit/`, `preview/`) are configured exclusively by trusted local Python runtime configuration. Prompts, LLMs, ExecutionResults, ResultBundles, and ChangeSets have zero authority to specify or alter roots.
5. **Pre-Existing Source Custody:** The source document `Livros/word/feito/animalidade.docx` is tracked in the baseline Git history (`PRE_EXISTING_SOURCE_CUSTODY_CONDITION`). The pipeline must never create new tracked copies in Git, duplicate sources into `docs/`, or publish the source publicly.
6. **Immutable Bundles:** Once sealed or imported, bundles are strictly read-only. Rework creates a new attempt (`attempt-002`, `attempt-003`); bundles are never modified in-place and automatic retries are prohibited.
7. **Manual Antigravity Bridge:** No automated API network calls, no browser automation, no Puppeteer/Selenium/Playwright. Bundles are transported manually by the operator.
8. **Deterministic Legacy Comparison:** The `LegacyComparator` does not use LLMs and does not interpret semantics. Divergences require human review.
9. **Hash-Bound Human Review:** Human review decisions are cryptographically bound to the SHA-256 hash of the Result Manifest. Any artifact modification invalidates approval (`ERR_REVIEW_HASH_MISMATCH`). The model cannot approve its own results.
10. **Segregated Audit Authority:** The `PilotAuditStore` is owned exclusively by trusted runtime and segregated from content storage. Content ChangeSets cannot write to or alter the audit store.
11. **Two-Tier QA Strategy:** Repository Regression Gates validate that existing canonical data remains 100% green; Restricted Pilot Dataset Gates validate candidate data in the isolated workspace.
12. **Runtime-Only Preview:** Local preview is served via local HTTP server runtime overlay. Zero files are materialized in `docs/` or deployed publicly in V2.2.
13. **Publication Deferred:** `PublishProjector` remains `BLOCKED / DEFERRED`. `GateEngine` retains sole release authority.
14. **Offline Hermetic Testing:** 100% of pipeline infrastructure is testable offline via unit tests and synthetic fixtures without external tokens or network access.
---

## Preflight Special: Source Custody Audit

| Propriedade | Valor Auditado |
|---|---|
| **Source Document** | `Livros/word/feito/animalidade.docx` |
| **Tracked in Git?** | `YES` (`git ls-files` confirma presença) |
| **Ignored in .gitignore?** | `NO` (`git check-ignore` confirma não ignorado) |
| **Present in V2.1 Baseline?** | `YES` (blob `5d29232c68c18b12d7c71f9fc87cbe7c19589f9a` em `multiagent-persistence-v2.1`) |
| **Custody Classification** | `PRE_EXISTING_SOURCE_CUSTODY_CONDITION` |
| **Pilot Book Identity** | `animalidade` |
| **Rights Status** | `rightsStatus = UNKNOWN`, `publicationMode = NOT_PUBLIC` |
| **Pilot Mode** | `LOCAL_RESTRICTED` |
| **Public Release** | `BLOCKED` |
| **Promotion to Main Tree** | `BLOCKED / DEFERRED` |
| **Pipeline Invariant** | Sem novas cópias rastreadas no Git; sem duplicação de fontes em `docs/`; zero publicação de dados restritos. |
---

## Runtime Directory Architecture

```text
<repository-parent>/.daemon_runtime/
├── bundles/
│   ├── outgoing/<bundleId>/        <-- Read-only Execution Bundles gerados pelo runtime
│   ├── incoming/<bundleId>/        <-- Read-only Result Bundles recebidos do operador
│   ├── accepted/<bundleId>/        <-- Bundles aprovados em integridade e validação técnica
│   └── rejected/<bundleId>/        <-- Bundles reprovados em integridade ou rejeitados em revisão
│
├── workspaces/
│   └── pilot/<bookId>/repository/  <-- repository_root para a V2.1 (RestrictedPilotWorkspace)
│       └── data/
│           ├── text/
│           ├── books/
│           ├── entities/
│           └── pilot/
│
├── audit/
│   └── pilot/<bookId>/             <-- Evidências de governança duráveis (PilotAuditStore)
│       ├── transitions.jsonl
│       ├── comparisons/
│       ├── requests/
│       ├── decisions/
│       └── receipts/
│
└── preview/
    └── <bookId>/                   <-- Projeção de preview runtime-only (LocalPreviewProjector)
        ├── index.json
        └── <bookId>.json
```
---

## Proposed File Map

| Path | Mode | Single Responsibility | Primary Interfaces | Owning Task |
|---|---|---|---|---|
| `schemas/execution-bundle.schema.json` | NEW | Schema canônico do pacote de execução de saída | JSON Schema Draft 2020-12 | Task 35 |
| `schemas/result-bundle.schema.json` | NEW | Schema canônico do pacote de resultado de entrada | JSON Schema Draft 2020-12 | Task 35 |
| `scripts/agents/canonical_json.py` | NEW | Serialização canônica JSON e cálculo imutável de SHA-256 | `canonical_json_bytes()`, `sha256_bytes()`, `compute_input_manifest_hash()`, `compute_result_manifest_hash()` | Task 35 |
| `tests/agents/test_canonical_json.py` | NEW | Testes determinísticos de serialização e hashes canônicos | `test_canonical_ordering()`, `test_sha256_stability()`, `test_hash_exclusions()` | Task 35 |
| `tests/agents/test_bundle_schemas.py` | NEW | Testes de conformidade de schemas de bundles | `test_execution_bundle_schema()`, `test_result_bundle_schema()` | Task 35 |
| `schemas/context-manifest.schema.json` | NEW | Schema formal do manifesto de contexto de entrada | JSON Schema Draft 2020-12 | Task 36 |
| `scripts/agents/bundle_exporter.py` | NEW | Exportador de Execution Bundles e instruções para Antigravity | `ExecutionBundleExporter.export_bundle()` | Task 36 |
| `tests/agents/test_bundle_exporter.py` | NEW | Testes para exportação de pacotes e renderização do guia | `test_export_structure()`, `test_instruction_rendering()`, `test_manifest_hash()` | Task 36 |
| `scripts/agents/bundle_importer.py` | NEW | Ingestão e quarentena segura de pacotes de retorno | `ResultBundleImporter.import_from_directory()`, `seal_and_quarantine()` | Task 37 |
| `tests/agents/test_bundle_importer.py` | NEW | Testes para ingestão segura e isolamento de bundles | `test_safe_ingestion()`, `test_invalid_structure()`, `test_staging_move()` | Task 37 |
| `scripts/agents/bundle_integrity_validator.py` | NEW | Validador de integridade, hashes e amarração de identidade | `BundleIntegrityValidator.validate()` | Task 38 |
| `tests/agents/test_bundle_integrity_validator.py` | NEW | Suíte TDD de segurança, integridade e path traversal | `test_hash_mismatch()`, `test_path_traversal()`, `test_orphaned_artifacts()` | Task 38 |
| `scripts/agents/legacy_comparator.py` | NEW | Comparador estrutural determinístico sem uso de LLM | `LegacyComparator.compare_entities()` | Task 39 |
| `tests/agents/test_legacy_comparator.py` | NEW | Testes de comparação mecânica e diagnósticos canônicos | `test_semantic_equivalent()`, `test_semantic_difference()`, `test_no_legacy()` | Task 39 |
| `schemas/pilot-review-request.schema.json` | NEW | Schema canônico da solicitação formal de revisão humana | JSON Schema Draft 2020-12 | Task 40 |
| `schemas/pilot-review-decision.schema.json` | NEW | Schema canônico da decisão humana amarrada a hash | JSON Schema Draft 2020-12 | Task 40 |
| `scripts/agents/pilot_review.py` | NEW | Motor de emissão de requisições e verificação de decisões | `PilotReviewEngine.create_review_request()`, `validate_review_decision()` | Task 40 |
| `tests/agents/test_pilot_review.py` | NEW | Testes de amarrações criptográficas de revisão humana | `test_create_request()`, `test_approve_decision()`, `test_hash_mismatch_fails()` | Task 40 |
| `scripts/agents/pilot_audit_store.py` | NEW | Armazenamento de governança e auditoria segregado | `PilotAuditStore.record_transition()`, `record_review_decision()` | Task 41 |
| `tests/agents/test_pilot_audit_store.py` | NEW | Testes de imutabilidade e segregação de auditoria | `test_record_transitions()`, `test_audit_isolation()`, `test_no_purge_impact()` | Task 41 |
| `scripts/agents/restricted_workspace.py` | NEW | Provedor e layout do workspace isolado em runtime | `RestrictedPilotWorkspace.get_workspace_path()`, `initialize_layout()` | Task 42 |
| `scripts/agents/pilot_persistence_adapter.py` | NEW | Adaptador que instancia V2.1 apontando para o workspace | `PilotPersistenceAdapter.apply_pilot_artifacts()` | Task 42 |
| `tests/agents/test_restricted_workspace.py` | NEW | Testes de isolamento do workspace fora da working tree | `test_workspace_layout()`, `test_same_volume()`, `test_clean_main_tree()` | Task 42 |
| `tests/agents/test_pilot_persistence_adapter.py` | NEW | Testes de execução da V2.1 contra raiz isolada | `test_apply_to_workspace()`, `test_v21_policy_enforced()`, `test_zero_main_mutation()` | Task 42 |
| `scripts/agents/pilot_state_machine.py` | NEW | Máquina de estados formal do ciclo de vida do piloto | `PilotStateMachine.transition()`, `PilotStateMachine.can_transition()` | Task 43 |
| `scripts/agents/pilot_coordinator.py` | NEW | Coordenador de tentativas sequenciais e orquestrador | `PilotCoordinator.initialize_attempt()`, `process_imported_bundle()` | Task 43 |
| `tests/agents/test_pilot_state_machine.py` | NEW | Testes de todas as transições canônicas da máquina | `test_valid_transitions()`, `test_invalid_transition_fails_closed()` | Task 43 |
| `tests/agents/test_pilot_coordinator.py` | NEW | Testes do modelo de tentativas imutáveis (`attempt-N`) | `test_attempt_progression()`, `test_no_retry_overwrite()` | Task 43 |
| `scripts/agents/pilot_qa_validator.py` | NEW | Validador de QA de dataset no workspace restrito | `PilotQAValidator.validate_dataset()` | Task 44 |
| `tests/agents/test_pilot_qa_validator.py` | NEW | Testes determinísticos dos gates de dataset restrito | `test_schema_check()`, `test_provenance_check()`, `test_coverage_check()` | Task 44 |
| `scripts/agents/preview_projector.py` | NEW | Projetor de dados para preview local runtime-only | `LocalPreviewProjector.project_local_preview()` | Task 45 |
| `tests/agents/test_preview_projector.py` | NEW | Testes de isolamento de preview e bloqueio público | `test_project_restricted()`, `test_blocked_public_leak()`, `test_docs_clean()` | Task 45 |
| `scripts/agents/preview_server.py` | NEW | Servidor HTTP de desenvolvimento com overlay de preview | `PreviewServer.run_preview_server()` | Task 46 |
| `docs/assets/app.js` | MODIFY | Suporte a parâmetro dinâmico de preview em desenvolvimento | `load({ previewBookId })` dynamic loader | Task 46 |
| `tests/agents/test_preview_server.py` | NEW | Testes do servidor de preview e overlay de dados | `test_serve_app()`, `test_serve_runtime_preview_data()`, `test_docs_untouched()` | Task 46 |
| `tests/agents/test_pilot_pipeline_e2e.py` | NEW | Suíte hermética integrada ponta a ponta | `test_full_pilot_pipeline_hermetic_success()`, `test_pipeline_rework()` | Task 47 |
| `scripts/agents/prepare_pilot_job.py` | NEW | Preflight e emissor de checkpoint operacional | `PilotJobPreparer.prepare_pilot_environment()` | Task 48 |
| `tests/agents/test_prepare_pilot_job.py` | NEW | Testes do preflight e emissão do checkpoint | `test_preflight_success()`, `test_checkpoint_infrastructure_verified()` | Task 48 |
---

## Failure Taxonomy Mapping

| Código Canônico | Componente Responsável | Teste Responsável | Status Resultante | Ação do Sistema |
|:---|:---|:---|:---|:---|
| `ERR_EXECUTION_BUNDLE_INVALID` | `ExecutionBundleExporter` | `test_bundle_exporter.py` | `BLOCKED` | Aborta exportação |
| `ERR_EXECUTION_BUNDLE_INTEGRITY_FAILED` | `ExecutionBundleExporter` | `test_bundle_exporter.py` | `BLOCKED` | Aborta exportação |
| `ERR_RESULT_BUNDLE_INVALID` | `BundleIntegrityValidator` | `test_bundle_integrity_validator.py` | `VALIDATION_FAILED` | Move para `rejected/` |
| `ERR_RESULT_BUNDLE_INTEGRITY_FAILED` | `BundleIntegrityValidator` | `test_bundle_integrity_validator.py` | `VALIDATION_FAILED` | Move para `rejected/` |
| `ERR_REQUEST_ID_MISMATCH` | `BundleIntegrityValidator` | `test_bundle_integrity_validator.py` | `VALIDATION_FAILED` | Move para `rejected/` |
| `ERR_BUNDLE_ID_MISMATCH` | `BundleIntegrityValidator` | `test_bundle_integrity_validator.py` | `VALIDATION_FAILED` | Move para `rejected/` |
| `ERR_INPUT_MANIFEST_HASH_MISMATCH` | `BundleIntegrityValidator` | `test_bundle_integrity_validator.py` | `VALIDATION_FAILED` | Move para `rejected/` |
| `ERR_ARTIFACT_HASH_MISMATCH` | `BundleIntegrityValidator` | `test_bundle_integrity_validator.py` | `VALIDATION_FAILED` | Move para `rejected/` |
| `ERR_UNEXPECTED_ARTIFACT` | `BundleIntegrityValidator` | `test_bundle_integrity_validator.py` | `VALIDATION_FAILED` | Rejeita bundle corrompido |
| `ERR_MISSING_ARTIFACT` | `BundleIntegrityValidator` | `test_bundle_integrity_validator.py` | `VALIDATION_FAILED` | Rejeita bundle incompleto |
| `ERR_RESULT_CONTRACT_INVALID` | `ExecutionValidator` | `test_bundle_integrity_validator.py` | `VALIDATION_FAILED` | Rejeita resultado não-ACCEPT |
| `ERR_SEMANTIC_DIFFERENCE_REQUIRES_REVIEW` | `LegacyComparator` | `test_legacy_comparator.py` | `NEEDS_HUMAN_REVIEW` | Escalação com relatório comparativo |
| `ERR_REVIEW_REQUIRED` | `PilotCoordinator` | `test_pilot_coordinator.py` | `BLOCKED` | Bloqueia persistência sem aprovação |
| `ERR_REVIEW_REJECTED` | `PilotReviewEngine` | `test_pilot_review.py` | `REJECTED` | Transiciona para `REWORK_REQUIRED` |
| `ERR_REVIEW_HASH_MISMATCH` | `PilotReviewEngine` | `test_pilot_review.py` | `VALIDATION_FAILED` | Invalida aprovação adulterada |
| `ERR_AUDIT_STORE_VIOLATION` | `PilotAuditStore` | `test_pilot_audit_store.py` | `BLOCKED` | Bloqueia operação |
| `ERR_PERSISTENCE_FAILED` | `PilotPersistenceAdapter` | `test_pilot_persistence_adapter.py` | `VALIDATION_FAILED` | Rollback V2.1 + auditoria |
| `ERR_QA_FAILED` | `PilotQAValidator` | `test_pilot_qa_validator.py` | `QA_FAILED` | Transiciona para `REWORK_REQUIRED` |
| `ERR_RESTRICTED_CONTENT_PROJECTION_BLOCKED` | `LocalPreviewProjector` | `test_preview_projector.py` | `BLOCKED` | Bloqueia vazamento em `docs/` |
| `ERR_PREVIEW_PROJECTION_FAILED` | `LocalPreviewProjector` | `test_preview_projector.py` | `BLOCKED` | Falha de projeção de preview |
| `ERR_STATE_TRANSITION_ILLEGAL` | `PilotStateMachine` | `test_pilot_state_machine.py` | `BLOCKED` | Transição inválida aborta |
---

## State Transition Table

| De (Current State) | Evento Disparador | Para (Target State) | Permitido? | Efeito de Auditoria no `PilotAuditStore` |
|:---|:---|:---|:---:|:---|
| `READY_TO_EXPORT` | `export_bundle(attempt_n)` | `WAITING_FOR_RESULT` | SIM | Registra exportação, bundle IDs e hash de entrada |
| `WAITING_FOR_RESULT` | `import_bundle(attempt_n)` | `RESULT_IMPORTED` | SIM | Registra ingestão física e timestamp |
| `RESULT_IMPORTED` | `integrity_failed` | `VALIDATION_FAILED` | SIM | Registra falha de integridade e detalhes do erro |
| `RESULT_IMPORTED` | `integrity_passed` | `NEEDS_HUMAN_REVIEW` | SIM | Registra veredicto de integridade e resultado comparativo |
| `VALIDATION_FAILED` | `request_rework` | `REWORK_REQUIRED` | SIM | Registra encerramento da tentativa por erro técnico |
| `NEEDS_HUMAN_REVIEW` | `human_reject` | `REJECTED` | SIM | Registra decisão humana de rejeição e motivos |
| `REJECTED` | `request_rework` | `REWORK_REQUIRED` | SIM | Registra encerramento da tentativa por deliberação humana |
| `REWORK_REQUIRED` | `prepare_attempt(n+1)` | `READY_TO_EXPORT` | SIM | Registra criação de nova tentativa vinculada ao job |
| `NEEDS_HUMAN_REVIEW` | `human_approve(hash)` | `APPROVED` | SIM | Registra aprovação humana vinculada ao hash exato |
| `APPROVED` | `apply_persistence` | `PERSISTED` | SIM | Registra hash da transação V2.1 e paths no workspace |
| `APPROVED` | `persistence_failed` | `VALIDATION_FAILED` | SIM | Registra falha de aplicação e status de rollback |
| `PERSISTED` | `qa_gates_passed` | `QA_PASS` | SIM | Registra aprovação de schemas, cobertura e grafos |
| `PERSISTED` | `qa_gates_failed` | `QA_FAILED` | SIM | Registra falha nos gates de dataset |
| `QA_FAILED` | `request_rework` | `REWORK_REQUIRED` | SIM | Registra necessidade de rework por inconsistência de dados |
| `QA_PASS` | `project_preview` | `PREVIEW_READY` | SIM | Registra projeção runtime e URL local de preview |
| `PREVIEW_READY` | `validate_navigation` | `PILOT_VALIDATED` | SIM | Registra checklist de navegação e busca como concluído |
| *Qualquer* | *Transição não listada* | *Qualquer* | **NÃO** | Emite `ERR_STATE_TRANSITION_ILLEGAL`, aborta execução |
---

## Tasks de Implementação (Tasks 35–48)

### Task 35: Canonical Hashing & Core Bundle Schemas
- **Objetivo:** Estabelecer a camada de serialização canônica JSON e hashing SHA-256 à prova de variações de formatação e os schemas estruturais para pacotes de execução (`execution-bundle.schema.json`) e de resultado (`result-bundle.schema.json`).
- **Consumes:**
  - `schemas/execution-request.schema.json`
  - `schemas/execution-result.schema.json`
- **Produces:**
  - `schemas/execution-bundle.schema.json`
  - `schemas/result-bundle.schema.json`
  - `scripts/agents/canonical_json.py`
  - `tests/agents/test_canonical_json.py`
  - `tests/agents/test_bundle_schemas.py`
- **Interfaces:**
  - `canonical_json_bytes(payload: dict) -> bytes`
  - `sha256_bytes(data: bytes) -> str`
  - `sha256_file(path: Path) -> str`
  - `compute_input_manifest_hash(context_manifest: dict) -> str` (exclui `createdAt`)
  - `compute_result_manifest_hash(result_manifest: dict) -> str` (exclui campos de self-hash)
  - `derive_execution_bundle_id(book_id: str, stage: str, attempt: int, content_hash: str) -> str`
- **TDD Steps:**
  - [ ] **RED:** Criar testes em `tests/agents/test_canonical_json.py` e `tests/agents/test_bundle_schemas.py` cobrindo ordenação de chaves, separadores compactos `(",", ":")`, exclusão de `createdAt` no hash de entrada, ausência de BOM e validação dos schemas.
  - [ ] Executar: `python -m pytest tests/agents/test_canonical_json.py tests/agents/test_bundle_schemas.py -q` (deve falhar).
  - [ ] **GREEN:** Implementar `schemas/execution-bundle.schema.json`, `schemas/result-bundle.schema.json` e `scripts/agents/canonical_json.py`.
  - [ ] Executar: `python -m pytest tests/agents/test_canonical_json.py tests/agents/test_bundle_schemas.py -q` (deve passar 100%).
  - [ ] Executar regressão: `python -m pytest tests/agents -q`.
  - [ ] Commit: `git commit -m "feat(pilot): implement canonical hashing and bundle schemas"`

---

### Task 36: Execution Bundle Exporter & Manual Antigravity Bridge Instructions
- **Objetivo:** Implementar o empacotador de solicitações de execução que materializa bundles imutáveis de saída contendo `execution-request.json`, `prompt.md`, `output-contract.json`, `context-manifest.json`, subpastas `context/` e `attachments/`, e o guia operacional `ANTIGRAVITY-INSTRUCTIONS.md`.
- **Consumes:**
  - `scripts/agents/canonical_json.py`
  - `schemas/context-manifest.schema.json`
  - `schemas/execution-bundle.schema.json`
- **Produces:**
  - `schemas/context-manifest.schema.json`
  - `scripts/agents/bundle_exporter.py`
  - `tests/agents/test_bundle_exporter.py`
- **Interfaces:**
  - `class ExecutionBundleExporter:`
    - `export_bundle(request: ExecutionRequest, attempt: int, output_base_dir: Path, source_doc: Path | None = None) -> Path`
    - `render_antigravity_instructions(bundle_id: str, request_id: str, contract_name: str) -> str`
- **TDD Steps:**
  - [ ] **RED:** Criar testes em `tests/agents/test_bundle_exporter.py` verificando geração do layout de diretórios, cálculo correto do `inputManifestSha256`, inclusão de `ANTIGRAVITY-INSTRUCTIONS.md` e permissões de somente-leitura pós-exportação.
  - [ ] Executar: `python -m pytest tests/agents/test_bundle_exporter.py -q` (deve falhar).
  - [ ] **GREEN:** Implementar `schemas/context-manifest.schema.json` e `scripts/agents/bundle_exporter.py`.
  - [ ] Executar: `python -m pytest tests/agents/test_bundle_exporter.py -q` (deve passar 100%).
  - [ ] Executar regressão: `python -m pytest tests/agents -q`.
  - [ ] Commit: `git commit -m "feat(pilot): implement execution bundle exporter and instructions"`

---

### Task 37: Result Bundle Importer & Ingestion Hardening
- **Objetivo:** Implementar a fronteira de recepção física dos pacotes retornados pelo operador, validando estrutura básica de arquivos (`execution-result.json`, `result-manifest.json`, pasta `artifacts/`) e organizando o fluxo entre `incoming/`, `accepted/` e `rejected/`.
- **Consumes:**
  - `schemas/result-bundle.schema.json`
  - `scripts/agents/canonical_json.py`
- **Produces:**
  - `scripts/agents/bundle_importer.py`
  - `tests/agents/test_bundle_importer.py`
- **Interfaces:**
  - `@dataclass(frozen=True) class ResultBundleEnvelope:`
    - `bundle_id: str`, `bundle_dir: Path`, `result_manifest_path: Path`, `execution_result_path: Path`, `artifacts_dir: Path`
  - `class ResultBundleImporter:`
    - `import_from_directory(incoming_dir: Path) -> ResultBundleEnvelope`
    - `seal_and_quarantine(bundle_dir: Path, rejected_dir: Path, reason: str) -> Path`
    - `promote_to_accepted(bundle_dir: Path, accepted_dir: Path) -> Path`
- **TDD Steps:**
  - [ ] **RED:** Criar testes em `tests/agents/test_bundle_importer.py` para ingestão bem-sucedida, detecção de arquivos faltantes, isolamento em `rejected/` diante de anomalias estruturais e imutabilidade dos artefatos.
  - [ ] Executar: `python -m pytest tests/agents/test_bundle_importer.py -q` (deve falhar).
  - [ ] **GREEN:** Implementar `scripts/agents/bundle_importer.py`.
  - [ ] Executar: `python -m pytest tests/agents/test_bundle_importer.py -q` (deve passar 100%).
  - [ ] Executar regressão: `python -m pytest tests/agents -q`.
  - [ ] Commit: `git commit -m "feat(pilot): implement result bundle importer and staging layout"`

---

### Task 38: Bundle Integrity Validator & Cryptographic Binding
- **Objetivo:** Implementar o validador de integridade e segurança de pacotes, garantindo casamento estrito entre saída e retorno, verificação byte-a-byte de artefatos físicos, e proteção rigorosa contra path traversal, nomes de dispositivos reservados e symlinks.
- **Consumes:**
  - `scripts/agents/bundle_importer.py`
  - `scripts/agents/canonical_json.py`
  - `schemas/result-bundle.schema.json`
- **Produces:**
  - `scripts/agents/bundle_integrity_validator.py`
  - `tests/agents/test_bundle_integrity_validator.py`
- **Interfaces:**
  - `@dataclass(frozen=True) class IntegrityVerdict:`
    - `is_valid: bool`, `errors: list[str]`, `result_manifest_sha256: str`, `artifact_hashes: dict[str, str]`
  - `class BundleIntegrityValidator:`
    - `validate(envelope: ResultBundleEnvelope, expected_request_id: str, expected_bundle_id: str, expected_input_manifest_hash: str) -> IntegrityVerdict`
- **TDD Steps:**
  - [ ] **RED:** Criar testes abrangentes em `tests/agents/test_bundle_integrity_validator.py` cobrindo: `ERR_REQUEST_ID_MISMATCH`, `ERR_BUNDLE_ID_MISMATCH`, `ERR_INPUT_MANIFEST_HASH_MISMATCH`, `ERR_ARTIFACT_HASH_MISMATCH`, artefatos órfãos, artefatos faltantes, caracteres proibidos (`..`, `:`, drive letters, `CON`, `NUL`), e limites de tamanho (50MB por arquivo, 200MB por bundle).
  - [ ] Executar: `python -m pytest tests/agents/test_bundle_integrity_validator.py -q` (deve falhar).
  - [ ] **GREEN:** Implementar `scripts/agents/bundle_integrity_validator.py`.
  - [ ] Executar: `python -m pytest tests/agents/test_bundle_integrity_validator.py -q` (deve passar 100%).
  - [ ] Executar regressão: `python -m pytest tests/agents -q`.
  - [ ] Commit: `git commit -m "feat(pilot): implement bundle integrity validator and binding"`

---

### Task 39: Deterministic Legacy Comparator (No-LLM)
- **Objetivo:** Implementar o comparador estrutural determinístico entre entidades extraídas do livro e bases legadas de referência existentes, gerando diagnósticos objetivos e precisos sem nenhuma interpretação por LLM.
- **Consumes:**
  - `scripts/agents/canonical_json.py`
- **Produces:**
  - `scripts/agents/legacy_comparator.py`
  - `tests/agents/test_legacy_comparator.py`
- **Interfaces:**
  - `@dataclass(frozen=True) class LegacyDiscrepancy:`
    - `entity_id: str`, `field_path: str`, `extracted_value: Any`, `legacy_value: Any`, `source_citation: str`
  - `@dataclass(frozen=True) class LegacyComparisonResult:`
    - `verdict: str` (`SEMANTIC_EQUIVALENT` | `STRUCTURAL_DIFFERENCE_ONLY` | `SEMANTIC_DIFFERENCE` | `NO_LEGACY_REFERENCE`),
    - `equivalent_count: int`, `structural_diff_count: int`, `semantic_diff_count: int`, `new_entities_count: int`,
    - `discrepancies: list[LegacyDiscrepancy]`
  - `class LegacyComparator:`
    - `compare_entities(extracted_entities: list[dict], legacy_entities: list[dict]) -> LegacyComparisonResult`
- **TDD Steps:**
  - [ ] **RED:** Criar testes em `tests/agents/test_legacy_comparator.py` validando: equivalência canônica determinística (mesmos IDs, valores normalizados, atributos e relações), diferenças estruturais (adaptações a novos schemas), diferenças de valor mecânico (gera `SEMANTIC_DIFFERENCE` e escala para review) e novas entidades (`NO_LEGACY_REFERENCE`).
  - [ ] Executar: `python -m pytest tests/agents/test_legacy_comparator.py -q` (deve falhar).
  - [ ] **GREEN:** Implementar `scripts/agents/legacy_comparator.py`.
  - [ ] Executar: `python -m pytest tests/agents/test_legacy_comparator.py -q` (deve passar 100%).
  - [ ] Executar regressão: `python -m pytest tests/agents -q`.
  - [ ] Commit: `git commit -m "feat(pilot): implement deterministic legacy comparator"`

---

### Task 40: Pilot Review Request & Decision Engine
- **Objetivo:** Implementar os contratos formais e motor de validação da revisão humana, separando estritamente a solicitação do sistema (`PilotReviewRequest`) da deliberação humana (`PilotReviewDecision`), com amarração criptográfica via hash SHA-256 ao manifesto do pacote.
- **Consumes:**
  - `scripts/agents/canonical_json.py`
  - `scripts/agents/legacy_comparator.py`
- **Produces:**
  - `schemas/pilot-review-request.schema.json`
  - `schemas/pilot-review-decision.schema.json`
  - `scripts/agents/pilot_review.py`
  - `tests/agents/test_pilot_review.py`
- **Interfaces:**
  - `class PilotReviewEngine:`
    - `create_review_request(job_id: str, attempt: int, request_id: str, bundle_id: str, result_manifest_hash: str, comparison: LegacyComparisonResult) -> dict`
    - `validate_review_decision(decision: dict, request: dict, current_result_manifest_hash: str) -> tuple[bool, str]`
- **TDD Steps:**
  - [ ] **RED:** Criar testes em `tests/agents/test_pilot_review.py` verificando validação contra schemas JSON, aprovação válida vinculada ao hash exato, rejeição de decisões adulteradas (`ERR_REVIEW_HASH_MISMATCH`), e bloqueio de deliberações geradas pelo próprio modelo.
  - [ ] Executar: `python -m pytest tests/agents/test_pilot_review.py -q` (deve falhar).
  - [ ] **GREEN:** Implementar schemas e `scripts/agents/pilot_review.py`.
  - [ ] Executar: `python -m pytest tests/agents/test_pilot_review.py -q` (deve passar 100%).
  - [ ] Executar regressão: `python -m pytest tests/agents -q`.
  - [ ] Commit: `git commit -m "feat(pilot): implement pilot review schemas and validation engine"`

---

### Task 41: Segregated Pilot Audit Store & Governance Ledger
- **Objetivo:** Implementar o armazenamento durável e segregado de evidências de governança em `<repository-parent>/.daemon_runtime/audit/pilot/<bookId>/`, garantindo imutabilidade de registros e separação total de autoridade contra ChangeSets e motor de conteúdo.
- **Consumes:**
  - `scripts/agents/canonical_json.py`
- **Produces:**
  - `scripts/agents/pilot_audit_store.py`
  - `tests/agents/test_pilot_audit_store.py`
- **Interfaces:**
  - `class PilotAuditStore:`
    - `record_transition(book_id: str, from_state: str, event: str, to_state: str, details: dict) -> None`
    - `record_review_request(book_id: str, request_data: dict) -> Path`
    - `record_review_decision(book_id: str, decision_data: dict) -> Path`
    - `record_persistence_receipt(book_id: str, receipt_data: dict) -> Path`
    - `get_audit_history(book_id: str) -> list[dict]`
- **TDD Steps:**
  - [ ] **RED:** Criar testes em `tests/agents/test_pilot_audit_store.py` validando gravação em append-only (`transitions.jsonl`), persistência segura de decisões e requisições, preservação dos dados mesmo sob expurgo de bundles e prevenção contra tentativas de escrita via ChangeSet.
  - [ ] Executar: `python -m pytest tests/agents/test_pilot_audit_store.py -q` (deve falhar).
  - [ ] **GREEN:** Implementar `scripts/agents/pilot_audit_store.py`.
  - [ ] Executar: `python -m pytest tests/agents/test_pilot_audit_store.py -q` (deve passar 100%).
  - [ ] Executar regressão: `python -m pytest tests/agents -q`.
  - [ ] Commit: `git commit -m "feat(pilot): implement segregated pilot audit store"`

---

### Task 42: Restricted Pilot Workspace & V2.1 Application Adapter
- **Objetivo:** Implementar o provedor de workspace isolado (`RestrictedPilotWorkspace`) e o adaptador de persistência que inicializa a V2.1 (`ApplicationRuntimeConfig.create(repository_root=...)`) apontando para a raiz de runtime, garantindo que nenhum arquivo de `animalidade` seja escrito na working tree principal.
- **Consumes:**
  - `scripts/agents/application_runtime.py` (V2.1)
  - `scripts/agents/application_coordinator.py` (V2.1)
  - `scripts/agents/change_set.py` (V2.1)
- **Produces:**
  - `scripts/agents/restricted_workspace.py`
  - `scripts/agents/pilot_persistence_adapter.py`
  - `tests/agents/test_restricted_workspace.py`
  - `tests/agents/test_pilot_persistence_adapter.py`
- **Interfaces:**
  - `class RestrictedPilotWorkspace:`
    - `get_workspace_path(runtime_root: Path, book_id: str) -> Path`
    - `initialize_layout(workspace_root: Path) -> None`
  - `class PilotPersistenceAdapter:`
    - `apply_pilot_artifacts(workspace_root: Path, staging_root: Path, proposed_artifacts: list[dict], review_decision: dict) -> ApplicationResult`
- **TDD Steps:**
  - [ ] **RED:** Criar testes em `tests/agents/test_restricted_workspace.py` e `tests/agents/test_pilot_persistence_adapter.py` comprovando: persistência exclusiva no workspace isolado, integridade de todas as garantias da V2.1 (TOCTOU, `open(xb)`, atomicidade, rollback), e assert de que a pasta `data/pilot/` da working tree principal permanece 100% inalterada.
  - [ ] Executar: `python -m pytest tests/agents/test_restricted_workspace.py tests/agents/test_pilot_persistence_adapter.py -q` (deve falhar).
  - [ ] **GREEN:** Implementar `scripts/agents/restricted_workspace.py` e `scripts/agents/pilot_persistence_adapter.py`.
  - [ ] Executar: `python -m pytest tests/agents/test_restricted_workspace.py tests/agents/test_pilot_persistence_adapter.py -q` (deve passar 100%).
  - [ ] Executar regressão: `python -m pytest tests/agents -q`.
  - [ ] Commit: `git commit -m "feat(pilot): implement restricted workspace and v2.1 persistence adapter"`

---

### Task 43: Pilot State Machine & Attempt Lifecycle Coordinator
- **Objetivo:** Implementar o motor formal da máquina de estados do piloto e o coordenador de tentativas sequenciais imutáveis (`attempt-001`, `attempt-002`), impondo parada imediata diante de erros e impossibilidade de sobreposição de tentativas.
- **Consumes:**
  - `scripts/agents/pilot_audit_store.py`
  - `scripts/agents/bundle_exporter.py`
  - `scripts/agents/bundle_importer.py`
  - `scripts/agents/bundle_integrity_validator.py`
  - `scripts/agents/pilot_review.py`
  - `scripts/agents/pilot_persistence_adapter.py`
- **Produces:**
  - `scripts/agents/pilot_state_machine.py`
  - `scripts/agents/pilot_coordinator.py`
  - `tests/agents/test_pilot_state_machine.py`
  - `tests/agents/test_pilot_coordinator.py`
- **Interfaces:**
  - `class PilotStateMachine:`
    - `transition(current_state: str, event: str) -> str`
    - `can_transition(current_state: str, event: str) -> bool`
  - `class PilotCoordinator:`
    - `initialize_attempt(job_id: str, book_id: str, stage: str, attempt_num: int) -> dict`
    - `process_imported_bundle(envelope: ResultBundleEnvelope) -> dict`
    - `submit_human_decision(decision: dict) -> dict`
- **TDD Steps:**
  - [ ] **RED:** Criar testes em `tests/agents/test_pilot_state_machine.py` e `tests/agents/test_pilot_coordinator.py` testando cada transição válida da tabela canônica, rejeição com `ERR_STATE_TRANSITION_ILLEGAL` para transições proibidas, e criação estrita de nova tentativa ao invés de retry in-place.
  - [ ] Executar: `python -m pytest tests/agents/test_pilot_state_machine.py tests/agents/test_pilot_coordinator.py -q` (deve falhar).
  - [ ] **GREEN:** Implementar `scripts/agents/pilot_state_machine.py` e `scripts/agents/pilot_coordinator.py`.
  - [ ] Executar: `python -m pytest tests/agents/test_pilot_state_machine.py tests/agents/test_pilot_coordinator.py -q` (deve passar 100%).
  - [ ] Executar regressão: `python -m pytest tests/agents -q`.
  - [ ] Commit: `git commit -m "feat(pilot): implement pilot state machine and attempt coordinator"`

---

### Task 44: Restricted Pilot Dataset QA Gates
- **Objetivo:** Implementar a suíte determinística de validação de qualidade voltada especificamente para o `RestrictedPilotWorkspace`, auditando conformidade com schemas, proveniência completa (fonte e página em cada entidade), cobertura integral de páginas e integridade relacional.
- **Consumes:**
  - `scripts/agents/restricted_workspace.py`
  - `schemas/entity.schema.json`
  - `schemas/relation.schema.json`
- **Produces:**
  - `scripts/agents/pilot_qa_validator.py`
  - `tests/agents/test_pilot_qa_validator.py`
- **Interfaces:**
  - `@dataclass(frozen=True) class DatasetQAVerdict:`
    - `passed: bool`, `errors: list[str]`, `pages_covered: set[int]`, `total_pages: int`, `entity_count: int`, `relation_count: int`
  - `class PilotQAValidator:`
    - `validate_dataset(workspace_root: Path, book_id: str, expected_pages: int) -> DatasetQAVerdict`
- **TDD Steps:**
  - [ ] **RED:** Criar testes em `tests/agents/test_pilot_qa_validator.py` testando aprovação de dataset íntegro, falha diante de página ausente, falha diante de entidade sem fonte/página e falha diante de relação quebrada.
  - [ ] Executar: `python -m pytest tests/agents/test_pilot_qa_validator.py -q` (deve falhar).
  - [ ] **GREEN:** Implementar `scripts/agents/pilot_qa_validator.py`.
  - [ ] Executar: `python -m pytest tests/agents/test_pilot_qa_validator.py -q` (deve passar 100%).
  - [ ] Executar regressão: `python -m pytest tests/agents -q`.
  - [ ] Commit: `git commit -m "feat(pilot): implement restricted pilot dataset qa gates"`

---

### Task 45: Local Preview Projector & Runtime Data Isolation
- **Objetivo:** Implementar o projetor de dados para preview local, lendo os dados persistidos no `RestrictedPilotWorkspace` e gerando os arquivos de projeção exclusivamente em `<repository-parent>/.daemon_runtime/preview/<bookId>/`, com bloqueio absoluto de qualquer projeção pública para conteúdos `UNKNOWN` / `NOT_PUBLIC`.
- **Consumes:**
  - `scripts/agents/restricted_workspace.py`
  - `scripts/agents/canonical_json.py`
- **Produces:**
  - `scripts/agents/preview_projector.py`
  - `tests/agents/test_preview_projector.py`
- **Interfaces:**
  - `class LocalPreviewProjector:`
    - `project_local_preview(workspace_root: Path, preview_root: Path, book_id: str, rights_status: str, publication_mode: str) -> Path`
- **TDD Steps:**
  - [ ] **RED:** Criar testes em `tests/agents/test_preview_projector.py` verificando projeção válida no runtime, formatação do `index.json` local, e emissão de `ERR_RESTRICTED_CONTENT_PROJECTION_BLOCKED` se o caminho de destino for dentro de `docs/` ou repositório rastreado.
  - [ ] Executar: `python -m pytest tests/agents/test_preview_projector.py -q` (deve falhar).
  - [ ] **GREEN:** Implementar `scripts/agents/preview_projector.py`.
  - [ ] Executar: `python -m pytest tests/agents/test_preview_projector.py -q` (deve passar 100%).
  - [ ] Executar regressão: `python -m pytest tests/agents -q`.
  - [ ] Commit: `git commit -m "feat(pilot): implement local preview projector and rights guard"`

---

### Task 46: Frontend Runtime Preview Integration (Non-destructive local loader)
- **Objetivo:** Implementar o servidor local HTTP de desenvolvimento com rota de overlay para dados de preview e ajustar pontualmente `docs/assets/app.js` para aceitar parâmetro de preview dinâmico sem alterar ou escrever nenhum arquivo em `docs/assets/data/`.
- **Consumes:**
  - `scripts/agents/preview_projector.py`
  - `docs/assets/app.js`
  - `docs/index.html`
- **Produces:**
  - `scripts/agents/preview_server.py`
  - `docs/assets/app.js` (MODIFIED)
  - `tests/agents/test_preview_server.py`
- **Interfaces:**
  - `class PreviewServer:`
    - `run_preview_server(preview_root: Path, port: int = 8080) -> None`
  - Frontend contract:
    - URL: `http://localhost:8080/?preview=animalidade` carrega dados runtime sem tocar `docs/assets/data/pilot/`.
- **TDD Steps:**
  - [ ] **RED:** Criar testes em `tests/agents/test_preview_server.py` testando que o servidor entrega os arquivos estáticos de `docs/` e intercepta requests de dados direcionando para a pasta runtime `<runtime>/preview/animalidade/`.
  - [ ] Executar: `python -m pytest tests/agents/test_preview_server.py -q` (deve falhar).
  - [ ] **GREEN:** Implementar `scripts/agents/preview_server.py` e modificar minimamente `docs/assets/app.js` para suporte a preview sem quebrar o baseline.
  - [ ] Executar: `python -m pytest tests/agents/test_preview_server.py -q` (deve passar 100%).
  - [ ] Executar validação de sintaxe JS: `node --check docs/assets/app.js`.
  - [ ] Executar regressão: `python -m pytest tests/agents -q`.
  - [ ] Commit: `git commit -m "feat(pilot): implement preview server and non-destructive frontend loader"`

---

### Task 47: Hermetic End-to-End Pipeline Integration & Regression Suite
- **Objetivo:** Construir a suíte hermética completa E2E integrando todos os componentes da V2.2, simulando a jornada ponta a ponta com fixtures sintéticas do livro piloto (13 páginas de regras, criaturas e rituais), validando fluxos felizes e caminhos de erro/rework.
- **Consumes:**
  - Todos os componentes criados nas Tasks 35 a 46.
- **Produces:**
  - `tests/agents/test_pilot_pipeline_e2e.py`
- **Interfaces:**
  - `test_full_pilot_pipeline_hermetic_success()`
  - `test_pilot_pipeline_integrity_tamper_rejection()`
  - `test_pilot_pipeline_human_rejection_and_rework()`
  - `test_main_worktree_remains_strictly_clean_after_persistence()`
- **TDD Steps:**
  - [ ] **RED:** Implementar testes ponta a ponta em `tests/agents/test_pilot_pipeline_e2e.py` exercitando: Export -> Import -> Integrity Validator -> Legacy Comparator -> Review Request -> Review Decision -> Restricted Workspace Persistence -> QA Gates -> Preview Projection -> Invariant check (main worktree clean).
  - [ ] Executar: `python -m pytest tests/agents/test_pilot_pipeline_e2e.py -q` (deve falhar).
  - [ ] **GREEN:** Ajustar eventuais arestas de integração até que 100% dos cenários E2E passem hermeticamente offline.
  - [ ] Executar: `python -m pytest tests/agents/test_pilot_pipeline_e2e.py -q` (deve passar 100%).
  - [ ] Executar suite completa: `python -m pytest -q`.
  - [ ] Commit: `git commit -m "test(pilot): add hermetic e2e pipeline integration suite"`

---

### Task 48: Operational Pilot Preparation & `INFRASTRUCTURE_VERIFIED` Checkpoint
- **Objetivo:** Implementar o script de preparação do job piloto real de `animalidade`, validando a custódia da fonte (`Livros/word/feito/animalidade.docx`), pré-requisitos de runtime e emitindo formalmente o checkpoint de verificação da infraestrutura antes de qualquer geração de bundle real.
- **Consumes:**
  - `scripts/agents/pilot_coordinator.py`
  - `Livros/word/feito/animalidade.docx`
- **Produces:**
  - `scripts/agents/prepare_pilot_job.py`
  - `tests/agents/test_prepare_pilot_job.py`
- **Interfaces:**
  - `class PilotJobPreparer:`
    - `verify_source_custody(book_id: str) -> SourceCustodyReport`
    - `prepare_pilot_environment(book_id: str) -> PilotReadinessStatus`
    - `emit_infrastructure_verified_checkpoint() -> str`
- **TDD Steps:**
  - [ ] **RED:** Criar testes em `tests/agents/test_prepare_pilot_job.py` verificando detecção correta da custódia de `animalidade`, inicialização das pastas runtime e validação de prontidão.
  - [ ] Executar: `python -m pytest tests/agents/test_prepare_pilot_job.py -q` (deve falhar).
  - [ ] **GREEN:** Implementar `scripts/agents/prepare_pilot_job.py`.
  - [ ] Executar: `python -m pytest tests/agents/test_prepare_pilot_job.py -q` (deve passar 100%).
  - [ ] Executar suite completa e validadores.
  - [ ] Commit: `git commit -m "feat(pilot): implement pilot job preparation and readiness checkpoint"`

---

## Checkpoint Operacional: `INFRASTRUCTURE_VERIFIED`

> [!IMPORTANT]
> A conclusão bem-sucedida das **Tasks 35 a 48** atinge formalmente o checkpoint:
> ```text
> INFRASTRUCTURE_VERIFIED
> ```
> NENHUM bundle real do livro `animalidade` será exportado e NENHUM dado piloto será processado antes da verificação e validação formal desse checkpoint por aprovação humana.

---

## Self-Review de Conformidade com a Especificação

- [x] **Spec Coverage:** Todas as seções e requisitos da especificação V2.2 (`docs/superpowers/specs/2026-09-08-pilot-content-pipeline-v2-2-design.md`) foram cobertos nas Tasks 35–48.
- [x] **No Placeholders:** Nenhum `TODO`, `TBD` ou descrição genérica foi utilizada. Todas as interfaces, schemas e testes possuem assinaturas e responsabilidades explícitas.
- [x] **Restricted Invariant:** `RESTRICTED_CONTENT_NEVER_ENTERS_MAIN_WORKTREE` protegido arquiteturalmente e verificado em testes de integração (Task 42 e Task 47).
- [x] **V2.1 Reuse:** Reuso total e exclusivo do `ApplicationCoordinator`, `ChangeSetBuilder`, `StagingManager` e primitivas atômicas da V2.1 sem código duplicado (Task 42).
- [x] **Segregated Audit:** `PilotAuditStore` de propriedade exclusiva do runtime confiável, segregated from content (Task 41).
- [x] **Manual Antigravity Bridge:** Geração de `ANTIGRAVITY-INSTRUCTIONS.md` sem automação de API de terceiros ou browser (Task 36).
- [x] **Frontend / Publication Isolation:** `PublishProjector` permanece deferido; preview local opera através de servidor runtime overlay sem escrita em `docs/` (Task 45 e Task 46).
- [x] **Deterministic Legacy Comparator:** Comparação estrutural estrita sem uso de LLM (Task 39).
- [x] **Pre-existing Source Custody:** Condição de `Livros/word/feito/animalidade.docx` formalizada como `PRE_EXISTING_SOURCE_CUSTODY_CONDITION` sem novas cópias no Git (Preflight e Task 48).
