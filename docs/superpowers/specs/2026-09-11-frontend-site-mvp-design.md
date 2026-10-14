# Frontend/Site MVP — Design oficial

Data: 2026-09-11
Status: design arquitetural aprovado em seis seções; consolidação documental para revisão humana.
Origem: conversa “Planejamento de agentes do site”, 6a99c269-2e28-83e9-adfe-9ecd7a710ca8, e solicitação explícita de registro desta Spec.

## Objetivo e limites

Evoluir a camada de dados e navegação do Daemon Tools para um catálogo pesquisável de entidades e relações, mantendo a identidade visual e os comportamentos existentes do frontend. O primeiro aceite real usa Animalidade em preview restrito. O pipeline e a interface devem permanecer genéricos para outros livros.

Este documento registra requisitos de design, não resultados de implementação. Sua criação e commit não iniciam plano, código, migração, execução do piloto ou publicação. A aprovação do Frontend Stage não autoriza publicar Animalidade. O plano de implementação depende da revisão humana desta Spec e de autorização posterior.

As regras de fonte, proveniência, não invenção, ontologia Relations V2 e aprovação humana do repositório continuam válidas. Nenhum schema canônico é alterado por este documento.

## 1. Arquitetura e fluxo de dados

A decisão escolhida é **opção A: núcleo compartilhado FrontendProjector + adaptadores finos**.

```text
Sources / dados canônicos
  → Extraction → Editorial → Entities → Relations
  → QA / aprovação dos dados de entrada
  → FrontendProjector
      → restricted_preview → Site View Model restrito → Frontend local
      → public             → Site View Model público → Frontend público
  → validação do frontend / QA final → gate humano de release
```

O QA anterior à projeção verifica os dados aprovados de entrada; não substitui o QA posterior ao estágio FRONTEND nem altera a máquina de estados descrita em docs/architecture/pipeline.md.

Responsabilidades:

- Pipeline: verdade canônica e correções na camada de origem.
- FrontendProjector: política de exposição, transformação, labels, relações navegáveis, índices e validação da projeção.
- LocalPreviewProjector: fachada/adaptador de compatibilidade com o piloto existente, delegando a transformação principal ao núcleo compartilhado e preservando o isolamento do preview local.
- Site View Model: contrato de leitura entre projector e frontend.
- Frontend: apresentação, navegação, filtros e busca sobre dados já autorizados; não consome diretamente schemas, handoffs, manifests ou artifacts canônicos.

Os modos explícitos de execução do projector são `restricted_preview` e `public`. Não se confundem com `publicationMode`, que é a política de conteúdo do livro/fonte. A interface nunca recebe conteúdo proibido para escondê-lo por CSS ou JavaScript.

### Particionamento e versionamento

A raiz lógica de cada projeção é `site-data/`, contendo:

| Saída | Responsabilidade |
| --- | --- |
| `catalog.json` | Pequeno índice global de livros, grupos e metadados necessários à navegação e localização dos arquivos por livro. |
| `search-index.json` | Pequeno índice global de busca e rotas de entidades, sem exigir carregar todos os livros. |
| `books/<bookId>.json` | Conteúdo do livro carregado sob demanda; Animalidade usa `books/animalidade.json` apenas no preview autorizado. |

A separação adicional em `entities/` fica reservada somente para necessidade demonstrada de volume; não é requisito de entrega do MVP. A base é particionamento por livro mais pequenos índices globais.

O contrato é identificado por `siteViewModelVersion`, versão inicial `"1"`. Catálogo, índice e arquivos de livro devem pertencer ao mesmo contrato e modo. O frontend recusa versão incompatível ou arquivo inconsistente, sem apresentar carregamento parcial como íntegro.

`site-data/` designa a estrutura lógica, não uma autorização de escrita em `docs/`. A projeção restrita permanece fora do repositório e de diretórios publicados, preservando as barreiras do LocalPreviewProjector existente. Saídas públicas são geradas separadamente e só podem seguir ao destino público após o Public Projection Gate.

