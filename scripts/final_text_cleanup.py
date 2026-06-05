#!/usr/bin/env python3
"""
Final targeted text cleanup - ONLY safe, unambiguous fixes
"""

import re
from pathlib import Path

TEXT_PATH = Path("data/text/anjos-a-cidade-de-prata.txt")

content = TEXT_PATH.read_text(encoding="utf-8")

# ONLY unambiguous fixes (no risk of creating new errors)
SAFE_FIXES = [
    # Direct replacements - NO ambiguity
    ('VERIFQUE DETALHCS', 'VERIFIQUE DETALHES'),
    ('DETALHCS DA', 'DETALHES DA'),
    ('2 37 anos', '237 anos'),
    ('pessoa!', 'pessoal'),
    # Double spaces
    ('  ', ' '),
    # Space before punctuation
    (r' ([,;:!?])', r'\1'),  # This is regex
]

print("LIMPEZA FINAL - FIXES SEGUROS APENAS")
print("=" * 80)

fixed_count = 0

for old, new in SAFE_FIXES:
    if old.startswith('('):  # It's regex
        pattern = old
        before = len(content)
        content = re.sub(pattern, new, content)
        after = len(content)
        if before != after:
            fixed_count += 1
            print(f"[OK] Fixed: {pattern} -> {new}")
    else:
        count = content.count(old)
        if count > 0:
            content = content.replace(old, new)
            fixed_count += 1
            print(f"[OK] Fixed: '{old}' -> '{new}' ({count}x)")

# Save
TEXT_PATH.write_text(content, encoding="utf-8")

print("\n" + "=" * 80)
print(f"Fixes aplicados: {fixed_count}")
print(f"\nERROS RESTANTES que requerem revisao manual:")
print("  - Acentuacao (politica, milenio, demonio, etc.): ~32 erros")
print("  - rn -> m (contexto ambiguo): 195 erros")
print("  - Outros erros OCR complexos")
print("\n  => Recomendacao: Revisao humana/manual para esses erros restantes")
print("=" * 80)

TEXT_PATH.write_text(content, encoding="utf-8")
