import copy
from pathlib import Path
import pytest

from scripts.agents.contracts import ContractValidationError
from scripts.agents.gate_engine import PIPELINE_STAGES, GateEngine
from scripts.agents.orchestrator_state import (
    STAGE_AGENT_MAP,
    OrchestratorSelection,
    OrchestratorStateError,
    OrchestratorStateSelector,
)

ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Test Helpers & Fixtures
# ---------------------------------------------------------------------------


def _valid_job_payload(
    stage_statuses: dict[str, str] | None = None,
    current_stage: str = "source",
    status: str = "in_progress",
) -> dict:
    default_stages = {
        "source": "waiting",
        "extraction": "waiting",
        "editorial": "waiting",
        "entities": "waiting",
        "relations": "waiting",
        "frontend": "waiting",
        "qa": "waiting",
        "release": "waiting",
    }
    if stage_statuses:
        default_stages.update(stage_statuses)

    return {
        "schemaVersion": "1.0",
        "jobId": "JOB-TREVAS-001",
        "kind": "book_ingestion",
        "bookId": "trevas",
        "status": status,
        "createdAt": "2026-09-04T12:00:00Z",
        "updatedAt": "2026-09-04T12:00:00Z",
        "requestedBy": "orchestrator",
        "currentStage": current_stage,
        "stages": default_stages,
        "humanReviewRequired": False,
        "blockingReasons": [],
        "artifacts": [],
        "history": [
            {
                "timestamp": "2026-09-04T12:00:00Z",
                "event": "created",
                "stage": "source",
                "message": "Job created"
            }
        ]
    }


def _valid_source_manifest(
    rights_status: str = "AUTHORIZED",
    publication_mode: str = "FULL_TEXT",
) -> dict:
    return {
        "schemaVersion": "1.0",
        "sourceId": "SRC-TREVAS-3ED",
        "title": "Trevas 3.0",
        "path": "Livros/trevas-3-0.pdf",
        "extension": ".pdf",
        "sha256": "a" * 64,
        "rightsStatus": rights_status,
        "visibility": "public",
        "publicationMode": publication_mode
    }


# ---------------------------------------------------------------------------
# Hierarchy & Dataclass Tests
# ---------------------------------------------------------------------------


def test_orchestrator_state_error_hierarchy():
    assert issubclass(OrchestratorStateError, RuntimeError)


def test_orchestrator_selection_immutability():
    sel = OrchestratorSelection(
        action="RUN_STAGE",
        code="ALLOW",
        stage="editorial",
        agent="editorial-agent",
        reasons=("Stage is ready",)
    )
    assert sel.action == "RUN_STAGE"
    assert sel.code == "ALLOW"
    assert sel.stage == "editorial"
    assert sel.agent == "editorial-agent"
    assert sel.reasons == ("Stage is ready",)

    with pytest.raises((AttributeError, TypeError)):
        sel.action = "WAIT"


def test_orchestrator_selection_equality_and_hashing():
    s1 = OrchestratorSelection(action="WAIT", code="STAGE_WAITING", stage="source", agent="source-agent")
    s2 = OrchestratorSelection(action="WAIT", code="STAGE_WAITING", stage="source", agent="source-agent")
    s3 = OrchestratorSelection(action="BLOCKED", code="STAGE_BLOCKED", stage="source", agent="source-agent")

    assert s1 == s2
    assert s1 != s3
    assert hash(s1) == hash(s2)


def test_stage_agent_map_covers_all_pipeline_stages():
    for stage in PIPELINE_STAGES:
        assert stage in STAGE_AGENT_MAP
        agent = STAGE_AGENT_MAP[stage]
        assert agent != "orchestrator"
        assert agent.endswith("-agent")

    assert STAGE_AGENT_MAP["qa"] == "qa-release-agent"
    assert STAGE_AGENT_MAP["release"] == "qa-release-agent"


# ---------------------------------------------------------------------------
# Stage Execution Recommendation Tests (ready status)
# ---------------------------------------------------------------------------


def test_select_initial_source_stage_ready():
    selector = OrchestratorStateSelector()
    job = _valid_job_payload(stage_statuses={"source": "ready"}, current_stage="source")

    selection = selector.select(job)
    assert selection.action == "RUN_STAGE"
    assert selection.code == "ALLOW"
    assert selection.stage == "source"
    assert selection.agent == "source-agent"


@pytest.mark.parametrize(
    "target_stage,predecessor,expected_agent",
    [
        ("extraction", "source", "extraction-agent"),
        ("editorial", "extraction", "editorial-agent"),
        ("entities", "editorial", "entity-agent"),
        ("relations", "entities", "relations-agent"),
        ("frontend", "relations", "frontend-agent"),
        ("qa", "frontend", "qa-release-agent"),
    ]
)
def test_select_ready_stage_with_passed_predecessor(target_stage, predecessor, expected_agent):
    selector = OrchestratorStateSelector()
    # Mark all stages prior to target_stage as "pass"
    stage_statuses = {}
    for s in PIPELINE_STAGES:
        if s == target_stage:
            stage_statuses[s] = "ready"
            break
        stage_statuses[s] = "pass"

    job = _valid_job_payload(stage_statuses=stage_statuses, current_stage=target_stage)
    selection = selector.select(job)

    assert selection.action == "RUN_STAGE"
    assert selection.code == "ALLOW"
    assert selection.stage == target_stage
    assert selection.agent == expected_agent


