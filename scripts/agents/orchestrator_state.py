from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from scripts.agents.contracts import validate_payload
from scripts.agents.gate_engine import PIPELINE_STAGES, GateEngine

STAGE_AGENT_MAP: dict[str, str] = {
    "source": "source-agent",
    "extraction": "extraction-agent",
    "editorial": "editorial-agent",
    "entities": "entity-agent",
    "relations": "relations-agent",
    "frontend": "frontend-agent",
    "qa": "qa-release-agent",
    "release": "qa-release-agent",
}


class OrchestratorStateError(RuntimeError):
    """Raised when orchestrator state selection encounters invalid arguments, inconsistent pipeline states, or data errors."""
    pass


@dataclass(frozen=True)
class OrchestratorSelection:
    """Immutable, deterministic result of an orchestrator state selection."""
    action: str
    code: str
    stage: str | None = None
    agent: str | None = None
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.action, str) or not self.action.strip():
            raise ValueError("action must be a non-empty string")
        if not isinstance(self.code, str) or not self.code.strip():
            raise ValueError("code must be a non-empty string")
        if self.stage is not None and not isinstance(self.stage, str):
            raise TypeError(f"stage must be a string or None, got {type(self.stage).__name__}")
        if self.agent is not None and not isinstance(self.agent, str):
            raise TypeError(f"agent must be a string or None, got {type(self.agent).__name__}")
        if isinstance(self.reasons, (list, tuple)):
            object.__setattr__(self, "reasons", tuple(str(r) for r in self.reasons))
        else:
            raise TypeError(f"reasons must be a sequence of strings, got {type(self.reasons).__name__}")


