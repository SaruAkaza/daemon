# Legacy Coordination Migration

Este documento define a estratégia canônica, os princípios de coexistência e o plano de migração gradual da camada de coordenação legada (`coordination/`) para a nova arquitetura determinística de agentes baseada em Jobs, Handoffs, Context e Gates.

---

## 1. Purpose

### 1.1 Contexto da Coordenação Legada
Historicamente, a coordenação operacional do repositório Daemon Tools foi construída para permitir o trabalho paralelo entre dois provedores de IA distintos (Codex e Claude) operando em git worktrees isolados (`daemon` e `daemon-claude`). Essa coordenação baseava-se em:
- Arquivos de fila (`queue/<provider>.json`) mantidos manualmente ou por scripts ad-hoc;
- Arquivos de recados e handoffs em markdown (`handoff/<provider>.md`);
- Contratos de livros em markdown (`books/<livro>.md`);
- Divisão de trabalho aproximada por volume de arquivos (`book_assignments.md`);
- Regras de catalogação operacionais resumidas (`catalog_rules.md`).

### 1.2 Motivação da Nova Arquitetura
Embora funcional na fase piloto, o modelo legado apresentava vulnerabilidades estruturais:
- Ausência de validação determinística de schemas (arquivos podiam corromper ou omitir dados sem erro imediato);
- Dependência de provedores específicos nos caminhos de arquivo (`claude.json`, `codex.md`);
- Falta de garantias atômicas de escrita e isolamento seguro contra *path traversal*;
- Ausência de gates formais de entrada, release e direitos autorais;
- Risco de perda de memória e inconsistências entre execuções assíncronas.

A nova arquitetura multiagente foi projetada sobre contratos formais:
- **Repositório Git como memória durável** (ADR-0001);
- **Validação humana mandatória para conclusão de jobs** (ADR-0002);
- **Modelo de desenvolvimento em fork e release via upstream** (ADR-0003);
- **Armazenamento persistente e atômico de Jobs e Handoffs** (`JobStore`, `HandoffStore`);
- **Carregamento determinístico e seguro de contexto** (`ContextLoader`);
- **Construção de Context Packs fatiados e validados** (`ContextPackBuilder`);
- **Motor determinístico de políticas e portas de entrada/release** (`GateEngine`);
- **Seleção determinística de próximo estado do orquestrador** (`OrchestratorStateSelector`).

### 1.3 Preservação de Histórico e Não-Destrutividade
Nenhum artefato legado será destruído ou reescrito sumariamente. A história de extração de cada livro, os relatórios de OCR e as anotações de triagem representam proveniência e patrimônio técnico essenciais do projeto. A coexistência temporária garante continuidade operacional enquanto a transição ocorre de forma segura, determinística e auditável.

---

## 2. Current Systems

O repositório abriga simultaneamente dois subsistemas no diretório `coordination/`:

```text
coordination/
├── README.md                      ← Guia operacional (ponte transitória)
├── book_assignments.md            ← [LEGACY/HISTORICAL] Divisão de carga piloto
├── catalog_rules.md               ← [LEGACY/NEEDS_REVIEW] Resumo operacional de regras
├── queue/                         ← [LEGACY] Filas informais por provedor
│   └── claude.json
├── handoff/                       ← [LEGACY] Notas e mensagens informais por provedor
│   ├── claude.md
│   └── codex.md
├── books/                         ← [LEGACY/NEEDS_REVIEW] Contratos em markdown por livro
│   ├── daemon-medieval.md
│   ├── daemon-tormenta.md
│   └── guia-de-itens-magicos.md
├── jobs/                          ← [NEW_CANONICAL] Armazenamento de Agent Jobs JSON
│   └── .gitkeep
└── handoffs/                      ← [NEW_CANONICAL] Armazenamento de Agent Handoffs JSON
    └── .gitkeep
```

### 2.1 Subsistema Legado
- **`coordination/queue/`**: Armazena arquivos JSON informais por provedor (ex.: `claude.json`) com arrays `active`, `queue`, `done` e `released`.
- **`coordination/handoff/`** (singular): Armazena notas informais em markdown geradas por sessões anteriores de LLMs (`claude.md`, `codex.md`).
- **`coordination/books/`**: Armazena notas estruturais, triagem de OCR e taxonomias preliminares de livros específicos.
- **`coordination/book_assignments.md`**: Tabela histórica de atribuições de arquivos DOCX da pasta `Livros/word`.
- **`coordination/catalog_rules.md`**: Cartilha resumida de regras de catalogação criada na fase piloto.

