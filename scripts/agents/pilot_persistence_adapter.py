from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts.agents.application_coordinator import ApplicationCoordinator
from scripts.agents.application_policy import ApplicationPolicy
from scripts.agents.application_result import ApplicationResult
from scripts.agents.application_runtime import ApplicationRuntimeConfig
from scripts.agents.change_set import ChangeSetBuilder
from scripts.agents.change_set_applier import ChangeSetApplier
from scripts.agents.content_validator import ContentValidator
from scripts.agents.contracts import validate_payload
from scripts.agents.execution_validator import (
    ExecutionResultValidator,
    ExecutionValidationVerdict,
)
from scripts.agents.patch_applier import PatchApplier
from scripts.agents.precondition_validator import PreconditionValidator
from scripts.agents.staging_manager import StagingManager


class PilotPersistenceAdapter:
    """Adapts pilot candidate artifacts to V2.1 ApplicationCoordinator targeting RestrictedPilotWorkspace."""

    def apply_pilot_artifacts(
        self,
        workspace_root: Path | str,
        staging_root: Path | str,
        execution_request: dict[str, Any],
        execution_result: dict[str, Any],
        review_decision: dict[str, Any],
        execution_validator: ExecutionResultValidator | None = None,
    ) -> ApplicationResult:
        """Invokes V2.1 ApplicationCoordinator with authentic execution contracts and genuine validator verdict."""
        req_id = execution_request.get("requestId") or review_decision.get("requestId", "unknown")

        # 1. Gate: Human review approval
        decision_val = review_decision.get("decision")
        if decision_val != "APPROVE":
            res = ApplicationResult(
                change_set_id="cs-blocked-unapproved",
                request_id=req_id,
                status="BLOCKED",
                applied_operations=(),
                blocked_operations=(),
                failure_code="ERR_REVIEW_REQUIRED",
                reasons=(f"Review decision is not APPROVE: {decision_val}",),
                applied_at=None,
                duration_ms=0.0,
                journal=None,
                metadata={},
            )
            validate_payload("application-result.schema.json", res.to_dict())
            return res

        # 2. Gate: Authentic V2 technical execution validation
        validator = execution_validator or ExecutionResultValidator()
        verdict = validator.validate(result=execution_result, request=execution_request)
        if verdict.verdict != "ACCEPT":
            res = ApplicationResult(
                change_set_id="cs-blocked-validation-failed",
                request_id=req_id,
                status="BLOCKED",
                applied_operations=(),
                blocked_operations=(),
                failure_code=f"ERR_PERSISTENCE_FAILED:{verdict.code}",
                reasons=verdict.reasons,
                applied_at=None,
                duration_ms=0.0,
                journal=None,
                metadata=dict(verdict.details) if verdict.details else {},
            )
            validate_payload("application-result.schema.json", res.to_dict())
            return res

        # 3. Setup V2.1 isolated workspace application
        workspace_root = Path(workspace_root).resolve()
        staging_root = Path(staging_root).resolve()
        audit_root = staging_root.parent / "audit" / "pilot"

        config = ApplicationRuntimeConfig.create(
            repository_root=workspace_root,
            staging_root=staging_root,
            audit_root=audit_root,
        )

        builder = ChangeSetBuilder(repository_root=workspace_root)
        policy = ApplicationPolicy(config=config)
        content_validator = ContentValidator(config.resource_bounds)
        precondition_validator = PreconditionValidator(config, policy, content_validator)
        patch_applier = PatchApplier()
        staging_manager = StagingManager(config)
        applier = ChangeSetApplier(
            config=config,
            precondition_validator=precondition_validator,
            patch_applier=patch_applier,
            staging_manager=staging_manager,
        )
        coordinator = ApplicationCoordinator(
            config=config,
            builder=builder,
            policy=policy,
            applier=applier,
        )

        return coordinator.coordinate_application(execution_request, execution_result, verdict)

