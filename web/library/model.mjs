// Personal, unverified reading material. Never a canonical entity/release payload.
export const LIMITS = Object.freeze({ fileBytes: 50 * 1024 * 1024, pages: 1500, textChars: 12_000_000, blocks: 100_000, backupBytes: 128 * 1024 * 1024 });
export const CATEGORIES = Object.freeze({ all: 'Todo o conteúdo', regras: 'Regras', poderes: 'Poderes', aprimoramentos: 'Aprimoramentos', magias: 'Magias e rituais', kits: 'Kits e classes', racas: 'Raças e linhagens', criaturas: 'Criaturas e NPCs', equipamentos: 'Equipamentos', cenarios: 'Cenários e histórias', outros: 'Outros trechos' });
export const fold = value => String(value).normalize('NFD').replace(/\p{M}/gu, '').toLocaleLowerCase('pt-BR');
export const digest = async bytes => [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))].map(n => n.toString(16).padStart(2, '0')).join('');
export const normalize = text => text.replace(/[\uFB00-\uFB06]/g, char => char.normalize('NFKC'));

export function categoryForHeading(title) {
  const value = fold(title).replace(/^\s*(?:\d+[.\s:-]+)?/, '').trim();
  const rules = [
    ['racas', /^(aprimoramentos raciais|racas?|linhagens?)(\b|:)/],
    ['regras', /^(regras?|sistema|combate|atributos?|pericias?|criacao de personagem)(\b|:)/],
    ['aprimoramentos', /^(aprimoramentos?|vantagens?|desvantagens?)(\b|:)/],
    ['poderes', /^(poderes?|disciplinas?)(\b|:)/],
    ['magias', /^(magias?|rituais?|feiticos?)(\b|:)/],
    ['kits', /^(kits?|classes?)(\b|:)/],
    ['criaturas', /^(criaturas?|monstros?|npcs?|personagens do mestre)(\b|:)/],
    ['equipamentos', /^(equipamentos?|armas?|armaduras?|itens)(\b|:)/],
    ['cenarios', /^(cenarios?|historia|cronologia|geografia|lugares|aventuras?|lendas?)(\b|:)/],
  ];
  return rules.find(([, pattern]) => pattern.test(value))?.[0] || 'outros';
}

export function fileKind(bytes, filename) {
  if (!bytes.length || bytes.length > LIMITS.fileBytes) throw new Error('Escolha um arquivo não vazio, de até 50 MB.');
  const ext = filename.split('.').pop().toLowerCase();
  const ascii = (start, end) => String.fromCharCode(...bytes.slice(start, end));
  if (ext === 'pdf' && ascii(0, 5) === '%PDF-') return 'pdf';
  if (ext === 'docx' && ascii(0, 2) === 'PK') return 'docx';
  if (['png'].includes(ext) && bytes[0] === 137 && ascii(1, 4) === 'PNG') return 'png';
  if (['jpg', 'jpeg'].includes(ext) && bytes[0] === 255 && bytes[1] === 216) return 'jpeg';
  if (ext === 'webp' && ascii(0, 4) === 'RIFF' && ascii(8, 12) === 'WEBP') return 'webp';
  if (ext === 'gif' && ['GIF87a', 'GIF89a'].includes(ascii(0, 6))) return 'gif';
  if (ext === 'bmp' && ascii(0, 2) === 'BM') return 'bmp';
  throw new Error('Formato não reconhecido. Use PDF, DOCX, PNG, JPG, WebP, GIF ou BMP.');
}

export function organize(units) {
  const sections = [];
  let current = null, category = 'outros', chars = 0;
  for (const [unitIndex, unit] of units.entries()) {
    let started = false;
    for (const [index, block] of unit.blocks.entries()) {
      const text = normalize(block.rawText);
      const title = text.trim().split('\n')[0];
      if (block.heading && title) {
        const inferred = categoryForHeading(title);
        category = inferred !== 'outros' ? inferred : block.level === 1 ? 'outros' : category;
      }
      // Start at real headings/page boundaries or whole-paragraph size boundaries.
      if (!current || block.heading || !started || chars > 4500) {
        current = { id: `s${sections.length + 1}`, title: title.slice(0, 110), category,
                    page: unit.page, unitIndex, blocks: [] };
        sections.push(current); chars = 0;
      }
      if (!current.title && title) current.title = title.slice(0, 110);
      current.blocks.push({ ...block, text, index }); chars += text.length; started = true;
    }
    if (!unit.blocks.length) {
      sections.push({ id: `s${sections.length + 1}`, title: `${unit.label} · sem texto reconhecido`, category: 'outros', page: unit.page, unitIndex, blocks: [] });
      current = null;
    }
  }
  return sections.map(section => ({ ...section, title: section.title || units[section.unitIndex].label || 'Trecho sem texto' }));
}