### 2.2 Novo Substrato Canônico de Coordenação
- **`coordination/jobs/`**: Diretório canônico gerenciado pelo `JobStore`, contendo arquivos JSON validados pelo schema `schemas/agent-job.schema.json`.
- **`coordination/handoffs/`** (plural): Diretório canônico gerenciado pelo `HandoffStore`, contendo arquivos JSON validados pelo schema `schemas/agent-handoff.schema.json`.
- **Componentes de Software**:
  - `JobStore` (`scripts/agents/job_store.py`): CRUD atômico, imutabilidade de IDs e validação de Jobs.
  - `HandoffStore` (`scripts/agents/handoff_store.py`): Append atômico, imutabilidade estrita e validação de Handoffs.
  - `ContextLoader` (`scripts/agents/context_loader.py`): Leitura segura e canônica da memória em Git.
  - `ContextPackBuilder` (`scripts/agents/context_pack_builder.py`): Montagem determinística de pacotes de contexto por camada.
  - `GateEngine` (`scripts/agents/gate_engine.py`): Avaliação determinística de gates de estágio, release e conclusão.
  - `OrchestratorStateSelector` (`scripts/agents/orchestrator_state.py`): Seleção determinística da próxima ação segura para cada Job.

---

## 3. Classificação do Inventário Existente

Cada artefato no ecossistema de coordenação classifica-se formalmente conforme a taxonomia abaixo:

| Caminho / Componente | Classificação | Justificativa e Papel |
|---|---|---|
| `coordination/queue/` | `LEGACY` | Filas soltas acopladas a provedores sem validação de schema. |
| `coordination/queue/claude.json` | `LEGACY` | Fila histórica informal do Claude. |
| `coordination/handoff/` | `LEGACY` | Diretório singular de handoffs informais em texto livre. |
| `coordination/handoff/claude.md` | `HISTORICAL` | Registro histórico de diagnósticos e decisões da fase piloto. |
| `coordination/handoff/codex.md` | `HISTORICAL` | Registro histórico de correções e releases da fase piloto. |
| `coordination/book_assignments.md` | `HISTORICAL` | Divisão estática de carga de trabalho entre Codex e Claude. |
| `coordination/catalog_rules.md` | `NEEDS_REVIEW` | Resumo de regras; a fonte canônica é `docs/reference/cataloging-rules.md`. |
| `coordination/books/*.md` | `NEEDS_REVIEW` | Contratos de livros com dados valiosos de OCR e taxonomia a integrar como Book Context. |
| `coordination/README.md` | `SHARED_OR_STILL_VALID` | Documento de orientação operacional; mantido atualizado como ponte. |
| `coordination/jobs/` | `NEW_CANONICAL` | Storage canônico de Jobs persistentes da nova arquitetura. |
| `coordination/handoffs/` | `NEW_CANONICAL` | Storage canônico de Handoffs persistentes da nova arquitetura. |
| `schemas/agent-*.json` | `NEW_CANONICAL` | Contratos formais JSON Schema que governam todo o estado do sistema. |
| `scripts/agents/*.py` | `NEW_CANONICAL` | Módulos determinísticos da arquitetura multiagente. |

---

## 4. Matriz de Migração (Legacy → New)

