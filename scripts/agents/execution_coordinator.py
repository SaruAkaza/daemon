from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from scripts.agents.context_materializer import ContextMaterializer
from scripts.agents.contracts import ContractValidationError, validate_payload
from scripts.agents.execution_adapter import ExecutionAdapter, RawExecutionResponse
from scripts.agents.execution_profile import ExecutionProfile
from scripts.agents.execution_validator import (
    ExecutionResultValidator,
    ExecutionValidationVerdict,
)
from scripts.agents.gate_engine import PIPELINE_STAGES
from scripts.agents.prompt_renderer import PromptRenderer
from scripts.agents.repair_engine import StructuralRepairEngine


@dataclass(frozen=True)
class ExecutionCoordinationResult:
    """Immutable result of an in-memory execution coordination cycle."""
    request: dict[str, Any]
    raw_response: RawExecutionResponse
    result: dict[str, Any]
    verdict: ExecutionValidationVerdict
    proposed_handoff: dict[str, Any] | None = None


class ExecutionCoordinator:
    """In-memory coordinator chaining V2 execution stages without mutating repository or Job state."""

    def __init__(
        self,
        adapter: ExecutionAdapter,
        materializer: ContextMaterializer | None = None,
        renderer: PromptRenderer | None = None,
        repair_engine: StructuralRepairEngine | None = None,
        validator: ExecutionResultValidator | None = None,
    ) -> None:
        self.adapter = adapter
        self.materializer = materializer or ContextMaterializer()
        self.renderer = renderer or PromptRenderer()
        self.repair_engine = repair_engine or StructuralRepairEngine()
        self.validator = validator or ExecutionResultValidator()

    def coordinate_execution(
        self,
        request: dict[str, Any],
        profile: ExecutionProfile,
    ) -> ExecutionCoordinationResult:
        """Coordinates the in-memory execution cycle without mutating repository or Job state.

        1. Validates request schema.
        2. Materializes context pack in memory.
        3. Renders prompt.
        4. Executes prompt via adapter.
        5. Parses and structurally repairs response into ExecutionResult.
        6. Audits ExecutionResult with validator.
        7. If ACCEPT and stage != release, constructs proposed in-memory AgentHandoff payload.
        """
        if not isinstance(request, dict):
            raise ValueError(f"request must be a dict, got {type(request).__name__}")
        if not isinstance(profile, ExecutionProfile):
            raise TypeError(f"profile must be an ExecutionProfile instance, got {type(profile).__name__}")

        validate_payload("execution-request.schema.json", request)

        # 1. Materialize context
        context_pack = request["contextPack"]
        materialized = self.materializer.materialize(context_pack)

        # 2. Render prompt
        prompt = self.renderer.render(request, materialized)

        # 3. Execute adapter
        raw_response = self.adapter.execute(request, prompt, profile)

        # 4. Parse & repair
        result_payload = self.repair_engine.parse_and_repair(raw_response, request)

        # 5. Validate execution result
        verdict = self.validator.validate(result_payload, request)

        # 6. Prepare in-memory proposed handoff if verdict is ACCEPT
        proposed_handoff: dict[str, Any] | None = None
        if verdict.verdict == "ACCEPT":
            stage = request["targetStage"]
            next_stage = None
            if stage in PIPELINE_STAGES:
                idx = PIPELINE_STAGES.index(stage)
                if idx + 1 < len(PIPELINE_STAGES):
                    next_stage = PIPELINE_STAGES[idx + 1]

            handoff_id = f"HANDOFF-{request['jobId']}-{stage.upper()}-001"

            evidence_items = []
            for ev in result_payload.get("evidence", []):
                if isinstance(ev, dict):
                    evidence_items.append({
                        "type": "provenance",
                        "value": f"{ev.get('book', 'unknown')}:{ev.get('page', 1)}",
                        "source": str(ev.get("book", "")),
                        "page": int(ev.get("page", 1)),
                    })
            if not evidence_items:
                evidence_items.append({
                    "type": "execution",
                    "value": f"Execution completed for stage {stage}",
                })

            proposed_handoff = {
                "schemaVersion": "1.0",
                "handoffId": handoff_id,
                "jobId": request["jobId"],
                "agent": request["assignedAgent"],
                "stage": stage,
                "status": "pass",
                "startedAt": "2026-09-08T12:00:00-03:00",
                "completedAt": "2026-09-08T12:05:00-03:00",
                "inputs": list(context_pack.get("mandatory", [])) + list(context_pack.get("domain", [])),
                "outputs": list(result_payload.get("proposedArtifacts", {}).keys()),
                "changes": [f"Execution of stage {stage} completed successfully."],
                "evidence": evidence_items,
                "warnings": [],
                "uncertainties": [],
                "qualityMetrics": {
                    "artifactCount": len(result_payload.get("proposedArtifacts", {})),
                },
                "recommendedNextStage": next_stage,
                "requiresHumanReview": False,
            }
            validate_payload("agent-handoff.schema.json", proposed_handoff)

        return ExecutionCoordinationResult(
            request=copy.deepcopy(request),
            raw_response=raw_response,
            result=copy.deepcopy(result_payload),
            verdict=verdict,
            proposed_handoff=proposed_handoff,
        )
