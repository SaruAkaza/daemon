from __future__ import annotations

import argparse
import difflib
import json
import re
import time
import unicodedata
import zipfile
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree

from common import ROOT, TEXT_DIR, sha256_file, write_json


WORD_DIR = ROOT / "Livros" / "word"
REPORT_PATH = ROOT / "docs" / "reports" / "manual-review" / "word-docx-quality-report.json"
MONITOR_LOG = ROOT / "docs" / "reports" / "manual-review" / "word-docx-quality-monitor.log"

NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
MOJIBAKE_MARKERS = [
    "Ãƒ",
    "Ã‚",
    "Ã¢â‚¬",
    "ï¿½",
    "\ufffd",
    "Ã",
    "Ã°",
    "Ã¾",
    "Ã½",
    "_U00",
    "\x93",
    "\x94",
]
COMMON_PT = {
    "a",
    "ao",
    "aos",
    "as",
    "com",
    "como",
    "da",
    "das",
    "de",
    "do",
    "dos",
    "e",
    "em",
    "entre",
    "mais",
    "mas",
    "na",
    "nas",
    "no",
    "nos",
    "o",
    "os",
    "ou",
    "para",
    "por",
    "que",
    "se",
    "sem",
    "sua",
    "suas",
    "seu",
    "seus",
    "um",
    "uma",
    "personagem",
    "personagens",
    "sistema",
    "daemon",
    "mestre",
    "jogador",
    "jogadores",
    "teste",
    "pontos",
    "poder",
    "magia",
    "dano",
    "classe",
    "kit",
    "atributo",
    "atributos",
    "criaturas",
    "armas",
}

MANUAL_TEXT_ALIASES = {
    "Cabala_OCR_alta_qualidade": "cabala-2.txt",
    "Grimorio_Arkanun_2_01_OCR_alta_qualidade": "grimark201.txt",
    "Grimorio_Arton_1_01_OCR_alta_qualidade": "grimorio101.txt",
    "Metropolis_8p_OCR_alta_qualidade": "metropolis.txt",
    "Metropolis_92p_OCR_alta_qualidade": "metropolis-2.txt",
    "Marvel_RPG_OCR_alta_qualidade": "marvel.txt",
    "Marvel_RPG_7a_Edicao_OCR_alta_qualidade": "marvel-rpg-7o-edicao.txt",
}


def clean_stem(stem: str) -> str:
    value = stem.lower()
    value = re.sub(r"_ocr_(alta_qualidade|parcial|extraido)$", "", value)
    value = re.sub(r"_ocr_.*$", "", value)
    value = value.replace("_", " ")
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")


def extract_docx_text(path: Path) -> tuple[str, int, int]:
    with zipfile.ZipFile(path) as archive:
        root = ElementTree.fromstring(archive.read("word/document.xml"))

    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", NS):
        text = "".join(node.text or "" for node in paragraph.findall(".//w:t", NS)).strip()
        if text:
            paragraphs.append(text)

    return "\n".join(paragraphs), len(paragraphs), len(root.findall(".//w:tbl", NS))


def words(text: str) -> list[str]:
    return re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9]+", text)


def weird_count(text: str) -> int:
    marker_hits = sum(text.count(marker) for marker in MOJIBAKE_MARKERS)
    control_hits = sum(1 for char in text if ord(char) < 32 and char not in "\n\r\t")
    return marker_hits + control_hits


def symbol_ratio(text: str) -> float:
    stripped = text.strip()
    if not stripped:
        return 1.0
    allowed = ".,;:!?()[]{}<>/%+-ºª'\"“”‘’•·–—_#@&*=|\\/~"
    symbol_count = sum(
        1
        for char in stripped
        if not char.isalnum() and not char.isspace() and char not in allowed
    )
    return symbol_count / len(stripped)


def common_word_ratio(text_words: list[str]) -> float:
    alpha = [word.casefold() for word in text_words if any(char.isalpha() for char in word)]
    if not alpha:
        return 0
    return sum(1 for word in alpha if word in COMMON_PT) / len(alpha)


