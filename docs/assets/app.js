const AREAS = [
  ["all", "Todas"],
  ["regras_base", "Regras Base"],
  ["pericias", "Perícias"],
  ["aprimoramentos", "Aprimoramentos"],
  ["manobras_combate", "Manobras de Combate"],
  ["kits", "Kits"],
  ["classes", "Classes"],
  ["racas", "Raças"],
  ["linhagens", "Linhagens"],
  ["poderes", "Poderes"],
  ["magias", "Magias"],
  ["rituais", "Rituais"],
  ["itens_equipamentos", "Itens e Equipamentos"],
  ["criaturas_npcs", "Criaturas e NPCs"],
  ["cenarios_lore", "Cenários e Lore"],
  ["aventuras", "Aventuras"],
  ["tabelas", "Tabelas"],
];

const SECTION_LABELS = {
  intro: "Introdução",
  ficha: "Ficha",
  historia: "História",
  personalidade: "Personalidade",
  poderes_npc: "Poderes",
  curiosidades: "Curiosidades",
};

const THEME_KEY = "daemonPilots.theme";

const state = {
  books: [],
  items: [],
  areaCounts: new Map(),
  filterGroupsCache: null,
  filterGroupsCacheKey: "",
  selectedArea: null,
  selectedItemId: null,
  query: "",
  section: "all",
  filters: {
    books: new Set(),
    areas: new Set(),
    kinds: new Set(),
  },
  globalFilters: {
    books: new Set(),
  },
  filterMode: "category",
  collapsedGroups: new Set(),
  draftFilters: null,
  filterSearch: "",
};

const nodes = {
  categoryHub: document.querySelector("#categoryHub"),
  segmentsList: document.querySelector("#segmentsList"),
  segmentsTitle: document.querySelector("#segmentsTitle"),
  segmentsCount: document.querySelector("#segmentsCount"),
  detailPanel: document.querySelector("#detailPanel"),
  searchInput: document.querySelector("#searchInput"),
  areaFilter: document.querySelector("#areaFilter"),
  flagFilter: document.querySelector("#flagFilter"),
  brandHomeButton: document.querySelector("#brandHomeButton"),
  themeToggle: document.querySelector("#themeToggle"),
  refreshButton: document.querySelector("#refreshButton"),
  filterOpenButton: document.querySelector("#filterOpenButton"),
  categoryFilterButton: document.querySelector("#categoryFilterButton"),
  filterBackdrop: document.querySelector("#filterBackdrop"),
  filterPanel: document.querySelector("#filterPanel"),
  filterTitle: document.querySelector("#filterTitle"),
  filterCloseButton: document.querySelector("#filterCloseButton"),
  filterSearchInput: document.querySelector("#filterSearchInput"),
  filterGroups: document.querySelector("#filterGroups"),
  filterSummary: document.querySelector("#filterSummary"),
  filterShowAllButton: document.querySelector("#filterShowAllButton"),
  filterClearButton: document.querySelector("#filterClearButton"),
  filterDefaultButton: document.querySelector("#filterDefaultButton"),
  filterApplyButton: document.querySelector("#filterApplyButton"),
  filterCancelButton: document.querySelector("#filterCancelButton"),
  categoryCardTemplate: document.querySelector("#categoryCardTemplate"),
  segmentTemplate: document.querySelector("#segmentTemplate"),
  filterGroupTemplate: document.querySelector("#filterGroupTemplate"),
};

async function fetchJson(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) throw new Error(`Falha ao carregar ${path}`);
  return response.json();
}