| Artefato Legado | Propósito Existente | Equivalente Novo | Status de Migração | Notas |
|---|---|---|---|---|
| `coordination/queue/*.json` | Rastreamento de estado e atribuição por provedor | `coordination/jobs/<jobId>.json` | NOT MIGRATED | Exige conversão estruturada para schema `agent-job` com `jobId` canônico. Proibido renomear diretamente. |
| `coordination/handoff/*.md` | Mensagens livres e diagnósticos entre sessões | `coordination/handoffs/<handoffId>.json` | NOT MIGRATED | Handoffs formais exigem `agentRole`, `stage`, `summary` e `openQuestions`. |
| `coordination/book_assignments.md` | Atribuição manual de livros e prioridades | Source Manifests + Criação de Jobs | HISTORICAL / NOT MIGRATED | Substituído por criação explícita de Jobs via `JobStore` a partir de `Livros/`. |
| `coordination/catalog_rules.md` | Resumo de convenções de catalogação | `docs/reference/cataloging-rules.md` | CANONICAL DEFINED | `docs/reference/cataloging-rules.md` já é a fonte canônica; resumo mantido como referência histórica. |
| `coordination/books/<livro>.md` | Levantamento estrutural de parágrafos e OCR | `docs/context/books/<bookId>.md` | NEEDS_REVIEW | Conteúdo rico a ser avaliado para se tornar a camada Book Context do `ContextPackBuilder`. |

---

## 5. Diferenciação Conceitual: Queue Legada vs. Agent Job

### 5.1 Fila Legada (`queue/*.json`)
- Estrutura não validada, suscetível a erros de digitação e campos faltantes;
- Acoplada a um provedor específico (ex.: "Claude" ou "Codex");
- Rastreamento binário e informal de progresso (`todo`, `in_progress`, `needs_review`, `approved`, `done`, `blocked`);
- Não armazena histórico estruturado de transições nem artefatos gerados.

### 5.2 Agent Job (`agent-job.schema.json`)
- Entidade formalmente validada por JSON Schema v1.0;
- Totalmente neutra em relação a provedores de LLM;
- Identificador canônico e imutável (`JOB-<BOOK_ID>-<SEQ>`);
- Rastreamento granular de cada estágio do pipeline sequencial (`stages` map: `waiting`, `ready`, `running`, `pass`, `fail`, `blocked`, `human_review`);
- Histórico auditável (`history` com `timestamp`, `event`, `stage`, `message`);
- Registro explícito de bloqueios (`blockingReasons`) e artefatos produzidos (`artifacts`);
- Governança estrita por gates determinísticos (`GateEngine`).

> [!CAUTION]
> **Proibição de Renomeação Direta**: Nenhum arquivo de fila legado pode ser simplesmente renomeado para `.json` e colocado em `coordination/jobs/`. Toda transição exige instanciação formal via `JobStore.create()` com validação estrita de schema.

---

## 6. Diferenciação de Armazenamento: `handoff/` vs. `handoffs/`

Para evitar que operadores humanos ou ferramentas automatizadas escrevam no destino incorreto, a distinção morfológica e estrutural é rigorosa:

- **`coordination/handoff/` (SINGULAR — LEGADO)**:
  - Contém arquivos Markdown livres (`claude.md`, `codex.md`).
  - Escrita manual / não validada.
  - Somente leitura nesta fase de coexistência.
- **`coordination/handoffs/` (PLURAL — NOVO CANÔNICO)**:
  - Armazena exclusivamente arquivos JSON atômicos nomeados `<handoffId>.json` (ex.: `HND-TREVAS-001-01.json`).
  - Governança exclusiva pela classe `HandoffStore`.
  - Conformidade obrigatória com `schemas/agent-handoff.schema.json`.
  - Imutabilidade absoluta pós-escrita (proibido sobrescrever ou atualizar).

---

## 7. Arquivos Legados Específicos de Provedores

Os arquivos `coordination/handoff/claude.md`, `coordination/handoff/codex.md` e `coordination/queue/claude.json` documentam o esforço inicial de engenharia reversa e correção de OCR do projeto.

- **Status**: Preservados como registros históricos de proveniência.
- **Autoridade**: Não constituem fonte canônica para o comportamento de novos agentes.
- **Ação Proibida**: Não devem ser apagados sumariamente nem promovidos a especificações arquiteturais.

---

## 8. Regras Editoriais e Catálogo: Fonte Canônica

A autoridade editorial do repositório é única e centralizada:
- **Fonte Canônica Editorial**: `docs/reference/cataloging-rules.md`.
- O arquivo `coordination/catalog_rules.md` é uma cartilha histórica/resumida. Em qualquer divergência, prevalece estritamente `docs/reference/cataloging-rules.md`.

---

## 9. Coordenação por Livro (`coordination/books/`)

