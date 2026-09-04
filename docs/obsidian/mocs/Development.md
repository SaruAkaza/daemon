---
type: moc
area: development
---
# MOC — Desenvolvimento

## Entrada
- [[AGENTS|AGENTS.md]]
- [[docs/architecture/project-context|Project Context]]
- [[coordination/README|Coordination]]

## Qualidade
```bash
python -m pytest -q
python scripts/validate_data.py
python scripts/check_book_coverage.py
node --check docs/assets/app.js
```

Consulte [[docs/architecture/pipeline|Pipeline]] para os gates oficiais.

## Branch atual
`feat/multiagent-context-v1`

## Executor principal
Antigravity + Gemini 3.7 High.
