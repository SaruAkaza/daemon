from __future__ import annotations

import copy
from typing import Any

from scripts.agents.contracts import ContractValidationError, validate_payload
from scripts.agents.orchestrator_state import OrchestratorSelection


class ExecutionRequestBuilderError(RuntimeError):
    """Raised when building an ExecutionRequest fails due to invalid inputs or state."""
    pass


class ExecutionRequestBuilder:
    """Pure, deterministic builder for provider-neutral ExecutionRequest payloads."""

    @staticmethod
    def build_request(
        job: dict[str, Any],
        selection: OrchestratorSelection,
        context_pack: dict[str, Any],
        *,
        execution_profile: str,
        allowed_write_scope: list[str],
        task_instruction: str,
        output_schema_name: str,
        request_id: str | None = None,
        timeout_seconds: int = 300,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Constructs and validates a schema-compliant ExecutionRequest from an approved Orchestrator selection."""
        if not isinstance(job, dict):
            raise ExecutionRequestBuilderError(f"job must be a dict, got {type(job).__name__}")
        if not isinstance(selection, OrchestratorSelection):
            raise ExecutionRequestBuilderError(
                f"selection must be an OrchestratorSelection instance, got {type(selection).__name__}"
            )
        if not isinstance(context_pack, dict):
            raise ExecutionRequestBuilderError(
                f"context_pack must be a dict, got {type(context_pack).__name__}"
            )
        if not isinstance(execution_profile, str) or not execution_profile.strip():
            raise ExecutionRequestBuilderError("execution_profile must be a non-empty string.")
        if not isinstance(allowed_write_scope, list) or not all(isinstance(p, str) and p.strip() for p in allowed_write_scope):
            raise ExecutionRequestBuilderError("allowed_write_scope must be a list of non-empty strings.")
        if not isinstance(task_instruction, str) or not task_instruction.strip():
            raise ExecutionRequestBuilderError("task_instruction must be a non-empty string.")
        if not isinstance(output_schema_name, str) or not output_schema_name.strip():
            raise ExecutionRequestBuilderError("output_schema_name must be a non-empty string.")
        if not isinstance(timeout_seconds, int) or timeout_seconds <= 0:
            raise ExecutionRequestBuilderError("timeout_seconds must be a positive integer.")
        if metadata is not None and not isinstance(metadata, dict):
            raise ExecutionRequestBuilderError(f"metadata must be a dict or None, got {type(metadata).__name__}")

        # Check selection action
        if selection.action != "RUN_STAGE":
            raise ExecutionRequestBuilderError(
                f"Cannot build ExecutionRequest for selection action '{selection.action}'. Expected 'RUN_STAGE'."
            )

        if not selection.stage:
            raise ExecutionRequestBuilderError("Selection with RUN_STAGE action must specify a target stage.")
        if not selection.agent:
            raise ExecutionRequestBuilderError("Selection with RUN_STAGE action must specify an assigned agent.")

        # Validate job against schema
        try:
            validate_payload("agent-job.schema.json", job)
        except ContractValidationError as e:
            raise ExecutionRequestBuilderError(f"Invalid job payload: {e}") from e

        # Validate context_pack against schema
        try:
            validate_payload("context-pack.schema.json", context_pack)
        except ContractValidationError as e:
            raise ExecutionRequestBuilderError(f"Invalid context_pack payload: {e}") from e

        # Check consistency between selection and context_pack
        if context_pack.get("stage") != selection.stage:
            raise ExecutionRequestBuilderError(
                f"Mismatch between selection stage '{selection.stage}' and context_pack stage '{context_pack.get('stage')}'"
            )
        if context_pack.get("agent") != selection.agent:
            raise ExecutionRequestBuilderError(
                f"Mismatch between selection agent '{selection.agent}' and context_pack agent '{context_pack.get('agent')}'"
            )
        if context_pack.get("jobId") != job.get("jobId"):
            raise ExecutionRequestBuilderError(
                f"Mismatch between job jobId '{job.get('jobId')}' and context_pack jobId '{context_pack.get('jobId')}'"
            )

        job_id = job.get("jobId")
        book_id = job.get("bookId")
        if not book_id:
            raise ExecutionRequestBuilderError("job must have a non-empty 'bookId'.")

        target_stage = selection.stage
        assigned_agent = selection.agent

        if request_id is None:
            req_id = f"REQ-{job_id}-{target_stage.upper()}"
        else:
            if not isinstance(request_id, str) or not request_id.strip():
                raise ExecutionRequestBuilderError("request_id must be a non-empty string when provided.")
            req_id = request_id

        req_payload: dict[str, Any] = {
            "schemaVersion": "2.0",
            "requestId": req_id,
            "jobId": job_id,
            "bookId": book_id,
            "targetStage": target_stage,
            "assignedAgent": assigned_agent,
            "allowedWriteScope": copy.deepcopy(allowed_write_scope),
            "executionProfile": execution_profile,
            "contextPack": copy.deepcopy(context_pack),
            "taskInstruction": task_instruction,
            "outputSchemaName": output_schema_name,
            "timeoutSeconds": timeout_seconds,
        }
        if metadata is not None:
            req_payload["metadata"] = copy.deepcopy(metadata)

        # Validate generated request against execution-request schema
        try:
            validate_payload("execution-request.schema.json", req_payload)
        except ContractValidationError as e:
            raise ExecutionRequestBuilderError(f"Generated execution request failed schema validation: {e}") from e

        return req_payload
