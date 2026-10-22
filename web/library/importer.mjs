import * as pdfjs from 'pdfjs-dist/build/pdf.mjs';
import { createWorker } from 'tesseract.js';
import { unzipSync, strFromU8 } from 'fflate';
import { LIMITS, digest, fileKind, organize, categoryForHeading } from './model.mjs';

const asset = name => new URL(`assets/${name}`, document.baseURI).href;
pdfjs.GlobalWorkerOptions.workerSrc = asset('pdf.worker.mjs');
const abortError = () => new DOMException('Importação cancelada.', 'AbortError');
const check = signal => { if (signal?.aborted) throw abortError(); };
const W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main';

async function ocr(canvas, signal, progress) {
  check(signal);
  let worker;
  let rejectCancelled;
  const cancelled = new Promise((_, reject) => {
    rejectCancelled = reject;
  });
  const abort = () => { worker?.terminate(); rejectCancelled(abortError()); };
  signal?.addEventListener('abort', abort, { once: true });
  const task = (async () => {
    worker = await createWorker('por+eng', 1, { workerPath: asset('ocr-worker.js'), corePath: asset(''), langPath: asset(''), workerBlobURL: false,
      logger: message => { if (message.status === 'recognizing text') progress(message.progress); } });
    if (signal?.aborted) { await worker.terminate(); throw abortError(); }
    const result = await worker.recognize(canvas);
    return result.data;
  })();
  try { return await Promise.race([task, cancelled]); }
  finally { signal?.removeEventListener('abort', abort); if (worker) { try { await worker.terminate(); } catch {} } }
}

function ocrBlocks(text, prefix) {
  const blocks = [];
  for (const [index, rawText] of text.split(/\n\s*\n/).entries()) {
    const lines = rawText.split('\n'), first = lines[0];
    if (first.length < 120 && categoryForHeading(first) !== 'outros') {
      blocks.push({ rawText: first, locator: `${prefix}:paragraph:${index + 1}:heading`, heading: true, level: 1 });
      if (lines.length > 1) blocks.push({ rawText: lines.slice(1).join('\n'), locator: `${prefix}:paragraph:${index + 1}:body`, heading: false });
    } else blocks.push({ rawText, locator: `${prefix}:paragraph:${index + 1}`, heading: false });
  }
  return blocks;
}

function pdfBlocks(content, page) {
  const lines = []; let current = null;
  for (const item of content.items) {
    if (typeof item.str !== 'string') continue;
    const y = item.transform[5];
    if (!current || Math.abs(current.y - y) > Math.max(2, item.height * .35)) {
      current = { text: '', height: item.height, y }; lines.push(current);
    }
    current.text += (current.text && !/\s$/.test(current.text) && item.str && !/^\s/.test(item.str) ? ' ' : '') + item.str;
    current.height = Math.max(current.height, item.height);
    if (item.hasEOL) current = null;
  }
  const heights = lines.filter(l => l.text.trim()).map(l => l.height).sort((a, b) => a - b);
  const median = heights[Math.floor(heights.length / 2)] || 12;
  const blocks = [];
  for (const [index, line] of lines.entries()) {
    const heading = !!line.text.trim() && line.text.length < 130 && (line.height > median * 1.2 || (line.text === line.text.toUpperCase() && categoryForHeading(line.text) !== 'outros'));
    const previous = lines[index - 1];
    if (!blocks.length || heading || blocks.at(-1).heading || (previous && Math.abs(previous.y - line.y) > median * 1.8)) {
      blocks.push({ rawText: line.text, locator: `pdf:page:${page}:line:${index + 1}`, heading });
    } else blocks.at(-1).rawText += '\n' + line.text;
  }
  return blocks;
}

function canvasFor(viewport) {
  const canvas = document.createElement('canvas');
  canvas.width = Math.max(1, Math.ceil(viewport.width)); canvas.height = Math.max(1, Math.ceil(viewport.height));
  return canvas;
}

