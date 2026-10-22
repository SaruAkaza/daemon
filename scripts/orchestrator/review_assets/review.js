"use strict";
(() => {
  const packet = JSON.parse(document.getElementById("packet-data").textContent);
  const blocks = packet.extraction.blocks;
  const media = packet.media;
  const $ = id => document.getElementById(id);
  const blockMap = new Map(blocks.map((b, index) => [b.anchor, { ...b, index }]));
  const mediaMap = new Map(media.map((m, index) => [m.part, { ...m, index }]));
  let blockNotes = new Map(), mediaNotes = new Map();
  let tab = "text", offset = 0, dirty = false;
  const PAGE_SIZE = 40;
  const binding = { sourceId: packet.sourceId, sourceSha256: packet.sourceSha256, evidenceSha256: packet.evidenceSha256 };
  const fields = ["reviewer", "reference", "page-basis", "page-count", "general"];
  const setDirty = () => { dirty = true; $("save-status").textContent = "Alterações pendentes de exportação."; };
  fields.forEach(id => $(id).addEventListener("input", setDirty));
  window.addEventListener("beforeunload", event => { if (dirty) { event.preventDefault(); event.returnValue = ""; } });

  function el(tag, text, className) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  }
  function noteFor(item) { return (tab === "text" ? blockNotes.get(item.anchor) : mediaNotes.get(item.part)) || {}; }
  function updateNote(item, key, value) {
    const notes = tab === "text" ? blockNotes : mediaNotes;
    const id = tab === "text" ? item.anchor : item.part;
    notes.set(id, { ...notes.get(id), [key]: value });
    setDirty();
    progress();
  }
  function inputField(card, label, item, key, multiline = false) {
    const wrapper = el("label", label);
    const input = el(multiline ? "textarea" : "input");
    input.maxLength = multiline ? 10000 : 200;
    if (multiline) input.rows = 2;
    input.value = noteFor(item)[key] || "";
    input.addEventListener("input", () => updateNote(item, key, input.value));
    wrapper.append(input); card.append(wrapper);
  }
  function progress() {
    const textCount = [...blockNotes.values()].filter(n => n.checked).length;
    const mediaCount = [...mediaNotes.values()].filter(n => n.checked).length;
    const pages = [...blockNotes.values()].filter(n => n.pageLabel?.trim()).length;
    $("progress").textContent = `${textCount}/${blocks.length} blocos conferidos · ${mediaCount}/${media.length} imagens conferidas · ${pages} blocos com página anotada. Rascunho sem certificação.`;
  }
  function gotoBlock(anchor) {
    tab = "text"; offset = 0; $("search").value = anchor; $("pending").checked = false; render();
    $("items").scrollIntoView({ behavior: "smooth" });
  }
  function card(item, index) {
    const node = el("article", undefined, "card");
    const isText = tab === "text";
    node.append(el("h2", isText ? `Bloco ${index + 1}` : `Imagem ${index + 1}`));
    node.append(el("p", isText ? item.anchor : item.part, "anchor"));
    if (isText) {
      node.append(el("p", item.rawText || "(Parágrafo vazio preservado)", item.rawText ? "source-text" : "empty"));
      node.append(el("p", item.page === null ? "Página da fonte: não certificada" : `Página física do PDF: ${item.page}`, "anchor"));
      if (item.cleanText !== item.rawText || item.auxiliaryTokens.length) {
        const detail = el("details"); detail.append(el("summary", "Normalização e tokens auxiliares"));
        detail.append(el("pre", JSON.stringify({ cleanText: item.cleanText, normalizations: item.normalizations, auxiliaryTokens: item.auxiliaryTokens }, null, 2)));
        node.append(detail);
      }
      const images = media.filter(m => m.anchors.includes(item.anchor));
      if (images.length) {
        const links = el("div", undefined, "links");
        images.forEach(image => {
          const button = el("button", `Ver imagem ${mediaMap.get(image.part).index + 1}`);
          button.addEventListener("click", () => { tab = "media"; offset = 0; $("search").value = image.part; $("pending").checked = false; render(); });
          links.append(button);
        });
        node.append(links);
      }
    } else {
      if (item.preview) { const img = el("img"); img.src = item.preview; img.alt = `Prévia de ${item.part}`; img.loading = "lazy"; node.append(img); }
      node.append(el("p", item.preview ? `Prévia do primeiro quadro; original ${item.width} × ${item.height} pixels, ${item.frameCount} quadro(s). Confira detalhes no original.` : "Sem prévia compatível. Confira esta parte no documento original.", "anchor"));
      const links = el("div", undefined, "links");
      item.anchors.forEach(anchor => { const button = el("button", `Ir ao bloco ${blockMap.get(anchor)?.index + 1}`); button.addEventListener("click", () => gotoBlock(anchor)); links.append(button); });
      node.append(links);
      if (!item.anchors.length) node.append(el("p", "Sem vínculo de parágrafo recuperado; conferir no original.", "anchor"));
    }
    const controls = el("div", undefined, "card-fields");
    if (isText) inputField(controls, "Página ou intervalo na referência", item, "pageLabel");
    inputField(controls, "Observação / correção proposta", item, "note", true);
    node.append(controls);
    const checked = el("label", undefined, "check"), checkbox = el("input"); checkbox.type = "checkbox"; checkbox.checked = !!noteFor(item).checked;
    checkbox.addEventListener("change", () => { updateNote(item, "checked", checkbox.checked); if ($("pending").checked) render(); });
    checked.append(checkbox, document.createTextNode(isText ? "Conferi este trecho com a referência" : "Conferi esta imagem no original")); node.append(checked);
    return node;
  }
  function render() {
    $("text-tab").setAttribute("aria-pressed", String(tab === "text")); $("media-tab").setAttribute("aria-pressed", String(tab === "media"));
    const query = $("search").value.toLocaleLowerCase("pt-BR").trim();
    const source = tab === "text" ? blocks : media;
    const filtered = source.map((item, index) => ({ item, index })).filter(({ item, index }) => {
      const haystack = tab === "text" ? `${index + 1} ${item.anchor} ${item.rawText} ${item.cleanText}` : `${index + 1} ${item.part}`;
      return (!$("pending").checked || !noteFor(item).checked) && (!query || haystack.toLocaleLowerCase("pt-BR").includes(query));
    });
    offset = Math.max(0, Math.min(offset, Math.max(0, Math.ceil(filtered.length / PAGE_SIZE) - 1) * PAGE_SIZE));
    $("items").replaceChildren(...filtered.slice(offset, offset + PAGE_SIZE).map(({ item, index }) => card(item, index)));
    if (!filtered.length) $("items").append(el("p", "Nenhum item encontrado."));
    $("range").textContent = filtered.length ? `${offset + 1}–${Math.min(offset + PAGE_SIZE, filtered.length)} de ${filtered.length}` : "0 itens";
    $("previous").disabled = offset === 0; $("next").disabled = offset + PAGE_SIZE >= filtered.length; progress();
  }
  $("text-tab").addEventListener("click", () => { tab = "text"; offset = 0; $("search").value = ""; render(); });
  $("media-tab").addEventListener("click", () => { tab = "media"; offset = 0; $("search").value = ""; render(); });
  $("search").addEventListener("input", () => { offset = 0; render(); });
  $("pending").addEventListener("change", () => { offset = 0; render(); });
  $("previous").addEventListener("click", () => { offset -= PAGE_SIZE; render(); $("items").scrollIntoView(); });
  $("next").addEventListener("click", () => { offset += PAGE_SIZE; render(); $("items").scrollIntoView(); });

  function draft() {
    if (!$("page-count").checkValidity()) throw new Error("Informe um total de páginas inteiro, entre 1 e 100.000, ou deixe vazio.");
    return { format: "daemon-review-notes", version: 1, status: "DRAFT_UNVERIFIED", ...binding,
      reviewer: $("reviewer").value, reference: $("reference").value, pageBasis: $("page-basis").value,
      referencePageCount: $("page-count").value ? Number($("page-count").value) : null, generalNotes: $("general").value,
      blockNotes: [...blockNotes].map(([anchor, value]) => ({ anchor, rawTextSha256: blockMap.get(anchor).rawTextSha256, pageLabel: value.pageLabel || "", note: value.note || "", checked: !!value.checked })),
      mediaNotes: [...mediaNotes].map(([part, value]) => ({ part, sha256: mediaMap.get(part).sha256, note: value.note || "", checked: !!value.checked })) };
  }
  $("export").addEventListener("click", () => {
    try {
      const data = JSON.stringify(draft(), null, 2);
      if (new Blob([data]).size > 10 * 1024 * 1024) throw new Error("As anotações excedem 10 MiB. Reduza observações longas antes de exportar; seu trabalho permanece nesta tela.");
      const url = URL.createObjectURL(new Blob([data], { type: "application/json" }));
      const link = el("a"); link.href = url; link.download = `daemon-anotacoes-${packet.sourceSha256.slice(0, 12)}.json`;
      link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
      dirty = false; $("save-status").textContent = "Exportação solicitada. Guarde o JSON para continuar depois."; $("error").hidden = true;
    } catch (error) { $("error").textContent = error.message; $("error").hidden = false; }
  });
  function validateDraft(value) {
    const fail = () => { throw new Error("Anotações inválidas ou de outra fonte/tentativa. Nenhuma anotação atual foi substituída."); };
    const string = (s, max) => typeof s === "string" && s.length <= max;
    if (!value || value.format !== "daemon-review-notes" || value.version !== 1 || value.status !== "DRAFT_UNVERIFIED" ||
        Object.entries(binding).some(([key, expected]) => value[key] !== expected) ||
        !string(value.reviewer, 200) || !string(value.reference, 2000) || !string(value.generalNotes, 10000) ||
        !["UNSPECIFIED", "PDF_PHYSICAL_INDEX", "PRINTED_LABEL", "DOCX_RENDERED_PAGE"].includes(value.pageBasis) ||
        !(value.referencePageCount === null || (Number.isInteger(value.referencePageCount) && value.referencePageCount >= 1 && value.referencePageCount <= 100000)) ||
        !Array.isArray(value.blockNotes) || value.blockNotes.length > blocks.length || !Array.isArray(value.mediaNotes) || value.mediaNotes.length > media.length) fail();
    const bn = new Map(), mn = new Map();
    for (const note of value.blockNotes) {
      if (!note || !blockMap.has(note.anchor) || bn.has(note.anchor) || note.rawTextSha256 !== blockMap.get(note.anchor).rawTextSha256 || !string(note.pageLabel, 200) || !string(note.note, 10000) || typeof note.checked !== "boolean") fail();
      bn.set(note.anchor, { pageLabel: note.pageLabel, note: note.note, checked: note.checked });
    }
    for (const note of value.mediaNotes) {
      if (!note || !mediaMap.has(note.part) || mn.has(note.part) || note.sha256 !== mediaMap.get(note.part).sha256 || !string(note.note, 10000) || typeof note.checked !== "boolean") fail();
      mn.set(note.part, { note: note.note, checked: note.checked });
    }
    return { bn, mn };
  }
  $("import").addEventListener("change", async event => {
    try {
      const file = event.target.files[0]; if (!file) return;
      if (file.size > 10 * 1024 * 1024) throw new Error("O JSON excede o limite de 10 MiB.");
      const value = JSON.parse(await file.text()); const { bn, mn } = validateDraft(value);
      if (dirty && !window.confirm("Substituir as anotações atuais pelo JSON importado? Exporte antes para guardá-las.")) return;
      blockNotes = bn; mediaNotes = mn;
      $("reviewer").value = value.reviewer; $("reference").value = value.reference; $("page-basis").value = value.pageBasis;
      $("page-count").value = value.referencePageCount ?? ""; $("general").value = value.generalNotes;
      dirty = false; $("save-status").textContent = "Anotações importadas como rascunho."; $("error").hidden = true; render();
    } catch (error) { $("error").textContent = error.message; $("error").hidden = false; }
    finally { event.target.value = ""; }
  });
  $("title").textContent = packet.title;
  $("summary").textContent = `${blocks.length} blocos de texto · ${media.length} partes de mídia recuperadas · ${packet.extraction.pageCount === null ? "paginação não certificada" : `${packet.extraction.pageCount} páginas físicas no PDF`}`;
  $("integrity").textContent = JSON.stringify({ ...binding, rightsStatus: packet.rightsStatus, visibility: packet.visibility, publicationMode: packet.publicationMode, pageBasis: packet.extraction.pageBasis, issueCodes: packet.extraction.issueCodes, unresolvedMediaReferences: packet.unresolvedMediaReferences }, null, 2);
  render();
})();
