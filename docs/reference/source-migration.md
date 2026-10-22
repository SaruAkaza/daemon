# Preparação privada da migração de proveniência

`scripts/prepare_source_migration.py` transforma a reconciliação atual em
propostas concretas para revisão. O plano fica em
`data/index/source-migration-plan.json`; cópias propostas dos pilotos são
gravadas somente em staging privado, fora do checkout.

## O que muda nas propostas

- `sourcePath` passa a apontar para o arquivo candidato identificado.
- `sourceFile` é conferido contra o nome desse arquivo.
- `sourceVariantId` vincula o candidato à variante `file-<SHA-256>`.
- `sourceMigration` registra hashes e estados de revisão, com versão de origem
  não verificada e liberação pública desabilitada.

Os IDs legados (`source`, IDs de entidades/seções e referências), regras,
valores, conteúdo e campos de páginas são preservados. O plano registra
valores anteriores e propostos dos campos de raiz. Metadados de migração já
existentes exigem revisão em vez de serem sobrescritos silenciosamente.

## Verificação de inputs e páginas

A preparação refaz a conferência de custódia das fontes e exige que o relatório
de reconciliação salvo seja atual. Manifestos de variantes precisam existir e
continuar válidos. Os hashes dos pilotos, da reconciliação e dos manifestos
entram no plano, assim como os hashes das cópias propostas.

A auditoria procura `page`, `pages`, `sourcePage` e `sourcePages` em todas as
camadas do JSON. Valores declarados são preservados; números positivos inteiros
são tratados como declarações ainda não verificadas. Valores ausentes, inválidos,
listas vazias e booleanos são registrados como pendências. O script nunca
substitui uma página ausente por `1` nem converte índices de parágrafo em páginas.

Mesmo declarações de página estruturalmente válidas exigem revisão da edição,
versão e paginação efetivamente usadas. O plano mantém `promotionAllowed: false`
e `NEEDS_HUMAN_REVIEW` em todos os candidatos. Ele não contém autorização de
publicação nem decisão humana fabricada.

## Comandos

```bash
# Diagnóstico somente de leitura
python scripts/prepare_source_migration.py

# Gravar o plano de revisão, sem alterar os pilotos
python scripts/prepare_source_migration.py --write-plan

# Conferir o plano salvo, sem criar staging
python scripts/prepare_source_migration.py --check

# Materializar as cópias propostas em staging privado
python scripts/prepare_source_migration.py --stage
```

`--repo-root` seleciona outro checkout. O staging padrão fica em
`<pai-do-checkout>/.daemon_runtime/source-migrations/<nome-do-checkout>/<hash-do-plano>/`.
O pacote contém `plan.json` e `candidates/<operationId>.bin`; cada `.bin` é JSON
UTF-8 e seu destino proposto e SHA-256 constam no plano. O mesmo plano gera o
mesmo identificador de pacote, sem timestamps variáveis.

O CI executa apenas `--check`. Não materializa cópias do acervo nem publica
conteúdo durante a validação.

## Integridade do staging

O staging reutiliza `ApplicationRuntimeConfig`, `ResourceBounds` e
`StagingManager`. Exige o mesmo filesystem e um destino fora do repositório.
Limites de arquivos, operações e bytes são checados antes de criar o pacote.

Um lock exclusivo protege cada plano. O pacote é preparado em um diretório
temporário privado, verificado e depois promovido por rename dentro do runtime.
Uma nova execução verifica o pacote existente sem regravá-lo. Alterações humanas,
arquivos inesperados ou conflitos de lock são preservados e sinalizados; erros
de escrita removem somente o temporário criado pela execução.

## Alcance

Esta ferramenta prepara a revisão técnica da migração. Não oferece `--apply`,
não escreve destinos canônicos ou públicos e não resolve versões/páginas por
inferência. A aplicação definitiva requer evidências das versões e páginas,
decisões de migração registradas e os gates do estágio responsável. Direitos e
release continuam sujeitos aos seus manifestos e à aprovação correspondente.
