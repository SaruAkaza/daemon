from __future__ import annotations

import argparse
import re

from common import INDEX_DIR, ROOT, TEXT_DIR, write_json
from text_quality_report import count_weird_chars


REPORT_PATH = INDEX_DIR / "encoding-repair-report.json"
DEFAULT_IDS = [
    "anjos-involucro-e-barreira",
    "archonan",
    "armasmagicas",
    "cobaias",
    "jiraya",
    "marvel",
    "naruto",
    "tradicoes-magicas-vodu",
]

COMMON_WORDS = {
    "a", "ao", "aos", "as", "capitulo", "com", "como", "da", "das", "de",
    "do", "dos", "e", "em", "era", "foi", "jogador", "mago", "mais",
    "medieval", "mestre", "na", "no", "o", "os", "para", "personagem",
    "por", "que", "sistema", "sua", "um", "uma",
}

ACCENT_MAP = {
    "i": "á",
    "j": "à",
    "m": "ã",
    "o": "ç",
    "p": "é",
    "r": "ê",
    "t": "í",
    "y": "ó",
    "{": "ô",
}


def clean_controls(text: str) -> str:
    return "".join(
        char if char in "\n\r\t" or ord(char) >= 32 else " "
        for char in text
    )


def decode_shift_29(text: str) -> str:
    out: list[str] = []
    for char in text:
        code = ord(char)
        if char in "\n\r\t":
            out.append(char)
        elif char == " ":
            out.append(" ")
        elif code == 3:
            out.append(" ")
        elif 32 <= code <= 95:
            out.append(chr(code + 29))
        elif char in ACCENT_MAP:
            out.append(ACCENT_MAP[char])
        elif code < 32:
            out.append(" ")
        else:
            out.append(char)
    return "".join(out)


def score_readability(text: str) -> float:
    words = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ]+", text.casefold())
    if not words:
        return -1000
    common_hits = sum(1 for word in words if word in COMMON_WORDS)
    longish_words = sum(1 for word in words if len(word) >= 3)
    vowels = sum(1 for char in text.casefold() if char in "aeiouáàãâéêíóôõú")
    letters = sum(1 for char in text if char.isalpha())
    vowel_ratio = vowels / max(1, letters)
    uppercase_ratio = sum(1 for char in text if char.isupper()) / max(1, letters)
    controls = sum(1 for char in text if ord(char) < 32 and char not in "\n\r\t")
    replacement = text.count("\ufffd")
    return (
        common_hits * 12
        + longish_words * 2
        + len(text) * 0.01
        + vowel_ratio * 12
        - uppercase_ratio * 8
        - controls * 8
        - replacement * 30
    )


def repair_line(line: str) -> tuple[str, str]:
    if line.startswith("--- page "):
        return line, "marker"

    cleaned = clean_controls(line)
    shifted = decode_shift_29(line)

    original_score = score_readability(cleaned)
    shifted_score = score_readability(shifted)
    has_shift_markers = "\x03" in line or bool(re.search(r"[A-Z0-9&][A-Z0-9\\^_`{}\\[\\]-]{3,}", line))

    if has_shift_markers and shifted_score > original_score + 6:
        return " ".join(shifted.split()), "shift29"
    if cleaned != line:
        return " ".join(cleaned.split()), "controls"
    return line, "unchanged"


def repair_text(text: str) -> tuple[str, dict[str, int]]:
    counts = {"shift29": 0, "controls": 0, "unchanged": 0, "marker": 0}
    repaired_lines = []
    for line in text.splitlines():
        repaired, method = repair_line(line)
        counts[method] += 1
        repaired_lines.append(repaired)
    return "\n".join(repaired_lines).rstrip() + "\n", counts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("ids", nargs="*", default=DEFAULT_IDS)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    report = {"version": 1, "sources": []}
    backup_dir = ROOT / "data" / "work" / "encoding-backup"
    if not args.dry_run:
        backup_dir.mkdir(parents=True, exist_ok=True)

    for source_id in args.ids:
        path = TEXT_DIR / f"{source_id}.txt"
        if not path.exists():
            report["sources"].append({"id": source_id, "status": "missing_text"})
            continue

        before = path.read_text(encoding="utf-8", errors="ignore")
        after, counts = repair_text(before)
        row = {
            "id": source_id,
            "status": "dry_run" if args.dry_run else "written",
            "charsBefore": len(before),
            "charsAfter": len(after),
            "weirdBefore": count_weird_chars(before),
            "weirdAfter": count_weird_chars(after),
            "methods": counts,
        }
        report["sources"].append(row)

        if not args.dry_run:
            backup = backup_dir / f"{source_id}.txt"
            if not backup.exists():
                backup.write_text(before, encoding="utf-8")
            path.write_text(after, encoding="utf-8")

        print(
            f"{source_id}: weird {row['weirdBefore']} -> {row['weirdAfter']} "
            f"methods={counts}"
        )

    write_json(REPORT_PATH, report)
    print(f"Encoding repair report written to {REPORT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
