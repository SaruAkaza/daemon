/**
 * Daemon Tools — Deterministic Entity Search and Ranking (ES Module)
 * Implements strict lexical sorting, 5-tier scoring, and authorized field filtering.
 */

/**
 * Normalizes text for search indexing and query comparison.
 * Decomposes Unicode diacritics (NFD), strips combining marks (U+0300-U+036F),
 * lowercases and trims.
 *
 * @param {*} value
 * @returns {string}
 */
export function normalizeSearch(value) {
  return String(value ?? '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .trim();
}

/**
 * Deterministic, locale-independent lexical comparator.
 *
 * @param {string} a
 * @param {string} b
 * @returns {number}
 */
function lexical(a, b) {
  const sa = String(a ?? '');
  const sb = String(b ?? '');
  return sa < sb ? -1 : sa > sb ? 1 : 0;
}

/**
 * Searches and ranks entity index entries deterministically.
 *
 * Ranking tiers:
 *   0: Exact name match
 *   1: Exact alias match
 *   2: Name prefix match
 *   3: Alias prefix match
 *   4: All query terms contained in authorized fields
 *   Infinity: No match (excluded)
 *
 * Tie-breakers: displayType, name, entityId (lexical).
 *
 * @param {Array} entries - List of authorized search index entries
 * @param {string} query - Raw search query string
 * @param {object} [filters={}] - Optional filters { bookId, type }
 * @returns {Array} - Deterministically ordered, deduplicated matching entries
 */
export function searchEntities(entries, query, { bookId = null, type = null } = {}) {
  if (!Array.isArray(entries)) {
    return [];
  }

  // 1. Filter by bookId and type
  const filtered = entries.filter((e) => {
    if (!e || typeof e !== 'object') return false;
    if (bookId && e.bookId !== bookId) return false;
    if (type && e.type !== type && e.displayType !== type) return false;
    return true;
  });

  const normQuery = normalizeSearch(query);

  // Helper tie-breaker comparator
  const tieBreaker = (a, b) =>
    lexical(a.displayType, b.displayType) ||
    lexical(a.name, b.name) ||
    lexical(a.entityId, b.entityId);

  // 2. Empty query returns all filtered entries ordered by tie-breakers
  if (!normQuery) {
    // Deduplicate by entityId just in case
    const uniqueMap = new Map();
    for (const e of filtered) {
      if (!uniqueMap.has(e.entityId)) {
        uniqueMap.set(e.entityId, e);
      }
    }
    return Array.from(uniqueMap.values()).sort(tieBreaker);
  }

  // 3. Search and score each entry
  const queryTerms = normQuery.split(/\s+/).filter(Boolean);
  const scoredMap = new Map(); // entityId -> { entry, score }

  for (const entry of filtered) {
    const normName = normalizeSearch(entry.name);
    const normAliases = Array.isArray(entry.aliases)
      ? entry.aliases.map(normalizeSearch).filter(Boolean)
      : [];

    let score = Infinity;

    // Tier 0: Exact name
    if (normName === normQuery) {
      score = 0;
    }
    // Tier 1: Exact alias
    else if (normAliases.some((a) => a === normQuery)) {
      score = 1;
    }
    // Tier 2: Name prefix
    else if (normName.startsWith(normQuery)) {
      score = 2;
    }
    // Tier 3: Alias prefix
    else if (normAliases.some((a) => a.startsWith(normQuery))) {
      score = 3;
    }
    // Tier 4: All terms match in authorized searchable text
    else {
      const normTags = Array.isArray(entry.tags)
        ? entry.tags.map(normalizeSearch).filter(Boolean)
        : [];
      const normSearchText = normalizeSearch(entry.searchText);
      const normDisplayType = normalizeSearch(entry.displayType);
      const normType = normalizeSearch(entry.type);

      const combinedText = [
        normName,
        ...normAliases,
        ...normTags,
        normSearchText,
        normDisplayType,
        normType,
      ].join(' ');

      if (queryTerms.every((term) => combinedText.includes(term))) {
        score = 4;
      }
    }

    if (score === Infinity) {
      continue;
    }

    const eid = entry.entityId;
    if (!scoredMap.has(eid) || score < scoredMap.get(eid).score) {
      scoredMap.set(eid, { entry, score });
    }
  }

  // 4. Sort results by score, then tie-breakers
  const results = Array.from(scoredMap.values());
  results.sort((a, b) => {
    if (a.score !== b.score) {
      return a.score - b.score;
    }
    return tieBreaker(a.entry, b.entry);
  });

  return results.map((r) => r.entry);
}

/**
 * Filters and sorts catalog books based on dual-axis criteria and text search.
 *
 * @param {Array} books - List of catalog book entries
 * @param {object} [options={}] - Filter and sort options
 * @returns {Array} - Filtered and sorted books
 */
export function filterBooks(
  books,
  {
    query = '',
    pipelineStatus = '',
    rightsStatus = '',
    publicationMode = '',
    categoryHint = '',
    sortBy = 'title_asc',
  } = {}
) {
  if (!Array.isArray(books)) {
    return [];
  }

  let result = [...books];

  const q = normalizeSearch(query);
  if (q) {
    result = result.filter(
      (b) =>
        normalizeSearch(b.title).includes(q) ||
        normalizeSearch(b.bookId).includes(q)
    );
  }

  if (pipelineStatus && pipelineStatus !== 'all') {
    result = result.filter((b) => b.pipelineStatus === pipelineStatus);
  }

  if (rightsStatus && rightsStatus !== 'all') {
    result = result.filter((b) => b.rightsStatus === rightsStatus);
  }

  if (publicationMode && publicationMode !== 'all') {
    result = result.filter((b) => b.publicationMode === publicationMode);
  }

  if (categoryHint && categoryHint !== 'all') {
    result = result.filter(
      (b) => Array.isArray(b.categoryHints) && b.categoryHints.includes(categoryHint)
    );
  }

  if (sortBy === 'title_asc') {
    result.sort((a, b) => String(a.title || '').localeCompare(String(b.title || '')));
  } else if (sortBy === 'title_desc') {
    result.sort((a, b) => String(b.title || '').localeCompare(String(a.title || '')));
  } else if (sortBy === 'entities_desc') {
    result.sort(
      (a, b) =>
        (b.entityCount || 0) - (a.entityCount || 0) ||
        String(a.title || '').localeCompare(String(b.title || ''))
    );
  } else if (sortBy === 'pages_desc') {
    result.sort(
      (a, b) =>
        (b.pageCount || 0) - (a.pageCount || 0) ||
        String(a.title || '').localeCompare(String(b.title || ''))
    );
  }

  return result;
}

