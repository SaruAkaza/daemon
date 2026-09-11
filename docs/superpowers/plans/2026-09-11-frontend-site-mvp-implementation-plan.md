# Frontend/Site MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar catálogo pesquisável de entidades e relações, com projeção protegida por direitos e aceite local restrito de Animalidade.

**Architecture:** FrontendProjector concentra transformação e política; LocalPreviewProjector permanece fachada compatível. Site View Model versionado alimenta módulos vanilla de carregamento, rotas, busca e apresentação, preservando o frontend legado e sua identidade visual. Preview e projeção pública têm destinos e gates separados.

**Tech Stack:** Python 3, pytest, JSON estático, JavaScript vanilla ES modules, HTML/CSS, Node test runner; Playwright Python proposto apenas para testes de navegador, sem dependência adicional de runtime do site.

**Spec:** `docs/superpowers/specs/2026-09-11-frontend-site-mvp-design.md`, commit `c7c83388d8cad7fba16a94d3f4fb6d4a460dce14`.

## Global Constraints

- `siteViewModelVersion`: versão inicial `"1"`.
- Modos `restricted_preview` e `public`, distintos de `publicationMode`.
- Animalidade: `rightsStatus = UNKNOWN`, `publicationMode = NOT_PUBLIC`, contexto `LOCAL_RESTRICTED`.
- `site-data/catalog.json`, `site-data/search-index.json`, `site-data/books/<bookId>.json`; sem particionamento adicional por entidade no MVP.
- Preview restrito fora do repositório, da main worktree, de `docs/` e de diretórios publicados. Dados reais restritos nunca entram nas fixtures, commits ou capturas versionadas.
- Conteúdo, metadados e índices passam pela política antes da serialização. CSS/JavaScript não são controle de acesso.
- Inversa é projeção da mesma relação canônica; não gravar outra aresta nem alterar schemas ou ontologia.
- `CAN_CHOOSE_POWER`: “Pode escolher poder” / “Pode ser escolhido por”; distinto de `HAS_POWER`.
- “Referência não vinculada” somente no preview; Rapidez não recebe entidade, target ou link artificial.
- Layouts Clássico, Equilibrado (padrão) e Avançado; mudança imediata, persistência em `localStorage`, preservação de estado e composição mobile comum.
- Busca: nome exato, alias exato, nome por prefixo, alias por prefixo, termos contidos; desempate por `displayType`, `name`, `entityId`.
- Sem fuzzy, stemming, sinônimos automáticos, embeddings, redesign, migração ou resolução de novas referências entre livros.
- 56 é expectativa de entidades aprovadas do piloto; 281 livros não significa 281 livros processados/publicáveis. Não codificar essas contagens na UI.
- QA de entrada não substitui QA após FRONTEND; release e `done` exigem aprovação humana registrada.

## Autorização e pré-condições

Plano documental de 2026-09-11, preparado para revisão humana. Nenhuma tarefa executada. A autorização desta rodada cobre commit da Spec e escrita/revisão deste plano, não implementação, instalação de dependências, publicação ou execução do piloto.

Checkpoint comprovado: Spec commitada, 1 arquivo/246 inserções; working tree limpo imediatamente após o commit e novamente antes de escrever este plano. O plano permanece não rastreado para revisão, sem alterar o commit da Spec.

Na futura execução, revalidar autorização do plano, branch, árvore limpa, origem e aprovação do dataset, gates Relations V2 e runtime externo. Aprovação arquitetural não certifica os dados. Bloqueios de origem impedem o aceite real; fixtures sintéticas permitem desenvolver somente após autorização de implementação. Não reparar migração histórica como tarefa implícita deste MVP.

## Interfaces e mapa de arquivos

Caminhos relativos à raiz do repositório. Arquivos marcados Create são propostas futuras. Alterações de código abaixo são instruções, não código implantado.

