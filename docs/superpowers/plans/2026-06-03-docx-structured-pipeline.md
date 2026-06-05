# DOCX Structured Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar `build_docx_structured.py` e `build_docx_blocks.py` — os dois primeiros estágios do novo pipeline de processamento de livros DOCX.

**Architecture:** Script único integrado para cada estágio. `build_docx_structured.py` abre o DOCX com python-docx, aplica limpeza inline e produz `data/structured/<slug>.json` (árvore hierárquica). `build_docx_blocks.py` lê essa árvore e produz `data/blocks/<slug>.json` (lista plana de blocks). Cleaning reutiliza lógica de `repair_encoding.py`.

**Tech Stack:** Python 3.11+, python-docx 1.1+, pytest, json, argparse. Sem dependências novas.

---

## Mapa de arquivos

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `scripts/build_docx_structured.py` | Criar | Parser DOCX → árvore hierárquica + CLI |
| `scripts/build_docx_blocks.py` | Criar | Árvore → lista plana de blocks + CLI |
| `tests/test_build_docx_structured.py` | Criar | Testes de cleaning, heading detection e tree builder |
| `tests/test_build_docx_blocks.py` | Criar | Testes de flatten_tree e geração de IDs |

Arquivos existentes não são modificados.

---

## Contexto do codebase (leia antes de implementar)

- `scripts/common.py` exports: `ROOT`, `BOOKS_DIR`, `DATA_DIR`, `INDEX_DIR`, `slugify`, `read_json`, `write_json`
- `scripts/repair_encoding.py` exports: `score_readability`, `decode_shift_29`, `clean_controls`, `repair_text`, `repair_line`
- Testes usam `sys.path.insert(0, str(ROOT / "scripts"))` para importar scripts
- `write_json` cria diretórios pai automaticamente
- DOCX pilots em `Livros/` — único disponível agora: `Livros/Vantagens.docx`
- Para iterar parágrafos E tabelas em ordem de documento, usar `doc.element.body` (ver Task 2)

---

## Task 1: Funções de limpeza — testes e implementação

**Files:**
- Create: `scripts/build_docx_structured.py` (só as funções de limpeza por ora — sem parser, sem CLI)
- Create: `tests/test_build_docx_structured.py`

### Funções a implementar nesta task

```python
detect_repeated_patterns(texts: list[str], threshold: float = 0.40) -> set[str]
clean_paragraph(text: str, repeated: set[str]) -> str | None
join_hyphenated_lines(text: str) -> str
normalize_whitespace(text: str) -> str
normalize_quotes(text: str) -> str
repair_encoding_in_paragraph(text: str) -> tuple[str, bool]
```

- [ ] **Step 1: Criar o arquivo de testes com os casos de limpeza**

Criar `tests/test_build_docx_structured.py`:

```python
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_docx_structured import (
    clean_paragraph,
    detect_repeated_patterns,
    join_hyphenated_lines,
    normalize_quotes,
    normalize_whitespace,
)


def test_detect_repeated_patterns_flags_high_frequency_text() -> None:
    texts = ["Daemon Trevas"] * 8 + ["Texto normal"] * 2 + ["Outro texto"] * 2
    result = detect_repeated_patterns(texts, threshold=0.40)
    assert "Daemon Trevas" in result
    assert "Texto normal" not in result


def test_detect_repeated_patterns_ignores_long_texts() -> None:
    long_text = "Este é um parágrafo longo que não deve ser considerado cabeçalho de página repetido." * 2
    texts = [long_text] * 10 + ["curto"] * 2
    result = detect_repeated_patterns(texts, threshold=0.40)
    assert long_text not in result


def test_detect_repeated_patterns_returns_empty_for_unique_texts() -> None:
    texts = [f"Texto único {i}" for i in range(20)]
    result = detect_repeated_patterns(texts, threshold=0.40)
    assert result == set()


def test_clean_paragraph_discards_repeated_patterns() -> None:
    repeated = {"© Daemon Editora"}
    assert clean_paragraph("© Daemon Editora", repeated) is None


def test_clean_paragraph_discards_lone_numbers() -> None:
    repeated: set[str] = set()
    assert clean_paragraph("42", repeated) is None
    assert clean_paragraph("3", repeated) is None


def test_clean_paragraph_discards_only_symbols() -> None:
    repeated: set[str] = set()
    assert clean_paragraph("•••", repeated) is None
    assert clean_paragraph("___", repeated) is None


def test_clean_paragraph_preserves_normal_text() -> None:
    repeated: set[str] = set()
    result = clean_paragraph("O exobiólogo estuda vida alienígena.", repeated)
    assert result == "O exobiólogo estuda vida alienígena."


def test_join_hyphenated_lines_joins_word_split_across_lines() -> None:
    text = "O persona-\ngem avança"
    assert join_hyphenated_lines(text) == "O personagem avança"


def test_join_hyphenated_lines_preserves_legitimate_hyphens() -> None:
    text = "Ele é bem-\nhumorado"
    # "bem-humorado" começa com minúscula → deve juntar
    assert join_hyphenated_lines(text) == "Ele é bem-humorado"


def test_join_hyphenated_lines_does_not_join_before_uppercase() -> None:
    # Hífen antes de palavra que começa com maiúscula → não juntar (pode ser novo parágrafo)
    text = "Veja o capí-\nTULO seguinte"
    result = join_hyphenated_lines(text)
    assert "capí-\nTULO" in result or "capí-\nTULO" in text  # preservado


def test_normalize_whitespace_collapses_multiple_spaces() -> None:
    assert normalize_whitespace("texto  com   espaços") == "texto com espaços"


def test_normalize_whitespace_removes_control_characters() -> None:
    assert normalize_whitespace("texto\x00com\x01controles") == "texto com controles"


def test_normalize_quotes_replaces_typographic_quotes() -> None:
    result = normalize_quotes("“Daemon” é ‘ótimo’")
    assert result == '"Daemon" é \'ótimo\''
```

