from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from scripts.agents.contracts import ContractValidationError, validate_payload
from scripts.agents.gate_engine import GateEngine
from scripts.agents.write_scope import WriteScopeValidator


@dataclass(frozen=True)
class ExecutionValidationVerdict:
    """Immutable verdict emitted after comprehensive audit of an ExecutionResult."""
    verdict: str  # "ACCEPT", "HUMAN_REVIEW", "BLOCKED"
    code: str
    reasons: tuple[str, ...]
    details: dict[str, Any] = field(default_factory=dict)


class ExecutionResultValidator:
    """Aggregated, deterministic auditor for ExecutionResult payloads prior to persistence."""

    def __init__(
        self,
        write_scope_validator: WriteScopeValidator | None = None,
        gate_engine: GateEngine | None = None,
    ) -> None:
        self.write_scope_validator = write_scope_validator or WriteScopeValidator()
        self.gate_engine = gate_engine or GateEngine()

    def validate(
        self,
        result: dict[str, Any],
        request: dict[str, Any],
    ) -> ExecutionValidationVerdict:
        """Perform comprehensive deterministic audit on an ExecutionResult before persistence.

        Precedence of failure:
        1. Schema conformance of result payload -> BLOCKED
        2. Request correlation (matching requestId) -> BLOCKED
        3. Adapter failure / status (TIMEOUT, ERROR, REPAIR_FAILED) -> BLOCKED
        4. Write scope violation -> BLOCKED
        5. Semantic uncertainties -> HUMAN_REVIEW
        6. Missing provenance evidence -> HUMAN_REVIEW
        7. Output artifact schema validity -> HUMAN_REVIEW / BLOCKED
        8. Everything valid -> ACCEPT
        """
        if not isinstance(result, dict) or not isinstance(request, dict):
            return ExecutionValidationVerdict(
                verdict="BLOCKED",
                code="INVALID_ARGUMENTS",
                reasons=("Result and request must both be dictionaries.",),
            )

        # 1. Result schema validation
        try:
            validate_payload("execution-result.schema.json", result)
        except ContractValidationError as e:
            return ExecutionValidationVerdict(
                verdict="BLOCKED",
                code="ERR_RESULT_SCHEMA_VIOLATION",
                reasons=(f"ExecutionResult failed schema validation: {e}",),
            )

        # 2. Request correlation
        req_id = request.get("requestId")
        if result.get("requestId") != req_id:
            return ExecutionValidationVerdict(
                verdict="BLOCKED",
                code="ERR_REQUEST_CORRELATION",
                reasons=(
                    f"Result requestId '{result.get('requestId')}' does not match request requestId '{req_id}'.",
                ),
            )

        # 3. Adapter status check
        status = result.get("status")
        if status in ("TIMEOUT", "ERROR", "REPAIR_FAILED", "VALIDATION_FAILED"):
            return ExecutionValidationVerdict(
                verdict="BLOCKED",
                code=f"ERR_ADAPTER_{status}",
                reasons=(f"Execution adapter terminated with failure status: '{status}'.",),
                details={"status": status},
            )

        # 4. Write scope validation (fail-closed)
        proposed_artifacts = result.get("proposedArtifacts", {})
        allowed_write_scope = request.get("allowedWriteScope", [])
        scope_decision = self.write_scope_validator.validate(proposed_artifacts, allowed_write_scope)
        if not scope_decision.allowed:
            return ExecutionValidationVerdict(
                verdict="BLOCKED",
                code="ERR_WRITE_SCOPE_VIOLATION",
                reasons=scope_decision.reasons,
                details={"violations": list(scope_decision.violations)},
            )

        # 5. Semantic uncertainties check
        uncertainties = result.get("uncertainties", [])
        if uncertainties:
            return ExecutionValidationVerdict(
                verdict="HUMAN_REVIEW",
                code="ERR_SEMANTIC_UNCERTAINTY",
                reasons=(f"Agent registered {len(uncertainties)} uncertainties requiring human evaluation.",),
                details={"uncertainties": uncertainties},
            )

        # 6. Provenance evidence check for stages generating artifacts
        stage = request.get("targetStage")
        evidence = result.get("evidence", [])
        if proposed_artifacts and not evidence and stage in ("extraction", "editorial", "entities", "relations"):
            return ExecutionValidationVerdict(
                verdict="HUMAN_REVIEW",
                code="ERR_EVIDENCE_MISSING",
                reasons=(f"Stage '{stage}' produced artifacts without citing provenance evidence (book/page).",),
            )

        # 7. Validate output artifacts against output schema if applicable
        output_schema_name = request.get("outputSchemaName")
        if output_schema_name and proposed_artifacts:
            for path, content in proposed_artifacts.items():
                if path.endswith(".json") and output_schema_name.endswith(".schema.json"):
                    try:
                        parsed_artifact = json.loads(content)
                        validate_payload(output_schema_name, parsed_artifact)
                    except json.JSONDecodeError as e:
                        return ExecutionValidationVerdict(
                            verdict="HUMAN_REVIEW",
                            code="ERR_SCHEMA_VALIDATION",
                            reasons=(f"Proposed artifact '{path}' contains invalid JSON: {e}",),
                        )
                    except ContractValidationError as e:
                        return ExecutionValidationVerdict(
                            verdict="HUMAN_REVIEW",
                            code="ERR_SCHEMA_VALIDATION",
                            reasons=(f"Proposed artifact '{path}' failed validation against '{output_schema_name}': {e}",),
                        )
                    except Exception:
                        pass

        # 8. All checks passed
        return ExecutionValidationVerdict(
            verdict="ACCEPT",
            code="ALLOW",
            reasons=("All execution validations and governance policies satisfied.",),
        )