| Arquivo | Ação e responsabilidade |
| --- | --- |
| `scripts/agents/site_view_model.py` | Create: envelopes e validação do contrato de leitura. |
| `scripts/agents/frontend_labels.py` | Create: labels centralizados de tipos e predicados. |
| `scripts/agents/frontend_policy.py` | Create: seleção explícita dos campos permitidos. |
| `scripts/agents/frontend_projector.py` | Create: transformação, índices, relações e escrita protegida. |
| `scripts/agents/preview_projector.py` | Modify: fachada, assinatura/retorno e index.json legado preservados. |
| `scripts/agents/preview_server.py` | Modify: overlay Site View Model, loopback e contenção de caminhos. |
| `docs/assets/site-model.mjs` | Create: carregador, validação e cache por livro. |
| `docs/assets/site-search.mjs` | Create: ranking e filtros puros. |
| `docs/assets/site-state.mjs` | Create: rotas, estado e preferência de layout. |
| `docs/assets/site-ui.mjs` | Create: renderização e interações. |
| `docs/assets/app.js`, `docs/index.html`, `docs/assets/styles.css` | Modify: integração mínima e layouts responsivos. |
| `tests/agents/test_site_view_model.py`, `tests/agents/test_frontend_policy.py`, `tests/agents/test_frontend_projector.py` | Create: contratos e segurança. |
| `tests/agents/test_preview_projector.py`, `tests/agents/test_preview_server.py`, `tests/agents/test_pilot_pipeline_e2e.py` | Modify: compatibilidade e integração. |
| `tests/frontend/site-model.test.mjs`, `tests/frontend/site-search.test.mjs`, `tests/frontend/site-state.test.mjs` | Create: testes Node. |
| `tests/frontend/test_site_browser.py`, `tests/frontend/conftest.py` | Create: testes de navegador com fixtures sintéticas externas. |
| `requirements-dev.txt` | Modify: dependência de testes de navegador. |

Base observada: `PilotCoordinator.project_preview(...)` chama `LocalPreviewProjector.project_local_preview(...)`. Este retorna `preview_root/book_id`, contendo `index.json`; testes verificam compatibilidade de `characters`, entidades e relações. PreviewServer já expõe `/api/preview/<bookId>/...` e cabeçalho `X-Daemon-Local-Preview: active`. `app.js` carrega `assets/data/pilot/index.json`, mantém rotas de áreas e renderizadores editoriais. Preservar esse suporte.

O CSS real é `styles.css`, apesar da referência antiga a `style.css` no contrato frontend-agent. Acrescentar `tests/test_editorial_catalog_ui.py` às regressões. O contrato do agente restringe dados e schemas a leitura; o núcleo Python é trabalho de projeção definido pela Spec, não autorização para editar entidades.

### Contratos internos propostos

Python usa `dict[str, Any]` nas fronteiras JSON e `ProjectionError(ValueError)`. `ApprovedBook` designa dict interno com `bookId`, `title`, `rightsStatus`, `publicationMode`, `entities`, `relations`, `unresolvedReferences`, `sources` e `approval`. `sources` mapeia sourceId para política/metadados aprovados. `approval` referencia decisões verificadas aplicáveis local/público; nunca é exportado. Não aceitar booleano informado pela UI como aprovação nem ampliar permissões dos manifests.

As entidades de entrada mantêm `id`, `category`, `source`, `page`, `entries`; relações mantêm `id`, `type`, `sourceEntityId`, `targetEntityId`. Campos ausentes não são inventados. A adaptação deve obter títulos e aprovações reais das fontes e decisões existentes; se indisponíveis, bloquear o piloto e encaminhar à origem.

Envelopes têm `siteViewModelVersion`, `mode`, `projectionId`. Este último é SHA256 dos bytes canônicos do conjunto projetado antes de adicionar o próprio campo; sem timestamp aleatório. Catálogo tem `books` com `bookId`, `title`, `publicationMode`, `path`, `groups`. Índice tem `entries`. Livro tem `book`, `groups`, `entities`, `relations`. A mesma geração/mode/versão é obrigatória em todos os arquivos.

Entidade projetada: `{entityId,type,displayType,name,aliases,tags,content,provenance}`. `content` é lista de blocos `{title,paragraphs}` preservando estrutura autorizada; provenance preserva fonte/páginas reais. `technicalDetails` é opcional e exclusivo do preview. `groups` contém `{id,label,entityIds}`; não cria entidade. `category` é o tipo canônico; subtype só refina label pelo registro.

Relação projetada: `{relationId,type,sourceEntityId,targetEntityId,outgoingLabel,incomingLabel}`. UI monta outgoing/incoming da mesma relação autorizada, usando nomes/rotas do índice global. Relação entre livros aparece nos dois arquivos envolvidos com o mesmo relationId, sem nova aresta canônica. Deduplicar por relationId no consumo.

Unresolved no preview: `{sourceEntityId,name,provenance,status}`, apenas campos disponíveis, sem rota ou target inventado. O índice contém exatamente os campos da Spec; rota = `#/entity/` + entityId codificado para URL.

## Task 1: Contrato de leitura e labels

**Files:** Create `scripts/agents/site_view_model.py`, `scripts/agents/frontend_labels.py`, `tests/agents/test_site_view_model.py`.

**Interfaces:** `validate_projection(files: dict[str,dict]) -> None`; `entity_label(category: str, subtype: str | None = None) -> str`; `relation_labels(predicate: str) -> tuple[str,str]`; `ProjectionError` definido em site_view_model. Consome schemas existentes em leitura; produz contrato para Tasks 2–9.