- [ ] **Step 2: Rodar testes e confirmar falha**

```bash
cd c:\Projetos\Daemon Trevas\livros\Repositorio\daemon
pytest tests/test_build_docx_structured.py -v 2>&1 | head -30
```

Esperado: `ImportError: cannot import name 'clean_paragraph' from 'build_docx_structured'` (arquivo não existe ainda).

- [ ] **Step 3: Criar `scripts/build_docx_structured.py` com as funções de limpeza**

```python
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

from common import BOOKS_DIR, DATA_DIR, INDEX_DIR, ROOT, slugify, read_json, write_json
from repair_encoding import clean_controls, decode_shift_29, score_readability


STRUCTURED_DIR = DATA_DIR / "structured"
BLOCKS_DIR = DATA_DIR / "blocks"
STATUS_PATH = INDEX_DIR / "structured-status.json"


# ---------------------------------------------------------------------------
# Cleaning utilities
# ---------------------------------------------------------------------------

def detect_repeated_patterns(texts: list[str], threshold: float = 0.40) -> set[str]:
    """Return short texts that appear in >= threshold fraction of all short texts.

    These are likely page headers/footers injected by the DOCX converter.
    Only considers texts with 1–120 characters.
    """
    short = [t.strip() for t in texts if 0 < len(t.strip()) <= 120]
    if not short:
        return set()
    counter = Counter(short)
    total = len(short)
    return {text for text, count in counter.items() if count / total >= threshold}


def join_hyphenated_lines(text: str) -> str:
    """Join words broken across lines with a hyphen before a lowercase letter."""
    return re.sub(r"-\n([a-záàãâéêíóôõúüç])", r"\1", text)


def normalize_whitespace(text: str) -> str:
    """Collapse multiple spaces and remove control characters."""
    cleaned = "".join(
        char if char.isprintable() or char in "\n\t" else " "
        for char in text
    )
    return re.sub(r"[ \t]+", " ", cleaned).strip()


def normalize_quotes(text: str) -> str:
    """Replace typographic quotes with straight ASCII equivalents."""
    text = text.replace("“", '"').replace("”", '"')
    text = text.replace("‘", "'").replace("’", "'")
    text = text.replace("«", '"').replace("»", '"')
    return text


def repair_encoding_in_paragraph(text: str) -> tuple[str, bool]:
    """Apply shift-29 / encoding repair to a single paragraph text.

    Returns (repaired_text, was_repaired).
    """
    cleaned = clean_controls(text)
    shifted = decode_shift_29(text)
    original_score = score_readability(cleaned)
    shifted_score = score_readability(shifted)
    has_markers = "\x03" in text or bool(
        re.search(r"[A-Z0-9&][A-Z0-9\\^_`{}\\[\\]-]{3,}", text)
    )
    if has_markers and shifted_score > original_score + 6:
        return normalize_whitespace(shifted), True
    if cleaned != text:
        return normalize_whitespace(cleaned), True
    return text, False


def clean_paragraph(text: str, repeated: set[str]) -> str | None:
    """Clean a paragraph text. Returns None if the paragraph should be discarded."""
    stripped = text.strip()
    if not stripped:
        return None
    if stripped in repeated:
        return None
    # Discard lone numbers (page numbers) or lone symbols
    if re.fullmatch(r"\d+", stripped):
        return None
    if re.fullmatch(r"[^\w\s]+", stripped, re.UNICODE):
        return None

    # Apply cleaning pipeline
    result = join_hyphenated_lines(stripped)
    result, _ = repair_encoding_in_paragraph(result)
    result = normalize_quotes(result)
    result = normalize_whitespace(result)
    return result if result else None
```

- [ ] **Step 4: Rodar testes e confirmar que passam**

```bash
pytest tests/test_build_docx_structured.py -v 2>&1 | head -40
```

Esperado: todos os testes de limpeza passam (pode haver falhas nos de parsing que ainda não existem — ok por ora).

---

## Task 2: Detecção de headings — testes e implementação

**Files:**
- Modify: `scripts/build_docx_structured.py` — adicionar `classify_heading_level`
- Modify: `tests/test_build_docx_structured.py` — adicionar testes de heading

A detecção usa estilo Word primeiro, depois heurísticas de fallback.

- [ ] **Step 1: Adicionar testes de heading detection**

Acrescentar ao final de `tests/test_build_docx_structured.py`:

```python
from docx import Document as DocxDocument
from build_docx_structured import classify_heading_level


