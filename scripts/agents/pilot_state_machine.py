from __future__ import annotations


class PilotStateMachineError(RuntimeError):
    """Raised when an illegal state transition is attempted."""
    pass


VALID_TRANSITIONS: dict[tuple[str, str], str] = {
    ("READY_TO_EXPORT", "export_bundle"): "WAITING_FOR_RESULT",
    ("WAITING_FOR_RESULT", "import_bundle"): "RESULT_IMPORTED",
    ("RESULT_IMPORTED", "integrity_failed"): "VALIDATION_FAILED",
    ("RESULT_IMPORTED", "integrity_passed"): "NEEDS_HUMAN_REVIEW",
    ("VALIDATION_FAILED", "request_rework"): "REWORK_REQUIRED",
    ("NEEDS_HUMAN_REVIEW", "human_reject"): "REJECTED",
    ("REJECTED", "request_rework"): "REWORK_REQUIRED",
    ("REWORK_REQUIRED", "prepare_attempt"): "READY_TO_EXPORT",
    ("NEEDS_HUMAN_REVIEW", "human_approve"): "APPROVED",
    ("APPROVED", "apply_persistence"): "PERSISTED",
    ("APPROVED", "persistence_failed"): "VALIDATION_FAILED",
    ("PERSISTED", "qa_gates_passed"): "QA_PASS",
    ("PERSISTED", "qa_gates_failed"): "QA_FAILED",
    ("QA_FAILED", "request_rework"): "REWORK_REQUIRED",
    ("QA_PASS", "project_preview"): "PREVIEW_READY",
    ("PREVIEW_READY", "validate_navigation"): "PILOT_VALIDATED",
}


class PilotStateMachine:
    """Deterministic, fail-closed state machine enforcing pilot lifecycle transitions."""

    def can_transition(self, current_state: str, event: str) -> bool:
        """Returns True if the transition is explicitly permitted."""
        return (current_state, event) in VALID_TRANSITIONS

    def transition(self, current_state: str, event: str) -> str:
        """Transitions from current_state on event, or raises PilotStateMachineError."""
        key = (current_state, event)
        if key not in VALID_TRANSITIONS:
            raise PilotStateMachineError(
                f"ERR_STATE_TRANSITION_ILLEGAL: Illegal transition from state '{current_state}' on event '{event}'"
            )
        return VALID_TRANSITIONS[key]
