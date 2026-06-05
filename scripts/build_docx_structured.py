from __future__ import annotations

import argparse
import re
from collections import Counter
from pathlib import Path
from typing import Any

from common import BOOKS_DIR, DATA_DIR, INDEX_DIR, slugify, read_json, write_json
from repair_encoding import clean_controls, decode_shift_29, score_readability

from docx import Document as DocxDocument
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph as DocxParagraph
from docx.table import Table as DocxTable


STRUCTURED_DIR = DATA_DIR / "structured"
BLOCKS_DIR = DATA_DIR / "blocks"
STATUS_PATH = INDEX_DIR / "structured-status.json"


# ---------------------------------------------------------------------------
# Cleaning utilities
# ---------------------------------------------------------------------------

def detect_repeated_patterns(texts: list[str], threshold: float = 0.40) -> set[str]:
    """Return short texts that appear in >= threshold fraction of all short texts."""
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
    # Unicode left/right double quotes (U+201C, U+201D)
    text = text.replace(chr(0x201C), '"').replace(chr(0x201D), '"')
    # Unicode left/right single quotes (U+2018, U+2019)
    text = text.replace(chr(0x2018), "'").replace(chr(0x2019), "'")
    # Unicode guillemets (« »)
    text = text.replace(chr(0xAB), '"').replace(chr(0xBB), '"')
    # Additional variants
    text = text.replace(chr(0x201E), '"')  # double low-9 quote
    text = text.replace(chr(0x201F), '"')  # double high-reversed-9 quote
    text = text.replace(chr(0x2039), "'").replace(chr(0x203A), "'")  # single guillemets
    text = text.replace(chr(0x201A), "'")  # single low-9 quote
    text = text.replace(chr(0x201B), "'")  # single high-reversed-9 quote
    return text


def repair_encoding_in_paragraph(text: str) -> str:
    """Apply shift-29 / encoding repair to a single paragraph text."""
    cleaned = clean_controls(text)
    shifted = decode_shift_29(text)
    original_score = score_readability(cleaned)
    shifted_score = score_readability(shifted)
    has_markers = "\x03" in text or bool(
        re.search(r"[A-Z0-9&][A-Z0-9\\^_`{}\\[\\]-]{3,}", text)
    )
    if has_markers and shifted_score > original_score + 6:
        return normalize_whitespace(shifted)
    if cleaned != text:
        return normalize_whitespace(cleaned)
    return text


def clean_paragraph(text: str, repeated: set[str]) -> str | None:
    """Clean a paragraph text. Returns None if the paragraph should be discarded."""
    stripped = text.strip()
    if not stripped:
        return None
    if stripped in repeated:
        return None
    if re.fullmatch(r"\d+", stripped):
        return None
    # Check if text has no alphanumeric characters (only symbols/punctuation)
    if not re.search(r"[a-zA-Z0-9]", stripped):
        return None

    result = repair_encoding_in_paragraph(stripped)
    result = join_hyphenated_lines(result)
    result = normalize_quotes(result)
    result = normalize_whitespace(result)
    return result if result else None


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

    if _CHAPTER_PATTERN.match(text):
        return 1

    if len(text) <= 80 and not text.endswith("."):
        is_bold = any(run.bold for run in para.runs if run.bold is not None)
        if is_bold:
            return 2

    return None


# ---------------------------------------------------------------------------
# DOCX iteration helpers
# ---------------------------------------------------------------------------

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
    """Parse a DOCX file and return a structured tree dict."""
    from datetime import datetime, timezone

    doc = DocxDocument(str(docx_path))
    warnings: list[str] = []

    all_texts = [p.text for p in doc.paragraphs]
    repeated = detect_repeated_patterns(all_texts, threshold=0.40)

    root_children: list[dict[str, Any]] = []
    frontmatter_node: dict[str, Any] = {"type": "frontmatter", "children": []}
    root_children.append(frontmatter_node)
    in_frontmatter = True
    heading_stack: list[tuple[int, dict[str, Any]]] = []
    page: int | None = 1

    def current_parent() -> dict[str, Any]:
        return heading_stack[-1][1] if heading_stack else frontmatter_node

    def push_heading(level: int, node: dict[str, Any]) -> None:
        while heading_stack and heading_stack[-1][0] >= level:
            heading_stack.pop()
        parent = heading_stack[-1][1] if heading_stack else None
        if parent is None:
            root_children.append(node)
        else:
            parent["children"].append(node)
        heading_stack.append((level, node))

    for block in iter_block_items(doc):
        if isinstance(block, DocxParagraph):
            if 'type="page"' in block._element.xml or "w:type=\"page\"" in block._element.xml:
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

    for node in root_children:
        if node.get("type") in {"chapter", "section", "subsection"}:
            child_texts = [c.get("text", "") for c in node.get("children", []) if c.get("type") == "paragraph"]
            if is_index_node(node.get("heading", ""), child_texts):
                node["type"] = "index"

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


# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------


def find_docx(source_id: str) -> Path | None:
    """Find a DOCX in BOOKS_DIR whose slugified stem matches source_id."""
    for path in BOOKS_DIR.glob("*.docx"):
        if slugify(path.stem) == source_id:
            return path
    return None


def all_docx_source_ids() -> list[str]:
    """Return slugified source IDs for all DOCX files in BOOKS_DIR."""
    return [slugify(p.stem) for p in sorted(BOOKS_DIR.glob("*.docx"))]


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


def process_source(source_id: str, force: bool = False) -> None:
    from datetime import datetime, timezone

    status = read_json(STATUS_PATH, {})
    entry = status.get(source_id, {})

    docx_path = find_docx(source_id)
    if docx_path is None:
        print(f"  SKIP {source_id}: DOCX não encontrado em {BOOKS_DIR}")
        return

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
            "file": docx_path.name if docx_path else None,
        }
        print(f"  FAIL {source_id}: {exc}")

    write_json(STATUS_PATH, status)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Parse DOCX files into structured JSON trees."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--source", help="Source ID (ex: vantagens)")
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