def test_select_release_ready_with_valid_source_manifest():
    selector = OrchestratorStateSelector()
    stage_statuses = {s: "pass" for s in PIPELINE_STAGES}
    stage_statuses["release"] = "ready"

    job = _valid_job_payload(stage_statuses=stage_statuses, current_stage="release")
    manifest = _valid_source_manifest(rights_status="AUTHORIZED", publication_mode="FULL_TEXT")

    selection = selector.select(job, source_manifest=manifest)
    assert selection.action == "RUN_STAGE"
    assert selection.code == "ALLOW"
    assert selection.stage == "release"
    assert selection.agent == "qa-release-agent"


def test_select_release_ready_without_source_manifest_blocks():
    selector = OrchestratorStateSelector()
    stage_statuses = {s: "pass" for s in PIPELINE_STAGES}
    stage_statuses["release"] = "ready"

    job = _valid_job_payload(stage_statuses=stage_statuses, current_stage="release")

    selection = selector.select(job, source_manifest=None)
    assert selection.action == "BLOCKED"
    assert selection.code == "SOURCE_MANIFEST_REQUIRED"
    assert selection.stage == "release"
    assert selection.agent == "qa-release-agent"


def test_select_release_ready_with_incompatible_rights_blocks():
    selector = OrchestratorStateSelector()
    stage_statuses = {s: "pass" for s in PIPELINE_STAGES}
    stage_statuses["release"] = "ready"

    job = _valid_job_payload(stage_statuses=stage_statuses, current_stage="release")
    manifest = _valid_source_manifest(rights_status="METADATA_ONLY", publication_mode="FULL_TEXT")

    selection = selector.select(job, source_manifest=manifest)
    assert selection.action == "BLOCKED"
    assert selection.code == "RIGHTS_BLOCK_RELEASE"
    assert selection.stage == "release"


# ---------------------------------------------------------------------------
# Non-Ready Status Tests
# ---------------------------------------------------------------------------


def test_select_stage_waiting():
    selector = OrchestratorStateSelector()
    job = _valid_job_payload(stage_statuses={"source": "waiting"})

    selection = selector.select(job)
    assert selection.action == "WAIT"
    assert selection.code == "STAGE_WAITING"
    assert selection.stage == "source"
    assert selection.agent == "source-agent"


def test_select_stage_running():
    selector = OrchestratorStateSelector()
    job = _valid_job_payload(stage_statuses={"source": "running"}, current_stage="source")

    selection = selector.select(job)
    assert selection.action == "WAIT"
    assert selection.code == "STAGE_ALREADY_RUNNING"
    assert selection.stage == "source"
    assert selection.agent == "source-agent"


def test_select_stage_blocked():
    selector = OrchestratorStateSelector()
    job = _valid_job_payload(stage_statuses={"source": "blocked"}, current_stage="source")

    selection = selector.select(job)
    assert selection.action == "BLOCKED"
    assert selection.code == "STAGE_BLOCKED"
    assert selection.stage == "source"
    assert selection.agent == "source-agent"


def test_select_stage_failed():
    selector = OrchestratorStateSelector()
    job = _valid_job_payload(stage_statuses={"source": "fail"}, current_stage="source")

    selection = selector.select(job)
    assert selection.action == "BLOCKED"
    assert selection.code == "STAGE_FAILED"
    assert selection.stage == "source"
    assert selection.agent == "source-agent"


def test_select_stage_human_review():
    selector = OrchestratorStateSelector()
    job = _valid_job_payload(stage_statuses={"source": "human_review"}, current_stage="source")

    selection = selector.select(job)
    assert selection.action == "HUMAN_REVIEW"
    assert selection.code == "HUMAN_REVIEW_REQUIRED"
    assert selection.stage == "source"
    assert selection.agent == "source-agent"


# ---------------------------------------------------------------------------
# Pipeline Priority & Sequential Order Tests
# ---------------------------------------------------------------------------


def test_select_prioritizes_earliest_uncompleted_stage():
    selector = OrchestratorStateSelector()
    # source and extraction pass, editorial and entities both ready
    job = _valid_job_payload(
        stage_statuses={
            "source": "pass",
            "extraction": "pass",
            "editorial": "ready",
            "entities": "ready",
        }
    )

    selection = selector.select(job)
    assert selection.stage == "editorial"
    assert selection.agent == "editorial-agent"
    assert selection.action == "RUN_STAGE"


