import { CATEGORIES, LIMITS, matchingSections, sourceLabel, validateBook } from './model.mjs';
import { listBooks, addBooks, removeBook } from './store.mjs';
import { prepareFiles, convert, sourcePreview } from './importer.mjs';
import { exportLibrary, importLibrary } from './backup.mjs';

const $ = id => document.getElementById(id);
const el = (tag, text, className) => { const node = document.createElement(tag); if (text !== undefined) node.textContent = text; if (className) node.className = className; return node; };
let books = [], category = 'all', selected = '', visible = 80, busy = false, controller, previewEpoch = 0;
const filePicker = $('files');
const key = (book, section) => `${book.id}/${section.id}`;
const download = (blob, name) => { const url = URL.createObjectURL(blob); const link = el('a'); link.href = url; link.download = name; link.click(); setTimeout(() => URL.revokeObjectURL(url), 3000); };
const friendlyError = error => error.name === 'InvalidPDFException' ? 'O PDF está inválido ou incompleto. Tente outra cópia.' : error.message || 'Não foi possível concluir. Tente novamente.';

function message(text, error = false) {
  const node = el('div', undefined, error ? 'message error' : 'message');
  const close = el('button', '×'); close.setAttribute('aria-label', 'Dispensar mensagem'); close.addEventListener('click', () => node.remove());
  node.append(close, document.createTextNode(text)); $('messages').prepend(node);
  while ($('messages').children.length > 6) $('messages').lastChild.remove();
}

function setBusy(value, cancellable = true) {
  busy = value; $('conversion').hidden = !value;
  for (const id of ['choose-files', 'backup-export', 'backup-import', 'group-images']) $(id).disabled = value;
  $('cancel').hidden = !cancellable; filePicker.disabled = value;
  for (const button of document.querySelectorAll('[data-mutates]')) button.disabled = value;
}

const selectedBooks = () => $('book-filter').value === 'all' ? books : books.filter(book => book.id === $('book-filter').value);
function results() { return selectedBooks().flatMap(book => matchingSections(book, $('search').value, category).map(section => ({ book, section }))); }

function renderCards() {
  $('book-count').textContent = books.length;
  const value = $('book-filter').value;
  $('book-filter').replaceChildren(new Option('Todos os livros', 'all'), ...books.map(book => new Option(book.title, book.id)));
  if (books.some(book => book.id === value)) $('book-filter').value = value;
  $('book-cards').replaceChildren(...books.map(book => {
    const card = el('button', undefined, book.id === $('book-filter').value ? 'book-card active' : 'book-card');
    const pages = book.pageBasis === 'DOCX_UNVERIFIED' ? 'Word' : `${book.units.length} ${book.pageBasis === 'IMAGE_FILE_ORDER' ? 'imagens' : 'páginas'}`;
    card.append(el('strong', book.title), el('span', `${pages} · ${book.sections.length} seções e trechos`));
    card.addEventListener('click', () => { $('book-filter').value = book.id; category = 'all'; selected = ''; visible = 80; render(); $('browser').scrollIntoView({ behavior: 'smooth', block: 'start' }); });
    return card;
  }));
}

function renderCategories() {
  const source = selectedBooks().flatMap(book => matchingSections(book, $('search').value));
  $('categories').replaceChildren(...Object.entries(CATEGORIES).map(([id, label]) => {
    const count = id === 'all' ? source.length : source.filter(section => section.category === id).length;
    const button = el('button', undefined); button.setAttribute('aria-pressed', String(category === id));
    button.append(document.createTextNode(label), el('span', count));
    button.addEventListener('click', () => { category = id; selected = ''; visible = 80; render(); }); return button;
  }));
}

