/**
 * Daemon Tools — Site View Model Store and Client-Side Validator (ES Module)
 * Implements strict, fail-closed schema validation and lazy per-book loading.
 */

const EXPECTED_VERSION = '1';
const VALID_MODES = new Set(['restricted_preview', 'public']);

export class SiteModelError extends Error {
  constructor(message) {
    super(message);
    this.name = 'SiteModelError';
  }
}

/**
 * Validates envelope headers and ensures projection consistency across artifacts.
 */
function validateEnvelopeHeader(payload, expected) {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    throw new SiteModelError('Payload deve ser um objeto JSON válido');
  }

  if (payload.siteViewModelVersion !== EXPECTED_VERSION) {
    throw new SiteModelError(
      `Versão incompatível: ${payload.siteViewModelVersion} (esperada: ${EXPECTED_VERSION})`
    );
  }

  if (!VALID_MODES.has(payload.mode)) {
    throw new SiteModelError(`Modo de projeção inválido: ${payload.mode}`);
  }

  if (!payload.projectionId || typeof payload.projectionId !== 'string') {
    throw new SiteModelError('projectionId ausente ou inválido');
  }

  if (expected) {
    if (expected.mode && payload.mode !== expected.mode) {
      throw new SiteModelError(
        `Projeção inconsistente: modo '${payload.mode}' difere de '${expected.mode}'`
      );
    }
    if (expected.projectionId && payload.projectionId !== expected.projectionId) {
      throw new SiteModelError(
        `Projeção inconsistente: projectionId '${payload.projectionId}' difere de '${expected.projectionId}'`
      );
    }
  }

  return payload;
}

/**
 * Validates catalog.json envelope and book declarations.
 */
function validateCatalogPayload(payload) {
  validateEnvelopeHeader(payload);

  if (!Array.isArray(payload.books)) {
    throw new SiteModelError("Catálogo inválido: propriedade 'books' deve ser um array");
  }

  const bookMap = new Map();
  for (const b of payload.books) {
    if (!b || typeof b !== 'object') {
      throw new SiteModelError('Entrada de livro no catálogo inválida');
    }
    const { bookId, title, publicationMode, path } = b;
    if (!bookId || typeof bookId !== 'string') {
      throw new SiteModelError('Livro no catálogo sem bookId válido');
    }
    if (!title || typeof title !== 'string') {
      throw new SiteModelError(`Livro '${bookId}' sem título válido`);
    }
    if (!publicationMode || typeof publicationMode !== 'string') {
      throw new SiteModelError(`Livro '${bookId}' sem publicationMode válido`);
    }
    if (!path || path !== `books/${bookId}.json`) {
      throw new SiteModelError(
        `Livro '${bookId}' com caminho inválido: '${path}' (esperado: 'books/${bookId}.json')`
      );
    }
    if (bookMap.has(bookId)) {
      throw new SiteModelError(`Livro duplicado no catálogo: '${bookId}'`);
    }
    bookMap.set(bookId, b);
  }

  return payload;
}

/**
 * Validates search-index.json envelope and search entries.
 */
function validateSearchIndexPayload(payload, expected) {
  validateEnvelopeHeader(payload, expected);

  if (!Array.isArray(payload.entries)) {
    throw new SiteModelError("Índice de busca inválido: propriedade 'entries' deve ser um array");
  }

  const seenEntityIds = new Set();
  for (const e of payload.entries) {
    if (!e || typeof e !== 'object') {
      throw new SiteModelError('Entrada no índice de busca inválida');
    }
    const { entityId, route, name, type, displayType, bookId, searchText } = e;
    if (!entityId || typeof entityId !== 'string') {
      throw new SiteModelError('Entrada no índice sem entityId válido');
    }
    if (route !== `#/entity/${entityId}`) {
      throw new SiteModelError(
        `Entrada '${entityId}' com rota inválida: '${route}' (esperada: '#/entity/${entityId}')`
      );
    }
    if (!name || typeof name !== 'string') {
      throw new SiteModelError(`Entrada '${entityId}' sem nome válido`);
    }
    if (!type || typeof type !== 'string') {
      throw new SiteModelError(`Entrada '${entityId}' sem tipo válido`);
    }
    if (!displayType || typeof displayType !== 'string') {
      throw new SiteModelError(`Entrada '${entityId}' sem displayType válido`);
    }
    if (!bookId || typeof bookId !== 'string') {
      throw new SiteModelError(`Entrada '${entityId}' sem bookId válido`);
    }
    if (searchText === undefined || typeof searchText !== 'string') {
      throw new SiteModelError(`Entrada '${entityId}' sem searchText válido`);
    }
    if (seenEntityIds.has(entityId)) {
      throw new SiteModelError(`Entidade duplicada no índice de busca: '${entityId}'`);
    }
    seenEntityIds.add(entityId);
  }

  return payload;
}

/**
 * Validates individual book envelope (books/<bookId>.json).
 */
