#!/usr/bin/env python3
"""
Cleaning pipeline for 'Anjos - Réquiem de Fé'.

The DOCX (two-column layout) is full of:
  1. Mid-word hyphenation from column wrapping: "De-miurgo", "rara-mente".
  2. Soft line-breaks that split sentences across paragraphs.

dehyphenate() uses a Portuguese dictionary to tell a wrapped word
("celes-tiais" -> "celestiais") from a legitimate hyphen/enclitic
("tornar-se", "guarda-chuvas") which must be kept.

coherent_paragraphs() then rejoins sentence fragments across paragraphs.
"""
from __future__ import annotations
import re

try:
    from spellchecker import SpellChecker
    _SP = SpellChecker(language="pt")
    def _valid(word: str) -> bool:
        return word.lower() in _SP
except Exception:  # pragma: no cover - fallback if dependency missing
    _SP = None
    def _valid(word: str) -> bool:
        return False

# Enclitic / mesoclitic pronoun suffixes (legitimate hyphen after a verb)
CLITICS = {
    "se", "lo", "la", "los", "las", "lhe", "lhes", "lho", "lha", "lhos", "lhas",
    "me", "te", "nos", "vos", "mo", "ma", "no", "na",
}
ACCENT_END = tuple("áéíóúâêôûãõà")

WORD = "A-Za-zÀ-ÿ"
HYPHEN_RE = re.compile(rf"([{WORD}]+)-([{WORD}]+)")


def _keep_hyphen(prefix: str, suffix: str) -> bool:
    """True when the hyphen is legitimate (enclitic/compound), not a wrap."""
    joined = prefix + suffix
    suf_l = suffix.lower()
    # Enclitic pronoun attached to a verb form (infinitive 'r' or accented stem).
    # Guard: if the fused form is itself a real word (batalhas, orelhas), it was
    # a wrapped word, not an enclitic — so do NOT keep the hyphen.
    if (suf_l in CLITICS and not _valid(joined)
            and (prefix.lower().endswith("r")
                 or prefix.endswith(ACCENT_END)
                 or prefix.lower().endswith("ndo")
                 or _valid(prefix))):
        return True
    # Generic compound: both parts are real words but the fusion is not
    if _valid(prefix) and _valid(suffix) and not _valid(joined):
        return True
    return False


def dehyphenate(text: str) -> str:
    def repl(m: re.Match) -> str:
        prefix, suffix = m.group(1), m.group(2)
        if _keep_hyphen(prefix, suffix):
            return m.group(0)
        return prefix + suffix
    # Apply twice to catch chains like "a-b-c"
    return HYPHEN_RE.sub(repl, HYPHEN_RE.sub(repl, text))


def normalize(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def join_body(raw_paragraphs: list[str]) -> list[str]:
    """Join sentence fragments within a single heading's body (no titles)."""
    paras = [normalize(p) for p in raw_paragraphs]
    paras = [p for p in paras if p]

    def ends_terminal(line: str) -> bool:
        return line.rstrip().endswith((".", "!", "?", "”", "\"", ")", "]", ":"))

    result: list[str] = []
    buffer = ""
    def flush():
        nonlocal buffer
        if buffer.strip():
            result.append(dehyphenate(buffer.strip()))
        buffer = ""
    for line in paras:
        # Sub-power / sub-entry headers ("– Nome") stay standalone
        if line.lstrip().startswith(("–", "—")):
            flush()
            result.append(dehyphenate(line.strip()))
            continue
        if not buffer:
            buffer = line
        elif buffer.rstrip().endswith("-"):
            base = buffer.rstrip()[:-1]
            head_word = line.split(" ", 1)[0]
            prefix = base.rsplit(" ", 1)[-1]
            buffer = (base + "-" + line) if _keep_hyphen(prefix, head_word) else (base + line)
        elif ends_terminal(buffer):
            flush()
            buffer = line
        else:
            buffer = buffer + " " + line
    flush()
    return result


def extract_blocks(docx_path):
    """Return ordered blocks [(level:int|None, title:str|None, body:list[str])].

    Heading-styled paragraphs (Heading 1/2/3) start new blocks; their body is
    the following non-heading paragraphs, cleaned and fragment-joined.
    Heading 4 (epigraph quotes) is treated as body of the current block.
    """
    from docx import Document
    doc = Document(docx_path)
    blocks = []
    cur_level, cur_title, cur_raw = None, None, []

    def push():
        if cur_title is not None or cur_raw:
            blocks.append((cur_level, cur_title, join_body(cur_raw)))

    for p in doc.paragraphs:
        t = p.text.strip()
        if not t:
            continue
        style = p.style.name if p.style else ""
        if style.startswith("Heading") and style[-1] in "123":
            push()
            cur_level = int(style[-1])
            cur_title = normalize(t)
            cur_raw = []
        else:
            cur_raw.append(t)
    push()
    return blocks


def coherent_paragraphs(raw_paragraphs: list[str], titles: set[str] | None = None,
                        is_title=None) -> list[str]:
    """Rejoin sentence fragments split across paragraphs.

    A paragraph that ends with '-' is a wrapped word -> dehyphenate-join.
    A following paragraph starting lowercase continues the previous one.
    Buffer flushes on terminal punctuation, a recognised title, or a heading.
    """
    titles = titles or set()
    if is_title is None:
        def is_title(line: str) -> bool:
            return line in titles

    paras = [normalize(p) for p in raw_paragraphs]
    paras = [p for p in paras if p]

    def ends_terminal(line: str) -> bool:
        return line.rstrip().endswith((".", "!", "?", "”", "\"", ")", "]", ":"))

    result: list[str] = []
    buffer = ""

    def flush():
        nonlocal buffer
        if buffer.strip():
            result.append(dehyphenate(buffer.strip()))
        buffer = ""

    for line in paras:
        if is_title(line):
            flush()
            result.append(line)
            continue
        if not buffer:
            buffer = line
        elif buffer.rstrip().endswith("-"):
            # wrapped word across paragraph boundary
            base = buffer.rstrip()[:-1]
            tail = line.split(" ", 1)
            head_word = tail[0]
            prefix = base.rsplit(" ", 1)[-1]
            if _keep_hyphen(prefix, head_word):
                buffer = base + "-" + line
            else:
                buffer = base + line
        elif ends_terminal(buffer):
            flush()
            buffer = line
        elif line[0].islower():
            buffer = buffer + " " + line
        else:
            # Uppercase start after non-terminal buffer: still likely a wrap
            buffer = buffer + " " + line
    flush()
    return result