### Integridade referencial

Uma relação declarada resolvida cujo alvo não exista nos dados aprovados é erro do projector: a geração daquele output falha de forma fechada. Não emitir link quebrado, converter silenciosamente a relação em unresolved ou fabricar alvo. Referências reconhecidamente não resolvidas seguem o contrato separado da seção 2.

## 2. Contrato do Site View Model

O modelo é uma projeção de leitura versionada, descartável, regenerável e não canônica. Não editar `site-data` manualmente para corrigir dados: corrigir a camada de origem e regenerar a projeção.

### Projeção por livro

O contrato contém `siteViewModelVersion`, `book`, `groups`, `entities` e `relations`. `unresolvedReferences` existe separadamente apenas no modo restrito. `book` identifica `bookId`, `title` e `publicationMode`; `groups` organiza as entidades para navegação, sem criar novas entidades de domínio.

Cada entidade preserva a identidade canônica e fornece:

| Campo | Semântica |
| --- | --- |
| `entityId` | Identidade canônica estável para seleção e rota. |
| `type` | Tipo canônico, sem recategorização pela UI. |
| `displayType` | Label amigável produzido pelo projector. |
| `name`, `aliases`, `tags` | Nome e dados aprovados de identificação e consulta. |
| `content` | Somente conteúdo autorizado para o modo de projeção e publicationMode. |
| `provenance` | Livro/fonte e páginas reais de origem; vínculo rastreável, sem páginas inventadas. |

O contrato especifica esses campos de consumo e suas invariantes; não substitui os schemas canônicos nem exige copiar seus detalhes internos para o navegador.

### Labels e relações

O projector produz os labels de entidades e relações por registro central. O JavaScript não mantém tabelas paralelas de tradução. As perspectivas `outgoing` e `incoming` são produzidas para navegação a partir da mesma relação canônica, preservando seu predicado e seus endpoints.

Para `CAN_CHOOSE_POWER`, os labels são “Pode escolher poder” na saída e “Pode ser escolhido por” na entrada. O registro também cobre `HAS_POWER`, `HAS_WEAKNESS` e os demais predicados aceitos, respeitando a diferença entre posse efetiva e opção selecionável definida em Relations V2. Nenhuma tela inventa tradução ou semântica própria.

As relações navegáveis são agrupadas por tipo e identificam a entidade relacionada, seu nome e rota. A perspectiva inversa é somente projeção: não grava uma segunda aresta, não modifica a ontologia e não transforma entrada em posse efetiva. Somente endpoints autorizados e presentes na projeção podem produzir links. Se um endpoint canônico existe, mas foi excluído por direitos, a navegação correspondente é omitida, sem expor seu nome ou identificador restrito. Isso difere de um alvo inexistente no conjunto aprovado, que é erro de integridade.

### Proveniência e unresolved

A UI normal mostra proveniência enxuta: fonte/livro e página ou páginas. Apenas `restricted_preview` oferece uma seção recolhível “Detalhes técnicos”, com IDs, tipo canônico, sourceId, relationOntologyVersion, evidências e estado de resolução disponíveis e autorizados. Não inventar valores ausentes. A área técnica não existe no público; IDs estritamente necessários a rotas continuam permitidos quando a própria entidade for publicável.

`unresolvedReferences` não se mistura com `relations`. No preview, apresenta “Referência não vinculada”, nome e proveniência disponível, sem link nem target artificial. Rapidez permanece nesse bloco, sem entidade fictícia e sem aresta canônica. No modo `public`, o bloco e seus detalhes técnicos são omitidos de todos os outputs.

### Índices globais

`catalog.json` oferece livros, agrupamentos e metadados de navegação compatíveis com o modo atual. Não implica que todos os livros inventariados tenham conteúdo processado ou autorizado.

