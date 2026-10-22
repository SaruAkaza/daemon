import { validateBook } from './model.mjs';
let database;
export function openDatabase() {
  return database ||= new Promise((resolve, reject) => {
    const request = indexedDB.open('daemon-personal-library', 1);
    request.onupgradeneeded = () => request.result.createObjectStore('books', { keyPath: 'id' });
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(new Error('Não foi possível abrir o armazenamento deste navegador. Verifique o modo privado ou as permissões.'));
    request.onblocked = () => reject(new Error('Feche outras abas da biblioteca e tente novamente.'));
  });
}
export async function listBooks() {
  const db = await openDatabase();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction('books');
    const request = transaction.objectStore('books').getAll();
    request.onsuccess = () => { try { resolve(request.result.map(validateBook)); } catch (error) { reject(error); } };
    request.onerror = () => reject(request.error);
  });
}
export async function addBooks(books) {
  const db = await openDatabase();
  books.forEach(validateBook);
  return new Promise((resolve, reject) => {
    const transaction = db.transaction('books', 'readwrite');
    for (const book of books) transaction.objectStore('books').add(book);
    transaction.oncomplete = () => resolve();
    transaction.onabort = () => reject(transaction.error?.name === 'ConstraintError' ? new Error('Este arquivo já está na biblioteca.') : new Error('Não foi possível salvar. O espaço do navegador pode estar cheio; exporte sua biblioteca antes de liberar espaço.'));
  });
}
export async function removeBook(id) {
  const db = await openDatabase();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('books', 'readwrite'); tx.objectStore('books').delete(id);
    tx.oncomplete = resolve; tx.onabort = () => reject(tx.error);
  });
}
