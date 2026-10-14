from __future__ import annotations

import json
import os
import stat
from pathlib import Path
import pytest

from scripts.agents.canonical_json import compute_input_manifest_hash, sha256_file
from scripts.agents.bundle_exporter import ExecutionBundleExporter, ExecutionBundleExporterError


@pytest.fixture
def sample_request() -> dict:
    return {
        "schemaVersion": "2.0",
        "requestId": "REQ-ANIM-001-EXTRACTION-01",
        "jobId": "JOB-ANIM-001",
        "bookId": "animalidade",
        "targetStage": "extraction",
        "assignedAgent": "extraction-agent",
        "allowedWriteScope": ["data/text/animalidade.txt"],
        "executionProfile": "manual-antigravity",
        "contextPack": {
            "sourceType": "docx",
            "sourcePath": "Livros/word/feito/animalidade.docx",
        },
        "taskInstruction": "Extract and clean text paragraphs from animalidade source.",
        "outputSchemaName": "raw-text-block.schema.json",
        "timeoutSeconds": 300,
    }


def test_exporter_creates_bundle_structure_and_files(tmp_path: Path, sample_request: dict):
    exporter = ExecutionBundleExporter()
    bundle_dir = exporter.export_bundle(sample_request, attempt=1, output_base_dir=tmp_path)

    assert bundle_dir.exists()
    assert bundle_dir.is_dir()
    assert bundle_dir.name.startswith("EB-ANIM-EXTRACTION-att1-")

    # Required files
    assert (bundle_dir / "execution-request.json").exists()
    assert (bundle_dir / "prompt.md").exists()
    assert (bundle_dir / "output-contract.json").exists()
    assert (bundle_dir / "context-manifest.json").exists()
    assert (bundle_dir / "ANTIGRAVITY-INSTRUCTIONS.md").exists()
    assert (bundle_dir / "execution-bundle.json").exists()

    # Subdirectories
    assert (bundle_dir / "context").is_dir()
    assert (bundle_dir / "attachments").is_dir()

    # Verify execution-request.json content
    with open(bundle_dir / "execution-request.json", encoding="utf-8") as f:
        saved_req = json.load(f)
    assert saved_req["requestId"] == sample_request["requestId"]

    for root, _, files in os.walk(bundle_dir):
        for fname in files:
            os.chmod(Path(root) / fname, stat.S_IWRITE | stat.S_IREAD)


def test_exporter_with_source_document(tmp_path: Path, sample_request: dict):
    source_file = tmp_path / "synthetic_source.docx"
    source_file.write_bytes(b"PK\x03\x04fake-docx-content-for-testing")

    exporter = ExecutionBundleExporter()
    out_dir = tmp_path / "bundles"
    bundle_dir = exporter.export_bundle(
        sample_request, attempt=1, output_base_dir=out_dir, source_doc=source_file
    )

    copied_doc = bundle_dir / "attachments" / "synthetic_source.docx"
    assert copied_doc.exists()
    assert copied_doc.read_bytes() == source_file.read_bytes()

    # Verify context-manifest includes attachment
    with open(bundle_dir / "context-manifest.json", encoding="utf-8") as f:
        manifest = json.load(f)

    attachment_items = [it for it in manifest["items"] if "synthetic_source.docx" in it["path"]]
    assert len(attachment_items) == 1
    assert attachment_items[0]["sha256"] == sha256_file(source_file)

    for root, _, files in os.walk(bundle_dir):
        for fname in files:
            os.chmod(Path(root) / fname, stat.S_IWRITE | stat.S_IREAD)


def test_exporter_input_manifest_hash_integrity(tmp_path: Path, sample_request: dict):
    exporter = ExecutionBundleExporter()
    bundle_dir = exporter.export_bundle(sample_request, attempt=1, output_base_dir=tmp_path)

    with open(bundle_dir / "context-manifest.json", encoding="utf-8") as f:
        manifest = json.load(f)

    with open(bundle_dir / "execution-bundle.json", encoding="utf-8") as f:
        envelope = json.load(f)

    expected_hash = compute_input_manifest_hash(manifest)
    assert envelope["inputManifestSha256"] == expected_hash
    assert envelope["executionBundleId"] == bundle_dir.name

    for root, _, files in os.walk(bundle_dir):
        for fname in files:
            os.chmod(Path(root) / fname, stat.S_IWRITE | stat.S_IREAD)


def test_exporter_read_only_permissions(tmp_path: Path, sample_request: dict):
    exporter = ExecutionBundleExporter()
    bundle_dir = exporter.export_bundle(sample_request, attempt=1, output_base_dir=tmp_path)

    target_file = bundle_dir / "prompt.md"
    file_stat = target_file.stat().st_mode
    assert not (file_stat & stat.S_IWUSR)

    for root, _, files in os.walk(bundle_dir):
        for fname in files:
            os.chmod(Path(root) / fname, stat.S_IWRITE | stat.S_IREAD)


def test_exporter_refuses_overwrite_existing_bundle(tmp_path: Path, sample_request: dict):
    exporter = ExecutionBundleExporter()
    bundle_dir = exporter.export_bundle(sample_request, attempt=1, output_base_dir=tmp_path)

    with pytest.raises(ExecutionBundleExporterError):
        exporter.export_bundle(sample_request, attempt=1, output_base_dir=tmp_path)

    for root, _, files in os.walk(bundle_dir):
        for fname in files:
            os.chmod(Path(root) / fname, stat.S_IWRITE | stat.S_IREAD)


def test_render_antigravity_instructions():
    instr = ExecutionBundleExporter.render_antigravity_instructions(
        bundle_id="EB-ANIM-EXTRACTION-att1-a1b2c3d4",
        request_id="REQ-01",
        contract_name="raw-text-block.schema.json",
    )
    assert "EB-ANIM-EXTRACTION-att1-a1b2c3d4" in instr
    assert "REQ-01" in instr
    assert "raw-text-block.schema.json" in instr
    assert "artifacts/" in instr


def test_exporter_with_custom_repo_root_resolves_schemas(tmp_path: Path, sample_request: dict):
    custom_repo = tmp_path / "custom_repo"
    custom_schemas = custom_repo / "schemas"
    custom_schemas.mkdir(parents=True)
    custom_schema_file = custom_schemas / "custom-contract.schema.json"
    custom_schema_file.write_text(json.dumps({"$id": "custom", "type": "object"}), encoding="utf-8")

    req = dict(sample_request)
    req["outputSchemaName"] = "custom-contract.schema.json"

    exporter = ExecutionBundleExporter(repo_root=custom_repo)
    bundle_dir = exporter.export_bundle(req, attempt=1, output_base_dir=tmp_path / "bundles")

    contract_file = bundle_dir / "output-contract.json"
    with open(contract_file, encoding="utf-8") as f:
        contract_data = json.load(f)
    assert contract_data.get("$id") == "custom"

    for root, _, files in os.walk(bundle_dir):
        for fname in files:
            os.chmod(Path(root) / fname, stat.S_IWRITE | stat.S_IREAD)

