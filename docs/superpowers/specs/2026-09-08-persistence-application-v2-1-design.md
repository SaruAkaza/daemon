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
5. **Trusted Runtime Root Authority.** (O caminho raiz do repositório, o diretório de staging, o diretório de auditoria e os limites de recursos são derivados estritamente da configuração local confiável do runtime. Modelos e requisições nunca podem definir ou influenciar essas raízes).
6. **Multi-Layer Canonical Path Containment & Symlink/Reparse Safety.** (Todo caminho alvo deve passar por validação léxica, canonicalização e verificação de contenção no repositório. Qualquer presença de symlinks, directory junctions ou Windows reparse points na cadeia ancestral do alvo resulta em recusa fail-closed).
7. **Deterministic Windows Path Hardening.** (Normalização insensível a maiúsculas/minúsculas para contenção, rejeição estrita de Alternate Data Streams, nomes de dispositivos reservados do Windows, caminhos UNC e prefixos de dispositivo).
8. **Every filesystem mutation must pass deterministic preconditions immediately before mutation (TOCTOU Recheck).** (Verificação fail-closed de contenção física, ausência de symlinks, SHA256 base e ausência de arquivo imediatamente antes da primeira mutação física).
9. **No partial ChangeSet application is allowed.** (Semântica all-or-nothing implementada através de pré-validação, staging isolado no mesmo volume, journal transacional e rollback compensatório restrito).
10. **Destructive operations (DELETE, RENAME, MOVE) are strictly forbidden in V2.1.** (Apenas criação exclusiva de novos arquivos e atualização de arquivos existentes são autorizadas para propostas e ChangeSets. Remoção de arquivos é autorizada exclusivamente como rotina interna de compensação/rollback para desarmar um `CREATE` recém-aplicado na mesma transação que falhou).
11. **CREATE operations never overwrite existing targets.** (Criação exclusiva atômica via `O_CREAT | O_EXCL`; qualquer conflito aborta a transação e escala para `HUMAN_REVIEW`).
12. **Same-Filesystem Staging Invariant.** (O diretório de staging deve residir no mesmo volume do repositório para garantir atomicidade de renomeação. Se a equivalência de volume não puder ser garantida, a auto-aplicação falha em modo fechado: `AUTO_APPLY` fail-closed).
13. **Strict Content Domain & Enforced Resource Bounds.** (Mutações automáticas são restritas a texto UTF-8 comprovado; arquivos binários e propostas que excedam limites de tamanho ou contagem falham em modo fechado).

---

## 2. Escopo: Goals e Non-Goals

### 2.1 Goals (Metas da V2.1)
- **ChangeSet Formal**: Definir modelo estruturado, tipado e imutável de `ChangeSet` e `ChangeOperation`.
- **ChangeSetBuilder Determinístico**: Transformar `ExecutionResult` aceito em manifesto de alterações determinístico.
- **ApplicationPolicy com Allowlist Restritiva**: Implementar política de governança baseada em `AutoApplyRoots`, `ProtectedRoots`, `HardBlockedRoots` e regra default `HUMAN_REVIEW`.
- **Interseção Estrita de Autoridade**: Garantir que `allowedWriteScope` da requisição nunca amplie as raízes elegíveis de auto-aplicação.
- **Root Authority Confiável**: Garantir que `repo_root`, `staging_root`, `audit_root` e `backup_root` sejam controlados exclusivamente pelo runtime local.
- **Hardening de Filesystem e Windows**: Proteger contra escapes de symlink, junction, reparse points, Alternate Data Streams (`:stream`), nomes de dispositivos (`CON`, `NUL`, etc.) e colisões de casing no Windows.
- **PreconditionValidator com Proteção TOCTOU**: Validar integridade e contenção canônica na análise inicial e revalidar a árvore física e hashes imediatamente antes da primeira mutação física.
- **PatchApplier UTF-8 / Text-Only**: Gerar e validar conteúdo candidato exclusivamente textual UTF-8 (e parse JSON) sem alterar arquivos vivos.
- **Limites de Recursos (Resource Bounds)**: Impor limites rígidos de tamanho máximo de arquivo, tamanho total de ChangeSet e número de operações.
- **Staging no Mesmo Filesystem Fora da Árvore Versionada**: Gerenciar staging temporário em diretório runtime-owned no mesmo volume de disco dos alvos, fora do controle do LLM e hard-blocked como alvo de mutações.
- **Aplicação All-or-Nothing em 6 Fases**: Executar mutações atômicas individuais com journal transacional como fonte única de autoridade para compensação.
- **Proteção de Criação Exclusiva**: Garantir que `CREATE` nunca sobrescreva arquivos existentes mesmo sob condições de corrida concorrente.
- **Rollback Compensatório Estritamente Delimitado**:
  - Reversão de `CREATE`: Remoção compensatória restrita ao arquivo recém-criado, verificando correspondência exata de hash.
  - Reversão de `UPDATE`: Restauração de snapshot original verificando que o arquivo não foi modificado por processo concorrente externo.
