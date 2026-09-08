from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from scripts.agents.application_runtime import ResourceBounds
from scripts.agents.change_set import ChangeOperation, ChangeSet


@dataclass(frozen=True)
class ContentValidationResult:
    """Result of content domain and resource bounds validation."""
    valid: bool
    code: str | None
    reasons: tuple[str, ...]


class ContentValidator:
    """Enforces UTF-8 domain, syntactical validity, and resource bounds on mutations."""

    def __init__(self, bounds: ResourceBounds | None = None) -> None:
        self.bounds = bounds or ResourceBounds()

    def validate_operation_content(self, op: ChangeOperation) -> ContentValidationResult:
        # 1. Encoding check:
        if op.encoding.lower() != "utf-8":
            return ContentValidationResult(
                valid=False,
                code="ERR_UNSUPPORTED_CONTENT_DOMAIN",
                reasons=(f"Encoding must be 'utf-8', got '{op.encoding}'",),
            )

        # 2. UTF-8 content validation and BOM check
        raw_text = op.candidate_content
        if raw_text.startswith("\ufeff"):
            return ContentValidationResult(
                valid=False,
                code="ERR_UNSUPPORTED_CONTENT_DOMAIN",
                reasons=("UTF-8 BOM detected; content must be UTF-8 strictly without BOM.",),
            )

        if "\x00" in raw_text:
            return ContentValidationResult(
                valid=False,
                code="ERR_UNSUPPORTED_CONTENT_DOMAIN",
                reasons=("Null bytes detected in text content.",),
            )

        try:
            content_bytes = raw_text.encode("utf-8")
        except UnicodeEncodeError as exc:
            return ContentValidationResult(
                valid=False,
                code="ERR_UNSUPPORTED_CONTENT_DOMAIN",
                reasons=(f"Content cannot be encoded as UTF-8: {exc}",),
            )

        # Check BOM in bytes just in case
        if content_bytes.startswith(b"\xef\xbb\xbf"):
            return ContentValidationResult(
                valid=False,
                code="ERR_UNSUPPORTED_CONTENT_DOMAIN",
                reasons=("UTF-8 BOM detected; content must be UTF-8 strictly without BOM.",),
            )

        # 3. File size bound check
        if len(content_bytes) > self.bounds.max_file_size_bytes:
            return ContentValidationResult(
                valid=False,
                code="ERR_RESOURCE_BOUND_EXCEEDED",
                reasons=(
                    f"Operation '{op.operation_id}' size ({len(content_bytes)} bytes) exceeds "
                    f"max_file_size_bytes limit ({self.bounds.max_file_size_bytes} bytes)",
                ),
            )

        # 4. JSON syntactic validity check
        target_path_lower = op.target_path.lower()
        if target_path_lower.endswith(".json"):
            try:
                json.loads(raw_text)
            except json.JSONDecodeError as exc:
                return ContentValidationResult(
                    valid=False,
                    code="ERR_PATCH_INVALID",
                    reasons=(f"Malformed JSON in '{op.target_path}': {exc}",),
                )

        return ContentValidationResult(
            valid=True,
            code=None,
            reasons=(),
        )

    def validate_changeset_bounds(self, change_set: ChangeSet) -> ContentValidationResult:
        # Check operation count
        op_count = len(change_set.operations)
        if op_count > self.bounds.max_operations_per_changeset:
            return ContentValidationResult(
                valid=False,
                code="ERR_RESOURCE_BOUND_EXCEEDED",
                reasons=(
                    f"ChangeSet '{change_set.change_set_id}' operation count ({op_count}) exceeds "
                    f"max_operations_per_changeset limit ({self.bounds.max_operations_per_changeset})",
                ),
            )

        # Check total bytes across all operations
        total_bytes = 0
        for op in change_set.operations:
            total_bytes += len(op.candidate_content.encode("utf-8"))

        if total_bytes > self.bounds.max_changeset_size_bytes:
            return ContentValidationResult(
                valid=False,
                code="ERR_RESOURCE_BOUND_EXCEEDED",
                reasons=(
                    f"ChangeSet '{change_set.change_set_id}' total content size ({total_bytes} bytes) exceeds "
                    f"max_changeset_size_bytes limit ({self.bounds.max_changeset_size_bytes} bytes)",
                ),
            )

        return ContentValidationResult(
            valid=True,
            code=None,
            reasons=(),
        )
