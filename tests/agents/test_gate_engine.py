import copy
from pathlib import Path
import pytest

from scripts.agents.contracts import ContractValidationError
from scripts.agents.gate_engine import (
    PIPELINE_STAGES,
    GateDecision,
    GateEngine,
    GateEngineError,
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
    visibility: str = "public",
) -> dict:
    return {
        "schemaVersion": "1.0",
        "sourceId": "SRC-TREVAS-3ED",
        "title": "Trevas 3.0",
        "path": "Livros/trevas-3-0.pdf",
        "extension": ".pdf",
        "sha256": "a" * 64,
        "rightsStatus": rights_status,
        "visibility": visibility,
        "publicationMode": publication_mode
    }


# ---------------------------------------------------------------------------
# GateDecision & Error Hierarchy Tests
# ---------------------------------------------------------------------------


def test_gate_engine_error_hierarchy():
    assert issubclass(GateEngineError, RuntimeError)


def test_gate_decision_immutability():
    decision = GateDecision(allowed=True, code="ALLOW", reasons=("All good",))
    assert decision.allowed is True
    assert decision.code == "ALLOW"
    assert decision.reasons == ("All good",)

    # Dataclass is frozen
    with pytest.raises((AttributeError, TypeError)):
        decision.allowed = False


def test_gate_decision_equality_and_hashing():
    d1 = GateDecision(allowed=True, code="ALLOW", reasons=("Reason 1", "Reason 2"))
    d2 = GateDecision(allowed=True, code="ALLOW", reasons=("Reason 1", "Reason 2"))
    d3 = GateDecision(allowed=False, code="DENY", reasons=("Reason 1",))

    assert d1 == d2
    assert d1 != d3
    assert hash(d1) == hash(d2)


def test_gate_decision_validation():
    with pytest.raises(TypeError):
        GateDecision(allowed="true", code="ALLOW", reasons=())

    with pytest.raises(ValueError):
        GateDecision(allowed=True, code="", reasons=())

    with pytest.raises(TypeError):
        GateDecision(allowed=True, code="ALLOW", reasons=123)


# ---------------------------------------------------------------------------
# Stage Entry Gate Tests
# ---------------------------------------------------------------------------


def test_stage_entry_source_is_always_allowed():
    engine = GateEngine()
    job = _valid_job_payload()
    decision = engine.evaluate_stage_entry(job, "source")

    assert decision.allowed is True
    assert decision.code == "ALLOW"
    assert len(decision.reasons) > 0


@pytest.mark.parametrize(
    "stage,pred",
    [
        ("extraction", "source"),
        ("editorial", "extraction"),
        ("entities", "editorial"),
        ("relations", "entities"),
        ("frontend", "relations"),
        ("qa", "frontend"),
        ("release", "qa"),
    ]
)
def test_stage_entry_allows_when_predecessor_passed(stage, pred):
    engine = GateEngine()
    job = _valid_job_payload(stage_statuses={pred: "pass"})
    decision = engine.evaluate_stage_entry(job, stage)

    assert decision.allowed is True
    assert decision.code == "ALLOW"
    assert pred in decision.reasons[0]


@pytest.mark.parametrize(
    "stage,pred",
    [
        ("extraction", "source"),
        ("editorial", "extraction"),
        ("entities", "editorial"),
        ("relations", "entities"),
        ("frontend", "relations"),
        ("qa", "frontend"),
        ("release", "qa"),
    ]
)
@pytest.mark.parametrize(
    "unpassed_status",
    ["waiting", "ready", "running", "fail", "blocked", "human_review"]
)
def test_stage_entry_denies_when_predecessor_not_passed(stage, pred, unpassed_status):
    engine = GateEngine()
    job = _valid_job_payload(stage_statuses={pred: unpassed_status})
    decision = engine.evaluate_stage_entry(job, stage)

    assert decision.allowed is False
    assert decision.code == "PREREQUISITE_STAGE_NOT_PASSED"
    assert len(decision.reasons) > 0
    assert pred in decision.reasons[0]
    assert unpassed_status in decision.reasons[0]