function normalize(value) {
  return String(value ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}

function formatNumber(value) {
  return new Intl.NumberFormat("pt-BR").format(value ?? 0);
}

function clearNode(node) {
  while (node.firstChild) node.firstChild.remove();
}

function preferredTheme() {
  const saved = localStorage.getItem(THEME_KEY);
  if (saved === "dark" || saved === "light") return saved;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function applyTheme(theme) {
  const nextTheme = theme === "dark" ? "dark" : "light";
  document.documentElement.dataset.theme = nextTheme;
  nodes.themeToggle.setAttribute("aria-pressed", nextTheme === "dark" ? "true" : "false");
  nodes.themeToggle.textContent = nextTheme === "dark" ? "Tema claro" : "Tema escuro";
}

function areaLabel(area) {
  return AREAS.find(([id]) => id === area)?.[1] || area;
}

function sectionText(section) {
  return section.paragraphs.join("\n\n");
}

function pill(label, tone = "") {
  const span = document.createElement("span");
  span.className = `pill ${tone}`.trim();
  span.textContent = label;
  return span;
}

function baseItem(book, extra) {
  const item = {
    book,
    bookTitle: book.title,
    sourceFile: book.sourceFile,
    parentName: book.title,
    ...extra,
  };
  if (item.area === "cenarios_lore") {
    item.title = `Cenarios/Lore - ${book.title}`;
  }
  return item;
}

function buildCharacterItems(book) {
  const items = [];

  if (book.intro) {
    items.push(baseItem(book, {
      id: `${book.source}:lore-intro`,
      kind: "section",
      area: "cenarios_lore",
      title: book.loreTitle || book.title,
      sectionId: "intro",
      sectionTitle: book.intro.title || "Introdução",
      paragraphs: [...(book.intro.quote || []), ...(book.intro.paragraphs || [])],
      npc: null,
    }));
  }

  for (const npc of book.characters || []) {
    items.push(baseItem(book, {
      id: `${book.source}:npc-${npc.id}`,
      kind: "npc",
      area: "criaturas_npcs",
      title: npc.name,
      sectionId: "ficha",
      sectionTitle: "NPC",
      paragraphs: npc.sections.flatMap((section) => section.paragraphs),
      npc,
    }));
  }

  return items;
}

function buildSectionItems(book) {
  const items = (book.sections || [])
    .filter((section) => section.area !== "front_matter")
    .map((section) => baseItem(book, {
      id: `${book.source}:section-${section.area}-${section.kind || "section"}-${section.id}`,
      kind: section.kind || "section",
      area: section.area,
      title: section.title,
      sectionId: section.id,
      sectionTitle: section.title,
      paragraphs: section.paragraphs || [],
      sections: section.sections || [],
      npc: null,
    }));

  for (const group of book.groups || []) {
    items.push(baseItem(book, {
      id: `${book.source}:group-${group.id}`,
      kind: group.kind || "group",
      area: group.area,
      title: group.title,
      sectionId: group.kind || "group",
      sectionTitle: group.sectionTitle || areaLabel(group.area),
      paragraphs: group.sections.flatMap((section) => section.paragraphs || []),
      sections: group.sections || [],
      npc: null,
    }));
  }

  for (const adventure of book.adventures || []) {
    items.push(baseItem(book, {
      id: `${book.source}:adventure-${adventure.id}`,
      kind: "adventure",
      area: "aventuras",
      title: adventure.title,
      sectionId: "aventura",
      sectionTitle: "Aventura",
      paragraphs: adventure.sections.flatMap((section) => section.paragraphs || []),
      sections: adventure.sections || [],
      npc: null,
    }));
  }

  return items;
}

function buildItems(book) {
  return [
    ...buildCharacterItems(book),
    ...buildSectionItems(book),
  ];
}

function categoryCount(area) {
  const items = globalScopedItems();
  if (area === "all") return items.length;
  return items.filter((item) => item.area === area).length;
}

function countBy(items, getKey) {
  const counts = new Map();
  for (const item of items) {
    const keys = [].concat(getKey(item)).filter(Boolean);
    for (const key of keys) counts.set(key, (counts.get(key) || 0) + 1);
  }
  return counts;
}

function invalidateFilterGroups() {
  state.filterGroupsCache = null;
  state.filterGroupsCacheKey = "";
}

function refreshAreaCounts() {
  state.areaCounts = countBy(state.items, (item) => item.area);
}

function scopedFilterItems() {
  const items = globalScopedItems();
  if (!state.selectedArea) return items;
  if (state.selectedArea === "all") return items;
  return items.filter((item) => item.area === state.selectedArea);
}

function sectionByTitle(item, title) {
  const target = normalize(title);
  return (item.sections || []).find((section) => normalize(section.title) === target);
}

function sectionTitles(item) {
  if (item._sectionTitles) return item._sectionTitles;
  return (item.sections || []).map((section) => section.title).filter(Boolean);
}

function itemCostOptions(item) {
  if (item._costOptions) return item._costOptions;
  const costSections = (item.sections || []).filter((section) => {
    const title = normalize(section.title);
    return title === "custo" || title === "custo de pericia";
  });
  return costSections.flatMap((section) => (section.paragraphs || []).map((paragraph) => {
    const text = String(paragraph).trim();
    const points = text.match(/^\s*([+-]?\d+)\s+pontos?/i);
    if (points) {
      const value = Number(points[1]);
      return `${points[1]} ${Math.abs(value) === 1 ? "Ponto" : "Pontos"}`;
    }
    const pts = text.match(/^\s*([+-]?\d+)\s+pts?\.?(?:\s+de\s+(.+?))?\.?\s*$/i);
    if (pts) return pts[2] ? `${pts[1]} pts. ${pts[2]}` : `${pts[1]} pts.`;
    const numeric = text.match(/^\s*([+-]?\d+)\s*$/);
    if (numeric) return numeric[1];
    return "";
  })).filter(Boolean);
}

function itemPolarityOption(item) {
  if (Object.prototype.hasOwnProperty.call(item, "_polarityOption")) return item._polarityOption;
  if (item.area !== "aprimoramentos") return null;
  if (item.polarity) return item.polarity;
  const values = itemCostOptions(item)
    .map((cost) => Number(cost.match(/^[+-]?\d+/)?.[0]))
    .filter((value) => Number.isFinite(value));
  if (values.some((value) => value < 0)) return "negativo";
  if (values.some((value) => value > 0)) return "positivo";
  return "sem-marcacao";
}

function itemLevelOptions(item) {
  if (item._levelOptions) return item._levelOptions;
  return sectionTitles(item)
    .map((title) => normalize(title).match(/vel\s+(\d+)/i)?.[1])
    .filter(Boolean)
    .map((value) => `Nível ${value}`);
}

function itemPrerequisiteOptions(item) {
  if (item._prerequisiteOptions) return item._prerequisiteOptions;
  const prerequisite = (item.sections || []).find((section) => normalize(section.title).includes("requisito"));
  return (prerequisite?.paragraphs || [])
    .map((paragraph) => paragraph.replace(/[()]/g, "").trim())
    .filter(Boolean);
}

function itemCaminhoOptions(item) {
  const section = (item.sections || []).find((s) => normalize(s.title) === "caminho");
  return (section?.paragraphs || []).map((p) => String(p).trim()).filter(Boolean);
}

function itemCirculoOptions(item) {
  const section = (item.sections || []).find((s) => normalize(s.title) === "circulo");
  return (section?.paragraphs || []).map((p) => `${String(p).trim()}º Círculo`).filter(Boolean);
}

function optionListFromCounts(counts) {
  return [...counts.entries()]
    .map(([id, count]) => ({ id, label: id, count }))
    .sort((a, b) => a.label.localeCompare(b.label, "pt-BR", { sensitivity: "base" }));
}

function globalFilterGroupsData() {
  const bookCounts = countBy(state.items, (item) => item.book.source);
  return [{
    id: "books",
    title: "Livros",
    options: state.books
      .map((book) => ({ id: book.source, label: book.title, count: bookCounts.get(book.source) || 0 }))
      .filter((option) => option.count > 0)
      .sort((a, b) => a.label.localeCompare(b.label, "pt-BR", { sensitivity: "base" })),
  }];
}

function globalScopedItems(filters = state.globalFilters) {
  const groups = globalFilterGroupsData();
  const booksGroup = groups.find((group) => group.id === "books");
  const selected = filters.books;
  if (!booksGroup || !selected || selected.size === booksGroup.options.length) return state.items;
  if (selected.size === 0) return [];
  return state.items.filter((item) => selected.has(item.book.source));
}

function filterGroupsData() {
  const globalBooks = [...(state.globalFilters.books || [])].sort().join(",");
  const cacheKey = `${state.selectedArea || ""}:${state.items.length}:${globalBooks}`;
  if (state.filterGroupsCache && state.filterGroupsCacheKey === cacheKey) {
    return state.filterGroupsCache;
  }

  const scopedItems = scopedFilterItems();
  const groups = [];

  if (!state.selectedArea || state.selectedArea === "all") {
    const areaCounts = countBy(scopedItems, (item) => item.area);
    groups.push({
      id: "areas",
      title: "Categorias",
      options: AREAS
        .filter(([area]) => area !== "all" && (areaCounts.get(area) || 0) > 0)
        .map(([area, label]) => ({ id: area, label, count: areaCounts.get(area) || 0 })),
    });
  }

  const kindCounts = countBy(scopedItems, (item) => item.kind || "section");
  if (kindCounts.size > 1 || !state.selectedArea || state.selectedArea === "all") {
    groups.push({
      id: "kinds",
      title: "Tipos",
      options: [...kindCounts.keys()]
        .map((kind) => ({ id: kind, label: itemTypeLabel({ kind }), count: kindCounts.get(kind) || 0 }))
        .sort((a, b) => a.label.localeCompare(b.label, "pt-BR", { sensitivity: "base" })),
    });
  }

  if (state.selectedArea === "aprimoramentos") {
    const polarityCounts = countBy(scopedItems, itemPolarityOption);
    const polarityLabels = new Map([
      ["negativo", "Negativos"],
      ["positivo", "Positivos"],
      ["sem-marcacao", "Sem marcacao"],
    ]);
    const polarityOptions = [...polarityLabels.entries()]
      .map(([id, label]) => ({ id, label, count: polarityCounts.get(id) || 0 }))
      .filter((option) => option.count > 0);
    if (polarityOptions.length > 1) {
      groups.push({ id: "polarity", title: "Natureza", options: polarityOptions });
    }
  }

  if (state.selectedArea === "aprimoramentos" || state.selectedArea === "racas") {
    groups.push({
      id: "costs",
      title: "Custo",
      options: optionListFromCounts(countBy(scopedItems, itemCostOptions)),
    });
  }

  if (state.selectedArea === "poderes") {
    const prerequisites = optionListFromCounts(countBy(scopedItems, itemPrerequisiteOptions));
    const levels = optionListFromCounts(countBy(scopedItems, itemLevelOptions));
    if (prerequisites.length) groups.push({ id: "prerequisites", title: "Pré-requisito", options: prerequisites });
    if (levels.length) groups.push({ id: "levels", title: "Nível", options: levels });
  }

  if (state.selectedArea === "magias") {
    const circulos = optionListFromCounts(countBy(scopedItems, itemCirculoOptions));
    if (circulos.length) groups.push({ id: "circulos", title: "Círculo", options: circulos });
  }

  const blocksExcluded = ["all", "aprimoramentos", "racas", "poderes", "magias"];
  if (!blocksExcluded.includes(state.selectedArea)) {
    const blocks = optionListFromCounts(countBy(scopedItems, sectionTitles));
    if (blocks.length > 1) groups.push({ id: "blocks", title: "Blocos", options: blocks });
  }

  state.filterGroupsCache = groups.filter((group) => group.options.length);
  state.filterGroupsCacheKey = cacheKey;
  return state.filterGroupsCache;
}

function activeFilterGroupsData() {
  return state.filterMode === "global" ? globalFilterGroupsData() : filterGroupsData();
}

function defaultFilters(groups = filterGroupsData()) {
  return Object.fromEntries(
    groups.map((group) => [group.id, new Set(group.options.map((option) => option.id))]),
  );
}

function cloneFilters(filters) {
  return Object.fromEntries(Object.entries(filters || {}).map(([key, value]) => [key, new Set(value)]));
}

function filtersWithDefaults(filters, groups = filterGroupsData()) {
  return {
    ...defaultFilters(groups),
    ...cloneFilters(filters),
  };
}

function filterAllows(groupId, value, filters = state.filters, groupsById = null) {
  const group = groupsById?.get(groupId) || filterGroupsData().find((entry) => entry.id === groupId);
  const allCount = group?.options.length || 0;
  const selected = filters[groupId];
  if (!selected || allCount === 0 || selected.size === allCount) return true;
  if (selected.size === 0) return false;
  return selected.has(value);
}

function filterAllowsAny(groupId, values, groupsById = null) {
  const group = groupsById?.get(groupId) || filterGroupsData().find((entry) => entry.id === groupId);
  const selected = state.filters[groupId];
  if (!group || !selected || group.options.length === 0 || selected.size === group.options.length) return true;
  if (selected.size === 0) return false;
  return values.some((value) => selected.has(value));
}

function selectedFilterCount(filters = state.filters, groups = filterGroupsData()) {
  let active = 0;
  for (const group of groups) {
    const selected = filters[group.id];
    if (selected && selected.size > 0 && selected.size < group.options.length) active += selected.size;
  }
  return active;
}

function renderAreaSelect() {
  clearNode(nodes.areaFilter);
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "Selecionar categoria";
  placeholder.disabled = true;
  nodes.areaFilter.append(placeholder);
  for (const [area, label] of AREAS) {
    if (area === "all") continue;
    const count = categoryCount(area);
    if (count === 0) continue;
    const option = document.createElement("option");
    option.value = area;
    option.textContent = `${label} (${formatNumber(count)})`;
    nodes.areaFilter.append(option);
  }
  nodes.areaFilter.value = state.selectedArea && categoryCount(state.selectedArea) ? state.selectedArea : "";
}

function selectCategory(area) {
  state.selectedArea = area;
  state.selectedItemId = null;
  state.filters = filtersWithDefaults({});
  nodes.areaFilter.value = area;
  render();
}

function renderCategoryHub() {
  clearNode(nodes.categoryHub);
  for (const [area, label] of AREAS) {
    if (area === "all") continue;
    const count = categoryCount(area);
    if (!count) continue;
    const card = nodes.categoryCardTemplate.content.firstElementChild.cloneNode(true);
    card.querySelector(".category-card-title").textContent = label;
    card.querySelector(".category-card-meta").textContent = `${formatNumber(count)} itens`;
    card.addEventListener("click", () => selectCategory(area));
    nodes.categoryHub.append(card);
  }
}

function itemSearchText(item) {
  if (item._searchText) return item._searchText;
  return normalize([
    item.title,
    item.bookTitle,
    item.sourceFile,
    item.area,
    item.sectionTitle,
    ...(item.sections || []).map((section) => section.title),
    item.paragraphs.join(" "),
    item.npc ? JSON.stringify(item.npc.statBlock) : "",
  ].join(" "));
}

function prepareItem(item) {
  item._sectionTitles = sectionTitles(item);
  item._costOptions = itemCostOptions(item);
  item._polarityOption = itemPolarityOption(item);
  item._levelOptions = itemLevelOptions(item);
  item._prerequisiteOptions = itemPrerequisiteOptions(item);
  item._searchText = itemSearchText(item);
  return item;
}

function visibleItems() {
  if (!state.selectedArea) return [];
  const query = normalize(state.query);
  const groupsById = new Map(filterGroupsData().map((group) => [group.id, group]));
  return globalScopedItems().filter((item) => {
    if (state.selectedArea !== "all" && item.area !== state.selectedArea) return false;
    if (state.section !== "all" && item.kind === "npc" && item.sectionId !== state.section) return false;
    if (!filterAllows("kinds", item.kind || "section", state.filters, groupsById)) return false;
    if (!filterAllows("polarity", itemPolarityOption(item), state.filters, groupsById)) return false;
    if (!filterAllowsAny("costs", itemCostOptions(item), groupsById)) return false;
    if (!filterAllowsAny("prerequisites", itemPrerequisiteOptions(item), groupsById)) return false;
    if (!filterAllowsAny("levels", itemLevelOptions(item), groupsById)) return false;
    if (!filterAllowsAny("caminhos", itemCaminhoOptions(item), groupsById)) return false;
    if (!filterAllowsAny("circulos", itemCirculoOptions(item), groupsById)) return false;
    if (!filterAllowsAny("blocks", sectionTitles(item), groupsById)) return false;
    if (query && !itemSearchText(item).includes(query)) return false;
    return true;
  }).sort((a, b) => a.title.localeCompare(b.title, "pt-BR", { sensitivity: "base" }));
}

function previewForItem(item) {
  if (item.kind === "npc" && item.npc) {
    return `${item.bookTitle} · ${item.npc.role} · ${item.npc.sections.length} blocos internos`;
  }
  return `${item.bookTitle} · ${item.paragraphs.join(" ").replace(/\s+/g, " ").slice(0, 170)}`;
}

function metaPillsForItem(item) {
  const costs = itemCostOptions(item);
  return costs.length ? [pill(costs.join(", "), "gold")] : [];
}

function renderSegmentRow(item) {
  const row = nodes.segmentTemplate.content.firstElementChild.cloneNode(true);
  row.dataset.itemId = item.id;
  row.classList.toggle("active", item.id === state.selectedItemId);
  row.querySelector(".segment-title").textContent = item.title;
  row.querySelector(".segment-preview").textContent = previewForItem(item);
  const meta = row.querySelector(".segment-meta");
  meta.append(...metaPillsForItem(item));
  row.addEventListener("click", () => {
    state.selectedItemId = item.id;
    updateActiveItem();
    renderDetail();
  });
  return row;
}

function renderEnhancementGroup(id, title, items) {
  const section = document.createElement("section");
  section.className = "segment-group";
  const collapsed = state.collapsedGroups.has(id);
  section.classList.toggle("collapsed", collapsed);

  const button = document.createElement("button");
  button.className = "segment-group-head";
  button.type = "button";
  button.setAttribute("aria-expanded", String(!collapsed));

  const label = document.createElement("span");
  label.textContent = title;
  const count = document.createElement("span");
  count.textContent = `${formatNumber(items.length)} itens`;
  const marker = document.createElement("span");
  marker.className = "segment-group-marker";
  marker.textContent = collapsed ? "+" : "-";
  button.append(label, count, marker);
  button.addEventListener("click", () => {
    if (state.collapsedGroups.has(id)) state.collapsedGroups.delete(id);
    else state.collapsedGroups.add(id);
    renderItems();
  });
  section.append(button);

  const body = document.createElement("div");
  body.className = "segment-group-body";
  if (!collapsed) {
    for (const item of items) body.append(renderSegmentRow(item));
  }
  section.append(body);
  nodes.segmentsList.append(section);
}

function renderItems() {
  const items = visibleItems();
  clearNode(nodes.segmentsList);
  nodes.segmentsTitle.textContent = state.selectedArea ? areaLabel(state.selectedArea) : "Itens";
  nodes.segmentsCount.textContent = `${formatNumber(items.length)} exibidos`;

  if (!items.some((item) => item.id === state.selectedItemId)) {
    state.selectedItemId = items[0]?.id || null;
  }

  if (state.selectedArea === "aprimoramentos") {
    renderEnhancementGroup("enhancements-positive", "Aprimoramentos positivos", items.filter((item) => itemPolarityOption(item) === "positivo"));
    renderEnhancementGroup("enhancements-negative", "Aprimoramentos negativos", items.filter((item) => itemPolarityOption(item) === "negativo"));
    const unmarked = items.filter((item) => itemPolarityOption(item) === "sem-marcacao");
    if (unmarked.length) renderEnhancementGroup("enhancements-unmarked", "Aprimoramentos sem marcacao", unmarked);
    return;
  }

  if (state.selectedArea === "magias") {
    const byCaminho = new Map();
    for (const item of items) {
      for (const caminho of (itemCaminhoOptions(item).length ? itemCaminhoOptions(item) : ["Outros"])) {
        if (!byCaminho.has(caminho)) byCaminho.set(caminho, []);
        byCaminho.get(caminho).push(item);
      }
    }
    const caminhos = [...byCaminho.keys()].sort((a, b) => a.localeCompare(b, "pt-BR", { sensitivity: "base" }));
    for (const caminho of caminhos) {
      renderEnhancementGroup(`magias-${caminho}`, caminho, byCaminho.get(caminho));
    }
    return;
  }

  for (const item of items) nodes.segmentsList.append(renderSegmentRow(item));
}

function updateActiveItem() {
  for (const row of nodes.segmentsList.querySelectorAll(".segment-row")) {
    row.classList.toggle("active", row.dataset.itemId === state.selectedItemId);
  }
}

function selectedItem() {
  return state.items.find((item) => item.id === state.selectedItemId);
}

function kv(value, label) {
  const node = document.createElement("div");
  node.className = "kv";
  const strong = document.createElement("strong");
  strong.textContent = value;
  const span = document.createElement("span");
  span.textContent = label;
  node.append(strong, span);
  return node;
}

function renderStatText(npc) {
  const attrs = Object.entries(npc.statBlock.attributes)
    .map(([key, value]) => `${key} ${value}`)
    .join(" · ");
  const vitals = Object.entries(npc.statBlock.vitals || {})
    .map(([key, value]) => `${key} ${value}`)
    .join(" · ");
  return [attrs, vitals].filter(Boolean).join(" · ");
}

function renderSkillsText(npc) {
  return [
    npc.statBlock.skills,
    ...(npc.statBlock.special || []),
  ].filter(Boolean).join("\n");
}

function renderTextBlock(title, text) {
  const block = document.createElement("section");
  block.className = "section";
  const heading = document.createElement("h3");
  heading.textContent = title;
  const body = document.createElement("div");
  body.className = "text-block";
  body.textContent = text;
  block.append(heading, body);
  return block;
}

function renderSectionGroup(title, sections, includeSectionTitles = false) {
  const paragraphs = sections.flatMap((section) => {
    const text = sectionText(section);
    if (!text) return [];
    if (includeSectionTitles) return [`${section.title}: ${text}`];
    return [text];
  });
  if (paragraphs.length) nodes.detailPanel.append(renderTextBlock(title, paragraphs.join("\n\n")));
}

function renderPilotNpcDetail(item) {
  const sections = item.sections || [];
  const consumed = new Set();
  const take = (predicate) => {
    const found = sections.filter((section) => !consumed.has(section) && predicate(normalize(section.title || "")));
    for (const section of found) consumed.add(section);
    return found;
  };

  renderSectionGroup("Atributos", take((title) => title.includes("atributo")), true);
  renderSectionGroup(
    "PerÃ­cias e Combate",
    take((title) => title.includes("pericia") || title.includes("combate") || title.includes("ataque")),
    true,
  );
  renderSectionGroup(
    "Habilidades",
    take((title) => (
      title.includes("habilidade")
      || title.includes("aprimoramento")
      || title.includes("caminho")
      || title.includes("poder")
      || title.includes("magia")
      || title.includes("especial")
    )),
    true,
  );

  for (const section of sections) {
    if (consumed.has(section)) continue;
    nodes.detailPanel.append(renderTextBlock(section.title, sectionText(section)));
  }
}

function renderNpcDetail(item) {
  if (!item.npc) {
    renderPilotNpcDetail(item);
    return;
  }
  const npc = item.npc;
  nodes.detailPanel.append(renderTextBlock("Atributos", renderStatText(npc)));
  nodes.detailPanel.append(renderTextBlock("Perícias e Combate", renderSkillsText(npc)));
  for (const section of npc.sections) {
    if (section.id === "ficha") continue;
    nodes.detailPanel.append(renderTextBlock(section.title, sectionText(section)));
  }
}

function renderSectionDetail(item) {
  nodes.detailPanel.append(renderTextBlock(item.sectionTitle, item.paragraphs.join("\n\n")));
}

function renderAdventureDetail(item) {
  for (const section of item.sections || []) {
    nodes.detailPanel.append(renderTextBlock(section.title, sectionText(section)));
  }
}

function npcSectionSort(a, b) {
  const order = [
    "atributos",
    "pericias-e-combate",
    "habilidades",
    "ficha",
    "historia",
    "personalidade-e-objetivos",
  ];
  const aIndex = order.indexOf(a.id);
  const bIndex = order.indexOf(b.id);
  return (aIndex === -1 ? order.length : aIndex) - (bIndex === -1 ? order.length : bIndex);
}

function renderGroupedDetail(item, sortFunction = null) {
  const sections = [...(item.sections || [])];
  if (sortFunction) sections.sort(sortFunction);
  for (const section of sections) {
    nodes.detailPanel.append(renderTextBlock(section.title, sectionText(section)));
  }
}

function itemTypeLabel(item) {
  if (item.kind === "npc") return "NPC";
  if (item.kind === "character") return "NPC";
  if (item.kind === "adventure") return "Aventura";
  if (item.kind === "ruleset") return "Regra Base";
  if (item.kind === "setting") return "Cenário";
  if (item.kind === "enhancement") return "Aprimoramento";
  if (item.kind === "power") return "Poder";
  if (item.kind === "race") return "Raça";
  if (item.kind === "ritual") return "Ritual";
  if (item.kind === "magia") return "Magia";
  if (item.kind === "class") return "Classe";
  if (item.kind === "maneuver") return "Manobra";
  if (item.kind === "equipment") return "Equipamento";
  if (item.kind === "kit") return "Kit";
  if (item.kind === "group") return "Grupo";
  return "";
}

function renderDetail() {
  const item = selectedItem();
  clearNode(nodes.detailPanel);
  if (!state.selectedArea) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "Selecione uma categoria para começar.";
    nodes.detailPanel.append(empty);
    return;
  }
  if (!item) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "Nenhum item encontrado.";
    nodes.detailPanel.append(empty);
    return;
  }

  const head = document.createElement("div");
  head.className = "detail-head";
  const title = document.createElement("h2");
  title.className = "detail-title";
  title.textContent = item.title;
  const subtitle = document.createElement("p");
  subtitle.className = "detail-subtitle";
  const typeLabel = itemTypeLabel(item);
  subtitle.textContent = [typeLabel, item.bookTitle, item.sourceFile].filter(Boolean).join(" · ");
  const tags = document.createElement("div");
  tags.className = "tag-row";
  tags.append(pill(areaLabel(item.area), "blue"));
  if (item.npc) tags.append(pill(item.npc.name, "gold"));
  head.append(title, subtitle, tags);

  nodes.detailPanel.append(head);
  if (item.kind === "npc") renderNpcDetail(item);
  else if (item.kind === "adventure") renderAdventureDetail(item);
  else if (item.sections?.length) renderGroupedDetail(item);
  else renderSectionDetail(item);
}