function validateBookPayload(payload, expectedBookId, expected) {
  validateEnvelopeHeader(payload, expected);

  if (!payload.book || typeof payload.book !== 'object') {
    throw new SiteModelError('Envelope do livro ausente de objeto de metadados "book"');
  }

  const fileBookId = payload.book.bookId;
  if (fileBookId !== expectedBookId) {
    throw new SiteModelError(
      `Identidade divergente: envelope contém bookId '${fileBookId}', esperado '${expectedBookId}'`
    );
  }

  if (!Array.isArray(payload.entities)) {
    throw new SiteModelError(`Livro '${expectedBookId}' inválido: 'entities' deve ser um array`);
  }

  if (!Array.isArray(payload.relations)) {
    throw new SiteModelError(`Livro '${expectedBookId}' inválido: 'relations' deve ser um array`);
  }

  if (payload.mode === 'public') {
    if ('unresolvedReferences' in payload) {
      throw new SiteModelError(
        `Livro público '${expectedBookId}' contém 'unresolvedReferences' proibido`
      );
    }
    if ('technicalDetails' in payload) {
      throw new SiteModelError(
        `Livro público '${expectedBookId}' contém 'technicalDetails' proibido`
      );
    }
  }

  const seenIds = new Set();
  for (const ent of payload.entities) {
    if (!ent || typeof ent !== 'object') {
      throw new SiteModelError(`Entidade inválida em '${expectedBookId}'`);
    }
    const { entityId, type, displayType, name, content, provenance } = ent;
    if (!entityId || typeof entityId !== 'string') {
      throw new SiteModelError(`Entidade em '${expectedBookId}' sem entityId`);
    }
    if (!type || typeof type !== 'string') {
      throw new SiteModelError(`Entidade '${entityId}' sem type`);
    }
    if (!displayType || typeof displayType !== 'string') {
      throw new SiteModelError(`Entidade '${entityId}' sem displayType`);
    }
    if (!name || typeof name !== 'string') {
      throw new SiteModelError(`Entidade '${entityId}' sem name`);
    }
    if (!Array.isArray(content)) {
      throw new SiteModelError(`Entidade '${entityId}' sem array de content`);
    }
    if (!provenance || typeof provenance !== 'object' || !Array.isArray(provenance.pages)) {
      throw new SiteModelError(`Entidade '${entityId}' sem proveniência válida`);
    }
    if (payload.mode === 'public' && 'technicalDetails' in ent) {
      throw new SiteModelError(`Entidade pública '${entityId}' contém 'technicalDetails' proibido`);
    }
    if (seenIds.has(entityId)) {
      throw new SiteModelError(`Entidade duplicada no livro '${expectedBookId}': '${entityId}'`);
    }
    seenIds.add(entityId);
  }

  return payload;
}

/**
 * Creates an isolated client-side site store for loading and caching site-data.
 *
 * @param {string} baseUrl - Base URL pointing to site-data directory (e.g. '/site-data/' or '/api/preview/xyz/site-data/')
 * @param {Function} [fetcher=fetch] - HTTP fetcher function returning a Response-like promise
 */
export function createSiteStore(baseUrl, fetcher = fetch) {
  const normalizedBase = baseUrl.endsWith('/') ? baseUrl : `${baseUrl}/`;

  let catalog = null;
  let searchIndex = null;
  const bookCache = new Map();
  let currentExpected = null; // { mode, projectionId }

  async function fetchJson(relativeUrl) {
    const fullUrl = `${normalizedBase}${relativeUrl}`;
    let resp;
    try {
      resp = await fetcher(fullUrl);
    } catch (err) {
      throw new SiteModelError(`Erro de rede ao acessar ${fullUrl}: ${err.message}`);
    }

    if (!resp || !resp.ok) {
      const status = resp ? resp.status : 'desconhecido';
      throw new SiteModelError(`Erro HTTP ${status} ao requisitar ${fullUrl}`);
    }

    try {
      return await resp.json();
    } catch (err) {
      throw new SiteModelError(`Erro ao decodificar JSON de ${fullUrl}: ${err.message}`);
    }
  }

  return {
    async loadCatalog() {
      if (catalog) return catalog;

      const raw = await fetchJson('catalog.json');
      const validated = validateCatalogPayload(raw);

      if (currentExpected && (validated.projectionId !== currentExpected.projectionId || validated.mode !== currentExpected.mode)) {
        // Different generation detected; clear book cache
        bookCache.clear();
      }

      catalog = validated;
      currentExpected = { mode: catalog.mode, projectionId: catalog.projectionId };
      return catalog;
    },

    async loadSearchIndex() {
      if (searchIndex) return searchIndex;

      const raw = await fetchJson('search-index.json');
      const validated = validateSearchIndexPayload(raw, currentExpected);

      if (!currentExpected) {
        currentExpected = { mode: validated.mode, projectionId: validated.projectionId };
      }

      searchIndex = validated;
      return searchIndex;
    },

    async loadBook(bookId) {
      if (bookCache.has(bookId)) {
        return bookCache.get(bookId);
      }

      if (catalog) {
        const declared = catalog.books.some((b) => b.bookId === bookId);
        if (!declared) {
          throw new SiteModelError(`Livro '${bookId}' não declarado no catálogo carregado`);
        }
      }

      const raw = await fetchJson(`books/${bookId}.json`);
      const validated = validateBookPayload(raw, bookId, currentExpected);

      if (!currentExpected) {
        currentExpected = { mode: validated.mode, projectionId: validated.projectionId };
      }

      bookCache.set(bookId, validated);
      return validated;
    },

    getCatalog() {
      return catalog;
    },

    getBookMetadata(bookId) {
      if (!catalog || !Array.isArray(catalog.books)) return null;
      return catalog.books.find((b) => b.bookId === bookId) || null;
    },

    getSearchIndex() {
      return searchIndex;
    },

    getLoadedBook(bookId) {
      return bookCache.get(bookId) || null;
    },

    getLoadedBookIds() {
      return Array.from(bookCache.keys());
    },

    clear() {
      catalog = null;
      searchIndex = null;
      bookCache.clear();
      currentExpected = null;
    },
  };
}
