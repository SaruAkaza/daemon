from __future__ import annotations

import argparse
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from common import ROOT, write_json


TARGETS = [
    "anime-rpg-powers",
    "anime-rpg-supers-powers",
]

PILOT_DIRS = [
    ROOT / "data" / "pilot",
    ROOT / "docs" / "assets" / "data" / "pilot",
]

REPORT_PATH = ROOT / "data" / "work" / "anime-text-cleanup-report.json"


def fix_mojibake(text: str) -> str:
    if "Ã" not in text and "Â" not in text:
        return text
    try:
        fixed = text.encode("latin1").decode("utf-8")
    except UnicodeError:
        return text
    if score_text(fixed) >= score_text(text):
        return fixed
    return text


def score_text(text: str) -> int:
    good = len(re.findall(r"\b(?:ção|ções|não|você|nível|descrição|herói|mágic\w*)\b", text, re.IGNORECASE))
    bad = text.count("Ã") + text.count("Â") + text.count("\ufffd")
    return good * 8 - bad * 10


def fix_ligatures(text: str) -> str:
    text = text.replace("\ufb01", "fi").replace("\ufb02", "fl")
    text = text.replace("ï¬", "fi").replace("ï¬‚", "fl")
    text = text.replace("tipo", "tipo")
    text = text.replace("sico", "físico")
    text = text.replace("sica", "física")
    text = text.replace("sicos", "físicos")
    text = text.replace("sicas", "físicas")
    text = text.replace("", "ti")
    text = text.replace("\x8d", "ti")
    text = text.replace("$", "fí")
    text = text.replace('"vel', "tível")
    text = text.replace('"veis', "tíveis")
    text = text.replace('"co', "tico")
    text = text.replace('"ca', "tica")
    text = re.sub(r'(?<=[A-Za-zÀ-ÿ])!(?=[A-Za-zÀ-ÿ])', "ti", text)
    return text


WORD_FIXES = [
    (r"\bNPé\s*o\b", "NP é o"),
    (r"\bsepreocupe\b", "se preocupe"),
    (r"\bseperde\b", "se perde"),
    (r"\beasutiliza\b", "e as utiliza"),
    (r"\bcarreiravive\b", "carreira vive"),
    (r"\bsobre[- ]?humana\b", "sobrehumana"),
    (r"\bsobre[- ]?humanas\b", "sobrehumanas"),
    (r"\bsobre[- ]?humanos\b", "sobrehumanos"),
    (r"\bmo vaç", "motivaç"),
    (r"\bmo vo\b", "motivo"),
    (r"\bmo vos\b", "motivos"),
    (r"\bmo vado\b", "motivado"),
    (r"\bmo vada\b", "motivada"),
    (r"\bu liza", "utiliza"),
    (r"\bu lizar", "utilizar"),
    (r"\bu lizado", "utilizado"),
    (r"\bu lizados", "utilizados"),
    (r"\bu lizada", "utilizada"),
    (r"\bu lizadas", "utilizadas"),
    (r"\bu lidade", "utilidade"),
    (r"\bu lidades", "utilidades"),
    (r"\ba var\b", "ativar"),
    (r"\bdesa var\b", "desativar"),
    (r"\ba vada\b", "ativada"),
    (r"\ba vado\b", "ativado"),
    (r"\ba vidades\b", "atividades"),
    (r"\bcria vo\b", "criativo"),
    (r"\bcria va\b", "criativa"),
    (r"\bcria vos\b", "criativos"),
    (r"\bcria vas\b", "criativas"),
    (r"\balterna va\b", "alternativa"),
    (r"\balterna vo\b", "alternativo"),
    (r"\balterna vas\b", "alternativas"),
    (r"\balterna vos\b", "alternativos"),
    (r"\bradioa va\b", "radioativa"),
    (r"\btenta va\b", "tentativa"),
    (r"\bgené ca\b", "genética"),
    (r"\bgené co\b", "genético"),
    (r"\bgené cas\b", "genéticas"),
    (r"\bsinté ca\b", "sintética"),
    (r"\bsinté co\b", "sintético"),
    (r"\bsinté cas\b", "sintéticas"),
    (r"\bdomés ca\b", "doméstica"),
    (r"\bmís co\b", "místico"),
    (r"\bmís ca\b", "mística"),
    (r"\bmís cos\b", "místicos"),
    (r"\bmís cas\b", "místicas"),
    (r"\bgalác co\b", "galáctico"),
    (r"\bgalác ca\b", "galáctica"),
    (r"\bgalác cos\b", "galácticos"),
    (r"\bgalác cas\b", "galácticas"),
    (r"\btelepá ca\b", "telepática"),
    (r"\btelepá co\b", "telepático"),
    (r"\bpolí ca\b", "política"),
    (r"\bpolí cas\b", "políticas"),
    (r"\bheroi ca\b", "heroica"),
    (r"\bheroi cas\b", "heroicas"),
    (r"\ben dade\b", "entidade"),
    (r"\ben dades\b", "entidades"),
    (r"\bnega vo\b", "negativo"),
    (r"\bnega vos\b", "negativos"),
    (r"\bdi ceis\b", "difíceis"),
    (r"\bdi cil\b", "difícil"),
    (r'\bdi"ceis\b', "difíceis"),
    (r'\bdi"cil\b', "difícil"),
    (r"\bre rado\b", "retirado"),
    (r"\bre rada\b", "retirada"),
    (r"\bre rar\b", "retirar"),
    (r'\bre"rado\b', "retirado"),
    (r'\bre"rada\b', "retirada"),
    (r'\bre"rar\b', "retirar"),
    (r"\bsubs tu", "substitu"),
    (r'\bsubs"tu', "substitu"),
    (r"\búl mo\b", "último"),
    (r"\brobó co\b", "robótico"),
    (r"\bar sta\b", "artista"),
    (r"\búl mos\b", "últimos"),
]