- [ ] Escrever testes de catálogo ausente, versão/mode/projectionId divergentes, livro faltante, campos inválidos, IDs duplicados, caminho inválido, label ausente e conjunto positivo completo.

```python
import pytest
from scripts.agents.site_view_model import validate_projection, ProjectionError
from scripts.agents.frontend_labels import relation_labels

def test_missing_catalog_is_invalid():
    with pytest.raises(ProjectionError):
        validate_projection({})

def test_choose_power_labels():
    assert relation_labels('CAN_CHOOSE_POWER') == (
        'Pode escolher poder', 'Pode ser escolhido por')
```

- [ ] Rodar `python -m pytest tests/agents/test_site_view_model.py -q`; confirmar falha pelo comportamento ausente, não ambiente quebrado.
- [ ] Implementar registro cobrindo categorias aceitas pelos schemas atuais e predicados de `schemas/relation-compatibility-v2.json`. Tipos sem label e predicados desconhecidos levantam ProjectionError; nenhum fallback improvisado. Categorias legadas só mantêm suporte na fachada, sem recategorizar o canônico.

```python
RELATION_LABELS = {
    'CAN_CHOOSE_POWER': ('Pode escolher poder', 'Pode ser escolhido por'),
    'HAS_POWER': ('Possui poder', 'É possuído por'),
    'HAS_WEAKNESS': ('Possui fraqueza', 'É fraqueza de'),
    'REQUIRES': ('Requer', 'É requerido por'),
    'GRANTS': ('Concede', 'É concedido por'),
    'BELONGS_TO': ('Pertence a', 'Inclui'),
    'DERIVED_FROM': ('Deriva de', 'Origina'),
    'APPEARS_IN': ('Aparece em', 'Contém referência a'),
    'MODIFIES': ('Modifica', 'É modificado por'),
    'REPLACES': ('Substitui', 'É substituído por'),
    'ALTERNATIVE_TO': ('É alternativa a', 'É alternativa a'),
    'HAS_SKILL': ('Possui perícia', 'É perícia de'),
    'USES_RULE': ('Usa regra', 'É usada por'),
}
def relation_labels(predicate):
    try:
        return RELATION_LABELS[predicate]
    except KeyError as exc:
        raise ProjectionError('Unknown predicate') from exc
```

Validar todos os campos dos contratos acima. Paths somente `books/<bookId>.json`; rejeitar caminhos absolutos, traversal e IDs com separadores. Validar referências entre arquivos. Em public, recusar technicalDetails/unresolvedReferences em qualquer nível. Conferir cobertura do registro contra schema, sem alterá-lo.
- [ ] Reexecutar testes e exigir PASS, incluindo caso positivo que valide catálogo, índice e livro juntos.
- [ ] Revisar diff e commit somente dos três arquivos: `feat: define site view model and labels`.

## Task 2: Política antes da serialização

**Files:** Create `scripts/agents/frontend_policy.py`, `tests/agents/test_frontend_policy.py`.

**Interfaces:** `project_allowed_book(book: dict, mode: str) -> dict | None`, sem I/O; consome ApprovedBook; retorna cópia com campos permitidos ou None se livro excluído. Usa ProjectionError para entradas/modos inválidos.

- [ ] Escrever teste público negativo e matriz de permissões:

```python
from scripts.agents.frontend_policy import project_allowed_book

def test_unknown_not_public_is_excluded():
    book = {'bookId':'synthetic', 'rightsStatus':'UNKNOWN',
            'publicationMode':'NOT_PUBLIC', 'entities':[], 'sources':{}}
    assert project_allowed_book(book, 'public') is None
```

- [ ] Rodar `python -m pytest tests/agents/test_frontend_policy.py -q` e confirmar vermelho.
- [ ] Reutilizar `PERMITTED_RIGHTS_COMBINATIONS` de `scripts/agents/gate_engine.py`, sem alterar tabela. Exigir política válida de Book e de cada Source, além da decisão de autorização verificável. Campos saem por lista explícita, nunca cópia integral de dict. Ausência, desconhecimento ou conflito bloqueiam exposição.

```python
from scripts.agents.gate_engine import PERMITTED_RIGHTS_COMBINATIONS

def public_combination_allowed(rights, publication_mode):
    return (rights, publication_mode) in PERMITTED_RIGHTS_COMBINATIONS
```

