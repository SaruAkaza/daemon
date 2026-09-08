# Daemon Tools — Version 2.1 Design Specification
# Persistence & Application Layer (Safe Filesystem Mutation)

- **Status**: Approved Specification / Ready for Implementation Plan
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

A **Version 2.1 (Persistence / Application Layer)** define a fronteira segura, determinística e transacional que traduz um resultado de execução aceito (`verdict == "ACCEPT"`) em mutações reais no sistema de arquivos do repositório.

### Cláusulas Pétreas de Segurança da V2.1:
1. **LLM output never has direct filesystem write authority.** (A saída de modelos de linguagem é sempre tratada como proposta não confiável em memória).
2. **`ACCEPT` authorizes evaluation for application; it does not bypass application policy.** (O veredito de aceitação do validador de execução qualifica a proposta para avaliação de aplicação, mas não autoriza escrita cega).
3. **Allowlist-First Application Authority.** (Por padrão, qualquer mutação exige `HUMAN_REVIEW`. Somente caminhos pertencentes explicitamente a `AutoApplyRoots` são elegíveis para aplicação automática).
4. **Requested write scope never expands application authority.** (A autoridade real de mutação é a interseção estrita: `requested_scope` $\cap$ `AutoApplyRoots` $\cap$ `ApplicationPolicy`).
5. **Every filesystem mutation must pass deterministic preconditions immediately before mutation (TOCTOU Recheck).** (Verificação fail-closed de concorrência otimista via SHA256 base e ausência de arquivo imediatamente antes da primeira mutação física).
6. **No partial ChangeSet application is allowed.** (Semântica all-or-nothing implementada através de pré-validação, staging isolado no mesmo volume, journal transacional e rollback compensatório restrito).
7. **Destructive operations (DELETE, RENAME, MOVE) are strictly forbidden in V2.1.** (Apenas criação exclusiva de novos arquivos e atualização de arquivos existentes são autorizadas para propostas e ChangeSets. Remoção de arquivos é autorizada exclusivamente como rotina interna de compensação/rollback para desarmar um `CREATE` recém-aplicado na mesma transação que falhou).
8. **CREATE operations never overwrite existing targets.** (Criação exclusiva atômica; qualquer conflito aborta a transação e escala para `HUMAN_REVIEW`).
9. **Same-Filesystem Staging Invariant.** (O diretório de staging deve residir no mesmo volume do repositório para garantir atomicidade de renomeação. Se a equivalência de volume não puder ser garantida, a auto-aplicação falha em modo fechado: `AUTO_APPLY` fail-closed).

---

## 2. Escopo: Goals e Non-Goals

### 2.1 Goals (Metas da V2.1)
- **ChangeSet Formal**: Definir modelo estruturado, tipado e imutável de `ChangeSet` e `ChangeOperation`.
- **ChangeSetBuilder Determinístico**: Transformar `ExecutionResult` aceito em manifesto de alterações determinístico.
- **ApplicationPolicy com Allowlist Restritiva**: Implementar política de governança baseada em `AutoApplyRoots`, `ProtectedRoots`, `HardBlockedRoots` e regra default `HUMAN_REVIEW`.
- **Interseção Estrita de Autoridade**: Garantir que `allowedWriteScope` da requisição nunca amplie as raízes elegíveis de auto-aplicação.
- **PreconditionValidator com Proteção TOCTOU**: Validar existência, ausência e hash SHA256 do arquivo base na análise inicial e revalidar imediatamente antes da primeira mutação física.
- **PatchApplier em Memória**: Gerar e validar conteúdo candidato (UTF-8, JSON) sem alterar arquivos vivos.
- **Staging no Mesmo Filesystem Fora da Árvore Versionada**: Gerenciar staging temporário em diretório runtime-owned no mesmo volume de disco dos alvos, fora do controle do LLM e hard-blocked como alvo de mutações.
- **Aplicação All-or-Nothing em 6 Fases**: Executar mutações atômicas individuais com journal transacional como fonte única de autoridade para compensação.
- **Proteção de Criação Exclusiva**: Garantir que `CREATE` nunca sobrescreva arquivos existentes mesmo sob condições de corrida concorrente.
- **Rollback Compensatório Estritamente Delimitado**:
  - Reversão de `CREATE`: Remoção compensatória restrita ao arquivo recém-criado, verificando correspondência exata de hash.
  - Reversão de `UPDATE`: Restauração de snapshot original verificando que o arquivo não foi modificado por processo concorrente externo.
