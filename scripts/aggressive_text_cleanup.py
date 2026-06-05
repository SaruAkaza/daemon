#!/usr/bin/env python3
"""
Aggressive cleanup of anjos-a-cidade-de-prata.txt
Removes OCR noise, corrupted characters, and formatting artifacts
"""

import re
from pathlib import Path

TEXT_PATH = Path("data/text/anjos-a-cidade-de-prata.txt")

content = TEXT_PATH.read_text(encoding="utf-8")
lines = content.split('\n')

print("LIMPEZA AGRESSIVA")
print("=" * 80)

# Track changes
removed_count = 0
fixed_count = 0

# 1. Remove completely empty lines and lines with only spaces
cleaned = []
prev_empty = False

for line in lines:
    # Skip pure whitespace
    if not line.strip():
        if not prev_empty:  # Keep max 1 blank line
            cleaned.append("")
            prev_empty = True
        continue
    prev_empty = False
    cleaned.append(line)

removed_count += len(lines) - len(cleaned)
lines = cleaned
print(f"1. Removed excess blank lines: {removed_count}")

# 2. Remove lines that are ONLY OCR noise/page artifacts
noise_patterns = [
    (r'^---\s*page\s+\d+\s*---$', "page marker"),
    (r'^[\s\^\-_\|~\.\\]+$', "symbol line"),
    (r'^\s*\d{1,3}\s*$', "page number"),
    (r'^[ivxlcm]+$', "roman numeral"),
]

new_lines = []
noise_removed = 0

for line in lines:
    stripped = line.strip()
    is_noise = False

    for pattern, desc in noise_patterns:
        if re.match(pattern, stripped, re.IGNORECASE):
            is_noise = True
            noise_removed += 1
            break

    if not is_noise:
        new_lines.append(line)

lines = new_lines
print(f"2. Removed OCR noise lines: {noise_removed}")

# 3. Remove corrupted characters (encoding issues)
# Characters with ord > 127 that are NOT valid Portuguese
valid_high_chars = {
    'á', 'é', 'í', 'ó', 'ú', 'à', 'â', 'ê', 'ô', 'ã', 'õ', 'ç',
    'Á', 'É', 'Í', 'Ó', 'Ú', 'À', 'Â', 'Ê', 'Ô', 'Ã', 'Õ', 'Ç',
    '—', '–', '…', '"', '"', ''', ''',  # punctuation
}

corrupted_chars = set()
for line in lines:
    for char in line:
        if ord(char) > 127 and char not in valid_high_chars and char not in '\n\r\t':
            corrupted_chars.add(char)

print(f"   Found corrupted chars: {[f'{c!r}(ord={ord(c)})' for c in sorted(corrupted_chars)]}")

new_lines = []
chars_fixed = 0

for line in lines:
    new_line = line
    for char in corrupted_chars:
        if char in new_line:
            new_line = new_line.replace(char, '')
            chars_fixed += 1
    new_lines.append(new_line)

lines = new_lines
print(f"3. Removed corrupted chars: {chars_fixed} occurrences")

# 4. Fix spacing issues
spacing_fixes = [
    (r'\s+([,;:!?\)])', r'\1', "space before punctuation"),
    (r'([(\[])\s+', r'\1', "space after opening bracket"),
    (r'\s+([0-9])\s+\.', r' \1.', "space around period-number"),
    (r'(\w)\s+([—–])\s+(\w)', r'\1 — \2 — \3'.replace(' — \2 — ', ' — '), "em-dash spacing"),
]

spacing_fixed = 0
for pattern, replacement, desc in spacing_fixes:
    before = len(lines)
    lines = [re.sub(pattern, replacement, line) for line in lines]
    # Count changes (rough estimate)

print(f"4. Fixed spacing issues")

# 5. Fix common OCR typos remaining
typo_fixes = [
    ('qua1idade', 'qualidade'),
    ('qua1quer', 'qualquer'),
    ('resu1tado', 'resultado'),
    ('oca1mente', 'localmente'),
    ('tota1', 'total'),
    ('professiona1', 'profissional'),
    ('a1guém', 'alguém'),
    ('ga1eria', 'galeria'),
    ('so1do', 'soldo'),
    ('oferta1', 'ofertal'),
]

typo_fixed = 0
for old, new in typo_fixes:
    before = '\n'.join(lines)
    after = before.replace(old, new)
    if before != after:
        typo_fixed += before.count(old)
        lines = after.split('\n')

print(f"5. Fixed remaining typos: {typo_fixed}")

# 6. Normalize quotes and dashes
quote_fixes = [
    ('"', '"'),  # Curly quotes to straight
    ('"', '"'),
    (''', "'"),
    (''', "'"),
    ('–', '-'),  # En-dash to hyphen
    ('—', '-'),  # Em-dash to hyphen (careful with context)
]

for old, new in quote_fixes:
    lines = [line.replace(old, new) for line in lines]

print(f"6. Normalized quotes and dashes")

# 7. Final validation - remove lines that are still corrupted
valid_lines = []
for line in lines:
    # Check for remaining corruption (any non-ASCII except valid Portuguese)
    has_corruption = False
    for char in line:
        if ord(char) > 127 and char not in valid_high_chars and char not in '\n\r\t':
            has_corruption = True
            break

    if not has_corruption:
        valid_lines.append(line)

lines = valid_lines
print(f"7. Final validation complete")

# Save
final_content = '\n'.join(lines)
TEXT_PATH.write_text(final_content, encoding="utf-8")

print("\n" + "=" * 80)
print(f"✓ LIMPEZA COMPLETA")
print(f"  Linhas antes: {len(content.split(chr(10)))}")
print(f"  Linhas depois: {len(lines)}")
print(f"  Removidas: {len(content.split(chr(10))) - len(lines)}")
print(f"\n  Arquivo salvo: {TEXT_PATH}")
