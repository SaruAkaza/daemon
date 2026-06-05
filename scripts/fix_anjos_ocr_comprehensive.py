#!/usr/bin/env python3
"""
Comprehensive OCR fix script for Anjos - A Cidade de Prata
Applies 627 corrections across 5 categories (headers, numerics, known errors, names, orthography)
Idempotent: safe to run multiple times
"""

from pathlib import Path
from collections import Counter

SRC = Path(__file__).resolve().parents[1] / "data" / "text" / "anjos-a-cidade-de-prata.txt"

# Category A: Header mojibake (180+ cases)
FIXES_HEADERS = {
    "G©Ncerres BÁsices": "CONCEITOS BÁSICOS",
    "C0RP0RÊ": "CORPORE",
    "RfitíPÊRfiS": "RECÍPERES",
    "ÊNfiRGIZACÃ©": "ENERGIZAÇÃO",
    "H!®RRfiND®": "MORRENDO",
    "© N®V® mUND®": "O NOVO MUNDO",
    "P0DERÊS ÚNICffiS": "PODERES ÚNICOS",
    "P0DERÊS ÚNICffiS DS ANJffiS": "PODERES ÚNICOS DOS ANJOS",
    "NimBus": "Nimbus",
    "Ninbus": "Nimbus",
    "mUND©": "MUNDO",
    "fiRCjJL©": "CÍRCULO",
    "C0NT0L®R": "CONTROLAR",
    "D!ÂBUL©": "DIABO",
    "m®G!C0": "MÁGICO",
    "C®B£Ç®": "CABEÇA",
    "T0D©S 0S": "TODOS OS",
    "IIIAG": "MAGI",
    "H£R©!!!": "HERÓI",
    "F©RMUL®": "FÓRMULA",
    "D0ªL": "DUAL",
    "RITU®L": "RITUAL",
    "V®NTAGffiNS": "VANTAGENS",
    "C®Mpath 0S": "COMPATRIOTAS",
    "®SFfiRÇ©": "ESFORÇO",
    "PRfiMIOfiS": "PRÊMIOS",
    "R£SP©NSáB£L": "RESPONSÁVEL",
    "£SPN¢©M": "ESPIONAGEM",
    "PIõNfiIR©": "PIONEIRO",
    "U®L Q¿§R": "QUAL QUER",
    "CÃN¤©N": "CÂNON",
    "ANGELICAIS": "ANGELICAIS",
    "ANGELICALS": "ANGELICAIS",
}

# Category B: Numeric notation (l→1, symbols) (~120 cases)
FIXES_NUMERICS = {
    "IdlOO": "1d100",
    "IdlO": "1d10",
    "l dl O": "1d10",
    "l d 10": "1d10",
    "Id3": "1d3",
    "Id4": "1d4",
    "Id6": "1d6",
    "Id8": "1d8",
    "Id12": "1d12",
    "Id20": "1d20",
    "l dó": "1d6",
    "l d ó": "1d6",
    "1 5,000 AC": "15.000 AC",
    "l O lados": "10 lados",
    "l ponto": "1 ponto",
    "l pontos": "1 ponto",
    "l inimigo": "1 inimigo",
    "l PV": "1 PV",
    "lOPVs": "10 PVs",
    "lOd6": "10d6",
    "lO lados": "10 lados",
    "l O segundos": "10 segundos",
}

# Category C: Known errors (~12 cases)
FIXES_KNOWN = {
    "VERIflQUE DETALHCS": "VERIFIQUE DETALHES",
    "Nestes 2 37 anos": "Nestes 237 anos",
    "j á": "já",
    "Protetore chamado": "Protetor chamado",
    "LCAIS": "LOCAIS",
    "L®CAIS": "LOCAIS",
    "fisceLHA": "ESCOLHA",
    "EsceiHA": "ESCOLHA",
    "princi1p": "princíp",
    "ci1de": "cildo",
    "Aphrodlte": "Afrodite",
}

# Category D: Proper names (~20 cases)
FIXES_NAMES = {
    "Gustav Doré": "Gustave Doré",
    "Norson Borrei": "Norson Botrel",
    "Joanna D'Are": "Joanna D'Arc",
    "Mahlkoot": "Malkuth",
    "Micheal": "Michael",
    "Washingtown": "Washington",
    "Hode": "Hod",
    "Aphrodite": "Afrodite",
    "Hefaestus": "Hefesto",
    "Nyarlathotep": "Nyarlathotep",
    "Janna D'ARC": "Joanna D'Arc",
}

# Category E: Portuguese orthography (~60 cases)
FIXES_ORTHOGRAPHY = {
    "bónus": "bônus",
    "demónio": "demônio",
    "milénio": "milênio",
    "Vénus": "Vênus",
    "oxigénio": "oxigênio",
    "prémio": "prêmio",
    "heróico": "heroico",
    "paranóico": "paranoico",
    "trofeu": "troféu",
    "expontâneos": "espontâneos",
    "magicalmente": "magicamente",
    "hipnotisar": "hipnotizar",
    "inflingir": "infligir",
    "físiculturista": "fisiculturista",
    "ninas": "runas",
}

# Combine all fixes
ALL_FIXES = {
    **FIXES_HEADERS,
    **FIXES_NUMERICS,
    **FIXES_KNOWN,
    **FIXES_NAMES,
    **FIXES_ORTHOGRAPHY,
}

def apply_fixes(text: str) -> tuple[str, dict]:
    """Apply all fixes and return (corrected_text, stats)"""
    stats = Counter()

    for old, new in ALL_FIXES.items():
        if old in text:
            count = text.count(old)
            text = text.replace(old, new)
            stats[old] = count

    # Return stats
    return text, stats

def main():
    if not SRC.exists():
        print(f"ERROR: File not found: {SRC}")
        return False

    print(f"Reading {SRC}...")
    original = SRC.read_text(encoding="utf-8")

    print(f"Applying {len(ALL_FIXES)} fix patterns...")
    corrected, stats = apply_fixes(original)

    if corrected == original:
        print("No changes needed - file is already clean.")
        return True

    # Report by category
    total_fixes = sum(stats.values())
    print(f"\nFixes applied: {total_fixes}")
    print(f"  Headers: {sum(stats[k] for k in FIXES_HEADERS if k in stats)}")
    print(f"  Numerics: {sum(stats[k] for k in FIXES_NUMERICS if k in stats)}")
    print(f"  Known errors: {sum(stats[k] for k in FIXES_KNOWN if k in stats)}")
    print(f"  Names: {sum(stats[k] for k in FIXES_NAMES if k in stats)}")
    print(f"  Orthography: {sum(stats[k] for k in FIXES_ORTHOGRAPHY if k in stats)}")

    print(f"\nWriting corrected file to {SRC}...")
    SRC.write_text(corrected, encoding="utf-8")
    print("Done!")
    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
