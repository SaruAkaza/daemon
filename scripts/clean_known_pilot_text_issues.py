from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from common import ROOT, write_json


TARGETS = [
    "4killers",
    "abismo-infinito-quick-start",
    "alianca-daemon-01",
    "animalidade",
]

PILOT_DIRS = [
    ROOT / "data" / "pilot",
    ROOT / "docs" / "assets" / "data" / "pilot",
]

REPORT_PATH = ROOT / "data" / "work" / "known-pilot-text-cleanup-report.json"


REPLACEMENTS = [
    ("ArmasBrancas(todas)100/100,artesmarciais75/50,furtividade100", "Armas Brancas (todas) 100/100, artes marciais 75/50, furtividade 100"),
    ("www.seculargames.comA primeira", "www.seculargames.com. A primeira"),
    ("primeiro lugar.www.seculargames.com", "primeiro lugar. www.seculargames.com"),
    ("www. salacentoeum.com", "www.salacentoeum.com"),
    ("VMosjogadoresvivenciarão", "VM os jogadores vivenciarão"),
    ("contosdefadas", "contos de fadas"),
    ("CortezJohnExobiólogo", "Cortez. John, Exobiólogo. "),
    ('Exobiólogo"Um dia', 'Exobiólogo. "Um dia'),
    ("queeu", "que eu"),
    ('década"Medo', 'década". Medo'),
    ("maisrever", "mais rever"),
    ("filhos;Meus", "filhos; meus"),
    ("irmãoBRIAN", "irmão. Brian"),
    ("22332233nomE:CaRgo:CITação:jogadoR:SonolênCIamEdo PaRTICUlaRfERImEnToSânCoRaSS. B. Cortez. ", ""),
]


def clean_text(text: str) -> str:
    for before, after in REPLACEMENTS:
        text = text.replace(before, after)
    return text


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
        "samples": changes[:20],
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
                print(f"{row['file']}: {row['changes']} alteracoes")

    if not args.dry_run:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        write_json(REPORT_PATH, report)
        print(f"Relatorio: {REPORT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
