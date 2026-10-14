from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from common import ROOT, write_json

sys.path.insert(0, str(ROOT))
from scripts.legacy_publication import PublicationBlocked, read_publication_input, validate_publication  # noqa: E402


PILOT_DIR = ROOT / "data" / "pilot"
DOCS_PILOT_DIR = ROOT / "docs" / "assets" / "data" / "pilot"
INDEX_PATH = PILOT_DIR / "index.json"
DOCS_INDEX_PATH = DOCS_PILOT_DIR / "index.json"


def build_index(*, manifests_dir: Path, check_only: bool = False) -> None:
    sources = []
    pilots = []
    for path in sorted(PILOT_DIR.glob("*.json")):
        if path.name == "index.json":
            continue
        raw, payload = read_publication_input(path)
        pilots.append((path.name, raw, payload))
    required = validate_publication(
        [(payload, "pilot") for _, _, payload in pilots],
        inventory_path=ROOT / "data" / "index" / "sources.json",
        manifests_dir=manifests_dir,
    )
    for name, _, payload in pilots:
        if not isinstance(payload.get("title"), str) or not payload["title"].strip():
            raise PublicationBlocked(f"Pilot title required: {name}")
        sources.append(
            {
                "source": payload["source"],
                "title": payload["title"],
                "file": name,
                "status": payload.get("status"),
                "areas": payload.get("areas", []),
            }
        )
    if check_only:
        print(f"Publication preflight passed: {len(required)} sources, {len(pilots)} pilots.")
        return
    index = {
        "version": 1,
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "sources": sources,
    }
    index_raw = (json.dumps(index, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    write_json(INDEX_PATH, index)
    DOCS_PILOT_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_INDEX_PATH.write_bytes(index_raw)
    expected = {"index.json", *(name for name, _, _ in pilots)}
    for path in DOCS_PILOT_DIR.glob("*.json"):
        if path.name not in expected:
            path.unlink()
    for name, raw, _ in pilots:
        (DOCS_PILOT_DIR / name).write_bytes(raw)
    print(f"Indexed {len(sources)} pilot sources.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Index and publish legacy pilots with explicit full-text rights.")
    parser.add_argument("--manifests-dir", type=Path, default=ROOT / "data" / "source-manifests")
    parser.add_argument("--check-only", action="store_true", help="Check rights without writing any files.")
    args = parser.parse_args()
    try:
        build_index(manifests_dir=args.manifests_dir, check_only=args.check_only)
    except PublicationBlocked as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