def _make_para(tmp_path: Path, text: str, style: str = "Normal", bold: bool = False) -> Any:
    """Helper: cria um parágrafo python-docx em memória."""
    doc = DocxDocument()
    p = doc.add_paragraph(text)
    try:
        p.style = doc.styles[style]
    except KeyError:
        pass  # estilo não existe no template mínimo
    if bold and p.runs:
        p.runs[0].bold = True
    return p


def test_classify_heading_level_detects_heading1_by_style(tmp_path: Path) -> None:
    p = _make_para(tmp_path, "Capítulo 1: Introdução", style="Heading 1")
    assert classify_heading_level(p) == 1


def test_classify_heading_level_detects_heading2_by_style(tmp_path: Path) -> None:
    p = _make_para(tmp_path, "Combate corpo a corpo", style="Heading 2")
    assert classify_heading_level(p) == 2


def test_classify_heading_level_detects_chapter_by_pattern(tmp_path: Path) -> None:
    p = _make_para(tmp_path, "Capítulo 3: Magia")
    assert classify_heading_level(p) == 1


def test_classify_heading_level_detects_parte_by_pattern(tmp_path: Path) -> None:
    p = _make_para(tmp_path, "PARTE II — Regras Avançadas")
    assert classify_heading_level(p) == 1


def test_classify_heading_level_returns_none_for_normal_text(tmp_path: Path) -> None:
    p = _make_para(tmp_path, "O personagem pode gastar pontos de aprimoramento.")
    assert classify_heading_level(p) is None


def test_classify_heading_level_returns_none_for_long_bold_text(tmp_path: Path) -> None:
    long = "Este é um texto muito longo que mesmo sendo negrito não deve ser considerado heading pois ultrapassa o limite de caracteres."
    p = _make_para(tmp_path, long, bold=True)
    assert classify_heading_level(p) is None
```

- [ ] **Step 2: Rodar testes e confirmar falha em classify_heading_level**

```bash
pytest tests/test_build_docx_structured.py -k "heading" -v
```

Esperado: `ImportError: cannot import name 'classify_heading_level'`

- [ ] **Step 3: Implementar `classify_heading_level` em `build_docx_structured.py`**

Adicionar após as cleaning utilities:

```python
# ---------------------------------------------------------------------------
# Heading detection
# ---------------------------------------------------------------------------

_CHAPTER_PATTERN = re.compile(
    r"^(?:cap[ií]tulo|parte|ap[eê]ndice|appendix|chapter|part)\b",
    re.IGNORECASE,
)

_HEADING_STYLE_PREFIX = "Heading"


def classify_heading_level(para: Any) -> int | None:
    """Return heading level (1, 2, 3) or None if paragraph is not a heading.

    Priority:
    1. Word style (Heading 1/2/3)
    2. Textual pattern (Capítulo N, PARTE)
    3. Heuristic: short + bold + no terminal period (returns level 2)
    """
    style_name: str = getattr(getattr(para, "style", None), "name", "") or ""
    if style_name.startswith(_HEADING_STYLE_PREFIX):
        try:
            level = int(style_name.split()[-1])
            return min(level, 3)
        except (ValueError, IndexError):
            return 1

    text = para.text.strip()
    if not text:
        return None

    # Textual pattern: Capítulo N, PARTE, Apêndice
    if _CHAPTER_PATTERN.match(text):
        return 1

    # Heuristic: short + bold + no terminal period
    if len(text) <= 80 and not text.endswith("."):
        is_bold = any(run.bold for run in para.runs if run.bold is not None)
        if is_bold:
            return 2

    return None
```

- [ ] **Step 4: Rodar testes e confirmar que passam**

```bash
pytest tests/test_build_docx_structured.py -v
```

Esperado: todos os testes até agora passam.

---

## Task 3: Tree builder — testes e implementação

**Files:**
- Modify: `scripts/build_docx_structured.py` — adicionar `iter_block_items`, `is_index_node`, `build_structured`
- Modify: `tests/test_build_docx_structured.py` — testes de `build_structured`

Esta é a função principal: abre o DOCX e constrói a árvore.

- [ ] **Step 1: Adicionar testes de `build_structured`**

Acrescentar ao final de `tests/test_build_docx_structured.py`:

```python
from build_docx_structured import build_structured


def _make_structured_docx(tmp_path: Path) -> Path:
    """Cria DOCX de teste com estrutura mínima: frontmatter + capítulo + seção + parágrafo."""
    doc = DocxDocument()
    doc.add_paragraph("Texto de capa e copyright")   # frontmatter
    h1 = doc.add_heading("Capítulo 1: Introdução", level=1)
    h2 = doc.add_heading("O Sistema Daemon", level=2)
    doc.add_paragraph("O sistema Daemon usa dados de dez faces para resolver ações.")
    path = tmp_path / "test_book.docx"
    doc.save(str(path))
    return path


