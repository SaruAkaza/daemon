from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class WriteScopeDecision:
    """Immutable outcome of write scope evaluation."""
    allowed: bool
    code: str  # "ALLOW", "ERR_WRITE_SCOPE_VIOLATION", "INVALID_PATH"
    violations: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()


class WriteScopeValidator:
    """Deterministic, fail-closed validator for authorized write scope boundaries."""

    def __init__(self) -> None:
        pass

    def validate(
        self,
        proposed_artifacts: dict[str, Any],
        allowed_patterns: list[str],
    ) -> WriteScopeDecision:
        """Strictly checks if all proposed artifact paths match authorized write patterns.

        If ANY proposed artifact violates the scope or security rules, the ENTIRE proposal is rejected.
        """
        if not isinstance(proposed_artifacts, dict):
            return WriteScopeDecision(
                allowed=False,
                code="INVALID_PATH",
                violations=(),
                reasons=(f"proposed_artifacts must be a dict, got {type(proposed_artifacts).__name__}",),
            )

        if not isinstance(allowed_patterns, (list, tuple)):
            return WriteScopeDecision(
                allowed=False,
                code="INVALID_PATH",
                violations=(),
                reasons=(f"allowed_patterns must be a list/tuple, got {type(allowed_patterns).__name__}",),
            )

        if not proposed_artifacts:
            return WriteScopeDecision(
                allowed=True,
                code="ALLOW",
                violations=(),
                reasons=("No artifacts proposed (empty set is allowed).",),
            )

        violations: list[str] = []
        reasons: list[str] = []

        for raw_path in proposed_artifacts.keys():
            if not isinstance(raw_path, str) or not raw_path.strip():
                violations.append(str(raw_path))
                reasons.append("Path must be a non-empty string.")
                continue

            path_str = raw_path.strip().replace("\\", "/")

            # 1. Reject absolute paths (Unix, Windows drive letters, UNC paths)
            if (
                path_str.startswith("/")
                or (len(raw_path) >= 2 and raw_path[1] == ":")
                or raw_path.startswith("\\\\")
                or path_str.startswith("//")
            ):
                violations.append(raw_path)
                reasons.append(f"Absolute or UNC path forbidden: '{raw_path}'")
                continue

            # 2. Reject path traversal
            parts = path_str.split("/")
            if ".." in parts:
                violations.append(raw_path)
                reasons.append(f"Path traversal detected: '{raw_path}'")
                continue

            # 3. Check against allowed_patterns
            matched = False
            for pattern in allowed_patterns:
                pat_str = str(pattern).strip().replace("\\", "/")
                if path_str == pat_str or fnmatch.fnmatch(path_str, pat_str):
                    matched = True
                    break

            if not matched:
                violations.append(raw_path)
                reasons.append(f"Path '{raw_path}' is outside allowed write scope: {allowed_patterns}")

        if violations:
            return WriteScopeDecision(
                allowed=False,
                code="ERR_WRITE_SCOPE_VIOLATION",
                violations=tuple(violations),
                reasons=tuple(reasons),
            )

        return WriteScopeDecision(
            allowed=True,
            code="ALLOW",
            violations=(),
            reasons=("All proposed artifact paths are strictly within allowed write scope.",),
        )