export function validateBook(book) {
  const fail = () => { throw new Error('A cópia da biblioteca contém um livro inválido. Seus livros atuais foram preservados.'); };
  if (!book || book.version !== 1 || book.status !== 'PERSONAL_UNVERIFIED' || !/^[a-f0-9]{64}$/.test(book.id)
      || typeof book.title !== 'string' || !book.title.trim() || book.title.length > 500
      || !Array.isArray(book.originals) || !book.originals.length || book.originals.length > LIMITS.pages
      || !Array.isArray(book.units) || !book.units.length || book.units.length > LIMITS.pages
      || !['PDF_PHYSICAL_INDEX', 'IMAGE_FILE_ORDER', 'DOCX_UNVERIFIED'].includes(book.pageBasis)) fail();
  let chars = 0, blocks = 0;
  for (const original of book.originals) {
    if (!original || !/^[a-f0-9]{64}$/.test(original.sha256) || typeof original.name !== 'string' || original.name.length > 1000
        || !['pdf', 'docx', 'png', 'jpeg', 'webp', 'gif', 'bmp'].includes(original.kind)
        || !Number.isInteger(original.size) || original.size < 1 || original.size > LIMITS.fileBytes) fail();
  }
  if (book.pageBasis === 'PDF_PHYSICAL_INDEX' && (book.originals.length !== 1 || book.originals[0].kind !== 'pdf')) fail();
  if (book.pageBasis === 'DOCX_UNVERIFIED' && (book.originals.length !== 1 || book.originals[0].kind !== 'docx')) fail();
  if (book.pageBasis === 'IMAGE_FILE_ORDER' && (book.units.length !== book.originals.length || book.originals.some(original => ['pdf', 'docx'].includes(original.kind)))) fail();
  for (const [index, unit] of book.units.entries()) {
    if (!unit || typeof unit.label !== 'string' || unit.label.length > 500 || typeof unit.rawText !== 'string' || unit.rawText.length > LIMITS.textChars || !Array.isArray(unit.blocks)
        || typeof unit.method !== 'string' || unit.method.length > 40
        || (book.pageBasis === 'DOCX_UNVERIFIED' ? unit.page !== null : unit.page !== index + 1)
        || (unit.confidence !== null && (typeof unit.confidence !== 'number' || !Number.isFinite(unit.confidence) || unit.confidence < 0 || unit.confidence > 100))) fail();
    for (const block of unit.blocks) {
      if (!block || typeof block.rawText !== 'string' || typeof block.locator !== 'string' || block.locator.length > 3000 || typeof block.heading !== 'boolean') fail();
      chars += block.rawText.length; blocks++;
    }
  }
  if (chars > LIMITS.textChars || blocks > LIMITS.blocks) fail();
  return { ...book, sections: organize(book.units) };
}

export function matchingSections(book, query = '', category = 'all') {
  const tokens = fold(query).trim().split(/\s+/).filter(Boolean);
  return book.sections.filter(section => (category === 'all' || section.category === category)
    && tokens.every(token => fold(`${book.title} ${section.title} ${section.blocks.map(block => block.text).join('\n')}`).includes(token)));
}

export function sourceLabel(book, unit) {
  return book.pageBasis === 'PDF_PHYSICAL_INDEX' ? `Página ${unit.page} do PDF`
    : book.pageBasis === 'IMAGE_FILE_ORDER' ? `Imagem ${unit.page} · ${book.originals[unit.page - 1]?.name || ''}`
      : `${unit.label} · Word sem paginação fixa`;
}
