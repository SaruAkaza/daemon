import test from 'node:test';
import assert from 'node:assert/strict';
import { zipSync, unzipSync, strFromU8, strToU8 } from 'fflate';
import { categoryForHeading, normalize, organize, validateBook, matchingSections, fileKind, digest } from '../model.mjs';
import { exportLibrary, importLibrary } from '../backup.mjs';

async function fixture() {
  const bytes = new TextEncoder().encode('%PDF-1.7 synthetic source, never a real book');
  const sha256 = await digest(bytes);
  return validateBook({ version: 1, status: 'PERSONAL_UNVERIFIED', id: sha256, title: 'Livro sintético', importedAt: '2026-10-15T00:00:00Z', pageBasis: 'PDF_PHYSICAL_INDEX',
    originals: [{ sha256, name: 'teste.pdf', kind: 'pdf', size: bytes.length, blob: new Blob([bytes]) }],
    units: [
      { page: 1, label: 'Página 1', method: 'pdf-text', confidence: null, rawText: 'Poderes\nDano: 1d6; custo lO.', blocks: [
        { rawText: 'Poderes', heading: true, level: 1, locator: 'pdf:page:1:line:1' }, { rawText: 'Dano: 1d6; custo lO.', heading: false, locator: 'pdf:page:1:line:2' }] },
      { page: 2, label: 'Página 2', method: 'blank', confidence: null, rawText: '', blocks: [] },
    ] });
}

test('keeps all blocks and blank physical pages without turning paragraphs into pages', async () => {
  const book = await fixture();
  assert.equal(book.sections.length, 2); assert.equal(book.sections[1].page, 2);
  assert.deepEqual(book.sections[0].blocks.map(b => b.text), ['Poderes', 'Dano: 1d6; custo lO.']);
  const units = [{ ...book.units[0], page: null, method: 'docx-text' }];
  assert.equal(organize(units)[0].page, null);
  assert.equal(organize(units)[0].category, 'poderes');
});

test('conservative normalization never guesses numeric costs or hard hyphens', () => {
  assert.equal(normalize('ﬁm; ﬅ; lO pontos; 1d10O; ex-\nmarido'), 'fim; st; lO pontos; 1d10O; ex-\nmarido');
});

test('explicit heading categories respect racial improvements and uncertain headings', () => {
  assert.equal(categoryForHeading('Aprimoramentos Raciais'), 'racas');
  assert.equal(categoryForHeading('APrimoramentos'), 'aprimoramentos');
  assert.equal(categoryForHeading('Uma história desconhecida de um poder'), 'outros');
  const units = [{ page: null, label: 'Word', blocks: [
    { rawText: 'Magias', heading: true, level: 1 }, { rawText: 'Luz', heading: true, level: 2 }, { rawText: 'Custo lO.', heading: false }, { rawText: 'Apêndice', heading: true, level: 1 }] }];
  assert.deepEqual(organize(units).map(s => s.category), ['magias', 'magias', 'outros']);
});

test('search ignores accent/case, searches raw mechanical content and stays in category', async () => {
  const book = await fixture();
  assert.equal(matchingSections(book, 'SINTETICO 1d6', 'poderes').length, 1);
  assert.equal(matchingSections(book, '1d6', 'criaturas').length, 0);
});

test('rejects disguised formats and fabricated page indices in restored books', async () => {
  assert.throws(() => fileKind(new TextEncoder().encode('<script>x</script>'), 'book.pdf'), /Formato/);
  const book = await fixture(); const changed = structuredClone(book); changed.units[0].page = 99;
  assert.throws(() => validateBook(changed), /inválido/);
  changed.units[0].page = null; changed.pageBasis = 'DOCX_UNVERIFIED';
  assert.throws(() => validateBook(changed), /inválido/);
});

test('backup roundtrip preserves exact original bytes, text and unknown status', async () => {
  const book = await fixture(); const archive = await exportLibrary([book]);
  const [restored] = await importLibrary(archive);
  assert.equal(restored.status, 'PERSONAL_UNVERIFIED'); assert.deepEqual(restored.units, book.units);
  assert.equal(await restored.originals[0].blob.text(), await book.originals[0].blob.text());
});

test('restore rejects corrupted source bytes, duplicate books and zip path traversal', async () => {
  const book = await fixture(); const archive = await exportLibrary([book]);
  const files = unzipSync(new Uint8Array(await archive.arrayBuffer()));
  const path = Object.keys(files).find(name => name.startsWith('originais/'));
  const corrupted = { ...files, [path]: files[path].slice() }; corrupted[path][8] ^= 1;
  await assert.rejects(() => importLibrary(new Blob([zipSync(corrupted)])), /alterado/);
  const metadata = JSON.parse(strFromU8(files['biblioteca.json'])); metadata.books.push(metadata.books[0]);
  await assert.rejects(() => importLibrary(new Blob([zipSync({ ...files, 'biblioteca.json': strToU8(JSON.stringify(metadata)) })])), /duplicados/);
  await assert.rejects(() => importLibrary(new Blob([zipSync({ '../escape': strToU8('x') })])), /inválidos/);
});
