---
type: moc
area: architecture
---
# MOC — Arquitetura

## Núcleo
- [[docs/architecture/constitution|Constitution]]
- [[docs/architecture/project-context|Project Context]]
- [[docs/architecture/pipeline|Pipeline]]
- [[docs/architecture/context-system|Context System]]
- [[docs/architecture/decision-policy|Decision Policy]]

## Fluxo da Pipeline

```text
Source
 ↓
Extraction
 ↓
Editorial
 ↓
Entities
 ↓
Relations
 ↓
Frontend
 ↓
QA
 ↓
Release
 ↓
Human Validation
 ↓
Done
```

Consulte [[docs/architecture/pipeline|Pipeline]] para a definição canônica dos gates e critérios de transição.

## Mapas Relacionados
- [[docs/obsidian/mocs/Agents|Mapa dos Agentes]]
- [[docs/obsidian/mocs/Decisions|Mapa de Decisões]]
- [[docs/obsidian/mocs/Development|Mapa de Desenvolvimento]]
