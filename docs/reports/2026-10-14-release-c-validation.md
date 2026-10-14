# Validação da Release C — 2026-10-14

Implementação na branch `codex/release-c-batch-orchestrator`, sobre
`codex/legacy-publication-rights` (`fff33473`). Depende do PR #2 de proveniência;
não inclui promoção da migração, revisão de livros reais ou publicação nova.

## Resultado

O motor privado agora executa uma fila persistente com três vagas, ordenação
versionada e determinística, checkpoints validados, classificação de falhas,
retentativas limitadas, pausa na fronteira da etapa, retomada após crash e
invalidação apenas da etapa alterada e suas sucessoras. Jobs e revisões usam
os contratos existentes; não houve mudanças nos schemas globais.

O painel autenticado conecta pausa, retomada, prioridade, reprocessamento,
retirada da fila e decisões humanas ao motor. Exibe etapa/progresso e recebe
atualizações por SSE. Renderizações antigas são descartadas para impedir telas
de revisão duplicadas quando chegam vários eventos próximos.

A conclusão técnica fica `READY_FOR_HUMAN_APPROVAL`; uma decisão humana ligada
ao SHA-256 do snapshot produz `APPROVED_PRIVATE` e job canônico `approved`.
`release` permanece `waiting`. Essa distinção preserva o gate canônico que exige
release e validação humana para `done`. Revisões substituídas por reprocessamento
são marcadas `SUPERSEDED`, sem fabricar uma decisão humana.

## Evidências locais

| Verificação | Resultado |
| --- | --- |
| Suíte Python completa, incluindo Chromium | 983 aprovados |
| Novos cenários Python da Release C | 28 aprovados |
| Suíte Node do frontend | 46 aprovados |
| Cobertura de scripts | 65,92% |
| Ruff e sintaxe dos módulos frontend | Aprovados |
| Dados/schemas e cobertura do inventário histórico | Aprovados |
| Sincronização publicada | 14 áreas e resumo sincronizados |
| Reconciliação e plano de migração, `--check` | Aprovados, somente leitura |
| Demonstração CLI com cinco DOCXs sintéticos | Executada, três vagas |
| Arquivos de acervo, dados canônicos e schemas alterados | Nenhum |

A demonstração CLI termina com A, D e E esperando revisão final, B em revisão
por ambiguidade e C bloqueado por falha determinística. D retoma após uma falha
transitória. Nenhum livro de demonstração recebe aprovação automática.

Os testes adicionais matam um processo durante a etapa editorial e comprovam
que os checkpoints de fonte/extração não são reexecutados. Reprocessar entidades
de E preserva fonte, extração e editorial. Ensaios com três threads bloqueadas
conferem o limite real de concorrência e impedem que um resultado atrasado
revalide uma etapa substituída. Também verificam arquivos/schemas/gates inválidos,
fonte alterada, checkpoint corrompido, replay de comandos, deadlines de retry,
lease exclusiva, revisão obsoleta e bloqueio de publicação.

O teste Chromium inicia um servidor real, retoma o livro pelo painel, aguarda
a revisão e registra uma aprovação **somente sintética**, ligada ao snapshot.
Confere que há uma única tela de revisão e que release permanece pendente.

## Limites e próximo passo

Os adaptadores semânticos do acervo real ainda precisam de integração e
certificação. A API exige executores/gates confiáveis e versionados para as seis
etapas entre extração e QA; validação de JSON não substitui limpeza, páginas,
cobertura e revisão editorial. A única execução embutida além da custódia de
fonte é a demonstração sintética. O runtime é privado, externo ao checkout,
e depende de Linux/POSIX; callbacks externos devem usar timeouts.

A elevação para quatro/cinco vagas requer as oito evidências previstas e uma
aprovação humana do snapshot de evidências. Não foi realizada. Antes de uma onda
real, conectar os executores existentes com gates de limpeza/cobertura e resolver
proveniência/páginas dos candidatos do PR #2. Direitos e publicação continuam
sob revisão própria. Instruções: [Motor de lotes](../reference/batch-orchestrator.md).