function setDraftGroup(groupId, values) {
  state.draftFilters[groupId] = new Set(values);
  renderFilterPanel();
}

function renderFilterPanel() {
  if (!state.draftFilters) return;
  clearNode(nodes.filterGroups);
  const groups = activeFilterGroupsData();
  const search = normalize(state.filterSearch);
  let selectedVisible = 0;
  let totalVisible = 0;

  for (const group of groups) {
    const section = nodes.filterGroupTemplate.content.firstElementChild.cloneNode(true);
    const visibleOptions = group.options.filter((option) => !search || normalize(`${option.label} ${option.id}`).includes(search));
    section.querySelector("h3").textContent = group.title;
    const chipList = section.querySelector(".filter-chip-list");

    for (const option of visibleOptions) {
      const active = state.draftFilters[group.id].has(option.id);
      const chip = document.createElement("button");
      chip.className = "filter-chip";
      chip.classList.toggle("active", active);
      chip.type = "button";
      chip.dataset.group = group.id;
      chip.dataset.value = option.id;
      chip.innerHTML = `<span>${option.label}</span><small>${formatNumber(option.count)}</small>`;
      chip.addEventListener("click", () => {
        const next = new Set(state.draftFilters[group.id]);
        if (next.has(option.id)) next.delete(option.id);
        else next.add(option.id);
        setDraftGroup(group.id, next);
      });
      chipList.append(chip);
      totalVisible += 1;
      if (active) selectedVisible += 1;
    }

    if (!visibleOptions.length) {
      const empty = document.createElement("p");
      empty.className = "filter-empty";
      empty.textContent = "Nenhuma opção neste grupo.";
      chipList.append(empty);
    }

    section.querySelectorAll(".mini-actions button").forEach((button) => {
      button.addEventListener("click", () => {
        const action = button.dataset.action;
        if (action === "clear") setDraftGroup(group.id, []);
        if (action === "all" || action === "default") setDraftGroup(group.id, group.options.map((option) => option.id));
      });
    });

    nodes.filterGroups.append(section);
  }

  nodes.filterSummary.textContent = `${formatNumber(selectedVisible)} de ${formatNumber(totalVisible)} opções visíveis selecionadas`;
}

