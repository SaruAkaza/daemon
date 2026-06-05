from __future__ import annotations

import json
import re
from collections import Counter
from statistics import mean

from common import INDEX_DIR, ROOT, TEXT_DIR, write_json
from text_quality_report import split_pages


DOCS_DIR = ROOT / "docs" / "reports" / "manual-review"
REPORT_JSON = INDEX_DIR / "good-sources-page-coherence.json"
REPORT_MD = DOCS_DIR / "good-sources-page-coherence.md"

MOJIBAKE_MARKERS = ["Ãƒ", "Ã‚", "Ã¢â‚¬", "ï¿½", "\ufffd", "Ã", "Ã°", "Ã¾", "Ã½"]
COMMON_PT = {
    "a", "ao", "aos", "as", "com", "como", "da", "das", "de", "do", "dos",
    "e", "em", "entre", "mais", "mas", "na", "nas", "no", "nos", "o", "os",
    "ou", "para", "por", "que", "se", "sem", "sua", "suas", "seu", "seus",
    "um", "uma", "personagem", "personagens", "sistema", "daemon", "mestre",
    "jogador", "jogadores", "teste", "pontos", "poder", "magia", "dano",
}
ALLOWED_SYMBOLS = ".,;:!?()[]{}<>/%+-ºª'\"“”‘’•·–—_#@&*=|\\/"


def load_sources() -> dict[str, dict]:
    payload = json.loads((INDEX_DIR / "sources.json").read_text(encoding="utf-8"))
    return {row["id"]: row for row in payload["sources"]}


def good_source_ids() -> list[str]:
    ids: list[str] = []
    for report in sorted(DOCS_DIR.glob("manual-review-batch-*.md")):
        text = report.read_text(encoding="utf-8")
        for block in re.split(r"\n###\s+", text):
            heading = re.match(r"(?:\d+\.\s+)?`([^`]+)`", block)
            status = re.search(r"\nStatus:\s*([^\n]+)", block)
            if not heading or not status:
                continue
            if status.group(1).strip().lower().startswith("ok"):
                ids.append(heading.group(1))
    return ids


def words(text: str) -> list[str]:
    return re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9]+", text)


def weird_count(text: str) -> int:
    marker_hits = sum(text.count(marker) for marker in MOJIBAKE_MARKERS)
    control_hits = sum(1 for char in text if ord(char) < 32 and char not in "\n\r\t")
    return marker_hits + control_hits


def symbol_ratio(text: str) -> float:
    stripped = text.strip()
    if not stripped:
        return 0
    symbols = sum(
        1
        for char in stripped
        if not char.isalnum() and not char.isspace() and char not in ALLOWED_SYMBOLS
    )
    return symbols / len(stripped)


def vowel_ratio(text_words: list[str]) -> float:
    letters = "".join(char for word in text_words for char in word if char.isalpha())
    if not letters:
        return 0
    vowels = sum(1 for char in letters.casefold() if char in "aeiouáàãâéêíóôõúü")
    return vowels / len(letters)


def common_word_ratio(text_words: list[str]) -> float:
    alpha = [word.casefold() for word in text_words if any(char.isalpha() for char in word)]
    if not alpha:
        return 0
    return sum(1 for word in alpha if word in COMMON_PT) / len(alpha)


def repeated_token_ratio(text_words: list[str]) -> float:
    alpha = [word.casefold() for word in text_words if any(char.isalpha() for char in word)]
    if len(alpha) < 40:
        return 0
    counts = Counter(alpha)
    repeated = sum(count for count in counts.values() if count >= 8)
    return repeated / len(alpha)


