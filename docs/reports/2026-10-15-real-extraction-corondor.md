# Extração privada de Corondor — 2026-10-15

Branch `codex/real-extraction-review-adapters`, sobre a Release C (PR #3).
O ensaio usa a variante física de Corondor, sem aprovar seu vínculo ao inventário
histórico ou promover a migração do PR #2.

## Resultado do ensaio real

| Evidência | Resultado |
| --- | --- |
| Arquivo | `Livros/word/feito/Corondor.docx` |
| SHA-256 | `57dd236dd3e0a36888cc88f16a4d60f0121c9159c866a96475633e9fa2a98367` |
| Tamanho da fonte | 9.466.067 bytes |
| Blocos preservados | 2.609 |
| Parágrafos do documento principal | 2.605 |
| Parágrafos de notas | 4 |
| Partes XML com texto | 3 |
| Nós de texto Word extraídos | 7.196 de 7.196 |
| Tabelas | 14 |
| Partes de mídia | 118 |
| Marcas de última renderização | 89, sem certificação de páginas |
| Normalizações de ligaturas aplicadas | 0 |
| Paginação da obra original | Desconhecida, `null` |
| Estado operacional | `NEEDS_HUMAN_REVIEW`, etapa `extraction` |
| Checkpoints concluídos | Somente custódia da fonte; extração não aprovada |

A execução criou uma revisão por `SOURCE_PAGE_MAPPING_REQUIRED` e
`VISUAL_CONTENT_REQUIRES_REVIEW`. O relatório de extração preserva texto bruto
e normalizado, localizadores e hashes. Não foi publicada nenhuma passagem do
livro neste relatório ou nos novos testes.

Runtime local: `/workspace/.daemon_runtime/real-extraction-corondor-20261015`.
O registro privado usa o ID físico `file-<SHA-256>`; manifesto permanece
`UNKNOWN`, `private`, `NOT_PUBLIC`. Os arquivos privados não são versionados.
O pacote pode ser regenerado com a factory e esse manifesto em outra máquina.

O artefato desta tentativa tem 1.389.447 bytes, SHA-256
`ad889fea2156f4dc238783534bd89d4b3097f0e8f2a7e720d0bf70d06591f513`.
Snapshot da revisão:
`70d50a834bcb5c3f8f8c0911b2d73f0028f39a99eec052c10e3923c8847d40eb`.
IDs de execução/diretórios identificam a tentativa; seus hashes podem mudar
ao regenerar o pacote. O hash da fonte deve permanecer igual.

## Integração e limites

Foram conectadas a extração determinística de PDF/DOCX e a preparação editorial.
Um PDF sintético simples passa a extração com índices físicos e para no gate
editorial de classificação. O DOCX real para antes de categorizar porque não
há prova de páginas nem revisão de seu conteúdo visual.

O motor registra evidências de uma etapa rejeitada sem criar checkpoint para
ela. O painel permite download autenticado dos artefatos atuais; revalida os
hashes e bloqueia referências antigas, caminhos externos e acesso público.
Revisões de correção não avançam a etapa por mera aprovação humana sem corrigir
as entradas. O gate de publicação e o critério canônico de `done` permanecem.

Executores semânticos de entidades/relações e os adapters finais de frontend/QA
ainda precisam de implementação/certificação. A preparação editorial registra
destinos pendentes e não fabrica classificações. A migração dos pilotos continua
pendente. Não foram alterados fonte, inventário, pilotos, entidades, schemas ou
assets de dados publicados.

## Validação

Os testes usam apenas fontes sintéticas de autoria do projeto. Cobrem PDF com
página vazia, vetores, DOCX com tabelas, cabeçalhos/rodapés, quebras não
certificadas, campos, alterações rastreadas e texto aninhado, preservação de
valores, alteração de artefatos/contratos, retomada, limites de recursos, CLI e
download autenticado no HTTP real e no Chromium. Resultados finais dos gates
locais:

| Gate | Resultado |
| --- | --- |
| Suíte Python completa, incluindo Chromium | 1.002 aprovados |
| Novos testes da integração real | 18 aprovados |
| Suíte Node | 46 aprovados |
| Cobertura de scripts | 66,54% |
| Ruff e sintaxe frontend | Aprovados |
| Dados/schemas, cobertura de livros e sincronização | Aprovados |
| Reconciliação e plano de migração (`--check`) | Aprovados, somente leitura |

Próximo trabalho: obter prova de edição/páginas e revisar o conteúdo visual da
variante física antes de liberar a extração para catalogação. Não converter
marcas de renderização ou blocos por tamanho em páginas para eliminar a pendência.

Uso e contrato: [Extração real](../reference/real-extraction.md).
