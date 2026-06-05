from __future__ import annotations

import re
import unicodedata
from typing import Callable


# ============================================================================
# PHASE 1: Decompose Ligatures
# ============================================================================

LIGATURE_MAP = {
    'ﬁ': 'fi',      # ﬁ
    'ﬂ': 'fl',      # ﬂ
    'ﬃ': 'ffi',     # ﬃ
    'ﬄ': 'ffl',     # ﬄ
    'ﬅ': 'ft',      # ﬅ
    'ﬆ': 'st',      # ﬆ
}

def decompose_ligatures(text: str) -> str:
    """Convert Unicode ligatures to plain text equivalents."""
    for lig, replacement in LIGATURE_MAP.items():
        text = text.replace(lig, replacement)
    return text


# ============================================================================
# PHASE 2: Aggressively Join Fragments
# ============================================================================

def should_join_aggressive(previous: str, current: str) -> bool:
    """Determine if two paragraphs should be joined aggressively."""
    if not previous or not current:
        return False

    # Rule 1: Hyphen at end (continue compound word)
    if previous.endswith('-') and current[:1].islower():
        return True

    # Rule 2: Current starts with lowercase (fragment continuation)
    # AGGRESSIVE: join unless previous ends with sentence terminator
    if current[:1].islower() and not previous.endswith(('.', '!', '?')):
        return True

    # Rule 3: Current starts with punctuation (must join)
    if re.match(r'^[,.;:)\]}\'"«]', current):
        return True

    # Rule 3b: Current starts with closing bracket or parenthesis
    if current[:1] in ')]}':
        return True

    # Rule 4: Previous ends with preposition/article (always continue)
    # Use word boundary to avoid false positives on words ending with these letters
    prev_lower = previous.rstrip().lower()
    prepositions = {'de', 'do', 'da', 'dos', 'das', 'em', 'por', 'com', 'para'}
    for prep in prepositions:
        if re.search(rf'\b{re.escape(prep)}$', prev_lower):
            return True
    # Single-letter articles/prepositions (rare in this context)
    if prev_lower and prev_lower[-1] in {'e'} and len(prev_lower.split()) <= 3:
        # Only join if "e" is likely a connector word, not a suffix
        if prev_lower.endswith(' e'):
            return True

    # Rule 5: Current is very short and starts lowercase (fragment)
    if len(current) < 20 and current[:1].islower():
        return True

    # Rule 6: Current starts with lowercase and previous ends with % or number
    # (e.g., "5%" followed by "até 15% Curioso")
    if current[:1].islower() and re.search(r'(\d+%?|[-\d.]+)$', previous):
        return True

    return False


def join_fragments(text: str) -> str:
    """Aggressively join fragmented paragraphs."""
    paragraphs = text.split('\n')
    # Filter out empty paragraphs to improve join detection
    # (but keep their structure if needed - for now, remove them)
    result = []

    for current in paragraphs:
        if not current.strip():
            result.append(current)
            continue

        # Remove OCR debris at start: ffi/ffl sequences that don't belong
        # These are often remnants of mangled ligatures in OCR
        if re.match(r'^(ffi|ffl)\s+', current):
            # This is likely OCR debris - join cleaned version with previous non-empty paragraph
            cleaned = re.sub(r'^(ffi|ffl)\s+', '', current)
            # Find the last non-empty paragraph
            for i in range(len(result) - 1, -1, -1):
                if result[i].strip():
                    result[i] = f"{result[i]} {cleaned}"
                    # Skip adding this paragraph, it was joined
                    current = None
                    break
            if current is None:
                continue

        # Also remove "ffi" or "ffl" when directly attached to capital letter (mangled)
        current = re.sub(r'^(ffi|ffl)([A-Z])', r'\2', current)

        if result and result[-1].strip() and should_join_aggressive(result[-1], current):
            previous = result.pop()
            # Hyphenated join
            if previous.endswith('-') and current[:1].islower():
                result.append(previous[:-1] + current)
            # Normal join with space
            else:
                result.append(f"{previous} {current}")
        else:
            result.append(current)

    return '\n'.join(result)


