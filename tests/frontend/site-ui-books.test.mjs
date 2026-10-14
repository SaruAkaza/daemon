import test from 'node:test';
import assert from 'node:assert/strict';
import { createBookCard, escapeHtml } from '../../docs/assets/site-ui.mjs';

test('escapeHtml sanitizes special characters against markup injection', () => {
  const raw = '<script>alert("xss")</script> & \'Trevas\'';
  const escaped = escapeHtml(raw);
  assert.equal(escaped, '&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt; &amp; &#39;Trevas&#39;');
});

test('createBookCard renders .site-book-card with dual-axis badges and safe escaping', () => {
  const book = {
    bookId: 'animalidade',
    title: '<Animalidade & Feras>',
    pipelineStatus: 'RUNNING',
    rightsStatus: 'UNKNOWN',
    publicationMode: 'NOT_PUBLIC',
    currentStage: 'relations',
    entityCount: 56,
    pageCount: 13,
  };

  const cardHtml = createBookCard(book);
  // Must render .site-book-card container
  assert.match(cardHtml, /<div class="site-book-card"/);
  assert.match(cardHtml, /data-book-id="animalidade"/);
  // Must render correct link
  assert.match(cardHtml, /href="#\/book\/animalidade"/);
  // Must escape special characters in title
  assert.match(cardHtml, /&lt;Animalidade &amp; Feras&gt;/);
  assert.doesNotMatch(cardHtml, /<Animalidade/);
  // Badges
  assert.match(cardHtml, /class="site-badge site-badge-pipeline" data-status="RUNNING"/);
  assert.match(cardHtml, /class="site-badge site-badge-rights" data-rights="UNKNOWN"/);
  assert.match(cardHtml, /class="site-badge site-badge-pub" data-mode="NOT_PUBLIC"/);
  assert.match(cardHtml, /56 entidades/);
});

test('createBookCard in public mode does not render pipeline badge or stage text', () => {
  const publicBook = {
    bookId: 'inquisicao',
    title: 'Inquisição',
    rightsStatus: 'AUTHORIZED',
    publicationMode: 'FULL_TEXT',
    entityCount: 12,
    pageCount: 50,
  };

  const cardHtml = createBookCard(publicBook);
  assert.match(cardHtml, /<div class="site-book-card"/);
  assert.doesNotMatch(cardHtml, /site-badge-pipeline/);
  assert.doesNotMatch(cardHtml, /Estágio:/);
  assert.doesNotMatch(cardHtml, /Não iniciado/);
  assert.match(cardHtml, /class="site-badge site-badge-rights" data-rights="AUTHORIZED"/);
  assert.match(cardHtml, /class="site-badge site-badge-pub" data-mode="FULL_TEXT"/);
});
