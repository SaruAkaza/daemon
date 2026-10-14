from pathlib import Path

import pytest

from scripts.check_published_data_sync import check_published_data_sync


@pytest.fixture
def synchronized_data(tmp_path):
    data = tmp_path / "data"
    public = tmp_path / "public"
    for root in (data, public):
        (root / "areas").mkdir(parents=True)
        (root / "areas" / "synthetic.json").write_text('{"items": []}', encoding="utf-8")
    (data / "index").mkdir()
    for path in (data / "index" / "area-summary.json", public / "area-summary.json"):
        path.write_text('{"count": 0}', encoding="utf-8")
    return data, public


def test_identical_existing_assets_pass(synchronized_data):
    assert check_published_data_sync(*synchronized_data) == []


@pytest.mark.parametrize("fault", ["missing", "unexpected", "changed"])
def test_public_drift_is_rejected_without_modifying_files(synchronized_data, fault):
    data, public = synchronized_data
    target = public / "areas" / "synthetic.json"
    if fault == "missing":
        target.unlink()
    elif fault == "unexpected":
        (public / "areas" / "stale.json").write_text("{}", encoding="utf-8")
    else:
        target.write_text('{"items": ["synthetic"]}', encoding="utf-8")
    before = {str(path): path.read_bytes() for root in (data, public) for path in root.rglob("*.json")}
    assert check_published_data_sync(data, public)
    after = {str(path): path.read_bytes() for root in (data, public) for path in root.rglob("*.json")}
    assert after == before


def test_missing_canonical_data_cannot_pass(tmp_path: Path):
    assert check_published_data_sync(tmp_path / "missing-data", tmp_path / "missing-public")