# ============================================================================
# PHASE 3: Fix Numeric Confusion
# ============================================================================

NUMERIC_FIXES = [
    # Letter O confused with zero
    (r'\b1d10O\b', '1d100'),
    (r'\blO\b', '10'),
    (r'\blO\s', '10 '),
    (r'\b([Cc])hegam?a? a O\b', r'\1hegam a 0'),
    (r'\bO\s+lados', '10 lados'),

    # Letter l (lowercase L) confused with 1
    (r'\bl PV', '1 PV'),
    (r'\bl d', '1d'),
    (r'\bl D', '1D'),
    (r'\bl\.', '1.'),
    (r'\bl\s+ponto', '1 ponto'),
    (r'\bl\s+inimigo', '1 inimigo'),
    (r'\blOPVs', '10 PVs'),
    (r'\blOd6', '10d6'),
    (r'\bl(?:pontos?)', '1 ponto'),

    # Letter rn confused with m
    (r'\bVersá\br', 'Versal'),  # Avoid false positives with context

    # Fix Id to 1d
    (r'\bId\b', '1d'),
    (r'\bID\b', '1d'),

    # MORE AGGRESSIVE: Fix letter 1 (one) misread as l (lowercase L) in any position
    # Common pattern: consonant+vowel+1+vowel → consonant+vowel+l+vowel
    (r'([bcdfghjklmnpqrstvwxz])1([aeiouáéíóúàãõâê])', r'\1l\2'),

    # Also: vowel+consonant+1+vowel patterns
    (r'([aeiouáéíóúàãõâê][bcdfghjklmnpqrstvwxz])1([aeiouáéíóúàãõâê])', r'\1l\2'),

    # Catch remaining patterns: any 1 between letters
    (r'([a-z])1([a-z])', r'\1l\2'),

    # Fix remaining special cases
    (r'lega1', 'legal'),
    (r've1([^\d])', r'vel\1'),
    (r'd1entro', 'dentro'),
    (r'princi1p', 'principl'),  # typo prevention
]

def fix_numeric_patterns(text: str) -> str:
    """Fix OCR confusions with numbers (l→1, O→0, etc.)."""
    for pattern, replacement in NUMERIC_FIXES:
        text = re.sub(pattern, replacement, text)
    return text


# ============================================================================
# PHASE 4: Remove Invalid Unicode
# ============================================================================

INVALID_CHARS = {
    '£': '',   # £ (pound sign)
    '§': '',   # § (section sign)
    '†': '',   # † (dagger)
    '‡': '',   # ‡ (double dagger)
    '\x00': '',     # Null
}

def remove_invalid_unicode(text: str) -> str:
    """Remove invalid or unwanted Unicode characters."""
    # Replace known bad characters
    for char, replacement in INVALID_CHARS.items():
        text = text.replace(char, replacement)

    # Remove any remaining control characters (< 0x20, except tab/newline/carriage return)
    text = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f]', '', text)

    return text


# ============================================================================
# PHASE 5: Filter Corrupted Titles
# ============================================================================

def is_corrupted_title(text: str) -> bool:
    """Detect if a paragraph is a corrupted OCR title."""
    # Heuristic: if mostly uppercase with scattered lowercase and many special chars
    if len(text) < 5:
        return False

    upper_count = sum(1 for c in text if c.isupper())
    lower_count = sum(1 for c in text if c.islower())
    special_count = sum(1 for c in text if not c.isalnum() and c not in ' -')

    total = upper_count + lower_count
    if total == 0:
        return False

    # Corrupted title: >50% upper, 10-40% lower, >15% special chars
    upper_ratio = upper_count / total
    special_ratio = special_count / len(text)

    return upper_ratio > 0.5 and lower_count > 0 and special_ratio > 0.15


