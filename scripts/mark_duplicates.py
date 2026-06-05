from __future__ import annotations

import argparse

from common import INDEX_DIR, ROOT, read_json, write_json


BOOKS_META_DIR = ROOT / "data" / "books"
DUPLICATES_PATH = INDEX_DIR / "duplicates.json"
SOURCES_PATH = INDEX_DIR / "sources.json"


def update_source_entities(duplicate_id: str, canonical_id: str) -> None:
    path = ROOT / "data" / "entities" / "source.json"
    entities = read_json(path, [])
    for entity in entities:
        if entity.get("id") == duplicate_id:
            entity["duplicateOf"] = canonical_id
            entity["entries"] = [
                f"Fonte duplicada/variante de {canonical_id}.",
                "Arquivo preservado no acervo, mas o conteudo canonico deve ser lido na fonte principal.",
            ]
            entity["tags"] = sorted(set(entity.get("tags", []) + ["duplicate"]))
            entity["extractionMethod"] = "duplicate-pointer"
    write_json(path, entities)


def mark_duplicate(duplicate_id: str, canonical_id: str, reason: str) -> None:
    duplicate_path = BOOKS_META_DIR / f"{duplicate_id}.json"
    canonical_path = BOOKS_META_DIR / f"{canonical_id}.json"
    if not duplicate_path.exists():
        raise FileNotFoundError(duplicate_path)
    if not canonical_path.exists():
        raise FileNotFoundError(canonical_path)

    duplicate = read_json(duplicate_path, {})
    canonical = read_json(canonical_path, {})
    duplicate["status"] = "duplicate-of"
    duplicate["duplicateOf"] = canonical_id
    duplicate["duplicateReason"] = reason
    duplicate["primaryCategories"] = ["source"]
    duplicate["parts"] = [
        {
            "id": f"{duplicate_id}-duplicate-pointer",
            "name": f"Duplicado de {canonical.get('title', canonical_id)}",
            "category": "source",
            "pages": [[1, duplicate.get("pages", 1)]] if duplicate.get("pages", 1) > 1 else [1],
            "summary": f"Variante duplicada de {canonical.get('title', canonical_id)}. Use {canonical_id} como fonte canonica para categorizacao.",
            "entityRefs": [canonical_id],
        }
    ]
    write_json(duplicate_path, duplicate)

    duplicates = read_json(DUPLICATES_PATH, {"version": 1, "duplicates": []})
    rows = [row for row in duplicates["duplicates"] if row["duplicate"] != duplicate_id]
    rows.append({"duplicate": duplicate_id, "canonical": canonical_id, "reason": reason})
    duplicates["duplicates"] = sorted(rows, key=lambda row: row["duplicate"])
    write_json(DUPLICATES_PATH, duplicates)

    index = read_json(SOURCES_PATH, {"sources": []})
    for source in index["sources"]:
        if source["id"] == duplicate_id:
            source["duplicateOf"] = canonical_id
            source["duplicateReason"] = reason
    write_json(SOURCES_PATH, index)
    update_source_entities(duplicate_id, canonical_id)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pairs", nargs="+", help="duplicate=canonical")
    parser.add_argument("--reason", default="variant/duplicate file")
    args = parser.parse_args()

    for pair in args.pairs:
        duplicate_id, canonical_id = pair.split("=", 1)
        mark_duplicate(duplicate_id, canonical_id, args.reason)
        print(f"marked {duplicate_id} duplicate of {canonical_id}")


if __name__ == "__main__":
    main()