function openFilters(mode = "category") {
  state.filterMode = mode;
  const groups = activeFilterGroupsData();
  const sourceFilters = mode === "global" ? state.globalFilters : state.filters;
  state.draftFilters = filtersWithDefaults(sourceFilters, groups);
  state.filterSearch = "";
  nodes.filterSearchInput.value = "";
  nodes.filterTitle.textContent = mode === "global" ? "Filtrar livros" : `Filtros de ${areaLabel(state.selectedArea)}`;
  nodes.filterBackdrop.hidden = false;
  renderFilterPanel();
  nodes.filterSearchInput.focus();
}

function closeFilters() {
  nodes.filterBackdrop.hidden = true;
  state.draftFilters = null;
  state.filterSearch = "";
}

function setAllDraftFilters(selected) {
  const next = defaultFilters(activeFilterGroupsData());
  if (!selected) {
    for (const key of Object.keys(next)) next[key].clear();
  }
  state.draftFilters = next;
  renderFilterPanel();
}

function applyFilters() {
  if (state.filterMode === "global") {
    state.globalFilters = cloneFilters(state.draftFilters);
    invalidateFilterGroups();
    if (state.selectedArea && !categoryCount(state.selectedArea)) state.selectedArea = null;
    state.filters = filtersWithDefaults({});
  } else {
    state.filters = cloneFilters(state.draftFilters);
  }
  state.selectedItemId = null;
  closeFilters();
  render();
}