def sample(text: str) -> str:
    lines = [" ".join(line.split()) for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    lines.sort(
        key=lambda line: (
            weird_count(line) * 4
            + symbol_ratio(line) * 80
            + (12 if len(line) > 650 else 0)
            + (8 if len(words(line)) <= 2 else 0)
        ),
        reverse=True,
    )
    return lines[0][:260]


def classify_page(text: str) -> tuple[str, list[str], dict]:
    clean = text.strip()
    text_words = words(clean)
    line_lengths = [len(line) for line in clean.splitlines() if line.strip()]
    metrics = {
        "chars": len(clean),
        "words": len(text_words),
        "digitRatio": round(sum(1 for char in clean if char.isdigit()) / max(1, len(clean)), 6),
        "weirdChars": weird_count(clean),
        "symbolRatio": round(symbol_ratio(clean), 6),
        "vowelRatio": round(vowel_ratio(text_words), 6),
        "commonWordRatio": round(common_word_ratio(text_words), 6),
        "repeatedTokenRatio": round(repeated_token_ratio(text_words), 6),
        "maxLineLength": max(line_lengths, default=0),
    }
    flags: list[str] = []
    status = "ok"

    if not clean:
        return "note", ["empty_page"], metrics
    if metrics["chars"] < 25:
        return "note", ["tiny_page"], metrics
    if metrics["words"] <= 3 and metrics["chars"] < 80:
        return "note", ["very_short_or_page_number"], metrics

    if metrics["weirdChars"] >= 5 or (metrics["weirdChars"] >= 2 and metrics["chars"] < 500):
        flags.append("encoding_or_control_noise")
    if metrics["symbolRatio"] > 0.08 and metrics["chars"] > 120:
        flags.append("symbol_noise")
    if metrics["maxLineLength"] > 900:
        flags.append("layout_blob_line")
    if metrics["vowelRatio"] < 0.22 and metrics["words"] > 50 and metrics["digitRatio"] < 0.28:
        flags.append("low_vowel_ratio")
    if metrics["commonWordRatio"] < 0.015 and metrics["words"] > 120 and metrics["symbolRatio"] > 0.035:
        flags.append("low_language_signal")
    note_flags: list[str] = []
    if metrics["repeatedTokenRatio"] > 0.32:
        note_flags.append("repeated_terms_or_stat_block")
    if metrics["digitRatio"] >= 0.28 and metrics["words"] > 50:
        note_flags.append("table_or_stat_block")

    if flags:
        status = "review"
        return status, flags, metrics
    if note_flags:
        return "note", note_flags, metrics
    return status, flags, metrics


def main() -> None:
    sources_by_id = load_sources()
    ids = good_source_ids()
    results = []
    summary = {
        "goodSourcesExpected": 183,
        "goodSourcesFound": len(ids),
        "sourcesPassed": 0,
        "sourcesWithNotesOnly": 0,
        "sourcesWithReviewPages": 0,
        "totalPagesChecked": 0,
        "okPages": 0,
        "notePages": 0,
        "reviewPages": 0,
        "missingTextFiles": 0,
    }

    for source_id in ids:
        source = sources_by_id[source_id]
        path = TEXT_DIR / f"{source_id}.txt"
        if not path.exists():
            summary["missingTextFiles"] += 1
            results.append({
                "id": source_id,
                "title": source["title"],
                "status": "missing_text_file",
                "pages": [],
            })
            continue

        text = path.read_text(encoding="utf-8", errors="ignore")
        pages = split_pages(text)
        page_count = int(source.get("pageCount") or max(pages.keys(), default=1))
        page_results = []
        source_status = "ok"
        for page in range(1, page_count + 1):
            page_text = pages.get(page, "")
            status, flags, metrics = classify_page(page_text)
            summary["totalPagesChecked"] += 1
            summary[f"{status}Pages"] += 1
            if status == "review":
                source_status = "review"
            elif status == "note" and source_status == "ok":
                source_status = "notes_only"
            page_results.append({
                "page": page,
                "status": status,
                "flags": flags,
                **metrics,
                "sample": sample(page_text) if status != "ok" else "",
            })

        if source_status == "review":
            summary["sourcesWithReviewPages"] += 1
        elif source_status == "notes_only":
            summary["sourcesWithNotesOnly"] += 1
        else:
            summary["sourcesPassed"] += 1

        review_pages = [row for row in page_results if row["status"] == "review"]
        note_pages = [row for row in page_results if row["status"] == "note"]
        results.append({
            "id": source_id,
            "title": source["title"],
            "pages": page_count,
            "status": source_status,
            "reviewPageCount": len(review_pages),
            "notePageCount": len(note_pages),
            "avgCharsPerPage": round(mean([row["chars"] for row in page_results]), 2) if page_results else 0,
            "pageResults": page_results,
        })

    write_json(REPORT_JSON, {"version": 1, "summary": summary, "sources": results})
    write_markdown(summary, results)
    print(f"Good source page coherence JSON written to {REPORT_JSON}")
    print(f"Markdown report written to {REPORT_MD}")
    print(summary)
    for row in results:
        if row["status"] == "review":
            pages = [str(page["page"]) for page in row["pageResults"] if page["status"] == "review"][:20]
            print(f"review {row['id']} pages={','.join(pages)}")


def write_markdown(summary: dict, results: list[dict]) -> None:
    lines = [
        "# Good Sources Page Coherence Final Pass",
        "",
        "Final page-by-page coherence audit for sources previously marked as good enough to continue.",
        "",
        "## Summary",
        "",
        f"- Good sources expected from batch totals: {summary['goodSourcesExpected']}",
        f"- Good sources found from reports: {summary['goodSourcesFound']}",
        f"- Pages checked: {summary['totalPagesChecked']}",
        f"- Sources passed with all pages ok: {summary['sourcesPassed']}",
        f"- Sources with only note-level pages: {summary['sourcesWithNotesOnly']}",
        f"- Sources with review-level pages: {summary['sourcesWithReviewPages']}",
        f"- Ok pages: {summary['okPages']}",
        f"- Note pages: {summary['notePages']}",
        f"- Review pages: {summary['reviewPages']}",
        "",
        "Note-level pages are usually covers, page numbers, intentionally blank pages, or very short sheet fragments. Review-level pages contain stronger signals of encoding, OCR, symbol, or layout problems.",
        "",
    ]

    review_sources = [row for row in results if row["status"] == "review"]
    note_sources = [row for row in results if row["status"] == "notes_only"]

    lines += ["## Sources With Review-Level Pages", ""]
    if not review_sources:
        lines.append("None.")
    for row in review_sources:
        review_pages = [page for page in row["pageResults"] if page["status"] == "review"]
        pages = ", ".join(str(page["page"]) for page in review_pages[:40])
        if len(review_pages) > 40:
            pages += f", ... (+{len(review_pages) - 40})"
        flags = sorted({flag for page in review_pages for flag in page["flags"]})
        lines += [
            f"### `{row['id']}`",
            "",
            f"- Title: {row['title']}",
            f"- Review pages: {len(review_pages)} / {row['pages']}",
            f"- Pages: {pages}",
            f"- Flags: {', '.join(flags)}",
            "",
        ]
        for page in review_pages[:5]:
            lines.append(f"  - p. {page['page']}: `{', '.join(page['flags'])}` - {page['sample']}")
        lines.append("")

    lines += ["## Sources With Only Note-Level Pages", ""]
    if not note_sources:
        lines.append("None.")
    for row in note_sources:
        note_pages = [page for page in row["pageResults"] if page["status"] == "note"]
        pages = ", ".join(str(page["page"]) for page in note_pages[:40])
        if len(note_pages) > 40:
            pages += f", ... (+{len(note_pages) - 40})"
        lines.append(f"- `{row['id']}`: {len(note_pages)} note page(s): {pages}")
    lines.append("")

    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
