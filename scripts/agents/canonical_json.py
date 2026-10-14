from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def canonical_json_bytes(payload: Any) -> bytes:
    """Serializes a Python object to canonical JSON UTF-8 bytes.

    Ensures:
    - UTF-8 encoding without BOM
    - Sorted dictionary keys
    - Compact separators (',', ':') without whitespace
    - Preserves non-ASCII characters (ensure_ascii=False)
    """
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    """Computes hexadecimal SHA-256 digest of raw bytes."""
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    """Computes hexadecimal SHA-256 digest of a file on disk."""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_input_manifest_hash(context_manifest: dict) -> str:
    """Computes canonical hash of context-manifest, excluding temporal fields like createdAt."""
    manifest_copy = dict(context_manifest)
    manifest_copy.pop("createdAt", None)
    return sha256_bytes(canonical_json_bytes(manifest_copy))


def compute_result_manifest_hash(result_manifest: dict) -> str:
    """Computes canonical hash of result-manifest, excluding self-hash references."""
    manifest_copy = dict(result_manifest)
    manifest_copy.pop("resultManifestSha256", None)
    manifest_copy.pop("completedAt", None)
    manifest_copy.pop("createdAt", None)
    return sha256_bytes(canonical_json_bytes(manifest_copy))


def derive_execution_bundle_id(book_id: str, stage: str, attempt: int, content_hash: str) -> str:
    """Derives deterministic execution bundle ID: EB-<BOOK_ID>-<STAGE>-att<N>-<HASH[:8]>."""
    prefix = "EB-ANIM" if book_id == "animalidade" else f"EB-{book_id[:4].upper()}"
    hash_slice = content_hash[:8]
    return f"{prefix}-{stage}-att{attempt}-{hash_slice}"