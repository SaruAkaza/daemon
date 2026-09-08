from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Any

from scripts.agents.application_policy import ApplicationPolicy
from scripts.agents.application_runtime import ApplicationRuntimeConfig
from scripts.agents.change_set import ChangeOperation, ChangeSet
from scripts.agents.content_validator import ContentValidator


@dataclass(frozen=True)
class PreconditionValidationResult:
    """Outcome of initial or TOCTOU precondition validation."""
    valid: bool
    code: str | None
    reasons: tuple[str, ...]


class PreconditionValidator:
    """Enforces fail-closed preconditions both before staging and immediately before physical mutation."""

    def __init__(
        self,
        config: ApplicationRuntimeConfig,
        policy: ApplicationPolicy,
        content_validator: ContentValidator,
    ) -> None:
        self.config = config
        self.policy = policy
        self.content_validator = content_validator

    def validate_initial(
        self,
        change_set: ChangeSet,
        allowed_write_scope: list[str],
    ) -> PreconditionValidationResult:
        # 1. Content & Resource bounds validation
        bounds_res = self.content_validator.validate_changeset_bounds(change_set)
        if not bounds_res.valid:
            return PreconditionValidationResult(
                valid=False,
                code=bounds_res.code,
                reasons=bounds_res.reasons,
            )

        for op in change_set.operations:
            op_res = self.content_validator.validate_operation_content(op)
            if not op_res.valid:
                return PreconditionValidationResult(
                    valid=False,
                    code=op_res.code,
                    reasons=op_res.reasons,
                )

        # 2. Policy & Scope validation (AutoApplyRoots & allowedWriteScope)
        policy_res = self.policy.evaluate_changeset(change_set, allowed_write_scope)
        if not policy_res.allowed or policy_res.action not in ("AUTO_APPLY", "AUTO_APPLY_ELIGIBLE"):
            return PreconditionValidationResult(
                valid=False,
                code=policy_res.code,
                reasons=policy_res.reasons,
            )

        # 3. Initial filesystem preconditions
        for op in change_set.operations:
            target_path = self.config.repository_root / op.target_path
            if op.type == "CREATE":
                if target_path.exists():
                    return PreconditionValidationResult(
                        valid=False,
                        code="ERR_CREATE_CONFLICT",
                        reasons=(f"Target path already exists for CREATE operation: '{op.target_path}'",),
                    )
            elif op.type == "UPDATE":
                if not target_path.is_file():
                    return PreconditionValidationResult(
                        valid=False,
                        code="ERR_TARGET_NOT_FOUND",
                        reasons=(f"Target path does not exist for UPDATE operation: '{op.target_path}'",),
                    )
                if op.expected_base_sha256:
                    actual_sha256 = hashlib.sha256(target_path.read_bytes()).hexdigest()
                    if actual_sha256 != op.expected_base_sha256:
                        return PreconditionValidationResult(
                            valid=False,
                            code="ERR_STALE_BASE",
                            reasons=(
                                f"Base SHA256 mismatch for '{op.target_path}': "
                                f"expected {op.expected_base_sha256}, got {actual_sha256}",
                            ),
                        )
            else:
                return PreconditionValidationResult(
                    valid=False,
                    code="ERR_FORBIDDEN_OPERATION_TYPE",
                    reasons=(f"Unsupported operation type '{op.type}'",),
                )

        return PreconditionValidationResult(
            valid=True,
            code=None,
            reasons=(),
        )

    def validate_toctou_pre_mutation(
        self,
        change_set: ChangeSet,
        allowed_write_scope: list[str],
    ) -> PreconditionValidationResult:
        # Revalidate policy & reparse/symlink checks immediately before disk mutation
        policy_res = self.policy.evaluate_changeset(change_set, allowed_write_scope)
        if not policy_res.allowed or policy_res.action not in ("AUTO_APPLY", "AUTO_APPLY_ELIGIBLE"):
            return PreconditionValidationResult(
                valid=False,
                code=policy_res.code,
                reasons=policy_res.reasons,
            )

        for op in change_set.operations:
            target_path = self.config.repository_root / op.target_path
            if op.type == "CREATE":
                if target_path.exists():
                    return PreconditionValidationResult(
                        valid=False,
                        code="ERR_CREATE_CONFLICT",
                        reasons=(f"TOCTOU violation: Target path exists for CREATE operation: '{op.target_path}'",),
                    )
            elif op.type == "UPDATE":
                if not target_path.is_file():
                    return PreconditionValidationResult(
                        valid=False,
                        code="ERR_TARGET_NOT_FOUND",
                        reasons=(f"TOCTOU violation: Target path missing for UPDATE operation: '{op.target_path}'",),
                    )
                if op.expected_base_sha256:
                    actual_sha256 = hashlib.sha256(target_path.read_bytes()).hexdigest()
                    if actual_sha256 != op.expected_base_sha256:
                        return PreconditionValidationResult(
                            valid=False,
                            code="ERR_STALE_BASE",
                            reasons=(
                                f"TOCTOU violation: Base SHA256 changed for '{op.target_path}': "
                                f"expected {op.expected_base_sha256}, got {actual_sha256}",
                            ),
                        )
            else:
                return PreconditionValidationResult(
                    valid=False,
                    code="ERR_FORBIDDEN_OPERATION_TYPE",
                    reasons=(f"Unsupported operation type '{op.type}'",),
                )

        return PreconditionValidationResult(
            valid=True,
            code=None,
            reasons=(),
        )