Esse helper não substitui validação de fontes e decisão humana. FULL_TEXT admite conteúdo autorizado; SUMMARY_AND_METADATA somente resumo já autorizado, sem gerar resumo automaticamente; METADATA_ONLY remove corpo e relações além do limite autorizado; NOT_PUBLIC exclui tudo. Tags/aliases/proveniência/títulos são sujeitos à mesma autorização. Preview exige decisão local e preserva direitos.
- [ ] Provar UNKNOWN+FULL_TEXT excluído; NOT_PUBLIC com AUTHORIZED excluído; autorização ausente excluída; fonte restrita não liberada pelo livro; resumo não copia entries; metadados não incluem corpo/arestas indevidas. Usar sentinelas para identificar vazamento em todos os campos.
- [ ] Reexecutar suíte focal e commit dos dois arquivos: `feat: enforce frontend projection rights policy`.

## Task 3: Núcleo, relações e índices

**Files:** Create `scripts/agents/frontend_projector.py`, `tests/agents/test_frontend_projector.py`.

**Interfaces:** `FrontendProjector.build(books: list[dict], mode: str) -> dict[str,dict]`; `FrontendProjector.write(files: dict[str,dict], output_root: Path, repository_root: Path) -> Path`. Consome Tasks 1/2. output_root é a raiz lógica site-data; chaves do mapa são catalog.json, search-index.json e books/<bookId>.json.

- [ ] Criar fixture `synthetic_books()` no teste: livro sintético, duas entidades canônicas a/b com páginas 1/2, CAN_CHOOSE_POWER e unresolved. Sources e decisões sintéticas seguem os contratos reais; não usar dados do piloto real. Adicionar testes abaixo e casos de endpoint excluído, desconhecido, labels e determinismo.

```python
from copy import deepcopy
import pytest
from scripts.agents.frontend_projector import FrontendProjector
from scripts.agents.site_view_model import ProjectionError

def test_missing_target_blocks():
    books = synthetic_books()
    books[0]['relations'][0]['targetEntityId'] = 'absent'
    with pytest.raises(ProjectionError):
        FrontendProjector().build(books, 'restricted_preview')

def test_input_unchanged():
    books = synthetic_books()
    before = deepcopy(books)
    FrontendProjector().build(books, 'restricted_preview')
    assert books == before
```

- [ ] Rodar `python -m pytest tests/agents/test_frontend_projector.py -q`; confirmar falha esperada.
- [ ] Implementar sequência: validar IDs/endpoints no universo aprovado; aplicar política; gerar entidades/grupos; selecionar arestas com endpoints visíveis; aplicar labels; gerar índice de conteúdo já autorizado; ordenar e calcular projectionId; validar conjunto. Alvo inexistente falha; existente excluído por direitos omite aresta sem nome/ID restrito.

```python
# Dentro de build: all_ids = IDs aprovados; visible_ids = IDs após política.
for relation in canonical_relations:
    endpoints = {relation['sourceEntityId'], relation['targetEntityId']}
    if not endpoints <= all_ids:
        raise ProjectionError('Resolved relation target missing')
    if not endpoints <= visible_ids:
        continue
    outgoing, incoming = relation_labels(relation['type'])
    projected_relations.append({
        'relationId':relation['id'], 'type':relation['type'],
        'sourceEntityId':relation['sourceEntityId'],
        'targetEntityId':relation['targetEntityId'],
        'outgoingLabel':outgoing, 'incomingLabel':incoming})
```

SearchText deriva dos blocos autorizados; não serializar detalhes internos. Ordenar por chaves estáveis antes de canonical_json_bytes. Público sem livros permitidos gera catálogo/índice vazios válidos, sem arquivo de Animalidade. Não confundir esse resultado esperado com validação de dataset ausente.
- [ ] Implementar write: validar conjunto inteiro antes de I/O; resolver destino; rejeitar preview dentro de qualquer worktree registrada do repo, symlink/junction para ela, e segmento docs sem distinção de caixa. Staging e destino novo ficam fora de publicação. Recusar destino existente para impedir dados obsoletos; gravar conjunto completo em staging irmão e promover por rename no mesmo volume. Falha não retorna sucesso nem modifica geração anterior. Não remover árvore preexistente.
- [ ] Testar permutação de entrada com bytes iguais; IDs canônicos preservados; relação inversa/cross-book; unresolved separado; labels desconhecidos; public misto permitido/restrito; falha sem saída parcial; destino docs/Docs/repo/junction; geração em diretório já ocupado. Varrer todos os outputs por sentinelas/IDs/nomes restritos.
- [ ] Rodar suíte focal e commit dos dois arquivos: `feat: project protected site data and search indexes`.

## Task 4: Fachada e servidor compatíveis

