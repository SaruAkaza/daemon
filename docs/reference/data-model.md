# Modelo De Dados

## Fonte

Cada arquivo em `Livros/` vira uma fonte em `data/index/sources.json`.

Campos principais:

- `id`: identificador estavel derivado do nome do arquivo.
- `title`: titulo inferido do nome.
- `path`: caminho relativo do arquivo original.
- `extension`: `.pdf` ou `.docx`.
- `sizeBytes`: tamanho do arquivo.
- `sha256`: hash para detectar alteracoes.
- `categoryHints`: categorias provaveis pelo nome e pelo texto.
- `textStatus`: `pending`, `ok`, `failed` ou `partial`.

## Entidade

Entidades extraidas ficam em `data/entities/<category>.json`.

Campos comuns:

- `id`
- `name`
- `category`
- `source`
- `page`
- `entries`
- `tags`
- `confidence`
- `extractionMethod`

## Areas

Areas ficam em `data/areas/<area>.json` e funcionam como a camada de navegacao inspirada no 5e.tools, mas adaptada ao Daemon/Trevas.

Cada area contem:

- `entities`: itens ja curados em `data/entities`.
- `sourceParts`: blocos e secoes dos livros prontos para seguir.
- `readySourceCount`: quantidade de fontes boas usadas na montagem.

O resumo geral fica em `data/index/area-summary.json`.

Areas atuais:

- `regras_base`
- `aprimoramentos`
- `kits`
- `classes`
- `racas`
- `linhagens`
- `poderes`
- `magias`
- `rituais`
- `itens_equipamentos`
- `criaturas_npcs`
- `cenarios_lore`
- `aventuras`
- `tabelas`

## Categorias

- `core_rule`
- `attribute_skill`
- `combat`
- `character_option`
- `kit_class`
- `race_lineage`
- `power_magic`
- `ritual_spell`
- `item_equipment`
- `creature_npc`
- `setting_lore`
- `adventure`
- `table_generator`
- `source`

## Relações (Relations V2)

As interconexões semânticas entre entidades são armazenadas em `data/entities/relations.json`.

### Contratos de Schema
- **Contrato de Item**: `schemas/relation.schema.json` valida instâncias individuais de relação.
- **Contrato de Coleção**: `schemas/relation-collection.schema.json` valida o array de relações (`type: "array"`, itens referenciando `relation.schema.json`, `uniqueItems: true`).
- **Contrato de Relações Não Resolvidas**: `schemas/unresolved-relation-collection.schema.json` isola referências externas ou ausentes em `unresolved-relations.json`, impedindo referências quebradas no grafo canônico.

### Campos Principais de uma Relação
- `id`: identificador estável da relação.
- `sourceId`: ID da entidade de origem.
- `sourceCategory`: categoria da entidade de origem.
- `relationType`: tipo semântico da relação (predicado).
- `targetId`: ID da entidade de destino.
- `targetCategory`: categoria da entidade de destino.
- `sourcePage`: número da página no livro original de proveniência.
- `confidence`: nível de confiança da extração (`HIGH`, `MEDIUM`, `LOW`).

### Ontologia e Predicados Canônicos (V2)
A ontologia V2 (`relations-v2`) formaliza a semântica de vínculos:
- `HAS_POWER`: a entidade de origem efetivamente possui o poder alvo (posse efetiva distinta de opções disponíveis: `actual possession != selectable/available option`).
- `CAN_CHOOSE_POWER`: a entidade ou template de origem tem permissão para escolher o poder como opção de construção/configuração (listas de seleção, menus, poderes possíveis).
- `HAS_WEAKNESS`: a entidade de origem possui a fraqueza, vulnerabilidade ou limitação alvo.
- `REQUIRES`: pré-requisito obrigatório para compra, escolha ou evolução.
- `GRANTS`: concessão automática de bônus, benefício ou poder.
- `BELONGS_TO`: pertencimento a caminho, panteão ou facção.
- `DERIVED_FROM`: derivação direta ou variante de outra entidade base.
- `APPEARS_IN`: presença em suplemento adicional.
- `MODIFIES`: modificação de regra ou atributo preexistente.
- `REPLACES`: substituição formal de regra anterior.
- `ALTERNATIVE_TO`: variante mecânica ou opção temática equivalente.
- `HAS_SKILL`: associação direta a pacote de perícias.
- `USES_RULE`: vinculação mecânica a uma regra base.

*Nota de Decisão*: `CAN_CHOOSE_WEAKNESS` foi formalmente rejeitado por YAGNI e ausência de precedente canônico.

### Governança e Compatibilidade
- A autoridade canônica para pares permitidos reside em `schemas/relation-compatibility-v2.json`.
- Versionamento: `relations-v1` é estritamente histórico/somente-leitura (`historical / read-only`); `relations-v2` é obrigatório para novas execuções (`mandatory for new execution`).

## Estrategia De Extracao

1. Inventario dos arquivos.
2. Extracao de texto bruto.
3. Segmentacao por pagina/secao.
4. Deteccao de candidatos por padroes de titulo e palavras-chave.
5. Normalizacao em JSON.
6. Revisao humana dos itens de baixa confianca.

Esse fluxo evita tratar PDFs escaneados, DOCX e livros diagramados como se fossem todos iguais.
