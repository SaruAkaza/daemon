from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from common import DATA_DIR, ROOT

sys.path.insert(0, str(ROOT))
from scripts.legacy_publication import PublicationBlocked, read_publication_input, validate_publication  # noqa: E402


DOCS_DIR = ROOT / "docs"
PAGES_DATA_DIR = DOCS_DIR / "assets" / "data"


def publish(*, manifests_dir: Path, check_only: bool = False) -> None:
    # Keep the exact bytes checked by preflight; do not reread inputs afterwards.
    summary_raw, summary = read_publication_input(DATA_DIR / "index" / "area-summary.json")
    areas = []
    for source in sorted((DATA_DIR / "areas").glob("*.json")):
        raw, payload = read_publication_input(source)
        areas.append((source.name, raw, payload))
    if not areas:
        raise PublicationBlocked("No area files found; publication cannot be verified.")
    sources = validate_publication(
        [(summary, "area-summary"), *((payload, "area") for _, _, payload in areas)],
        inventory_path=DATA_DIR / "index" / "sources.json",
        manifests_dir=manifests_dir,
    )
    if check_only:
        print(f"Publication preflight passed: {len(sources)} sources, {len(areas)} areas.")
        return

    PAGES_DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / ".nojekyll").touch()

    (PAGES_DATA_DIR / "area-summary.json").write_bytes(summary_raw)

    areas_target = PAGES_DATA_DIR / "areas"
    if areas_target.exists():
        shutil.rmtree(areas_target)
    areas_target.mkdir(parents=True, exist_ok=True)

    for name, raw, _ in areas:
        (areas_target / name).write_bytes(raw)

    print(f"GitHub Pages data copied to {PAGES_DATA_DIR.relative_to(ROOT)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish legacy areas only with explicit full-text rights.")
    parser.add_argument("--manifests-dir", type=Path, default=DATA_DIR / "source-manifests")
    parser.add_argument("--check-only", action="store_true", help="Check rights without writing any files.")
    args = parser.parse_args()
    try:
        publish(manifests_dir=args.manifests_dir, check_only=args.check_only)
    except PublicationBlocked as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