def test_stage_entry_blocks_skipping_intermediate_stage():
    engine = GateEngine()
    # source and editorial passed, but entities is still waiting
    job = _valid_job_payload(
        stage_statuses={
            "source": "pass",
            "extraction": "pass",
            "editorial": "pass",
            "entities": "waiting",
            "relations": "waiting",
        }
    )
    # relations depends directly on entities, which is waiting
    decision = engine.evaluate_stage_entry(job, "relations")

    assert decision.allowed is False
    assert decision.code == "PREREQUISITE_STAGE_NOT_PASSED"
    assert "entities" in decision.reasons[0]


def test_stage_entry_invalid_stage_raises_gate_engine_error():
    engine = GateEngine()
    job = _valid_job_payload()

    with pytest.raises(GateEngineError) as exc_info:
        engine.evaluate_stage_entry(job, "banana")
    assert "banana" in str(exc_info.value)


def test_stage_entry_invalid_job_schema_propagates_contract_validation_error():
    engine = GateEngine()
    job = _valid_job_payload()
    job["status"] = "invalid_status"

    with pytest.raises(ContractValidationError):
        engine.evaluate_stage_entry(job, "extraction")


def test_stage_entry_non_dict_job_raises():
    engine = GateEngine()
    with pytest.raises((GateEngineError, ContractValidationError)):
        engine.evaluate_stage_entry("not a dict", "source")


# ---------------------------------------------------------------------------
# Done Gate Tests (ADR-0002)
# ---------------------------------------------------------------------------


def test_done_gate_denies_when_human_validated_is_false():
    engine = GateEngine()
    all_passed = {s: "pass" for s in PIPELINE_STAGES}
    job = _valid_job_payload(stage_statuses=all_passed, status="approved")

    decision = engine.evaluate_done(job, human_validated=False)

    assert decision.allowed is False
    assert decision.code == "HUMAN_VALIDATION_REQUIRED"
    assert len(decision.reasons) > 0
    assert "human validation" in decision.reasons[0].lower()


def test_done_gate_allows_when_human_validated_and_all_stages_pass():
    engine = GateEngine()
    all_passed = {s: "pass" for s in PIPELINE_STAGES}
    job = _valid_job_payload(stage_statuses=all_passed, status="approved")

    decision = engine.evaluate_done(job, human_validated=True)

    assert decision.allowed is True
    assert decision.code == "ALLOW"
    assert len(decision.reasons) > 0


def test_done_gate_denies_when_human_validated_true_but_stages_incomplete():
    engine = GateEngine()
    stages = {s: "pass" for s in PIPELINE_STAGES}
    stages["release"] = "waiting"  # release not passed
    job = _valid_job_payload(stage_statuses=stages, status="approved")

    decision = engine.evaluate_done(job, human_validated=True)

    assert decision.allowed is False
    assert decision.code == "PIPELINE_NOT_COMPLETED"
    assert "release" in decision.reasons[0]


def test_done_gate_strictly_rejects_non_boolean_human_validated():
    engine = GateEngine()
    job = _valid_job_payload()

    for invalid_val in ["true", "yes", 1, None, []]:
        with pytest.raises(GateEngineError):
            engine.evaluate_done(job, human_validated=invalid_val)


def test_done_gate_does_not_infer_approval_from_job_status_alone():
    engine = GateEngine()
    all_passed = {s: "pass" for s in PIPELINE_STAGES}
    job = _valid_job_payload(stage_statuses=all_passed, status="approved")

    # Even with status="approved", if human_validated is False -> DENY
    decision = engine.evaluate_done(job, human_validated=False)
    assert decision.allowed is False
    assert decision.code == "HUMAN_VALIDATION_REQUIRED"


# ---------------------------------------------------------------------------
# Release Gate Tests
# ---------------------------------------------------------------------------


