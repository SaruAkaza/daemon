from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any

from scripts.agents.change_set import ChangeSet


@dataclass(frozen=True)
class CandidateArtifact:
    """Immutable representation of a staged candidate file to be written."""
    operation_id: str
    target_path: str
    content_bytes: bytes
    candidate_sha256: str
    encoding: str = "utf-8"
    format: str = "text"


class PatchApplier:
    """Constructs in-memory candidate artifacts from a ChangeSet."""

    def __init__(self) -> None:
        pass

    def construct_candidates(self, change_set: ChangeSet) -> tuple[CandidateArtifact, ...]:
        candidates: list[CandidateArtifact] = []

        for op in change_set.operations:
            if op.encoding.lower() != "utf-8":
                raise ValueError(
                    f"ERR_PATCH_INVALID: Unsupported encoding '{op.encoding}' for op '{op.operation_id}'. Only 'utf-8' is supported."
                )

            if op.format.lower() not in ("text", "json"):
                raise ValueError(
                    f"ERR_PATCH_INVALID: Unsupported format '{op.format}' for op '{op.operation_id}'. Only text formats are supported."
                )

            try:
                content_bytes = op.candidate_content.encode("utf-8")
            except Exception as exc:
                raise ValueError(
                    f"ERR_PATCH_INVALID: Failed to encode content for op '{op.operation_id}': {exc}"
                )

            candidate_sha256 = hashlib.sha256(content_bytes).hexdigest()

            candidates.append(
                CandidateArtifact(
                    operation_id=op.operation_id,
                    target_path=op.target_path,
                    content_bytes=content_bytes,
                    candidate_sha256=candidate_sha256,
                    encoding=op.encoding,
                    format=op.format,
                )
            )

        return tuple(candidates)
