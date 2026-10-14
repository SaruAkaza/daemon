# Reconciliação de fontes legadas

O inventário histórico e os pilotos usam identificadores de livros; um mesmo
livro pode ter PDF, DOCX de OCR, edições diferentes e cópias movidas. Esses
arquivos não devem compartilhar permissões automaticamente.

`scripts/reconcile_sources.py` produz evidências para revisão sem reconstruir
o inventário canônico, reescrever pilotos, processar o texto ou publicar dados.

## Identificação e custódia

O script inspeciona a árvore `Livros/` do commit atual usando metadados Git.
Somente arquivos PDF/DOCX regulares versionados podem ser candidatos. O script
não baixa, move, modifica ou remove fontes.

Para cada piloto:

1. Usa o `sourcePath` declarado quando esse caminho existe na árvore Git.
2. Se o caminho está ausente, usa `sourceFile` ou o basename do caminho como
   candidato apenas quando há exatamente um arquivo versionado com esse nome.
3. Registra conflitos entre caminho e nome, ausência de fonte e nomes ambíguos.
   Não escolhe o primeiro resultado nem usa aproximação de título nesse vínculo.
4. Confere os bytes locais contra o blob Git e calcula SHA-256. Arquivos não
   materializados no checkout, modificados ou representados por symlinks não
   recebem certificação de custódia.

Cada arquivo identificado recebe um ID de variante `file-<SHA-256>`. Os IDs
legados dos livros permanecem no relatório e nos dados originais. A relação
entre um piloto e uma variante continua em `NEEDS_HUMAN_REVIEW`: identificar o
arquivo atual não comprova qual versão produziu um JSON histórico nem certifica
a equivalência entre o OCR e o PDF antigo.

Para o inventário antigo, nomes normalizados e sufixos de OCR geram somente
listas de candidatos para revisão. Essas sugestões não viram aliases, relações
canônicas ou permissões de publicação.

## Artefatos e comandos

```bash
# Diagnóstico sem escrita
python scripts/reconcile_sources.py

# Gravar o relatório e os manifestos pendentes que ainda não existem
python scripts/reconcile_sources.py --write

# Conferir os artefatos existentes sem modificá-los
python scripts/reconcile_sources.py --check
```

`--repo-root` permite executar os mesmos comandos em outro checkout. Fontes
usadas pelos pilotos precisam estar materializadas para a verificação de hashes;
em um checkout parcial, o script distingue essa situação de uma fonte ausente
da árvore Git.

O relatório fica em `data/index/source-reconciliation.json`. Ele registra o OID
da árvore de fontes, hashes dos inputs, caminhos candidatos, métodos de busca e
variantes verificadas. Commits que alteram apenas código/documentação não mudam
essa referência. Mudanças nos inputs ou nas fontes tornam o relatório obsoleto;
o CI verifica isso por leitura com `--check`.

Os manifestos em `data/source-manifests/` usam o schema global existente. Novos
registros nascem com `rightsStatus: UNKNOWN`, `visibility: private` e
`publicationMode: NOT_PUBLIC`. O script preserva byte a byte manifestos existentes
com identidade compatível, inclusive decisões humanas registradas; conflitos ou
IDs duplicados bloqueiam o plano de escrita antes de alterar os arquivos.

Esses IDs de variantes não substituem o inventário canônico. Seus manifestos
não autorizam a publicação dos pilotos sob os IDs históricos. É necessária uma
migração explícita da proveniência, com revisão das versões e páginas, além da
decisão sobre direitos e do aceite de release.

## Próxima etapa

Revisar os candidatos do inventário histórico e as versões efetivamente usadas
pelos pilotos; registrar decisões de migração e direitos. Em seguida, aplicar a
migração por estágio e usar o projetor público para os modos permitidos.