def test_release_gate_denies_when_qa_stage_not_passed():
    engine = GateEngine()
    job = _valid_job_payload(stage_statuses={"qa": "fail"})
    manifest = _valid_source_manifest()

    decision = engine.evaluate_release(job, source_manifest=manifest)
    assert decision.allowed is False
    assert decision.code == "QA_STAGE_NOT_PASSED"
    assert "qa" in decision.reasons[0].lower()


@pytest.mark.parametrize("blocked_rights", ["UNKNOWN", "PRIVATE"])
def test_release_gate_denies_blocked_rights_statuses(blocked_rights):
    engine = GateEngine()
    job = _valid_job_payload(stage_statuses={"qa": "pass"})
    manifest = _valid_source_manifest(rights_status=blocked_rights)

    decision = engine.evaluate_release(job, source_manifest=manifest)
    assert decision.allowed is False
    assert decision.code == "RIGHTS_BLOCK_RELEASE"
    assert blocked_rights in decision.reasons[0]


def test_release_gate_denies_not_public_publication_mode():
    engine = GateEngine()
    job = _valid_job_payload(stage_statuses={"qa": "pass"})
    manifest = _valid_source_manifest(rights_status="AUTHORIZED", publication_mode="NOT_PUBLIC")

    decision = engine.evaluate_release(job, source_manifest=manifest)
    assert decision.allowed is False
    assert decision.code == "RIGHTS_BLOCK_RELEASE"
    assert "NOT_PUBLIC" in decision.reasons[0]


@pytest.mark.parametrize(
    "rights_status,pub_mode",
    [
        ("AUTHORIZED", "FULL_TEXT"),
        ("PUBLIC_DOMAIN", "FULL_TEXT"),
        ("METADATA_ONLY", "METADATA_ONLY"),
        ("AUTHORIZED", "SUMMARY_AND_METADATA"),
    ]
)
def test_release_gate_allows_valid_rights_and_publication(rights_status, pub_mode):
    engine = GateEngine()
    job = _valid_job_payload(stage_statuses={"qa": "pass"})
    manifest = _valid_source_manifest(rights_status=rights_status, publication_mode=pub_mode)

    decision = engine.evaluate_release(job, source_manifest=manifest)
    assert decision.allowed is True
def test_release_gate_denies_when_source_manifest_is_none():
    engine = GateEngine()
    job = _valid_job_payload(stage_statuses={"qa": "pass"})
    decision = engine.evaluate_release(job, source_manifest=None)
    assert decision.allowed is False
    assert decision.code == "SOURCE_MANIFEST_REQUIRED"
    assert len(decision.reasons) > 0
    assert "source manifest" in decision.reasons[0].lower()



def test_release_gate_invalid_source_manifest_schema_raises():
    engine = GateEngine()
    job = _valid_job_payload(stage_statuses={"qa": "pass"})
    bad_manifest = _valid_source_manifest()
    bad_manifest["rightsStatus"] = "INVALID_RIGHTS"

    with pytest.raises(ContractValidationError):
        engine.evaluate_release(job, source_manifest=bad_manifest)


# ---------------------------------------------------------------------------
# Immutability & Determinism Tests
# ---------------------------------------------------------------------------


def test_gate_engine_inputs_immutability():
    engine = GateEngine()
    job = _valid_job_payload(stage_statuses={"source": "pass", "qa": "pass"})
    manifest = _valid_source_manifest()

    job_before = copy.deepcopy(job)
    manifest_before = copy.deepcopy(manifest)

    engine.evaluate_stage_entry(job, "extraction")
    engine.evaluate_done(job, human_validated=True)
    engine.evaluate_release(job, source_manifest=manifest)

    assert job == job_before
    assert manifest == manifest_before


def test_gate_engine_determinism():
    engine = GateEngine()
    job = _valid_job_payload(stage_statuses={"editorial": "pass"})

    d1 = engine.evaluate_stage_entry(job, "entities")
    d2 = engine.evaluate_stage_entry(job, "entities")
    assert d1 == d2

    d3 = engine.evaluate_done(job, human_validated=False)
    d4 = engine.evaluate_done(job, human_validated=False)
    assert d3 == d4