function renderReader(result) {
  const node = $('reader'); node.replaceChildren();
  if (!result) { node.append(el('p', 'Nenhum trecho encontrado. Tente outra palavra ou categoria.')); return; }
  const { book, section } = result, unit = book.units[section.unitIndex];
  node.append(el('span', CATEGORIES[section.category], 'tag'), el('h2', section.title), el('p', book.title, 'book-label'), el('p', sourceLabel(book, unit), 'source-line'));
  const tools = el('div', undefined, 'reader-tools');
  if (book.pageBasis !== 'DOCX_UNVERIFIED') {
    const source = el('button', 'Ver página original'); source.addEventListener('click', () => showSource(book, section.unitIndex)); tools.append(source);
  }
  const original = el('button', book.originals.length > 1 ? 'Baixar esta imagem' : 'Baixar original');
  original.addEventListener('click', () => { const file = book.originals[book.pageBasis === 'IMAGE_FILE_ORDER' ? section.unitIndex : 0]; download(file.blob, file.name); }); tools.append(original);
  const backup = el('button', 'Exportar este livro'); backup.addEventListener('click', () => runBackup([book])); tools.append(backup);
  const remove = el('button', 'Remover livro'); remove.dataset.mutates = 'true'; remove.disabled = busy;
  remove.addEventListener('click', async () => {
    if (!window.confirm(`Remover “${book.title}” deste navegador? Exporte uma cópia antes se quiser guardá-lo.`)) return;
    try { await removeBook(book.id); books = await listBooks(); selected = ''; render(); } catch (error) { message(friendlyError(error), true); }
  }); tools.append(remove); node.append(tools);
  if (unit.method.startsWith('ocr')) node.append(el('p', unit.method === 'ocr-empty' ? 'O reconhecimento não encontrou texto nesta página. Consulte a imagem original.' : 'Texto reconhecido de imagem. Confira no original ao consultar números ou regras.', 'ocr-note'));
  if (!section.blocks.some(block => block.text.trim())) node.append(el('p', 'Página ou trecho sem texto reconhecido. O original foi preservado.'));
  for (const block of section.blocks) {
    if (block.heading && block.text.trim() === section.title) continue;
    node.append(el('p', block.text, 'body-text'));
  }
  const details = el('details'); details.append(el('summary', 'Sobre a conversão'));
  details.append(el('p', 'Material importado para consulta pessoal. A organização inicial segue os títulos encontrados; não certifica regras ou entidades do catálogo.'));
  details.append(el('pre', `Fonte SHA-256: ${book.id}\nPaginação: ${book.pageBasis}\nExtração: ${unit.method}${unit.confidence === null ? '' : `\nConfiança do OCR: ${Math.round(unit.confidence)}%`}\nLocalizadores:\n${section.blocks.map(block => block.locator).join('\n')}`)); node.append(details);
}

function render() {
  renderCards(); renderCategories();
  $('browser').hidden = !books.length; $('empty').hidden = !!books.length;
  const matches = results(); $('result-count').textContent = matches.length;
  if (!matches.some(result => key(result.book, result.section) === selected)) selected = matches[0] ? key(matches[0].book, matches[0].section) : '';
  $('results').replaceChildren(...matches.slice(0, visible).map(({ book, section }) => {
    const button = el('button', undefined, 'result'); button.setAttribute('aria-pressed', String(key(book, section) === selected));
    button.append(el('strong', section.title), el('span', `${book.title} · ${sourceLabel(book, book.units[section.unitIndex])}`), el('small', section.blocks.map(block => block.text).join(' ').slice(0, 160)));
    button.addEventListener('click', () => { selected = key(book, section); render(); if (innerWidth < 761) $('reader').scrollIntoView({ behavior: 'smooth' }); }); return button;
  }));
  $('more').hidden = visible >= matches.length;
  renderReader(matches.find(result => key(result.book, result.section) === selected));
}

async function showSource(book, index) {
  const epoch = ++previewEpoch; $('source-title').textContent = `${book.title} · ${sourceLabel(book, book.units[index])}`;
  $('source-message').textContent = 'Abrindo original…'; $('source-canvas').hidden = true; $('source-dialog').showModal();
  try {
    const canvas = document.createElement('canvas'); await sourcePreview(book, index, canvas);
    if (epoch !== previewEpoch) return;
    const target = $('source-canvas'); target.width = canvas.width; target.height = canvas.height; target.getContext('2d').drawImage(canvas, 0, 0);
    target.hidden = false; $('source-message').textContent = ''; canvas.width = canvas.height = 1;
  } catch (error) { if (epoch === previewEpoch) $('source-message').textContent = friendlyError(error); }
}
$('source-close').addEventListener('click', () => $('source-dialog').close());
$('source-dialog').addEventListener('close', () => { previewEpoch++; $('source-canvas').width = $('source-canvas').height = 1; });

async function importFiles(files) {
  if (busy || !files.length) return;
  if (files.length > LIMITS.pages) { message('Selecione até 1.500 arquivos por vez.', true); return; }
  const tasks = [], images = [];
  for (const file of files) {
    if ($('group-images').checked && /\.(png|jpe?g|webp|gif|bmp)$/i.test(file.name)) images.push(file); else tasks.push([file]);
  }
  if (images.length) tasks.push(images.sort((a, b) => a.name.localeCompare(b.name, 'pt-BR', { numeric: true })));
  controller = new AbortController(); setBusy(true); let imported = 0;
  try {
    for (const [index, task] of tasks.entries()) {
      if (controller.signal.aborted) break;
      const title = task.length > 1 ? `${task.length} imagens` : task[0].name;
      $('conversion-title').textContent = `${index + 1} de ${tasks.length} · ${title}`;
      $('conversion-message').textContent = 'Conferindo o arquivo…'; $('conversion-progress').value = 0;
      try {
        const originals = await prepareFiles(task);
        const book = await convert(originals, { signal: controller.signal,
          exists: id => books.some(book => book.id === id), progress: (text, fraction) => { $('conversion-message').textContent = text; $('conversion-progress').value = fraction; } });
        if (book.duplicate) { message(`${title} já está na sua biblioteca.`); continue; }
        validateBook(book); await addBooks([book]); books = await listBooks(); imported++;
        $('book-filter').value = 'all'; selected = ''; render();
        $('book-filter').value = book.id; category = 'all'; render();
      } catch (error) {
        if (error.name === 'AbortError') { message('Importação cancelada. Os livros que já foram salvos continuam disponíveis.'); break; }
        message(`${title}: ${friendlyError(error)}`, true);
      }
    }
    if (imported) message(`${imported === 1 ? 'Livro importado' : `${imported} livros importados`}. O conteúdo já está disponível para busca e leitura.`);
  } finally { controller = null; setBusy(false); filePicker.value = ''; render(); }
}

