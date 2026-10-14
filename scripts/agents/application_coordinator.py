from __future__ import annotations

from datetime import datetime, timezone
import time
from typing import Any

from scripts.agents.application_policy import ApplicationPolicy
from scripts.agents.application_result import ApplicationResult
from scripts.agents.application_runtime import ApplicationRuntimeConfig
from scripts.agents.change_set import ChangeSetBuilder
from scripts.agents.change_set_applier import ChangeSetApplier
from scripts.agents.contracts import validate_payload
from scripts.agents.execution_validator import ExecutionValidationVerdict


class ApplicationCoordinator:
    """Orchestrates ChangeSet construction, policy evaluation, and atomic application."""

    def __init__(
        self,
        config: ApplicationRuntimeConfig,
        builder: ChangeSetBuilder,
        policy: ApplicationPolicy,
        applier: ChangeSetApplier,
    ) -> None:
        self.config = config
        self.builder = builder
        self.policy = policy
        self.applier = applier

    def coordinate_application(
        self,
        request: dict[str, Any],
        result: dict[str, Any],
        verdict: ExecutionValidationVerdict | None = None,
    ) -> ApplicationResult:
        start_time = time.perf_counter()
        req_id = request.get("requestId", "unknown")
        allowed_scope = request.get("allowedWriteScope", [])

        # 1. Build ChangeSet (enforces ACCEPT verdict)
        try:
            change_set = self.builder.build(request, result, verdict)
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            res = ApplicationResult(
                change_set_id="cs-failed",
                request_id=req_id,
                status="BLOCKED",
                applied_operations=(),
                blocked_operations=(),
                failure_code="ERR_BUILDER_REJECTED",
                reasons=(f"ChangeSet building failed: {exc}",),
                applied_at=None,
                duration_ms=round(duration_ms, 2),
                journal=None,
                metadata={},
            )
            validate_payload("application-result.schema.json", res.to_dict())
            return res

        # 2. Evaluate Policy
        policy_eval = self.policy.evaluate_changeset(change_set, allowed_scope)
        if policy_eval.action == "BLOCKED":
            duration_ms = (time.perf_counter() - start_time) * 1000
            res = ApplicationResult(
                change_set_id=change_set.change_set_id,
                request_id=req_id,
                status="BLOCKED",
                applied_operations=(),
                blocked_operations=tuple(op.to_dict() for op in change_set.operations),
                failure_code=policy_eval.code,
                reasons=policy_eval.reasons,
                applied_at=None,
                duration_ms=round(duration_ms, 2),
                journal=None,
                metadata={"bookId": change_set.book_id, "stage": change_set.stage, "agent": change_set.agent},
            )
            validate_payload("application-result.schema.json", res.to_dict())
            return res

        if policy_eval.action == "HUMAN_REVIEW":
            duration_ms = (time.perf_counter() - start_time) * 1000
            res = ApplicationResult(
                change_set_id=change_set.change_set_id,
                request_id=req_id,
                status="HUMAN_REVIEW",
                applied_operations=(),
                blocked_operations=tuple(op.to_dict() for op in change_set.operations),
                failure_code=policy_eval.code,
                reasons=policy_eval.reasons,
                applied_at=None,
                duration_ms=round(duration_ms, 2),
                journal=None,
                metadata={"bookId": change_set.book_id, "stage": change_set.stage, "agent": change_set.agent},
            )
            validate_payload("application-result.schema.json", res.to_dict())
            return res

        # 3. AUTO_APPLY_ELIGIBLE -> apply through applier
        outcome = self.applier.apply(change_set, allowed_scope)
        duration_ms = (time.perf_counter() - start_time) * 1000
        applied_at = datetime.now(timezone.utc).isoformat() if outcome.status == "APPLIED" else None

        res = ApplicationResult(
            change_set_id=change_set.change_set_id,
            request_id=req_id,
            status=outcome.status,
            applied_operations=outcome.applied_records,
            blocked_operations=(),
            failure_code=outcome.failure_code,
            reasons=outcome.reasons,
            applied_at=applied_at,
            duration_ms=round(duration_ms, 2),
            journal=outcome.journal,
            metadata={"bookId": change_set.book_id, "stage": change_set.stage, "agent": change_set.agent},
        )
        validate_payload("application-result.schema.json", res.to_dict())
        return res