**Files:** Modify `scripts/agents/preview_projector.py`, `scripts/agents/preview_server.py`, `tests/agents/test_preview_projector.py`, `tests/agents/test_preview_server.py`.

**Interfaces:** Preservar `project_local_preview(workspace_root, preview_root, book_id, rights_status, publication_mode, repository_root=None) -> Path`, retorno preview_root/book_id e index.json legado. Adicionar site-data sob o mesmo diretório, servido em `/api/preview/<bookId>/site-data/`. Não mudar estados de jobs nem assinatura do coordenador.

- [ ] Estender os testes atuais sem apagar assertions de characters/index/retorno. Exigir novos outputs e unresolved do arquivo canônico específico, hoje omitido no fallback de leitura.

```python
# out_path é o retorno da chamada existente nos testes.
assert (out_path / 'index.json').is_file()
assert (out_path / 'site-data' / 'catalog.json').is_file()
assert (out_path / 'site-data' / 'search-index.json').is_file()
assert (out_path / 'site-data' / 'books' / 'animalidade.json').is_file()
```

- [ ] Rodar `python -m pytest tests/agents/test_preview_projector.py tests/agents/test_preview_server.py -q`; confirmar falha nas novas exigências.
- [ ] Adaptar workspace/manifests/decisões ao ApprovedBook. Não usar capitalize() para fabricar título no contrato novo. Transformações legadas ficam no adaptador; nenhuma falha nova pode ser escondida pelo caminho antigo.

```python
# approved_book vem dos dados/metadados/decisões validados na fachada.
files = FrontendProjector().build([approved_book], 'restricted_preview')
FrontendProjector().write(files, staging_dir / 'site-data', repo)
```

Gerar index legado e site-data em staging externo e promover juntos somente após validação. O destino completo novo deve ser inexistente; em segunda geração, o chamador usa outra raiz externa, não sobrescrita insegura de arquivos read-only. Preservar selagem read-only do index legado.
- [ ] Manter loopback. Servir mjs como JavaScript e JSON como JSON. Usar contenção por Path resolvido, não prefixo textual, nas duas raízes. Testar diretório irmão de prefixo comum, traversal codificado, junction, nomes Windows e arquivo ausente. Nenhum endpoint novo de leitura arbitrária de manifests.
- [ ] Confirmar testes focais e `python -m pytest tests/agents/test_pilot_pipeline_e2e.py -q`; atualizar fixtures sintéticas com metadados legítimos de teste sem enfraquecer gates.
- [ ] Commit dos quatro arquivos: `feat: serve site view model through restricted preview`.

## Task 5: Carregamento por livro e validação no cliente

**Files:** Create `docs/assets/site-model.mjs`, `tests/frontend/site-model.test.mjs`.

**Interfaces:** `createSiteStore(baseUrl, fetcher=fetch) -> {loadCatalog(),loadSearchIndex(),loadBook(bookId),clear()}`; loads retornam Promises de envelopes validados. Consome outputs da Task 3.

- [ ] Testar contrato inválido, cache por livro, nenhum carregamento de todos os livros, erro de rede, identidade divergente e geração mista.

```javascript
import test from 'node:test';
import assert from 'node:assert/strict';
import {createSiteStore} from '../../docs/assets/site-model.mjs';
test('rejects incompatible contract', async () => {
  const store=createSiteStore('/site-data/', async()=>({
    ok:true, json:async()=>({siteViewModelVersion:'999'})}));
  await assert.rejects(store.loadCatalog());
});
```

- [ ] Rodar `node --test tests/frontend/site-model.test.mjs`; confirmar vermelho.
- [ ] Implementar validação de estrutura e vínculo com catálogo antes de atualizar estado. Cache por bookId/projectionId/base/mode; inconsistência invalida geração completa. Não tratar livro parcialmente carregado como íntegro.

```javascript
function requireEnvelope(value, expected) {
  if(value.siteViewModelVersion!=='1') throw new Error('Versão incompatível');
  if(expected && (value.mode!==expected.mode ||
    value.projectionId!==expected.projectionId)) throw new Error('Projeção inconsistente');
  return value;
}
```

Complementar o helper com todas as checagens dos contratos, IDs e paths. Não acessar schemas/manifests/artifacts. Livro só é buscado quando necessário à rota; catálogo e índice globais podem ser carregados inicialmente.
- [ ] Testar fetcher contador: catálogo+índice não buscam livros; duas aberturas do mesmo livro usam cache; troca de geração limpa dados e pede recarga consistente. Reexecutar teste e `node --check docs/assets/site-model.mjs`.
- [ ] Commit focal: `feat: load validated site data by book`.

## Task 6: Ranking e filtros determinísticos