Cada entrada de `search-index.json` contém apenas os campos necessários: `entityId`, `route`, `name`, `aliases`, `type`, `displayType`, `bookId`, `bookTitle`, `tags` e `searchText`. A rota segue `#/entity/:entityId`. `searchText` deriva somente de texto/resumo permitido. Metadados e índices também passam pela política; não são canais alternativos para conteúdo excluído.

## 3. Rotas, navegação e layouts

Usar hash routing, compatível com hospedagem estática e GitHub Pages:

| Rota | Destino |
| --- | --- |
| `#/` | Início / catálogo |
| `#/books` | Lista de livros |
| `#/book/:bookId` | Visão de um livro |
| `#/entities` | Catálogo global de entidades |
| `#/entity/:entityId` | Página de entidade |
| `#/search` | Busca global |

A navegação principal oferece Início, Livros, Entidades, Busca e Preferências. A entrada pode ocorrer por livro, tipo ou busca. O livro é contexto/filtro removível, não uma limitação permanente: relações entre livros podem ser navegadas quando já resolvidas e autorizadas. Resolver novas referências entre livros não faz parte deste MVP.

A página de entidade apresenta nome, tipo amigável, conteúdo permitido, proveniência, relações de saída e de entrada agrupadas por tipo e, no preview, referências não vinculadas e detalhes técnicos recolhíveis.

| Layout | Composição desktop |
| --- | --- |
| Clássico | Menu lateral e conteúdo amplo. |
| Equilibrado | Lista, detalhe e relações; padrão inicial. |
| Avançado | Filtros persistentes na composição, lista, detalhe e relações. |

Preferências → Layout oferece os três modos. A mudança é imediata, sem botão Aplicar, e preserva rota, entidade selecionada, livro ativo, termo de busca e filtros. A preferência de layout é salva em `localStorage` e restaurada ao retornar.

Layout é estado de apresentação: não altera dados, identidade, direitos, rota ou filtros, nem gera três modelos de dados. No mobile, os três layouts convergem para uma composição responsiva comum: menu recolhível, filtros, lista, detalhe e relações. A preferência desktop continua salva enquanto a largura exige a composição mobile. A identidade visual existente é a base; não realizar redesign nesta fase.

## 4. Busca, filtros e ranking determinístico

A busca usa o índice gerado pelo FrontendProjector, com esta prioridade:

1. Nome exato.
2. Alias exato.
3. Nome por prefixo.
4. Alias por prefixo.
5. Termos contidos nos campos indexados permitidos.

Cada entidade é classificada pela melhor correspondência, sem resultados duplicados por múltiplos aliases. O desempate é determinístico por `displayType`, depois `name`, depois `entityId`. A mesma consulta, filtros e projeção produzem a mesma ordem; não depender de aleatoriedade ou ordem de carregamento dos arquivos.

Os filtros Livro e Tipo podem ser combinados entre si e com a busca. `#/search` consulta o catálogo disponível no modo atual. Uma busca contextual em `#/book/:bookId` pode iniciar com filtro daquele livro, removível para retornar à busca global.

A busca é simples e literal nesta fase. Não inclui fuzzy matching, sinônimos automáticos, stemming, busca semântica, embeddings ou ranking por popularidade. As comparações de consulta e índice precisam seguir a mesma regra determinística, sem expansão semântica. Somente campos autorizados são pesquisáveis; conteúdo ocultado visualmente nunca é mecanismo de controle de acesso.

## 5. Direitos, publicação e comportamento fail-closed

O FrontendProjector aplica `rightsStatus` e `publicationMode` de Book/Source antes de gerar qualquer dado destinado ao navegador. A política pública é fail-closed: ausência, incerteza ou falta de autorização bloqueiam exposição. Um publicationMode permissivo isolado não supera direitos desconhecidos.

