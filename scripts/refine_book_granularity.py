from __future__ import annotations

import argparse

from common import ROOT, TEXT_DIR, infer_category_hints, read_json, slugify, write_json
from process_book_batch import page_map, repair_text, summarize


BOOKS_META_DIR = ROOT / "data" / "books"


def expand_pages(pages: list[int | list[int]]) -> list[int]:
    result: list[int] = []
    for item in pages:
        if isinstance(item, int):
            result.append(item)
        elif isinstance(item, list) and len(item) == 2:
            result.extend(range(item[0], item[1] + 1))
    return result


def page_value(start: int, end: int) -> list[int | list[int]]:
    return [start] if start == end else [[start, end]]


def refine(book_id: str, max_span: int) -> bool:
    meta_path = BOOKS_META_DIR / f"{book_id}.json"
    text_path = TEXT_DIR / f"{book_id}.txt"
    payload = read_json(meta_path, {})
    text = repair_text(text_path.read_text(encoding="utf-8", errors="ignore"))
    pages = page_map(text)

    changed = False
    refined_parts: list[dict] = []
    for part in payload.get("parts", []):
        part_pages = expand_pages(part.get("pages", []))
        if len(part_pages) <= max_span:
            refined_parts.append(part)
            continue

        changed = True
        for offset, start in enumerate(range(part_pages[0], part_pages[-1] + 1, max_span), start=1):
            end = min(start + max_span - 1, part_pages[-1])
            chunk_texts = [pages.get(page, "") for page in range(start, end + 1)]
            name = f"{part['name']} ({start}-{end})"
            category = infer_category_hints(f"{payload['title']} {name} {' '.join(chunk_texts)[:5000]}")[0]
            refined_parts.append(
                {
                    "id": slugify(f"{part['id']}-{offset}"),
                    "name": name,
                    "category": category,
                    "pages": page_value(start, end),
                    "summary": summarize(chunk_texts),
                    "entityRefs": part.get("entityRefs", []),
                }
            )

    if changed:
        payload["parts"] = refined_parts
        payload["status"] = "full-read-auto-pass-1-refined"
        write_json(meta_path, payload)
    return changed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("book_ids", nargs="+")
    parser.add_argument("--max-span", type=int, default=10)
    args = parser.parse_args()

    for book_id in args.book_ids:
        changed = refine(book_id, args.max_span)
        print(("refined " if changed else "unchanged ") + book_id)


if __name__ == "__main__":
    main()