function hasInk(canvas) {
  const small = document.createElement('canvas'); small.width = 96; small.height = 96;
  const context = small.getContext('2d', { willReadFrequently: true }); context.drawImage(canvas, 0, 0, 96, 96);
  const pixels = context.getImageData(0, 0, 96, 96).data;
  let ink = 0; for (let i = 0; i < pixels.length; i += 4) if (pixels[i] < 235 || pixels[i + 1] < 235 || pixels[i + 2] < 235) ink++;
  return ink > 2;
}

async function readPdf(original, signal, report) {
  const loading = pdfjs.getDocument({ data: new Uint8Array(await original.blob.arrayBuffer()), cMapUrl: asset('cmaps/'), cMapPacked: true,
    standardFontDataUrl: asset('standard_fonts/'), wasmUrl: asset('pdf-wasm/'), isEvalSupported: false, useSystemFonts: false });
  const abort = () => loading.destroy(); signal?.addEventListener('abort', abort, { once: true });
  let document;
  try {
    document = await loading.promise; check(signal);
    if (document.numPages > LIMITS.pages) throw new Error('O PDF ultrapassa o limite de 1.500 páginas. Divida-o em volumes menores.');
    const units = [];
    for (let number = 1; number <= document.numPages; number++) {
      check(signal); report(`Lendo página ${number} de ${document.numPages}`, (number - 1) / document.numPages);
      const page = await document.getPage(number); const content = await page.getTextContent();
      let blocks = pdfBlocks(content, number), method = 'pdf-text', confidence = null;
      let rawText = blocks.map(block => block.rawText).join('\n');
      if (rawText.replace(/\s/g, '').length < 40) {
        const base = page.getViewport({ scale: 1 });
        const viewport = page.getViewport({ scale: Math.min(2, 1800 / Math.max(base.width, base.height)) });
        const canvas = canvasFor(viewport);
        try {
          await page.render({ canvasContext: canvas.getContext('2d'), viewport, background: 'rgb(255,255,255)' }).promise; check(signal);
          if (hasInk(canvas)) {
            const result = await ocr(canvas, signal, fraction => report(`Reconhecendo texto · página ${number} de ${document.numPages}`, (number - 1 + fraction) / document.numPages));
            // Keep short digital text if OCR produces nothing useful.
            if (result.text.trim()) { rawText = result.text; blocks = ocrBlocks(rawText, `pdf:page:${number}:ocr`); method = 'ocr'; confidence = result.confidence; }
            else if (!rawText.trim()) { method = 'ocr-empty'; confidence = result.confidence; }
          } else if (!rawText.trim()) { blocks = []; rawText = ''; method = 'blank'; }
        } finally { canvas.width = canvas.height = 1; }
      }
      units.push({ page: number, label: `Página ${number}`, rawText, blocks, method, confidence });
      enforceBounds(units); page.cleanup();
    }
    return units;
  } catch (error) {
    check(signal);
    if (error.name === 'PasswordException') throw new Error('O PDF tem senha. Anexe uma cópia desbloqueada.');
    throw error;
  } finally { signal?.removeEventListener('abort', abort); await loading.destroy(); }
}

function parseXml(bytes) {
  const text = new TextDecoder().decode(bytes);
  if (/<!DOCTYPE|<!ENTITY/i.test(text)) throw new Error('Este documento Word contém estruturas XML não suportadas.');
  const xml = new DOMParser().parseFromString(text, 'application/xml');
  if (xml.getElementsByTagName('parsererror').length) throw new Error('O documento Word está corrompido.');
  return xml;
}