**Files:** Create `docs/assets/site-search.mjs`, `tests/frontend/site-search.test.mjs`.

**Interfaces:** `normalizeSearch(value: string) -> string`; `searchEntities(entries, query, {bookId=null,type=null}={}) -> Array`. Consome somente entradas autorizadas do índice; retorna entidades únicas.

- [ ] Escrever fixture com cinco níveis, dois desempates e aliases duplicados; testar filtros juntos, query vazia, acentos/case, zero resultado e ordem invertida.

```javascript
import test from 'node:test';
import assert from 'node:assert/strict';
import {searchEntities} from '../../docs/assets/site-search.mjs';
test('exact name precedes exact alias',()=>{
  const a={entityId:'a',name:'Lobo',aliases:[],displayType:'Criatura',
    type:'creature_npc',bookId:'s',tags:[],searchText:''};
  const b={...a,entityId:'b',name:'Outro',aliases:['Lobo']};
  assert.deepEqual(searchEntities([b,a],'lobo').map(x=>x.entityId),['a','b']);
});
```

- [ ] Executar `node --test tests/frontend/site-search.test.mjs`; confirmar falha.
- [ ] Implementar mesma normalização da consulta e de todos os campos: NFD, retirar U+0300–036F, lowercase, trim; pontuação literal, sem expansão semântica. Nível 5 exige todos os termos separados por espaço contidos em campos permitidos. Comparação lexical fixa, sem locale dependente do ambiente.

```javascript
export function normalizeSearch(value) {
  return String(value??'').normalize('NFD')
    .replace(/[\u0300-\u036f]/g,'').toLowerCase().trim();
}
function lexical(a,b) { return a<b ? -1 : a>b ? 1 : 0; }
```

Score: nome exato=0, alias exato=1, prefixo nome=2, prefixo alias=3, termos=4; sem match=Infinity, excluído. Cada ID usa melhor score. Empates com lexical nos valores displayType/name/entityId, nessa ordem. Query vazia retorna lista filtrada ordenada pelo desempate. Não buscar conteúdo de livro para melhorar ranking.
- [ ] Provar todos os scores e desempates, unicidade e invariância sob permutação; reexecutar teste/sintaxe.
- [ ] Commit focal: `feat: add deterministic entity search and filters`.

## Task 7: Rotas e preferência de layout

**Files:** Create `docs/assets/site-state.mjs`, `tests/frontend/site-state.test.mjs`.

**Interfaces:** `parseRoute(hash) -> {kind,id}`; `createState(storage) -> object`; `setLayout(state,layout,storage) -> object`. Estado contém route, selectedEntityId, bookId, query, type, layout. Layout = classic/balanced/advanced; chave daemonSite.layout.

- [ ] Testar seis rotas, URI inválida, voltar/avançar, storage bloqueado/valor inválido e preservação de todos os campos.

```javascript
import test from 'node:test';
import assert from 'node:assert/strict';
import {setLayout} from '../../docs/assets/site-state.mjs';
test('layout preserves navigation and filters',()=>{
  const state={route:'#/entity/a',selectedEntityId:'a',bookId:'s',
    query:'lobo',type:'creature_npc',layout:'balanced'};
  const next=setLayout(state,'classic',{setItem(){}});
  assert.deepEqual({...next,layout:state.layout},state);
});
```

- [ ] Rodar `node --test tests/frontend/site-state.test.mjs`; confirmar vermelho.
- [ ] Implementar parser fechado para #/, #/books, #/book/:bookId, #/entities, #/entity/:entityId, #/search. Inválidas geram not-found; entidade ausente mostra mensagem explícita. Preferências é painel, sem nova rota obrigatória. Layout inválido usa balanced; storage indisponível preserva funcionalidade em memória.

```javascript
export function setLayout(state,layout,storage) {
  const selected=['classic','balanced','advanced'].includes(layout)?layout:'balanced';
  try { storage.setItem('daemonSite.layout',selected); } catch {}
  return {...state,layout:selected};
}
```

createState lê mesma chave defensivamente. Hashchange controla navegação; layout nunca reseta seleção, query ou filtros. Contexto de livro inicia filtro removível, não prende busca global. Não há requisito de persistir query em localStorage.
- [ ] Confirmar refresh em rota, retorno da preferência e testes/sintaxe.
- [ ] Commit focal: `feat: manage site routes and layout preference`.

## Task 8: UI integrada e layouts responsivos

**Files:** Create `docs/assets/site-ui.mjs`, `tests/frontend/test_site_browser.py`, `tests/frontend/conftest.py`; Modify `docs/assets/app.js`, `docs/index.html`, `docs/assets/styles.css`, `requirements-dev.txt`.

