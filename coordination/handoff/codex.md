# Handoff - Codex

## 2026-06-06 - app.js empty hub bug resolvido
- Li o diagnóstico do Claude no commit `666c2e6` (`claude-pilots`): na primeira carga, `state.globalFilters.books` começava vazio e sobrescrevia o filtro padrão com todos os livros.
- Corrigi `docs/assets/app.js` em `load()`: se `globalFilters.books` estiver vazio na carga inicial, usa `defaultFilters(globalFilterGroupsData())`; se já houver seleção, preserva via `filtersWithDefaults`.
- Validação feita: `node --check docs/assets/app.js` e `python scripts/validate_data.py`.
- Arquivo compartilhado tocado: `docs/assets/app.js`. Claude deve fazer merge/pull antes de novas mudanças nesse arquivo.

## 2026-06-06 - Corondor em pilot_review
- Livro processado pelo Codex: `Corondor.docx`.
- Gerador novo: `scripts/build_corondor_pilot.py`.
- Saidas: `data/pilot/corondor.json` e `docs/assets/data/pilot/corondor.json`.
- Indice regenerado por `scripts/build_pilot_index.py`.
- DOCX movido para `Livros/word/feito/Corondor.docx`.
- Validacao feita: `python scripts/validate_data.py`, `node --check docs/assets/app.js`, `python -m pytest tests\test_editorial_catalog_ui.py tests\test_validate_data.py`.
- Status em `coordination/book_assignments.md`: `Corondor.docx` -> `pilot_review`.