def long_word_ratio(text_words: list[str]) -> float:
    alpha = [word for word in text_words if any(char.isalpha() for char in word)]
    if not alpha:
        return 0
    return sum(1 for word in alpha if len(word) > 28) / len(alpha)


def line_metrics(text: str) -> tuple[int, float, float, str, float]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return 0, 0, 0, "", 0

    worst_score = -1.0
    worst_sample = ""
    bad_lines = 0
    long_lines = 0
    for line in lines:
        clean = " ".join(line.split())
        score = (
            weird_count(clean) * 4
            + symbol_ratio(clean) * 100
            + (20 if len(clean) > 700 else 0)
            + (12 if len(words(clean)) < 4 and len(clean) > 50 else 0)
        )
        if score > 28:
            bad_lines += 1
        if len(clean) > 700:
            long_lines += 1
        if score > worst_score:
            worst_score = score
            worst_sample = clean[:220]

    return (
        len(lines),
        long_lines / len(lines),
        bad_lines / len(lines),
        worst_sample,
        round(worst_score, 3),
    )


def best_text_match(path: Path, text_files: dict[str, Path]) -> Path | None:
    alias = MANUAL_TEXT_ALIASES.get(path.stem)
    if alias:
        candidate = TEXT_DIR / alias
        return candidate if candidate.exists() else None

    doc_stem = clean_stem(path.stem)
    best_score = 0.0
    best_path: Path | None = None
    for stem, text_path in text_files.items():
        text_stem = clean_stem(stem)
        score = difflib.SequenceMatcher(None, doc_stem, text_stem).ratio()
        if doc_stem == text_stem:
            score = 1.0
        elif doc_stem in text_stem or text_stem in doc_stem:
            score = max(score, 0.88 if min(len(doc_stem), len(text_stem)) >= 8 else score)
        if score > best_score:
            best_score = score
            best_path = text_path

    return best_path if best_score >= 0.86 else None


def load_previous_documents() -> dict[str, dict]:
    if not REPORT_PATH.exists():
        return {}
    try:
        payload = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return {row["file"]: row for row in payload.get("documents", [])}