def fix_words(text: str) -> str:
    text = re.sub(r"\bU liza", "Utiliza", text)
    text = re.sub(r"\bU lizando", "Utilizando", text)
    text = re.sub(r"\bu lize\b", "utilize", text, flags=re.IGNORECASE)
    text = re.sub(r"\bu lizem\b", "utilizem", text, flags=re.IGNORECASE)
    text = re.sub(r"\bu lizá-los\b", "utilizá-los", text, flags=re.IGNORECASE)
    text = re.sub(r"\bpo(?=\s+(?:de|do|da|dos|das|para)\b)", "tipo", text)
    text = re.sub(r"\btrês pos\b", "três tipos", text, flags=re.IGNORECASE)
    text = re.sub(r"\bcada po\b", "cada tipo", text, flags=re.IGNORECASE)
    text = re.sub(r"\bfantás co\b", "fantástico", text, flags=re.IGNORECASE)
    text = re.sub(r"\bfantás ca\b", "fantástica", text, flags=re.IGNORECASE)
    text = re.sub(r"\bfantás cos\b", "fantásticos", text, flags=re.IGNORECASE)
    text = re.sub(r"\bfantás cas\b", "fantásticas", text, flags=re.IGNORECASE)
    text = re.sub(r"\besta s?ti?cas\b", "estatísticas", text, flags=re.IGNORECASE)
    text = re.sub(r"\bes pular\b", "estipular", text, flags=re.IGNORECASE)
    text = re.sub(r"\bgene camente\b", "geneticamente", text, flags=re.IGNORECASE)
    text = re.sub(r"\bcombus\"vel\b", "combustível", text, flags=re.IGNORECASE)
    text = re.sub(r"\bsusce\"vel\b", "suscetível", text, flags=re.IGNORECASE)
    text = re.sub(r"\bdete\"ve\b", "detetive", text, flags=re.IGNORECASE)
    text = re.sub(r"\bques!onad", "questionad", text, flags=re.IGNORECASE)
    text = re.sub(r"\biden!fica", "identifica", text, flags=re.IGNORECASE)
    text = re.sub(r"\bCaracterís!cas\b", "Características", text)
    text = re.sub(r"\bcaracterís!cas\b", "características", text)
    text = re.sub(r"\bmul!plicadores\b", "multiplicadores", text, flags=re.IGNORECASE)
    text = re.sub(r"\b#po\b", "tipo", text, flags=re.IGNORECASE)
    text = re.sub(r"\balterna#vos\b", "alternativos", text, flags=re.IGNORECASE)
    text = re.sub(r"\bcria#vo\b", "criativo", text, flags=re.IGNORECASE)
    text = re.sub(r"\bver#cais\b", "verticais", text, flags=re.IGNORECASE)
    text = re.sub(r"\brajadas ó#cas\b", "rajadas ópticas", text, flags=re.IGNORECASE)
    text = re.sub(r"\bde!ros\b", "de tiros", text, flags=re.IGNORECASE)
    text = re.sub(r"\bdo!tipo\b", "do tipo", text, flags=re.IGNORECASE)
    text = re.sub(r"\bsuper#cie\b", "superfície", text, flags=re.IGNORECASE)
    text = re.sub(r"\bsuper#cies\b", "superfícies", text, flags=re.IGNORECASE)
    text = text.replace("#tipo", "tipo")
    text = re.sub(r"\bu#liza", "utiliza", text, flags=re.IGNORECASE)
    text = re.sub(r"\ban#bios\b", "anfíbios", text, flags=re.IGNORECASE)
    text = re.sub(r"\bso#ware\b", "software", text, flags=re.IGNORECASE)
    text = re.sub(r"\bbene\"cios\b", "benefícios", text, flags=re.IGNORECASE)
    text = re.sub(r"\bmale\"cios\b", "malefícios", text, flags=re.IGNORECASE)
    text = re.sub(r"\bhos\"l\b", "hostil", text, flags=re.IGNORECASE)
    text = re.sub(r"\ban\"gos\b", "antigos", text, flags=re.IGNORECASE)
    text = re.sub(r"\ban\"bias\b", "anfíbias", text, flags=re.IGNORECASE)
    text = re.sub(r"\bdes\"no\b", "destino", text, flags=re.IGNORECASE)
    text = re.sub(r"\bnoarena água\b", "no ar e na água", text, flags=re.IGNORECASE)
    text = re.sub(r"\bpon agudas\b", "pontiagudas", text, flags=re.IGNORECASE)
    text = re.sub(r"\ba#rador\b", "atirador", text, flags=re.IGNORECASE)
    text = re.sub(r"\bportá#l\b", "portátil", text, flags=re.IGNORECASE)
    text = re.sub(r"\bdete#ve\b", "detetive", text, flags=re.IGNORECASE)
    text = re.sub(r"\bu#lidades\b", "utilidades", text, flags=re.IGNORECASE)
    text = re.sub(r"\bDi#cil\b", "Difícil", text)
    text = re.sub(r"\bu#lizando\b", "utilizando", text, flags=re.IGNORECASE)
    text = re.sub(r"\bmo#vo\b", "motivo", text, flags=re.IGNORECASE)
    text = re.sub(r"\ba#nge\b", "atinge", text, flags=re.IGNORECASE)
    text = re.sub(r"\bre#do\b", "retido", text, flags=re.IGNORECASE)
    text = re.sub(r"\besta%sticas\b", "estatísticas", text, flags=re.IGNORECASE)
    text = re.sub(r"\bpredes\"nado\b", "predestinado", text, flags=re.IGNORECASE)
    text = re.sub(r'(?<=[A-Za-zÀ-ÿ])"(?=[A-Za-zÀ-ÿ])', "ti", text)
    text = re.sub(r"\bresistênciatisica\b", "resistência física", text, flags=re.IGNORECASE)
    text = re.sub(r"\ban -gravidade\b", "antigravidade", text, flags=re.IGNORECASE)
    text = re.sub(r"\bman da\b", "mantida", text, flags=re.IGNORECASE)
    text = re.sub(r"\bjus ficando\b", "justificando", text, flags=re.IGNORECASE)
    text = re.sub(r"\bhos s\b", "hostis", text, flags=re.IGNORECASE)
    text = re.sub(r"\bpermi r\b", "permitir", text, flags=re.IGNORECASE)
    text = re.sub(r"\bresis r\b", "resistir", text, flags=re.IGNORECASE)
    text = re.sub(r"\b3131o clima\b", "Modificando o clima", text)
    text = re.sub(r"\bcombustivel\b", "combustível", text, flags=re.IGNORECASE)
    text = re.sub(r"\bSereias ossuem\b", "Sereias possuem", text)
    text = re.sub(r"\bseguílo\b", "segui-lo", text, flags=re.IGNORECASE)
    text = re.sub(r"\bseguilo\b", "segui-lo", text, flags=re.IGNORECASE)
    text = re.sub(r"\bumpode alvo\b", "um alvo", text, flags=re.IGNORECASE)
    text = re.sub(r"\bnavesPara\b", "naves. Para", text)
    text = re.sub(r"\bsão:Caça\b", "são: Caça", text)
    text = re.sub(r"\bTransportadorCaça\b", "Transportador. Caça", text)
    text = re.sub(r"\bBlindagem: a blindagem éa IPda nave\b", "Blindagem: a blindagem é a IP da nave", text)
    text = re.sub(r"\bsuper Messias\b", "Super Messias", text)
    for pattern, replacement in WORD_FIXES:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


