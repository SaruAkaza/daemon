/**
 * Daemon Tools — Site Route Parsing and Layout State Management (ES Module)
 * Handles client-side navigation, defensive storage reads, and responsive layout preferences.
 */

export const VALID_LAYOUTS = ['classic', 'balanced', 'advanced'];
export const DEFAULT_LAYOUT = 'balanced';
export const STORAGE_KEY_LAYOUT = 'daemonSite.layout';

/**
 * Parses URL hash into structured route descriptor.
 *
 * Recognized routes:
 *   #/ or empty -> { kind: 'home', id: null }
 *   #/books -> { kind: 'books', id: null }
 *   #/book/:bookId -> { kind: 'book', id: ':bookId' }
 *   #/entities -> { kind: 'entities', id: null }
 *   #/entity/:entityId -> { kind: 'entity', id: ':entityId' }
 *   #/search -> { kind: 'search', id: null }
 *   others -> { kind: 'not-found', id: null }
 *
 * @param {string} hash
 * @returns {{ kind: string, id: string | null }}
 */
export function parseRoute(hash) {
  const raw = String(hash ?? '').trim();
  const path = raw.startsWith('#') ? raw : `#${raw}`;

  if (path === '#' || path === '#/' || path === '') {
    return { kind: 'home', id: null };
  }
  if (path === '#/books') {
    return { kind: 'books', id: null };
  }
  if (path === '#/entities') {
    return { kind: 'entities', id: null };
  }
  if (path === '#/search') {
    return { kind: 'search', id: null };
  }

  const bookMatch = path.match(/^#\/book\/([a-z0-9-]+)$/);
  if (bookMatch) {
    return { kind: 'book', id: bookMatch[1] };
  }

  const entityMatch = path.match(/^#\/entity\/([a-z0-9-:]+)$/);
  if (entityMatch) {
    return { kind: 'entity', id: entityMatch[1] };
  }

  return { kind: 'not-found', id: null };
}

/**
 * Defensively reads saved layout preference from Web Storage.
 *
 * @param {Storage|object|null} storage
 * @returns {string}
 */
function readSavedLayout(storage) {
  if (!storage || typeof storage.getItem !== 'function') {
    return DEFAULT_LAYOUT;
  }
  try {
    const val = storage.getItem(STORAGE_KEY_LAYOUT);
    return VALID_LAYOUTS.includes(val) ? val : DEFAULT_LAYOUT;
  } catch {
    return DEFAULT_LAYOUT;
  }
}

/**
 * Creates initial application state.
 *
 * @param {Storage|object|null} [storage=null]
 * @param {string} [initialHash='#/']
 * @returns {object}
 */
export function createState(storage = null, initialHash = '#/') {
  const route = initialHash || '#/';
  const routeInfo = parseRoute(route);
  const layout = readSavedLayout(storage);

  return {
    route,
    routeInfo,
    selectedEntityId: routeInfo.kind === 'entity' ? routeInfo.id : null,
    bookId: null,
    query: '',
    type: null,
    layout,
  };
}

/**
 * Updates layout preference immutably and persists to storage if available.
 *
 * @param {object} state
 * @param {string} layout
 * @param {Storage|object|null} [storage=null]
 * @returns {object}
 */
export function setLayout(state, layout, storage = null) {
  const selected = VALID_LAYOUTS.includes(layout) ? layout : DEFAULT_LAYOUT;
  if (storage && typeof storage.setItem === 'function') {
    try {
      storage.setItem(STORAGE_KEY_LAYOUT, selected);
    } catch {
      // Storage unavailable or quota exceeded; maintain in-memory
    }
  }
  return { ...state, layout: selected };
}

/**
 * Updates route and associated route parameters without resetting other state.
 *
 * @param {object} state
 * @param {string} hash
 * @returns {object}
 */
export function setRoute(state, hash) {
  const route = hash || '#/';
  const routeInfo = parseRoute(route);
  const selectedEntityId =
    routeInfo.kind === 'entity' ? routeInfo.id : state.selectedEntityId;

  return {
    ...state,
    route,
    routeInfo,
    selectedEntityId,
  };
}

/**
 * Updates search query and filter parameters immutably.
 *
 * @param {object} state
 * @param {object} filters
 * @returns {object}
 */
export function setFilters(state, { query, bookId, type }) {
  return {
    ...state,
    ...(query !== undefined ? { query: String(query) } : {}),
    ...(bookId !== undefined ? { bookId: bookId ? String(bookId) : null } : {}),
    ...(type !== undefined ? { type: type ? String(type) : null } : {}),
  };
}
