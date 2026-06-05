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
