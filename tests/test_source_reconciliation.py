from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.agents.contracts import validate_payload  # noqa: E402
from scripts.reconcile_sources import (  # noqa: E402
    ReconciliationError,
    encoded,
    reconcile,
    saved_outputs,
    source_path,
)


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded(payload))


def git(repo, *args):
    return subprocess.check_output(["git", *args], cwd=repo, stderr=subprocess.DEVNULL, text=True).strip()


def snapshot(repo):
    return {str(p.relative_to(repo)): p.read_bytes() for p in repo.rglob("*") if p.is_file() and ".git" not in p.parts}


@pytest.fixture
def source_repo(tmp_path):
    git(tmp_path, "init", "-q")
    path = tmp_path / "Livros" / "word" / "feito" / "Synthetic.docx"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"SYNTHETIC_SOURCE_BYTES")
    write_json(tmp_path / "data" / "index" / "sources.json", {"sources": [{
        "id": "synthetic", "title": "Synthetic", "path": "Livros/Synthetic.pdf",
        "extension": ".pdf", "sha256": "a" * 64,
    }]})
    write_json(tmp_path / "data" / "pilot" / "synthetic.json", {
        "source": "synthetic", "title": "Synthetic", "sourceFile": "Synthetic.docx",
        "sourcePath": "Livros\\word\\feito\\Synthetic.docx",
    })
    git(tmp_path, "add", ".")
    git(tmp_path, "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "fixture")
    return tmp_path, path


def test_reconciliation_identifies_actual_bytes_without_renaming_legacy_ids(source_repo):
    repo, path = source_repo
    before = snapshot(repo)
    report, manifests = reconcile(repo)
    assert snapshot(repo) == before
    assert report["summary"]["inventoryPathsAbsent"] == 1
    assert report["summary"]["identifiedPilotCount"] == 1
    row = report["pilotReview"][0]
    assert row["legacySourceId"] == "synthetic"
    assert row["matchMethod"] == "EXACT_PATH"
    assert row["reviewStatus"] == "NEEDS_HUMAN_REVIEW"
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = manifests[f"file-{digest}"]
    assert manifest["path"] == "Livros/word/feito/Synthetic.docx"
    assert manifest["sha256"] == digest
    assert manifest["rightsStatus"] == "UNKNOWN"
    assert manifest["visibility"] == "private"
    assert manifest["publicationMode"] == "NOT_PUBLIC"
    validate_payload("source-manifest.schema.json", manifest)


def test_code_only_commits_do_not_invalidate_source_tree_report(source_repo):
    repo, _ = source_repo
    before, _ = reconcile(repo)
    (repo / "new_script.py").write_text("pass\n", encoding="utf-8")
    git(repo, "add", "new_script.py")
    git(repo, "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "code only")
    after, _ = reconcile(repo)
    assert before == after


@pytest.mark.parametrize("old_path", [None, "Livros/word/Synthetic.docx"])
def test_unique_filename_is_review_candidate_for_missing_or_moved_path(source_repo, old_path):
    repo, _ = source_repo
    payload = {"source": "synthetic", "sourceFile": "Synthetic.docx"}
    if old_path:
        payload["sourcePath"] = old_path
    write_json(repo / "data" / "pilot" / "synthetic.json", payload)
    report, _ = reconcile(repo)
    assert report["pilotReview"][0]["matchMethod"] == "UNIQUE_FILENAME"
    assert report["pilotReview"][0]["reviewStatus"] == "NEEDS_HUMAN_REVIEW"


def test_conflicting_path_and_filename_do_not_select_either_source(source_repo):
    repo, _ = source_repo
    write_json(repo / "data" / "pilot" / "synthetic.json", {
        "source": "synthetic", "sourcePath": "Livros/word/feito/Synthetic.docx", "sourceFile": "Other.docx",
    })
    report, manifests = reconcile(repo)
    assert report["pilotReview"][0]["status"] == "CONFLICTING_PROVENANCE"
    assert manifests == {}


def test_ambiguous_filename_never_uses_first_match(source_repo):
    repo, _ = source_repo
    other = repo / "Livros" / "word" / "Synthetic.docx"
    other.write_bytes(b"DIFFERENT_EDITION")
    git(repo, "add", "Livros")
    git(repo, "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "other edition")
    write_json(repo / "data" / "pilot" / "synthetic.json", {"source": "synthetic", "sourceFile": "Synthetic.docx"})
    report, manifests = reconcile(repo)
    assert report["pilotReview"][0]["status"] == "AMBIGUOUS_FILENAME"
    assert len(report["pilotReview"][0]["candidatePaths"]) == 2
    assert manifests == {}


def test_untracked_file_does_not_establish_source_identity(source_repo):
    repo, _ = source_repo
    untracked = repo / "Livros" / "word" / "Untracked.docx"
    untracked.write_bytes(b"UNTRACKED")
    write_json(repo / "data" / "pilot" / "synthetic.json", {"source": "synthetic", "sourceFile": "Untracked.docx"})
    report, manifests = reconcile(repo)
    assert report["pilotReview"][0]["status"] == "SOURCE_NOT_FOUND"
    assert manifests == {}


def test_sparse_checkout_omission_is_distinct_from_missing_source(source_repo):
    repo, path = source_repo
    path.unlink()
    report, manifests = reconcile(repo)
    assert report["pilotReview"][0]["status"] == "SOURCE_NOT_MATERIALIZED"
    assert report["pilotReview"][0]["candidatePaths"] == ["Livros/word/feito/Synthetic.docx"]
    assert manifests == {}


def test_modified_source_cannot_be_certified_against_git_tree(source_repo):
    repo, path = source_repo
    path.write_bytes(b"MODIFIED_SOURCE")
    with pytest.raises(ReconciliationError, match="differs from committed"):
        reconcile(repo)


def test_symlink_cannot_certify_source_custody(source_repo):
    repo, path = source_repo
    raw = path.read_bytes()
    outside = repo / "outside.docx"
    outside.write_bytes(raw)
    path.unlink()
    try:
        path.symlink_to(outside)
    except OSError:
        pytest.skip("Symlink creation is unavailable on this platform.")
    with pytest.raises(ReconciliationError, match="Symlink"):
        reconcile(repo)


@pytest.mark.parametrize("path", ["../outside.docx", "/Livros/a.docx", "Livros/../a.docx", "Livros//a.docx", "C:\\Livros\\a.docx"])
def test_source_paths_cannot_escape_or_obscure_source_root(path):
    with pytest.raises(ReconciliationError):
        source_path(path)


def test_duplicate_inventory_id_is_a_conflict(source_repo):
    repo, _ = source_repo
    path = repo / "data" / "index" / "sources.json"
    data = json.loads(path.read_text())
    data["sources"].append(data["sources"][0])
    write_json(path, data)
    with pytest.raises(ReconciliationError, match="Duplicate inventory"):
        reconcile(repo)


def test_inventory_filename_similarity_is_never_promoted_to_identity(source_repo):
    repo, _ = source_repo
    report, _ = reconcile(repo)
    assert report["inventoryReview"][0]["candidatePaths"] == ["Livros/word/feito/Synthetic.docx"]
    assert report["inventoryReview"][0]["sourceId"] == "synthetic"
    assert report["inventoryReview"][0]["reviewStatus"] == "NEEDS_HUMAN_REVIEW"


def test_existing_human_rights_decision_is_preserved_byte_for_byte(source_repo):
    repo, _ = source_repo
    report, manifests = reconcile(repo)
    source_id, manifest = next(iter(manifests.items()))
    approved = {**manifest, "rightsStatus": "AUTHORIZED", "publicationMode": "FULL_TEXT", "visibility": "public"}
    path = repo / "data" / "source-manifests" / "human-approved.json"
    write_json(path, approved)
    before = path.read_bytes()
    outputs = saved_outputs(repo, report, manifests)
    assert outputs[path] == before
    assert not (repo / "data" / "source-manifests" / f"{source_id}.json").exists()


def test_conflicting_existing_manifest_is_rejected_before_any_writes(source_repo):
    repo, _ = source_repo
    report, manifests = reconcile(repo)
    manifest = next(iter(manifests.values()))
    write_json(repo / "data" / "source-manifests" / "conflict.json", {**manifest, "sha256": "b" * 64})
    before = snapshot(repo)
    with pytest.raises(ReconciliationError, match="identity conflicts"):
        saved_outputs(repo, report, manifests)
    assert snapshot(repo) == before


def test_duplicate_manifest_ids_are_rejected(source_repo):
    repo, _ = source_repo
    report, manifests = reconcile(repo)
    manifest = next(iter(manifests.values()))
    for name in ("one.json", "two.json"):
        write_json(repo / "data" / "source-manifests" / name, manifest)
    with pytest.raises(ReconciliationError, match="Duplicate source manifest"):
        saved_outputs(repo, report, manifests)


def run_cli(repo, *args):
    return subprocess.run([sys.executable, str(ROOT / "scripts" / "reconcile_sources.py"), "--repo-root", str(repo), *args], capture_output=True, text=True)


def test_cli_default_and_check_do_not_write_and_write_is_repeatable(source_repo):
    repo, _ = source_repo
    before = snapshot(repo)
    assert run_cli(repo).returncode == 0
    assert snapshot(repo) == before
    assert run_cli(repo, "--check").returncode == 1
    assert snapshot(repo) == before
    assert run_cli(repo, "--write").returncode == 0
    after = snapshot(repo)
    assert before.items() <= after.items()
    assert run_cli(repo, "--check").returncode == 0
    assert run_cli(repo, "--write").returncode == 0
    assert snapshot(repo) == after


def test_cli_check_detects_changed_pilot_input_without_overwriting_report(source_repo):
    repo, _ = source_repo
    assert run_cli(repo, "--write").returncode == 0
    path = repo / "data" / "pilot" / "synthetic.json"
    payload = json.loads(path.read_text())
    payload["title"] = "Revised title"
    write_json(path, payload)
    before = snapshot(repo)
    result = run_cli(repo, "--check")
    assert result.returncode == 1
    assert "stale reconciliation" in result.stderr
    assert snapshot(repo) == before
