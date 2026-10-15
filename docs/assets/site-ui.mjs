/**
 * Daemon Tools — Site UI Presentation & Responsive Layout Integration (ES Module)
 * Pure vanilla DOM, secure textContent injection, zero unsafe innerHTML.
 */

import { searchEntities, filterBooks } from './site-search.mjs';
import {
  createState,
  parseRoute,
  setLayout,
  setRoute,
  setFilters,
  setBookFilters,
  setOperatorId,
  setSseStatus,
} from './site-state.mjs';
import { OpsClient } from './site-ops.mjs';

/**
 * Sanitizes special characters to prevent arbitrary HTML markup injection.
 *
 * @param {*} str
 * @returns {string}
 */
export function escapeHtml(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/**
 * Builds HTML string for a catalog book card with dual-axis badges and safe escaping.
 *
 * @param {object} b - Catalog book entry
 * @returns {string}
 */
export function createBookCard(b) {
  const safeId = encodeURIComponent(b.bookId || '');
  const safeTitle = escapeHtml(b.title || safeId);
  const safeRights = escapeHtml(b.rightsStatus || 'UNKNOWN');
  const safePub = escapeHtml(b.publicationMode || 'NOT_PUBLIC');
  const entityCount = Number.isInteger(b.entityCount) ? b.entityCount : 0;
  const pageCount = Number.isInteger(b.pageCount) ? b.pageCount : 0;

  const hasPipeline = b.pipelineStatus !== undefined && b.pipelineStatus !== null && b.pipelineStatus !== '';
  const safePipeline = hasPipeline ? escapeHtml(b.pipelineStatus) : '';
  const pipelineBadge = hasPipeline
    ? `<span class="site-badge site-badge-pipeline" data-status="${safePipeline}">${safePipeline}</span>`
    : '';

  const stageText = b.currentStage
    ? `<span class="site-card-stage">Estágio: ${escapeHtml(b.currentStage)}</span>`
    : hasPipeline
    ? `<span class="site-card-stage">Não iniciado</span>`
    : '';

  return `
    <div class="site-book-card" data-book-id="${safeId}">
      <a href="#/book/${safeId}" class="site-book-title">${safeTitle}</a>
      <div class="site-card-badges">
        ${pipelineBadge}
        <span class="site-badge site-badge-rights" data-rights="${safeRights}">${safeRights}</span>
        <span class="site-badge site-badge-pub" data-mode="${safePub}">${safePub}</span>
      </div>
      <div class="site-card-meta">
        ${stageText}
        <span class="site-card-count">${entityCount} entidades</span>
        <span class="site-card-pages">${pageCount} págs</span>
      </div>
    </div>
  `.trim();
}

export const PIPELINE_STAGES = [
  'Source',
  'Extraction',
  'Editorial',
  'Entities',
  'Relations',
  'Frontend',
  'QA',
];

/**
 * Computes state for each of the 7 pipeline stages.
 *
 * @param {string} pipelineStatus
 * @param {string|null} currentStage
 * @returns {Array<{ stage: string, state: string }>}
 */
export function getStageStates(pipelineStatus, currentStage) {
  if (pipelineStatus === 'DONE' || pipelineStatus === 'READY_FOR_HUMAN_APPROVAL') {
    return PIPELINE_STAGES.map((s) => ({ stage: s, state: 'done' }));
  }
  if (!currentStage || pipelineStatus === 'WAITING') {
    return PIPELINE_STAGES.map((s) => ({ stage: s, state: 'pending' }));
  }
  const curLower = currentStage.toLowerCase();
  const stagesLower = PIPELINE_STAGES.map((s) => s.toLowerCase());
  const curIdx = stagesLower.indexOf(curLower);
  if (curIdx === -1) {
    return PIPELINE_STAGES.map((s) => ({ stage: s, state: 'pending' }));
  }

  const activeState =
    pipelineStatus === 'BLOCKED' || pipelineStatus === 'NEEDS_HUMAN_REVIEW'
      ? 'blocked'
      : 'active';

  return PIPELINE_STAGES.map((s, idx) => {
    if (idx < curIdx) return { stage: s, state: 'done' };
    if (idx === curIdx) return { stage: s, state: activeState };
    return { stage: s, state: 'pending' };
  });
}

/**
 * Builds HTML string for book detail view including 7-stage visual stepper and entity list/empty banner.
 *
 * @param {object} params
 * @param {object} params.book
 * @param {object} [params.catalogMeta]
 * @param {Array} [params.entities]
 * @returns {string}
 */
export function renderBookDetailHtml({ book, catalogMeta, entities = [] }) {
  const meta = catalogMeta || {};
  const safeTitle = escapeHtml((book && book.title) || meta.title || 'Livro');
  const safeRights = escapeHtml(meta.rightsStatus || 'UNKNOWN');
  const safePub = escapeHtml(meta.publicationMode || 'NOT_PUBLIC');

  const hasPipeline = meta.pipelineStatus !== undefined && meta.pipelineStatus !== null && meta.pipelineStatus !== '';
  const safePipeline = hasPipeline ? escapeHtml(meta.pipelineStatus) : '';
  const pipelineBadge = hasPipeline
    ? `<span class="site-badge site-badge-pipeline" data-status="${safePipeline}">${safePipeline}</span>`
    : '';

  let stepperHtml = '';
  if (hasPipeline) {
    const stageStates = getStageStates(meta.pipelineStatus, meta.currentStage || null);
    stepperHtml = `
      <div class="pipeline-stepper">
        ${stageStates.map((s) => `<span class="stepper-step ${s.state}">${escapeHtml(s.stage)}</span>`).join('')}
      </div>
    `;
  }

  let contentHtml = '';
  if (entities.length === 0) {
    contentHtml = `
      <div class="site-book-empty-state">
        <p>Nenhuma entidade processada para este livro ainda. O livro encontra-se na fila de processamento.</p>
      </div>
    `;
  } else {
    contentHtml = `
      <h2>Entidades deste Livro (${entities.length})</h2>
      <ul class="site-entity-list">
        ${entities.map((e) => `<li><a href="#/entity/${encodeURIComponent(e.entityId)}">${escapeHtml(e.name)} (${escapeHtml(e.displayType)})</a></li>`).join('')}
      </ul>
    `;
  }

  return `
    <div class="site-book-detail">
      <a href="#/books" class="site-back-link">← Voltar ao Acervo de Livros</a>
      <div class="site-book-detail-header">
        <h1>${safeTitle}</h1>
        <div class="site-card-badges">
          ${pipelineBadge}
          <span class="site-badge site-badge-rights" data-rights="${safeRights}">${safeRights}</span>
          <span class="site-badge site-badge-pub" data-mode="${safePub}">${safePub}</span>
        </div>
      </div>
      ${stepperHtml}
      ${contentHtml}
    </div>
  `.trim();
}



/**
 * Mounts the site MVP UI into root element.
 *
 * @param {object} options
 * @param {HTMLElement} options.root
 * @param {object} options.store - Site store from createSiteStore()
 * @param {Storage|object} [options.storage=localStorage]
 * @returns {{ destroy: Function }}
 */
export function mountSite({ root, store, storage = localStorage, mode = 'restricted_preview' }) {
  let state = createState(storage, window.location.hash || '#/', { mode });
  let catalog = null;
  let searchIndex = null;
  let isPreferencesOpen = false;

  let opsClient = null;
  let opsEventsConnection = null;
  let renderVersion = 0;

  function connectOpsEvents() {
    if (state.mode !== 'restricted_preview' || !opsClient) return;
    if (opsEventsConnection) return;

    state = setSseStatus(state, 'CONECTANDO');
    opsEventsConnection = opsClient.connectEvents({
      onOpen: () => {
        state = setSseStatus(state, 'ATIVA');
        if (state.routeInfo.kind.startsWith('ops')) {
          renderActiveView();
        }
      },
      onEvent: (payload, eventType) => {
        if (eventType === 'command_updated') {
          const cmds = [...(state.ops.commands || [])];
          const idx = cmds.findIndex((c) => c.commandId === payload.commandId);
          if (idx >= 0) {
            cmds[idx] = payload;
          } else {
            cmds.unshift(payload);
          }
          state.ops.commands = cmds;
        } else if (eventType === 'review_updated') {
          const revs = [...(state.ops.reviews || [])];
          const idx = revs.findIndex((r) => r.reviewId === payload.reviewId);
          if (idx >= 0) {
            revs[idx] = payload;
          } else {
            revs.push(payload);
          }
          state.ops.reviews = revs;
        } else if (eventType === 'control_updated') {
          state.ops.controlState = payload;
        } else if (eventType === 'batch_updated') {
          state.ops.batch = payload;
        }
        if (state.routeInfo.kind.startsWith('ops')) {
          renderActiveView();
        }
      },
      onSnapshotRequired: async () => {
        await loadOpsData();
        if (state.routeInfo.kind.startsWith('ops')) {
          renderActiveView();
        }
      },
      onError: () => {
        state = setSseStatus(state, 'DESCONECTADA');
        if (state.routeInfo.kind.startsWith('ops')) {
          renderActiveView();
        }
      },
    });
  }

  if (state.mode === 'restricted_preview') {
    opsClient = new OpsClient();
    connectOpsEvents();
  }

  // Clear root
  while (root.firstChild) {
    root.removeChild(root.firstChild);
  }

  root.className = 'site-shell';
  root.setAttribute('data-layout', state.layout);

  // Top header
  const header = document.createElement('header');
  header.className = 'site-topbar';

  // Brand
  const brandLink = document.createElement('a');
  brandLink.className = 'site-brand';
  brandLink.href = '#/';
  brandLink.textContent = 'DAEMON/TREVAS';
  header.appendChild(brandLink);

  // Main navigation
  const nav = document.createElement('nav');
  nav.className = 'site-nav';
  nav.setAttribute('aria-label', 'Navegação principal');

  const navItems = [
    { label: 'Início', href: '#/' },
    { label: 'Livros', href: '#/books' },
    { label: 'Entidades', href: '#/entities' },
    { label: 'Busca', href: '#/search' },
  ];

  if (state.mode === 'restricted_preview') {
    navItems.push({ label: 'Operações', href: '#/ops' });
  }

  for (const item of navItems) {
    const link = document.createElement('a');
    link.href = item.href;
    link.textContent = item.label;
    link.className = 'site-nav-link';
    nav.appendChild(link);
  }
  header.appendChild(nav);

  // Search box in toolbar
  const searchWrap = document.createElement('div');
  searchWrap.className = 'site-search-wrap';

  const searchLabel = document.createElement('label');
  searchLabel.htmlFor = 'siteGlobalSearch';
  searchLabel.textContent = 'Busca global';
  searchLabel.className = 'site-search-label';

  const searchInput = document.createElement('input');
  searchInput.id = 'siteGlobalSearch';
  searchInput.type = 'search';
  searchInput.setAttribute('aria-label', 'Busca global');
  searchInput.placeholder = 'Buscar em todas as entidades...';
  searchInput.value = state.query || '';
  searchInput.className = 'site-search-input';

  searchInput.addEventListener('input', (e) => {
    const q = e.target.value;
    state = setFilters(state, { query: q });
    renderActiveView();
  });

  searchInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && state.routeInfo.kind !== 'search' && state.routeInfo.kind !== 'entities') {
      window.location.hash = '#/search';
    }
  });

  searchWrap.appendChild(searchLabel);
  searchWrap.appendChild(searchInput);
  header.appendChild(searchWrap);

  // Preferences button
  const prefButton = document.createElement('button');
  prefButton.type = 'button';
  prefButton.className = 'site-btn-preferences';
  prefButton.textContent = 'Preferências';
  prefButton.setAttribute('aria-haspopup', 'dialog');
  prefButton.addEventListener('click', () => {
    isPreferencesOpen = !isPreferencesOpen;
    prefModal.hidden = !isPreferencesOpen;
    prefButton.setAttribute('aria-expanded', String(isPreferencesOpen));
  });
  header.appendChild(prefButton);

  root.appendChild(header);

  // Preferences dialog
  const prefModal = document.createElement('div');
  prefModal.className = 'site-preferences-modal';
  prefModal.hidden = true;

  const prefPanel = document.createElement('section');
  prefPanel.className = 'site-preferences-panel';
  prefPanel.setAttribute('role', 'dialog');
  prefPanel.setAttribute('aria-modal', 'true');
  prefPanel.setAttribute('aria-label', 'Preferências de Layout');

  const prefTitle = document.createElement('h3');
  prefTitle.textContent = 'Preferências';
  prefPanel.appendChild(prefTitle);

  const layoutField = document.createElement('div');
  layoutField.className = 'site-field';

  const layoutLabel = document.createElement('label');
  layoutLabel.htmlFor = 'siteLayoutSelect';
  layoutLabel.textContent = 'Layout';

  const layoutSelect = document.createElement('select');
  layoutSelect.id = 'siteLayoutSelect';
  layoutSelect.setAttribute('aria-label', 'Layout');

  const layouts = [
    { value: 'classic', label: 'Clássico' },
    { value: 'balanced', label: 'Equilibrado' },
    { value: 'advanced', label: 'Avançado' },
  ];

  for (const opt of layouts) {
    const o = document.createElement('option');
    o.value = opt.value;
    o.textContent = opt.label;
    if (opt.value === state.layout) o.selected = true;
    layoutSelect.appendChild(o);
  }

  layoutSelect.addEventListener('change', (e) => {
    state = setLayout(state, e.target.value, storage);
    root.setAttribute('data-layout', state.layout);
    renderActiveView();
  });

  layoutField.appendChild(layoutLabel);
  layoutField.appendChild(layoutSelect);
  prefPanel.appendChild(layoutField);

  const closePrefBtn = document.createElement('button');
  closePrefBtn.type = 'button';
  closePrefBtn.textContent = 'Fechar';
  closePrefBtn.className = 'site-btn-close';
  closePrefBtn.addEventListener('click', () => {
    isPreferencesOpen = false;
    prefModal.hidden = true;
    prefButton.setAttribute('aria-expanded', 'false');
  });
  prefPanel.appendChild(closePrefBtn);

  prefModal.appendChild(prefPanel);
  root.appendChild(prefModal);

  // Main container
  const mainContent = document.createElement('main');
  mainContent.className = 'site-main-content';
  root.appendChild(mainContent);

  function clearNode(node) {
    while (node.firstChild) {
      node.removeChild(node.firstChild);
    }
  }

  function renderError(message) {
    clearNode(mainContent);
    const errBox = document.createElement('div');
    errBox.className = 'site-error-box';
    errBox.textContent = message;
    mainContent.appendChild(errBox);
  }

  async function renderActiveView() {
    const version = ++renderVersion;
    clearNode(mainContent);

    // Sync search input value with state query
    if (searchInput.value !== state.query) {
      searchInput.value = state.query;
    }

    const { kind, id } = state.routeInfo;

    if (kind === 'home') {
      renderHomeView();
    } else if (kind === 'books') {
      renderBooksView();
    } else if (kind === 'book') {
      await renderBookDetailView(id);
    } else if (kind === 'entities' || kind === 'entity') {
      await renderEntitiesOrEntityView(id);
    } else if (kind === 'search') {
      renderSearchView();
    } else if (kind === 'ops') {
      await renderOpsDashboard('overview', version);
    } else if (kind === 'ops-queue') {
      await renderOpsDashboard('queue', version);
    } else if (kind === 'ops-reviews') {
      await renderOpsDashboard('reviews', version);
    } else if (kind === 'ops-review') {
      await renderOpsReviewDetail(id, version);
    } else {
      renderNotFoundView();
    }
  }

  function renderHomeView() {
    const container = document.createElement('div');
    container.className = 'site-home-view';

    const h1 = document.createElement('h1');
    h1.textContent = 'Daemon Tools — Referência Digital';
    container.appendChild(h1);

    const desc = document.createElement('p');
    desc.textContent =
      'Enciclopédia e referência digital rastreável para o universo Daemon/Trevas com entidades canônicas, vínculos ontológicos e dados autorizados.';
    container.appendChild(desc);

    const stats = document.createElement('div');
    stats.className = 'site-stats-grid';

    const booksStat = document.createElement('div');
    booksStat.className = 'site-stat-card';
    const booksCount = document.createElement('strong');
    booksCount.textContent = String(catalog ? catalog.books.length : 0);
    const booksLabel = document.createElement('span');
    booksLabel.textContent = 'Livros Catalogados';
    booksStat.appendChild(booksCount);
    booksStat.appendChild(booksLabel);

    const entitiesStat = document.createElement('div');
    entitiesStat.className = 'site-stat-card';
    const entitiesCount = document.createElement('strong');
    entitiesCount.textContent = String(searchIndex ? searchIndex.entries.length : 0);
    const entitiesLabel = document.createElement('span');
    entitiesLabel.textContent = 'Entidades no Índice';
    entitiesStat.appendChild(entitiesCount);
    entitiesStat.appendChild(entitiesLabel);

    stats.appendChild(booksStat);
    stats.appendChild(entitiesStat);
    container.appendChild(stats);

    if (catalog && catalog.books.length === 0) {
      const emptyPublicMsg = document.createElement('p');
      emptyPublicMsg.className = 'site-empty-public-message';
      emptyPublicMsg.textContent = 'Nenhum conteúdo público disponível.';
      container.appendChild(emptyPublicMsg);
    }

    mainContent.appendChild(container);
  }

  function renderBooksView() {
    const container = document.createElement('div');
    container.className = 'site-books-view';

    const h1 = document.createElement('h1');
    h1.textContent = 'Acervo de Livros';
    container.appendChild(h1);

    if (!catalog || catalog.books.length === 0) {
      const empty = document.createElement('p');
      empty.className = 'site-empty-message';
      empty.textContent = 'Nenhum livro autorizado disponível.';
      container.appendChild(empty);
      mainContent.appendChild(container);
      return;
    }

    // Filter controls bar
    const filterbar = document.createElement('div');
    filterbar.className = 'site-books-filterbar';

    // Search input
    const searchInput = document.createElement('input');
    searchInput.id = 'siteBookSearch';
    searchInput.type = 'search';
    searchInput.placeholder = 'Filtrar por título ou ID...';
    searchInput.value = (state.bookFilters && state.bookFilters.query) || '';
    searchInput.className = 'site-input';
    searchInput.setAttribute('aria-label', 'Buscar livros');
    searchInput.addEventListener('input', (e) => {
      state = setBookFilters(state, { query: e.target.value });
      renderActiveView();
    });
    filterbar.appendChild(searchInput);

    // Pipeline status filter (restricted/archive only, hidden in public mode)
    if (!catalog || catalog.mode !== 'public') {
      const pipeSelect = document.createElement('select');
      pipeSelect.id = 'siteBookPipelineFilter';
      pipeSelect.className = 'site-select';
      pipeSelect.setAttribute('aria-label', 'Filtrar por status de processamento');
      const pipeOptions = [
        { value: 'all', label: 'Todos os Status (Pipeline)' },
        { value: 'WAITING', label: 'WAITING (Não iniciado)' },
        { value: 'RUNNING', label: 'RUNNING (Em processamento)' },
        { value: 'BLOCKED', label: 'BLOCKED (Bloqueado)' },
        { value: 'FAILED', label: 'FAILED (Falha)' },
        { value: 'NEEDS_HUMAN_REVIEW', label: 'NEEDS_HUMAN_REVIEW (Aguardando revisão)' },
        { value: 'READY_FOR_HUMAN_APPROVAL', label: 'READY_FOR_HUMAN_APPROVAL (Aguardando aprovação)' },
        { value: 'DONE', label: 'DONE (Concluído)' },
      ];
      for (const opt of pipeOptions) {
        const el = document.createElement('option');
        el.value = opt.value;
        el.textContent = opt.label;
        if (state.bookFilters && state.bookFilters.pipelineStatus === opt.value) el.selected = true;
        pipeSelect.appendChild(el);
      }
      pipeSelect.addEventListener('change', (e) => {
        state = setBookFilters(state, { pipelineStatus: e.target.value });
        renderActiveView();
      });
      filterbar.appendChild(pipeSelect);
    }

    // Rights status filter
    const rightsSelect = document.createElement('select');
    rightsSelect.id = 'siteBookRightsFilter';
    rightsSelect.className = 'site-select';
    rightsSelect.setAttribute('aria-label', 'Filtrar por direitos');
    const rightsOptions = [
      { value: 'all', label: 'Todos os Direitos' },
      { value: 'UNKNOWN', label: 'UNKNOWN (Desconhecido)' },
      { value: 'AUTHORIZED', label: 'AUTHORIZED (Autorizado)' },
      { value: 'PUBLIC_DOMAIN', label: 'PUBLIC_DOMAIN (Domínio Público)' },
      { value: 'METADATA_ONLY', label: 'METADATA_ONLY (Somente Metadados)' },
      { value: 'PRIVATE', label: 'PRIVATE (Privado)' },
    ];
    for (const opt of rightsOptions) {
      const el = document.createElement('option');
      el.value = opt.value;
      el.textContent = opt.label;
      if (state.bookFilters && state.bookFilters.rightsStatus === opt.value) el.selected = true;
      rightsSelect.appendChild(el);
    }
    rightsSelect.addEventListener('change', (e) => {
      state = setBookFilters(state, { rightsStatus: e.target.value });
      renderActiveView();
    });
    filterbar.appendChild(rightsSelect);

    // Publication mode filter
    const pubSelect = document.createElement('select');
    pubSelect.id = 'siteBookPublicationFilter';
    pubSelect.className = 'site-select';
    pubSelect.setAttribute('aria-label', 'Filtrar por modo de publicação');
    const pubOptions = [
      { value: 'all', label: 'Todos os Modos (Publicação)' },
      { value: 'FULL_TEXT', label: 'FULL_TEXT (Texto Completo)' },
      { value: 'SUMMARY_AND_METADATA', label: 'SUMMARY_AND_METADATA (Resumo e Metadados)' },
      { value: 'METADATA_ONLY', label: 'METADATA_ONLY (Somente Metadados)' },
      { value: 'NOT_PUBLIC', label: 'NOT_PUBLIC (Não Público)' },
    ];
    for (const opt of pubOptions) {
      const el = document.createElement('option');
      el.value = opt.value;
      el.textContent = opt.label;
      if (state.bookFilters && state.bookFilters.publicationMode === opt.value) el.selected = true;
      pubSelect.appendChild(el);
    }
    pubSelect.addEventListener('change', (e) => {
      state = setBookFilters(state, { publicationMode: e.target.value });
      renderActiveView();
    });
    filterbar.appendChild(pubSelect);

    // Sort select
    const sortSelect = document.createElement('select');
    sortSelect.id = 'siteBookSort';
    sortSelect.className = 'site-select';
    sortSelect.setAttribute('aria-label', 'Ordenar livros');
    const sortOptions = [
      { value: 'title_asc', label: 'Título (A-Z)' },
      { value: 'title_desc', label: 'Título (Z-A)' },
      { value: 'entities_desc', label: 'Mais entidades' },
      { value: 'pages_desc', label: 'Mais páginas' },
    ];
    for (const opt of sortOptions) {
      const el = document.createElement('option');
      el.value = opt.value;
      el.textContent = opt.label;
      if (state.bookFilters && state.bookFilters.sortBy === opt.value) el.selected = true;
      sortSelect.appendChild(el);
    }
    sortSelect.addEventListener('change', (e) => {
      state = setBookFilters(state, { sortBy: e.target.value });
      renderActiveView();
    });
    filterbar.appendChild(sortSelect);

    container.appendChild(filterbar);

    const filtered = filterBooks(catalog.books, state.bookFilters || {});

    // Counter badge
    const countP = document.createElement('p');
    countP.className = 'site-books-count';
    countP.textContent = `Exibindo ${filtered.length} de ${catalog.books.length} livros`;
    container.appendChild(countP);

    const grid = document.createElement('div');
    grid.className = 'site-books-grid';

    if (filtered.length === 0) {
      const noResults = document.createElement('p');
      noResults.className = 'site-empty-message';
      noResults.textContent = 'Nenhum livro corresponde aos filtros selecionados.';
      grid.appendChild(noResults);
    } else {
      for (const b of filtered) {
        const wrapper = document.createElement('div');
        wrapper.innerHTML = createBookCard(b);
        grid.appendChild(wrapper.firstElementChild);
      }
    }

    container.appendChild(grid);
    mainContent.appendChild(container);
  }

  async function renderBookDetailView(bookId) {
    try {
      const bookData = await store.loadBook(bookId);
      const catalogMeta = store.getBookMetadata
        ? store.getBookMetadata(bookId)
        : (catalog && catalog.books.find((b) => b.bookId === bookId));
      const wrapper = document.createElement('div');
      wrapper.innerHTML = renderBookDetailHtml({
        book: bookData.book,
        catalogMeta,
        entities: bookData.entities || [],
      });
      mainContent.appendChild(wrapper.firstElementChild || wrapper);
    } catch (err) {
      renderError(`Erro ao carregar livro: ${err.message}`);
    }
  }

  async function renderEntitiesOrEntityView(selectedId) {
    const browser = document.createElement('div');
    browser.className = 'site-browser';

    // 1. Entity list column
    const listPanel = document.createElement('section');
    listPanel.className = 'site-panel site-list-panel';

    const listHead = document.createElement('div');
    listHead.className = 'site-panel-head';
    const listTitle = document.createElement('h2');
    listTitle.textContent = 'Entidades';
    listHead.appendChild(listTitle);
    listPanel.appendChild(listHead);

    const results = searchEntities(searchIndex ? searchIndex.entries : [], state.query, {
      bookId: state.bookId,
      type: state.type,
    });

    const listEl = document.createElement('div');
    listEl.className = 'site-entity-items';
    listEl.setAttribute('role', 'listbox');

    for (const item of results) {
      const row = document.createElement('a');
      row.className = 'site-entity-row';
      row.href = `#/entity/${item.entityId}`;
      if (item.entityId === selectedId) {
        row.classList.add('is-selected');
      }

      const nameSpan = document.createElement('span');
      nameSpan.className = 'site-entity-row-name';
      nameSpan.textContent = item.name;

      const typeSpan = document.createElement('span');
      typeSpan.className = 'site-entity-row-type';
      typeSpan.textContent = item.displayType;

      row.appendChild(nameSpan);
      row.appendChild(typeSpan);
      listEl.appendChild(row);
    }
    listPanel.appendChild(listEl);
    browser.appendChild(listPanel);

    // 2. Detail and Relations panels
    const detailPanel = document.createElement('section');
    detailPanel.className = 'site-panel site-detail-panel';

    const relationsPanel = document.createElement('section');
    relationsPanel.className = 'site-panel site-relations-panel';

    if (selectedId) {
      const idxEntry = searchIndex ? searchIndex.entries.find((e) => e.entityId === selectedId) : null;
      if (!idxEntry) {
        detailPanel.textContent = 'Entidade não encontrada no catálogo.';
        browser.appendChild(detailPanel);
      } else {
        try {
          const bookData = await store.loadBook(idxEntry.bookId);
          const entity = bookData.entities.find((e) => e.entityId === selectedId);

          if (!entity) {
            detailPanel.textContent = 'Entidade não encontrada no livro.';
            browser.appendChild(detailPanel);
          } else {
            // Render Entity Detail
            const article = document.createElement('article');
            article.className = 'entity-detail';
            article.setAttribute('data-entity-id', entity.entityId);

            const h1 = document.createElement('h1');
            h1.textContent = entity.name;
            article.appendChild(h1);

            const dType = document.createElement('span');
            dType.className = 'entity-display-type';
            dType.textContent = entity.displayType;
            article.appendChild(dType);

            // Aliases and tags
            if (entity.aliases && entity.aliases.length > 0) {
              const aliasesP = document.createElement('p');
              aliasesP.className = 'entity-aliases';
              aliasesP.textContent = `Outros nomes: ${entity.aliases.join(', ')}`;
              article.appendChild(aliasesP);
            }

            // Content blocks
            if (entity.content && entity.content.length > 0) {
              for (const block of entity.content) {
                const blockSection = document.createElement('section');
                blockSection.className = 'entity-content-block';
                if (block.title) {
                  const blockTitle = document.createElement('h3');
                  blockTitle.textContent = block.title;
                  blockSection.appendChild(blockTitle);
                }
                for (const pText of block.paragraphs || []) {
                  const p = document.createElement('p');
                  p.textContent = pText;
                  blockSection.appendChild(p);
                }
                article.appendChild(blockSection);
              }
            }

            // Provenance
            if (entity.provenance) {
              const provP = document.createElement('footer');
              provP.className = 'entity-provenance';
              provP.textContent = `Fonte: ${entity.provenance.source}, pág. ${(entity.provenance.pages || []).join(', ')}`;
              article.appendChild(provP);
            }

            // Technical details (restricted_preview only)
            if (bookData.mode === 'restricted_preview' && entity.technicalDetails) {
              const tech = document.createElement('details');
              tech.className = 'entity-technical-details';
              const sum = document.createElement('summary');
              sum.textContent = 'Detalhes Técnicos';
              tech.appendChild(sum);

              const contentBox = document.createElement('div');
              contentBox.className = 'tech-details-content';

              const dl = document.createElement('dl');
              dl.className = 'technical-details-list';

              const td = entity.technicalDetails;
              const allowedScalars = [
                { key: 'entityId', label: 'ID da Entidade' },
                { key: 'type', label: 'Tipo Canônico' },
                { key: 'sourceId', label: 'ID da Fonte' },
                { key: 'mode', label: 'Modo' },
                { key: 'rightsStatus', label: 'Status de Direitos' },
                { key: 'publicationMode', label: 'Modo de Publicação' },
                { key: 'context', label: 'Contexto' },
                { key: 'relationOntologyVersion', label: 'Ontologia de Relações' },
              ];

              for (const { key, label } of allowedScalars) {
                if (td[key] !== undefined && td[key] !== null && String(td[key]).trim() !== '') {
                  const dt = document.createElement('dt');
                  dt.textContent = label;
                  const dd = document.createElement('dd');
                  dd.setAttribute('data-field', key);
                  dd.textContent = String(td[key]);
                  dl.appendChild(dt);
                  dl.appendChild(dd);
                }
              }

              // Provenance formatting
              if (td.provenance && typeof td.provenance === 'object') {
                const provSource = td.provenance.source;
                const provPages = Array.isArray(td.provenance.pages) ? td.provenance.pages.join(', ') : '';
                if (provSource) {
                  const dt = document.createElement('dt');
                  dt.textContent = 'Proveniência';
                  const dd = document.createElement('dd');
                  dd.setAttribute('data-field', 'provenance');
                  dd.textContent = provPages ? `${provSource}, pág. ${provPages}` : provSource;
                  dl.appendChild(dt);
                  dl.appendChild(dd);
                }
              }

              // Any other authorized custom non-internal fields that might exist in technicalDetails (except unresolvedReferences)
              for (const [k, v] of Object.entries(td)) {
                if (
                  k !== 'unresolvedReferences' &&
                  k !== 'provenance' &&
                  !allowedScalars.some((s) => s.key === k) &&
                  v !== undefined &&
                  v !== null &&
                  typeof v !== 'object'
                ) {
                  const dt = document.createElement('dt');
                  dt.textContent = k;
                  const dd = document.createElement('dd');
                  dd.setAttribute('data-field', k);
                  dd.textContent = String(v);
                  dl.appendChild(dt);
                  dl.appendChild(dd);
                }
              }

              contentBox.appendChild(dl);

              // Unresolved references list
              if (Array.isArray(td.unresolvedReferences) && td.unresolvedReferences.length > 0) {
                const unresBox = document.createElement('div');
                unresBox.className = 'tech-unresolved-box';
                unresBox.setAttribute('data-field', 'unresolvedReferences');

                const unresTitle = document.createElement('h4');
                unresTitle.textContent = 'Referências Não Vinculadas';
                unresBox.appendChild(unresTitle);

                const unresUl = document.createElement('ul');
                unresUl.className = 'tech-unresolved-list';
                for (const u of td.unresolvedReferences) {
                  if (u && u.name) {
                    const li = document.createElement('li');
                    li.className = 'tech-unresolved-item';
                    const nameSpan = document.createElement('span');
                    nameSpan.className = 'tech-unres-name';
                    nameSpan.textContent = u.name;
                    li.appendChild(nameSpan);

                    if (u.status) {
                      const statusSpan = document.createElement('span');
                      statusSpan.className = 'tech-unres-status';
                      statusSpan.textContent = `: ${u.status}`;
                      li.appendChild(statusSpan);
                    }
                    unresUl.appendChild(li);
                  }
                }
                unresBox.appendChild(unresUl);
                contentBox.appendChild(unresBox);
              }

              tech.appendChild(contentBox);
              article.appendChild(tech);
            }

            detailPanel.appendChild(article);
            browser.appendChild(detailPanel);

            // Render Relations Panel
            const relTitle = document.createElement('h2');
            relTitle.textContent = 'Relações';
            relationsPanel.appendChild(relTitle);

            const entityRels = (bookData.relations || []).filter(
              (r) => r.sourceEntityId === selectedId || r.targetEntityId === selectedId
            );

            if (entityRels.length === 0) {
              const noRel = document.createElement('p');
              noRel.textContent = 'Nenhuma relação registrada.';
              relationsPanel.appendChild(noRel);
            } else {
              const relList = document.createElement('ul');
              relList.className = 'site-relations-list';

              for (const r of entityRels) {
                const li = document.createElement('li');
                const isOutgoing = r.sourceEntityId === selectedId;
                const otherId = isOutgoing ? r.targetEntityId : r.sourceEntityId;
                const labelText = isOutgoing ? r.outgoingLabel : r.incomingLabel;

                const labelSpan = document.createElement('span');
                labelSpan.className = 'relation-label';
                labelSpan.textContent = `${labelText}: `;
                li.appendChild(labelSpan);

                const otherEntry = searchIndex
                  ? searchIndex.entries.find((e) => e.entityId === otherId)
                  : null;
                const otherName = otherEntry ? otherEntry.name : otherId;

                const link = document.createElement('a');
                link.href = `#/entity/${otherId}`;
                link.textContent = otherName;
                li.appendChild(link);

                relList.appendChild(li);
              }
              relationsPanel.appendChild(relList);
            }

            // Unresolved references (preview mode only)
            if (bookData.mode === 'restricted_preview' && Array.isArray(bookData.unresolvedReferences)) {
              const unres = bookData.unresolvedReferences.filter(
                (u) => !u.sourceEntityId || u.sourceEntityId === selectedId
              );
              if (unres.length > 0) {
                const unresTitle = document.createElement('h3');
                unresTitle.textContent = 'Referências Pendentes';
                relationsPanel.appendChild(unresTitle);

                const unresList = document.createElement('ul');
                unresList.className = 'site-unresolved-list';
                for (const u of unres) {
                  const uLi = document.createElement('li');

                  const uLabel = document.createElement('span');
                  uLabel.className = 'unresolved-label';
                  uLabel.textContent = 'Referência não vinculada: ';
                  uLi.appendChild(uLabel);

                  const uName = document.createElement('span');
                  uName.className = 'unresolved-name';
                  uName.textContent = u.name;
                  uLi.appendChild(uName);

                  unresList.appendChild(uLi);
                }
                relationsPanel.appendChild(unresList);
              }
            }

            browser.appendChild(relationsPanel);
          }
        } catch (err) {
          detailPanel.textContent = `Erro ao carregar detalhes: ${err.message}`;
          browser.appendChild(detailPanel);
        }
      }
    } else {
      const emptyMsg = document.createElement('div');
      emptyMsg.className = 'site-empty-detail';
      emptyMsg.textContent = 'Selecione uma entidade na lista para visualizar seus detalhes.';
      detailPanel.appendChild(emptyMsg);
      browser.appendChild(detailPanel);
    }

    mainContent.appendChild(browser);
  }

  function renderSearchView() {
    const container = document.createElement('div');
    container.className = 'site-search-view';

    const h1 = document.createElement('h1');
    h1.textContent = 'Busca de Entidades';
    container.appendChild(h1);

    // Filter controls: Book, Type, and Reset
    const filterBar = document.createElement('div');
    filterBar.className = 'site-search-filter-bar';

    // 1. Book Filter
    const bookWrap = document.createElement('div');
    bookWrap.className = 'site-search-filter-field';
    const bookLabel = document.createElement('label');
    bookLabel.htmlFor = 'siteSearchBookFilter';
    bookLabel.textContent = 'Livro:';
    const bookSelect = document.createElement('select');
    bookSelect.id = 'siteSearchBookFilter';
    bookSelect.setAttribute('aria-label', 'Filtrar por livro');

    const bookDefaultOpt = document.createElement('option');
    bookDefaultOpt.value = '';
    bookDefaultOpt.textContent = 'Todos os livros';
    bookSelect.appendChild(bookDefaultOpt);

    const availableBooks = catalog && Array.isArray(catalog.books) ? catalog.books : [];
    for (const b of availableBooks) {
      const opt = document.createElement('option');
      opt.value = b.bookId;
      opt.textContent = b.title;
      if (state.bookId === b.bookId) {
        opt.selected = true;
      }
      bookSelect.appendChild(opt);
    }

    bookSelect.addEventListener('change', (e) => {
      state = setFilters(state, { bookId: e.target.value || null });
      renderActiveView();
    });

    bookWrap.appendChild(bookLabel);
    bookWrap.appendChild(bookSelect);
    filterBar.appendChild(bookWrap);

    // 2. Type Filter (dynamically derived from authorized searchIndex entries)
    const typeWrap = document.createElement('div');
    typeWrap.className = 'site-search-filter-field';
    const typeLabel = document.createElement('label');
    typeLabel.htmlFor = 'siteSearchTypeFilter';
    typeLabel.textContent = 'Tipo:';
    const typeSelect = document.createElement('select');
    typeSelect.id = 'siteSearchTypeFilter';
    typeSelect.setAttribute('aria-label', 'Filtrar por tipo');

    const typeDefaultOpt = document.createElement('option');
    typeDefaultOpt.value = '';
    typeDefaultOpt.textContent = 'Todos os tipos';
    typeSelect.appendChild(typeDefaultOpt);

    const entries = searchIndex && Array.isArray(searchIndex.entries) ? searchIndex.entries : [];
    const uniqueTypesMap = new Map();
    for (const ent of entries) {
      const dt = ent.displayType || ent.type;
      if (dt && !uniqueTypesMap.has(dt)) {
        uniqueTypesMap.set(dt, { displayType: dt, type: ent.type });
      }
    }
    const sortedTypes = Array.from(uniqueTypesMap.values()).sort((a, b) =>
      a.displayType.localeCompare(b.displayType)
    );
    for (const t of sortedTypes) {
      const opt = document.createElement('option');
      opt.value = t.displayType;
      opt.textContent = t.displayType;
      if (state.type === t.displayType || state.type === t.type) {
        opt.selected = true;
      }
      typeSelect.appendChild(opt);
    }

    typeSelect.addEventListener('change', (e) => {
      state = setFilters(state, { type: e.target.value || null });
      renderActiveView();
    });

    typeWrap.appendChild(typeLabel);
    typeWrap.appendChild(typeSelect);
    filterBar.appendChild(typeWrap);

    // 3. Reset Button
    const resetBtn = document.createElement('button');
    resetBtn.id = 'siteSearchResetFilters';
    resetBtn.type = 'button';
    resetBtn.className = 'site-btn-reset-filters';
    resetBtn.textContent = 'Limpar filtros';
    resetBtn.addEventListener('click', () => {
      state = setFilters(state, { bookId: null, type: null, query: '' });
      searchInput.value = '';
      renderActiveView();
    });
    filterBar.appendChild(resetBtn);

    container.appendChild(filterBar);

    const countP = document.createElement('p');
    countP.className = 'site-search-count';

    const results = searchEntities(searchIndex ? searchIndex.entries : [], state.query, {
      bookId: state.bookId,
      type: state.type,
    });

    countP.textContent = `${results.length} resultado(s) encontrado(s).`;
    container.appendChild(countP);

    const list = document.createElement('div');
    list.className = 'site-search-results';

    for (const item of results) {
      const card = document.createElement('div');
      card.className = 'site-search-result-card';

      const titleLink = document.createElement('a');
      titleLink.href = `#/entity/${item.entityId}`;
      titleLink.textContent = item.name;
      titleLink.className = 'site-search-result-title';

      const badge = document.createElement('span');
      badge.className = 'site-badge';
      badge.textContent = item.displayType;

      const bookSpan = document.createElement('span');
      bookSpan.className = 'site-book-source';
      bookSpan.textContent = `Livro: ${item.bookTitle}`;

      card.appendChild(titleLink);
      card.appendChild(badge);
      card.appendChild(bookSpan);
      list.appendChild(card);
    }

    container.appendChild(list);
    mainContent.appendChild(container);
  }

  async function loadOpsData() {
    if (!opsClient) return;
    try {
      const snap = await opsClient.fetchSnapshot();
      if (snap) {
        state.ops.controlState = snap.controlState || { pausedBooks: [], priorityOverrides: {}, reprocessIntents: {} };
        state.ops.commands = snap.commands || [];
        state.ops.reviews = snap.reviews || [];
        state.ops.batch = snap.batch || null;
      }
    } catch (err) {
      console.warn('Ops snapshot error:', err);
    }
  }

  function promptOperatorIdentity(onSuccess, onCancel) {
    const existing = document.querySelector('.site-ops-modal-backdrop');
    if (existing) existing.remove();

    const backdrop = document.createElement('div');
    backdrop.className = 'site-ops-modal-backdrop';

    const panel = document.createElement('section');
    panel.className = 'site-ops-modal site-ops-modal-medium';
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-modal', 'true');
    panel.setAttribute('aria-label', 'Identificação do Operador Humano');

    const head = document.createElement('header');
    head.className = 'site-ops-modal-head';
    const h2 = document.createElement('h2');
    h2.textContent = 'Identificação do Operador Humano';
    head.appendChild(h2);
    panel.appendChild(head);

    const body = document.createElement('div');
    body.className = 'site-ops-modal-body';

    const pDesc = document.createElement('p');
    pDesc.textContent =
      'Para executar comandos operacionais ou resolver revisões na Release B, informe seu identificador humano para esta sessão (ex: seu nome ou matrícula). Valores em branco ou nomes de agentes automatizados serão rejeitados.';
    body.appendChild(pDesc);

    const errBox = document.createElement('div');
    errBox.className = 'site-ops-error-box';
    errBox.hidden = true;
    body.appendChild(errBox);

    const field = document.createElement('div');
    field.className = 'site-field';
    const label = document.createElement('label');
    label.htmlFor = 'siteOpsOperatorInput';
    label.textContent = 'Identificador do Operador:';
    const input = document.createElement('input');
    input.id = 'siteOpsOperatorInput';
    input.type = 'text';
    input.placeholder = 'ex: alice-silva';
    input.value = state.ops.operatorId || '';
    field.appendChild(label);
    field.appendChild(input);
    body.appendChild(field);
    panel.appendChild(body);

    const foot = document.createElement('footer');
    foot.className = 'site-ops-modal-foot';

    const cancelBtn = document.createElement('button');
    cancelBtn.type = 'button';
    cancelBtn.className = 'site-btn-cancel';
    cancelBtn.textContent = 'Cancelar';
    cancelBtn.addEventListener('click', () => {
      backdrop.remove();
      if (onCancel) onCancel();
    });

    const confirmBtn = document.createElement('button');
    confirmBtn.type = 'button';
    confirmBtn.className = 'site-btn-confirm site-btn-primary';
    confirmBtn.textContent = 'Confirmar Identidade';

    const handleConfirm = () => {
      const val = input.value.trim();
      if (!val) {
        errBox.textContent = 'O identificador do operador não pode ser vazio.';
        errBox.hidden = false;
        return;
      }
      const automated = ['gemini', 'claude', 'gpt', 'bot', 'subagent', 'pipeline', 'automated', 'system', 'agent'];
      if (automated.includes(val.toLowerCase())) {
        errBox.textContent = 'Identificador de agente automatizado não é permitido no console humano.';
        errBox.hidden = false;
        return;
      }
      const sessionStore = typeof window !== 'undefined' ? window.sessionStorage : null;
      state = setOperatorId(state, val, sessionStore);
      backdrop.remove();
      if (onSuccess) onSuccess(val);
    };

    confirmBtn.addEventListener('click', handleConfirm);
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') handleConfirm();
    });

    foot.appendChild(cancelBtn);
    foot.appendChild(confirmBtn);
    panel.appendChild(foot);
    backdrop.appendChild(panel);
    root.appendChild(backdrop);
    input.focus();
  }

  function ensureOperatorId(onReady) {
    if (state.ops.operatorId && state.ops.operatorId.trim().length > 0) {
      onReady(state.ops.operatorId.trim());
      return;
    }
    promptOperatorIdentity(onReady);
  }

  function openRiskModal({ title, riskLevel, message, targetBookId = null, onConfirm }) {
    const existing = document.querySelector('.site-ops-modal-backdrop');
    if (existing) existing.remove();

    const backdrop = document.createElement('div');
    backdrop.className = 'site-ops-modal-backdrop';

    const panel = document.createElement('section');
    panel.className = `site-ops-modal site-ops-modal-${riskLevel.toLowerCase()}`;
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-modal', 'true');
    panel.setAttribute('aria-label', title);

    const head = document.createElement('header');
    head.className = 'site-ops-modal-head';
    const h2 = document.createElement('h2');
    h2.textContent = title;
    const badge = document.createElement('span');
    badge.className = `site-badge site-badge-risk-${riskLevel.toLowerCase()}`;
    badge.textContent =
      riskLevel === 'HIGH' ? 'ALTO RISCO — ATENÇÃO' : (riskLevel === 'MEDIUM' ? 'MÉDIO RISCO' : 'BAIXO RISCO');
    head.appendChild(h2);
    head.appendChild(badge);
    panel.appendChild(head);

    const body = document.createElement('div');
    body.className = 'site-ops-modal-body';

    const msgP = document.createElement('p');
    msgP.textContent = message;
    body.appendChild(msgP);

    let reasonInput = null;
    let confirmCheckbox = null;
    let typedInput = null;

    if (riskLevel === 'MEDIUM' || riskLevel === 'HIGH') {
      const reasonLabel = document.createElement('label');
      reasonLabel.textContent = 'Motivo / Justificativa (obrigatório):';
      reasonLabel.className = 'site-ops-field-label';
      reasonInput = document.createElement('textarea');
      reasonInput.className = 'site-ops-textarea';
      reasonInput.placeholder = 'Explique a razão técnica ou operacional desta decisão...';
      body.appendChild(reasonLabel);
      body.appendChild(reasonInput);

      const checkWrap = document.createElement('label');
      checkWrap.className = 'site-ops-checkbox-label';
      confirmCheckbox = document.createElement('input');
      confirmCheckbox.type = 'checkbox';
      checkWrap.appendChild(confirmCheckbox);
      const checkSpan = document.createElement('span');
      checkSpan.textContent = ' Estou ciente das consequências desta ação operacional.';
      checkWrap.appendChild(checkSpan);
      body.appendChild(checkWrap);
    }

    if (riskLevel === 'HIGH') {
      const typedLabel = document.createElement('label');
      typedLabel.className = 'site-ops-field-label site-ops-danger-text';
      typedLabel.textContent = `Digite "${targetBookId}" exatamente para confirmar autoridade humana:`;
      typedInput = document.createElement('input');
      typedInput.type = 'text';
      typedInput.className = 'site-ops-input';
      typedInput.placeholder = targetBookId;
      body.appendChild(typedLabel);
      body.appendChild(typedInput);
    }

    const errBox = document.createElement('div');
    errBox.className = 'site-ops-error-box';
    errBox.hidden = true;
    body.appendChild(errBox);

    panel.appendChild(body);

    const foot = document.createElement('footer');
    foot.className = 'site-ops-modal-foot';

    const cancelBtn = document.createElement('button');
    cancelBtn.type = 'button';
    cancelBtn.className = 'site-btn-cancel';
    cancelBtn.textContent = 'Cancelar';
    cancelBtn.addEventListener('click', () => backdrop.remove());

    const confirmBtn = document.createElement('button');
    confirmBtn.type = 'button';
    confirmBtn.className = `site-btn-confirm ${riskLevel === 'HIGH' ? 'site-btn-danger' : 'site-btn-primary'}`;
    confirmBtn.textContent = 'Confirmar Ação';

    function checkValidity() {
      if (riskLevel === 'LOW') {
        confirmBtn.disabled = false;
        return;
      }
      const hasReason = reasonInput && reasonInput.value.trim().length > 0;
      const isChecked = confirmCheckbox && confirmCheckbox.checked;
      let typedOk = true;
      if (riskLevel === 'HIGH') {
        typedOk = typedInput && typedInput.value.trim() === targetBookId;
      }
      confirmBtn.disabled = !(hasReason && isChecked && typedOk);
    }

    if (riskLevel !== 'LOW') {
      confirmBtn.disabled = true;
      if (reasonInput) reasonInput.addEventListener('input', checkValidity);
      if (confirmCheckbox) confirmCheckbox.addEventListener('change', checkValidity);
      if (typedInput) typedInput.addEventListener('input', checkValidity);
    }

    confirmBtn.addEventListener('click', async () => {
      confirmBtn.disabled = true;
      errBox.hidden = true;
      try {
        await onConfirm({
          reason: reasonInput ? reasonInput.value.trim() : 'Comando operacional',
          confirmed: true,
          typedConfirmation: typedInput ? typedInput.value.trim() : undefined,
        });
        backdrop.remove();
      } catch (err) {
        confirmBtn.disabled = false;
        errBox.textContent = err.message || 'Erro ao processar comando';
        errBox.hidden = false;
      }
    });

    foot.appendChild(cancelBtn);
    foot.appendChild(confirmBtn);
    panel.appendChild(foot);
    backdrop.appendChild(panel);
    root.appendChild(backdrop);
  }

  async function renderOpsDashboard(activeTab = 'overview', version = renderVersion) {
    await loadOpsData();
    if (version !== renderVersion) return;

    const container = document.createElement('div');
    container.className = 'site-ops-view';

    const header = document.createElement('header');
    header.className = 'site-ops-header';
    const h1 = document.createElement('h1');
    h1.textContent = state.ops.batch ? 'Painel de Controle Operacional — Release C' : 'Painel de Controle Operacional — Release B';
    const sub = document.createElement('p');
    sub.className = 'site-ops-meta';
    const opDisplay = state.ops.operatorId ? escapeHtml(state.ops.operatorId) : 'Não identificado';
    const sseDisplay = escapeHtml(state.ops.sseStatus || 'DESCONECTADA');
    sub.innerHTML = `Modo: Restricted Preview | Operador: <strong>${opDisplay}</strong> | Conexão SSE: <strong>${sseDisplay}</strong>`;

    const changeOpBtn = document.createElement('button');
    changeOpBtn.type = 'button';
    changeOpBtn.className = 'site-btn-secondary site-btn-sm';
    changeOpBtn.style.marginLeft = '1rem';
    changeOpBtn.textContent = state.ops.operatorId ? 'Alterar Operador' : 'Identificar Operador';
    changeOpBtn.addEventListener('click', () => {
      promptOperatorIdentity(() => {
        renderActiveView();
      });
    });
    sub.appendChild(changeOpBtn);

    header.appendChild(h1);
    header.appendChild(sub);
    if (state.ops.batch) {
      const batchInfo = document.createElement('p');
      batchInfo.textContent = `Motor ativo: ${state.ops.batch.activeBooks.length}/${state.ops.batch.concurrency} livros. Aprovação privada exige revisão humana; publicação tem validação própria.`;
      header.appendChild(batchInfo);
      if (state.ops.batch.fatalError) {
        const engineError = document.createElement('p');
        engineError.setAttribute('role', 'alert');
        engineError.textContent = `Motor interrompido: ${state.ops.batch.fatalError}`;
        header.appendChild(engineError);
      }
    }
    container.appendChild(header);

    // Nav tabs
    const tabs = document.createElement('nav');
    tabs.className = 'site-ops-tabs';
    tabs.setAttribute('aria-label', 'Seções operacionais');

    const pendingReviews = (state.ops.reviews || []).filter((r) => r.status === 'PENDING');
    const tabItems = [
      { id: 'overview', label: 'Visão Geral', href: '#/ops' },
      { id: 'queue', label: 'Fila e Concorrência', href: '#/ops/queue' },
      { id: 'reviews', label: `Revisão Humana (${pendingReviews.length})`, href: '#/ops/reviews' },
    ];

    for (const t of tabItems) {
      const a = document.createElement('a');
      a.href = t.href;
      a.textContent = t.label;
      a.className = `site-ops-tab ${activeTab === t.id ? 'active' : ''}`;
      tabs.appendChild(a);
    }
    container.appendChild(tabs);

    // Summary metrics cards
    const metricsGrid = document.createElement('div');
    metricsGrid.className = 'site-ops-metrics-grid';

    const batchBooks = state.ops.batch && state.ops.batch.books;
    const totalBooks = batchBooks ? batchBooks.length : (catalog && catalog.books ? catalog.books.length : 281);
    const pausedBooks = (state.ops.controlState && state.ops.controlState.pausedBooks) || [];
    const pauseList = state.ops.batch ? state.ops.batch.books.filter((b) => b.paused) : ((state.ops.controlState && state.ops.controlState.pauseRequests) || pausedBooks);
    const operationalBooks = batchBooks || (catalog && catalog.books) || [];
    const doneBooks = operationalBooks.filter((b) => b.pipelineStatus === 'DONE' || b.pipelineStatus === 'APPROVED_PRIVATE').length;
    const runningBooks = operationalBooks.filter((b) => b.pipelineStatus === 'RUNNING').length;

    const cards = [
      { label: batchBooks ? 'Livros no lote' : 'Total Acervo', value: totalBooks },
      { label: 'Aprovados', value: doneBooks },
      { label: 'Em Execução', value: runningBooks },
      { label: 'Revisão Pendente', value: pendingReviews.length },
      { label: 'Pausa Solicitada', value: pauseList.length },
    ];

    for (const c of cards) {
      const card = document.createElement('div');
      card.className = 'site-ops-metric-card';
      const val = document.createElement('strong');
      val.textContent = String(c.value);
      const lbl = document.createElement('span');
      lbl.textContent = c.label;
      card.appendChild(val);
      card.appendChild(lbl);
      metricsGrid.appendChild(card);
    }
    container.appendChild(metricsGrid);

    // Render active tab content
    const tabContent = document.createElement('div');
    tabContent.className = 'site-ops-tab-content';

    if (activeTab === 'overview') {
      // Overrides Summary
      const overridesSec = document.createElement('section');
      overridesSec.className = 'site-ops-section';
      const secH2 = document.createElement('h2');
      secH2.textContent = 'Controles Operacionais Ativos';
      overridesSec.appendChild(secH2);

      const pDesc = document.createElement('p');
      pDesc.textContent = `Livros com Pausa Solicitada (${pauseList.length}): ${pauseList.length > 0 ? pauseList.join(', ') : 'Nenhum'}`;
      overridesSec.appendChild(pDesc);
      tabContent.appendChild(overridesSec);

      // Audit list
      const auditSec = document.createElement('section');
      auditSec.className = 'site-ops-section';
      const auditH2 = document.createElement('h2');
      auditH2.textContent = 'Últimos Comandos Operacionais';
      auditSec.appendChild(auditH2);

      const cmds = state.ops.commands || [];
      if (cmds.length === 0) {
        const noCmd = document.createElement('p');
        noCmd.textContent = 'Nenhum comando registrado ainda nesta sessão.';
        auditSec.appendChild(noCmd);
      } else {
        const cmdList = document.createElement('div');
        cmdList.className = 'site-ops-cmd-list';
        for (const cmd of cmds.slice(-10).reverse()) {
          const item = document.createElement('div');
          item.className = 'site-ops-cmd-item';
          const title = document.createElement('strong');
          title.textContent = `${cmd.commandType} (${cmd.commandId})`;
          const meta = document.createElement('span');
          meta.className = 'site-ops-cmd-meta';
          meta.textContent = `Status: ${cmd.status} | Operador: ${cmd.operatorId} | Livro: ${cmd.bookId || '-'}`;
          item.appendChild(title);
          item.appendChild(meta);
          cmdList.appendChild(item);
        }
        auditSec.appendChild(cmdList);
      }
      tabContent.appendChild(auditSec);

    } else if (activeTab === 'queue') {
      const queueSec = document.createElement('section');
      queueSec.className = 'site-ops-section';
      const qH2 = document.createElement('h2');
      qH2.textContent = 'Controle de Fila e Prioridade de Livros';
      queueSec.appendChild(qH2);

      const booksList = operationalBooks.slice(0, 50);
      const table = document.createElement('table');
      table.className = 'site-ops-table';

      const thead = document.createElement('thead');
      thead.innerHTML = `<tr><th>Livro</th><th>Status</th><th>Prioridade</th><th>Ações</th></tr>`;
      table.appendChild(thead);

      const tbody = document.createElement('tbody');
      for (const b of booksList) {
        const tr = document.createElement('tr');
        const isPauseRequested = state.ops.batch ? b.paused : (
          (state.ops.controlState && state.ops.controlState.pauseRequests && state.ops.controlState.pauseRequests.includes(b.bookId)) ||
          pausedBooks.includes(b.bookId)
        );
        const priorityOverrides = (state.ops.controlState && state.ops.controlState.priorityOverrides) || {};
        const prio = b.priorityWeight || priorityOverrides[b.bookId] || 100;

        const tdBook = document.createElement('td');
        tdBook.textContent = b.title || b.bookId;

        const tdStatus = document.createElement('td');
        tdStatus.textContent = isPauseRequested ? 'PAUSA SOLICITADA' : (b.pipelineStatus || 'WAITING');
        if (state.ops.batch && b.currentStage) {
          const stageNames = { source: 'Fonte', extraction: 'Extração', editorial: 'Editorial', entities: 'Entidades', relations: 'Relações', frontend: 'Apresentação', qa: 'Validação', release: 'Publicação pendente' };
          const stageInfo = document.createElement('small');
          stageInfo.textContent = ` ${stageNames[b.currentStage] || b.currentStage} (${b.completedStages}/7)`;
          tdStatus.appendChild(stageInfo);
        }

        const tdPrio = document.createElement('td');
        tdPrio.textContent = String(prio);

        const tdActions = document.createElement('td');
        tdActions.className = 'site-ops-actions-cell';

        // Pause / Resume button
        const pauseBtn = document.createElement('button');
        pauseBtn.type = 'button';
        pauseBtn.className = isPauseRequested ? 'site-btn-resume' : 'site-btn-pause';
        pauseBtn.textContent = isPauseRequested ? 'Retomar' : 'Pausar';
        pauseBtn.addEventListener('click', () => {
          ensureOperatorId((opId) => {
            openRiskModal({
              title: isPauseRequested ? 'Retomar Livro' : 'Pausar Livro',
              riskLevel: 'LOW',
              message: `Confirma ${isPauseRequested ? 'a retomada' : 'a solicitação de pausa'} do livro "${b.bookId}" no processamento?`,
              targetBookId: b.bookId,
              onConfirm: async (res) => {
                await opsClient.submitCommand({
                  commandType: isPauseRequested ? 'RESUME_BOOK' : 'PAUSE_BOOK',
                  bookId: b.bookId,
                  reason: res.reason,
                  operatorId: opId,
                  confirmation: { confirmed: true },
                });
                await loadOpsData();
                renderActiveView();
              },
            });
          });
        });
        tdActions.appendChild(pauseBtn);

        // Priority button
        const prioBtn = document.createElement('button');
        prioBtn.type = 'button';
        prioBtn.className = 'site-btn-priority';
        prioBtn.textContent = 'Priorizar';
        prioBtn.addEventListener('click', () => {
          ensureOperatorId((opId) => {
            const newWeightStr = window.prompt(`Defina a nova prioridade para "${b.bookId}" (1-200):`, String(prio));
            if (!newWeightStr) return;
            const weight = parseInt(newWeightStr, 10);
            if (isNaN(weight)) return;

            openRiskModal({
              title: 'Alterar Prioridade',
              riskLevel: 'LOW',
              message: `Definir peso de prioridade ${weight} para "${b.bookId}"?`,
              targetBookId: b.bookId,
              onConfirm: async (res) => {
                await opsClient.submitCommand({
                  commandType: 'PRIORITIZE_BOOK',
                  bookId: b.bookId,
                  payload: { priorityWeight: weight },
                  reason: res.reason,
                  operatorId: opId,
                  confirmation: { confirmed: true },
                });
                await loadOpsData();
                renderActiveView();
              },
            });
          });
        });
        tdActions.appendChild(prioBtn);

        if (state.ops.batch) {
          const stageSelect = document.createElement('select');
          stageSelect.setAttribute('aria-label', `Etapa para reprocessar ${b.title || b.bookId}`);
          for (const [value, label] of [['SOURCE', 'Fonte'], ['EXTRACTION', 'Extração'], ['EDITORIAL', 'Editorial'], ['ENTITIES', 'Entidades'], ['RELATIONS', 'Relações'], ['FRONTEND', 'Apresentação'], ['QA', 'Validação final']]) {
            const option = document.createElement('option');
            option.value = value;
            option.textContent = label;
            stageSelect.appendChild(option);
          }
          tdActions.appendChild(stageSelect);
          const reprocessBtn = document.createElement('button');
          reprocessBtn.type = 'button';
          reprocessBtn.textContent = 'Reprocessar';
          reprocessBtn.addEventListener('click', () => ensureOperatorId((opId) => {
            const stage = stageSelect.value;
            openRiskModal({
              title: 'Reprocessar etapa', riskLevel: 'MEDIUM', targetBookId: b.bookId,
              message: `Reexecutar a etapa selecionada e suas sucessoras para "${b.bookId}"?`,
              onConfirm: async (res) => {
                await opsClient.submitCommand({ commandType: 'REPROCESS_STAGE', bookId: b.bookId,
                  payload: { stage }, reason: res.reason, operatorId: opId, confirmation: { confirmed: true } });
                await loadOpsData();
                renderActiveView();
              },
            });
          }));
          tdActions.appendChild(reprocessBtn);
          const dequeueBtn = document.createElement('button');
          dequeueBtn.type = 'button';
          dequeueBtn.textContent = 'Retirar da fila';
          dequeueBtn.addEventListener('click', () => ensureOperatorId((opId) => openRiskModal({
            title: 'Retirar livro da fila', riskLevel: 'MEDIUM', targetBookId: b.bookId,
            message: `Retirar "${b.bookId}" após a etapa atual terminar?`,
            onConfirm: async (res) => {
              await opsClient.submitCommand({ commandType: 'DEQUEUE_BOOK', bookId: b.bookId,
                reason: res.reason, operatorId: opId, confirmation: { confirmed: true } });
              await loadOpsData();
              renderActiveView();
            },
          })));
          tdActions.appendChild(dequeueBtn);
        }

        tr.appendChild(tdBook);
        tr.appendChild(tdStatus);
        tr.appendChild(tdPrio);
        tr.appendChild(tdActions);
        tbody.appendChild(tr);
      }
      table.appendChild(tbody);
      queueSec.appendChild(table);
      tabContent.appendChild(queueSec);

    } else if (activeTab === 'reviews') {
      const reviewSec = document.createElement('section');
      reviewSec.className = 'site-ops-section';
      const rH2 = document.createElement('h2');
      rH2.textContent = 'Fila de Decisões Humanas Pendentes';
      reviewSec.appendChild(rH2);

      const allReviews = state.ops.reviews || [];
      if (allReviews.length === 0) {
        const emptyRev = document.createElement('p');
        emptyRev.textContent = 'Nenhuma revisão pendente no momento.';
        reviewSec.appendChild(emptyRev);
      } else {
        const revList = document.createElement('div');
        revList.className = 'site-ops-review-list';

        for (const rev of allReviews) {
          const card = document.createElement('div');
          card.className = `site-ops-review-card site-ops-review-card-${rev.status.toLowerCase()}`;

          const cHead = document.createElement('div');
          cHead.className = 'site-ops-review-head';

          const rTitle = document.createElement('h3');
          rTitle.textContent = `${rev.reviewId} — Livro: ${rev.bookId}`;

          const badgeWrap = document.createElement('div');
          badgeWrap.className = 'site-ops-badges-wrap';

          const catBadge = document.createElement('span');
          catBadge.className = `site-badge site-badge-${rev.category.toLowerCase()}`;
          catBadge.textContent = rev.category;

          const statusBadge = document.createElement('span');
          statusBadge.className = `site-badge site-badge-status-${rev.status.toLowerCase()}`;
          statusBadge.textContent = rev.status;

          badgeWrap.appendChild(catBadge);
          badgeWrap.appendChild(statusBadge);
          cHead.appendChild(rTitle);
          cHead.appendChild(badgeWrap);
          card.appendChild(cHead);

          const probP = document.createElement('p');
          probP.className = 'site-ops-problem-text';
          probP.textContent = rev.problem;
          card.appendChild(probP);

          const actLink = document.createElement('a');
          actLink.href = `#/ops/review/${rev.reviewId}`;
          actLink.className = 'site-btn-action-link';
          actLink.textContent = rev.status === 'PENDING' ? 'Examinar e Decidir →' : 'Ver Detalhes da Decisão →';
          card.appendChild(actLink);

          revList.appendChild(card);
        }
        reviewSec.appendChild(revList);
      }
      tabContent.appendChild(reviewSec);
    }

    container.appendChild(tabContent);
    mainContent.appendChild(container);
  }

  async function renderOpsReviewDetail(reviewId, version = renderVersion) {
    await loadOpsData();
    if (version !== renderVersion) return;

    const review = (state.ops.reviews || []).find((r) => r.reviewId === reviewId);
    const container = document.createElement('div');
    container.className = 'site-ops-review-detail-view';

    const backLink = document.createElement('a');
    backLink.href = '#/ops/reviews';
    backLink.className = 'site-back-link';
    backLink.textContent = '← Voltar para a Fila de Revisão';
    container.appendChild(backLink);

    if (!review) {
      const notFound = document.createElement('p');
      notFound.textContent = `Revisão "${reviewId}" não encontrada no sistema operacional.`;
      container.appendChild(notFound);
      mainContent.appendChild(container);
      return;
    }

    const h1 = document.createElement('h1');
    h1.textContent = `Revisão Humana: ${review.reviewId}`;
    container.appendChild(h1);

    // Meta box
    const metaBox = document.createElement('div');
    metaBox.className = 'site-ops-detail-meta';
    metaBox.innerHTML = `
      <div><strong>Livro:</strong> <span>${escapeHtml(review.bookId)}</span></div>
      <div><strong>Estágio:</strong> <span>${escapeHtml(review.stage)}</span></div>
      <div><strong>Categoria:</strong> <span class="site-badge site-badge-${escapeHtml(review.category.toLowerCase())}">${escapeHtml(review.category)}</span></div>
      <div><strong>Status:</strong> <span class="site-badge">${escapeHtml(review.status)}</span></div>
    `;
    container.appendChild(metaBox);

    // Problem description
    const probSec = document.createElement('section');
    probSec.className = 'site-ops-section';
    const probH2 = document.createElement('h2');
    probH2.textContent = 'Problema Identificado';
    const probP = document.createElement('p');
    probP.textContent = review.problem || review.summary || '';
    probSec.appendChild(probH2);
    probSec.appendChild(probP);
    container.appendChild(probSec);

    // Evidence / Diff Section (Safe textContent)
    const evSec = document.createElement('section');
    evSec.className = 'site-ops-section';
    const evH2 = document.createElement('h2');
    evH2.textContent = 'Evidência / Contexto Técnico';
    evSec.appendChild(evH2);

    const diffBox = document.createElement('div');
    diffBox.className = 'site-ops-diff-viewer';
    const pre = document.createElement('pre');
    pre.textContent = JSON.stringify(review.evidence || {}, null, 2);
    diffBox.appendChild(pre);
    evSec.appendChild(diffBox);
    if (state.ops.batch && review.reviewKind && review.reviewKind.startsWith('BATCH_')) {
      for (const relative of review.artifactRefs || []) {
        const download = document.createElement('a');
        download.href = `/api/ops/reviews/${encodeURIComponent(review.reviewId)}/artifact?path=${encodeURIComponent(relative)}`;
        download.textContent = `Baixar evidência privada: ${relative.split('/').pop()}`;
        download.className = 'site-btn-action-link';
        evSec.appendChild(download);
      }
    }
    container.appendChild(evSec);

    if (review.recommendation) {
      const recSec = document.createElement('section');
      recSec.className = 'site-ops-section';
      const recH2 = document.createElement('h2');
      recH2.textContent = 'Recomendação dos Agentes';
      const recP = document.createElement('p');
      recP.textContent = review.recommendation;
      recSec.appendChild(recH2);
      recSec.appendChild(recP);
      container.appendChild(recSec);
    }

    // Decision block
    const decSec = document.createElement('section');
    decSec.className = 'site-ops-section site-ops-decision-section';

    if (review.status === 'PENDING') {
      const decH2 = document.createElement('h2');
      decH2.textContent = 'Decisão Humana Obrigatória';
      decSec.appendChild(decH2);

      const btnRow = document.createElement('div');
      btnRow.className = 'site-ops-btn-row';

      // 1. Approve button
      const approveBtn = document.createElement('button');
      approveBtn.type = 'button';
      approveBtn.className = 'site-btn-approve';
      approveBtn.textContent = 'Aprovar Revisão';
      approveBtn.addEventListener('click', () => {
        ensureOperatorId((opId) => {
          const isHigh = review.category === 'POLICY_OR_RIGHTS';
          openRiskModal({
            title: isHigh ? 'Aprovação de Alto Risco — Direitos e Políticas' : 'Aprovar Revisão',
            riskLevel: isHigh ? 'HIGH' : 'LOW',
            targetBookId: review.bookId,
            message: isHigh
              ? `Esta revisão envolve direitos/política para "${review.bookId}". Sua aprovação assume autoridade humana formal.`
              : `Confirma a aprovação da revisão para o livro "${review.bookId}"?`,
            onConfirm: async (res) => {
              await opsClient.submitCommand({
                commandType: 'APPROVE_REVIEW',
                bookId: review.bookId,
                reviewId: review.reviewId,
                payload: review.snapshotSha256 ? { snapshotSha256: review.snapshotSha256 } : {},
                reason: res.reason,
                operatorId: opId,
                confirmation: { confirmed: true, typedConfirmation: res.typedConfirmation },
              });
              await loadOpsData();
              renderActiveView();
            },
          });
        });
      });
      btnRow.appendChild(approveBtn);

      // 2. Reject button
      const rejectBtn = document.createElement('button');
      rejectBtn.type = 'button';
      rejectBtn.className = 'site-btn-reject';
      rejectBtn.textContent = 'Rejeitar';
      rejectBtn.addEventListener('click', () => {
        ensureOperatorId((opId) => {
          openRiskModal({
            title: 'Rejeitar Revisão (Médio Risco)',
            riskLevel: 'MEDIUM',
            targetBookId: review.bookId,
            message: `Rejeitar esta alteração para o livro "${review.bookId}". Justificativa técnica obrigatória.`,
            onConfirm: async (res) => {
              await opsClient.submitCommand({
                commandType: 'REJECT_REVIEW',
                bookId: review.bookId,
                reviewId: review.reviewId,
                payload: review.snapshotSha256 ? { snapshotSha256: review.snapshotSha256 } : {},
                reason: res.reason,
                operatorId: opId,
                confirmation: { confirmed: true },
              });
              await loadOpsData();
              renderActiveView();
            },
          });
        });
      });
      btnRow.appendChild(rejectBtn);

      // 3. Request correction button
      const reqCorBtn = document.createElement('button');
      reqCorBtn.type = 'button';
      reqCorBtn.className = 'site-btn-correction';
      reqCorBtn.textContent = 'Solicitar Correção';
      reqCorBtn.addEventListener('click', () => {
        ensureOperatorId((opId) => {
          openRiskModal({
            title: 'Solicitar Correção (Médio Risco)',
            riskLevel: 'MEDIUM',
            targetBookId: review.bookId,
            message: `Solicitar correção para os agentes no livro "${review.bookId}". Indique os ajustes exigidos.`,
            onConfirm: async (res) => {
              await opsClient.submitCommand({
                commandType: 'REQUEST_CORRECTION',
                bookId: review.bookId,
                reviewId: review.reviewId,
                payload: review.snapshotSha256 ? { snapshotSha256: review.snapshotSha256 } : {},
                reason: res.reason,
                operatorId: opId,
                confirmation: { confirmed: true },
              });
              await loadOpsData();
              renderActiveView();
            },
          });
        });
      });
      btnRow.appendChild(reqCorBtn);

      decSec.appendChild(btnRow);
    } else if (review.status === 'SUPERSEDED') {
      const retired = document.createElement('p');
      retired.textContent = `Revisão substituída: ${review.supersededReason || 'As entradas ou etapas foram alteradas.'}`;
      decSec.appendChild(retired);
    } else {
      const resH2 = document.createElement('h2');
      resH2.textContent = 'Decisão Registrada';
      decSec.appendChild(resH2);

      const resBox = document.createElement('div');
      resBox.className = 'site-ops-resolved-box';
      resBox.innerHTML = `
        <p><strong>Decisão:</strong> ${escapeHtml(review.resolutionAction || 'RESOLVIDA')}</p>
        <p><strong>Decidido por:</strong> ${escapeHtml(review.decidedBy || 'Humano')}</p>
        <p><strong>Data/Hora:</strong> ${escapeHtml(review.resolvedAt || '-')}</p>
        <p><strong>ID da Decisão:</strong> ${escapeHtml(review.decisionId || '-')}</p>
      `;
      decSec.appendChild(resBox);
    }

    container.appendChild(decSec);
    mainContent.appendChild(container);
  }

  function renderNotFoundView() {
    const container = document.createElement('div');
    container.className = 'site-not-found';
    const h1 = document.createElement('h1');
    h1.textContent = 'Página Não Encontrada';
    const p = document.createElement('p');
    p.textContent = 'A rota solicitada não existe ou foi movida.';
    const link = document.createElement('a');
    link.href = '#/';
    link.textContent = 'Retornar ao Início';
    container.appendChild(h1);
    container.appendChild(p);
    container.appendChild(link);
    mainContent.appendChild(container);
  }

  // Handle hash change
  function onHashChange() {
    state = setRoute(state, window.location.hash);
    renderActiveView();
  }

  window.addEventListener('hashchange', onHashChange);

  // Initial load
  (async () => {
    try {
      catalog = await store.loadCatalog();
      searchIndex = await store.loadSearchIndex();
      await renderActiveView();
    } catch (err) {
      renderError(`Erro ao carregar dados do site: ${err.message}`);
    }
  })();

  return {
    destroy() {
      window.removeEventListener('hashchange', onHashChange);
      if (opsEventsConnection && typeof opsEventsConnection.close === 'function') {
        opsEventsConnection.close();
        opsEventsConnection = null;
      }
      clearNode(root);
    },
  };
}
