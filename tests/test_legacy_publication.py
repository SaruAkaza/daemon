from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from scripts import build_github_pages_site as pages  # noqa: E402
from scripts import build_pilot_index as pilots  # noqa: E402
from scripts.legacy_publication import (  # noqa: E402
    PublicationBlocked,
    referenced_sources,
    validate_publication,
)
import common  # noqa: E402


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def snapshot(root):
    return {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()}


@pytest.fixture
def publication_tree(tmp_path, monkeypatch):
    data = tmp_path / "data"
    public = tmp_path / "docs" / "assets" / "data"
    manifests = data / "source-manifests"
    inventory = data / "index" / "sources.json"
    source = {
        "id": "synthetic",
        "path": "Livros/synthetic.pdf",
        "extension": ".pdf",
        "sha256": "a" * 64,
    }
    manifest = {
        "schemaVersion": "1.0",
        "sourceId": "synthetic",
        "title": "Synthetic",
        "path": source["path"],
        "extension": ".pdf",
        "sha256": source["sha256"],
        "rightsStatus": "AUTHORIZED",
        "visibility": "public",
        "publicationMode": "FULL_TEXT",
    }
    write_json(inventory, {"sources": [source]})
    write_json(manifests / "synthetic.json", manifest)
    write_json(data / "index" / "area-summary.json", {"readySources": ["synthetic"]})
    write_json(data / "areas" / "poderes.json", {
        "entities": [{"id": "power", "source": "synthetic", "page": 1, "entries": ["SYNTHETIC_FULL_TEXT"]}],
        "sourceParts": [],
    })
    write_json(data / "pilot" / "synthetic.json", {
        "source": "synthetic", "title": "Synthetic", "sourcePath": source["path"],
        "sections": [{"paragraphs": ["SYNTHETIC_FULL_TEXT"]}],
    })
    write_json(public / "areas" / "old.json", {"sentinel": "existing published area"})
    write_json(public / "pilot" / "old.json", {"sentinel": "existing published pilot"})
    monkeypatch.setattr(pages, "ROOT", tmp_path)
    monkeypatch.setattr(pages, "DATA_DIR", data)
    monkeypatch.setattr(pages, "DOCS_DIR", tmp_path / "docs")
    monkeypatch.setattr(pages, "PAGES_DATA_DIR", public)
    monkeypatch.setattr(pilots, "ROOT", tmp_path)
    monkeypatch.setattr(pilots, "PILOT_DIR", data / "pilot")
    monkeypatch.setattr(pilots, "DOCS_PILOT_DIR", public / "pilot")
    monkeypatch.setattr(pilots, "INDEX_PATH", data / "pilot" / "index.json")
    monkeypatch.setattr(pilots, "DOCS_INDEX_PATH", public / "pilot" / "index.json")
    return tmp_path, data, public, manifests, inventory, manifest


@pytest.mark.parametrize("rights", ["AUTHORIZED", "PUBLIC_DOMAIN", "METADATA_ONLY", "PRIVATE", "UNKNOWN"])
@pytest.mark.parametrize("mode", ["FULL_TEXT", "SUMMARY_AND_METADATA", "METADATA_ONLY", "NOT_PUBLIC"])
def test_legacy_raw_copy_requires_public_full_text_rights(publication_tree, rights, mode):
    _, _, _, manifests, inventory, manifest = publication_tree
    manifest.update(rightsStatus=rights, publicationMode=mode)
    write_json(manifests / "synthetic.json", manifest)
    args = dict(inventory_path=inventory, manifests_dir=manifests)
    inputs = [({"source": "synthetic"}, "pilot")]
    if rights in {"AUTHORIZED", "PUBLIC_DOMAIN"} and mode == "FULL_TEXT":
        assert validate_publication(inputs, **args) == {"synthetic"}
    else:
        with pytest.raises(PublicationBlocked, match="FULL_TEXT permission"):
            validate_publication(inputs, **args)


@pytest.mark.parametrize("publisher", [pages.publish, pilots.build_index])
@pytest.mark.parametrize("failure", ["missing", "invalid", "stale_hash", "wrong_path", "wrong_extension", "private_visibility", "duplicate"])
def test_preflight_failure_preserves_all_existing_files(publication_tree, publisher, failure):
    root, _, _, manifests, _, manifest = publication_tree
    path = manifests / "synthetic.json"
    if failure == "missing":
        path.unlink()
    elif failure == "invalid":
        path.write_text("{broken json", encoding="utf-8")
    elif failure == "duplicate":
        write_json(manifests / "duplicate.json", manifest)
    else:
        field, value = {
            "stale_hash": ("sha256", "b" * 64),
            "wrong_path": ("path", "Livros/other-edition.pdf"),
            "wrong_extension": ("extension", ".docx"),
            "private_visibility": ("visibility", "private"),
        }[failure]
        manifest[field] = value
        write_json(path, manifest)
    before = snapshot(root)
    with pytest.raises(PublicationBlocked):
        publisher(manifests_dir=manifests)
    assert snapshot(root) == before


