import { zipSync, unzipSync, strToU8, strFromU8 } from 'fflate';
import { LIMITS, digest, fileKind, validateBook } from './model.mjs';

const originalPath = original => `originais/${original.sha256}.${original.kind}`;

export async function exportLibrary(books) {
  if (!books.length) throw new Error('Adicione um livro antes de exportar.');
  const files = {}; let total = 0;
  const metadata = books.map(book => ({ ...book, sections: undefined, originals: book.originals.map(({ blob, ...original }) => original) }));
  const json = strToU8(JSON.stringify({ format: 'daemon-personal-library', version: 1, books: metadata }));
  total += json.length; files['biblioteca.json'] = json;
  for (const book of books) {
    for (const original of book.originals) {
      const path = originalPath(original); if (files[path]) continue;
      total += original.size;
      if (total > LIMITS.backupBytes) throw new Error('A biblioteca ultrapassa 128 MB para esta cópia. Exporte livros individualmente pela tela de leitura.');
      files[path] = new Uint8Array(await original.blob.arrayBuffer());
    }
  }
  if (total > LIMITS.backupBytes) throw new Error('A cópia ultrapassa o limite de 128 MB.');
  return new Blob([zipSync(files, { level: 0 })], { type: 'application/zip' });
}

export async function importLibrary(file) {
  if (file.size > LIMITS.backupBytes + 1024 * 1024) throw new Error('A cópia ultrapassa o limite de 128 MB.');
  let total = 0; const names = new Set();
  const files = unzipSync(new Uint8Array(await file.arrayBuffer()), { filter: entry => {
    if (names.has(entry.name)) throw new Error('A cópia contém arquivos duplicados.'); names.add(entry.name);
    total += entry.originalSize;
    if (total > LIMITS.backupBytes || names.size > 3000 || entry.name.includes('..') || entry.name.startsWith('/') || entry.name.includes('\\')) throw new Error('A cópia contém arquivos inválidos ou excede o limite.');
    if (entry.name === 'biblioteca.json' && entry.originalSize > 32 * 1024 * 1024) throw new Error('Os dados de texto excedem o limite da cópia.');
    return true;
  } });
  if (!files['biblioteca.json']) throw new Error('Escolha uma cópia ZIP exportada pela biblioteca Daemon.');
  const data = JSON.parse(strFromU8(files['biblioteca.json']));
  if (data.format !== 'daemon-personal-library' || data.version !== 1 || !Array.isArray(data.books) || !data.books.length || data.books.length > 100) throw new Error('Formato da cópia da biblioteca inválido.');
  const ids = new Set(), books = [], verified = new Map();
  for (const raw of data.books) {
    const book = validateBook(raw);
    if (ids.has(book.id)) throw new Error('A cópia contém livros duplicados.'); ids.add(book.id);
    for (const original of book.originals) {
      const path = originalPath(original); const bytes = files[path];
      if (!bytes || bytes.length !== original.size) throw new Error('Um original está ausente ou foi alterado na cópia.');
      if (!verified.has(path)) {
        const name = `original.${original.kind === 'jpeg' ? 'jpg' : original.kind}`;
        if (await digest(bytes) !== original.sha256 || fileKind(bytes, name) !== original.kind) throw new Error('Um original está ausente ou foi alterado na cópia.');
        verified.set(path, new Blob([bytes]));
      }
      original.blob = verified.get(path);
    }
    const expectedId = book.originals.length === 1 ? book.originals[0].sha256 : await digest(new TextEncoder().encode(JSON.stringify(book.originals.map(o => ({ sha256: o.sha256, name: o.name })))));
    if (expectedId !== book.id) throw new Error('A identificação da fonte não corresponde aos arquivos originais.');
    books.push(book);
  }
  return books;
}