function readDocx(bytes) {
  let total = 0; const names = new Set();
  const files = unzipSync(bytes, { filter: file => {
    if (names.has(file.name)) throw new Error('O Word contém partes duplicadas.'); names.add(file.name);
    if (names.size > 4096) throw new Error('O Word contém partes demais.');
    if (!/^word\/.*\.xml$/.test(file.name)) return false;
    total += file.originalSize;
    if (total > 64 * 1024 * 1024 || names.size > 4096) throw new Error('O Word excede o limite de conteúdo descompactado.');
    return true;
  } });
  if (!files['word/document.xml']) throw new Error('Este arquivo não contém um documento Word válido.');
  const units = [];
  const ordered = Object.keys(files).sort((a, b) => (a === 'word/document.xml' ? -1 : b === 'word/document.xml' ? 1 : a.localeCompare(b)));
  for (const part of ordered) {
    const xml = parseXml(files[part]); const paragraphs = [...xml.getElementsByTagNameNS(W, 'p')];
    if (!paragraphs.length && !xml.getElementsByTagNameNS(W, 't').length) continue;
    const consumed = new Set();
    const blocks = paragraphs.map((paragraph, index) => {
      let rawText = '';
      const collect = element => {
        if (element !== paragraph && element.namespaceURI === W && element.localName === 'p') return;
        if (element.namespaceURI === W) {
          if (element.localName === 't') { rawText += element.textContent; consumed.add(element); }
          if (['br', 'cr'].includes(element.localName)) rawText += '\n';
          if (element.localName === 'tab') rawText += '\t';
          if (element.localName === 'noBreakHyphen') rawText += '\u2011';
          if (element.localName === 'softHyphen') rawText += '\u00ad';
        }
        for (const child of element.children) collect(child);
      }; collect(paragraph);
      const style = paragraph.getElementsByTagNameNS(W, 'pStyle')[0]?.getAttributeNS(W, 'val') || '';
      const explicitHeading = /^(?:heading|t[ií]tulo|title)\s*\d*/i.test(style);
      const title = rawText.trim();
      const shortTitle = title.length > 2 && title.length <= 100 && !/[\n:;.!?]/.test(title);
      const categoryHeading = shortTitle && categoryForHeading(title) !== 'outros';
      const uppercaseHeading = shortTitle && /\p{L}{3}/u.test(title) && title === title.toUpperCase();
      return { rawText, locator: `${part}#paragraph:${index + 1}`, heading: explicitHeading || categoryHeading || uppercaseHeading,
               level: explicitHeading ? Number(style.match(/\d+/)?.[0] || 1) : categoryHeading ? 1 : uppercaseHeading ? 2 : 0 };
    });
    for (const [index, text] of [...xml.getElementsByTagNameNS(W, 't')].entries()) {
      if (!consumed.has(text)) blocks.push({ rawText: text.textContent, locator: `${part}#orphan:${index + 1}`, heading: false });
    }
    units.push({ page: null, label: part === 'word/document.xml' ? 'Documento principal' : part.replace('word/', ''), rawText: blocks.map(b => b.rawText).join('\n'), blocks, method: 'docx-text', confidence: null });
    enforceBounds(units);
  }
  return units;
}

async function imageCanvas(blob) {
  const image = await createImageBitmap(blob, { resizeWidth: 1800, resizeQuality: 'high', imageOrientation: 'from-image' });
  try {
    if (image.width * image.height > 20_000_000) throw new Error('A imagem é muito grande para converter neste navegador.');
    const canvas = canvasFor(image); const context = canvas.getContext('2d');
    context.fillStyle = '#fff'; context.fillRect(0, 0, canvas.width, canvas.height); context.drawImage(image, 0, 0); return canvas;
  } finally { image.close(); }
}

async function readImages(originals, signal, report) {
  const units = [];
  for (const [index, original] of originals.entries()) {
    check(signal); const canvas = await imageCanvas(original.blob);
    try {
      const result = await ocr(canvas, signal, fraction => report(`Reconhecendo texto · imagem ${index + 1} de ${originals.length}`, (index + fraction) / originals.length));
      units.push({ page: index + 1, label: original.name, rawText: result.text, blocks: ocrBlocks(result.text, `image:${index + 1}:ocr`), method: result.text.trim() ? 'ocr' : 'ocr-empty', confidence: result.confidence });
      enforceBounds(units);
    } finally { canvas.width = canvas.height = 1; }
  }
  return units;
}

