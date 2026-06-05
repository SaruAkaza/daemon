from __future__ import annotations

import json
import re
from collections import Counter
from statistics import mean

from audit_good_pages import classify_page, sample, words
from common import INDEX_DIR, ROOT, TEXT_DIR, write_json
from text_quality_report import split_pages


DOCS_DIR = ROOT / "docs" / "reports" / "manual-review"
MANUAL_INDEX = DOCS_DIR / "manual-review-index.md"
REPORT_JSON = INDEX_DIR / "cleanup-sources-page-audit.json"
REPORT_MD = DOCS_DIR / "cleanup-sources-page-audit.md"


def load_sources() -> dict[str, dict]:
    payload = json.loads((INDEX_DIR / "sources.json").read_text(encoding="utf-8"))
    return {row["id"]: row for row in payload["sources"]}


def cleanup_source_ids() -> list[str]:
    ids: list[str] = []
    for report in sorted(DOCS_DIR.glob("manual-review-batch-*.md")):
        text = report.read_text(encoding="utf-8")
        for block in re.split(r"\n###\s+", text):
            heading = re.match(r"(?:\d+\.\s+)?`([^`]+)`", block)
            status = re.search(r"\nStatus:\s*([^\n]+)", block)
            if not heading or not status:
                continue
            if status.group(1).strip().lower().startswith("usable"):
                ids.append(heading.group(1))
    ids.extend(["arcadia-nova-arcadia", "loucura", "supers01"])
    return list(dict.fromkeys(ids))


def difficulty_for_page(status: str, flags: list[str], metrics: dict, page_text: str) -> tuple[str, list[str]]:
    reasons: list[str] = []
    clean = page_text.strip()
    page_words = words(clean)
    sym = metrics["symbolRatio"]
    weird = metrics["weirdChars"]
    max_line = metrics["maxLineLength"]
    chars = metrics["chars"]

    if status == "ok":
        if max_line > 650:
            return "easy", ["long_line_or_docx_join"]
        return "ok", []

    if status == "note":
        reasons.extend(flags)
        return "easy", reasons

    if "symbol_noise" in flags and (sym >= 0.16 or chars > 1500 and sym >= 0.10):
        reasons.append("heavy_symbol_or_ocr_noise")
        return "hard", reasons
    if "low_language_signal" in flags:
        reasons.append("low_language_signal")
        return "hard", reasons
    if "encoding_or_control_noise" in flags and weird >= 25:
        reasons.append("many_encoding_or_control_chars")
        return "hard", reasons
    if chars > 800 and len(page_words) < 40:
        reasons.append("large_page_low_word_signal")
        return "hard", reasons

    if "encoding_or_control_noise" in flags:
        reasons.append("encoding_or_control_noise")
    if "layout_blob_line" in flags:
        reasons.append("layout_blob_line")
    if "low_vowel_ratio" in flags:
        reasons.append("table_or_stat_block_language_signal")
    if "symbol_noise" in flags:
        reasons.append("symbol_noise")
    if not reasons:
        reasons.extend(flags or ["manual_check"])
    return "medium", reasons


def source_difficulty(page_rows: list[dict], page_count: int) -> str:
    hard = sum(1 for row in page_rows if row["difficulty"] == "hard")
    medium = sum(1 for row in page_rows if row["difficulty"] == "medium")
    easy = sum(1 for row in page_rows if row["difficulty"] == "easy")
    if hard:
        return "hard"
    if medium >= 8 or medium / max(1, page_count) >= 0.18:
        return "hard"
    if medium:
        return "medium"
    if easy:
        return "easy"
    return "ok"


def summarize_pages(rows: list[dict], difficulty: str, limit: int = 50) -> str:
    pages = [row["page"] for row in rows if row["difficulty"] == difficulty]
    if not pages:
        return "-"
    rendered = ", ".join(str(page) for page in pages[:limit])
    if len(pages) > limit:
        rendered += f", ... (+{len(pages) - limit})"
    return rendered


def suggested_actions(row: dict) -> list[str]:
    reasons = Counter(reason for page in row["pageResults"] for reason in page["reasons"])
    actions: list[str] = []
    if reasons["heavy_symbol_or_ocr_noise"] or reasons["low_language_signal"] or reasons["many_encoding_or_control_chars"]:
        actions.append("compare with source PDF/OCR or re-extract affected pages")
    if reasons["encoding_or_control_noise"]:
        actions.append("run targeted encoding/control-character cleanup")
    if reasons["layout_blob_line"] or reasons["long_line_or_docx_join"]:
        actions.append("split long DOCX/layout lines into entries")
    if reasons["table_or_stat_block"] or reasons["table_or_stat_block_language_signal"]:
        actions.append("normalize tables/stat blocks before entity extraction")
    if reasons["repeated_terms_or_stat_block"]:
        actions.append("treat repeated mechanical/stat labels as structured data")
    if reasons["empty_page"] or reasons["tiny_page"] or reasons["very_short_or_page_number"]:
        actions.append("drop or mark cover/page-number-only pages")
    if not actions:
        actions.append("manual spot check before final extraction")
    return actions


