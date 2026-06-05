"""Diagnóstico de estrutura do Guia de Itens Mágicos (OCR pesado).

Não modifica nada — só lê o DOCX e imprime um mapa:
- segmentação por marcador "Página N" (monotônico 1..288);
- onde está o corpo dos itens vs sumário/apêndice;
- transição alfabética dos nomes de item (para achar fronteira A-H / H-Z).

Uso: python scripts/analyze_itens_magicos.py
"""
import re
from collections import defaultdict
from docx import Document

DOCX = "Livros/word/Guia_de_Itens_Magicos_OCR_alta_qualidade.docx"
PG = re.compile(r"^P.gina (\d+)")


def load_lines():
    doc = Document(DOCX)
    cur = 0
    lines = []  # (pagina, texto)
    for p in doc.paragraphs:
        t = p.text.strip()
        if not t:
            continue
        m = PG.match(t)
        if m:
            cur = int(m.group(1))
            continue
        lines.append((cur, t))
    return lines


def looks_title(t):
    """Heurística para 'nome de item' no corpo."""
    if not (3 <= len(t) <= 44):
        return False
    if not t[0].isalpha() or not t[0].isupper():
        return False
    if t.endswith((".", ",", ":", ";")):
        return False
    # rejeita linhas que são claramente frase (têm verbo comum / muitos espaços minúsculos)
    return True


def main():
    lines = load_lines()
    print(f"linhas com texto (fora marcadores pagina): {len(lines)}")

    # candidatos a item: título seguido de descrição longa
    firsts = defaultdict(list)
    for k, (pgn, t) in enumerate(lines):
        if pgn < 13 or pgn > 279:
            continue
        if looks_title(t):
            nxt = lines[k + 1][1] if k + 1 < len(lines) else ""
            if len(nxt) > 40:
                firsts[pgn].append(t)

    print("\n=== transição alfabética (1ª inicial nova por página) ===")
    prev = None
    for pgn in sorted(firsts):
        initial = firsts[pgn][0][0].upper()
        if initial != prev:
            print(f"pg {pgn:3d}: inicial {initial}  ex: {firsts[pgn][0][:42]!r}")
            prev = initial

    print("\n=== total de candidatos a item por faixa de página ===")
    tot = sum(len(v) for v in firsts.values())
    print(f"total candidatos (heurística): {tot}")


VOL1 = (18, 146)  # páginas A–H (entrega 1)


def ocr_stats():
    """Quantifica padrões de OCR no Volume 1 (pg 18–146)."""
    lines = load_lines()
    vol1 = [t for p, t in lines if VOL1[0] <= p <= VOL1[1]]
    txt = "\n".join(vol1)
    print(f"\n=== Vol1: {len(vol1)} linhas, {len(txt)} chars ===")
    pats = {
        "ç var '<;'": len(re.findall(r"<;", txt)),
        "ç var 'c;'": len(re.findall(r"c;", txt)),
        "ç var 'c:;:'": len(re.findall(r"c:;:", txt)),
        "til '~' solto": txt.count("~"),
        "mojibake U+FFFD": txt.count("�"),
        "0 isolado ' 0 '": len(re.findall(r"(?<=\s)0(?=\s)", txt)),
        "urn (=um)": len(re.findall(r"\burn\b", txt)),
        "Urn (=Um)": len(re.findall(r"\bUrn\b", txt)),
        "dane (=dano)": len(re.findall(r"\bdane\b", txt)),
        "s6 (=só)": len(re.findall(r"\bs6\b", txt)),
        "fonna(s) (=forma)": len(re.findall(r"\bfonnas?\b", txt)),
        "Annadura": len(re.findall(r"Annadura", txt)),
        "nan (=não)": len(re.findall(r"\bnan\b", txt)),
        "enta~ (=então)": len(re.findall(r"enta~", txt)),
        "ld\\d (1->l: ld6/ld100)": len(re.findall(r"\bld\d", txt)),
    }
    for k, v in pats.items():
        print(f"  {v:5d}  {k}")


if __name__ == "__main__":
    main()
    ocr_stats()