- **Armazenamento de Auditoria e Journal Isolados**: Persistir journals e metadados fora das `AutoApplyRoots` e fora da autoridade de escrita dos agentes.
- **ApplicationResult e Journal Forense**: Registrar resultado detalhado com taxonomia clara (`APPLIED`, `NOT_APPLIED`, `ROLLED_BACK`, `ROLLBACK_FAILED`, `HUMAN_REVIEW`, `BLOCKED`).

### 2.2 Non-Goals (Fora do Escopo da V2.1)
- **NÃO** suporta operações destrutivas (`DELETE`, `RENAME`, `MOVE`) pelo usuário, LLM ou ExecutionResult.
- **NÃO** suporta mutação automática em arquivos binários (qualquer arquivo não decodificável como UTF-8 estrito é rejeitado para auto-aplicação).
- **NÃO** segue ou resolve symlinks, junctions ou reparse points automaticamente para tentar alcançar alvos fora da contenção.
- **NÃO** executa commits git automáticos, push remoto ou abertura de Pull Requests.
- **NÃO** implementa concorrência distribuída ou múltiplos escritores concorrentes (assume escritor único controlado).
- **NÃO** faz chamadas a provedores ou LLMs para "resolver conflitos" ou "recuperar falhas".
- **NÃO** substitui arquivos silenciosamente sem verificação de hash base (`expectedBaseSha256`).
- **NÃO** promete primitivas nativas de transação atômica multi-arquivo que o sistema de arquivos não oferece (utiliza semântica all-or-nothing com journal e rollback compensatório).
- **NÃO** degrada silenciosamente para cópia não-atômica entre volumes se o staging estiver em outro filesystem (falha fechado com `ERR_CROSS_VOLUME_STAGING`).
- **NÃO** permite que o modelo ou a ExecutionRequest configurem ou acessem o caminho de staging ou repositório.
- **NÃO** sobrescreve modificações externas concorrentes durante uma tentativa de rollback.

---

## 3. Segurança de Caminhos, Governança e Semântica de Sistema de Arquivos

### 3.1 Autoridade de Raiz e Configuração Confiável
- **Origem da Raiz**: O caminho absoluto `repository_root` é determinado **exclusivamente** pelo ambiente de execução local (ex: flag CLI confiável `--repo-root`, variável de ambiente ou contexto do orquestrador local).
- **Imunidade contra Injeção**: Nenhuma informação contida na `ExecutionRequest`, no `ExecutionResult`, no `ChangeSet` ou em metadados de provedores LLM pode definir, redefinir ou alterar o `repository_root`, o `staging_root`, o `audit_root` ou os limites de recursos (`ResourceBounds`).

### 3.2 Validação Multi-Camada de Caminhos e Proteção contra Symlinks/Reparse Points
A validação de cada `target_path` exige o cumprimento cumulativo de 4 camadas de segurança:

