from __future__ import annotations

import fnmatch
import os
from pathlib import Path
from typing import Sequence
from dataclasses import dataclass

from scripts.agents.application_runtime import ApplicationRuntimeConfig
from scripts.agents.change_set import ChangeSet


DOS_RESERVED_NAMES = frozenset({
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
})


@dataclass(frozen=True)
class PolicyEvaluationResult:
    """Immutable evaluation verdict of filesystem application policy."""
    allowed: bool
    action: str  # "AUTO_APPLY_ELIGIBLE", "HUMAN_REVIEW", "BLOCKED"
    code: str | None
    reasons: tuple[str, ...]


class ApplicationPolicy:
    """Deterministic, fail-closed policy engine governing filesystem mutations."""

    def __init__(self, config: ApplicationRuntimeConfig) -> None:
        self.config = config

    def evaluate_path(
        self,
        target_path: str,
        allowed_write_scope: Sequence[str],
    ) -> PolicyEvaluationResult:
        """Evaluates a single path against hardening, containment, allowlists, and write-scope."""
        if not isinstance(target_path, str) or not target_path.strip():
            return PolicyEvaluationResult(
                allowed=False,
                action="BLOCKED",
                code="ERR_PATH_TRAVERSAL",
                reasons=("target_path must be a non-empty string.",),
            )

        raw = target_path.strip()

        # 1. Reject drive letters, UNC, device prefixes, ADS, and absolute paths
        if (
            raw.startswith("/")
            or raw.startswith("\\")
            or raw.startswith("//")
            or (len(raw) >= 2 and raw[1] == ":")
            or raw.startswith("\\\\?\\")
            or raw.startswith("//?/")
            or raw.startswith("\\\\.\\")
            or raw.startswith("//./")
        ):
            return PolicyEvaluationResult(
                allowed=False,
                action="BLOCKED",
                code="ERR_HARD_BLOCKED_PATH",
                reasons=(f"Absolute, UNC, device, or drive-letter path rejected: '{raw}'",),
            )

        # Reject Alternate Data Stream (contains ':')
        if ":" in raw:
            return PolicyEvaluationResult(
                allowed=False,
                action="BLOCKED",
                code="ERR_HARD_BLOCKED_PATH",
                reasons=(f"Alternate Data Stream (colon) forbidden: '{raw}'",),
            )

        # Normalize to POSIX
        norm_path = raw.replace("\\", "/")
        parts = [p for p in norm_path.split("/") if p]

        # Reject path traversal
        if ".." in parts or any(p == ".." for p in parts):
            return PolicyEvaluationResult(
                allowed=False,
                action="BLOCKED",
                code="ERR_PATH_TRAVERSAL",
                reasons=(f"Path traversal detected: '{raw}'",),
            )

        # Windows hardening: DOS reserved names and trailing dots/spaces
        for part in parts:
            # Trailing dot or space
            if part.endswith(".") or part.endswith(" "):
                return PolicyEvaluationResult(
                    allowed=False,
                    action="BLOCKED",
                    code="ERR_HARD_BLOCKED_PATH",
                    reasons=(f"Trailing space or dot forbidden: '{part}' in '{raw}'",),
                )

            stem = part.split(".")[0].upper()
            if stem in DOS_RESERVED_NAMES:
                return PolicyEvaluationResult(
                    allowed=False,
                    action="BLOCKED",
                    code="ERR_HARD_BLOCKED_PATH",
                    reasons=(f"DOS reserved device name forbidden: '{part}' in '{raw}'",),
                )

        lower_path = norm_path.lower()

        # 2. Hard-blocked roots
        for hr in self.config.hard_blocked_roots:
            hr_lower = hr.lower()
            if lower_path.startswith(hr_lower) or lower_path == hr_lower.rstrip("/"):
                return PolicyEvaluationResult(
                    allowed=False,
                    action="BLOCKED",
                    code="ERR_HARD_BLOCKED_PATH",
                    reasons=(f"Path belongs to hard-blocked root '{hr}': '{raw}'",),
                )

        # 3. Canonical containment & symlink/junction/reparse-point inspection
        repo_root = self.config.repository_root
        target_abs = repo_root / norm_path
        curr = target_abs.parent

        while True:
            if curr.exists():
                # Check for symlink or Windows directory junction / reparse point
                try:
                    if os.path.islink(curr):
                        return PolicyEvaluationResult(
                            allowed=False,
                            action="HUMAN_REVIEW",
                            code="ERR_SYMLINK_REPARSE_POINT_DETECTED",
                            reasons=(f"Symlink or reparse point ancestor detected at '{curr}'",),
                        )
                except OSError:
                    pass

            if curr == repo_root or curr == curr.parent or not curr.is_relative_to(repo_root):
                break
            curr = curr.parent

        try:
            resolved_parent = target_abs.parent.resolve()
            resolved_repo = repo_root.resolve()
            if not str(resolved_parent).lower().startswith(str(resolved_repo).lower()):
                return PolicyEvaluationResult(
                    allowed=False,
                    action="BLOCKED",
                    code="ERR_CONTAINMENT_VIOLATION",
                    reasons=(f"Resolved target parent '{resolved_parent}' escapes repository root '{resolved_repo}'",),
                )
        except Exception as e:
            return PolicyEvaluationResult(
                allowed=False,
                action="BLOCKED",
                code="ERR_CONTAINMENT_VIOLATION",
                reasons=(f"Containment check failed: {e}",),
            )

        # 4. Write scope intersection (requested write scope must match)
        scope_matched = False
        for pattern in allowed_write_scope:
            pat_norm = pattern.strip().replace("\\", "/").lower()
            if (
                lower_path == pat_norm
                or (pat_norm.endswith("/") and lower_path.startswith(pat_norm))
                or fnmatch.fnmatch(lower_path, pat_norm)
                or fnmatch.fnmatch(lower_path, pat_norm.rstrip("/") + "/*")
            ):
                scope_matched = True
                break

        if not scope_matched:
            return PolicyEvaluationResult(
                allowed=False,
                action="BLOCKED",
                code="ERR_WRITE_SCOPE_VIOLATION",
                reasons=(f"Path '{raw}' is outside allowedWriteScope: {list(allowed_write_scope)}",),
            )

        # 5. Protected roots check (escalate to HUMAN_REVIEW)
        for pr in self.config.protected_roots:
            pr_lower = pr.lower()
            if lower_path.startswith(pr_lower) or lower_path == pr_lower.rstrip("/"):
                return PolicyEvaluationResult(
                    allowed=False,
                    action="HUMAN_REVIEW",
                    code="ERR_PROTECTED_PATH",
                    reasons=(f"Path '{raw}' matches protected root '{pr}'",),
                )

        # 6. AutoApplyRoots allowlist check
        auto_apply_matched = False
        for ar in self.config.auto_apply_roots:
            ar_lower = ar.lower()
            if lower_path.startswith(ar_lower):
                auto_apply_matched = True
                break

        if auto_apply_matched:
            return PolicyEvaluationResult(
                allowed=True,
                action="AUTO_APPLY_ELIGIBLE",
                code=None,
                reasons=(),
            )

        # Default fallback is HUMAN_REVIEW
        return PolicyEvaluationResult(
            allowed=False,
            action="HUMAN_REVIEW",
            code="ERR_NON_ALLOWLISTED_PATH",
            reasons=(f"Path '{raw}' is not within any AutoApplyRoots; escalated to HUMAN_REVIEW",),
        )

    def evaluate_changeset(
        self,
        change_set: ChangeSet,
        allowed_write_scope: Sequence[str],
    ) -> PolicyEvaluationResult:
        """Evaluates all operations in a ChangeSet using all-or-nothing fail-closed logic."""
        if not change_set.operations:
            return PolicyEvaluationResult(
                allowed=True,
                action="AUTO_APPLY_ELIGIBLE",
                code=None,
                reasons=("Empty ChangeSet is eligible.",),
            )

        blocked_reasons: list[str] = []
        review_reasons: list[str] = []
        blocked_code: str | None = None
        review_code: str | None = None

        for op in change_set.operations:
            res = self.evaluate_path(op.target_path, allowed_write_scope)
            if res.action == "BLOCKED":
                blocked_reasons.extend(res.reasons)
                if not blocked_code:
                    blocked_code = res.code
            elif res.action == "HUMAN_REVIEW":
                review_reasons.extend(res.reasons)
                if not review_code:
                    review_code = res.code

        if blocked_reasons:
            return PolicyEvaluationResult(
                allowed=False,
                action="BLOCKED",
                code=blocked_code,
                reasons=tuple(blocked_reasons),
            )

        if review_reasons:
            return PolicyEvaluationResult(
                allowed=False,
                action="HUMAN_REVIEW",
                code=review_code,
                reasons=tuple(review_reasons),
            )

        return PolicyEvaluationResult(
            allowed=True,
            action="AUTO_APPLY_ELIGIBLE",
            code=None,
            reasons=(),
        )