| publicationMode | Limite de conteúdo autorizado |
| --- | --- |
| `FULL_TEXT` | Texto permitido, metadados e relações autorizadas. |
| `SUMMARY_AND_METADATA` | Resumo autorizado, metadados e relações autorizadas; sem texto integral restrito. |
| `METADATA_ONLY` | Somente metadados permitidos, como título, tipo, fonte e proveniência; sem corpo textual ou relações além do limite autorizado. |
| `NOT_PUBLIC` | Nunca entra na projeção pública; preview local somente quando autorizado. |

`restricted_preview` permite conteúdo autorizado para validação local, inclusive detalhes técnicos e unresolved. Não concede publicação nem dispensa as barreiras de diretório e política. Animalidade permanece `rightsStatus = UNKNOWN` e `publicationMode = NOT_PUBLIC`, em contexto `LOCAL_RESTRICTED`; seu conteúdo só participa do preview restrito autorizado. Esses valores são premissas do piloto aprovado, não autorização para alterá-los.

Nenhum conteúdo restrito do piloto entra em `docs/`, `docs/assets/data/`, nos dados versionados ou na main worktree do Git. Esta Spec documenta comportamento e critérios, sem incorporar texto do livro ou artifacts restritos.

### Falhas explícitas

- Relação resolvida com alvo inexistente: erro de projeção, sem saída apresentada como válida.
- Tipo sem label obrigatório: falha do projector; nunca improvisar label silenciosamente.
- Predicado desconhecido: falha, sem navegação ad hoc ou alteração da ontologia.
- Site View Model incompatível ou arquivo de livro inconsistente: recusa de consumo; não tratar projeção parcial como íntegra.
- Unresolved: bloco separado no preview, omitido no público, sem criação artificial de entidade.

### Public Projection Gate

Antes de considerar válida a saída pública da execução, verificar conjuntamente:

1. Direitos válidos e autorização explícita aplicável.
2. publicationMode permitido e limites de conteúdo respeitados.
3. Ausência de conteúdo restricted em livros, catálogo, índice de busca e demais saídas.
4. Ausência de unresolved técnico e de detalhes técnicos exclusivos do preview.
5. Ausência de relações quebradas ou links para entidades excluídas.
6. Contrato do Site View Model válido e compatível em todos os arquivos.

Qualquer falha invalida a saída pública daquela execução; nenhuma projeção parcial deve ser promovida como válida. A aprovação desse gate técnico não substitui a aprovação humana de release. O frontend recebe conteúdo já protegido pelo projector.

## 6. Testes, compatibilidade e critérios de aceite

### Cobertura por responsabilidade

| Área | Evidência necessária na futura implementação |
| --- | --- |
| FrontendProjector | Direitos/publicationMode; entidades; labels; outgoing/incoming; unresolved separado; índices; contrato versionado; compatibilidade da fachada LocalPreviewProjector. |
| Frontend | Catálogo e carregamento por livro; hash routes; busca e desempate estáveis; filtros combinados; relações; troca e persistência de layout; responsividade. |
| Segurança | UNKNOWN e NOT_PUBLIC bloqueados em public; unresolved omitido; alvo inexistente bloqueia geração; endpoint excluído não vaza em links; dados restritos ausentes de docs e de todos os índices públicos. |

A suíte deve provar cada nível do ranking, desempates, aliases, filtros Livro/Tipo e independência da ordem de carregamento. A validação de frontend precisa cobrir as interações; `node --check` verifica somente sintaxe e não substitui testes funcionais.

O synthetic E2E existente em `tests/agents/test_pilot_pipeline_e2e.py` deve ser estendido até: Entities → Relations → QA → FrontendProjector → Site View Model → Frontend validation. Dados sintéticos válidos devem chegar ao contrato consumível, passando pelas validações reais da fronteira.

### Aceite do piloto Animalidade em restricted_preview