def main() -> None:
    sources = load_sources()
    ids = cleanup_source_ids()
    results = []
    summary = {
        "usableSources": len(ids),
        "pagesChecked": 0,
        "sourcesOkAfterPageAudit": 0,
        "sourcesEasy": 0,
        "sourcesMedium": 0,
        "sourcesHard": 0,
        "okPages": 0,
        "easyPages": 0,
        "mediumPages": 0,
        "hardPages": 0,
        "missingTextFiles": 0,
    }

    for source_id in ids:
        source = sources.get(source_id, {"id": source_id, "title": source_id, "pageCount": None})
        path = TEXT_DIR / f"{source_id}.txt"
        if not path.exists():
            summary["missingTextFiles"] += 1
            results.append({
                "id": source_id,
                "title": source["title"],
                "difficulty": "hard",
                "pages": 0,
                "pageResults": [],
                "actions": ["missing extracted text file"],
            })
            summary["sourcesHard"] += 1
            continue

        text = path.read_text(encoding="utf-8", errors="ignore")
        pages = split_pages(text)
        page_count = int(source.get("pageCount") or max(pages.keys(), default=1))
        page_rows = []
        for page in range(1, page_count + 1):
            page_text = pages.get(page, "")
            status, flags, metrics = classify_page(page_text)
            difficulty, reasons = difficulty_for_page(status, flags, metrics, page_text)
            summary["pagesChecked"] += 1
            summary[f"{difficulty}Pages"] += 1
            page_rows.append({
                "page": page,
                "status": status,
                "difficulty": difficulty,
                "flags": flags,
                "reasons": reasons,
                **metrics,
                "sample": sample(page_text) if difficulty != "ok" else "",
            })

        difficulty = source_difficulty(page_rows, page_count)
        summary_key = {
            "ok": "sourcesOkAfterPageAudit",
            "easy": "sourcesEasy",
            "medium": "sourcesMedium",
            "hard": "sourcesHard",
        }[difficulty]
        summary[summary_key] += 1
        row = {
            "id": source_id,
            "title": source["title"],
            "pages": page_count,
            "difficulty": difficulty,
            "affectedPages": sum(1 for page in page_rows if page["difficulty"] != "ok"),
            "hardPages": sum(1 for page in page_rows if page["difficulty"] == "hard"),
            "mediumPages": sum(1 for page in page_rows if page["difficulty"] == "medium"),
            "easyPages": sum(1 for page in page_rows if page["difficulty"] == "easy"),
            "avgCharsPerPage": round(mean([page["chars"] for page in page_rows]), 2) if page_rows else 0,
            "pageResults": page_rows,
        }
        row["actions"] = suggested_actions(row)
        results.append(row)

    difficulty_order = {"hard": 0, "medium": 1, "easy": 2, "ok": 3}
    results.sort(key=lambda row: (difficulty_order[row["difficulty"]], -row["affectedPages"], row["id"]))
    write_json(REPORT_JSON, {"version": 1, "summary": summary, "sources": results})
    write_markdown(summary, results)
    print(f"Cleanup page audit JSON written to {REPORT_JSON}")
    print(f"Markdown report written to {REPORT_MD}")
    print(summary)
    for row in results:
        if row["difficulty"] != "ok":
            print(
                f"{row['difficulty']:6} {row['id']} affected={row['affectedPages']} "
                f"hard={row['hardPages']} medium={row['mediumPages']} easy={row['easyPages']}"
            )


def write_markdown(summary: dict, results: list[dict]) -> None:
    lines = [
        "# Cleanup Sources Page Audit",
        "",
        "Page-by-page audit for sources explicitly marked as usable, plus good-source items demoted during the final page audit.",
        "",
        "## Summary",
        "",
        f"- Usable/verification sources audited: {summary['usableSources']}",
        f"- Pages checked: {summary['pagesChecked']}",
        f"- Sources ok after page audit: {summary['sourcesOkAfterPageAudit']}",
        f"- Easy sources: {summary['sourcesEasy']}",
        f"- Medium sources: {summary['sourcesMedium']}",
        f"- Hard sources: {summary['sourcesHard']}",
        f"- Ok pages: {summary['okPages']}",
        f"- Easy pages: {summary['easyPages']}",
        f"- Medium pages: {summary['mediumPages']}",
        f"- Hard pages: {summary['hardPages']}",
        "",
        "## Difficulty Rules",
        "",
        "- Easy: page-number/covers, note-only pages, repeated RPG stat labels, simple table/stat-block normalization, or long DOCX lines that remain coherent.",
        "- Medium: localized encoding/control noise, layout blobs, dense table text, or pages that need manual spot correction but still preserve content.",
        "- Hard: heavy OCR/symbol noise, low language signal, many control characters, or enough affected pages to require source comparison/re-extraction.",
        "",
    ]

    for difficulty, title in [("hard", "Hard"), ("medium", "Medium"), ("easy", "Easy"), ("ok", "Ok After Audit")]:
        group = [row for row in results if row["difficulty"] == difficulty]
        lines += [f"## {title}", ""]
        if not group:
            lines.append("None.")
            lines.append("")
            continue
        for row in group:
            lines += [
                f"### `{row['id']}`",
                "",
                f"- Title: {row['title']}",
                f"- Pages: {row['pages']}",
                f"- Affected pages: {row['affectedPages']}",
                f"- Hard pages: {summarize_pages(row['pageResults'], 'hard')}",
                f"- Medium pages: {summarize_pages(row['pageResults'], 'medium')}",
                f"- Easy pages: {summarize_pages(row['pageResults'], 'easy')}",
                f"- Suggested actions: {'; '.join(row['actions'])}",
                "",
            ]
            for page in [p for p in row["pageResults"] if p["difficulty"] != "ok"][:6]:
                lines.append(
                    f"  - p. {page['page']} [{page['difficulty']}]: "
                    f"{', '.join(page['reasons'])} - {page['sample']}"
                )
            lines.append("")

    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