@pytest.mark.parametrize("publisher", [pages.publish, pilots.build_index])
def test_check_only_is_read_only_even_with_permission(publication_tree, publisher):
    root, _, _, manifests, _, _ = publication_tree
    before = snapshot(root)
    publisher(manifests_dir=manifests, check_only=True)
    assert snapshot(root) == before


def test_authorized_areas_preserve_exact_input_bytes_and_remove_stale_files(publication_tree):
    _, data, public, manifests, _, _ = publication_tree
    pages.publish(manifests_dir=manifests)
    assert (public / "areas" / "poderes.json").read_bytes() == (data / "areas" / "poderes.json").read_bytes()
    assert (public / "area-summary.json").read_bytes() == (data / "index" / "area-summary.json").read_bytes()
    assert not (public / "areas" / "old.json").exists()


def test_authorized_pilots_preserve_exact_bytes_and_index(publication_tree):
    _, data, public, manifests, _, _ = publication_tree
    pilots.build_index(manifests_dir=manifests)
    assert (public / "pilot" / "synthetic.json").read_bytes() == (data / "pilot" / "synthetic.json").read_bytes()
    assert (public / "pilot" / "index.json").read_bytes() == (data / "pilot" / "index.json").read_bytes()
    assert not (public / "pilot" / "old.json").exists()


@pytest.mark.parametrize("publisher", [pages, pilots])
def test_publishers_use_the_input_bytes_validated_before_preflight(publication_tree, monkeypatch, publisher):
    _, data, public, manifests, _, _ = publication_tree
    relative = Path("areas/poderes.json") if publisher is pages else Path("pilot/synthetic.json")
    before = (data / relative).read_bytes()
    validator = publisher.validate_publication

    def replace_input_after_check(*args, **kwargs):
        result = validator(*args, **kwargs)
        (data / relative).write_text('{"source": "restricted", "entries": ["UNVALIDATED_SENTINEL"]}', encoding="utf-8")
        return result

    monkeypatch.setattr(publisher, "validate_publication", replace_input_after_check)
    operation = publisher.publish if publisher is pages else publisher.build_index
    operation(manifests_dir=manifests)
    assert (public / relative).read_bytes() == before


def test_pilot_index_is_published_from_memory_without_rereading_canonical_index(publication_tree, monkeypatch):
    _, _, public, manifests, _, _ = publication_tree
    writer = pilots.write_json

    def replace_index_after_write(path, payload):
        writer(path, payload)
        path.write_text('{"sources": [{"source": "restricted"}]}', encoding="utf-8")

    monkeypatch.setattr(pilots, "write_json", replace_index_after_write)
    pilots.build_index(manifests_dir=manifests)
    assert json.loads((public / "pilot" / "index.json").read_text())["sources"][0]["source"] == "synthetic"


@pytest.mark.parametrize("key", ["entities", "sourceParts"])
def test_all_area_items_need_explicit_provenance(publication_tree, key):
    root, data, _, manifests, _, _ = publication_tree
    write_json(data / "areas" / "poderes.json", {"entities": [], "sourceParts": [], key: [{"entries": ["UNATTRIBUTED"]}]})
    before = snapshot(root)
    with pytest.raises(PublicationBlocked, match="provenance"):
        pages.publish(manifests_dir=manifests)
    assert snapshot(root) == before


def test_secondary_source_cannot_borrow_primary_source_permission(publication_tree):
    root, data, _, manifests, _, _ = publication_tree
    write_json(data / "pilot" / "synthetic.json", {
        "source": "synthetic", "title": "Synthetic",
        "sections": [{"provenance": {"source": "restricted"}, "paragraphs": ["RESTRICTED_SENTINEL"]}],
    })
    before = snapshot(root)
    with pytest.raises(PublicationBlocked, match="restricted: absent"):
        pilots.build_index(manifests_dir=manifests)
    assert snapshot(root) == before


@pytest.mark.parametrize("sources", [["other"], [{"sourceId": "other"}], {"other": {"title": "Other"}}])
def test_nested_sources_are_included(sources):
    assert referenced_sources({"source": "synthetic", "sources": sources}, "pilot") == {"synthetic", "other"}