def filter_corrupted_paragraphs(text: str, corrupted_titles_dict: dict[str, str] | None = None) -> str:
    """Filter or fix corrupted OCR paragraphs."""
    if corrupted_titles_dict is None:
        corrupted_titles_dict = {}

    paragraphs = text.split('\n')
    result = []

    for para in paragraphs:
        stripped = para.strip()

        if not stripped:
            result.append(para)
            continue

        # Check if it matches a known corruption pattern
        if stripped in corrupted_titles_dict:
            result.append(corrupted_titles_dict[stripped])
            continue

        # Check if it looks like a corrupted title
        if is_corrupted_title(stripped):
            # Try to find a fix in the dictionary
            found = False
            for corruption, fix in corrupted_titles_dict.items():
                if stripped.startswith(corruption[:10]):  # Partial match
                    result.append(fix)
                    found = True
                    break

            if not found:
                # Mark it as suspicious but keep it (for manual review)
                # Could also remove it with: result.append('')
                result.append(para)
        else:
            result.append(para)

    return '\n'.join(result)


# ============================================================================
# MASTER CLEANUP FUNCTION
# ============================================================================

def clean_ocr_aggressive(
    text: str,
    phases: set[str] | None = None,
    title_fixes: dict[str, str] | None = None,
    decompose_first: bool = True,
) -> str:
    """
    Apply aggressive OCR cleanup in phases.

    Args:
        text: Raw OCR text
        phases: Set of phases to apply. Default: all 5 phases.
                Options: {"ligatures", "join", "numerics", "unicode", "titles"}
        title_fixes: Dictionary of corrupted → fixed titles
        decompose_first: If True, decompose ligatures before other processing

    Returns:
        Cleaned text
    """
    if phases is None:
        phases = {'ligatures', 'join', 'numerics', 'unicode', 'titles'}

    # Phase 1: Always decompose ligatures first (they affect other rules)
    if decompose_first or 'ligatures' in phases:
        text = decompose_ligatures(text)

    # Phase 2: Aggressively join fragments
    if 'join' in phases:
        text = join_fragments(text)

    # Phase 3: Fix numeric confusion
    if 'numerics' in phases:
        text = fix_numeric_patterns(text)

    # Phase 4: Remove invalid Unicode
    if 'unicode' in phases:
        text = remove_invalid_unicode(text)

    # Phase 5: Filter corrupted titles
    if 'titles' in phases and title_fixes:
        text = filter_corrupted_paragraphs(text, title_fixes)

    return text


# ============================================================================
# UTILITIES FOR AUDIT & VALIDATION
# ============================================================================

def count_suspicious_paragraphs(text: str) -> dict[str, int]:
    """Count paragraphs with signs of OCR corruption."""
    paragraphs = text.split('\n')

    stats = {
        'lowercase_start': 0,
        'very_short': 0,
        'corrupted_title': 0,
        'invalid_chars': 0,
        'total': 0,
    }

    for para in paragraphs:
        if not para.strip():
            continue

        stats['total'] += 1

        if para[0].islower():
            stats['lowercase_start'] += 1

        if len(para) < 20:
            stats['very_short'] += 1

        if is_corrupted_title(para):
            stats['corrupted_title'] += 1

        if any(c in para for c in INVALID_CHARS.keys()):
            stats['invalid_chars'] += 1

    return stats


def report_suspicious_paragraphs(text: str, limit: int = 10) -> list[str]:
    """Return list of suspicious paragraphs (for manual review)."""
    paragraphs = text.split('\n')
    suspicious = []

    for para in paragraphs:
        if not para.strip():
            continue

        if is_corrupted_title(para) or (para[0].islower() and len(para) > 3):
            suspicious.append(para)
            if len(suspicious) >= limit:
                break

    return suspicious