def test_build_structured_produces_valid_schema(tmp_path: Path) -> None:
    path = _make_structured_docx(tmp_path)
    result = build_structured(path, source_id="test-book", title="Test Book")
    assert result["version"] == 1
    assert result["source"] == "test-book"
    assert result["sourceType"] == "docx"
    assert isinstance(result["children"], list)
    assert isinstance(result["warnings"], list)


def test_build_structured_creates_frontmatter_before_first_chapter(tmp_path: Path) -> None:
    path = _make_structured_docx(tmp_path)
    result = build_structured(path, source_id="test-book", title="Test Book")
    types = [child["type"] for child in result["children"]]
    assert types[0] == "frontmatter"


def test_build_structured_creates_chapter_node(tmp_path: Path) -> None:
    path = _make_structured_docx(tmp_path)
    result = build_structured(path, source_id="test-book", title="Test Book")
    chapters = [c for c in result["children"] if c["type"] == "chapter"]
    assert len(chapters) == 1
    assert chapters[0]["heading"] == "Capítulo 1: Introdução"
    assert chapters[0]["level"] == 1


def test_build_structured_nests_section_inside_chapter(tmp_path: Path) -> None:
    path = _make_structured_docx(tmp_path)
    result = build_structured(path, source_id="test-book", title="Test Book")
    chapters = [c for c in result["children"] if c["type"] == "chapter"]
    sections = [c for c in chapters[0]["children"] if c["type"] == "section"]
    assert len(sections) == 1
    assert sections[0]["heading"] == "O Sistema Daemon"


def test_build_structured_emits_warning_when_no_chapter_detected(tmp_path: Path) -> None:
    doc = DocxDocument()
    doc.add_paragraph("Texto sem nenhum heading de capítulo.")
    path = tmp_path / "no_chapters.docx"
    doc.save(str(path))
    result = build_structured(path, source_id="no-chapters", title="No Chapters")
    assert any("no_chapter_detected" in w for w in result["warnings"])


def test_build_structured_detects_index_by_heading(tmp_path: Path) -> None:
    doc = DocxDocument()
    doc.add_heading("Capítulo 1", level=1)
    doc.add_paragraph("Conteúdo do capítulo.")
    doc.add_heading("Índice", level=1)
    doc.add_paragraph("Conteúdo..............1")
    doc.add_paragraph("Outro item..............2")
    path = tmp_path / "with_index.docx"
    doc.save(str(path))
    result = build_structured(path, source_id="with-index", title="With Index")
    types = [c["type"] for c in result["children"]]
    assert "index" in types
```

- [ ] **Step 2: Rodar testes e confirmar falha em `build_structured`**

```bash
pytest tests/test_build_docx_structured.py -k "structured" -v
```

Esperado: `ImportError: cannot import name 'build_structured'`

- [ ] **Step 3: Implementar `iter_block_items`, `is_index_node`, `build_structured`**

Adicionar ao final de `scripts/build_docx_structured.py` (antes de qualquer `if __name__`):

```python
# ---------------------------------------------------------------------------
# DOCX iteration helpers
# ---------------------------------------------------------------------------

from docx import Document as DocxDocument
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph as DocxParagraph
from docx.table import Table as DocxTable


def iter_block_items(doc: Any) -> Any:
    """Yield Paragraph and Table objects in document order."""
    for child in doc.element.body:
        if child.tag == qn("w:p"):
            yield DocxParagraph(child, doc)
        elif child.tag == qn("w:tbl"):
            yield DocxTable(child, doc)


_INDEX_HEADING_RE = re.compile(
    r"^(índice|indice|sumário|sumario|conteúdo|conteudo|table of contents)$",
    re.IGNORECASE,
)
_INDEX_LINE_RE = re.compile(r".+\.{2,}\s*\d+\s*$")


def is_index_node(heading: str, child_texts: list[str]) -> bool:
    """Return True if this block looks like a table of contents."""
    if _INDEX_HEADING_RE.match(heading.strip()):
        return True
    if not child_texts:
        return False
    dotted = sum(1 for t in child_texts if _INDEX_LINE_RE.match(t))
    return dotted / len(child_texts) >= 0.60


def _table_to_node(table: Any, page: int | None) -> dict[str, Any]:
    """Convert a python-docx Table to a structured node."""
    rows = [[cell.text.strip() for cell in row.cells] for row in table.rows]
    headers = rows[0] if rows else None
    data_rows = rows[1:] if len(rows) > 1 else []
    return {
        "type": "table",
        "headers": headers,
        "rows": data_rows,
        "page": page,
    }


# ---------------------------------------------------------------------------
# Tree builder
# ---------------------------------------------------------------------------

