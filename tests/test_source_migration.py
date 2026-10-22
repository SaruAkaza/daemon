from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.agents.application_runtime import ResourceBounds  # noqa: E402
from scripts.agents.canonical_json import sha256_bytes  # noqa: E402
from scripts.agents.staging_manager import StagingManager  # noqa: E402
from scripts.prepare_source_migration import (  # noqa: E402
    MigrationPreparationError, PLAN_PATH, page_audit, prepare, stage,
)
from scripts.reconcile_sources import encoded, reconcile, saved_outputs  # noqa: E402


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded(payload))


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file() and ".git" not in p.parts}


def refresh(repo):
    report, manifests = reconcile(repo)
    for path, raw in saved_outputs(repo, report, manifests).items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)


@pytest.fixture
def migration_repo(tmp_path):
    repo = tmp_path / "repository"
    repo.mkdir()
    source = repo / "Livros" / "word" / "feito" / "Synthetic.docx"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"SYNTHETIC_TRACKED_SOURCE")
    write_json(repo / "data/index/sources.json", {"sources": [{
        "id": "synthetic", "path": "Livros/Synthetic.pdf", "sha256": "a" * 64,
    }]})
    write_json(repo / "data/pilot/synthetic.json", {
        "source": "synthetic", "sourceFile": "Synthetic.docx", "sourcePath": "Livros/word/Synthetic.docx",
        "title": "Synthetic", "status": "pilot_review",
        "sections": [{"id": "synthetic--power", "paragraphs": ["SYNTHETIC_RULE_CONTENT"], "cost": 2}],
        "related": {"source": "other-book", "entityId": "other-entity"},
    })
    for args in (["init", "-q"], ["add", "."], ["-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "fixture"]):
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)
    refresh(repo)
    return repo


def save_plan(repo):
    plan, candidates = prepare(repo)
    write_json(repo / PLAN_PATH, plan)
    return plan, candidates


def test_plan_is_read_only_and_preserves_legacy_content_and_ids(migration_repo):
    repo = migration_repo
    before = snapshot(repo)
    plan, candidates = prepare(repo)
    assert snapshot(repo) == before
    original = json.loads((repo / "data/pilot/synthetic.json").read_text())
    candidate = json.loads(candidates[0].content_bytes)
    for key, value in original.items():
        if key not in {"sourcePath", "sourceFile"}:
            assert candidate[key] == value
    assert candidate["sourcePath"] == "Livros/word/feito/Synthetic.docx"
    assert candidate["sourceVariantId"].startswith("file-")
    assert candidate["sourceMigration"]["publicReleaseAllowed"] is False
    assert plan["summary"]["canonicalPromotionCount"] == 0
    assert plan["items"][0]["reviewStatus"] == "NEEDS_HUMAN_REVIEW"
    assert plan["items"][0]["pageAudit"]["status"] == "MISSING_PAGE_CLAIMS"
    assert plan["items"][0]["inputSha256"] == sha256_bytes((repo / "data/pilot/synthetic.json").read_bytes())
    assert candidates[0].candidate_sha256 == sha256_bytes(candidates[0].content_bytes)


def test_missing_pages_are_not_replaced_with_page_one(migration_repo):
    _, candidates = prepare(migration_repo)
    candidate = json.loads(candidates[0].content_bytes)
    assert "page" not in candidate and "pages" not in candidate
    assert "page" not in candidate["sections"][0] and "pages" not in candidate["sections"][0]


@pytest.mark.parametrize("claims", [{"page": 9}, {"pages": [3, 7]}, {"provenance": {"pages": [6]}}, {"sourcePage": 12}])
def test_existing_page_claims_are_preserved_without_reinterpreting_them(migration_repo, claims):
    path = migration_repo / "data/pilot/synthetic.json"
    original = json.loads(path.read_text())
    original["sections"][0].update(claims)
    write_json(path, original)
    refresh(migration_repo)
    plan, candidates = prepare(migration_repo)
    assert json.loads(candidates[0].content_bytes)["sections"] == original["sections"]
    assert plan["items"][0]["pageAudit"]["status"] == "UNVERIFIED_PAGE_CLAIMS"
    assert plan["items"][0]["promotionAllowed"] is False


@pytest.mark.parametrize("claims", [{"page": True}, {"page": 0}, {"page": "9"}, {"pages": []}, {"pages": [1, False]}, {"sourcePage": -1}])
def test_invalid_page_claims_are_explicitly_flagged_and_not_corrected(claims):
    payload = {"sections": [{"paragraphs": ["Synthetic"], **claims}]}
    before = encoded(payload)
    audit = page_audit(payload)
    assert audit["status"] == "INVALID_PAGE_CLAIMS"
    assert audit["invalidPageFieldPaths"]
    assert encoded(payload) == before


def test_nested_page_field_paths_use_json_pointer_escaping():
    audit = page_audit({"a/b~c": {"page": 0}})
    assert audit["invalidPageFieldPaths"] == ["/a~1b~0c/page"]


def test_changed_pilot_requires_fresh_reconciliation(migration_repo):
    path = migration_repo / "data/pilot/synthetic.json"
    data = json.loads(path.read_text())
    data["sections"][0]["cost"] = 3
    write_json(path, data)
    with pytest.raises(MigrationPreparationError, match="reconciliation is stale"):
        prepare(migration_repo)


@pytest.mark.parametrize("key", ["sourceVariantId", "sourceMigration"])
def test_existing_migration_metadata_is_not_silently_overwritten(migration_repo, key):
    path = migration_repo / "data/pilot/synthetic.json"
    data = json.loads(path.read_text())
    data[key] = "existing-review"
    write_json(path, data)
    refresh(migration_repo)
    before = snapshot(migration_repo)
    with pytest.raises(MigrationPreparationError, match="Existing migration metadata"):
        prepare(migration_repo)
    assert snapshot(migration_repo) == before


def test_staging_creates_a_private_verified_package_without_changing_repository(migration_repo, tmp_path):
    plan, candidates = save_plan(migration_repo)
    before = snapshot(migration_repo)
    target = stage(migration_repo, tmp_path / "private-staging")
    assert target.name == sha256_bytes(encoded(plan))
    assert (target / "plan.json").read_bytes() == encoded(plan)
    for candidate in candidates:
        assert (target / "candidates" / f"{candidate.operation_id}.bin").read_bytes() == candidate.content_bytes
    assert snapshot(migration_repo) == before
    assert not (migration_repo / "docs").exists()


def test_repeated_staging_preserves_existing_files_and_timestamps(migration_repo, tmp_path):
    save_plan(migration_repo)
    private = tmp_path / "private-staging"
    first = stage(migration_repo, private)
    before = {str(p.relative_to(first)): (p.read_bytes(), p.stat().st_mtime_ns) for p in first.rglob("*") if p.is_file()}
    assert stage(migration_repo, private) == first
    after = {str(p.relative_to(first)): (p.read_bytes(), p.stat().st_mtime_ns) for p in first.rglob("*") if p.is_file()}
    assert before == after


@pytest.mark.parametrize("relative", [".", "docs/assets/data", "data/pilot", "Livros"])
def test_staging_cannot_write_into_any_repository_directory(migration_repo, relative):
    save_plan(migration_repo)
    before = snapshot(migration_repo)
    with pytest.raises(MigrationPreparationError, match="outside the repository"):
        stage(migration_repo, migration_repo / relative)
    assert snapshot(migration_repo) == before


def test_staging_alias_into_public_assets_is_rejected(migration_repo, tmp_path):
    save_plan(migration_repo)
    public = migration_repo / "docs/assets/data"
    public.mkdir(parents=True)
    alias = tmp_path / "alias"
    try:
        alias.symlink_to(public, target_is_directory=True)
    except OSError:
        pytest.skip("Symlink creation unavailable.")
    with pytest.raises(MigrationPreparationError, match="outside the repository"):
        stage(migration_repo, alias)


def test_modified_staging_package_is_not_overwritten(migration_repo, tmp_path):
    _, candidates = save_plan(migration_repo)
    private = tmp_path / "private-staging"
    target = stage(migration_repo, private)
    candidate = target / "candidates" / f"{candidates[0].operation_id}.bin"
    candidate.write_bytes(b"HUMAN_EDIT")
    before = snapshot(target)
    with pytest.raises(MigrationPreparationError, match="package differs"):
        stage(migration_repo, private)
    assert snapshot(target) == before


def test_other_process_lock_is_preserved(migration_repo, tmp_path):
    plan, _ = save_plan(migration_repo)
    private = tmp_path / "private-staging"
    private.mkdir()
    lock = private / f".{sha256_bytes(encoded(plan))}.lock"
    lock.write_bytes(b"OTHER_PROCESS")
    with pytest.raises(MigrationPreparationError, match="Another process"):
        stage(migration_repo, private)
    assert lock.read_bytes() == b"OTHER_PROCESS"


@pytest.mark.parametrize("bounds", [ResourceBounds(max_operations_per_changeset=0), ResourceBounds(max_file_size_bytes=1), ResourceBounds(max_total_staging_bytes=1)])
def test_resource_bounds_are_checked_before_creating_staging(migration_repo, tmp_path, bounds):
    save_plan(migration_repo)
    private = tmp_path / "private-staging"
    with pytest.raises(MigrationPreparationError, match="resource bounds"):
        stage(migration_repo, private, bounds)
    assert not private.exists()


def test_write_failure_leaves_originals_intact_and_cleans_own_temporary_package(migration_repo, tmp_path, monkeypatch):
    save_plan(migration_repo)
    before = snapshot(migration_repo)
    private = tmp_path / "private-staging"

    def fail_after_partial_write(self, directory, candidates):
        (directory / "candidates/partial.bin").write_bytes(b"PARTIAL")
        raise OSError("simulated disk failure")

    monkeypatch.setattr(StagingManager, "stage_candidates", fail_after_partial_write)
    with pytest.raises(OSError, match="simulated disk failure"):
        stage(migration_repo, private)
    assert snapshot(migration_repo) == before
    assert list(private.iterdir()) == []


def test_stale_plan_after_manifest_decision_is_rejected_without_overwriting_decision(migration_repo, tmp_path):
    save_plan(migration_repo)
    manifest_path = next((migration_repo / "data/source-manifests").glob("*.json"))
    data = json.loads(manifest_path.read_text())
    data.update(rightsStatus="AUTHORIZED", publicationMode="FULL_TEXT", visibility="public")
    write_json(manifest_path, data)
    before = snapshot(migration_repo)
    with pytest.raises(MigrationPreparationError, match="plan is missing or stale"):
        stage(migration_repo, tmp_path / "private-staging")
    assert snapshot(migration_repo) == before
    plan, _ = prepare(migration_repo)
    assert plan["summary"]["canonicalPromotionCount"] == 0


def test_missing_plan_cannot_be_staged(migration_repo, tmp_path):
    with pytest.raises(MigrationPreparationError, match="plan is missing or stale"):
        stage(migration_repo, tmp_path / "private-staging")


def cli(repo, *args):
    return subprocess.run([sys.executable, str(ROOT / "scripts/prepare_source_migration.py"), "--repo-root", str(repo), *args], capture_output=True, text=True)


def test_cli_prepares_then_checks_and_stages_without_canonical_apply(migration_repo):
    before = snapshot(migration_repo)
    assert cli(migration_repo).returncode == 0
    assert cli(migration_repo, "--check").returncode == 1
    assert snapshot(migration_repo) == before
    assert cli(migration_repo, "--write-plan").returncode == 0
    assert cli(migration_repo, "--check").returncode == 0
    after_plan = snapshot(migration_repo)
    result = cli(migration_repo, "--stage")
    assert result.returncode == 0, result.stderr
    assert "Private review package:" in result.stdout
    assert snapshot(migration_repo) == after_plan
    assert cli(migration_repo, "--apply").returncode != 0
    assert snapshot(migration_repo) == after_plan