- **ApplicationResult e Journal Forense**: Registrar resultado detalhado com taxonomia clara (`APPLIED`, `NOT_APPLIED`, `ROLLED_BACK`, `ROLLBACK_FAILED`, `HUMAN_REVIEW`, `BLOCKED`).

### 2.2 Non-Goals (Fora do Escopo da V2.1)
- **NÃO** suporta operações destrutivas (`DELETE`, `RENAME`, `MOVE`) pelo usuário, LLM ou ExecutionResult.
- **NÃO** executa commits git automáticos, push remoto ou abertura de Pull Requests.
- **NÃO** implementa concorrência distribuída ou múltiplos escritores concorrentes (assume escritor único controlado).
- **NÃO** faz chamadas a provedores ou LLMs para "resolver conflitos" ou "recuperar falhas".
- **NÃO** substitui arquivos silenciosamente sem verificação de hash base (`expectedBaseSha256`).
- **NÃO** promete primitivas nativas de transação atômica multi-arquivo que o sistema de arquivos não oferece (utiliza semântica all-or-nothing com journal e rollback compensatório).
- **NÃO** degrada silenciosamente para cópia não-atômica entre volumes se o staging estiver em outro filesystem (falha fechado com `ERR_CROSS_VOLUME_STAGING`).
- **NÃO** permite que o modelo ou a ExecutionRequest configurem ou acessem o caminho de staging.
- **NÃO** sobrescreve modificações externas concorrentes durante uma tentativa de rollback.

---

## 3. Política de Governança e Classificação de Diretórios

A segurança do sistema de arquivos na V2.1 adota o princípio de **privilégio mínimo baseado em allowlist**:

$$\text{Default Action} = \text{HUMAN\_REVIEW}$$

Nenhum arquivo é aplicado automaticamente a menos que esteja explicitamente contido em uma raiz autorizada de dados derivados.

```text
                                    Target Path Evaluation
                                              │
                                              ▼
                                 ┌─────────────────────────┐
                                 │   Is HardBlockedRoot?   │ ──(YES)──► BLOCKED (ERR_HARD_BLOCKED_PATH)
                                 │ (.git, traversal, etc.) │
                                 └────────────┬────────────┘
                                              │ (NO)
                                              ▼
                                 ┌─────────────────────────┐
                                 │   Is in ProtectedRoot?  │ ──(YES)──► HUMAN_REVIEW (ERR_PROTECTED_PATH)
                                 │ (scripts, schemas, etc.)│
                                 └────────────┬────────────┘
                                              │ (NO)
                                              ▼
                                 ┌─────────────────────────┐
                                 │   Is in AutoApplyRoots? │ ──(NO)───► HUMAN_REVIEW (ERR_NON_ALLOWLISTED_PATH)
                                 │  (data/text, data/...,) │
                                 └────────────┬────────────┘
                                              │ (YES)
                                              ▼
                                 ┌─────────────────────────┐
                                 │ In allowedWriteScope?   │ ──(NO)───► BLOCKED (ERR_WRITE_SCOPE_VIOLATION)
                                 └────────────┬────────────┘
                                              │ (YES)
                                              ▼
                                     AUTO_APPLY_ELIGIBLE
```