def build_structured(
    docx_path: Path,
    source_id: str,
    title: str,
) -> dict[str, Any]:
    """Parse a DOCX file and return a structured tree dict.

    The tree has the shape defined in the pipeline spec:
    { version, source, sourceType, file, title, extractedAt, warnings, children }
    """
    from datetime import datetime, timezone

    doc = DocxDocument(str(docx_path))
    warnings: list[str] = []

    # --- Pre-pass: collect all paragraph texts for repeated-pattern detection ---
    all_texts = [p.text for p in doc.paragraphs]
    repeated = detect_repeated_patterns(all_texts, threshold=0.40)

    # --- Walk document in order ---
    # Stack tracks open heading nodes: list of (level, node_dict)
    root_children: list[dict[str, Any]] = []
    frontmatter_node: dict[str, Any] = {"type": "frontmatter", "children": []}
    root_children.append(frontmatter_node)
    in_frontmatter = True
    heading_stack: list[tuple[int, dict[str, Any]]] = []
    page: int | None = 1

    def current_parent() -> dict[str, Any]:
        return heading_stack[-1][1] if heading_stack else frontmatter_node

    def push_heading(level: int, node: dict[str, Any]) -> None:
        # Pop nodes of equal or deeper level
        while heading_stack and heading_stack[-1][0] >= level:
            heading_stack.pop()
        # Attach to current parent
        parent = heading_stack[-1][1] if heading_stack else None
        if parent is None:
            root_children.append(node)
        else:
            parent["children"].append(node)
        heading_stack.append((level, node))

    for block in iter_block_items(doc):
        if isinstance(block, DocxParagraph):
            # Track page breaks
            if qn("w:br") in block._element.xml and 'type="page"' in block._element.xml:
                page = (page or 0) + 1

            text = block.text
            cleaned = clean_paragraph(text, repeated)
            if cleaned is None:
                continue

            level = classify_heading_level(block)
            if level is not None:
                type_map = {1: "chapter", 2: "section", 3: "subsection"}
                node_type = type_map.get(level, "section")
                node: dict[str, Any] = {
                    "type": node_type,
                    "heading": cleaned,
                    "level": level,
                    "page": page,
                    "children": [],
                }
                if in_frontmatter:
                    in_frontmatter = False
                push_heading(level, node)
            else:
                para_node = {"type": "paragraph", "text": cleaned, "page": page}
                current_parent()["children"].append(para_node)

        elif isinstance(block, DocxTable):
            table_node = _table_to_node(block, page)
            current_parent()["children"].append(table_node)

    # --- Post-process: mark index nodes ---
    for node in root_children:
        if node.get("type") in {"chapter", "section", "subsection"}:
            child_texts = [c.get("text", "") for c in node.get("children", []) if c.get("type") == "paragraph"]
            if is_index_node(node.get("heading", ""), child_texts):
                node["type"] = "index"

    # --- Emit warnings ---
    has_chapter = any(c.get("type") == "chapter" for c in root_children)
    if not has_chapter:
        warnings.append(
            "no_chapter_detected: documento sem Heading 1 real; estrutura inferida por heurística"
        )
    if repeated:
        warnings.append(
            f"repeated_patterns_removed: {len(repeated)} padrão(ões) removido(s)"
        )

    return {
        "version": 1,
        "source": source_id,
        "sourceType": "docx",
        "file": docx_path.name,
        "title": title,
        "extractedAt": datetime.now(timezone.utc).isoformat(),
        "warnings": warnings,
        "children": root_children,
    }
```

- [ ] **Step 4: Rodar todos os testes e confirmar que passam**

```bash
pytest tests/test_build_docx_structured.py -v
```

Esperado: todos os testes passam. Se algum falhar, investigar o erro antes de continuar.

---

## Task 4: CLI de `build_docx_structured.py`

**Files:**
- Modify: `scripts/build_docx_structured.py` — adicionar `find_docx`, `load_status`, `save_status`, `process_source`, `main`

Sem novos testes — a CLI é verificada manualmente com `Vantagens.docx` no Step 4.

- [ ] **Step 1: Adicionar funções de CLI ao final de `build_docx_structured.py`**

```python
# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------

import argparse
from datetime import datetime, timezone


def find_docx(source_id: str) -> Path | None:
    """Find a DOCX in BOOKS_DIR whose slugified stem matches source_id."""
    for path in BOOKS_DIR.glob("*.docx"):
        if slugify(path.stem) == source_id:
            return path
    return None


def all_docx_source_ids() -> list[str]:
    """Return slugified source IDs for all DOCX files in BOOKS_DIR."""
    return [slugify(p.stem) for p in sorted(BOOKS_DIR.glob("*.docx"))]


def load_status() -> dict[str, Any]:
    return read_json(STATUS_PATH, {})


def save_status(status: dict[str, Any]) -> None:
    write_json(STATUS_PATH, status)


