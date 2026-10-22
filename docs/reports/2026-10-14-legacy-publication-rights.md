# Retomada: política de direitos no fluxo legado — 2026-10-14

Status: `NEEDS_HUMAN_REVIEW`.

Base: `main`, commit `50ec6aeb6a67e21a1cf5219b815c9179e1f0a30c`, após a
integração do PR #1. Esta rodada trata a pendência de direitos registrada no
relatório de consolidação; não certifica livros nem autoriza uma release pública.

## Alteração

- `build_github_pages_site.py` e `build_pilot_index.py` verificam todos os inputs
  antes de gravar qualquer destino. `--check-only` verifica sem escrita.
- `common.write_json` protege também gravações diretas de geradores individuais
  e rotinas de limpeza em `docs/assets/data/`. Saídas locais/canônicas continuam
  disponíveis sem autorização de distribuição.
- As fontes primárias, secundárias e declaradas no resumo/índice exigem
  manifestos válidos do schema existente, com correspondência de ID, hash,
  caminho e extensão no inventário. Caminhos de pilotos também são conferidos.
- A cópia integral exige `AUTHORIZED`/`PUBLIC_DOMAIN`, `public`, `FULL_TEXT`.
  Permissões de resumo/metadados continuam sendo atendidas pelo projetor público;
  o publicador bruto não pode converter essas permissões em texto integral.
- A escrita usa snapshots dos payloads verificados. O índice de pilotos é
  publicado da memória, sem reler o índice canônico após o gate.
- Falhas de política preservam os arquivos existentes. Após preflight aprovado,
  os publicadores removem JSONs obsoletos apenas em seus diretórios de saída.

Contrato e comandos: [Publicação dos JSONs legados](../reference/legacy-publication.md).

## Verificações e limites

Ambiente: Linux, Python 3.12.14, Node 24.19.0 e Playwright 1.62.0 (Chromium).

| Verificação | Resultado |
| --- | --- |
| Suíte Python completa, incluindo navegador | 898 aprovados, nenhum ignorado |
| Novos testes da publicação legada, incluídos no total | 57 aprovados |
| Testes dos módulos Node | 46 aprovados |
| Cobertura Python | 64,02%; mínimo de 15% preservado |
| Lint de todos os scripts Python | PASS |
| JSONs e schemas | PASS |
| Cobertura de páginas | 281 livros, nenhum erro |
| Sincronização dos assets existentes | 14 áreas e resumo idênticos |
| Sintaxe JS/MJS | 6 módulos, PASS |
| Integridade do diff e dos dados protegidos | PASS |

Comandos: `python -m pytest -q --cov=scripts --cov-report=term --cov-fail-under=15`,
`node --test tests/frontend/*.test.mjs`, `python -m ruff check scripts/`,
`python scripts/validate_data.py`, `python scripts/check_book_coverage.py`,
`python scripts/check_published_data_sync.py` e `node --check` em cada módulo.
O CI do PR é uma evidência separada destes resultados locais.

Não há alterações em `data/`, `Livros/`, `docs/assets/data/` ou `schemas/`.
Os novos testes usam conteúdo sintético, incluindo os testes de CLI em uma cópia
temporária dos scripts e schemas; não dependem de direitos ou runtime privados.

O checkout inicial omitira os livros para evitar baixar o acervo inteiro. Dois
testes de custódia falharam porque `Livros/word/feito/animalidade.docx` estava
ausente; o arquivo versionado foi recuperado sem alteração e os testes passaram.
Nenhum teste foi relaxado ou removido para contornar essa ausência.

A cópia após o gate ainda não oferece rollback transacional para falhas de disco.
Esta rodada não saneia assets históricos nem transforma o verificador de
sincronização em certificado de autorização de publicação.

## Reconciliação ainda necessária

Uma verificação somente de leitura do acervo atual registrou:

- 275 fontes usadas nas áreas sem os manifestos exigidos; o preflight bloqueia
  a reconstrução pública com código de saída `1`.
- 38 pilotos locais; 4 IDs não existem no inventário atual:
  `anime-rpg-supers-monstros-viloes`, `anjos-angelicos-sicarios`,
  `aprimoramentos-tormenta`, `cabala-forum`.
- 25 pilotos com `sourcePath` diferente do caminho inventariado para o mesmo ID.
  Isso exige reconciliação da identidade de PDF/DOCX/edição, sem reutilizar
  permissões de fontes diferentes nem alterar os originais.

Próxima retomada: reconciliar esses vínculos, obter decisões de direitos por
fonte e preparar projeções públicas de metadados/resumos. O motor de batch da
Release C permanece planejado no plano de implementação existente.
