/**
 * Daemon Tools — Site UI Presentation & Responsive Layout Integration (ES Module)
 * Pure vanilla DOM, secure textContent injection, zero unsafe innerHTML.
 */

import { searchEntities, filterBooks } from './site-search.mjs';
import { createState, parseRoute, setLayout, setRoute, setFilters, setBookFilters } from './site-state.mjs';

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
export function mountSite({ root, store, storage = localStorage }) {
  let state = createState(storage, window.location.hash || '#/');
  let catalog = null;
  let searchIndex = null;
  let isPreferencesOpen = false;

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

    // Pipeline status filter
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
      clearNode(root);
    },
  };
}
