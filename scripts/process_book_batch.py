from __future__ import annotations

import argparse
import re

from common import ROOT, TEXT_DIR, infer_category_hints, read_json, slugify, write_json


BOOKS_META_DIR = ROOT / "data" / "books"
SOURCES_PATH = ROOT / "data" / "index" / "sources.json"


def repair_text(text: str) -> str:
    try:
        return text.encode("latin1").decode("utf-8")
    except UnicodeError:
        return text


def page_map(text: str) -> dict[int, str]:
    pages: dict[int, str] = {}
    for match in re.finditer(r"--- page (\d+) ---", text):
        page = int(match.group(1))
        start = match.end()
        next_match = re.search(r"--- page \d+ ---", text[start:])
        end = start + next_match.start() if next_match else len(text)
        pages[page] = text[start:end].strip()
    if not pages and text.strip():
        pages[1] = text.strip()
    return pages


def clean_line(line: str) -> str:
    return " ".join(line.replace("\ufb01", "fi").replace("\ufb02", "fl").strip().split())


def candidate_heading(page_text: str, fallback: str) -> str:
    candidates: list[str] = []
    for raw in page_text.splitlines()[:35]:
        line = clean_line(raw)
        if not line or line.isdigit() or len(line) > 90:
            continue
        alpha = sum(char.isalpha() for char in line)
        if alpha < 3:
            continue
        if line.isupper() or line.endswith(":") or len(line.split()) <= 7:
            candidates.append(line.strip(":"))

    for candidate in candidates:
        normalized = candidate.casefold()
        if normalized not in {"sumario", "indice", "contents"}:
            return candidate
    return candidates[0] if candidates else fallback


def summarize(page_texts: list[str]) -> str:
    text = clean_line(" ".join(page_texts))
    text = re.sub(r"\s+", " ", text)
    if not text:
        return "Pagina sem texto extraido relevante."
    return text[:360].rstrip() + ("..." if len(text) > 360 else "")


def is_new_section(page: int, heading: str, previous_heading: str | None, page_text: str) -> bool:
    if page == 1:
        return True
    if not heading or heading == previous_heading:
        return False
    if re.search(r"(cap[ií]tulo|parte|book|indice|sum[aá]rio)", heading, re.I):
        return True
    if heading.isupper() and len(heading.split()) <= 6:
        return True
    first_lines = [clean_line(line) for line in page_text.splitlines()[:8] if clean_line(line)]
    return bool(first_lines and heading == first_lines[0] and len(heading.split()) <= 5)


def build_book(source: dict) -> dict:
    text_path = TEXT_DIR / f"{source['id']}.txt"
    text = repair_text(text_path.read_text(encoding="utf-8", errors="ignore"))
    pages = page_map(text)
    page_count = int(source.get("pageCount") or (max(pages) if pages else 1))

    sections: list[dict] = []
    current: dict | None = None
    previous_heading: str | None = None

    for page in range(1, page_count + 1):
        page_text = pages.get(page, "")
        fallback = "Pagina inicial" if page == 1 else f"Pagina {page}"
        heading = candidate_heading(page_text, fallback)

        if current is None or is_new_section(page, heading, previous_heading, page_text):
            if current is not None:
                sections.append(current)
            current = {
                "start": page,
                "end": page,
                "heading": heading,
                "texts": [page_text],
            }
        else:
            current["end"] = page
            current["texts"].append(page_text)

        previous_heading = heading

    if current is not None:
        sections.append(current)

    parts = []
    for section in sections:
        start = section["start"]
        end = section["end"]
        heading = section["heading"]
        basis = f"{source['title']} {heading} {' '.join(section['texts'])[:5000]}"
        category = infer_category_hints(basis)[0]
        part_id = slugify(f"{source['id']}-{heading}-{start}")
        pages_value: list[int | list[int]]
        pages_value = [start] if start == end else [[start, end]]
        parts.append(
            {
                "id": part_id,
                "name": heading,
                "category": category,
                "pages": pages_value,
                "summary": summarize(section["texts"]),
                "entityRefs": [],
            }
        )

    return {
        "source": source["id"],
        "title": source["title"],
        "status": "full-read-auto-pass-1",
        "pages": page_count,
        "primaryCategories": infer_category_hints(f"{source['title']} {text[:20000]}"),
        "parts": parts,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, help="1-based source index")
    parser.add_argument("--count", type=int)
    parser.add_argument("--ids", nargs="*", help="Explicit source ids to process")
    parser.add_argument("--force", action="store_true", help="Overwrite existing book metadata")
    args = parser.parse_args()

    index = read_json(SOURCES_PATH, {"sources": []})
    if args.ids:
        by_id = {source["id"]: source for source in index["sources"]}
        selected = [by_id[source_id] for source_id in args.ids if source_id in by_id]
    else:
        if args.start is None or args.count is None:
            parser.error("--start and --count are required when --ids is not used")
        selected = index["sources"][args.start - 1 : args.start - 1 + args.count]
    BOOKS_META_DIR.mkdir(parents=True, exist_ok=True)

    for source in selected:
        output = BOOKS_META_DIR / f"{source['id']}.json"
        if output.exists() and not args.force:
            print(f"skip existing {source['id']}")
            continue
        payload = build_book(source)
        write_json(output, payload)
        print(f"wrote {output.relative_to(ROOT)} with {len(payload['parts'])} parts")


if __name__ == "__main__":
    main()
