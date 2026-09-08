from __future__ import annotations

import copy
from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Any

from scripts.agents.contracts import validate_payload
from scripts.agents.execution_validator import (
    ExecutionResultValidator,
    ExecutionValidationVerdict,
)


@dataclass(frozen=True)
class ChangeOperation:
    """Immutable single atomic filesystem operation proposed for execution."""
    operation_id: str
    type: str  # "CREATE" | "UPDATE"
    target_path: str
    expected_base_sha256: str | None
    candidate_content: str
    encoding: str = "utf-8"
    format: str = "text"

    def to_dict(self) -> dict[str, Any]:
        return {
            "operationId": self.operation_id,
            "type": self.type,
            "targetPath": self.target_path,
            "expectedBaseSha256": self.expected_base_sha256,
            "candidateContent": self.candidate_content,
            "encoding": self.encoding,
            "format": self.format,
        }


@dataclass(frozen=True)
class ChangeSet:
    """Immutable manifest of validated filesystem mutations correlated with an ExecutionResult."""
    change_set_id: str
    request_id: str
    job_id: str
    book_id: str
    stage: str
    agent: str
    operations: tuple[ChangeOperation, ...]
    metadata: dict[str, Any]
    schema_version: str = "2.1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "changeSetId": self.change_set_id,
            "requestId": self.request_id,
            "jobId": self.job_id,
            "bookId": self.book_id,
            "stage": self.stage,
            "agent": self.agent,
            "operations": [op.to_dict() for op in self.operations],
            "metadata": dict(self.metadata),
        }


class ChangeSetBuilder:
    """Deterministic builder constructing an immutable ChangeSet from an ACCEPTed ExecutionResult."""

    def __init__(
        self,
        repo_root: Path | str,
        validator: ExecutionResultValidator | None = None,
    ) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.validator = validator or ExecutionResultValidator()

    def build(
        self,
        request: dict[str, Any],
        result: dict[str, Any],
        verdict: ExecutionValidationVerdict | None = None,
    ) -> ChangeSet:
        """Builds a deterministic ChangeSet from request and ACCEPTed result.

        Raises:
            ValueError: If inputs are invalid or verdict is not ACCEPT.
        """
        if not isinstance(request, dict):
            raise ValueError(f"request must be a dict, got {type(request).__name__}")
        if not isinstance(result, dict):
            raise ValueError(f"result must be a dict, got {type(result).__name__}")

        # Validate schemas of input payloads
        validate_payload("execution-request.schema.json", request)
        validate_payload("execution-result.schema.json", result)

        # Enforce ACCEPT boundary
        active_verdict = verdict
        if active_verdict is None:
            active_verdict = self.validator.validate(result, request)

        if active_verdict.verdict != "ACCEPT":
            raise ValueError(
                f"Cannot build ChangeSet: ExecutionResult was not ACCEPTed (verdict: {active_verdict.verdict}, reasons: {active_verdict.reasons})"
            )

        proposed_artifacts = result.get("proposedArtifacts", {})
        if not isinstance(proposed_artifacts, dict):
            raise ValueError("proposedArtifacts must be a dict")

        # Deterministic sorting by normalized path
        sorted_items = sorted(
            proposed_artifacts.items(),
            key=lambda item: item[0].strip().replace("\\", "/"),
        )

        operations_list: list[ChangeOperation] = []
        for idx, (raw_path, content) in enumerate(sorted_items, start=1):
            norm_path = raw_path.strip().replace("\\", "/")
            if not isinstance(content, str):
                raise ValueError(f"Artifact content for '{raw_path}' must be string, got {type(content).__name__}")

            target_file = self.repo_root / norm_path
            op_format = "json" if norm_path.lower().endswith(".json") else "text"

            if target_file.is_file():
                current_bytes = target_file.read_bytes()
                base_sha = hashlib.sha256(current_bytes).hexdigest()
                op_type = "UPDATE"
            else:
                base_sha = None
                op_type = "CREATE"

            op = ChangeOperation(
                operation_id=f"OP-{idx:03d}",
                type=op_type,
                target_path=norm_path,
                expected_base_sha256=base_sha,
                candidate_content=content,
                encoding="utf-8",
                format=op_format,
            )
            operations_list.append(op)

        change_set_id = f"CS-{request['requestId']}"
        cs = ChangeSet(
            change_set_id=change_set_id,
            request_id=request["requestId"],
            job_id=request["jobId"],
            book_id=request["bookId"],
            stage=request["targetStage"],
            agent=request["assignedAgent"],
            operations=tuple(operations_list),
            metadata={
                "executionId": result.get("executionId", ""),
                "builtFromStatus": result.get("status", ""),
            },
        )

        # Validate resulting payload against change-set schema
        validate_payload("change-set.schema.json", cs.to_dict())
        return cs