Os arquivos presentes em `coordination/books/` (`daemon-medieval.md`, `daemon-tormenta.md`, `guia-de-itens-magicos.md`) contêm levantamentos minuciosos de estrutura de parágrafos, marcadores de atributos, taxas de erro de OCR e decisões de taxonomia.

- **Classificação**: `NEEDS_REVIEW`.
- **Estratégia Futura**: Em fases posteriores de migração, esses arquivos deverão ser revisados humanamente para compor a camada de **Book Context** (`docs/context/books/<bookId>.md`), alimentando de forma canônica o `ContextPackBuilder`.
- **Preservação**: Permanecem inalterados e protegidos contra exclusão até a conclusão dessa revisão.

---

## 10. Matriz de Fontes da Verdade

| Responsabilidade do Sistema | Fonte Canônica da Verdade |
|---|---|
| Princípios constitucionais e hierarquia de autoridade | `docs/architecture/constitution.md` |
| Contexto do projeto e objetivos arquiteturais | `docs/architecture/project-context.md` |
| Estágios do pipeline, gates e critérios de transição | `docs/architecture/pipeline.md` |
| Políticas de decisão, autoridade e autonomia de agentes | `docs/architecture/decision-policy.md` |
| Arquitetura do sistema de contexto e camadas | `docs/architecture/context-system.md` |
| Estrutura de Jobs de agentes | `schemas/agent-job.schema.json` |
| Estado persistente em tempo de execução de Jobs | `coordination/jobs/*.json` (via `JobStore`) |
| Estrutura de Handoffs de agentes | `schemas/agent-handoff.schema.json` |
| Estado persistente em tempo de execução de Handoffs | `coordination/handoffs/*.json` (via `HandoffStore`) |
| Estrutura e montagem de pacotes de contexto | `schemas/context-pack.schema.json` (via `ContextPackBuilder`) |
| Regras editoriais, taxonomia e catalogação | `docs/reference/cataloging-rules.md` |
| Modelo canônico de dados e entidades | `docs/reference/data-model.md` |
| Contratos e papéis específicos dos agentes | `docs/agents/*.md` |
| Decisões arquiteturais registradas | `docs/context/decisions/ADR-*.md` |
| Estratégia de migração e coexistência legada | `docs/architecture/legacy-coordination-migration.md` |

---

## 11. Modelo de Coexistência

Durante a fase de transição:
1. **Autoridade do Substrato Novo**: Toda execução automatizada de novos agentes é governada exclusivamente pelos schemas `schemas/agent-*.json`, pelas classes de `scripts/agents/` e pelos diretórios `coordination/jobs/` e `coordination/handoffs/`.
2. **Autoridade do Legado**: O ecossistema legado atua como repositório de consulta histórica e proveniência para operadores humanos e revisores.
3. **Isolamento de Escrita**: Novos agentes NÃO escrevem em `coordination/queue/` nem em `coordination/handoff/`.

---

## 12. Estado Alvo (Target State)

No estado final consolidado da arquitetura multiagente:
- **Gestão de Jobs**: 100% via `JobStore` em `coordination/jobs/`.
- **Gestão de Handoffs**: 100% via `HandoffStore` em `coordination/handoffs/`.
- **Carregamento de Contexto**: 100% determinístico via `ContextLoader`.
- **Fatiamento de Contexto**: 100% via `ContextPackBuilder` montando `ContextPack` estruturado.
- **Validação de Políticas e Gates**: 100% via `GateEngine`.
- **Decisão de Próxima Ação**: 100% via `OrchestratorStateSelector`.
- **Execução**: Despacho de agentes operacionais especializados e agnósticos a provedor de IA.
- **Legado**: Totalmente catalogado, migrado para Book Context ou arquivado em diretório histórico com trilha de proveniência preservada.

---

## 13. Fases Futuras de Migração (Planejamento)

A migração real será conduzida em fases rigorosamente sequenciais em missões futuras:

```text
Phase 0: Inventory & Classification
 ↓
Phase 1: Freeze New Legacy Writes
 ↓
Phase 2: Compatibility Analysis
 ↓
Phase 3: Dry-Run Migration
 ↓
Phase 4: Validation & Schema Enforcement
 ↓
Phase 5: Human Review & Conflict Resolution
 ↓
Phase 6: Cutover
 ↓
Phase 7: Archive & Preservation
```