def test_unknown_summary_source_is_checked_even_without_entities(publication_tree):
    _, data, _, manifests, _, _ = publication_tree
    write_json(data / "index" / "area-summary.json", {"readySources": ["synthetic", "unreviewed"]})
    with pytest.raises(PublicationBlocked, match="unreviewed: absent"):
        pages.publish(manifests_dir=manifests)


def test_pilot_source_path_cannot_borrow_permission_for_another_file(publication_tree):
    _, data, _, manifests, _, _ = publication_tree
    write_json(data / "pilot" / "synthetic.json", {
        "source": "synthetic", "title": "Synthetic", "sourcePath": "Livros/synthetic.docx",
    })
    with pytest.raises(PublicationBlocked, match="sourcePath"):
        pilots.build_index(manifests_dir=manifests)


@pytest.mark.parametrize("source_file", ["synthetic.docx", "other-edition.pdf", "../synthetic.pdf"])
def test_pilot_without_source_path_cannot_borrow_rights_for_a_different_filename(publication_tree, source_file):
    _, data, _, manifests, _, _ = publication_tree
    write_json(data / "pilot" / "synthetic.json", {
        "source": "synthetic", "title": "Synthetic", "sourceFile": source_file,
    })
    with pytest.raises(PublicationBlocked, match="sourceFile"):
        pilots.build_index(manifests_dir=manifests)


def test_shared_writer_blocks_individual_generators_before_touching_public_tree(publication_tree, monkeypatch):
    root, _, public, manifests, _, _ = publication_tree
    monkeypatch.setattr(common, "ROOT", root)
    (manifests / "synthetic.json").unlink()
    before = snapshot(root)
    with pytest.raises(PublicationBlocked, match="source manifest required"):
        common.write_json(public / "pilot" / "synthetic.json", {"source": "synthetic"})
    assert snapshot(root) == before


def test_shared_writer_keeps_canonical_output_available_without_public_permission(publication_tree, monkeypatch):
    root, data, _, manifests, _, _ = publication_tree
    monkeypatch.setattr(common, "ROOT", root)
    (manifests / "synthetic.json").unlink()
    common.write_json(data / "pilot" / "new.json", {"source": "synthetic", "entries": ["LOCAL_ONLY"]})
    assert json.loads((data / "pilot" / "new.json").read_text())["entries"] == ["LOCAL_ONLY"]


def test_shared_writer_accepts_authorized_public_pilot_and_index(publication_tree, monkeypatch):
    root, _, public, _, _, _ = publication_tree
    monkeypatch.setattr(common, "ROOT", root)
    common.write_json(public / "pilot" / "synthetic.json", {"source": "synthetic"})
    common.write_json(public / "pilot" / "index.json", {"sources": [{"source": "synthetic"}]})
    assert json.loads((public / "pilot" / "synthetic.json").read_text())["source"] == "synthetic"


def test_public_path_alias_still_requires_permission(publication_tree, monkeypatch):
    root, _, public, manifests, _, _ = publication_tree
    monkeypatch.setattr(common, "ROOT", root)
    (manifests / "synthetic.json").unlink()
    alias = root / "alias"
    try:
        alias.symlink_to(public, target_is_directory=True)
    except OSError:
        pytest.skip("Symlink creation is unavailable on this platform.")
    with pytest.raises(PublicationBlocked, match="source manifest required"):
        common.write_json(alias / "pilot" / "synthetic.json", {"source": "synthetic"})


@pytest.mark.parametrize("publisher", [pages.publish, pilots.build_index])
def test_invalid_manifest_schema_is_blocked(publication_tree, publisher):
    _, _, _, manifests, _, manifest = publication_tree
    manifest.pop("sha256")
    write_json(manifests / "synthetic.json", manifest)
    with pytest.raises(PublicationBlocked, match="Invalid source manifest"):
        publisher(manifests_dir=manifests)


@pytest.mark.parametrize("script", ["build_github_pages_site.py", "build_pilot_index.py"])
def test_cli_preflight_blocks_unmanifested_sources_without_mutation(publication_tree, script):
    root, data, public, manifests, _, _ = publication_tree
    shutil.copytree(ROOT / "scripts", root / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(ROOT / "schemas", root / "schemas")
    (manifests / "synthetic.json").unlink()
    before_data = snapshot(data)
    before_public = snapshot(public)
    result = subprocess.run(
        [sys.executable, str(root / "scripts" / script), "--check-only"],
        capture_output=True, text=True, cwd=root,
    )
    assert result.returncode == 1
    assert "source manifest required" in result.stderr
    assert "Traceback" not in result.stderr
    assert snapshot(data) == before_data
    assert snapshot(public) == before_public