def fix_spacing(text: str) -> str:
    text = re.sub(r"(?<=[a-záéíóúãõâêôç])(?=Regra Opcional:)", " ", text)
    text = re.sub(r"(Regra Opcional: Sem Custo)(?=Muitos)", r"\1. ", text)
    text = re.sub(r"(Regra Opcional: Sem Mortes)(?=A maioria)", r"\1. ", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"([.!?])([A-ZÁÉÍÓÚÃÕ])", r"\1 \2", text)
    text = re.sub(r"([a-záéíóúãõç])([A-ZÁÉÍÓÚÃÕ][a-záéíóúãõç]{2,})", r"\1 \2", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def clean_text(text: str) -> str:
    before = text
    text = fix_mojibake(text)
    text = fix_ligatures(text)
    text = fix_words(text)
    text = fix_spacing(text)
    text = text.replace("super Messias", "Super Messias")
    # Avoid accidental duplicated optional-rule paragraphs from extraction.
    repeated = (
        "Regra Opcional: Sem Custo. Muitos poderes do SUPERS utilizam de gasto de WILL temporário "
    )
    if text.count(repeated) > 1:
        first = text.find(repeated)
        second = text.find(repeated, first + len(repeated))
        text = text[:second].rstrip()
    return text if text != before else before


def walk_clean(value: Any, changes: list[dict[str, str]], path: str = "") -> Any:
    if isinstance(value, dict):
        return {key: walk_clean(item, changes, f"{path}/{key}") for key, item in value.items()}
    if isinstance(value, list):
        return [walk_clean(item, changes, f"{path}/{index}") for index, item in enumerate(value)]
    if isinstance(value, str):
        cleaned = clean_text(value)
        if cleaned != value:
            changes.append({"path": path, "before": value, "after": cleaned})
        return cleaned
    return value


def clean_file(path: Path, dry_run: bool = False) -> dict[str, Any]:
    before = json.loads(path.read_text(encoding="utf-8"))
    changes: list[dict[str, str]] = []
    after = walk_clean(deepcopy(before), changes)
    if changes and not dry_run:
        write_json(path, after)
    return {
        "file": str(path.relative_to(ROOT)),
        "changes": len(changes),
        "samples": changes[:25],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    report = {"version": 1, "targets": []}
    for source in TARGETS:
        for directory in PILOT_DIRS:
            path = directory / f"{source}.json"
            if path.exists():
                row = clean_file(path, dry_run=args.dry_run)
                report["targets"].append(row)
                print(f"{row['file']}: {row['changes']} alterações")

    if not args.dry_run:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        write_json(REPORT_PATH, report)
        print(f"Relatório: {REPORT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
