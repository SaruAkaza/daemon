---
type: moc
area: development
---
# MOC — Desenvolvimento

## Repositórios Remotos
- `origin` → `https://github.com/SaruAkaza/daemon.git` (Repositório de desenvolvimento)
- `upstream` → `https://github.com/guraassessoria/daemon.git` (Repositório oficial / release)

Consulte o [[docs/context/decisions/ADR-0003-development-fork-and-upstream-release-model|ADR-0003]] para o fluxo de desenvolvimento fork/upstream.

## Branch de Trabalho Atual
`feat/multiagent-context-v1`

## Entrada para Agentes
- [[AGENTS|AGENTS.md]]
- [[docs/architecture/project-context|Project Context]]
- [[coordination/README|Coordination]]

## Baseline de Testes e Validação

```powershell
python -m pytest tests/agents -q
python -m pytest -q
python scripts/validate_data.py
python scripts/check_book_coverage.py
node --check docs/assets/app.js
```

> **Atenção**: Consulte [[docs/architecture/pipeline|Pipeline]] para a definição canônica e completa de todos os gates.

## Executor Principal Nesta Fase
Antigravity + Gemini 3.7 High.
