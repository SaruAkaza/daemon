from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.agents.canonical_json import (
    compute_result_manifest_hash,
    sha256_file,
)
from scripts.agents.bundle_importer import ResultBundleEnvelope


DOS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50MB
MAX_BUNDLE_SIZE_BYTES = 200 * 1024 * 1024  # 200MB


@dataclass(frozen=True)
class IntegrityVerdict:
    """Immutable verdict produced by BundleIntegrityValidator."""
    is_valid: bool
    errors: list[str]
    result_manifest_sha256: str
    artifact_hashes: dict[str, str]


class BundleIntegrityValidator:
    """Enforces cryptographic bindings, schema rules, and physical artifact integrity on Result Bundles."""

    @staticmethod
    def _is_safe_relative_path(path_str: str) -> bool:
        """Validates that a path is safe and free of traversal or device injections."""
        if not path_str or not isinstance(path_str, str):
            return False
        # Disallow leading slash, backslashes, colon (ADS/drive letter)
        if path_str.startswith("/") or path_str.startswith("\\") or ":" in path_str:
            return False
        # Check components
        parts = Path(path_str).parts
        for part in parts:
            if part in ("..", ".", ""):
                return False
            stem = part.split(".")[0].upper()
            if stem in DOS_RESERVED_NAMES:
                return False
        return True

    def validate(
        self,
        envelope: ResultBundleEnvelope,
        expected_request_id: str,
        expected_bundle_id: str,
        expected_input_manifest_hash: str,
        expected_execution_bundle_id: str | None = None,
    ) -> IntegrityVerdict:
        """Validates bundle envelope byte-for-byte against expected parameters."""
        errors: list[str] = []
        artifact_hashes: dict[str, str] = {}
        result_manifest_sha256 = ""

        # 1. Validate execution-result.json
        try:
            with open(envelope.execution_result_path, encoding="utf-8") as f:
                exec_res = json.load(f)
            if not isinstance(exec_res, dict):
                errors.append("ERR_RESULT_CONTRACT_INVALID: execution-result.json must be an object")
            else:
                status = exec_res.get("status")
                verdict = exec_res.get("verdict")
                if status != "SUCCESS" and verdict != "ACCEPT":
                    errors.append(f"ERR_RESULT_CONTRACT_INVALID: execution result status '{status or verdict}' is not SUCCESS")
                res_req_id = exec_res.get("requestId")
                if res_req_id != expected_request_id:
                    errors.append(
                        f"ERR_REQUEST_ID_MISMATCH: execution-result requestId '{res_req_id}' != expected '{expected_request_id}'"
                    )
        except Exception as e:
            errors.append(f"ERR_RESULT_BUNDLE_INVALID: Failed to parse execution-result.json: {e}")

        # 2. Validate result-manifest.json
        manifest_data: dict[str, Any] = {}
        try:
            with open(envelope.result_manifest_path, encoding="utf-8") as f:
                manifest_data = json.load(f)
            if not isinstance(manifest_data, dict):
                errors.append("ERR_RESULT_BUNDLE_INVALID: result-manifest.json must be an object")
            else:
                result_manifest_sha256 = compute_result_manifest_hash(manifest_data)

                man_bundle_id = manifest_data.get("resultBundleId")
                if man_bundle_id != expected_bundle_id:
                    errors.append(
                        f"ERR_BUNDLE_ID_MISMATCH: result-manifest bundleId '{man_bundle_id}' != expected '{expected_bundle_id}'"
                    )

                if expected_execution_bundle_id is not None:
                    man_exec_bundle_id = manifest_data.get("executionBundleId")
                    if man_exec_bundle_id != expected_execution_bundle_id:
                        errors.append(
                            f"ERR_BUNDLE_ID_MISMATCH: result-manifest executionBundleId '{man_exec_bundle_id}' != expected '{expected_execution_bundle_id}'"
                        )

                man_req_id = manifest_data.get("requestId")
                if man_req_id != expected_request_id:
                    errors.append(
                        f"ERR_REQUEST_ID_MISMATCH: result-manifest requestId '{man_req_id}' != expected '{expected_request_id}'"
                    )

                man_input_hash = manifest_data.get("inputManifestSha256")
                if man_input_hash != expected_input_manifest_hash:
                    errors.append(
                        f"ERR_INPUT_MANIFEST_HASH_MISMATCH: manifest input hash '{man_input_hash}' != expected '{expected_input_manifest_hash}'"
                    )
        except Exception as e:
            errors.append(f"ERR_RESULT_BUNDLE_INVALID: Failed to parse result-manifest.json: {e}")

        # 3. Validate artifacts declared in manifest
        declared_artifacts = manifest_data.get("artifacts", []) if isinstance(manifest_data, dict) else []
        manifest_artifact_paths: set[str] = set()
        total_bundle_size = 0

        if not isinstance(declared_artifacts, list):
            errors.append("ERR_RESULT_BUNDLE_INVALID: artifacts in manifest must be a list")
        else:
            for item in declared_artifacts:
                if not isinstance(item, dict):
                    errors.append("ERR_RESULT_BUNDLE_INVALID: artifact entry must be an object")
                    continue
                art_path_str = item.get("path", "")
                if not self._is_safe_relative_path(art_path_str):
                    errors.append(f"ERR_RESULT_BUNDLE_INTEGRITY_FAILED: Path traversal or forbidden path detected: '{art_path_str}'")
                    continue

                manifest_artifact_paths.add(art_path_str)
                disk_path = envelope.bundle_dir / art_path_str

                if disk_path.is_symlink():
                    errors.append(f"ERR_RESULT_BUNDLE_INTEGRITY_FAILED: Symlinks prohibited: '{art_path_str}'")
                    continue

                if not disk_path.exists() or not disk_path.is_file():
                    errors.append(f"ERR_MISSING_ARTIFACT: Declared artifact missing on disk: '{art_path_str}'")
                    continue

                file_size = disk_path.stat().st_size
                total_bundle_size += file_size
                if file_size > MAX_FILE_SIZE_BYTES:
                    errors.append(f"ERR_RESULT_BUNDLE_INTEGRITY_FAILED: File size {file_size} exceeds 50MB: '{art_path_str}'")

                actual_hash = sha256_file(disk_path)
                declared_hash = item.get("sha256", "")
                if actual_hash != declared_hash:
                    errors.append(
                        f"ERR_ARTIFACT_HASH_MISMATCH: Artifact '{art_path_str}' hash '{actual_hash}' != declared '{declared_hash}'"
                    )
                artifact_hashes[art_path_str] = actual_hash

        if total_bundle_size > MAX_BUNDLE_SIZE_BYTES:
            errors.append(f"ERR_RESULT_BUNDLE_INTEGRITY_FAILED: Bundle total size {total_bundle_size} exceeds 200MB")

        # 4. Check for orphaned / unexpected artifacts on disk
        if envelope.artifacts_dir.exists():
            for root, _, files in os.walk(envelope.artifacts_dir):
                for fname in files:
                    full_p = Path(root) / fname
                    if full_p.is_symlink():
                        errors.append(f"ERR_RESULT_BUNDLE_INTEGRITY_FAILED: Symlink detected on disk: {full_p}")
                        continue
                    rel_p = full_p.relative_to(envelope.bundle_dir).as_posix()
                    if rel_p not in manifest_artifact_paths:
                        errors.append(f"ERR_UNEXPECTED_ARTIFACT: Untracked artifact on disk: '{rel_p}'")

        is_valid = len(errors) == 0
        return IntegrityVerdict(
            is_valid=is_valid,
            errors=errors,
            result_manifest_sha256=result_manifest_sha256,
            artifact_hashes=artifact_hashes,
        )
