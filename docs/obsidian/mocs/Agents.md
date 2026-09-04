---
type: moc
area: agents
---
# MOC — Agentes

## Coordenação
- [[docs/agents/orchestrator|Daemon Orchestrator]]

## Especialistas
- [[docs/agents/source-agent|Source Agent]]
- [[docs/agents/extraction-agent|Extraction Agent]]
- [[docs/agents/editorial-agent|Editorial Agent]]
- [[docs/agents/entity-agent|Entity Agent]]
- [[docs/agents/relations-agent|Relations Agent]]
- [[docs/agents/frontend-agent|Frontend & Search Agent]]
- [[docs/agents/qa-release-agent|QA & Release Agent]]

## Ciclo de Execução

```text
Orchestrator
     ↓
Context Pack
     ↓
Specialist
     ↓
Handoff
     ↓
Gate / QA
```

## Contexto e Contratos
- [[docs/architecture/context-system|Context System]]
- [[docs/context/domain/taxonomy|Taxonomy]]
- [[docs/context/domain/entity-patterns|Entity Patterns]]
- [[docs/context/domain/relation-types|Relation Types]]

## Executor Atual

> Atualmente os papéis são executados principalmente por Antigravity + Gemini 3.7 High.

> Papel lógico e modelo executor são conceitos separados. A arquitetura permanece provider-neutral.