async function runBackup(selection = books) {
  if (busy) return; setBusy(true, false); $('conversion-title').textContent = 'Preparando sua cópia';
  $('conversion-message').textContent = 'Incluindo o texto convertido e os arquivos originais…'; $('conversion-progress').removeAttribute('value');
  try { await new Promise(resolve => setTimeout(resolve, 30)); download(await exportLibrary(selection), 'daemon-biblioteca.zip'); message('Cópia preparada. Guarde o ZIP para restaurar seus livros depois.'); }
  catch (error) { message(friendlyError(error), true); } finally { setBusy(false); }
}

$('choose-files').addEventListener('click', () => filePicker.click());
filePicker.addEventListener('change', () => importFiles([...filePicker.files]));
$('cancel').addEventListener('click', () => { controller?.abort(); $('conversion-message').textContent = 'Cancelando…'; });
for (const event of ['dragenter', 'dragover']) $('dropzone').addEventListener(event, e => { e.preventDefault(); $('dropzone').classList.add('drag'); });
for (const event of ['dragleave', 'drop']) $('dropzone').addEventListener(event, e => { e.preventDefault(); $('dropzone').classList.remove('drag'); });
$('dropzone').addEventListener('drop', event => { if (busy) message('Aguarde a importação atual terminar antes de adicionar outros arquivos.'); else importFiles([...event.dataTransfer.files]); });
let searchTimer;
$('search').addEventListener('input', () => { clearTimeout(searchTimer); searchTimer = setTimeout(() => { selected = ''; visible = 80; render(); }, 160); });
$('book-filter').addEventListener('change', () => { category = 'all'; selected = ''; visible = 80; render(); });
$('more').addEventListener('click', () => { visible += 80; render(); });
$('backup-export').addEventListener('click', () => runBackup());
$('backup-import').addEventListener('click', () => $('backup-file').click());
$('backup-file').addEventListener('change', async event => {
  const file = event.target.files[0]; if (!file || busy) return;
  setBusy(true, false); $('conversion-title').textContent = 'Restaurando sua biblioteca'; $('conversion-message').textContent = 'Conferindo os arquivos da cópia…'; $('conversion-progress').removeAttribute('value');
  try {
    const restored = await importLibrary(file), existing = new Set(books.map(book => book.id));
    const fresh = restored.filter(book => !existing.has(book.id));
    if (fresh.length) await addBooks(fresh);
    books = await listBooks(); selected = ''; render(); message(`${fresh.length} livro(s) restaurado(s). Os livros que já estavam aqui foram preservados.`);
  } catch (error) { message(friendlyError(error), true); }
  finally { setBusy(false); event.target.value = ''; }
});
window.addEventListener('beforeunload', event => { if (busy) { event.preventDefault(); event.returnValue = ''; } });

try {
  books = await listBooks(); render();
  // Optional private deployment configuration. No book is bundled in the public source.
  const response = await fetch('library-config.json', { cache: 'no-store' });
  if (response.ok) {
    const config = await response.json();
    if (config.starter?.path && config.starter?.name) {
      const url = new URL(config.starter.path, document.baseURI);
      if (url.origin === location.origin && !url.username && !url.password) {
        const button = el('button', `Importar ${config.starter.name.replace(/\.[^.]+$/, '')} do projeto`); button.dataset.mutates = 'true';
        button.addEventListener('click', async () => {
          if (busy) return; button.disabled = true;
          try { const response = await fetch(url); if (!response.ok) throw new Error('Não foi possível abrir o livro do projeto.'); const blob = await response.blob(); await importFiles([new File([blob], config.starter.name)]); }
          catch (error) { message(friendlyError(error), true); } finally { button.disabled = false; }
        }); $('dropzone').append(button);
      }
    }
  }
} catch (error) { message(friendlyError(error), true); }
