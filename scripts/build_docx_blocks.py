from __future__ import annotations

import argparse
from datetime import datetime, timezone
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
            for child in node.get("children", []):
                if child.get("type") in _LEAF_TYPES:
                    block = _make_block(child, source_id, title, file_name, counter, path, node_type)
                    blocks.append(block)
                    counter += 1
                else:
                    walk(child, path)

        elif node_type in _LEAF_TYPES:
            block = _make_block(node, source_id, title, file_name, counter, path, None)
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
    type_override: str | None,
) -> dict[str, Any]:
    block_type = type_override if type_override is not None else node.get("type", "paragraph")
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

    status = read_json(STATUS_PATH, {})
    if source_id in status:
        status[source_id]["blocksAt"] = datetime.now(timezone.utc).isoformat()
        status[source_id]["blockCount"] = len(blocks)
        write_json(STATUS_PATH, status)

    print(f"  OK {source_id}: {len(blocks)} blocks -> data/blocks/{source_id}.json")


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