### 3.1 HardBlockedRoots (Rejeição Imediata — `BLOCKED`)
Mutações nestes destinos representam violação grave de segurança e são bloqueadas sem possibilidade de auto-aplicação ou escalação cega:
- `.git/**` (Metadados do repositório Git, hooks, objetos e refs).
- Caminhos contendo path traversal (`..`), caminhos absolutos (`C:\`, `/`), ou prefixos UNC (`\\`).
- Caminhos que apontem para diretórios de staging ou runtime (`.daemon_staging/**`, `.daemon_runtime/**`, etc.).
- Caminhos contendo caracteres nulos (`\0`) ou caracteres ilegais para o sistema operacional.
- Ambientes virtuais e dependências externas (`.venv/**`, `node_modules/**`).

### 3.2 ProtectedRoots (Control-Plane / Source-Sensitive — `HUMAN_REVIEW`)
Arquivos vitais de controle, lógica do sistema, schemas e fontes canônicas. Exigem sempre revisão humana com código `ERR_PROTECTED_PATH`:
- `scripts/**` (Todo código Python, runtime de agentes, scripts de validação como `validate_data.py`).
- `schemas/**` (Todos os schemas JSON formais Draft 2020-12).
- `.github/**` (Workflows de CI/CD e automações de repositório).
- `tests/**` (Suítes de testes unitários, de agentes e de integração).
- `Livros/**` (Acervo original de fontes, PDFs e imagens canônicas — leitura estrita).
- `coordination/**` (Filas de jobs, contratos de livros, handoffs e estado do orquestrador).
- `docs/architecture/**` (Constituição, pipeline e decisões arquiteturais).
- `docs/reference/**` (Regras canônicas de catalogação e data models).
- `docs/superpowers/**` (Especificações técnicas e planos de implementação).
- `docs/agents/**` (Contratos de agentes especialistas).
- `docs/missions/**` (Histórico de missões e runbooks).
- `docs/obsidian/**` (Notas estruturadas da base de conhecimento).
- `docs/index.html`, `docs/assets/**` (Código frontend da aplicação web).
- Arquivos de controle na raiz: `AGENTS.md`, `PROJECT-BRAIN.md`, `README.md`, `CLAUDE.md`, `OCR_CLEANUP_SUMMARY.md`, `requirements*.txt`, `ruff.toml`, `.coveragerc`, `.gitattributes`, `.gitignore`, `.nojekyll`.

### 3.3 AutoApplyRoots (Explicit Allowlist — Dados Derivados do Pipeline)
Somente artefatos derivados e compilados gerados determinística e exclusivamente pelas etapas do pipeline de dados são elegíveis para auto-aplicação:
- `data/text/**` (Texto bruto e limpo extraído dos livros).
- `data/structured/**` (Registros e entidades normalizadas em JSON).
- `data/blocks/**` (Blocos estruturais segmentados).
- `data/segments/**` (Segmentos semânticos classificados).
- `data/entities/**` (Catálogos derivados de entidades).
- `data/index/**` (Índices e sumários gerados).
- `data/books/**` (Metadados de catalogação de livros gerados).
- `data/work/**` (Artefatos intermediários do pipeline de livros).
- `data/editorial/**` (Notas editoriais geradas pelo pipeline).
- `data/pilot/**` (Artefatos do pipeline piloto).
- `data/areas/**` (Classificação de áreas gerada).
- `docs/reports/**` (Relatórios determinísticos de cobertura e auditoria gerados por scripts).

### 3.4 Interseção Estrita de Autoridade
A autoridade de aplicação de uma requisição é determinada exclusivamente pela interseção:

$$\text{EffectiveAutoApplyScope} = \text{requested\_write\_scope} \cap \text{AutoApplyRoots} \cap \text{ApplicationPolicy}$$

- O parâmetro `allowedWriteScope` da `ExecutionRequest` é uma **restrição adicional**, **NUNCA** uma ampliação.
- Se a `ExecutionRequest` solicitar escrita em `scripts/agents/`, essa requisição será classificada como `HUMAN_REVIEW` (`ERR_PROTECTED_PATH`), mesmo que esteja em seu `allowedWriteScope`.
- Se um `ChangeSet` contiver 5 arquivos em `data/text/` e 1 arquivo fora de `AutoApplyRoots`, o `ChangeSet` **inteiro** é escalado para `HUMAN_REVIEW`.

---

## 4. Arquitetura e Fluxo de Execução em 6 Fases

O sistema de arquivos local não oferece suporte a transações ACID multi-arquivo nativas. Por isso, a V2.1 garante a semântica **all-or-nothing** através de um processo determinístico em 6 fases com journal transacional:

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                   V2 Pipeline (In-Memory)                               │
│  OrchestratorSelection → ExecutionRequestBuilder → ContextMaterializer → PromptRenderer  │
│                     → ExecutionAdapter → RepairEngine → ExecutionResultValidator       │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │ (Verdict: ACCEPT)
                                            ▼
                        ┌───────────────────────────────────────┐
                        │ Phase 1: Validate & Build ChangeSet   │
                        │ - ChangeSetBuilder                    │
                        │ - Policy & Allowlist Intersection     │
                        │ - Path safety & scope validation      │
                        └───────────────────┬───────────────────┘
                                            │ (PASS)
                                            ▼
                        ┌───────────────────────────────────────┐
                        │ Phase 2: Construct Candidates         │
                        │ - PatchApplier (In-Memory UTF-8/JSON) │
                        └───────────────────┬───────────────────┘
                                            │
                                            ▼
                        ┌───────────────────────────────────────┐
                        │ Phase 3: Same-Filesystem Staging      │
                        │ - Same volume check (fail-closed)     │
                        │ - Outside tracked repo tree           │
                        │ - Write candidates & verify hashes    │
                        └───────────────────┬───────────────────┘
                                            │
                                            ▼
                        ┌───────────────────────────────────────┐
                        │ Phase 4: TOCTOU Precondition Recheck  │
                        │ - Immediately before first mutation   │
                        │ - UPDATE: current == expectedBaseSha  │
                        │ - CREATE: target still not exists     │
                        └───────────────┬───────────────────────┘
                                 (PASS) │       │ (FAIL: Stale base / Create conflict)
                                        │       ▼
                                        │  Abort: Zero target mutations
                                        │  Clean staging → HUMAN_REVIEW
                                        ▼
                        ┌───────────────────────────────────────┐
                        │ Phase 5: Individual Atomic Operations │
                        │ - Sequential atomic replace / create  │
                        │ - Exclusive CREATE (O_CREAT | O_EXCL) │
                        │ - Pre-mutation backup snapshot        │
                        │ - Active transaction journal logging  │
                        └───────────────┬───────────────────────┘
                                        │
                 ┌──────────────────────┴──────────────────────┐
                 │ (All Succeeded)                             │ (Any Step Failed)
                 ▼                                             ▼
┌─────────────────────────────────┐           ┌─────────────────────────────────┐
│ Success Finalization            │           │ Phase 6: Compensating Rollback  │
│ - Final state verification      │           │ - Journal-driven compensation   │
│ - Cleanup temporary candidates  │           │ - CREATE: Compensating cleanup  │
│ - Status: APPLIED               │           │ - UPDATE: Snapshot restoration  │
└─────────────────────────────────┘           │ - If clean: ROLLED_BACK         │
                                              │ - If external change / fail:    │
                                              │   ROLLBACK_FAILED (BLOCKED)     │
                                              └─────────────────────────────────┘
```

### 4.1 Detalhamento das 6 Fases

#### Fase 1: Validação Estrutural e Construção do ChangeSet
1. Recebe a `ExecutionRequest` e o `ExecutionResult` com veredito `ACCEPT`.
2. Constrói o `ChangeSet` imutável mapeando cada arquivo proposto.
3. Classifica operações:
   - Se o arquivo existe em disco: `UPDATE` com `expected_base_sha256 = sha256(current_disk_bytes)`.
   - Se o arquivo não existe em disco: `CREATE` com `expected_base_sha256 = None`.
4. Executa a primeira validação de políticas:
   - Rejeita operações não permitidas (`DELETE`, `RENAME`, `MOVE`) $\rightarrow$ `BLOCKED` (`ERR_OPERATION_NOT_ALLOWED`).
   - Verifica `HardBlockedRoots` $\rightarrow$ `BLOCKED` (`ERR_HARD_BLOCKED_PATH`).
   - Verifica `ProtectedRoots` $\rightarrow$ `HUMAN_REVIEW` (`ERR_PROTECTED_PATH`).
   - Verifica `AutoApplyRoots` $\rightarrow$ Se fora da allowlist: `HUMAN_REVIEW` (`ERR_NON_ALLOWLISTED_PATH`).
   - Valida `allowedWriteScope` da requisição $\rightarrow$ Se fora do escopo: `BLOCKED` (`ERR_WRITE_SCOPE_VIOLATION`).

#### Fase 2: Construção dos Candidatos em Memória
1. `PatchApplier` valida sintaxe e codificação de cada artefato candidato em memória:
   - Validação estrita de decodificação UTF-8 (sem bytes inválidos).
   - Para arquivos com extensão `.json`: validação de parse sintático JSON.
2. Gera estruturas em memória `CandidateArtifact` prontas para estagiamento.

#### Fase 3: Estagiamento Isolado no Mesmo Filesystem (Same-Volume Staging)
1. **Regra de Invariância de Volume**: O diretório de staging deve residir comprovadamente no **mesmo filesystem / volume** que os alvos do repositório (para garantir que `os.replace` execute uma substituição atômica de inode/diretório sem fallback para cópia entre volumes).
   - Se o caminho de staging estiver em volume diferente ou se a verificação de volume falhar $\rightarrow$ `AUTO_APPLY` falha em modo fechado com código `ERR_CROSS_VOLUME_STAGING` e escala para `HUMAN_REVIEW`.
2. **Localização Segura**: O staging deve residir **fora da árvore rastreada do Git** (ex: diretório derivado localmente no parent ou em `.daemon_runtime/staging/<changeSetId>/` com gitignore estrito e hard-blocked como alvo).
3. O caminho de staging é gerenciado exclusivamente pelo runtime; modelos e requisições não podem configurá-lo, observá-lo ou direcionar mutações para ele.
4. Grava os candidatos no staging e calcula o SHA256 de cada arquivo estagiado (`candidate_sha256`).

#### Fase 4: Revalidação de Pré-condições TOCTOU (Imediatamente Pré-Mutação)
Imediatamente antes de realizar a primeira mutação física no repositório, o `PreconditionValidator` inspeciona o sistema de arquivos ao vivo:
1. Para cada operação `UPDATE`:
   - Confirma que o arquivo existe em disco.
   - Lê os bytes do arquivo em disco e verifica: `sha256(disk_bytes) == expected_base_sha256`.
   - Se o hash divergir $\rightarrow$ Conflito de concorrência detectado (`ERR_STALE_BASE`).
2. Para cada operação `CREATE`:
   - Confirma que o arquivo **ainda não existe** em disco (`os.path.exists(target) == False`).
   - Se o arquivo existir $\rightarrow$ Conflito de criação detectado (`ERR_CREATE_CONFLICT`).
3. Se QUALQUER operação falhar na Fase 4:
   - O ChangeSet é **abortado imediatamente**.
   - **Zero mutações** são realizadas nos alvos finais do repositório.
   - O diretório de staging é limpo.
   - Emite `ApplicationResult` com status `HUMAN_REVIEW` (ou `BLOCKED`) e o código de erro correspondente.

#### Fase 5: Aplicação de Operações Atômicas Individuais
1. Cria subdiretório de backup no staging: `<stagingDir>/backups/`.
2. Para cada operação no `ChangeSet`:
   - Para `UPDATE`: Copia o arquivo atual em disco para o diretório de backups antes da substituição.
   - Registra entrada `PENDING` no `TransactionJournal`.
3. Aplica cada operação individualmente:
   - Para `UPDATE`: Executa substituição atômica via `os.replace(staged_file, target_path)` no mesmo volume.
   - Para `CREATE`: Executa **criação exclusiva atômica** via flags de sistema `os.O_CREAT | os.O_EXCL | os.O_WRONLY` (ou modo `"x"` em Python). Se o arquivo tiver surgido milissegundos antes, a criação falha deterministicamente sem sobrescrever o arquivo existente.
4. Lê o hash pós-aplicação no disco (`observed_post_apply_sha256`) e atualiza o journal para `APPLIED`.
5. Se todas as operações forem concluídas com sucesso:
   - Executa limpeza dos arquivos temporários de staging (conforme Seção 5.4).
   - Emite `ApplicationResult` com status `APPLIED`.

#### Fase 6: Rollback Compensatório Orientado por Journal (Falha Parcial)
Se ocorrer qualquer falha durante a Fase 5 (erro de I/O, falha de permissão, conflito de criação concorrente na operação $K$ de $N$):
1. Interrompe imediatamente novas gravações.
2. O `TransactionJournal` é a **fonte determinística exclusiva de autoridade** para a compensação. O rollback só atua sobre operações com status `APPLIED` registradas naquele `changeSetId`.
3. Para cada operação aplicada anteriormente ($1$ a $K-1$), na ordem inversa:
   - **Para operação `CREATE` (Internal Compensating Cleanup)**:
     - Verifica se o hash atual no disco coincide rigorosamente com o hash gerado pela própria transação (`current_disk_hash == observed_post_apply_sha256`).
     - Se o hash coincidir: remove **exclusivamente** o arquivo criado pela transação (`os.remove(target_path)`).
     - Se o hash NÃO coincidir (o arquivo foi modificado por processo externo após a criação): **NÃO REMOVER**. Marca `rollback_result = SKIPPED_EXTERNAL_MUTATION`, aborta a compensação e define o status como `ROLLBACK_FAILED` $\rightarrow$ `CRITICAL` (`ERR_CRITICAL_ROLLBACK_FAILED`).
   - **Para operação `UPDATE` (Snapshot Restoration)**:
     - Verifica se o hash atual no disco coincide rigorosamente com o hash aplicado pela transação (`current_disk_hash == observed_post_apply_sha256`).
     - Se o hash coincidir: restaura o arquivo original a partir do snapshot em `<stagingDir>/backups/` usando `os.replace`.
     - Se o hash NÃO coincidir (o arquivo foi alterado por processo externo após o replace): **NÃO SOBRESCREVER**. Marca `rollback_result = SKIPPED_EXTERNAL_MUTATION`, aborta a compensação e define o status como `ROLLBACK_FAILED` $\rightarrow$ `CRITICAL` (`ERR_CRITICAL_ROLLBACK_FAILED`).
4. Avalia o resultado da compensação:
   - Se todas as operações aplicadas foram revertidas com 100% de sucesso e integridade confirmada:
     - Status: `ROLLED_BACK`.
     - Código de Erro: `ERR_ATOMIC_COMMIT_FAILED`.
     - Staging de backups é limpo após confirmação dos hashes originais.
     - Ação: Escalação para `HUMAN_REVIEW`.
   - Se qualquer passo de rollback falhar (erro de I/O ou mutação externa concorrente detectada):
     - Status: `ROLLBACK_FAILED`.
     - Código de Erro: `ERR_CRITICAL_ROLLBACK_FAILED`.
     - Severidade: `CRITICAL` $\rightarrow$ `BLOCKED` + `HUMAN_REVIEW`.
     - **Preservação Obrigatória**: O staging, os backups e o journal **NÃO são excluídos**, permanecendo em disco para recuperação forense e manual.
     - `ROLLBACK_FAILED` **nunca** é reportado como uma aplicação limpa.

---

## 5. Modelos de Dados Estruturados

### 5.1 `ChangeOperation` e `ChangeSet`

```python
@dataclass(frozen=True)
class ChangeOperation:
    operation_id: str             # Ex: "OP-001"
    type: str                     # "CREATE" ou "UPDATE" (DELETE/RENAME/MOVE são proibidos)
    target_path: str              # Caminho relativo POSIX normalizado (ex: "data/text/trevas-3-0.txt")
    expected_base_sha256: str | None  # None para CREATE; SHA256 hex de 64 chars para UPDATE
    candidate_content: str        # Conteúdo em texto UTF-8 a ser gravado
    encoding: str = "utf-8"
    format: str = "text"          # "text" ou "json"

@dataclass(frozen=True)
class ChangeSet:
    change_set_id: str            # Ex: "CS-REQ-JOB-TREVAS-001-EXTRACTION-01"
    request_id: str               # Correlação direta com ExecutionRequest
    job_id: str
    book_id: str
    stage: str
    agent: str
    operations: tuple[ChangeOperation, ...]
    metadata: dict[str, Any]
```

### 5.2 `TransactionJournal` (Autoridade Determinística de Compensação)

```python
@dataclass(frozen=True)
class JournalOperationEntry:
    operation_id: str
    type: str                     # "CREATE" ou "UPDATE"
    target_path: str
    original_exists: bool
    expected_base_sha256: str | None
    candidate_sha256: str
    applied_status: str           # "NOT_APPLIED", "APPLIED", "REVERTED", "REVERT_FAILED"
    observed_post_apply_sha256: str | None
    backup_path: str | None
    applied_at: str | None
    reverted_at: str | None
    rollback_attempted: bool
    rollback_result: str | None   # "SUCCESS", "SKIPPED_EXTERNAL_MUTATION", "FAILED_IO"
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
    filesystem_state: str         # "CLEAN_INITIAL", "FULLY_APPLIED", "CLEAN_ROLLED_BACK", "PARTIALLY_MODIFIED_UNCERTAIN"
```

### 5.3 `ApplicationResult` e Taxonomia de Status

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
    status: str                   # "APPLIED", "NOT_APPLIED", "ROLLED_BACK", "ROLLBACK_FAILED", "HUMAN_REVIEW", "BLOCKED"
    applied_operations: tuple[AppliedOperationRecord, ...]
    blocked_operations: tuple[dict[str, Any], ...]
    failure_code: str | None      # Ex: "ERR_STALE_BASE", "ERR_NON_ALLOWLISTED_PATH"
    reasons: tuple[str, ...]
    applied_at: str | None        # ISO 8601 timestamp
    duration_ms: float
    journal: TransactionJournal | None
    metadata: dict[str, Any]
```

#### Tabela Semântica de Status do `ApplicationResult`

| Status | Mutações no Alvo | Integridade do Disco | Ação Subsequente |
|---|---|---|---|
| `APPLIED` | 100% das operações aplicadas com sucesso | Consistente (novo estado) | Prosseguir no pipeline |
| `NOT_APPLIED` | 0 mutações realizadas (abortado na validação ou TOCTOU) | Consistente (estado original) | Escalar ou encerrar |
| `ROLLED_BACK` | Mutações parciais foram 100% revertidas | Consistente (estado original) | `HUMAN_REVIEW` |
| `ROLLBACK_FAILED`| Mutações parciais não puderam ser revertidas | **Inconsistente** | `CRITICAL` $\rightarrow$ `BLOCKED` + `HUMAN_REVIEW` |
| `HUMAN_REVIEW` | 0 mutações automáticas realizadas | Consistente (estado original) | Fila de revisão humana |
| `BLOCKED` | 0 mutações realizadas (violação grave de segurança) | Consistente (estado original) | Rejeição imediata |

### 5.4 Política de Ciclo de Vida e Limpeza de Staging

1. **Quando o status é `APPLIED`**:
   - Os arquivos candidatos e snapshots temporários são removidos do diretório de staging.
   - O journal estruturado é mantido em log/metadados da execução para fins de auditoria.
2. **Quando o status é `ROLLED_BACK`**:
   - O runtime verifica a integridade de todos os hashes originais no disco.
   - Somente após confirmar que o sistema de arquivos retornou 100% ao estado inicial, o diretório de staging é limpo.
3. **Quando o status é `ROLLBACK_FAILED`**:
   - O runtime **NÃO limpa** o diretório de staging, mantendo intactos todos os backups, arquivos candidatos e o journal.
   - O estado do sistema é classificado como `PARTIALLY_MODIFIED_UNCERTAIN` e os artefatos preservados servem de base para resolução manual por operadores humanos.

---

## 6. Taxonomia Completa de Falhas da V2.1

| Código de Erro | Status Resultante | Severidade | Descrição |
|---|---|---|---|
| `ERR_CHANGESET_INVALID` | `BLOCKED` | Alta | Estrutura ou dados do ChangeSet inválidos / corrompidos |
| `ERR_OPERATION_NOT_ALLOWED` | `BLOCKED` | Alta | Tentativa de DELETE, RENAME, MOVE ou operação não suportada |
| `ERR_WRITE_SCOPE_VIOLATION` | `BLOCKED` | Alta | Caminho fora do allowedWriteScope da ExecutionRequest |
| `ERR_HARD_BLOCKED_PATH` | `BLOCKED` | Crítica | Tentativa de mutação em `.git/`, staging ou path traversal |
| `ERR_CROSS_VOLUME_STAGING` | `HUMAN_REVIEW` | Alta | Staging e alvos estão em volumes diferentes; atomicidade inviabilizada |
| `ERR_NON_ALLOWLISTED_PATH` | `HUMAN_REVIEW` | Média | Caminho fora de `AutoApplyRoots` (política default de revisão) |
| `ERR_PROTECTED_PATH` | `HUMAN_REVIEW` | Média | Tentativa de mutação em arquivos de código, schemas ou docs vitais |
| `ERR_STALE_BASE` | `HUMAN_REVIEW` | Média | Hash SHA256 do arquivo em disco difere da base esperada (TOCTOU) |
| `ERR_CREATE_CONFLICT` | `HUMAN_REVIEW` | Média | Arquivo de CREATE já existe em disco (TOCTOU ou exclusive create) |
| `ERR_PATCH_INVALID` | `BLOCKED` | Alta | Conteúdo candidato não é UTF-8 válido ou falha em parse JSON |
| `ERR_STAGING_FAILED` | `BLOCKED` | Alta | Falha de I/O ao gravar arquivos candidatos no diretório de staging |
| `ERR_ATOMIC_COMMIT_FAILED` | `ROLLED_BACK` | Alta | Falha durante mutação individual; rollback compensatório teve sucesso |
| `ERR_CRITICAL_ROLLBACK_FAILED`| `ROLLBACK_FAILED`| Crítica | Falha durante mutação e falha ao restaurar backups; exige resgate |
| `ERR_FILESYSTEM_PERMISSIONS` | `BLOCKED` | Alta | Permissão negada pelo sistema operacional ao tentar gravação |

---

## 7. Estratégia de Testes e Portões de Qualidade

### 7.1 Testabilidade Determinística e Offline
- **Zero Dependências de Rede**: Todos os testes rodam de forma offline, determinística e hermética.
- **Isolamento de Filesystem (`tmp_path`)**: Todos os testes de aplicação, staging, falhas TOCTOU, conflitos concorrentes e rollback compensatório executam exclusivamente dentro de fixtures de diretórios temporários (`tmp_path`). A árvore real do repositório nunca é modificada pelos testes.

### 7.2 Casos de Teste Essenciais da V2.1
1. **Allowlist Policy Enforcement**:
   - Mutações estritamente em `data/text/` e `data/structured/` $\rightarrow$ `AUTO_APPLY` aprovado (se no write-scope).
   - Mutações em `scripts/`, `schemas/`, `Livros/`, `coordination/` $\rightarrow$ `HUMAN_REVIEW` com `ERR_PROTECTED_PATH`.
   - Mutações em caminhos novos fora de `AutoApplyRoots` $\rightarrow$ `HUMAN_REVIEW` com `ERR_NON_ALLOWLISTED_PATH`.
   - Tentativa de mutação em `.git/` ou path traversal `../` $\rightarrow$ `BLOCKED` com `ERR_HARD_BLOCKED_PATH`.
   - Interseção estrita: `allowedWriteScope` contendo `scripts/` não autoriza auto-aplicação.
2. **Same-Filesystem Verification & Fail-Closed Staging**:
   - Staging configurado no mesmo volume $\rightarrow$ aplicação normal autorizada.
   - Staging simulado em ponto de montagem/volume distinto $\rightarrow$ rejeição fail-closed com `ERR_CROSS_VOLUME_STAGING`.
3. **TOCTOU Precondition Recheck**:
   - `UPDATE`: Teste com alteração concorrente do arquivo no disco entre a Fase 1 e a Fase 4 $\rightarrow$ aborta antes da Fase 5 com `ERR_STALE_BASE` e zero alterações no repo.
   - `CREATE`: Teste com criação concorrente de arquivo no disco antes da Fase 4 $\rightarrow$ aborta com `ERR_CREATE_CONFLICT`.
4. **Exclusive CREATE Race Protection**:
   - Simulação de criação concorrente imediata durante a chamada de `CREATE` $\rightarrow$ detecção via `FileExistsError` / `O_EXCL`, abortando com rollback limpo.
5. **Rollback Compensation & Journal Authority**:
   - Compensating cleanup de `CREATE`: remove estritamente o arquivo criado pela transação quando o hash bate.
   - Proteção de mutação externa em `CREATE`: se o arquivo criado for alterado externamente antes do rollback $\rightarrow$ não remove, status `ROLLBACK_FAILED`.
   - Rollback de `UPDATE`: restaura o snapshot original quando o hash pós-aplicação bate.
   - Proteção de mutação externa em `UPDATE`: se o arquivo atualizado for alterado externamente antes do rollback $\rightarrow$ não sobrescreve, status `ROLLBACK_FAILED`.
   - Lote de 3 arquivos com falha induzida no 3º: 1º e 2º revertidos com integridade perfeita, status `ROLLED_BACK`.
6. **Staging Cleanup Lifecycle**:
   - Em `APPLIED`: staging temporário limpo.
   - Em `ROLLED_BACK`: staging limpo somente após verificação de integridade dos hashes originais.
   - Em `ROLLBACK_FAILED`: staging e backups preservados em disco para intervenção manual.

---

## 8. Sequência de Implementação Proposta (Tasks da V2.1)

1. **Task 25 — ChangeSet Contracts & ChangeSetBuilder**:
   - Schemas JSON e dataclasses para `ChangeSet`, `ChangeOperation`, `TransactionJournal` e `ApplicationResult`.
   - Implementação do `ChangeSetBuilder` determinístico.
2. **Task 26 — ApplicationPolicy & Allowlist Engine**:
   - Implementação da política baseada em allowlist (`AutoApplyRoots`, `ProtectedRoots`, `HardBlockedRoots`, `default=HUMAN_REVIEW`).
   - Lógica de interseção estrita com `allowedWriteScope`.
3. **Task 27 — PreconditionValidator & TOCTOU Rechecker**:
   - Validador fail-closed de pré-condições, path safety, verificação de base SHA256 e revalidação TOCTOU pré-mutação.
4. **Task 28 — PatchApplier & Same-Filesystem Staging Manager**:
   - Construtor de candidatos em memória e gerenciador de staging temporário com validação fail-closed de mesmo volume de disco.
5. **Task 29 — Atomic Applier with Compensating Rollback Engine**:
   - Executor transacional all-or-nothing com substituição atômica unitária, exclusive CREATE, journal forense como autoridade única de rollback e proteções contra mutações externas concorrentes.
6. **Task 30 — End-to-End Persistence Pipeline & Fixtures**:
   - Integração completa da camada de persistência com `ExecutionCoordinator` da V2 em ambiente de teste determinístico.

---

## 9. Compatibilidade com as Versões Anteriores

- **Versão 1 (`multiagent-context-v1`)**: 100% inalterada e compatível. Todos os schemas e contratos de jobs, handoffs, context packs e seleções do orquestrador continuam intactos.
- **Versão 2 (`multiagent-execution-v2`)**: 100% inalterada e compatível. O `ExecutionCoordinator` e `ExecutionResultValidator` continuam gerando `ExecutionResult` em memória. A V2.1 consome o resultado aceito como entrada para o pipeline de persistência sem alterar o runtime da V2.
