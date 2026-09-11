import test from 'node:test';
import assert from 'node:assert/strict';
import { createSiteStore } from '../../docs/assets/site-model.mjs';

function mockFetcher(responses) {
  const fetchCounts = {};
  const fetcher = async (url) => {
    fetchCounts[url] = (fetchCounts[url] || 0) + 1;
    const resp = responses[url];
    if (!resp) {
      return {
        ok: false,
        status: 404,
        statusText: 'Not Found',
        json: async () => ({ error: 'Not found' }),
      };
    }
    if (resp.throws) {
      throw new Error(resp.throws);
    }
    return {
      ok: resp.ok !== false,
      status: resp.status || 200,
      json: async () => resp.data,
    };
  };
  fetcher.getCounts = () => fetchCounts;
  return fetcher;
}

const validCatalog = {
  siteViewModelVersion: '1',
  mode: 'restricted_preview',
  projectionId: 'proj-001',
  books: [
    {
      bookId: 'book-a',
      title: 'Book A',
      publicationMode: 'NOT_PUBLIC',
      path: 'books/book-a.json',
      groups: [],
    },
  ],
};

const validSearchIndex = {
  siteViewModelVersion: '1',
  mode: 'restricted_preview',
  projectionId: 'proj-001',
  entries: [
    {
      entityId: 'ent-1',
      route: '#/entity/ent-1',
      name: 'Entidade 1',
      aliases: [],
      type: 'creature_npc',
      displayType: 'Criatura / NPC',
      bookId: 'book-a',
      bookTitle: 'Book A',
      tags: [],
      searchText: 'entidade 1',
    },
  ],
};

const validBookA = {
  siteViewModelVersion: '1',
  mode: 'restricted_preview',
  projectionId: 'proj-001',
  book: {
    bookId: 'book-a',
    title: 'Book A',
    publicationMode: 'NOT_PUBLIC',
  },
  groups: [],
  entities: [
    {
      entityId: 'ent-1',
      type: 'creature_npc',
      displayType: 'Criatura / NPC',
      name: 'Entidade 1',
      aliases: [],
      tags: [],
      content: [{ title: 'Desc', paragraphs: ['Parágrafo 1'] }],
      provenance: { source: 'book-a', pages: [1] },
    },
  ],
  relations: [],
};

test('rejects incompatible contract version', async () => {
  const store = createSiteStore('/site-data/', async () => ({
    ok: true,
    json: async () => ({ siteViewModelVersion: '999' }),
  }));
  await assert.rejects(store.loadCatalog(), /versão/i);
});

test('rejects network error on catalog load', async () => {
  const fetcher = mockFetcher({
    '/site-data/catalog.json': { ok: false, status: 500 },
  });
  const store = createSiteStore('/site-data/', fetcher);
  await assert.rejects(store.loadCatalog(), /erro/i);
});

test('loads and validates catalog and search index envelopes', async () => {
  const fetcher = mockFetcher({
    '/site-data/catalog.json': { data: validCatalog },
    '/site-data/search-index.json': { data: validSearchIndex },
  });
  const store = createSiteStore('/site-data/', fetcher);

  const cat = await store.loadCatalog();
  assert.equal(cat.projectionId, 'proj-001');
  assert.equal(cat.books.length, 1);

  const idx = await store.loadSearchIndex();
  assert.equal(idx.projectionId, 'proj-001');
  assert.equal(idx.entries.length, 1);
});

test('rejects mixed generation / divergent projectionId in search index', async () => {
  const fetcher = mockFetcher({
    '/site-data/catalog.json': { data: validCatalog },
    '/site-data/search-index.json': {
      data: { ...validSearchIndex, projectionId: 'proj-divergent' },
    },
  });
  const store = createSiteStore('/site-data/', fetcher);
  await store.loadCatalog();
  await assert.rejects(store.loadSearchIndex(), /projeção inconsistente|divergente/i);
});

test('rejects loading undeclared book', async () => {
  const fetcher = mockFetcher({
    '/site-data/catalog.json': { data: validCatalog },
  });
  const store = createSiteStore('/site-data/', fetcher);
  await store.loadCatalog();
  await assert.rejects(store.loadBook('unknown-book'), /não encontrado|não declarado/i);
});

test('rejects divergent book identity in book envelope', async () => {
  const corruptedBook = {
    ...validBookA,
    book: { ...validBookA.book, bookId: 'different-id' },
  };
  const fetcher = mockFetcher({
    '/site-data/catalog.json': { data: validCatalog },
    '/site-data/books/book-a.json': { data: corruptedBook },
  });
  const store = createSiteStore('/site-data/', fetcher);
  await store.loadCatalog();
  await assert.rejects(store.loadBook('book-a'), /identidade|mismatched/i);
});

test('caches loaded books without redundant fetches', async () => {
  const fetcher = mockFetcher({
    '/site-data/catalog.json': { data: validCatalog },
    '/site-data/books/book-a.json': { data: validBookA },
  });
  const store = createSiteStore('/site-data/', fetcher);

  await store.loadCatalog();
  const b1 = await store.loadBook('book-a');
  const b2 = await store.loadBook('book-a');

  assert.equal(b1, b2);
  assert.equal(fetcher.getCounts()['/site-data/books/book-a.json'], 1);
});

test('does not fetch any books when loading catalog and search index', async () => {
  const fetcher = mockFetcher({
    '/site-data/catalog.json': { data: validCatalog },
    '/site-data/search-index.json': { data: validSearchIndex },
  });
  const store = createSiteStore('/site-data/', fetcher);

  await store.loadCatalog();
  await store.loadSearchIndex();

  const counts = fetcher.getCounts();
  assert.equal(counts['/site-data/catalog.json'], 1);
  assert.equal(counts['/site-data/search-index.json'], 1);
  assert.equal(counts['/site-data/books/book-a.json'], undefined);
});

test('clear() resets store and cached books', async () => {
  const fetcher = mockFetcher({
    '/site-data/catalog.json': { data: validCatalog },
    '/site-data/books/book-a.json': { data: validBookA },
  });
  const store = createSiteStore('/site-data/', fetcher);

  await store.loadCatalog();
  await store.loadBook('book-a');
  assert.equal(fetcher.getCounts()['/site-data/books/book-a.json'], 1);

  store.clear();
  assert.equal(store.getCatalog(), null);
  assert.equal(store.getLoadedBook('book-a'), null);

  await store.loadCatalog();
  await store.loadBook('book-a');
  assert.equal(fetcher.getCounts()['/site-data/books/book-a.json'], 2);
});