class OrchestratorStateSelector:
    """Deterministic, side-effect-free component that evaluates an Agent Job state and decides the next safe action."""

    def __init__(self, gate_engine: GateEngine | None = None) -> None:
        self.gate_engine = gate_engine or GateEngine()

    def select(
        self,
        job: dict[str, Any],
        *,
        human_validated: bool = False,
        source_manifest: dict[str, Any] | None = None,
    ) -> OrchestratorSelection:
        """Analyze job and manifest state to determine next safe orchestrator action."""
        if not isinstance(job, dict):
            raise OrchestratorStateError(f"job must be a dict, got {type(job).__name__}")

        if not isinstance(human_validated, bool):
            raise OrchestratorStateError(
                f"human_validated must be a boolean, got {type(human_validated).__name__}"
            )

        if source_manifest is not None and not isinstance(source_manifest, dict):
            raise OrchestratorStateError(
                f"source_manifest must be a dict or None, got {type(source_manifest).__name__}"
            )

        # Validate schema conformance
        validate_payload("agent-job.schema.json", job)

        stages_map: dict[str, str] = job.get("stages", {})

        # 1. Pipeline consistency check: detect multiple running stages
        running_stages = [s for s in PIPELINE_STAGES if stages_map.get(s) == "running"]
        if len(running_stages) > 1:
            raise OrchestratorStateError(
                f"Multiple running stages detected in sequential pipeline: {running_stages}"
            )

        # 2. Pipeline consistency check: detect multiple human_review stages
        review_stages = [s for s in PIPELINE_STAGES if stages_map.get(s) == "human_review"]
        if len(review_stages) > 1:
            raise OrchestratorStateError(
                f"Multiple human_review stages detected in sequential pipeline: {review_stages}"
            )

        # 3. Pipeline consistency check: detect out-of-order passed stages
        for i, stage in enumerate(PIPELINE_STAGES):
            if stages_map.get(stage) == "pass":
                for pred_stage in PIPELINE_STAGES[:i]:
                    pred_status = stages_map.get(pred_stage)
                    if pred_status != "pass":
                        raise OrchestratorStateError(
                            f"Out-of-order pass detected: stage '{stage}' has passed, but preceding stage '{pred_stage}' is '{pred_status}'"
                        )

        all_passed = all(stages_map.get(s) == "pass" for s in PIPELINE_STAGES)
        job_status = job.get("status")

        # 4. Inconsistency check: job status 'done' must have all stages passed
        if job_status == "done":
            if not all_passed:
                raise OrchestratorStateError(
                    "Job status is 'done', but not all pipeline stages are 'pass'"
                )
            return OrchestratorSelection(
                action="NO_ACTION",
                code="JOB_ALREADY_DONE",
                reasons=("Job is already marked as done with all stages completed.",),
            )

        # 5. Check if all pipeline stages are passed -> evaluate done transition
        if all_passed:
            done_decision = self.gate_engine.evaluate_done(job, human_validated=human_validated)
            if done_decision.allowed:
                return OrchestratorSelection(
                    action="READY_FOR_DONE",
                    code=done_decision.code,
                    stage=None,
                    agent=None,
                    reasons=done_decision.reasons,
                )
            else:
                action = "HUMAN_REVIEW" if done_decision.code == "HUMAN_VALIDATION_REQUIRED" else "BLOCKED"
                return OrchestratorSelection(
                    action=action,
                    code=done_decision.code,
                    stage=None,
                    agent=None,
                    reasons=done_decision.reasons,
                )

        # Find earliest uncompleted stage (candidate stage)
        candidate_stage = next((s for s in PIPELINE_STAGES if stages_map.get(s) != "pass"), None)
        candidate_agent = STAGE_AGENT_MAP.get(candidate_stage) if candidate_stage else None

        # 6. Job-level status overrides when not all stages are done
        if job_status == "blocked":
            blocking_reasons = tuple(job.get("blockingReasons") or ["Job status is blocked."])
            return OrchestratorSelection(
                action="BLOCKED",
                code="JOB_BLOCKED",
                stage=candidate_stage,
                agent=candidate_agent,
                reasons=blocking_reasons,
            )

        if job_status == "needs_review":
            return OrchestratorSelection(
                action="HUMAN_REVIEW",
                code="JOB_REVIEW_REQUIRED",
                stage=candidate_stage,
                agent=candidate_agent,
                reasons=("Job status is needs_review.",),
            )

        if candidate_stage is None:
            return OrchestratorSelection(
                action="NO_ACTION",
                code="NO_STAGE_AVAILABLE",
                reasons=("No uncompleted stages remaining in pipeline.",),
            )

        # 7. Evaluate candidate stage status
        stage_status = stages_map.get(candidate_stage)

        if stage_status == "running":
            return OrchestratorSelection(
                action="WAIT",
                code="STAGE_ALREADY_RUNNING",
                stage=candidate_stage,
                agent=candidate_agent,
                reasons=(f"Stage '{candidate_stage}' is currently running.",),
            )

        if stage_status == "waiting":
            return OrchestratorSelection(
                action="WAIT",
                code="STAGE_WAITING",
                stage=candidate_stage,
                agent=candidate_agent,
                reasons=(f"Stage '{candidate_stage}' is waiting.",),
            )

        if stage_status == "blocked":
            return OrchestratorSelection(
                action="BLOCKED",
                code="STAGE_BLOCKED",
                stage=candidate_stage,
                agent=candidate_agent,
                reasons=(f"Stage '{candidate_stage}' is blocked.",),
            )

        if stage_status == "fail":
            return OrchestratorSelection(
                action="BLOCKED",
                code="STAGE_FAILED",
                stage=candidate_stage,
                agent=candidate_agent,
                reasons=(f"Stage '{candidate_stage}' has failed.",),
            )

        if stage_status == "human_review":
            return OrchestratorSelection(
                action="HUMAN_REVIEW",
                code="HUMAN_REVIEW_REQUIRED",
                stage=candidate_stage,
                agent=candidate_agent,
                reasons=(f"Stage '{candidate_stage}' requires human review.",),
            )

        if stage_status == "ready":
            # Check entry gate
            entry_decision = self.gate_engine.evaluate_stage_entry(job, candidate_stage)
            if not entry_decision.allowed:
                return OrchestratorSelection(
                    action="BLOCKED",
                    code=entry_decision.code,
                    stage=candidate_stage,
                    agent=candidate_agent,
                    reasons=entry_decision.reasons,
                )

            # Check release gate if candidate stage is release
            if candidate_stage == "release":
                release_decision = self.gate_engine.evaluate_release(
                    job, source_manifest=source_manifest
                )
                if not release_decision.allowed:
                    return OrchestratorSelection(
                        action="BLOCKED",
                        code=release_decision.code,
                        stage=candidate_stage,
                        agent=candidate_agent,
                        reasons=release_decision.reasons,
                    )

            return OrchestratorSelection(
                action="RUN_STAGE",
                code="ALLOW",
                stage=candidate_stage,
                agent=candidate_agent,
                reasons=(f"Stage '{candidate_stage}' is ready to run.",),
            )

        raise OrchestratorStateError(
            f"Unexpected stage status '{stage_status}' for stage '{candidate_stage}'"
        )
