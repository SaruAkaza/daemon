from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from scripts.agents.context_materializer import MaterializedContext
from scripts.agents.contracts import ContractValidationError, validate_payload


class PromptRendererError(RuntimeError):
    """Raised when prompt rendering fails due to invalid inputs or missing data."""
    pass


@dataclass(frozen=True)
class RenderedPrompt:
    """Immutable rendered prompt composed of system instruction, user content, and metadata."""
    system_instruction: str
    user_content: str
    metadata: dict[str, Any]


class PromptRenderer:
    """Deterministic, side-effect-free component that renders layered prompts from ExecutionRequest and MaterializedContext."""

    def __init__(self) -> None:
        pass

    def render(
        self,
        request: dict[str, Any],
        materialized: MaterializedContext,
        agent_contract_text: str | None = None,
    ) -> RenderedPrompt:
        """Deterministically renders layered prompt ready for model execution.

        Raises:
            PromptRendererError: If request or materialized context is invalid.
        """
        if not isinstance(request, dict):
            raise PromptRendererError(f"request must be a dict, got {type(request).__name__}")
        if not isinstance(materialized, MaterializedContext):
            raise PromptRendererError(
                f"materialized must be a MaterializedContext instance, got {type(materialized).__name__}"
            )

        try:
            validate_payload("execution-request.schema.json", request)
        except ContractValidationError as e:
            raise PromptRendererError(f"Execution request failed schema validation: {e}") from e

        agent = request["assignedAgent"]
        stage = request["targetStage"]
        job_id = request["jobId"]
        book_id = request["bookId"]
        req_id = request["requestId"]
        execution_profile = request["executionProfile"]
        task_instruction = request["taskInstruction"]
        allowed_write_scope = request["allowedWriteScope"]
        output_schema_name = request["outputSchemaName"]

        # --- 1. Compose System Instruction ---
        sys_parts: list[str] = []

        sys_parts.append(f"# SPECIALIST AGENT ROLE: {agent.upper()}")
        sys_parts.append(f"Target Pipeline Stage: `{stage}`")
        if agent_contract_text:
            sys_parts.append(f"## Specialist Contract\n{agent_contract_text.strip()}")

        sys_parts.append("## Inviolable Constitutional Principles")
        mandatory_items = materialized.layers.get("mandatory", ())
        if mandatory_items:
            for item in mandatory_items:
                sys_parts.append(f"### File: `{item['path']}`\n{item['content'].strip()}")
        else:
            sys_parts.append("- Non-invention: Never invent rules, mechanics, or omissions.")
            sys_parts.append("- Provenance: Always preserve and cite source and page.")
            sys_parts.append("- Total Coverage: Every processed page must have explicit coverage.")
            sys_parts.append("- Uncertainty: Record ambiguities as uncertainties rather than fabricating conclusions.")

        system_instruction = "\n\n".join(sys_parts)

        # --- 2. Compose User Content ---
        user_parts: list[str] = []

        user_parts.append(f"# WORK ORDER: {req_id}")
        user_parts.append(f"- **Job ID**: `{job_id}`\n- **Book ID**: `{book_id}`\n- **Stage**: `{stage}`\n- **Assigned Agent**: `{agent}`")

        user_parts.append(f"## Task Instruction\n{task_instruction.strip()}")

        task_meta = materialized.metadata.get("task", {})
        if task_meta:
            user_parts.append(f"## Task Parameters & Scope\n```json\n{json.dumps(task_meta, indent=2, ensure_ascii=False)}\n```")

        user_parts.append("## Allowed Write Scope (Strict Boundaries)")
        user_parts.append("You are strictly authorized to propose changes ONLY to the following relative paths:")
        for path in allowed_write_scope:
            user_parts.append(f"- `{path}`")
        user_parts.append("Any attempt to propose artifacts outside these paths will be rejected immediately.")

        # Domain Rules
        domain_items = materialized.layers.get("domain", ())
        if domain_items:
            user_parts.append("## Domain Rules & Reference Context")
            for item in domain_items:
                user_parts.append(f"### Domain File: `{item['path']}`\n{item['content'].strip()}")

        # Book & Job Context
        book_items = materialized.layers.get("bookContext", ())
        if book_items:
            user_parts.append("## Book Context")
            for item in book_items:
                user_parts.append(f"### Book File: `{item['path']}`\n{item['content'].strip()}")

        job_items = materialized.layers.get("jobContext", ())
        if job_items:
            user_parts.append("## Job Context & Queues")
            for item in job_items:
                user_parts.append(f"### Job File: `{item['path']}`\n{item['content'].strip()}")

        handoff_items = materialized.layers.get("handoffContext", ())
        if handoff_items:
            user_parts.append("## Prior Stage Handoffs")
            for item in handoff_items:
                user_parts.append(f"### Handoff File: `{item['path']}`\n{item['content'].strip()}")

        # Output Contract & Expectations
        user_parts.append(f"## Expected Output Contract: `{output_schema_name}`")
        output_contracts = materialized.layers.get("outputContract", ())
        if output_contracts:
            for item in output_contracts:
                user_parts.append(f"### Schema Definition (`{item['path']}`)\n```json\n{item['content'].strip()}\n```")

        user_parts.append("## Output Requirements")
        user_parts.append("1. Provide proposed artifacts in valid format matching the specified schema.")
        user_parts.append("2. Include explicit evidence records citing book and page numbers.")
        user_parts.append("3. If any detail is missing, ambiguous, or unverifiable in the original text, document it in `uncertainties`.")

        user_content = "\n\n".join(user_parts)

        meta: dict[str, Any] = {
            "requestId": req_id,
            "jobId": job_id,
            "agent": agent,
            "stage": stage,
            "executionProfile": execution_profile,
        }

        return RenderedPrompt(
            system_instruction=system_instruction,
            user_content=user_content,
            metadata=meta,
        )