- **Phase 0 — Inventory & Classification** *(Concluída na Missão 011)*: Mapeamento de todos os arquivos legados e formalização deste documento canônico.
- **Phase 1 — Freeze New Legacy Writes**: Bloqueio definitivo de novas escritas em `coordination/queue/` e `coordination/handoff/`.
- **Phase 2 — Compatibility Analysis**: Análise técnica e mapeamento de quais livros na fila legada requerem Jobs formais.
- **Phase 3 — Dry-Run Migration**: Execução de conversão em memória/staging gerando relatórios de equivalência sem tocar no repositório de produção.
- **Phase 4 — Validation & Schema Enforcement**: Validação estrita de todos os artefatos convertidos contra `agent-job.schema.json` e `agent-handoff.schema.json`.
- **Phase 5 — Human Review & Conflict Resolution**: Resolução por operador humano de todas as ambiguidades de OCR, direitos e atribuições.
- **Phase 6 — Cutover**: Transição operacional formal, ativando `coordination/jobs/` como única fonte de execução.
- **Phase 7 — Archive & Preservation**: Movimentação segura de arquivos legados obsoletos para arquivo histórico (ex.: `coordination/archive/`), mantendo integridade do Git.

> [!IMPORTANT]
> Nenhuma dessas fases de migração foi executada nesta missão documental.

---

## 14. Regras Fundamentais e Salvaguardas

### 14.1 Regra de Não-Migração Silenciosa (*No Silent Migration*)
Nenhum artefato legado pode ser implicitamente considerado como migrado ou assumido por um agente sem uma transformação formal registrada, validação determinística de schema e rastreabilidade da fonte de origem.

### 14.2 Proibição de Exclusão sem Aprovação Humana (*No Deletion Without Human Approval*)
A exclusão física de qualquer arquivo de coordenação legado (`queue/`, `handoff/`, `books/`) é estritamente proibida a agentes automatizados. Qualquer limpeza só poderá ocorrer mediante aprovação humana explícita após migração comprovada e verificação de backup.

### 14.3 Política de Rollback (Princípio de Isolamento Progressivo)
Durante futuras operações de migração:
1. Os arquivos originais permanecem intactos no disco.
2. Os novos artefatos são gerados em caminhos segregados.
3. Se qualquer erro ou inconsistência de schema for detectado, os novos artefatos transitórios são descartados, mantendo o estado original 100% íntegro.

### 14.4 Preservação de Identidade e Proveniência
Toda migração de dados ou contratos legados deve gerar um manifesto de proveniência registrando:
- Caminho e hash do artefato legado original;
- Identificador do novo Job/Handoff gerado;
- Timestamp da transformação e agente/operador responsável.

### 14.5 Gates de Migração
Antes de qualquer corte operacional (*cutover*), todos os gates técnicos devem ser validados:
1. Schema validation (0 erros);
2. Segurança de caminhos (*zero path traversal*);
3. Determinismo e ausência de colisões de IDs;
4. Proveniência integralmente registrada;
5. Suíte completa de testes verde (`pytest`, `validate_data.py`, `check_book_coverage.py`, `node --check app.js`);
6. Homologação e validação humana registrada.

### 14.6 Política de Falha
Caso ocorra qualquer erro durante processos futuros de migração:
- A operação é abortada imediatamente;
- Nenhuma alteração na origem é persistida;
- Nenhum artefato legado é removido;
- O erro é catalogado e enviado para análise de um operador humano.

---

## 15. Relações do Sistema

### 15.1 Relação com o Orquestrador
O componente `OrchestratorStateSelector` (e futuros executores de orquestração) opera **exclusivamente** sobre a estrutura canônica de Jobs (`coordination/jobs/`) e schemas formais. Ele **não lê** nem interage com arquivos em `coordination/queue/`. Toda compatibilidade deve ser tratada em camada externa de migração.

### 15.2 Neutralidade em Relação a Provedores de IA
A nova arquitetura e o processo de migração são completamente agnósticos a modelos ou plataformas de LLM (Claude, Codex, Gemini, Antigravity, OpenAI). Todas as decisões, validações e persistências operam sobre estruturas de dados abertas e verificáveis no repositório Git.