1. **Validação Léxica**:
   - O caminho deve ser estritamente relativo ao `repository_root`.
   - Normalizado para separador POSIX `/`.
   - Rejeição imediata de `..` (path traversal), caracteres nulos (`\0`), barras iniciais (`/`), e caminhos absolutos (`C:\`, `/`).
2. **Hardening Específico para Windows**:
   - **Drive Letters**: Rejeição de letras de unidade (`C:`, `D:`, etc.).
   - **UNC & Device Paths**: Rejeição de caminhos UNC (`\\server\share`), caminhos de dispositivo (`\\.\`, `\\?\`).
   - **Alternate Data Streams (ADS)**: Rejeição de qualquer caractere de dois-pontos `:` no caminho (ex: `data.txt:hidden_stream`).
   - **Nomes de Dispositivos Reservados**: Rejeição de nomes reservados do DOS/Windows em qualquer segmento do caminho, com ou sem extensão (`CON`, `PRN`, `AUX`, `NUL`, `COM1`..`COM9`, `LPT1`..`LPT9`).
   - **Caracteres Especiais / Trailing**: Rejeição de pontos ou espaços no final de diretórios/nomes (`dir. /`, `file.txt.`), caracteres curinga (`*`, `?`, `<`, `>`, `|`, `"`).
   - **Normalização de Casing (Case-Insensitivity)**: Toda comparação de pertinência a allowlists e contenção utiliza normalização de casing canônica (`os.path.normcase` / case-folding no Windows) para impedir que variações como `Data/...`, `data/...`, `DATA/...` bypassem políticas ou acessem autoridades distintas.
3. **Validação de Contenção Canônica no Repositório**:
   - O caminho resolvido (`realpath`) do diretório pai deve residir comprovadamente dentro do `repository_root` canônico resolvido.
4. **Política Conservadora de Symlink / Junction / Reparse Point**:
   - Se **qualquer** componente na cadeia ancestral do caminho alvo for um link simbólico (`os.path.islink`), uma junção de diretório (Windows Directory Junction) ou um Reparse Point:
     - A auto-aplicação é **recusada imediatamente em modo fail-closed** com código `ERR_SYMLINK_REPARSE_POINT_DETECTED`.
     - O runtime **NÃO segue automaticamente links** para tentar alcançar o arquivo.

```text
                               Target Path Validation Pipeline
                                              │
                                              ▼
                                 ┌─────────────────────────┐
                                 │ 1. Lexical Path Check   │ ──(FAIL)──► BLOCKED (ERR_PATH_TRAVERSAL)
                                 │ (Relative, no .., no \0)│
                                 └────────────┬────────────┘
                                              │ (PASS)
                                              ▼
                                 ┌─────────────────────────┐
                                 │ 2. Windows Hardening    │ ──(FAIL)──► BLOCKED (ERR_HARD_BLOCKED_PATH)
                                 │ (No UNC/ADS/Reserved/\?)│
                                 └────────────┬────────────┘
                                              │ (PASS)
                                              ▼
                                 ┌─────────────────────────┐
                                 │ 3. Reparse/Symlink Test │ ──(FAIL)──► HUMAN_REVIEW (ERR_SYMLINK_REPARSE_POINT_DETECTED)
                                 │ (No symlink in ancestor)│
                                 └────────────┬────────────┘
                                              │ (PASS)
                                              ▼
                                 ┌─────────────────────────┐
                                 │ 4. Canonical Containment│ ──(FAIL)──► BLOCKED (ERR_CONTAINMENT_VIOLATION)
                                 │ (Resolved inside repo)  │
                                 └────────────┬────────────┘
                                              │ (PASS)
                                              ▼
                                     CANONICAL_PATH_SAFE
```

---

## 4. Política de Governança e Classificação de Diretórios

A governança do sistema de arquivos na V2.1 adota o princípio de **privilégio mínimo baseado em allowlist**:

$$\text{Default Action} = \text{HUMAN\_REVIEW}$$

Nenhum arquivo é aplicado automaticamente a menos que esteja explicitamente contido em uma raiz autorizada de dados derivados.

### 4.1 HardBlockedRoots (Rejeição Imediata — `BLOCKED`)
Mutações nestes destinos representam violação grave de integridade ou segurança:
- `.git/**` (Metadados do repositório Git, hooks, objetos e refs).
- Caminhos contendo path traversal (`..`), caminhos absolutos, UNC ou ADS.
- Caminhos que apontem para diretórios de staging, runtime ou auditoria (`.daemon_staging/**`, `.daemon_runtime/**`, etc.).
- Ambientes virtuais e dependências externas (`.venv/**`, `node_modules/**`).

### 4.2 ProtectedRoots (Control-Plane / Source-Sensitive — `HUMAN_REVIEW`)
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

### 4.3 AutoApplyRoots (Explicit Allowlist — Dados Derivados do Pipeline)
Somente artefatos derivados gerados determinística e exclusivamente pelas etapas do pipeline de dados são elegíveis para auto-aplicação:
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

### 4.4 Interseção Estrita de Autoridade
A autoridade de aplicação de uma requisição é determinada exclusivamente pela interseção:

$$\text{EffectiveAutoApplyScope} = \text{requested\_write\_scope} \cap \text{AutoApplyRoots} \cap \text{ApplicationPolicy}$$

- O parâmetro `allowedWriteScope` da `ExecutionRequest` é uma **restrição adicional**, **NUNCA** uma ampliação.
- Se a `ExecutionRequest` solicitar escrita em `scripts/agents/`, essa requisição será classificada como `HUMAN_REVIEW` (`ERR_PROTECTED_PATH`), mesmo que esteja em seu `allowedWriteScope`.
- Se um `ChangeSet` contiver 5 arquivos em `data/text/` e 1 arquivo fora de `AutoApplyRoots`, o `ChangeSet` **inteiro** é escalado para `HUMAN_REVIEW`.

---

## 5. Domínio de Conteúdo Suportado e Limites de Recursos

### 5.1 Domínio de Conteúdo Estritamente Textual (UTF-8)
A V2.1 suporta mutações automáticas **exclusivamente para arquivos textuais** com codificação UTF-8 comprovada:
- **Codificação Obrigatória**: UTF-8 estrito sem Byte Order Mark (BOM). Caracteres ou sequências de bytes inválidas geram rejeição imediata (`ERR_PATCH_INVALID`).
- **Sem Suposição de Encoding**: O sistema nunca tenta "adivinhar" ou aplicar fallbacks para latin-1, Windows-1252 ou ISO-8859-1.
- **Validação Sintática Estruturada**: Para arquivos `.json`, o `PatchApplier` executa validação sintática rigorosa antes de qualquer estagiamento.
- **Exclusão de Binários**: Arquivos binários (imagens, PDFs, binários compilados) **não são suportados para mutação automática** na V2.1. Qualquer proposta de patch sobre binários é escalada para `HUMAN_REVIEW` (`ERR_UNSUPPORTED_CONTENT_DOMAIN`).

### 5.2 Limites de Recursos Configuráveis (Resource Bounds)
Para proteger o sistema contra exaustão de memória, disco ou ataques de negação de serviço, o runtime impõe limites locais rígidos:

| Parâmetro de Limite | Descrição | Comportamento em Caso de Violação |
|---|---|---|
| `MAX_FILE_SIZE_BYTES` | Tamanho máximo permitido para um único arquivo candidato | `BLOCKED` (`ERR_RESOURCE_BOUND_EXCEEDED`) |
| `MAX_CHANGESET_SIZE_BYTES` | Tamanho total cumulativo de todos os candidatos do ChangeSet | `BLOCKED` (`ERR_RESOURCE_BOUND_EXCEEDED`) |
| `MAX_OPERATIONS_PER_CHANGESET` | Quantidade máxima de operações permitidas em um único ChangeSet | `BLOCKED` (`ERR_RESOURCE_BOUND_EXCEEDED`) |
| `MAX_TOTAL_STAGING_BYTES` | Limite de ocupação de disco permitido no diretório de staging | `BLOCKED` (`ERR_RESOURCE_BOUND_EXCEEDED`) |

- Todos os limites de recursos são **configurados exclusivamente no runtime local confiável**.
- Modelos de IA e `ExecutionRequests` **nunca podem ampliar ou desativar** esses limites.

---

## 6. Arquitetura e Fluxo de Execução em 6 Fases

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
                        │ - Resource bounds check               │
                        │ - Lexical & Windows path validation   │
                        └───────────────────┬───────────────────┘
                                            │ (PASS)
                                            ▼
                        ┌───────────────────────────────────────┐
                        │ Phase 2: Construct Candidates         │
                        │ - PatchApplier (In-Memory UTF-8/JSON) │
                        │ - Strict text domain validation       │
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
                        │ Phase 4: TOCTOU Full Revalidation     │
                        │ - Immediately before first mutation   │
                        │ - Recheck canonical path containment  │
                        │ - Recheck no symlinks/reparse points  │
                        │ - UPDATE: current == expectedBaseSha  │
                        │ - CREATE: target still not exists     │
                        └───────────────┬───────────────────────┘
                                 (PASS) │       │ (FAIL: Precondition / Containment violated)
                                        │       ▼
                                        │  Abort: Zero target mutations
                                        │  Clean staging → Escalate (HUMAN_REVIEW / BLOCKED)
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

### 6.1 Detalhamento das 6 Fases

#### Fase 1: Validação Estrutural, Caminhos e Limites
1. Recebe a `ExecutionRequest` e o `ExecutionResult` com veredito `ACCEPT`.
2. Constrói o `ChangeSet` imutável mapeando cada arquivo proposto.
3. Valida os limites de recursos (`ResourceBounds`):
   - Se o número de operações ou tamanho de arquivos exceder os limites $\rightarrow$ `BLOCKED` (`ERR_RESOURCE_BOUND_EXCEEDED`).
4. Executa validação de políticas e caminhos:
   - Rejeita operações não permitidas (`DELETE`, `RENAME`, `MOVE`) $\rightarrow$ `BLOCKED` (`ERR_OPERATION_NOT_ALLOWED`).
   - Valida regras léxicas e de hardening Windows (sem `..`, sem UNC, sem ADS, sem nomes reservados) $\rightarrow$ `BLOCKED` (`ERR_HARD_BLOCKED_PATH`).
   - Verifica `HardBlockedRoots` $\rightarrow$ `BLOCKED` (`ERR_HARD_BLOCKED_PATH`).
   - Verifica `ProtectedRoots` $\rightarrow$ `HUMAN_REVIEW` (`ERR_PROTECTED_PATH`).
   - Verifica `AutoApplyRoots` $\rightarrow$ Se fora da allowlist: `HUMAN_REVIEW` (`ERR_NON_ALLOWLISTED_PATH`).
   - Valida `allowedWriteScope` da requisição $\rightarrow$ Se fora do escopo: `BLOCKED` (`ERR_WRITE_SCOPE_VIOLATION`).

#### Fase 2: Construção e Validação dos Candidatos em Memória
1. `PatchApplier` valida sintaxe e codificação de cada artefato candidato em memória:
   - Validação estrita de decodificação UTF-8 (sem bytes inválidos, sem adivinhação de encoding).
   - Rejeição de conteúdos binários $\rightarrow$ `HUMAN_REVIEW` (`ERR_UNSUPPORTED_CONTENT_DOMAIN`).
   - Para arquivos com extensão `.json`: validação de parse sintático JSON.
2. Gera estruturas em memória `CandidateArtifact` prontas para estagiamento.

#### Fase 3: Estagiamento Isolado no Mesmo Filesystem (Same-Volume Staging)
1. **Regra de Invariância de Volume**: O diretório de staging deve residir comprovadamente no **mesmo filesystem / volume** que os alvos do repositório (para garantir que `os.replace` execute uma substituição atômica de inode/diretório sem fallback para cópia entre volumes).
   - Se o caminho de staging estiver em volume diferente ou se a verificação de volume falhar $\rightarrow$ `AUTO_APPLY` falha em modo fechado com código `ERR_CROSS_VOLUME_STAGING` e escala para `HUMAN_REVIEW`.
2. **Localização Segura**: O staging deve residir **fora da árvore rastreada do Git** (ex: diretório runtime-owned no volume local derivado da configuração confiável).
3. O caminho de staging é gerenciado exclusivamente pelo runtime; modelos e requisições não podem configurá-lo, observá-lo ou direcionar mutações para ele.
4. Grava os candidatos no staging e calcula o SHA256 de cada arquivo estagiado (`candidate_sha256`).

#### Fase 4: Revalidação Total TOCTOU (Imediatamente Pré-Mutação)
Imediatamente antes de realizar a primeira mutação física no repositório, o `PreconditionValidator` inspeciona o sistema de arquivos ao vivo:
1. **Revalidação de Contenção Física e Reparse/Symlinks**:
   - Revalida que o caminho resolvido do diretório pai ainda reside dentro do `repository_root` canônico.
   - Revalida que nenhum componente ancestral foi substituído por symlink, junction ou reparse point entre a Fase 1 e a Fase 4. Se detectado $\rightarrow$ aborta com `ERR_SYMLINK_REPARSE_POINT_DETECTED`.
   - Revalida que o caminho continua estritamente dentro de `AutoApplyRoots` e `allowedWriteScope`.
2. **Revalidação de Estado dos Arquivos**:
   - Para `UPDATE`: Confirma existência e que `sha256(disk_bytes) == expected_base_sha256`. Se divergir $\rightarrow$ `ERR_STALE_BASE`.
   - Para `CREATE`: Confirma que o arquivo **ainda não existe** em disco (`os.path.exists(target) == False`). Se existir $\rightarrow$ `ERR_CREATE_CONFLICT`.
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
   - Executa limpeza dos arquivos temporários de staging (conforme Seção 7.4).
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

## 7. Modelos de Dados Estruturados e Auditoria

### 7.1 `ChangeOperation` e `ChangeSet`

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

### 7.2 `TransactionJournal` (Autoridade Determinística de Compensação)

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

### 7.3 `ApplicationResult` e Taxonomia de Status

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

### 7.4 Armazenamento de Auditoria e Política de Limpeza

1. **Local de Armazenamento de Auditoria / Journals**:
   - Os journals de transação preservados residem **exclusivamente no diretório de auditoria do runtime** (`audit_root`), derivado da configuração local confiável.
   - O armazenamento de auditoria fica **fora das `AutoApplyRoots`**, **fora da árvore rastreada do Git** e **fora do alcance de escrita de modelos/agentes**.
   - Nenhum `ChangeSet` pode ter como alvo o diretório de auditoria ou staging.
2. **Quando o status é `APPLIED`**:
   - Os arquivos temporários (candidatos e backups) são excluídos do diretório de staging.
   - O registro do journal é persistido no `audit_root` para fins de auditoria e governança.
3. **Quando o status é `ROLLED_BACK`**:
   - O runtime verifica a integridade de todos os hashes originais no disco.
   - Somente após confirmar que o sistema de arquivos retornou 100% ao estado inicial, os arquivos temporários de staging são limpos.
4. **Quando o status é `ROLLBACK_FAILED`**:
   - O runtime **NÃO limpa** o diretório de staging, mantendo intactos todos os backups, arquivos candidatos e o journal.
   - O estado do sistema é classificado como `PARTIALLY_MODIFIED_UNCERTAIN` e os artefatos preservados servem de base para resolução manual por operadores humanos.

---

## 8. Taxonomia Completa de Falhas da V2.1

| Código de Erro | Status Resultante | Severidade | Descrição |
|---|---|---|---|
| `ERR_CHANGESET_INVALID` | `BLOCKED` | Alta | Estrutura ou dados do ChangeSet inválidos / corrompidos |
| `ERR_OPERATION_NOT_ALLOWED` | `BLOCKED` | Alta | Tentativa de DELETE, RENAME, MOVE ou operação não suportada |
| `ERR_WRITE_SCOPE_VIOLATION` | `BLOCKED` | Alta | Caminho fora do allowedWriteScope da ExecutionRequest |
| `ERR_HARD_BLOCKED_PATH` | `BLOCKED` | Crítica | Tentativa de mutação em `.git/`, staging, ADS (`:stream`), UNC ou reserved names |
| `ERR_PATH_TRAVERSAL` | `BLOCKED` | Crítica | Caminho contém `..`, caminhos absolutos ou barras iniciais |
| `ERR_CONTAINMENT_VIOLATION` | `BLOCKED` | Crítica | Caminho resolvido escapa do repository_root canônico |
| `ERR_SYMLINK_REPARSE_POINT_DETECTED` | `HUMAN_REVIEW` | Alta | Componente ancestral é link simbólico, junction ou reparse point |
| `ERR_RESOURCE_BOUND_EXCEEDED` | `BLOCKED` | Alta | Limite de tamanho de arquivo, total de bytes ou contagem excedido |
| `ERR_UNSUPPORTED_CONTENT_DOMAIN` | `HUMAN_REVIEW` | Média | Arquivo candidato é binário ou não é texto UTF-8 comprovado |
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

## 9. Estratégia de Testes e Portões de Qualidade

### 9.1 Testabilidade Determinística e Offline
- **Zero Dependências de Rede**: Todos os testes rodam de forma offline, determinística e hermética.
- **Isolamento de Filesystem (`tmp_path`)**: Todos os testes de aplicação, staging, falhas TOCTOU, conflitos concorrentes e rollback compensatório executam exclusivamente dentro de fixtures de diretórios temporários (`tmp_path`). A árvore real do repositório nunca é modificada pelos testes.

### 9.2 Casos de Teste Essenciais da V2.1
1. **Allowlist Policy Enforcement**:
   - Mutações estritamente em `data/text/` e `data/structured/` $\rightarrow$ `AUTO_APPLY` aprovado (se no write-scope).
   - Mutações em `scripts/`, `schemas/`, `Livros/`, `coordination/` $\rightarrow$ `HUMAN_REVIEW` com `ERR_PROTECTED_PATH`.
   - Mutações em caminhos novos fora de `AutoApplyRoots` $\rightarrow$ `HUMAN_REVIEW` com `ERR_NON_ALLOWLISTED_PATH`.
   - Tentativa de mutação em `.git/` $\rightarrow$ `BLOCKED` com `ERR_HARD_BLOCKED_PATH`.
   - Interseção estrita: `allowedWriteScope` contendo `scripts/` não autoriza auto-aplicação.
2. **Symlink, Junction & Canonical Containment Hardening**:
   - Tentativa de escrita através de link simbólico em diretório ancestral $\rightarrow$ recusado com `ERR_SYMLINK_REPARSE_POINT_DETECTED`.
   - Tentativa de escape via `..` $\rightarrow$ `BLOCKED` com `ERR_PATH_TRAVERSAL`.
   - Verificação de que o caminho resolvido fica 100% contido dentro do repositório raiz.
3. **Windows Hardening (ADS, Reserved Names, Case-Insensitivity)**:
   - Caminho com Alternate Data Stream (`data/text/file.txt:stream`) $\rightarrow$ `BLOCKED` com `ERR_HARD_BLOCKED_PATH`.
   - Caminho com dispositivo reservado (`data/text/con.txt`, `data/aux/file.txt`) $\rightarrow$ `BLOCKED` com `ERR_HARD_BLOCKED_PATH`.
   - Casing variations (`Data/Text/file.txt` vs `data/text/file.txt`) $\rightarrow$ normalização determinística sem bypass.
4. **Resource Bounds & Content Domain**:
   - Candidato excedendo `MAX_FILE_SIZE_BYTES` $\rightarrow$ `BLOCKED` (`ERR_RESOURCE_BOUND_EXCEEDED`).
   - Candidato contendo bytes binários / não UTF-8 $\rightarrow$ `HUMAN_REVIEW` (`ERR_UNSUPPORTED_CONTENT_DOMAIN`).
5. **Same-Filesystem Verification & Fail-Closed Staging**:
   - Staging configurado no mesmo volume $\rightarrow$ aplicação normal autorizada.
   - Staging simulado em ponto de montagem/volume distinto $\rightarrow$ rejeição fail-closed com `ERR_CROSS_VOLUME_STAGING`.
6. **TOCTOU Full Precondition Recheck**:
   - `UPDATE`: Teste com alteração concorrente do arquivo no disco entre a Fase 1 e a Fase 4 $\rightarrow$ aborta antes da Fase 5 com `ERR_STALE_BASE` e zero alterações no repo.
   - `CREATE`: Teste com criação concorrente de arquivo no disco antes da Fase 4 $\rightarrow$ aborta com `ERR_CREATE_CONFLICT`.
   - Modificação física de symlink na Fase 4 $\rightarrow$ aborta com `ERR_SYMLINK_REPARSE_POINT_DETECTED`.
7. **Exclusive CREATE Race Protection**:
   - Simulação de criação concorrente imediata durante a chamada de `CREATE` $\rightarrow$ detecção via `FileExistsError` / `O_EXCL`, abortando com rollback limpo.
8. **Rollback Compensation & Journal Authority**:
   - Compensating cleanup de `CREATE`: remove estritamente o arquivo criado pela transação quando o hash bate.
   - Proteção de mutação externa em `CREATE`: se o arquivo criado for alterado externamente antes do rollback $\rightarrow$ não remove, status `ROLLBACK_FAILED`.
   - Rollback de `UPDATE`: restaura o snapshot original quando o hash pós-aplicação bate.
   - Proteção de mutação externa em `UPDATE`: se o arquivo atualizado for alterado externamente antes do rollback $\rightarrow$ não sobrescreve, status `ROLLBACK_FAILED`.
   - Lote de 3 arquivos com falha induzida no 3º: 1º e 2º revertidos com integridade perfeita, status `ROLLED_BACK`.
9. **Staging & Audit Storage Lifecycle**:
   - Em `APPLIED`: staging temporário limpo, journal persistido no `audit_root` (fora do repo).
   - Em `ROLLED_BACK`: staging limpo somente após verificação de integridade dos hashes originais.
   - Em `ROLLBACK_FAILED`: staging e backups preservados em disco para intervenção manual.

---

## 10. Sequência de Implementação Proposta (Tasks da V2.1)

1. **Task 25 — ChangeSet Contracts & ChangeSetBuilder**:
   - Schemas JSON e dataclasses para `ChangeSet`, `ChangeOperation`, `TransactionJournal` e `ApplicationResult`.
   - Implementação do `ChangeSetBuilder` determinístico.
2. **Task 26 — ApplicationPolicy, Allowlist Engine & Path Hardening**:
   - Implementação da política baseada em allowlist (`AutoApplyRoots`, `ProtectedRoots`, `HardBlockedRoots`, `default=HUMAN_REVIEW`).
   - Hardening multi-camada: validação léxica, Windows ADS/nomes reservados, contenção canônica e detecção de symlinks/reparse points.
   - Lógica de interseção estrita com `allowedWriteScope`.
3. **Task 27 — PreconditionValidator & Full TOCTOU Rechecker**:
   - Validador fail-closed de pré-condições, path safety, verificação de base SHA256 e revalidação TOCTOU física completa pré-mutação.
4. **Task 28 — PatchApplier & Same-Filesystem Staging Manager**:
   - Construtor de candidatos em memória restrito a UTF-8/JSON, limites de recursos e gerenciador de staging temporário com validação fail-closed de mesmo volume.
5. **Task 29 — Atomic Applier with Compensating Rollback Engine**:
   - Executor transacional all-or-nothing com substituição atômica unitária, exclusive CREATE, journal forense no audit storage e proteções contra mutações externas concorrentes.
6. **Task 30 — End-to-End Persistence Pipeline & Fixtures**:
   - Integração completa da camada de persistência com `ExecutionCoordinator` da V2 em ambiente de teste determinístico.

---

## 11. Compatibilidade com as Versões Anteriores

- **Versão 1 (`multiagent-context-v1`)**: 100% inalterada e compatível. Todos os schemas e contratos de jobs, handoffs, context packs e seleções do orquestrador continuam intactos.
- **Versão 2 (`multiagent-execution-v2`)**: 100% inalterada e compatível. O `ExecutionCoordinator` e `ExecutionResultValidator` continuam gerando `ExecutionResult` em memória. A V2.1 consome o resultado aceito como entrada para o pipeline de persistência sem alterar o runtime da V2.
