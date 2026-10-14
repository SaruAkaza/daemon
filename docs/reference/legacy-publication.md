# Publicação dos JSONs legados

Os JSONs de áreas e pilotos contêm texto integral. O status editorial (`approved`,
`done`, `pilot_review` etc.) e os testes técnicos não concedem direitos de
distribuição. Antes de gravar em `docs/assets/data/`, os publicadores verificam as
fontes primárias e secundárias referenciadas em todos os payloads.

## Manifestos e política

Cada fonte precisa de um manifesto validado pelo contrato existente
`schemas/source-manifest.schema.json`, em `data/source-manifests/*.json`.
O nome do arquivo é livre; a chave é `sourceId`. Manifestos duplicados ou inválidos
bloqueiam a operação. Não crie manifestos de autorização sem evidência e decisão
humana registrada sobre os direitos da fonte.

Para uma cópia integral, o manifesto deve:

- identificar uma fonte existente em `data/index/sources.json`;
- corresponder ao `sha256`, `path` e `extension` dessa fonte;
- ter `visibility: public`;
- ter `rightsStatus: AUTHORIZED` ou `PUBLIC_DOMAIN`;
- ter `publicationMode: FULL_TEXT`.

O `sourcePath` de um piloto, quando presente, também deve corresponder à fonte
inventariada. Caminhos Windows e POSIX são comparados com separadores normalizados.
O `sourceFile`, quando declarado, deve corresponder ao nome do arquivo inventariado,
inclusive quando o piloto não informa `sourcePath`.
Um DOCX, outra edição ou um arquivo de mesmo nome não pode usar a autorização
de um PDF diferente.

`UNKNOWN`, `PRIVATE`, `NOT_PUBLIC`, visibilidade interna/privada e a ausência de
manifesto bloqueiam a cópia. `METADATA_ONLY` e `SUMMARY_AND_METADATA` também a
bloqueiam: esses modos exigem a projeção pública filtrada implementada em
`scripts/agents/frontend_policy.py` e `FrontendProjector`, sem copiar o JSON bruto.
Nenhum schema ou combinação canônica de direitos foi alterado.

## Verificação sem escrita

```bash
python scripts/build_github_pages_site.py --check-only
python scripts/build_pilot_index.py --check-only
```

Os dois comandos retornam código `1` quando a política bloqueia a publicação.
`--check-only` não cria, remove nem atualiza arquivos, inclusive índices locais.
Para consultar outro diretório de manifestos já revisados:

```bash
python scripts/build_github_pages_site.py --manifests-dir /caminho/manifestos --check-only
```

Sem `--check-only`, o comando copia os arquivos somente após passar o preflight
completo. Os bytes publicados são os mesmos que foram verificados, evitando
releitura dos payloads após a checagem. JSONs obsoletos nos diretórios de áreas
ou pilotos são removidos apenas depois desse gate.

O escritor compartilhado `common.write_json` aplica a mesma política a gravações
públicas feitas diretamente pelos geradores e pelas rotinas de limpeza de livros.
Ele usa o diretório padrão de manifestos. Gravações canônicas em `data/` e saídas
locais continuam disponíveis, sem promover seu conteúdo para distribuição.

## Alcance do gate

O preflight verifica direitos e proveniência; não substitui revisão editorial,
QA, aceite humano de uma release ou a etapa de deploy. Falhas de política
preservam os arquivos existentes. A operação de cópia, depois do preflight,
ainda não é uma transação com rollback para falhas de disco.

Os assets históricos já versionados não são saneados automaticamente. A integração
desta barreira não certifica sua autorização nem altera os livros existentes.
O verificador de sincronização continua comparando esses arquivos por leitura.

Próximas etapas: reconciliar os IDs/caminhos legados com o inventário, registrar
direitos por fonte e migrar a distribuição de metadados/resumos para o projetor
público antes de autorizar uma reconstrução do acervo publicado.

O fluxo de evidências, sem migração automática, está em
[Reconciliação de fontes legadas](source-reconciliation.md).
