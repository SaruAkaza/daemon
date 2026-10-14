# Handoff - Codex

## 2026-10-14 — Motor privado da Release C

- Branch `codex/release-c-batch-orchestrator`, baseada em
  `codex/legacy-publication-rights` (`fff33473`, PR #2). Status `needs_review`.
- `scripts/orchestrator/`: fila persistente, até três livros ativos,
  checkpoints com hashes/gates, dois retries transitórios (2s/8s), recuperação
  após kill, invalidação da etapa/sucessoras e proteção contra resultados tardios.
  Runtime externo ao checkout com lease POSIX; nenhum dado canônico foi alterado.
- Comandos do painel conectados ao motor via `CommandProcessor`; servidor
  privado compartilha a instância de `ReviewStore`. Modo público rejeita motor.
  SSE mostra progresso; corrigida duplicação de telas durante eventos concorrentes.
- Decisão humana deve citar o hash do snapshot. Aprovação técnica resulta em
  `APPROVED_PRIVATE` e job `approved`, mantendo `release=waiting`. Não usar o
  `DONE` técnico simplificado do plano para contornar o `GateEngine` canônico.
  Revisões obsoletas são substituídas sem inventar decisões humanas.
- CLI: `python -m scripts.orchestrator --demo --runtime-dir /tmp/daemon-demo --serve`.
  Cinco DOCXs sintéticos; nenhum livro real processado ou aprovado. Executores
  reais de extração/editorial/entidades/relações/frontend/QA ainda precisam
  de integração e certificação. A factory exige adapters e gates independentes.
- Validação local: 983 Python (28 novos, incluindo Chromium e kill/restart),
  46 Node, cobertura 65,92%; lint, sintaxe, dados, cobertura, sincronização,
  reconciliação e plano de migração aprovados. Demonstração CLI executada.
- Arquivos compartilhados tocados: `scripts/ops/{command_processor,review_store,
  ops_server}.py`, `scripts/agents/preview_server.py`, `docs/assets/site-{ui,
  state,ops}.mjs`. Faça merge/pull antes de alterá-los.
- Relatório: `docs/reports/2026-10-14-release-c-validation.md`.
  Contrato e uso: `docs/reference/batch-orchestrator.md`.
- Próximo trabalho: conectar executores reais com gates de limpeza/proveniência/
  páginas/cobertura; resolver as pendências do PR #2 antes de uma onda real.
  Não elevar de três para cinco vagas sem evidências e aprovação humana.

## 2026-10-14 — Plano e staging privado da migração

- Continuação no PR #2, branch `codex/legacy-publication-rights`.
  O CI de `b316432` passou antes desta extensão.
- Auditoria: nenhum dos 38 pilotos contém campos de páginas de origem;
  11.431 objetos com conteúdo. Não inferir página `1` nem transformar índices
  de parágrafos em páginas para fazer o gate passar.
- `scripts/prepare_source_migration.py`: diagnóstico por leitura, `--write-plan`,
  `--check` e `--stage`. O CI executa somente `--check`, sem staging do acervo.
- Plano salvo: `data/index/source-migration-plan.json`. Inclui hashes dos inputs
  e candidatos, mudanças de raiz antes/depois, auditoria de páginas e bloqueios.
- 38 candidatos foram materializados fora do checkout no runtime privado:
  8.838.526 bytes. Pacote identificado pelo hash
  `cdeda640ea8da31555de2db47d7ba8d026ceea7a79d279d4d1ccd7555ca573f3`.
  Outra máquina pode regenerar o pacote usando `--stage`.
- Os candidatos propõem corrigir/normalizar 33 `sourcePath`s e acrescentam
  variante física e revisão. IDs legados, referências, regras, valores,
  conteúdo e páginas são preservados. Tudo continua `NEEDS_HUMAN_REVIEW`.
- Nenhum candidato foi promovido. Não há modo de aplicação canônica nessa
  ferramenta. Alterações de inputs ou manifestos exigem regeneração do plano.
- Validação local: 955 Python (32 novos), 46 Node, cobertura 64,65%; lint,
  JSONs/schemas, cobertura, sincronização, sintaxe e verificações por leitura
  aprovados. Testes de limites, locks, edições existentes, symlinks e falhas de
  disco verificam que os originais e decisões existentes ficam intactos.
- Relatório: `docs/reports/2026-10-14-source-migration-preparation.md`.
  Contrato: `docs/reference/source-migration.md`.
- Próximo trabalho: evidências de versões e localizadores de páginas nos
  estágios de extração/editorial, antes de aplicar a migração definitiva.
  Direitos e release permanecem sujeitos aos manifestos e gates próprios.

## 2026-10-14 — Reconciliação de fontes e manifestos pendentes

- Continuação na branch `codex/legacy-publication-rights`, PR #2 em rascunho.
  O CI do commit anterior `086ec858` passou.
- Descoberta: os 281 caminhos do inventário histórico estão ausentes da árvore
  atual. Existem 269 DOCXs versionados; não reconstruir o inventário antigo
  automaticamente, pois IDs, entidades e páginas ainda dependem dele.
- `scripts/reconcile_sources.py`: diagnóstico por leitura, `--write` para
  evidências e manifestos pendentes, `--check` para verificação sem escrita.
  A checagem está no workflow `Validate`.
- Relatório gerado: `data/index/source-reconciliation.json`. Os 38 pilotos têm
  arquivo candidato identificado: 25 por caminho exato e 13 por nome único.
  Bytes de todos os candidatos conferidos contra Git; variantes recebem IDs
  `file-<SHA-256>`, sem renomear livros ou promover aliases de identidade.
- 38 manifestos novos em `data/source-manifests/`, todos `UNKNOWN`, `private`,
  `NOT_PUBLIC`. Decisões existentes são preservadas; não há autorização nova.
- Inventário antigo: 196 IDs têm um candidato nominal, 83 nenhum e 2 múltiplos.
  Essas sugestões e os vínculos de pilotos continuam em `NEEDS_HUMAN_REVIEW`.
- Preflight adicional: `sourceFile` também precisa corresponder ao inventário,
  mesmo quando `sourcePath` não é declarado. Arquivo compartilhado tocado:
  `scripts/legacy_publication.py`; faça merge/pull antes de editá-lo.
- Validação local: 923 Python (incluindo Chromium), 46 Node, cobertura 64,33%;
  lint, dados/schemas, cobertura de páginas, sincronização, sintaxe e `--check`
  aprovados. O teste de limpeza do worktree permaneceu sem alterações.
- Relatório: `docs/reports/2026-10-14-source-reconciliation.md`.
  Contrato: `docs/reference/source-reconciliation.md`.
- Próximo trabalho: revisar versões/proveniência histórica e registrar decisões
  de migração e direitos. Nenhum piloto, livro, entidade, área ou asset público
  foi reescrito nesta rodada. Release C continua planejada.

## 2026-10-14 — Retomada após a consolidação: gate de publicação legada

- Base recuperada do GitHub: `main` em `50ec6ae`; PR #1 já integrado.
- Branch de trabalho: `codex/legacy-publication-rights`.
- Os publicadores de áreas e pilotos agora exigem manifestos de direitos
  validados e vinculados ao inventário antes de gravar arquivos públicos.
  `--check-only` faz a checagem sem escrita. A cópia integral exige permissão
  explícita `FULL_TEXT`; resumo/metadados usam o projetor público existente.
- Arquivo compartilhado tocado: `scripts/common.py`. O escritor JSON protege
  também as gravações diretas de geradores individuais e rotinas de limpeza.
  Faça merge/pull antes de novas mudanças no escritor ou nos publicadores.
- Dados, originais, assets publicados e schemas foram preservados. Não houve
  reconstrução pública do acervo nem fabricação de manifestos de autorização.
- Diagnóstico somente de leitura: 275 fontes das áreas sem manifestos;
  38 pilotos, dos quais 4 têm IDs ausentes e 25 têm caminho divergente do
  inventário. Próximo trabalho: reconciliar identidade de fontes e direitos.
- Relatório e resultados: `docs/reports/2026-10-14-legacy-publication-rights.md`.
  Orientações: `docs/reference/legacy-publication.md`.
- Status da mudança: `needs_review`. O aceite de integração do PR #1 é
  específico à consolidação anterior. O motor de batch da Release C permanece
  planejado; não foi implementado nesta rodada.

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
