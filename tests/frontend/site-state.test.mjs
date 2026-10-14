import test from 'node:test';
import assert from 'node:assert/strict';
import { parseRoute, createState, setLayout, setRoute, setFilters, setBookFilters } from '../../docs/assets/site-state.mjs';

function createMockStorage(initial = {}) {
  const store = { ...initial };
  return {
    getItem(key) {
      return Object.prototype.hasOwnProperty.call(store, key) ? store[key] : null;
    },
    setItem(key, value) {
      store[key] = String(value);
    },
    removeItem(key) {
      delete store[key];
    },
  };
}

test('parseRoute handles the six standard routes and invalid fallback', () => {
  assert.deepEqual(parseRoute(''), { kind: 'home', id: null });
  assert.deepEqual(parseRoute('#'), { kind: 'home', id: null });
  assert.deepEqual(parseRoute('#/'), { kind: 'home', id: null });
  assert.deepEqual(parseRoute('#/books'), { kind: 'books', id: null });
  assert.deepEqual(parseRoute('#/book/livro-a'), { kind: 'book', id: 'livro-a' });
  assert.deepEqual(parseRoute('#/entities'), { kind: 'entities', id: null });
  assert.deepEqual(parseRoute('#/entity/ent-123'), { kind: 'entity', id: 'ent-123' });
  assert.deepEqual(parseRoute('#/search'), { kind: 'search', id: null });
  assert.deepEqual(parseRoute('#/invalid/path/here'), { kind: 'not-found', id: null });
  assert.deepEqual(parseRoute('#/book/'), { kind: 'not-found', id: null });
  assert.deepEqual(parseRoute('#/entity/'), { kind: 'not-found', id: null });
});

test('parseRoute handles ops routes in restricted_preview and falls back in public mode', () => {
  const restrictedOpts = { mode: 'restricted_preview' };
  assert.deepEqual(parseRoute('#/ops', restrictedOpts), { kind: 'ops', id: null });
  assert.deepEqual(parseRoute('#/ops/queue', restrictedOpts), { kind: 'ops-queue', id: null });
  assert.deepEqual(parseRoute('#/ops/reviews', restrictedOpts), { kind: 'ops-reviews', id: null });
  assert.deepEqual(parseRoute('#/ops/review/REV-123', restrictedOpts), { kind: 'ops-review', id: 'REV-123' });

  const publicOpts = { mode: 'public' };
  assert.deepEqual(parseRoute('#/ops', publicOpts), { kind: 'home', id: null });
  assert.deepEqual(parseRoute('#/ops/queue', publicOpts), { kind: 'home', id: null });
  assert.deepEqual(parseRoute('#/ops/reviews', publicOpts), { kind: 'home', id: null });
  assert.deepEqual(parseRoute('#/ops/review/REV-123', publicOpts), { kind: 'home', id: null });
});

test('createState initializes from storage and route', () => {
  const storage = createMockStorage({ 'daemonSite.layout': 'advanced' });
  const state = createState(storage, '#/entity/lobo-1');

  assert.equal(state.layout, 'advanced');
  assert.equal(state.route, '#/entity/lobo-1');
  assert.equal(state.selectedEntityId, 'lobo-1');
  assert.equal(state.query, '');
  assert.equal(state.bookId, null);
  assert.equal(state.type, null);
});

test('createState falls back to balanced on invalid or missing stored layout', () => {
  const storage = createMockStorage({ 'daemonSite.layout': 'invalid_mode' });
  const state = createState(storage, '#/');
  assert.equal(state.layout, 'balanced');

  const emptyState = createState(null, '#/');
  assert.equal(emptyState.layout, 'balanced');
});

test('createState works when storage throws errors', () => {
  const throwingStorage = {
    getItem() {
      throw new Error('Access denied');
    },
    setItem() {
      throw new Error('Access denied');
    },
  };
  const state = createState(throwingStorage, '#/');
  assert.equal(state.layout, 'balanced');
});

test('setLayout updates state and storage while preserving selection, filters and route', () => {
  const storage = createMockStorage();
  const state = {
    route: '#/entity/a',
    routeInfo: { kind: 'entity', id: 'a' },
    selectedEntityId: 'a',
    bookId: 's',
    query: 'lobo',
    type: 'creature_npc',
    layout: 'balanced',
  };

  const next = setLayout(state, 'classic', storage);
  assert.equal(next.layout, 'classic');
  assert.equal(storage.getItem('daemonSite.layout'), 'classic');
  // All other fields strictly preserved
  assert.deepEqual({ ...next, layout: state.layout }, state);

  // Invalid layout falls back to balanced
  const fallback = setLayout(state, 'nonexistent', storage);
  assert.equal(fallback.layout, 'balanced');
  assert.equal(storage.getItem('daemonSite.layout'), 'balanced');
});

test('setRoute updates route and selectedEntityId without resetting filters or layout', () => {
  const state = {
    route: '#/entities',
    routeInfo: { kind: 'entities', id: null },
    selectedEntityId: null,
    bookId: 'b1',
    query: 'faro',
    type: 'character_option',
    layout: 'advanced',
  };

  const next = setRoute(state, '#/entity/poder-faro');
  assert.equal(next.route, '#/entity/poder-faro');
  assert.equal(next.selectedEntityId, 'poder-faro');
  assert.equal(next.query, 'faro');
  assert.equal(next.bookId, 'b1');
  assert.equal(next.type, 'character_option');
  assert.equal(next.layout, 'advanced');
});

test('setFilters updates query, bookId, and type preserving route and layout', () => {
  const state = {
    route: '#/entity/a',
    routeInfo: { kind: 'entity', id: 'a' },
    selectedEntityId: 'a',
    bookId: null,
    query: '',
    type: null,
    layout: 'classic',
  };

  const next = setFilters(state, { query: 'garras', bookId: 'b1', type: 'creature_npc' });
  assert.equal(next.query, 'garras');
  assert.equal(next.bookId, 'b1');
  assert.equal(next.type, 'creature_npc');
  assert.equal(next.selectedEntityId, 'a');
  assert.equal(next.route, '#/entity/a');
  assert.equal(next.layout, 'classic');
});

test('createState initializes bookFilters with dual-axis defaults', () => {
  const state = createState();
  assert.deepEqual(state.bookFilters, {
    query: '',
    pipelineStatus: 'all',
    rightsStatus: 'all',
    publicationMode: 'all',
    sortBy: 'title_asc',
  });
});

test('setBookFilters updates bookFilters immutably', () => {
  const state = createState();
  const next = setBookFilters(state, { pipelineStatus: 'RUNNING', rightsStatus: 'UNKNOWN' });
  assert.notEqual(state, next);
  assert.equal(next.bookFilters.pipelineStatus, 'RUNNING');
  assert.equal(next.bookFilters.rightsStatus, 'UNKNOWN');
  assert.equal(next.bookFilters.sortBy, 'title_asc');
  assert.equal(state.bookFilters.pipelineStatus, 'all');
});

