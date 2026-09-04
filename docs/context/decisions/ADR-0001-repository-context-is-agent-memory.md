# ADR-0001 — Repository Context Is Agent Memory

## Status
Accepted

## Context
Em sistemas multiagentes baseados em modelos de linguagem (LLMs), a dependência de janelas de contexto voláteis, históricos de chat em memória e estados locais entre execuções causa perda de rastreabilidade, inconsistência na aplicação de regras e bloqueia a alternância entre diferentes modelos ou ambientes de execução.

No projeto **Daemon Tools**, diferentes provedores ou ferramentas (como Antigravity, Gemini, Codex, Claude ou scripts locais) precisam cooperar no processamento de dezenas de livros e milhares de entidades sem risco de esquecimento ou alucinação cumulativa.

## Decision
Fica estabelecido que **a memória durável de todos os agentes reside exclusivamente no repositório Git versionado**.

Nenhum agente, executor ou automação deve assumir que outro agente compartilha histórico de conversação prévia. Todo o conhecimento de contexto, regras editoriais, contratos de livros, status de jobs e handoffs deve ser persistido em arquivos versionados (`docs/architecture/`, `docs/reference/`, `docs/context/`, `coordination/`).

## Consequences
### Positivas
- **Independência de Provedor**: Qualquer modelo de linguagem ou executor (Gemini, Claude, GPT, etc.) pode assumir uma tarefa a qualquer momento lendo apenas o pacote de contexto fornecido.
- **Auditabilidade e Reprodutibilidade**: Todo o histórico de decisões e transformações de dados fica registrado em commits e relatórios determinísticos.
- **Isolamento de Erros**: Falhas de uma sessão ou alucinações não contaminam as execuções subsequentes.

### Negativas / Custos
- Exige rigor na escrita de handoffs e na manutenção contínua da documentação no repositório.
- Ações e decisões não registradas em arquivos são tratadas como inexistentes pelo sistema.

## Supersedes
None
