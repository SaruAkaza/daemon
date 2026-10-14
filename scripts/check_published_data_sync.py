"""Check existing public assets without rebuilding or publishing any data."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def check_published_data_sync(data_dir: Path, published_dir: Path) -> list[str]:
    source_areas = data_dir / "areas"
    published_areas = published_dir / "areas"
    expected = {path.name for path in source_areas.glob("*.json")}
    actual = {path.name for path in published_areas.glob("*.json")}
    errors: list[str] = []
    if not expected:
        errors.append("No canonical area files found; synchronization cannot be verified.")
    for name in sorted(expected - actual):
        errors.append(f"Missing published area: {name}")
    for name in sorted(actual - expected):
        errors.append(f"Unexpected published area: {name}")
    pairs = [(source_areas / name, published_areas / name) for name in sorted(expected & actual)]
    pairs.append((data_dir / "index" / "area-summary.json", published_dir / "area-summary.json"))
    for source, target in pairs:
        if not source.is_file() or not target.is_file():
            errors.append(f"Missing synchronization input or output: {source.name}")
        elif source.read_bytes() != target.read_bytes():
            errors.append(f"Published file differs from canonical data: {source.name}")
    return errors


def main() -> None:
    errors = check_published_data_sync(ROOT / "data", ROOT / "docs" / "assets" / "data")
    for error in errors:
        print(error)
    if errors:
        raise SystemExit(1)
    count = len(list((ROOT / "data" / "areas").glob("*.json")))
    print(f"Published data synchronized: {count} areas and area summary.")


if __name__ == "__main__":
    main()
