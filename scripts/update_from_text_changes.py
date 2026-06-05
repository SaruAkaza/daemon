from __future__ import annotations

import argparse
import subprocess
import sys
import time
from typing import Any

from common import INDEX_DIR, ROOT, TEXT_DIR, read_json, sha256_file, write_json


STATE_PATH = INDEX_DIR / "text-change-state.json"

BASE_REBUILD_COMMANDS = [
    ("books", ["scripts/process_book_batch.py", "--force"]),
    ("source entities", ["scripts/sync_source_entities.py"]),
    ("area catalog", ["scripts/build_area_catalog.py"]),
    ("github pages data", ["scripts/build_github_pages_site.py"]),
]

GRANULAR_REBUILD_COMMANDS = [
    ("extract aprimoramentos", ["scripts/extract_granular_aprimoramentos.py"]),
    ("certify aprimoramentos", ["scripts/certify_aprimoramentos.py"]),
    ("extract kits", ["scripts/extract_granular_kits.py"]),
    ("certify kits", ["scripts/certify_kits.py"]),
    ("extract classes", ["scripts/extract_granular_classes.py"]),
    ("certify classes", ["scripts/certify_classes.py"]),
    ("extract racas/linhagens", ["scripts/extract_granular_racas.py"]),
    ("certify racas/linhagens", ["scripts/certify_racas.py"]),
    ("extract poderes/magias", ["scripts/extract_granular_poderes_magias.py"]),
    ("certify poderes/magias", ["scripts/certify_poderes_magias.py"]),
]

RITUAL_REBUILD_COMMANDS = [
    ("extract rituais", ["scripts/extract_granular_rituais.py"]),
    ("certify rituais", ["scripts/certify_rituais.py"]),
]


def text_hashes() -> dict[str, str]:
    return {path.stem: sha256_file(path) for path in sorted(TEXT_DIR.glob("*.txt"))}


def load_state() -> dict[str, Any]:
    return read_json(STATE_PATH, {"version": 1, "hashes": {}, "initialized": False})


def changed_source_ids(current: dict[str, str], previous: dict[str, str], force: bool) -> tuple[list[str], list[str]]:
    if force:
        return sorted(current), sorted(set(previous) - set(current))
    changed = sorted(source_id for source_id, digest in current.items() if previous.get(source_id) != digest)
    deleted = sorted(set(previous) - set(current))
    return changed, deleted


def run_command(label: str, command: list[str], ids: list[str] | None = None) -> None:
    final_command = [sys.executable, *command]
    if ids is not None:
        final_command.extend(["--ids", *ids])
    print(f"[text-sync] {label}: {' '.join(final_command)}")
    subprocess.run(final_command, cwd=ROOT, check=True)


def rebuild(changed_ids: list[str], granular: bool, include_rituais: bool) -> None:
    run_command("books", ["scripts/process_book_batch.py", "--force"], changed_ids)
    run_command("source entities", ["scripts/sync_source_entities.py"], changed_ids)

    if granular:
        for label, command in GRANULAR_REBUILD_COMMANDS:
            run_command(label, command)
        if include_rituais:
            for label, command in RITUAL_REBUILD_COMMANDS:
                run_command(label, command)

    for label, command in BASE_REBUILD_COMMANDS[2:]:
        run_command(label, command)


def write_state(current: dict[str, str]) -> None:
    write_json(
        STATE_PATH,
        {
            "version": 1,
            "initialized": True,
            "hashes": current,
            "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
        },
    )


def scan_once(granular: bool, include_rituais: bool, force: bool, init_only: bool = False) -> bool:
    state = load_state()
    previous = state.get("hashes", {})
    current = text_hashes()

    if init_only or (not force and not state.get("initialized")):
        write_state(current)
        print(f"[text-sync] Baseline initialized with {len(current)} text file(s).")
        return False

    changed, deleted = changed_source_ids(current, previous, force)

    if deleted:
        print("[text-sync] Text files removed since last scan: " + ", ".join(deleted))

    if not changed:
        write_state(current)
        print("[text-sync] No data/text changes detected.")
        return False

    print(f"[text-sync] Changed text sources: {', '.join(changed)}")
    rebuild(changed, granular=granular, include_rituais=include_rituais)
    write_state(current)
    print("[text-sync] Rebuild complete.")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild generated data when data/text/*.txt changes.")
    parser.add_argument("--watch", action="store_true", help="Keep watching data/text and rebuild after changes.")
    parser.add_argument("--init", action="store_true", help="Initialize the text hash baseline without rebuilding.")
    parser.add_argument("--interval", type=float, default=2.0, help="Watch interval in seconds.")
    parser.add_argument("--force", action="store_true", help="Treat all text files as changed on this run.")
    parser.add_argument(
        "--granular",
        action="store_true",
        help="Also rerun granular extraction/certification before rebuilding the site data.",
    )
    parser.add_argument(
        "--include-rituais",
        action="store_true",
        help="With --granular, also rerun the ritual extraction/certification pass.",
    )
    args = parser.parse_args()

    if args.include_rituais and not args.granular:
        parser.error("--include-rituais requires --granular")

    if not args.watch:
        scan_once(granular=args.granular, include_rituais=args.include_rituais, force=args.force, init_only=args.init)
        return

    print(f"[text-sync] Watching {TEXT_DIR.relative_to(ROOT)} every {args.interval:g}s. Press Ctrl+C to stop.")
    first = True
    try:
        while True:
            scan_once(
                granular=args.granular,
                include_rituais=args.include_rituais,
                force=args.force and first,
                init_only=args.init and first,
            )
            first = False
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n[text-sync] Watch stopped.")


if __name__ == "__main__":
    main()
