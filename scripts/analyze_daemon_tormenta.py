"""Diagnóstico de estrutura do Daemon Tormenta (read-only).

Mapeia fronteiras dos capítulos catalogáveis (Raças, Kits, Aprimoramentos) via
marcadores de campo, usando a paginação "Página N" como âncora.

Uso: python scripts/analyze_daemon_tormenta.py
"""
import re
from docx import Document

DOCX = "Livros/word/Daemon_Tormenta_OCR_alta_qualidade.docx"
PG = re.compile(r"^Página (\d+)")
FOOTER = 'TORMENTA RPG - SISTEMA Daemon - VERSÃO DE THIAGO "MESTRE KWAN" RODRIGUES'


def load_lines():
    doc = Document(DOCX)
    cur = 0
    lines = []
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


def main():
    lines = load_lines()
    print(f"linhas de corpo: {len(lines)} | última página: {lines[-1][0]}")

    # Raças: bloco iniciado por 'Custo:'/'Idade Inicial:' + 'Atributos:'
    print("\n=== RAÇAS (marcador 'Atributos:' precedido de 'Custo:'/'Idade Inicial:') ===")
    for i, (p, t) in enumerate(lines):
        if re.match(r"^Atributos:", t):
            ctx = [lines[j][1] for j in range(max(0, i - 4), i)]
            has_cost = any(c.startswith("Custo:") for c in ctx)
            # nome = primeira linha curta-título do contexto que não é campo
            name = next((c for c in ctx
                         if 3 <= len(c) <= 24 and c[0].isupper()
                         and not re.match(r"(Custo|Idade|Atributos|Vantagens|Desvantagens|Idiomas):", c)
                         and c != FOOTER), "?")
            print(f"  pg{p:3d} | custo={'sim' if has_cost else 'NÃO'} | {name!r} | {t[:40]}")

    # Kits: bloco com 'Restrições:' e 'Perícias:'
    print("\n=== KITS/PROFISSÕES (marcador 'Restrições:') por página ===")
    kit_pages = sorted({p for p, t in lines if re.match(r"^Restri[çc][õo]es:", t)})
    print(f"  páginas com 'Restrições:': {kit_pages}")

    # Aprimoramentos: linhas '-N ponto(s)' / '+N ponto(s)' iniciando bloco
    print("\n=== APRIMORAMENTOS (linhas '[+-]N ponto(s):') por página ===")
    apr_pages = sorted({p for p, t in lines if re.match(r"^[+\-]?\d+\s*pontos?\s*:", t)})
    print(f"  páginas: {apr_pages}")


if __name__ == "__main__":
    main()
