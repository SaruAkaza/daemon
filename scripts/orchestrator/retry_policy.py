from __future__ import annotations

from enum import Enum


class FailureClass(str, Enum):
    TRANSIENT_TECHNICAL = "TRANSIENT_TECHNICAL"
    DETERMINISTIC_TECHNICAL = "DETERMINISTIC_TECHNICAL"
    DOMAIN_AMBIGUITY = "DOMAIN_AMBIGUITY"
    POLICY_OR_RIGHTS = "POLICY_OR_RIGHTS"


class StageFailure(RuntimeError):
    def __init__(self, category: FailureClass, message: str) -> None:
        super().__init__(message)
        self.category = FailureClass(category)


def retry_delay(category: FailureClass, attempt: int) -> float | None:
    """Two automatic retries, only for explicitly classified transient failures."""
    if category == FailureClass.TRANSIENT_TECHNICAL and 1 <= attempt <= 2:
        return (2.0, 8.0)[attempt - 1]
    return None
