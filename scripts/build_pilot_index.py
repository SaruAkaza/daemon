from __future__ import annotations

from datetime import datetime
from pathlib import Path

from common import ROOT, read_json, write_json


PILOT_DIR = ROOT / "data" / "pilot"
DOCS_PILOT_DIR = ROOT / "docs" / "assets" / "data" / "pilot"
INDEX_PATH = PILOT_DIR / "index.json"
DOCS_INDEX_PATH = DOCS_PILOT_DIR / "index.json"


def main() -> None:
    sources = []
    for path in sorted(PILOT_DIR.glob("*.json")):
        if path.name == "index.json":
            continue
        payload = read_json(path, {})
        if not payload:
            continue
        sources.append(
            {
                "source": payload["source"],
                "title": payload["title"],
                "file": path.name,
                "status": payload.get("status"),
                "areas": payload.get("areas", []),
            }
        )
    index = {
        "version": 1,
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "sources": sources,
    }
    write_json(INDEX_PATH, index)
    write_json(DOCS_INDEX_PATH, index)
    for path in PILOT_DIR.glob("*.json"):
        if path.name != "index.json":
            write_json(DOCS_PILOT_DIR / path.name, read_json(path, {}))
    print(f"Indexed {len(sources)} pilot sources.")


if __name__ == "__main__":
    main()