function renderFilterButton() {
  const globalActive = selectedFilterCount(state.globalFilters, globalFilterGroupsData());
  nodes.filterOpenButton.textContent = globalActive ? `Livros (${formatNumber(globalActive)})` : "Livros";
  nodes.filterOpenButton.classList.toggle("active", globalActive > 0);
  nodes.filterOpenButton.hidden = false;

  const categoryActive = selectedFilterCount(state.filters, filterGroupsData());
  nodes.categoryFilterButton.textContent = categoryActive ? `Filtros (${formatNumber(categoryActive)})` : "Filtros";
  nodes.categoryFilterButton.classList.toggle("active", categoryActive > 0);
  nodes.categoryFilterButton.hidden = !state.selectedArea;
}

function render() {
  renderAreaSelect();
  renderCategoryHub();
  document.body.classList.toggle("is-home", !state.selectedArea);
  renderItems();
  renderDetail();
  renderFilterButton();
}

async function load() {
  const index = await fetchJson("assets/data/pilot/index.json");
  state.books = await Promise.all(
    index.sources.map((source) => fetchJson(`assets/data/pilot/${source.file}`)),
  );
  state.items = state.books.flatMap(buildItems).map(prepareItem);
  refreshAreaCounts();
  invalidateFilterGroups();
  state.globalFilters = filtersWithDefaults(state.globalFilters, globalFilterGroupsData());
  state.filters = filtersWithDefaults(state.filters);
  if (state.selectedArea && !categoryCount(state.selectedArea)) state.selectedArea = null;
  render();
}

