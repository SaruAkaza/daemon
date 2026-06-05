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


LIGATURES = {"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl",
             "ﬃ": "ffi", "ﬄ": "ffl", "ﬅ": "ft", "ﬆ": "st"}


# ---------------------------------------------------------------------------
# OCR character/word repair (added for "Guia de Itens Mágicos", heavy OCR).
# Additive and OPT-IN: fix_ocr() is NOT called by normalize(), so the Anjos
# pipeline output is byte-for-byte unchanged. The Itens Mágicos build calls
# fix_ocr() explicitly before normalize(). Safe/idempotent on clean text.
# ---------------------------------------------------------------------------

# Multi-variant 'ç' artefacts, longest first so 'c:;:' wins over 'c;'.
_CEDILLA_RE = [
    (re.compile(r"c:;:"), "ç"),
    (re.compile(r"<;"), "ç"),
    (re.compile(r"c;"), "ç"),
]

# Whole-word OCR fixes (case-sensitive where it matters). Applied on word
# boundaries so we never touch substrings of legitimate words.
_OCR_WORDS = {
    "urn": "um", "Urn": "Um",
    "dane": "dano", "s6": "só",
    "fonna": "forma", "fonnas": "formas",
    "Annadura": "Armadura", "annadura": "armadura",
    "nan": "não", "enta": "então",  # 'enta~' -> after ~ stripping below
}
_OCR_WORD_RE = re.compile(
    r"\b(" + "|".join(sorted(map(re.escape, _OCR_WORDS), key=len, reverse=True)) + r")\b"
)

# '1' misread as 'l'/'I' in dice tokens: ld6/Id6 -> 1d6, ld100/Id100 -> 1d100.
_DICE_L_RE = re.compile(r"\b[lI]d(\d)")

# Digit '0' standing in for the article 'o'/'O': only when isolated as a whole
# token (surrounded by whitespace / sentence start), never adjacent to digits,
# so numeric ranges in tables (e.g. '01-55', '7-0') are preserved.
_ZERO_ART_RE = re.compile(r"(^|(?<=\s))0(?=\s)")


def fix_ocr(text: str) -> str:
    """Repair recurrent OCR artefacts seen in the Itens Mágicos scan.

    Conservative by design: every rule is anchored (word boundary, isolated
    token, or specific bigram) to avoid corrupting valid text or numeric tables.
    Safe to run on already-clean text (idempotent / no-op).
    """
    # 'enta~' -> 'então' (handle the tilde form before generic ~ stripping).
    text = re.sub(r"\benta~", "então", text)
    # ç variants
    for rx, rep in _CEDILLA_RE:
        text = rx.sub(rep, text)
    # leftover stray '~' that survived (kerning noise) -> drop
    text = text.replace("~", "")
    # dice 'l' -> '1'
    text = _DICE_L_RE.sub(r"1d\1", text)
    # isolated '0' article -> 'o' (preserve capitalisation at sentence start
    # is ambiguous from OCR; lower 'o' is the overwhelmingly common case)
    text = _ZERO_ART_RE.sub("o", text)
    # whole-word fixes
    text = _OCR_WORD_RE.sub(lambda m: _OCR_WORDS[m.group(1)], text)
    return text


_SPACED_RE = re.compile(r"(?:(?<![A-Za-zÀ-ÿ])[A-Za-zÀ-ÿ] ){3,}[A-Za-zÀ-ÿ](?![A-Za-zÀ-ÿ])")


def collapse_spaced_letters(text: str) -> str:
    """Collapse kerning artefacts like 'T e n d ê n c i a' -> 'Tendência'."""
    text = _SPACED_RE.sub(lambda m: m.group(0).replace(" ", ""), text)
    text = re.sub(r"\s+:\s+", ": ", text)
    return text


def normalize(text: str) -> str:
    text = text.replace("\xa0", " ")
    for lig, repl in LIGATURES.items():
        text = text.replace(lig, repl)
    text = collapse_spaced_letters(text)
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
