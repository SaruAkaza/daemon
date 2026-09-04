from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from scripts.agents.contracts import validate_payload

PIPELINE_STAGES: tuple[str, ...] = (
    "source",
    "extraction",
    "editorial",
    "entities",
    "relations",
    "frontend",
    "qa",
    "release",
)


class GateEngineError(RuntimeError):
    """Raised when gate evaluation fails due to invalid arguments, unknown stages, or type mismatch."""
    pass


@dataclass(frozen=True)
class GateDecision:
    """Immutable, deterministic result of a policy gate evaluation."""
    allowed: bool
    code: str
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.allowed, bool):
            raise TypeError(f"allowed must be a bool, got {type(self.allowed).__name__}")
        if not isinstance(self.code, str) or not self.code.strip():
            raise ValueError("code must be a non-empty string")
        if isinstance(self.reasons, (list, tuple)):
            object.__setattr__(self, "reasons", tuple(str(r) for r in self.reasons))
        else:
            raise TypeError(f"reasons must be a sequence of strings, got {type(self.reasons).__name__}")


class GateEngine:
    """Deterministic policy gate evaluator for agent workflow progression and completion."""

    def evaluate_stage_entry(
        self,
        job: dict[str, Any],
        stage: str,
    ) -> GateDecision:
        """Determine if a pipeline stage is permitted to start based on predecessor status.

        Args:
            job: Agent Job dictionary conforming to agent-job.schema.json.
            stage: Target pipeline stage name to evaluate for entry.

        Returns:
            GateDecision with allowed=True if all prerequisites are satisfied, False otherwise.

        Raises:
            GateEngineError: If stage is unknown or arguments are structurally invalid.
            ContractValidationError: If job payload violates agent-job.schema.json.
        """
        if not isinstance(job, dict):
            raise GateEngineError(f"job must be a dict, got {type(job).__name__}")

        if not isinstance(stage, str) or stage not in PIPELINE_STAGES:
            raise GateEngineError(
                f"Unknown stage '{stage}'. Canonical pipeline stages are: {PIPELINE_STAGES}"
            )

        # Validate job schema integrity
        validate_payload("agent-job.schema.json", job)

        stage_idx = PIPELINE_STAGES.index(stage)

        # Initial stage has no predecessors
        if stage_idx == 0:
            return GateDecision(
                allowed=True,
                code="ALLOW",
                reasons=("Source is the initial pipeline stage with no prerequisites.",),
            )

        # Preceding stage must have status "pass"
        pred_stage = PIPELINE_STAGES[stage_idx - 1]
        stages_map = job.get("stages", {})
        pred_status = stages_map.get(pred_stage)

        if pred_status == "pass":
            return GateDecision(
                allowed=True,
                code="ALLOW",
                reasons=(f"Prerequisite stage '{pred_stage}' has passed.",),
            )

        return GateDecision(
            allowed=False,
            code="PREREQUISITE_STAGE_NOT_PASSED",
            reasons=(
                f"Prerequisite stage '{pred_stage}' is '{pred_status}', required 'pass'.",
            ),
        )

    def evaluate_done(
        self,
        job: dict[str, Any],
        *,
        human_validated: bool,
    ) -> GateDecision:
        """Determine if a Job can transition to the final 'done' status.

        In accordance with ADR-0002, human validation is mandatory and cannot be bypassed.

        Args:
            job: Agent Job dictionary conforming to agent-job.schema.json.
            human_validated: Explicit boolean confirming human review approval.

        Returns:
            GateDecision with allowed=True if human validated and all stages passed, False otherwise.

        Raises:
            GateEngineError: If human_validated is not a strict boolean or job is invalid.
            ContractValidationError: If job payload violates agent-job.schema.json.
        """
        if not isinstance(human_validated, bool):
            raise GateEngineError(
                f"human_validated must be a boolean, got {type(human_validated).__name__}"
            )

        if not isinstance(job, dict):
            raise GateEngineError(f"job must be a dict, got {type(job).__name__}")

        validate_payload("agent-job.schema.json", job)

        if not human_validated:
            return GateDecision(
                allowed=False,
                code="HUMAN_VALIDATION_REQUIRED",
                reasons=("Final human validation is required before done (ADR-0002).",),
            )

        stages_map = job.get("stages", {})
        unpassed = [
            f"'{s}' ({stages_map.get(s)})"
            for s in PIPELINE_STAGES
            if stages_map.get(s) != "pass"
        ]

        if unpassed:
            return GateDecision(
                allowed=False,
                code="PIPELINE_NOT_COMPLETED",
                reasons=(f"Pipeline stages not passed: {', '.join(unpassed)}.",),
            )

        return GateDecision(
            allowed=True,
            code="ALLOW",
            reasons=("Human validation confirmed and all pipeline stages passed.",),
        )

    def evaluate_release(
        self,
        job: dict[str, Any],
        *,
        source_manifest: dict[str, Any] | None = None,
    ) -> GateDecision:
        """Determine if publication release conditions are satisfied.

        Checks QA stage completion and verifies rightsStatus / publicationMode in Source Manifest.

        Args:
            job: Agent Job dictionary conforming to agent-job.schema.json.
            source_manifest: Optional Source Manifest conforming to source-manifest.schema.json.

        Returns:
            GateDecision with allowed=True if QA passed and legal rights permit release, False otherwise.

        Raises:
            ContractValidationError: If job or source_manifest violate their respective schemas.
        """
        if not isinstance(job, dict):
            raise GateEngineError(f"job must be a dict, got {type(job).__name__}")

        validate_payload("agent-job.schema.json", job)

        stages_map = job.get("stages", {})
        qa_status = stages_map.get("qa")

        if qa_status != "pass":
            return GateDecision(
                allowed=False,
                code="QA_STAGE_NOT_PASSED",
                reasons=(f"QA stage is '{qa_status}', required 'pass' before release.",),
            )

        if source_manifest is None:
            return GateDecision(
                allowed=False,
                code="SOURCE_MANIFEST_REQUIRED",
                reasons=("Source manifest with rights evidence is required for release evaluation.",),
            )

        if not isinstance(source_manifest, dict):
            raise GateEngineError(
                f"source_manifest must be a dict, got {type(source_manifest).__name__}"
            )

        validate_payload("source-manifest.schema.json", source_manifest)

        rights = source_manifest.get("rightsStatus")
        pub_mode = source_manifest.get("publicationMode")

        if rights in ("UNKNOWN", "PRIVATE") or pub_mode == "NOT_PUBLIC":
            return GateDecision(
                allowed=False,
                code="RIGHTS_BLOCK_RELEASE",
                reasons=(
                    f"Rights status '{rights}' with publicationMode '{pub_mode}' blocks release.",
                ),
            )

        return GateDecision(
            allowed=True,
            code="ALLOW",
            reasons=("Release conditions and rights evidence satisfied.",),
        )