**Interfaces:** `mountSite({root,store,storage=localStorage}) -> {destroy()}`. Consome Tasks 5–7. Proposta de bootstrap explícito `?site=1`; preview acrescenta `preview=<bookId>`, base `/api/preview/<bookId>/site-data/`; público usa `assets/site-data/`. Query preview seleciona transporte, não direitos. Entrada/rotas legadas continuam disponíveis enquanto não houver release da nova projeção.

- [ ] Preparar Playwright Python como dependência de testes e registrar versão efetivamente validada no futuro commit. Obter navegador por mecanismo autorizado. Fixtures conftest geram dados sintéticos pelo projector em tmp_path externo, iniciam PreviewServer loopback/porta dinâmica e oferecem page/site_url; teardown em finally. Sem dados reais. Indisponibilidade do navegador bloqueia evidência funcional, não autoriza substituí-la por sintaxe.
- [ ] Escrever teste funcional com entidade sintética a (Lobo), b, relação e unresolved:

```python
def test_layout_preserves_entity_and_search(page, site_url):
    page.goto(site_url + '#/entity/a')
    page.get_by_label('Busca global', exact=True).fill('Lobo')
    page.get_by_role('button', name='Preferências', exact=True).click()
    page.get_by_label('Layout', exact=True).select_option('classic')
    assert page.url.endswith('#/entity/a')
    assert page.get_by_label('Busca global', exact=True).input_value() == 'Lobo'
    assert page.locator('[data-entity-id="a"]').count() >= 1
    page.reload()
    assert page.locator('[data-layout="classic"]').count() == 1
```

site_url termina em `/?site=1&preview=synthetic`. Dados vêm do projector, não JSON manual que esconda incompatibilidade.
- [ ] Rodar `python -m pytest tests/frontend/test_site_browser.py -q`; confirmar falha funcional.
- [ ] Integrar Início/Livros/Entidades/Busca/Preferências. app.js escolhe novo bootstrap antes de load legado, usando import dinâmico; impedir dupla inicialização. Conservar renderizadores/tema/filtros editoriais legados. Contrato novo inválido mostra erro, sem fallback para dados legados.

```javascript
const title=document.createElement('h1');
title.textContent=entity.name;
const type=document.createElement('span');
type.textContent=entity.displayType;
root.append(title,type);
```

entity vem de store validado; usar DOM/textContent, nunca executar HTML da fonte. Renderizar conteúdo permitido/proveniência, outgoing/incoming agrupadas, e details técnico/unresolved só no preview. Unresolved sem link; contagem exclui grupos e referências. Labels vêm do projector.
- [ ] Aplicar layouts ao mesmo estado: Clássico menu lateral/conteúdo; Equilibrado lista/detalhe/relações; Avançado filtros persistentes/lista/detalhe/relações. Mobile menu recolhível/sequência comum, sem regravar preferência desktop. Reutilizar tokens/cores/tipografia, sem redesign.

```css
.site-shell[data-layout="balanced"] .site-browser {
  display:grid;
  grid-template-columns:minmax(12rem,1fr) minmax(20rem,2fr) minmax(12rem,1fr);
}
@media (max-width:48rem) {
  .site-shell[data-layout] .site-browser { display:flex; flex-direction:column; }
}
```

Adicionar regras classic/advanced por composição especificada, foco visível, aria-expanded e teclado. Layout é imediato, sem Aplicar. Regras mobile devem sobrepor todos os seletores desktop em especificidade.
- [ ] Testar seis rotas, filtros removíveis/combinados, alias/termo/tipo, inversa/cross-book, unresolved sem link, público sem painel técnico, erros rede/contrato, storage, reload e tema. Inspecionar 390/768/1440 px nos três layouts, ausência de overflow inesperado e navegação por teclado. Comparar visualmente com baseline legado.
- [ ] Rodar testes de navegador, testes Node, `python -m pytest tests/test_editorial_catalog_ui.py -q`, node --check de app.js e cada mjs novo. Commit dos sete arquivos: `feat: integrate site catalog and responsive layouts`.

## Task 9: E2E, gate público e aceite real

**Files:** Modify `tests/agents/test_pilot_pipeline_e2e.py`, `tests/agents/test_frontend_projector.py`, `tests/frontend/test_site_browser.py`; Create `docs/reports/2026-09-11-frontend-site-mvp-validation.md` somente na execução futura, ajustando data ao dia real.

**Interfaces:** Estender `test_synthetic_pilot_relations_stage_v2_e2e` existente: Entities → Relations → QA → FrontendProjector → Site View Model → frontend validation. Não substituir coordenação/persistência/QA por mocks.

