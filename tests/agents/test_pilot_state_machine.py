from __future__ import annotations

import pytest
from scripts.agents.pilot_state_machine import PilotStateMachine, PilotStateMachineError


def test_valid_transitions():
    sm = PilotStateMachine()

    assert sm.transition("READY_TO_EXPORT", "export_bundle") == "WAITING_FOR_RESULT"
    assert sm.transition("WAITING_FOR_RESULT", "import_bundle") == "RESULT_IMPORTED"
    assert sm.transition("RESULT_IMPORTED", "integrity_failed") == "VALIDATION_FAILED"
    assert sm.transition("RESULT_IMPORTED", "integrity_passed") == "NEEDS_HUMAN_REVIEW"
    assert sm.transition("VALIDATION_FAILED", "request_rework") == "REWORK_REQUIRED"
    assert sm.transition("NEEDS_HUMAN_REVIEW", "human_reject") == "REJECTED"
    assert sm.transition("REJECTED", "request_rework") == "REWORK_REQUIRED"
    assert sm.transition("REWORK_REQUIRED", "prepare_attempt") == "READY_TO_EXPORT"
    assert sm.transition("NEEDS_HUMAN_REVIEW", "human_approve") == "APPROVED"
    assert sm.transition("APPROVED", "apply_persistence") == "PERSISTED"
    assert sm.transition("APPROVED", "persistence_failed") == "VALIDATION_FAILED"
    assert sm.transition("PERSISTED", "qa_gates_passed") == "QA_PASS"
    assert sm.transition("PERSISTED", "qa_gates_failed") == "QA_FAILED"
    assert sm.transition("QA_FAILED", "request_rework") == "REWORK_REQUIRED"
    assert sm.transition("QA_PASS", "project_preview") == "PREVIEW_READY"
    assert sm.transition("PREVIEW_READY", "validate_navigation") == "PILOT_VALIDATED"


def test_illegal_transition_fails_closed():
    sm = PilotStateMachine()

    with pytest.raises(PilotStateMachineError) as exc:
        sm.transition("READY_TO_EXPORT", "human_approve")
    assert "ERR_STATE_TRANSITION_ILLEGAL" in str(exc.value)

    with pytest.raises(PilotStateMachineError) as exc:
        sm.transition("APPROVED", "export_bundle")
    assert "ERR_STATE_TRANSITION_ILLEGAL" in str(exc.value)


def test_can_transition():
    sm = PilotStateMachine()

    assert sm.can_transition("READY_TO_EXPORT", "export_bundle") is True
    assert sm.can_transition("READY_TO_EXPORT", "human_approve") is False
