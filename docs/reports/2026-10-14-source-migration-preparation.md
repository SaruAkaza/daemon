# Plano e staging privado de proveniência — 2026-10-14

Status: `NEEDS_HUMAN_REVIEW`.

Esta rodada continua o PR #2 depois da reconciliação de fontes. O
[CI de `b316432`](https://github.com/SaruAkaza/daemon/actions/runs/38630972447)
passou antes desta extensão. A preparação abaixo não aplica uma migração ao
acervo canônico nem concede direitos ou aceite de release.

## Achado e resultado

Nenhum dos 38 pilotos registra `page`, `pages`, `sourcePage` ou `sourcePages`,
inclusive nas camadas internas do JSON. A auditoria identificou 11.431 objetos
com conteúdo nesses pilotos. A ausência de páginas impede tratar a mudança de
fonte como proveniência definitivamente validada.

Foram preparados:

- um plano determinístico em `data/index/source-migration-plan.json`;
- 38 cópias propostas em staging privado, com 8.838.526 bytes de JSON;
- 33 propostas de atualização/normalização de `sourcePath`;
- 38 vínculos propostos de `sourceVariantId` e metadados de revisão;
- zero mudanças necessárias em `sourceFile`, pois os nomes já correspondem
  aos arquivos candidatos identificados;
- zero promoções canônicas ou públicas.

O pacote local desta execução está fora do checkout, em
`/workspace/.daemon_runtime/source-migrations/daemon/cdeda640ea8da31555de2db47d7ba8d026ceea7a79d279d4d1ccd7555ca573f3/`.
Esse caminho é específico deste ambiente; outro ambiente pode materializar o
mesmo plano com `python scripts/prepare_source_migration.py --stage`.

Cada cópia preserva os IDs legados de fonte/entidades/seções, as referências,
regras, valores, conteúdo e declarações de página originais. Somente os campos
de metadados de raiz registrados no plano são propostos para mudança. Não foi
inventada uma página inicial ou convertida a posição de parágrafo em página.

## Verificações de preparação

- Custódia e hashes das fontes são reconferidos antes da preparação.
- O relatório de reconciliação e os manifestos salvos precisam ser atuais.
- Pilotos, manifestos, plano e cópias propostas ficam vinculados por hashes.
- Alterações de input ou decisão de direitos tornam o plano salvo obsoleto.
- As propostas mantêm `NEEDS_HUMAN_REVIEW`, versão de origem não verificada e
  `promotionAllowed: false` / `publicReleaseAllowed: false`.
- Staging usa os componentes existentes de runtime, limites e staging. Exige
  destino externo ao checkout e no mesmo filesystem, com pacote privado,
  lock exclusivo, construção temporária e verificação antes do rename final.
- Pacotes existentes são verificados sem regravação. Conflitos ou edições
  humanas são preservados; falhas de escrita limpam apenas o temporário próprio.

O CI acrescenta `prepare_source_migration.py --check`, somente de leitura.
O staging do acervo real não é criado durante o CI.

## Validação local

| Gate | Resultado |
| --- | --- |
| Suíte Python completa, incluindo Chromium | 955 aprovados, nenhum ignorado |
| Testes novos da preparação/staging, incluídos no total | 32 aprovados |
| Publicação, reconciliação e staging, incluídos no total | 114 aprovados |
| Testes Node | 46 aprovados |
| Cobertura Python | 64,65%; mínimo de 15% preservado |
| Lint de todos os scripts | PASS |
| JSONs/schemas e cobertura das páginas existentes | PASS, 281 livros |
| Sincronização publicada e sintaxe | 14 áreas + resumo e 6 módulos, PASS |
| Reconciliação e plano por leitura | PASS |
| Staging real e integridade dos destinos originais | PASS |

Os testes verificam preservação dos campos de página e conteúdo, valores de
página inválidos/booleanos, planos obsoletos, metadados preexistentes, staging
em destinos proibidos, aliases por symlink, pacotes editados, locks concorrentes,
limites de recursos e falha de disco após escrita parcial. Fixtures usam somente
conteúdo sintético.

O novo dado versionado desta rodada é o plano de revisão. Os conteúdos propostos
ficam exclusivamente no runtime privado. Inventário original, pilotos, entidades,
áreas, fontes, schemas e assets públicos continuam idênticos à base.

## Próxima etapa

Obter evidências da versão de fonte efetivamente usada por cada piloto e dos
localizadores de páginas correspondentes. Registrar essas decisões no estágio
de origem antes da aplicação definitiva. O aceite dos vínculos físicos e dos
direitos não substitui a validação das páginas.

Contrato e comandos: [Preparação privada da migração](../reference/source-migration.md).
