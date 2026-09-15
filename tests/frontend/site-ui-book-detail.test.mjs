import test from 'node:test';
import assert from 'node:assert/strict';
import { getStageStates, renderBookDetailHtml } from '../../docs/assets/site-ui.mjs';

test('getStageStates returns all 7 stages as pending for unworked book', () => {
  const stages = getStageStates('WAITING', null);
  assert.equal(stages.length, 7);
  for (const s of stages) {
    assert.equal(s.state, 'pending');
  }
});

test('getStageStates returns all 7 stages as done for READY_FOR_HUMAN_APPROVAL and DONE', () => {
  const readyStages = getStageStates('READY_FOR_HUMAN_APPROVAL', 'qa');
  assert.equal(readyStages.length, 7);
  readyStages.forEach(s => assert.equal(s.state, 'done'));

  const doneStages = getStageStates('DONE', 'qa');
  assert.equal(doneStages.length, 7);
  doneStages.forEach(s => assert.equal(s.state, 'done'));
});

test('getStageStates marks stages correctly for in-progress and blocked books', () => {
  // In-progress at editorial: Source and Extraction done, Editorial active, rest pending
  const inProgress = getStageStates('RUNNING', 'editorial');
  assert.equal(inProgress.find(s => s.stage === 'Source').state, 'done');
  assert.equal(inProgress.find(s => s.stage === 'Extraction').state, 'done');
  assert.equal(inProgress.find(s => s.stage === 'Editorial').state, 'active');
  assert.equal(inProgress.find(s => s.stage === 'Entities').state, 'pending');
  assert.equal(inProgress.find(s => s.stage === 'Relations').state, 'pending');
  assert.equal(inProgress.find(s => s.stage === 'QA').state, 'pending');

  // Blocked at relations: preceding done, Relations blocked, subsequent strictly pending
  const blocked = getStageStates('BLOCKED', 'relations');
  assert.equal(blocked.find(s => s.stage === 'Editorial').state, 'done');
  assert.equal(blocked.find(s => s.stage === 'Entities').state, 'done');
  assert.equal(blocked.find(s => s.stage === 'Relations').state, 'blocked');
  assert.equal(blocked.find(s => s.stage === 'Frontend').state, 'pending');
  assert.equal(blocked.find(s => s.stage === 'QA').state, 'pending');
});

test('renderBookDetailHtml renders unworked book with 7 pending stages and empty state', () => {
  const catalogMeta = {
    bookId: 'synthetic-empty',
    title: 'Livro Sintético Vazio',
    pipelineStatus: 'WAITING',
    rightsStatus: 'UNKNOWN',
    publicationMode: 'NOT_PUBLIC',
    currentStage: null,
  };
  const html = renderBookDetailHtml({ book: { title: 'Livro Sintético Vazio' }, catalogMeta, entities: [] });

  assert.match(html, /<div class="site-book-detail"/);
  assert.match(html, /class="pipeline-stepper"/);
  // All 7 steps must be pending
  const pendingMatches = html.match(/stepper-step pending/g) || [];
  assert.equal(pendingMatches.length, 7);
  // Empty state must be visible
  assert.match(html, /class="site-book-empty-state"/);
  assert.match(html, /Nenhuma entidade processada para este livro ainda/);
  // Dual-axis badges visible
  assert.match(html, /data-status="WAITING"/);
  assert.match(html, /data-rights="UNKNOWN"/);
});

test('renderBookDetailHtml renders processed book with all 7 done stages and entity list', () => {
  const catalogMeta = {
    bookId: 'animalidade',
    title: 'Animalidade',
    pipelineStatus: 'READY_FOR_HUMAN_APPROVAL',
    rightsStatus: 'UNKNOWN',
    publicationMode: 'NOT_PUBLIC',
    currentStage: 'qa',
  };
  const entities = [{ entityId: 'ent-1', name: 'Garras', displayType: 'Poder' }];
  const html = renderBookDetailHtml({ book: { title: 'Animalidade' }, catalogMeta, entities });

  const doneMatches = html.match(/stepper-step done/g) || [];
  assert.equal(doneMatches.length, 7);
  assert.doesNotMatch(html, /site-book-empty-state/);
  assert.match(html, /class="site-entity-list"/);
  assert.match(html, /Garras/);
});

test('renderBookDetailHtml in public mode does not render pipeline badge or stepper', () => {
  const catalogMeta = {
    bookId: 'inquisicao',
    title: 'Inquisição',
    rightsStatus: 'AUTHORIZED',
    publicationMode: 'FULL_TEXT',
  };
  const entities = [{ entityId: 'ent-1', name: 'Inquisidor', displayType: 'Classe' }];
  const html = renderBookDetailHtml({ book: { title: 'Inquisição' }, catalogMeta, entities });

  assert.match(html, /<div class="site-book-detail"/);
  assert.doesNotMatch(html, /pipeline-stepper/);
  assert.doesNotMatch(html, /site-badge-pipeline/);
  assert.match(html, /class="site-badge site-badge-rights" data-rights="AUTHORIZED"/);
  assert.match(html, /class="site-badge site-badge-pub" data-mode="FULL_TEXT"/);
  assert.match(html, /Inquisidor/);
});