def process_source(source_id: str, force: bool = False) -> None:
    status = load_status()
    entry = status.get(source_id, {})

    docx_path = find_docx(source_id)
    if docx_path is None:
        print(f"  SKIP {source_id}: DOCX não encontrado em {BOOKS_DIR}")
        return

    # Skip if already processed and not forced
    if not force and entry.get("status") == "ok":
        structured_path = STRUCTURED_DIR / f"{source_id}.json"
        if structured_path.exists():
            docx_mtime = docx_path.stat().st_mtime
            structured_mtime = structured_path.stat().st_mtime
            if structured_mtime >= docx_mtime:
                print(f"  SKIP {source_id}: já processado")
                return

    print(f"  Processing {source_id} ({docx_path.name})...")
    try:
        # Infer title from DOCX filename
        title = docx_path.stem.replace("-", " ").replace("_", " ")
        tree = build_structured(docx_path, source_id=source_id, title=title)

        out_path = STRUCTURED_DIR / f"{source_id}.json"
        write_json(out_path, tree)

        block_count = _count_leaf_blocks(tree)
        status[source_id] = {
            "status": "ok",
            "warnings": tree["warnings"],
            "structuredAt": datetime.now(timezone.utc).isoformat(),
            "blocksAt": None,
            "blockCount": block_count,
            "file": docx_path.name,
        }
        print(f"  OK {source_id}: {block_count} blocos, {len(tree['warnings'])} warnings")
    except Exception as exc:
        status[source_id] = {
            "status": "failed",
            "error": str(exc),
            "structuredAt": None,
            "blocksAt": None,
            "file": docx_path.name,
        }
        print(f"  FAIL {source_id}: {exc}")

    save_status(status)


def _count_leaf_blocks(tree: dict[str, Any]) -> int:
    """Count paragraph + table nodes in the tree (leaves only)."""
    count = 0

    def walk(node: dict[str, Any]) -> None:
        nonlocal count
        if node.get("type") in {"paragraph", "table", "special_block"}:
            count += 1
        for child in node.get("children", []):
            walk(child)

    for child in tree.get("children", []):
        walk(child)
    return count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Parse DOCX files into structured JSON trees."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--source", help="Source ID (slugified DOCX stem, ex: vantagens)")
    group.add_argument("--all", action="store_true", help="Process all DOCX files in Livros/")
    parser.add_argument("--force", action="store_true", help="Reprocess even if already done")
    args = parser.parse_args()

    if args.all:
        ids = all_docx_source_ids()
        print(f"Processing {len(ids)} DOCX file(s)...")
        for source_id in ids:
            process_source(source_id, force=args.force)
    else:
        process_source(args.source, force=args.force)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Rodar os testes existentes para garantir que as adições não quebram nada**

```bash
pytest tests/test_build_docx_structured.py -v
```

Esperado: todos os testes passam.

- [ ] **Step 3: Rodar contra o DOCX piloto**

```bash
cd c:\Projetos\Daemon Trevas\livros\Repositorio\daemon
python scripts/build_docx_structured.py --source vantagens
```

Esperado (exemplo):
```
Processing vantagens (Vantagens.docx)...
OK vantagens: 47 blocos, 1 warnings
```

Ou, se `Vantagens.docx` não tiver Heading 1 real:
```
OK vantagens: 47 blocos, 1 warnings   ← warning: no_chapter_detected
```

- [ ] **Step 4: Inspecionar o arquivo gerado**

```bash
python -c "
import json
from pathlib import Path
d = json.loads(Path('data/structured/vantagens.json').read_text(encoding='utf-8'))
print('version:', d['version'])
print('warnings:', d['warnings'])
print('top-level types:', [c['type'] for c in d['children']])
print('primeiro capítulo:', next((c for c in d['children'] if c['type'] == 'chapter'), {}).get('heading', 'n/a'))
"
```

Verificar que a árvore tem estrutura sensata. Se todos os nós forem `frontmatter`, o DOCX não tem headings styled — anote para tratar depois.

---

## Task 5: Blocks flattener — testes e implementação

**Files:**
- Create: `scripts/build_docx_blocks.py`
- Create: `tests/test_build_docx_blocks.py`

- [ ] **Step 1: Criar `tests/test_build_docx_blocks.py`**

