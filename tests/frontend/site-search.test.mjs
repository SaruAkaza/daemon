import test from 'node:test';
import assert from 'node:assert/strict';
import { normalizeSearch, searchEntities, filterBooks } from '../../docs/assets/site-search.mjs';

test('normalizeSearch strips accents, lowercases and trims', () => {
  assert.equal(normalizeSearch('  Árvore de Ébano!  '), 'arvore de ebano!');
  assert.equal(normalizeSearch(null), '');
  assert.equal(normalizeSearch(undefined), '');
  assert.equal(normalizeSearch('   '), '');
});

test('exact name precedes exact alias', () => {
  const a = {
    entityId: 'a',
    name: 'Lobo',
    aliases: [],
    displayType: 'Criatura',
    type: 'creature_npc',
    bookId: 's',
    tags: [],
    searchText: 'lobo',
  };
  const b = {
    ...a,
    entityId: 'b',
    name: 'Outro',
    aliases: ['Lobo'],
  };
  const result = searchEntities([b, a], 'lobo');
  assert.deepEqual(result.map((x) => x.entityId), ['a', 'b']);
});

test('ranking levels from 0 to 4: exact name, exact alias, name prefix, alias prefix, terms match', () => {
  const e0 = {
    entityId: 'e0',
    name: 'Fogo',
    aliases: [],
    displayType: 'Poder',
    type: 'character_option',
    bookId: 'b1',
    tags: [],
    searchText: 'fogo',
  };
  const e1 = {
    entityId: 'e1',
    name: 'Labareda',
    aliases: ['Fogo'],
    displayType: 'Poder',
    type: 'character_option',
    bookId: 'b1',
    tags: [],
    searchText: 'labareda fogo',
  };
  const e2 = {
    entityId: 'e2',
    name: 'Fogoso',
    aliases: [],
    displayType: 'Item',
    type: 'item',
    bookId: 'b1',
    tags: [],
    searchText: 'fogoso',
  };
  const e3 = {
    entityId: 'e3',
    name: 'Magia',
    aliases: ['Fogosa'],
    displayType: 'Poder',
    type: 'character_option',
    bookId: 'b1',
    tags: [],
    searchText: 'magia fogosa',
  };
  const e4 = {
    entityId: 'e4',
    name: 'Inferno',
    aliases: ['Brasa'],
    displayType: 'Poder',
    type: 'character_option',
    bookId: 'b1',
    tags: ['fogo'],
    searchText: 'inferno brasa fogo ardente',
  };

  const results = searchEntities([e4, e3, e2, e1, e0], 'fogo');
  assert.deepEqual(results.map((x) => x.entityId), ['e0', 'e1', 'e2', 'e3', 'e4']);
});

test('tie-breaking: displayType, then name, then entityId', () => {
  const e1 = {
    entityId: 'id-1',
    name: 'Alfa',
    aliases: [],
    displayType: 'B',
    type: 'creature_npc',
    bookId: 'b1',
    tags: [],
    searchText: 'alfa',
  };
  const e2 = {
    entityId: 'id-2',
    name: 'Alfa',
    aliases: [],
    displayType: 'A',
    type: 'creature_npc',
    bookId: 'b1',
    tags: [],
    searchText: 'alfa',
  };
  const e3 = {
    entityId: 'id-3',
    name: 'Beta',
    aliases: [],
    displayType: 'A',
    type: 'creature_npc',
    bookId: 'b1',
    tags: [],
    searchText: 'beta alfa',
  };

  const res1 = searchEntities([e1, e2], 'alfa');
  assert.deepEqual(res1.map((x) => x.entityId), ['id-2', 'id-1']);

  const e4a = { ...e2, entityId: 'id-a', name: 'Gama' };
  const e4b = { ...e2, entityId: 'id-b', name: 'Gama' };
  const res2 = searchEntities([e4b, e4a], 'gama');
  assert.deepEqual(res2.map((x) => x.entityId), ['id-a', 'id-b']);
});

test('filters by bookId and type independently and combined', () => {
  const entries = [
    { entityId: '1', name: 'Lobo', displayType: 'C', type: 'creature_npc', bookId: 'b1', aliases: [], tags: [], searchText: 'lobo' },
    { entityId: '2', name: 'Lobo Cinzento', displayType: 'C', type: 'creature_npc', bookId: 'b2', aliases: [], tags: [], searchText: 'lobo cinzento' },
    { entityId: '3', name: 'Lobo Espiritual', displayType: 'P', type: 'character_option', bookId: 'b1', aliases: [], tags: [], searchText: 'lobo espiritual' },
  ];

  const resBook = searchEntities(entries, 'lobo', { bookId: 'b1' });
  assert.deepEqual(resBook.map((x) => x.entityId), ['1', '3']);

  const resType = searchEntities(entries, 'lobo', { type: 'character_option' });
  assert.deepEqual(resType.map((x) => x.entityId), ['3']);

  const resBoth = searchEntities(entries, 'lobo', { bookId: 'b2', type: 'creature_npc' });
  assert.deepEqual(resBoth.map((x) => x.entityId), ['2']);
});

