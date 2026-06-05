#!/usr/bin/env python3
"""
Phase 2 OCR fixes - Handle encoding issues and residual errors
"""

from pathlib import Path
import unicodedata

SRC = Path(__file__).resolve().parents[1] / "data" / "text" / "anjos-a-cidade-de-prata.txt"

# Secondary fixes for encoding/mojibake issues
FIXES_PHASE2 = {
    # Encoding artifacts with mojibake characters
    "bánus": "bônus",  # bónus with wrong accent
    "demônio": "demônio",  # demónio
    "milénio": "milênio",  # milênio
    "pais serem mortos": "país serem mortos",  # accent missing
    "j á": "já",  # space in middle
    "2 37 anos": "237 anos",  # broken number

    # Remaining known errors
    "VERIflQUE DETALHCS": "VERIFIQUE DETALHES",
    "VERIFQUE DETALHCS": "VERIFIQUE DETALHES",
    "DETALHCS": "DETALHES",
    "LCAIS": "LOCAIS",
    "2CAIS": "LOCAIS",
    "fisceLHA": "ESCOLHA",
    "EsceiHA": "ESCOLHA",
}

def normalize_accents(text: str) -> str:
    """Normalize accents to NFC form"""
    return unicodedata.normalize('NFC', text)

def apply_fixes(text: str) -> tuple[str, int]:
    """Apply phase 2 fixes"""
    count = 0

    for old, new in FIXES_PHASE2.items():
        occurrences = text.count(old)
        if occurrences > 0:
            text = text.replace(old, new)
            count += occurrences
            print(f"  Fixed '{old}' -> '{new}' ({occurrences}x)")

    # Normalize Unicode
    text = normalize_accents(text)

    return text, count

def main():
    if not SRC.exists():
        print(f"ERROR: File not found: {SRC}")
        return False

    print(f"Reading {SRC}...")
    original = SRC.read_text(encoding="utf-8")

    print("Applying phase 2 fixes...")
    corrected, count = apply_fixes(original)

    if corrected == original:
        print("No additional changes needed.")
        return True

    print(f"\nTotal fixes: {count}")
    print("Writing corrected file...")
    SRC.write_text(corrected, encoding="utf-8")
    print("Done!")
    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
