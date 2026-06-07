# Handoff - Codex

## 2026-06-06 - app.js empty hub bug resolvido
- Li o diagnóstico do Claude no commit `666c2e6` (`claude-pilots`): na primeira carga, `state.globalFilters.books` começava vazio e sobrescrevia o filtro padrão com todos os livros.
- Corrigi `docs/assets/app.js` em `load()`: se `globalFilters.books` estiver vazio na carga inicial, usa `defaultFilters(globalFilterGroupsData())`; se já houver seleção, preserva via `filtersWithDefaults`.
- Validação feita: `node --check docs/assets/app.js` e `python scripts/validate_data.py`.
- Arquivo compartilhado tocado: `docs/assets/app.js`. Claude deve fazer merge/pull antes de novas mudanças nesse arquivo.