test('empty query returns all filtered entries ordered by tie-breakers', () => {
  const entries = [
    { entityId: 'b', name: 'Zebra', displayType: 'A', type: 'creature_npc', bookId: 'b1', aliases: [], tags: [], searchText: '' },
    { entityId: 'a', name: 'Antílope', displayType: 'A', type: 'creature_npc', bookId: 'b1', aliases: [], tags: [], searchText: '' },
  ];
  const res = searchEntities(entries, '');
  assert.deepEqual(res.map((x) => x.entityId), ['a', 'b']);
});

test('zero results when query does not match', () => {
  const entries = [
    { entityId: '1', name: 'Lobo', displayType: 'C', type: 'creature_npc', bookId: 'b1', aliases: [], tags: [], searchText: 'lobo' },
  ];
  const res = searchEntities(entries, 'dragão');
  assert.deepEqual(res, []);
});

test('input permutation invariance', () => {
  const e1 = { entityId: '1', name: 'Lobo Alfa', displayType: 'C', type: 'creature_npc', bookId: 'b1', aliases: [], tags: [], searchText: 'lobo alfa' };
  const e2 = { entityId: '2', name: 'Lobo', displayType: 'C', type: 'creature_npc', bookId: 'b1', aliases: [], tags: [], searchText: 'lobo' };
  const e3 = { entityId: '3', name: 'Raposa', displayType: 'C', type: 'creature_npc', bookId: 'b1', aliases: ['Lobo Pequeno'], tags: [], searchText: 'raposa lobo pequeno' };

  const r1 = searchEntities([e1, e2, e3], 'lobo');
  const r2 = searchEntities([e3, e2, e1], 'lobo');
  const r3 = searchEntities([e2, e1, e3], 'lobo');

  assert.deepEqual(r1, r2);
  assert.deepEqual(r2, r3);
});

test('filterBooks filters by rightsStatus and pipelineStatus independently and combined', () => {
  const books = [
    { bookId: 'b1', title: 'Trevas', pipelineStatus: 'DONE', rightsStatus: 'UNKNOWN', publicationMode: 'NOT_PUBLIC', entityCount: 10, pageCount: 50 },
    { bookId: 'b2', title: 'Arkanun', pipelineStatus: 'WAITING', rightsStatus: 'AUTHORIZED', publicationMode: 'FULL_TEXT', entityCount: 0, pageCount: 20 },
    { bookId: 'b3', title: 'Invasao', pipelineStatus: 'WAITING', rightsStatus: 'UNKNOWN', publicationMode: 'NOT_PUBLIC', entityCount: 0, pageCount: 100 },
  ];

  // Filter by pipelineStatus
  assert.equal(filterBooks(books, { pipelineStatus: 'WAITING' }).length, 2);

  // Filter by rightsStatus
  assert.equal(filterBooks(books, { rightsStatus: 'AUTHORIZED' }).length, 1);
  assert.equal(filterBooks(books, { rightsStatus: 'AUTHORIZED' })[0].bookId, 'b2');

  // Combined filter
  assert.equal(filterBooks(books, { pipelineStatus: 'WAITING', rightsStatus: 'UNKNOWN' }).length, 1);
  assert.equal(filterBooks(books, { pipelineStatus: 'WAITING', rightsStatus: 'UNKNOWN' })[0].bookId, 'b3');
});

test('filterBooks sorting options', () => {
  const books = [
    { bookId: 'b1', title: 'Trevas', entityCount: 10, pageCount: 50 },
    { bookId: 'b2', title: 'Arkanun', entityCount: 5, pageCount: 200 },
    { bookId: 'b3', title: 'Invasao', entityCount: 20, pageCount: 10 },
  ];

  const byTitleAsc = filterBooks(books, { sortBy: 'title_asc' });
  assert.deepEqual(byTitleAsc.map(b => b.bookId), ['b2', 'b3', 'b1']);

  const byTitleDesc = filterBooks(books, { sortBy: 'title_desc' });
  assert.deepEqual(byTitleDesc.map(b => b.bookId), ['b1', 'b3', 'b2']);

  const byEntitiesDesc = filterBooks(books, { sortBy: 'entities_desc' });
  assert.deepEqual(byEntitiesDesc.map(b => b.bookId), ['b3', 'b1', 'b2']);

  const byPagesDesc = filterBooks(books, { sortBy: 'pages_desc' });
  assert.deepEqual(byPagesDesc.map(b => b.bookId), ['b2', 'b1', 'b3']);
});

