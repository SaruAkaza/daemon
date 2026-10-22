# Reconciliação das fontes atuais — 2026-10-14

Status: `NEEDS_HUMAN_REVIEW`.

Esta rodada continua a branch `codex/legacy-publication-rights` e o PR #2.
O CI da primeira entrega, commit `086ec858f73adbf75875578173446e79eb0d2ecb`,
[terminou com sucesso](https://github.com/SaruAkaza/daemon/actions/runs/38628948256).
Os resultados abaixo se referem à reconciliação acrescentada depois dessa entrega.

## Achado principal

Nenhum dos 281 caminhos registrados no inventário histórico existe na árvore
Git atual. O inventário apontava para a raiz `Livros/`, enquanto o acervo atual
contém 269 DOCXs versionados em `Livros/word/`, além de 3 arquivos markdown.
O diagnóstico inicial de 4 IDs ausentes e 25 caminhos divergentes entre pilotos
e inventário era correto, mas não cobria essa obsolescência global dos caminhos.

O inventário canônico permanece intacto: alterar seus IDs/caminhos diretamente
afetaria entidades, páginas, referências e assets históricos. A nova ferramenta
registra as evidências para uma migração deliberada, sem promover equivalências
entre PDFs e DOCXs pelo nome.

## Evidências produzidas

| Verificação | Resultado |
| --- | --- |
| Fontes PDF/DOCX na árvore atual | 269 DOCXs |
| Caminhos históricos ausentes da árvore atual | 281 de 281 |
| Pilotos com arquivo candidato identificado | 38 de 38 |
| Correspondência por caminho exato declarado | 25 |
| Correspondência por nome de arquivo único | 13 |
| Arquivos candidatos com bytes conferidos contra o Git | 38 |
| Manifestos novos de variantes | 38, todos `UNKNOWN` / `private` / `NOT_PUBLIC` |
| Inventário histórico com um candidato nominal | 196 |
| Inventário histórico sem candidato nominal | 83 |
| Inventário histórico com candidatos nominais ambíguos | 2 |

O relatório determinístico está em `data/index/source-reconciliation.json`.
Inclui OID da árvore de fontes, SHA-256 dos inputs e arquivos, IDs separados de
variantes, caminhos e método de identificação. Os manifestos usam o schema
existente e IDs `file-<SHA-256>`, sem substituir os IDs históricos dos livros.
Nenhum texto dos livros foi extraído ou acrescentado aos novos artefatos.

Todos os vínculos continuam com `NEEDS_HUMAN_REVIEW`. Conferir o arquivo atual
não comprova a versão exata que gerou um piloto histórico, a equivalência do OCR
com o PDF antigo, a correspondência entre suas páginas ou o direito de distribuição.

## Código e gates

- `reconcile_sources.py` faz diagnóstico somente de leitura por padrão;
  `--write` grava evidências e manifestos pendentes, e `--check` verifica sua
  atualidade sem reconstruir ou publicar conteúdo.
- Caminhos que escapam de `Livros/`, fontes não versionadas, conteúdo local
  diferente do blob Git, symlinks e nomes ambíguos não são certificados.
- Manifestos existentes com identidade compatível são preservados byte a byte.
  Duplicatas e conflitos bloqueiam o plano antes de escrever.
- O preflight de publicação verifica também `sourceFile`: omitir `sourcePath`
  não permite que um DOCX use a autorização de um PDF ou de outra edição.
- O CI acrescenta a checagem de reconciliação por leitura.

## Validação local

Linux, Python 3.12.14, Node 24.19.0 e Playwright 1.62.0 (Chromium).

| Gate | Resultado |
| --- | --- |
| Suíte Python completa, incluindo Chromium | 923 aprovados, nenhum ignorado |
| Publicação legada e reconciliação, incluídos no total | 82 aprovados |
| Testes Node | 46 aprovados |
| Cobertura Python | 64,33%; mínimo de 15% preservado |
| Lint, JSONs e schemas | PASS |
| Cobertura de páginas | 281 livros, nenhum erro |
| Sincronização publicada e sintaxe do frontend | 14 áreas + resumo e 6 módulos, PASS |
| Verificação read-only dos artefatos de reconciliação | PASS |

Um teste existente exige que `data/` não tenha mudanças não commitadas. A
primeira execução completa sinalizou os novos registros ainda não commitados.
Após registrar esses artefatos no Git, a suíte passou sem alteração desse teste.

Foram adicionados somente o relatório de reconciliação e os 38 manifestos sob
`data/`; o inventário original, pilotos, entidades, áreas, fontes, schemas e
assets públicos permanecem idênticos à base. A conferência de publicação mantém
as variantes candidatas sem autoridade canônica para liberar os pilotos antigos.

## Próxima etapa

Revisar a identidade e as versões históricas dos pilotos, incluindo os 13
vínculos por nome único e as sugestões de 196/83/2 fontes do inventário. Registrar
decisões de migração e direitos; depois migrar proveniência por estágio, sem
destruir as referências antigas. A Release C continua planejada.

Comandos e alcance: [Reconciliação de fontes legadas](../reference/source-reconciliation.md).