# ---------------------------------------------------------------------------
# Job-Level Status Precedence Tests
# ---------------------------------------------------------------------------


def test_select_job_status_blocked_takes_precedence():
    selector = OrchestratorStateSelector()
    job = _valid_job_payload(
        status="blocked",
        stage_statuses={"source": "ready"}
    )

    selection = selector.select(job)
    assert selection.action == "BLOCKED"
    assert selection.code == "JOB_BLOCKED"


def test_select_job_status_needs_review_takes_precedence():
    selector = OrchestratorStateSelector()
    job = _valid_job_payload(
        status="needs_review",
        stage_statuses={"source": "ready"}
    )

    selection = selector.select(job)
    assert selection.action == "HUMAN_REVIEW"
    assert selection.code == "JOB_REVIEW_REQUIRED"


def test_select_job_status_done_when_completed():
    selector = OrchestratorStateSelector()
    all_passed = {s: "pass" for s in PIPELINE_STAGES}
    job = _valid_job_payload(
        status="done",
        stage_statuses=all_passed,
        current_stage="release"
    )

    selection = selector.select(job)
    assert selection.action == "NO_ACTION"
    assert selection.code == "JOB_ALREADY_DONE"


def test_select_job_status_done_with_incomplete_stages_raises_state_error():
    selector = OrchestratorStateSelector()
    job = _valid_job_payload(
        status="done",
        stage_statuses={"source": "pass", "extraction": "waiting"}
    )

    with pytest.raises(OrchestratorStateError):
        selector.select(job)


# ---------------------------------------------------------------------------
# Pipeline Completed Tests (evaluate_done)
# ---------------------------------------------------------------------------


def test_select_pipeline_all_passed_without_human_validation():
    selector = OrchestratorStateSelector()
    all_passed = {s: "pass" for s in PIPELINE_STAGES}
    job = _valid_job_payload(stage_statuses=all_passed, status="approved")

    selection = selector.select(job, human_validated=False)
    assert selection.action == "HUMAN_REVIEW"
    assert selection.code == "HUMAN_VALIDATION_REQUIRED"
    assert selection.stage is None
    assert selection.agent is None


def test_select_pipeline_all_passed_with_human_validation():
    selector = OrchestratorStateSelector()
    all_passed = {s: "pass" for s in PIPELINE_STAGES}
    job = _valid_job_payload(stage_statuses=all_passed, status="approved")

    selection = selector.select(job, human_validated=True)
    assert selection.action == "READY_FOR_DONE"
    assert selection.code == "ALLOW"
    assert selection.stage is None
    assert selection.agent is None


# ---------------------------------------------------------------------------
# Pipeline Inconsistency Tests
# ---------------------------------------------------------------------------


def test_select_detects_out_of_order_passed_stage():
    selector = OrchestratorStateSelector()
    # extraction is waiting, but editorial is pass
    job = _valid_job_payload(
        stage_statuses={
            "source": "pass",
            "extraction": "waiting",
            "editorial": "pass",
        }
    )

    with pytest.raises(OrchestratorStateError) as exc_info:
        selector.select(job)
    assert "editorial" in str(exc_info.value)
    assert "extraction" in str(exc_info.value)


def test_select_detects_multiple_running_stages():
    selector = OrchestratorStateSelector()
    job = _valid_job_payload(
        stage_statuses={
            "source": "pass",
            "extraction": "running",
            "editorial": "running",
        }
    )

    with pytest.raises(OrchestratorStateError) as exc_info:
        selector.select(job)
    assert "running" in str(exc_info.value).lower()


def test_select_detects_multiple_human_review_stages():
    selector = OrchestratorStateSelector()
    job = _valid_job_payload(
        stage_statuses={
            "source": "human_review",
            "extraction": "human_review",
        }
    )

    with pytest.raises(OrchestratorStateError) as exc_info:
        selector.select(job)
    assert "human_review" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Immutability & Determinism Tests
# ---------------------------------------------------------------------------


def test_selector_inputs_immutability():
    selector = OrchestratorStateSelector()
    job = _valid_job_payload(stage_statuses={"source": "ready"})
    manifest = _valid_source_manifest()

    job_before = copy.deepcopy(job)
    manifest_before = copy.deepcopy(manifest)

    selector.select(job, source_manifest=manifest)

    assert job == job_before
    assert manifest == manifest_before


def test_selector_determinism():
    selector = OrchestratorStateSelector()
    job = _valid_job_payload(stage_statuses={"source": "pass", "extraction": "ready"})

    s1 = selector.select(job)
    s2 = selector.select(job)

    assert s1 == s2


def test_selector_invalid_job_schema_propagates_contract_validation_error():
    selector = OrchestratorStateSelector()
    job = _valid_job_payload()
    job["status"] = "invalid_job_status"

    with pytest.raises(ContractValidationError):
        selector.select(job)