```python
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_docx_blocks import flatten_tree, make_block_id


_SAMPLE_TREE: dict = {
    "version": 1,
    "source": "livro-teste",
    "sourceType": "docx",
    "file": "Livro Teste.docx",
    "title": "Livro Teste",
    "extractedAt": "2026-06-03T00:00:00+00:00",
    "warnings": [],
    "children": [
        {
            "type": "frontmatter",
            "children": [
                {"type": "paragraph", "text": "Copyright 2024", "page": 1},
            ],
        },
        {
            "type": "chapter",
            "heading": "Capítulo 1: Personagens",
            "level": 1,
            "page": 2,
            "children": [
                {
                    "type": "section",
                    "heading": "Exobiólogo",
                    "level": 2,
                    "page": 3,
                    "children": [
                        {"type": "paragraph", "text": "O exobiólogo estuda vida alienígena.", "page": 3},
                        {"type": "table", "headers": ["Perícia", "Nível"], "rows": [["Biologia", "2"]], "page": 4},
                    ],
                }
            ],
        },
        {
            "type": "index",
            "heading": "Índice",
            "level": 1,
            "page": 50,
            "children": [
                {"type": "paragraph", "text": "Personagens..............2", "page": 50},
            ],
        },
    ],
}


def test_make_block_id_format() -> None:
    assert make_block_id("livro-teste", 0) == "livro-teste--0000"
    assert make_block_id("livro-teste", 42) == "livro-teste--0042"
    assert make_block_id("livro-teste", 1000) == "livro-teste--1000"


def test_flatten_tree_produces_list_of_blocks() -> None:
    blocks = flatten_tree(_SAMPLE_TREE)
    assert isinstance(blocks, list)
    assert len(blocks) > 0


def test_flatten_tree_includes_frontmatter_blocks() -> None:
    blocks = flatten_tree(_SAMPLE_TREE)
    frontmatter_blocks = [b for b in blocks if b["type"] == "frontmatter"]
    assert len(frontmatter_blocks) == 1
    assert frontmatter_blocks[0]["text"] == "Copyright 2024"


def test_flatten_tree_includes_index_blocks() -> None:
    blocks = flatten_tree(_SAMPLE_TREE)
    index_blocks = [b for b in blocks if b["type"] == "index"]
    assert len(index_blocks) == 1


def test_flatten_tree_paragraph_has_correct_path() -> None:
    blocks = flatten_tree(_SAMPLE_TREE)
    para = next(b for b in blocks if b.get("text") == "O exobiólogo estuda vida alienígena.")
    assert para["path"] == ["Capítulo 1: Personagens", "Exobiólogo"]


def test_flatten_tree_table_has_correct_path() -> None:
    blocks = flatten_tree(_SAMPLE_TREE)
    table = next(b for b in blocks if b["type"] == "table")
    assert table["path"] == ["Capítulo 1: Personagens", "Exobiólogo"]
    assert table["headers"] == ["Perícia", "Nível"]


def test_flatten_tree_blocks_have_source_fields() -> None:
    blocks = flatten_tree(_SAMPLE_TREE)
    for block in blocks:
        assert "source" in block
        assert block["source"]["book"] == "Livro Teste"
        assert block["source"]["file"] == "Livro Teste.docx"


def test_flatten_tree_all_blocks_have_area_hint_null() -> None:
    blocks = flatten_tree(_SAMPLE_TREE)
    for block in blocks:
        assert "areaHint" in block
        assert block["areaHint"] is None


def test_flatten_tree_block_ids_are_unique() -> None:
    blocks = flatten_tree(_SAMPLE_TREE)
    ids = [b["id"] for b in blocks]
    assert len(ids) == len(set(ids))


def test_flatten_tree_block_ids_use_source_slug() -> None:
    blocks = flatten_tree(_SAMPLE_TREE)
    for block in blocks:
        assert block["id"].startswith("livro-teste--")
```

- [ ] **Step 2: Rodar testes e confirmar falha**

```bash
pytest tests/test_build_docx_blocks.py -v 2>&1 | head -20
```

Esperado: `ImportError: No module named 'build_docx_blocks'`

- [ ] **Step 3: Criar `scripts/build_docx_blocks.py`**

```python
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from common import DATA_DIR, INDEX_DIR, read_json, write_json


STRUCTURED_DIR = DATA_DIR / "structured"
BLOCKS_DIR = DATA_DIR / "blocks"
STATUS_PATH = INDEX_DIR / "structured-status.json"

_LEAF_TYPES = {"paragraph", "table", "special_block"}
_HEADING_TYPES = {"chapter", "section", "subsection"}
_TYPED_PASSTHROUGH = {"frontmatter", "index"}


def make_block_id(source_id: str, index: int) -> str:
    """Return a zero-padded block ID: '{source_id}--{index:04d}'."""
    return f"{source_id}--{index:04d}"


def flatten_tree(tree: dict[str, Any]) -> list[dict[str, Any]]:
    """DFS walk of a structured tree → flat list of blocks.

    Each block has: id, type, path, areaHint, text or headers/rows, source, page.
    Frontmatter and index blocks are included with their type preserved.
    """
    source_id: str = tree["source"]
    title: str = tree["title"]
    file_name: str = tree["file"]
    blocks: list[dict[str, Any]] = []
    counter = 0

    def walk(node: dict[str, Any], path: list[str]) -> None:
        nonlocal counter
        node_type = node.get("type", "")

        if node_type in _HEADING_TYPES:
            new_path = [*path, node["heading"]]
            for child in node.get("children", []):
                walk(child, new_path)

        elif node_type in _TYPED_PASSTHROUGH:
            # Emit each leaf child as a typed block
            for child in node.get("children", []):
                if child.get("type") in _LEAF_TYPES:
                    block = _make_block(child, source_id, title, file_name, counter, path, node_type)
                    blocks.append(block)
                    counter += 1
                else:
                    walk(child, path)

        elif node_type in _LEAF_TYPES:
            block = _make_block(node, source_id, title, file_name, counter, path, node_type)
            blocks.append(block)
            counter += 1

    for child in tree.get("children", []):
        walk(child, [])

    return blocks


def _make_block(
    node: dict[str, Any],
    source_id: str,
    title: str,
    file_name: str,
    index: int,
    path: list[str],
    type_override: str | None = None,
) -> dict[str, Any]:
    block_type = type_override or node.get("type", "paragraph")
    block: dict[str, Any] = {
        "id": make_block_id(source_id, index),
        "type": block_type,
        "path": list(path),
        "areaHint": None,
        "source": {
            "book": title,
            "file": file_name,
            "page": node.get("page"),
        },
    }
    if node.get("type") == "table":
        block["headers"] = node.get("headers")
        block["rows"] = node.get("rows", [])
    else:
        block["text"] = node.get("text", "")
    return block


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def process_source(source_id: str) -> None:
    structured_path = STRUCTURED_DIR / f"{source_id}.json"
    if not structured_path.exists():
        print(f"  SKIP {source_id}: structured JSON não encontrado")
        return

    tree = read_json(structured_path, {})
    if not tree:
        print(f"  SKIP {source_id}: structured JSON vazio")
        return

    blocks = flatten_tree(tree)
    payload = {
        "version": 1,
        "source": source_id,
        "sourceType": tree.get("sourceType", "docx"),
        "blocks": blocks,
    }

    out_path = BLOCKS_DIR / f"{source_id}.json"
    write_json(out_path, payload)

    # Update structured-status.json
    status = read_json(STATUS_PATH, {})
    if source_id in status:
        status[source_id]["blocksAt"] = datetime.now(timezone.utc).isoformat()
        status[source_id]["blockCount"] = len(blocks)
        write_json(STATUS_PATH, status)

    print(f"  OK {source_id}: {len(blocks)} blocks → {out_path.relative_to(out_path.parents[2])}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Flatten structured DOCX trees into block lists.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--source", help="Source ID (ex: vantagens)")
    group.add_argument("--all", action="store_true", help="Process all structured JSONs")
    args = parser.parse_args()

    if args.all:
        paths = sorted(STRUCTURED_DIR.glob("*.json"))
        print(f"Processing {len(paths)} structured file(s)...")
        for path in paths:
            process_source(path.stem)
    else:
        process_source(args.source)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Rodar testes e confirmar que passam**

```bash
pytest tests/test_build_docx_blocks.py -v
```

Esperado: todos os testes passam.

---

## Task 6: Integração — rodar pipeline completo contra Vantagens.docx

**Files:** nenhum modificado — apenas execução e inspeção.

- [ ] **Step 1: Rodar toda a suite de testes**

```bash
pytest tests/test_build_docx_structured.py tests/test_build_docx_blocks.py -v
```

Esperado: todos os testes passam sem erros.

- [ ] **Step 2: Rodar `build_docx_structured.py` contra o piloto**

```bash
python scripts/build_docx_structured.py --source vantagens
```

Anotar: quantos blocos foram detectados? Há o warning `no_chapter_detected`?

- [ ] **Step 3: Rodar `build_docx_blocks.py` contra o resultado**

```bash
python scripts/build_docx_blocks.py --source vantagens
```

- [ ] **Step 4: Inspecionar os blocks gerados**

```bash
python -c "
import json
from pathlib import Path

