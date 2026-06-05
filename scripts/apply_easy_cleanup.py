from __future__ import annotations

import re

from common import INDEX_DIR, ROOT, TEXT_DIR, read_json, write_json
from text_quality_report import split_pages


AUDIT_PATH = INDEX_DIR / "cleanup-sources-page-audit.json"
REPORT_PATH = INDEX_DIR / "easy-cleanup-report.json"
BACKUP_DIR = ROOT / "data" / "work" / "easy-cleanup-backup"


def page_marker(page: int, text: str) -> str:
    body = text.strip()
    return f"--- page {page} ---\n{body}".rstrip()


def is_page_number_line(line: str) -> bool:
    clean = line.strip()
    if not clean:
        return False
    return bool(
        re.fullmatch(r"(?:[-_ ]*)\d{1,4}(?:[-_ ]*)", clean)
        or re.fullmatch(r"\d(?:\s+\d){1,4}", clean)
    )


def is_separator_line(line: str) -> bool:
    clean = line.strip()
    if len(clean) < 12:
        return False
    chars = set(clean)
    return chars <= {"_", "-", "=", ".", " "}


def wrap_long_line(line: str, max_chars: int = 650) -> list[str]:
    stripped = line.strip()
    if len(stripped) <= max_chars:
        return [line.rstrip()]

    parts = re.split(r"(?<=[.!?])\s+", stripped)
    if len(parts) == 1:
        parts = re.split(r"(?<=;)\s+", stripped)
    if len(parts) == 1:
        return [stripped]

    lines: list[str] = []
    current = ""
    for part in parts:
        if current and len(current) + len(part) + 1 > max_chars:
            lines.append(current.strip())
            current = part
        else:
            current = f"{current} {part}".strip()
    if current:
        lines.append(current.strip())
    return lines


def clean_easy_page(text: str, reasons: set[str]) -> tuple[str, dict[str, int]]:
    counts = {
        "page_number_lines_removed": 0,
        "separator_lines_removed": 0,
        "long_lines_wrapped": 0,
        "whitespace_normalized": 0,
    }

    lines = []
    for line in text.splitlines():
        if is_page_number_line(line):
            counts["page_number_lines_removed"] += 1
            continue
        if is_separator_line(line):
            counts["separator_lines_removed"] += 1
            continue
        wrapped = wrap_long_line(line)
        if len(wrapped) > 1:
            counts["long_lines_wrapped"] += 1
        lines.extend(wrapped)

    cleaned = "\n".join(lines)
    before = cleaned
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    if cleaned != before:
        counts["whitespace_normalized"] += 1

    return cleaned.strip(), counts


def easy_pages_by_source() -> dict[str, dict[int, set[str]]]:
    audit = read_json(AUDIT_PATH, {"sources": []})
    by_source: dict[str, dict[int, set[str]]] = {}
    for source in audit.get("sources", []):
        source_id = source["id"]
        for page in source.get("pageResults", []):
            if page.get("difficulty") != "easy":
                continue
            by_source.setdefault(source_id, {})[int(page["page"])] = set(page.get("reasons", []))
    return by_source


def main() -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    targets = easy_pages_by_source()
    report = {
        "version": 1,
        "sourcesTouched": 0,
        "easyPagesTargeted": sum(len(pages) for pages in targets.values()),
        "sources": [],
    }

    for source_id, page_reasons in sorted(targets.items()):
        path = TEXT_DIR / f"{source_id}.txt"
        if not path.exists():
            report["sources"].append({"id": source_id, "status": "missing_text"})
            continue

        before = path.read_text(encoding="utf-8", errors="ignore")
        backup = BACKUP_DIR / f"{source_id}.txt"
        if not backup.exists():
            backup.write_text(before, encoding="utf-8")

        pages = split_pages(before)
        changed_pages = []
        totals = {
            "page_number_lines_removed": 0,
            "separator_lines_removed": 0,
            "long_lines_wrapped": 0,
            "whitespace_normalized": 0,
        }

        max_page = max(max(pages.keys(), default=1), max(page_reasons.keys(), default=1))
        for page, reasons in page_reasons.items():
            original = pages.get(page, "")
            cleaned, counts = clean_easy_page(original, reasons)
            if cleaned != original.strip():
                pages[page] = cleaned
                changed_pages.append(page)
                for key, value in counts.items():
                    totals[key] += value

        if changed_pages:
            after = "\n\n".join(page_marker(page, pages.get(page, "")) for page in range(1, max_page + 1))
            path.write_text(after.rstrip() + "\n", encoding="utf-8")
            report["sourcesTouched"] += 1
            status = "written"
        else:
            status = "unchanged"

        report["sources"].append({
            "id": source_id,
            "status": status,
            "easyPagesTargeted": sorted(page_reasons),
            "changedPages": changed_pages,
            "counts": totals,
        })
        print(f"{source_id}: {status} changed={len(changed_pages)} targeted={len(page_reasons)}")

    write_json(REPORT_PATH, report)
    print(f"Easy cleanup report written to {REPORT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