- [ ] Acrescentar validação dos outputs reais após project_preview:

```python
from scripts.agents.site_view_model import validate_projection

# projected_path é o retorno já existente da projeção no teste E2E.
site_root=projected_path/'site-data'
files={p.relative_to(site_root).as_posix():json.loads(p.read_text(encoding='utf-8'))
       for p in site_root.rglob('*.json')}
validate_projection(files)
assert files['catalog.json']['mode']=='restricted_preview'
assert files['search-index.json']['entries']
```

- [ ] Rodar E2E com falha esperada nas novas exigências antes do ajuste de integração. Confirmar três predicados sintéticos; consumir esse conjunto no navegador com transporte real e validar relação/rota. Nenhuma escrita canônica pela projeção. Falha de origem para no finding, sem correção no frontend.
- [ ] Provar Public Projection Gate com seis itens: direitos+autorização, limites publicationMode, ausência restricted em todas as saídas, ausência unresolved/detalhes técnicos, ausência relações quebradas/endpoints excluídos, contrato consistente. Teste misto prova preservação do permitido e exclusão do restrito. Varrer arquivos inteiros por sentinelas, nomes e IDs, não apenas DOM.
- [ ] Executar gates da Spec e registrar comando/exit code/SHA:

```text
python -m pytest tests/agents -q
python -m pytest -q
python scripts/validate_data.py
python scripts/check_book_coverage.py
node --check docs/assets/app.js
python -m pytest tests/agents/test_pilot_pipeline_e2e.py -q
node --test tests/frontend/site-model.test.mjs tests/frontend/site-search.test.mjs tests/frontend/site-state.test.mjs
python -m pytest tests/frontend/test_site_browser.py -q
python -m pytest tests/test_editorial_catalog_ui.py -q
```

Verificar sintaxe de cada mjs novo. Problemas temporários podem usar basetemp externo controlado, com justificativa, sem contornar permissões. Não executar builds que copiem dados reais para docs como validação automática. Cobertura significa páginas, não novo limiar de cobertura de código.
- [ ] Após verificar dataset e autorização local: executar Animalidade externamente; conferir 56 entidades, Rapidez não vinculada, buscas/filtros, relações, três layouts preservando estado, persistência e mobile. Rodar público negativo com UNKNOWN+NOT_PUBLIC e comprovar ausência de conteúdo em todos os outputs. Não publicar. Capturas/texto restrito ficam externos; relatório versionado só resultados agregados e hashes permitidos.
- [ ] Conferir zero alteração de dados/schemas causada pelo frontend; registrar limitações reais, falhas e aprovação pendente. Commit somente testes/relatório: `test: validate frontend projection and pilot acceptance`.
- [ ] Parar para revisão humana final; testes verdes não autorizam done, deploy ou promoção pública.

## Sequência e revisão documental

Tasks 1 → 2 → 3 → 4 estabelecem fronteira protegida; 5/6/7 consomem contrato; 8 integra; 9 reúne evidência. Um plano é apropriado porque projeção, índices e UI dependem do mesmo contrato e gate de segurança. Cada tarefa termina com teste focal e commit pequeno, usando git add com paths explícitos, nunca inclusão ampla de dados.

Mudanças fora do mapa exigem revisão de escopo. Não mudar upstream, copiar repositório, usar índice alternativo, fazer push ou ampliar permissões silenciosamente. Na execução futura usar isolamento conforme skill aplicável; esta rodada documental permanece no repositório original solicitado.

Autorrevisão de cobertura:

| Spec | Tarefas e evidências previstas |
| --- | --- |
| §1 arquitetura | 1/3/4/5: núcleo, fachada, partição, geração consistente, integridade referencial. |
| §2 contrato | 1–5/8: identidade, labels, provenance, inversas/cross-book, unresolved e índices. |
| §3 rotas/layouts | 7/8: seis rotas, estado, três layouts, storage, mobile e regressão legado. |
| §4 busca | 6/8: cinco scores, desempates, aliases, filtros e invariância de ordem. |
| §5 direitos | 2–4/9: política antes de saída, contenção, seis critérios públicos e teste de vazamento. |
| §6 aceite | 8/9: browser real, E2E estendido, 56/Rapidez, visual, negativo público e aprovação humana. |

Nomes de interfaces consistentes: build/write, createSiteStore, searchEntities, setLayout, mountSite. ProjectionError é importado de site_view_model. Sem alteração da Spec ou schema canônico; fixtures sempre sintéticas e validação real sempre condicionada aos gates de origem. Trechos são guias de implementação futura, não alegação de código pronto. A revisão realizada aqui é documental; todas as tarefas permanecem desmarcadas.