b = json.loads(Path('data/blocks/vantagens.json').read_text(encoding='utf-8'))
blocks = b['blocks']
print(f'Total blocks: {len(blocks)}')
print()
# Mostrar primeiros 3
for block in blocks[:3]:
    print(f'  [{block[\"type\"]}] path={block[\"path\"]} page={block[\"source\"][\"page\"]}')
    if 'text' in block:
        print(f'    text: {block[\"text\"][:80]!r}')
    print()
# Mostrar distribuição de tipos
from collections import Counter
types = Counter(b['type'] for b in blocks)
print('Tipos:', dict(types))
"
```

Verificar:
- Blocks têm `path` sensato (não todos com `[]`)
- Textos estão limpos (sem cabeçalhos repetidos, sem hifenização quebrada)
- Tipos distribuídos: maioria `paragraph`, alguns `table`
- Se `path` estiver sempre `[]`, o DOCX não tem headings styled — anotar como `no_chapter_detected` esperado

- [ ] **Step 5: Verificar `structured-status.json`**

```bash
python -c "
import json
from pathlib import Path
s = json.loads(Path('data/index/structured-status.json').read_text(encoding='utf-8'))
import pprint; pprint.pprint(s)
"
```

Esperado: entrada `vantagens` com `status: ok`, `blockCount`, `structuredAt` e `blocksAt` preenchidos.

---

## Self-Review

**Cobertura do spec:**
- ✅ `data/structured/<slug>.json` com campos version, source, sourceType, file, title, extractedAt, warnings, children
- ✅ `data/blocks/<slug>.json` com version, source, sourceType, blocks[]
- ✅ Blocos com id, type, path, areaHint, text/headers/rows, source{book, file, page}
- ✅ `data/index/structured-status.json` atualizado após cada estágio
- ✅ `--source` e `--all` com `--force` em build_docx_structured
- ✅ detect_repeated_patterns com threshold 40%
- ✅ join_hyphenated_lines para hífen antes de minúscula
- ✅ normalize_quotes para aspas tipográficas
- ✅ repair_encoding reutilizando repair_encoding.py
- ✅ Frontmatter = conteúdo antes do primeiro chapter
- ✅ Warning no_chapter_detected quando sem Heading 1
- ✅ Index detectado por heading + padrão de pontinhos
- ✅ Tabelas com headers/rows
- ✅ DFS walk preservando path de headings
- ✅ areaHint: null em todos os blocks (classificação é fase futura)
- ✅ Sem commits (conforme instrução do usuário)

**Fora do escopo (fase futura):**
- `classify_blocks.py` — preenchimento de areaHint
- PDF pipeline
- Frontend reader de data/blocks/