def audit() -> dict:
    previous = load_previous_documents()
    text_files = {path.stem: path for path in TEXT_DIR.glob("*.txt")}
    documents = []

    for path in sorted(WORD_DIR.glob("*.docx"), key=lambda item: clean_stem(item.stem)):
        file_hash = sha256_file(path)
        row = {
            "file": path.name,
            "path": str(path.relative_to(ROOT)),
            "size": path.stat().st_size,
            "sha256": file_hash,
            "flags": [],
        }
        previous_row = previous.get(path.name)
        row["newSincePreviousRun"] = previous_row is None
        row["changedSincePreviousRun"] = bool(previous_row and previous_row.get("sha256") != file_hash)

        if "_OCR_parcial" in path.stem or "OCR_parcial" in path.stem:
            row["flags"].append("nome_indica_ocr_parcial")

        try:
            text, paragraph_count, table_count = extract_docx_text(path)
            text_words = words(text)
            char_count = len(text.strip())
            line_count, long_line_ratio, bad_line_ratio, sample, bad_line_score = line_metrics(text)
            odd_chars = weird_count(text)
            symbols = symbol_ratio(text)
            common_ratio = common_word_ratio(text_words)
            long_ratio = long_word_ratio(text_words)

            row.update(
                chars=char_count,
                words=len(text_words),
                paragraphs=paragraph_count,
                tables=table_count,
                lines=line_count,
                weird=odd_chars,
                weirdRatio=round(odd_chars / max(1, char_count), 6),
                symbolRatio=round(symbols, 6),
                commonWordRatio=round(common_ratio, 6),
                longWordRatio=round(long_ratio, 6),
                longLineRatio=round(long_line_ratio, 6),
                badLineRatio=round(bad_line_ratio, 6),
                badLineScore=bad_line_score,
                sample=sample,
            )

            if char_count < 300:
                row["flags"].append("texto_quase_vazio")
            elif char_count < 1500 and not any(name in path.name for name in ["Ficha", "Metropolis_8p"]):
                row["flags"].append("texto_muito_curto")
            if row["weirdRatio"] > 0.01:
                row["flags"].append("ruido_codificacao_ocr")
            if symbols > 0.055:
                row["flags"].append("muitos_simbolos")
            if common_ratio < 0.02 and len(text_words) > 250:
                row["flags"].append("baixa_coerencia_vocabulario_pt")
            if long_ratio > 0.02:
                row["flags"].append("muitas_palavras_coladas")
            if long_line_ratio > 0.35:
                row["flags"].append("linhas_muito_longas_layout")
            if bad_line_ratio > 0.03 or bad_line_score > 80:
                row["flags"].append("trechos_com_ocr_ruidoso")

            text_match = best_text_match(path, text_files)
            if text_match:
                old_text = text_match.read_text(encoding="utf-8", errors="ignore")
                old_chars = len(old_text.strip())
                row["matchedTxt"] = text_match.name
                row["txtChars"] = old_chars
                if old_chars > 2000:
                    ratio = char_count / old_chars
                    row["docxToTxtRatio"] = round(ratio, 3)
                    if ratio < 0.30:
                        row["flags"].append("docx_muito_menor_que_txt_existente")
                    elif ratio < 0.55:
                        row["flags"].append("docx_possivelmente_truncado_vs_txt")
                    elif ratio > 3.0:
                        row["flags"].append("docx_muito_maior_que_txt_existente")

            severe_flags = {
                "texto_quase_vazio",
                "ruido_codificacao_ocr",
                "docx_muito_menor_que_txt_existente",
            }
            if any(flag in severe_flags for flag in row["flags"]):
                row["status"] = "ruim"
            elif row["flags"]:
                row["status"] = "revisar"
            else:
                row["status"] = "ok"
        except Exception as exc:
            row["status"] = "ruim"
            row["flags"].append("erro_abrindo_docx")
            row["error"] = str(exc)

        documents.append(row)

    summary = {status: sum(1 for row in documents if row["status"] == status) for status in ["ruim", "revisar", "ok"]}
    payload = {
        "version": 1,
        "lastRun": datetime.now().isoformat(timespec="seconds"),
        "intervalSeconds": None,
        "summary": summary,
        "total": len(documents),
        "newFiles": [row["file"] for row in documents if row.get("newSincePreviousRun")],
        "changedFiles": [row["file"] for row in documents if row.get("changedSincePreviousRun")],
        "documents": documents,
    }
    return payload


def write_report(interval_seconds: int | None = None) -> dict:
    payload = audit()
    payload["intervalSeconds"] = interval_seconds
    write_json(REPORT_PATH, payload)
    return payload


def log_monitor(message: str) -> None:
    MONITOR_LOG.parent.mkdir(parents=True, exist_ok=True)
    with MONITOR_LOG.open("a", encoding="utf-8") as log:
        log.write(f"{datetime.now().isoformat(timespec='seconds')} {message}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit DOCX quality in Livros/word.")
    parser.add_argument("--watch", action="store_true", help="Keep auditing periodically.")
    parser.add_argument("--interval", type=int, default=600, help="Watch interval in seconds.")
    args = parser.parse_args()

    if args.watch:
        log_monitor(f"watch started interval={args.interval}s")
        while True:
            try:
                payload = write_report(args.interval)
                new_count = len(payload["newFiles"])
                changed_count = len(payload["changedFiles"])
                log_monitor(
                    "run "
                    f"total={payload['total']} "
                    f"summary={payload['summary']} "
                    f"new={new_count} changed={changed_count}"
                )
            except Exception as exc:
                log_monitor(f"error {exc!r}")
            time.sleep(args.interval)
    else:
        payload = write_report()
        print(json.dumps({"total": payload["total"], "summary": payload["summary"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