- Abrir Animalidade e listar as **56 entidades de domínio aprovadas**.
- Navegar por tipo e buscar por nome, alias e termos; combinar filtros por livro/tipo.
- Abrir entidade com conteúdo autorizado e proveniência.
- Navegar pelas relações de saída e inversas projetadas, sem duplicar arestas canônicas.
- Mostrar Rapidez como “Referência não vinculada”, sem link, entidade fictícia ou mistura com relações válidas.
- Alternar Clássico, Equilibrado e Avançado imediatamente, preservando rota, entidade, livro, busca e filtros.
- Restaurar a preferência salva em localStorage e oferecer a composição mobile comum.
- Preservar o frontend existente e sua identidade visual.

56 é uma expectativa verificável do dataset aprovado do piloto, não constante no frontend, nem total acrescido de grupos, fonte ou unresolved. Contagens são derivadas dos dados. A referência de 281 livros catalogados na discussão descreve o acervo, não promete 281 livros processados/publicáveis nem autoriza hardcoding.

### Teste negativo público

Executar a projeção em modo `public` com Animalidade em UNKNOWN + NOT_PUBLIC e comprovar que nenhum conteúdo restrito do livro foi emitido. Inspecionar todos os arquivos gerados, incluindo catalog.json, search-index.json, arquivos por livro, relações e detalhes técnicos. O teste deve detectar vazamento mesmo quando a interface não o exibe. A geração restrita também deve rejeitar destino dentro do repositório ou de docs.

### Gates obrigatórios do estágio futuro

Preservar os gates atuais e estender sua cobertura ao novo contrato:

```text
python -m pytest tests/agents -q
python -m pytest -q
python scripts/validate_data.py
python scripts/check_book_coverage.py
node --check docs/assets/app.js
python -m pytest tests/agents/test_pilot_pipeline_e2e.py -q
```

Além desses comandos, são obrigatórios testes do FrontendProjector, validação funcional do frontend e public leak tests cobrindo os requisitos acima. `check_book_coverage.py` é o gate de cobertura das páginas; não confundir com percentual de cobertura de código nem inventar um limiar novo nesta Spec. Módulos JavaScript adicionados futuramente também precisam de verificação de sintaxe.

Abrir a página não basta para aceitar o estágio. Exigir gates técnicos, evidência de não vazamento, revisão visual desktop/mobile e aprovação humana final registrada e resolvida antes de `done`. Este registro documental não declara esses critérios implementados ou aprovados em execução.

## Autorrevisão da consolidação

- Completude: as seis seções e decisões anteriores estão registradas, incluindo opção A, labels no projector, proveniência enxuta, detalhes recolhíveis, particionamento, três layouts e busca determinística.
- Placeholders: não há conteúdo pendente de preenchimento, exemplos de entidades inventadas nem páginas presumidas. Os parâmetros bookId/entityId indicam padrões de arquivo e rota, não lacunas editoriais.
- Contradições: modo de projeção foi distinguido de publicationMode; QA de entrada foi distinguido do QA final; alvo canônico inexistente foi distinguido de endpoint omitido por direitos; índices globais também obedecem à política.
- Ambiguidade: saída restrita fica fora do repositório; unresolved não é relação; inversa não é aresta canônica; 56 é expectativa do piloto; coverage de páginas não é cobertura de código; o padrão é Equilibrado.
- Escopo: documento de design apenas. Não autoriza plano, implementação, publicação, migração, novos predicados, resolução entre livros ou redesign.

## Referências normativas do repositório

- `docs/architecture/constitution.md`
- `docs/architecture/project-context.md`
- `docs/architecture/pipeline.md`
- `docs/reference/cataloging-rules.md`
- `docs/reference/data-model.md`
- `docs/superpowers/specs/2026-09-08-pilot-content-pipeline-v2-2-design.md`
- `docs/superpowers/specs/2026-09-09-relations-v2-ontology-contract-design.md`
- `.github/workflows/validate.yml` (comandos dos gates atuais)