function enforceBounds(units) {
  let chars = 0, blocks = 0;
  for (const unit of units) { chars += unit.rawText.length; blocks += unit.blocks.length; }
  if (chars > LIMITS.textChars || blocks > LIMITS.blocks) throw new Error('O texto ultrapassa o limite de importação. Divida o livro em volumes menores.');
}

export async function prepareFiles(files) {
  const originals = [];
  for (const file of files) {
    if (file.size > LIMITS.fileBytes) throw new Error(`${file.name}: limite de 50 MB por arquivo.`);
    const bytes = new Uint8Array(await file.arrayBuffer()); const kind = fileKind(bytes, file.name);
    originals.push({ name: file.name, sha256: await digest(bytes), kind, size: file.size, blob: file });
  }
  return originals;
}

export async function convert(originals, { signal, progress = () => {}, exists = () => false } = {}) {
  check(signal);
  if (!originals.length || originals.length > LIMITS.pages) throw new Error('Selecione de 1 a 1.500 arquivos.');
  const first = originals[0];
  const imageGroup = originals.every(original => !['pdf', 'docx'].includes(original.kind));
  if (originals.length > 1 && !imageGroup) throw new Error('PDFs e documentos Word devem ser importados individualmente.');
  const id = originals.length === 1 ? first.sha256 : await digest(new TextEncoder().encode(JSON.stringify(originals.map(o => ({ sha256: o.sha256, name: o.name })))));
  if (await exists(id)) return { duplicate: true, id };
  let units;
  progress('Preparando arquivo', 0);
  if (first.kind === 'pdf') units = await readPdf(first, signal, progress);
  else if (first.kind === 'docx') units = readDocx(new Uint8Array(await first.blob.arrayBuffer()));
  else units = await readImages(originals, signal, progress);
  check(signal);
  if (!units.some(unit => unit.rawText.trim())) throw new Error('Não foi encontrado texto legível. Tente uma imagem mais nítida ou um PDF com melhor resolução.');
  const book = { version: 1, status: 'PERSONAL_UNVERIFIED', id,
    title: originals.length > 1 ? `Livro em imagens · ${first.name.replace(/\.[^.]+$/, '')}` : first.name.replace(/\.[^.]+$/, '').replace(/_/g, ' '),
    pageBasis: first.kind === 'pdf' ? 'PDF_PHYSICAL_INDEX' : first.kind === 'docx' ? 'DOCX_UNVERIFIED' : 'IMAGE_FILE_ORDER',
    importedAt: new Date().toISOString(), originals, units, sections: organize(units) };
  progress('Salvando na biblioteca', 1); return book;
}

export async function sourcePreview(book, unitIndex, canvas) {
  const original = book.originals[book.pageBasis === 'IMAGE_FILE_ORDER' ? unitIndex : 0];
  if (original.kind === 'pdf') {
    const loading = pdfjs.getDocument({ data: new Uint8Array(await original.blob.arrayBuffer()), cMapUrl: asset('cmaps/'), cMapPacked: true, standardFontDataUrl: asset('standard_fonts/'), wasmUrl: asset('pdf-wasm/'), isEvalSupported: false });
    try {
      const document = await loading.promise; const page = await document.getPage(book.units[unitIndex].page);
      const base = page.getViewport({ scale: 1 }); const viewport = page.getViewport({ scale: Math.min(2, 1300 / base.width) });
      canvas.width = Math.ceil(viewport.width); canvas.height = Math.ceil(viewport.height);
      await page.render({ canvasContext: canvas.getContext('2d'), viewport }).promise;
    } finally { await loading.destroy(); }
  } else {
    const image = await imageCanvas(original.blob); canvas.width = image.width; canvas.height = image.height; canvas.getContext('2d').drawImage(image, 0, 0); image.width = image.height = 1;
  }
}

export { pdfBlocks, readDocx };