nodes.searchInput.addEventListener("input", (event) => {
  state.query = event.target.value;
  state.selectedItemId = null;
  renderItems();
  renderDetail();
});

nodes.areaFilter.addEventListener("change", (event) => {
  if (event.target.value) selectCategory(event.target.value);
});

nodes.flagFilter.addEventListener("change", (event) => {
  state.section = event.target.value;
  state.selectedItemId = null;
  renderItems();
  renderDetail();
});

nodes.refreshButton.addEventListener("click", () => {
  state.selectedItemId = null;
  load().catch(showError);
});

nodes.brandHomeButton.addEventListener("click", () => {
  state.selectedArea = null;
  state.selectedItemId = null;
  state.filters = filtersWithDefaults({});
  nodes.searchInput.value = "";
  state.query = "";
  render();
});

nodes.themeToggle.addEventListener("click", () => {
  const current = document.documentElement.dataset.theme === "dark" ? "dark" : "light";
  const nextTheme = current === "dark" ? "light" : "dark";
  localStorage.setItem(THEME_KEY, nextTheme);
  applyTheme(nextTheme);
});

nodes.filterOpenButton.addEventListener("click", () => openFilters("global"));
nodes.categoryFilterButton.addEventListener("click", () => openFilters("category"));
nodes.filterCloseButton.addEventListener("click", closeFilters);
nodes.filterCancelButton.addEventListener("click", closeFilters);

nodes.filterBackdrop.addEventListener("click", (event) => {
  if (event.target === nodes.filterBackdrop) closeFilters();
});

nodes.filterSearchInput.addEventListener("input", (event) => {
  state.filterSearch = event.target.value;
  renderFilterPanel();
});

nodes.filterShowAllButton.addEventListener("click", () => setAllDraftFilters(true));
nodes.filterClearButton.addEventListener("click", () => setAllDraftFilters(false));
nodes.filterDefaultButton.addEventListener("click", () => setAllDraftFilters(true));
nodes.filterApplyButton.addEventListener("click", applyFilters);

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !nodes.filterBackdrop.hidden) closeFilters();
});

function showError(error) {
  clearNode(nodes.detailPanel);
  const node = document.createElement("div");
  node.className = "empty";
  node.textContent = error.message;
  nodes.detailPanel.append(node);
}

applyTheme(preferredTheme());
load().catch(showError);
