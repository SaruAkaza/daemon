from __future__ import annotations

import copy
from pathlib import Path
import pytest

from scripts.agents.context_loader import ContextLoader
from scripts.agents.context_pack_builder import ContextPackBuilder
from scripts.agents.contracts import validate_payload
from scripts.agents.gate_engine import PIPELINE_STAGES, GateEngine
from scripts.agents.handoff_store import HandoffStore
from scripts.agents.job_store import JobStore
from scripts.agents.orchestrator_state import (
    STAGE_AGENT_MAP,
    OrchestratorSelection,
    OrchestratorStateError,
    OrchestratorStateSelector,
)

# ---------------------------------------------------------------------------
# Test Helpers & Fixture Factories
# ---------------------------------------------------------------------------

def _make_e2e_job_payload(
    job_id: str = "JOB-TEST-CANONICAL-001",
    book_id: str = "test-book",
    current_stage: str = "source",
    status: str = "in_progress",
    stage_statuses: dict[str, str] | None = None,
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
        "jobId": job_id,
        "kind": "book_ingestion",
        "bookId": book_id,
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
                "message": f"Job {job_id} initiated for {book_id}"
            }
        ]
    }


def _make_e2e_handoff_payload(
    handoff_id: str = "HND-TEST-EXTRACTION-001",
    job_id: str = "JOB-TEST-CANONICAL-001",
    agent: str = "extraction-agent",
    stage: str = "extraction",
) -> dict:
    return {
        "schemaVersion": "1.0",
        "handoffId": handoff_id,
        "jobId": job_id,
        "agent": agent,
        "stage": stage,
        "status": "pass_with_warnings",
        "startedAt": "2026-09-04T12:00:00Z",
        "completedAt": "2026-09-04T12:10:00Z",
        "inputs": ["Livros/test-book.pdf"],
        "outputs": ["data/text/test-book.txt"],
        "changes": ["Extracted 150 pages", "Normalized hyphenation"],
        "evidence": [
            {
                "type": "coverage",
                "value": "150/150 pages",
                "command": "python scripts/check_book_coverage.py"
            }
        ],
        "warnings": [
            {
                "code": "OCR_UNCERTAIN",
                "source": "test-book",
                "page": 42,
                "message": "Low confidence on footnote"
            }
        ],
        "uncertainties": [],
        "qualityMetrics": {
            "sourcePages": 150,
            "processedPages": 150,
            "coverageRatio": 1.0,
            "warningsCount": 1
        },
        "recommendedNextStage": "editorial",
        "requiresHumanReview": False,
        "blockingReason": None
    }


def _make_e2e_source_manifest(
    source_id: str = "SRC-TEST-BOOK-001",
    rights_status: str = "PUBLIC_DOMAIN",
    publication_mode: str = "FULL_TEXT",
) -> dict:
    return {
        "schemaVersion": "1.0",
        "sourceId": source_id,
        "title": "Livro de Teste Canônico",
        "path": "Livros/test-book.pdf",
        "extension": ".pdf",
        "sha256": "f" * 64,
        "rightsStatus": rights_status,
        "visibility": "public",
        "publicationMode": publication_mode
    }


# ---------------------------------------------------------------------------
# End-to-End Orchestration Integration Tests
# ---------------------------------------------------------------------------

def test_e2e_full_stage_progression(tmp_path: Path):
    """Demonstrate a full, deterministic lifecycle progression through all 8 stages.
    
    Exercises JobStore, GateEngine, and OrchestratorStateSelector at every transition.
    """
    jobs_dir = tmp_path / "jobs"
    job_store = JobStore(root=jobs_dir)
    gate_engine = GateEngine()
    selector = OrchestratorStateSelector(gate_engine=gate_engine)

    manifest = _make_e2e_source_manifest()
    validate_payload("source-manifest.schema.json", manifest)

    # 1. Initialize Job with 'source' ready and all other stages 'waiting'
    initial_job = _make_e2e_job_payload(
        job_id="JOB-E2E-001",
        book_id="test-e2e-book",
        current_stage="source",
        stage_statuses={"source": "ready"}
    )
    job_store.create(initial_job)

    # Verify persistence round-trip
    current_job = job_store.load("JOB-E2E-001")
    assert current_job == initial_job

    # 2. Iterate sequentially through all 8 stages
    for idx, stage in enumerate(PIPELINE_STAGES):
        expected_agent = STAGE_AGENT_MAP[stage]

        # Query next safe action from OrchestratorStateSelector
        selection = selector.select(
            current_job,
            source_manifest=manifest if stage == "release" else None,
            human_validated=False
        )

        # Assert correct action and mapped agent
        assert selection.action == "RUN_STAGE"
        assert selection.code == "ALLOW"
        assert selection.stage == stage
        assert selection.agent == expected_agent

        # Simulate external agent execution and update Job payload
        updated_job = copy.deepcopy(current_job)
        updated_job["stages"][stage] = "pass"

        is_last_stage = (idx == len(PIPELINE_STAGES) - 1)
        if not is_last_stage:
            next_stage = PIPELINE_STAGES[idx + 1]
            updated_job["stages"][next_stage] = "ready"
            updated_job["currentStage"] = next_stage

        updated_job["history"].append({
            "timestamp": f"2026-09-04T12:{idx + 1:02d}:00Z",
            "event": "stage_completed",
            "stage": stage,
            "message": f"Stage {stage} successfully processed by {expected_agent}"
        })

        # Persist through JobStore API
        job_store.update(updated_job)

        # Reload from disk to verify persistence
        current_job = job_store.load("JOB-E2E-001")
        assert current_job["stages"][stage] == "pass"

    # 3. All 8 stages passed -> evaluate done gate (ADR-0002 compliance)
    pre_done_selection = selector.select(
        current_job,
        source_manifest=manifest,
        human_validated=False
    )
    assert pre_done_selection.action == "HUMAN_REVIEW"
    assert pre_done_selection.code == "HUMAN_VALIDATION_REQUIRED"
    assert pre_done_selection.stage is None

    # Confirm human validation permits completion
    final_selection = selector.select(
        current_job,
        source_manifest=manifest,
        human_validated=True
    )
    assert final_selection.action == "READY_FOR_DONE"
    assert final_selection.code == "ALLOW"
    assert final_selection.stage is None


def test_e2e_context_pack_and_handoff_integration(tmp_path: Path):
    """Demonstrate inter-stage handoff persistence and layered context pack assembly.
    
    Exercises HandoffStore, ContextLoader, ContextPackBuilder, and minimum sufficient context isolation.
    """
    # 1. Create and persist inter-stage handoff
    handoffs_dir = tmp_path / "handoffs"
    handoff_store = HandoffStore(root=handoffs_dir)

    handoff_payload = _make_e2e_handoff_payload(
        handoff_id="HND-E2E-EXTRACTION-001",
        job_id="JOB-E2E-001",
        agent="extraction-agent",
        stage="extraction"
    )
    handoff_store.create(handoff_payload)

    loaded_handoff = handoff_store.load("HND-E2E-EXTRACTION-001")
    assert loaded_handoff == handoff_payload
    assert loaded_handoff["status"] == "pass_with_warnings"

    # 2. Setup synthetic repository structure for context loading
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir(parents=True, exist_ok=True)

    const_path = repo_dir / "docs" / "architecture" / "constitution.md"
    const_path.parent.mkdir(parents=True, exist_ok=True)
    const_path.write_text("# Constitution\nInviolable rules.", encoding="utf-8")

    domain_path = repo_dir / "docs" / "reference" / "cataloging-rules.md"
    domain_path.parent.mkdir(parents=True, exist_ok=True)
    domain_path.write_text("# Cataloging Rules\nTaxonomy definitions.", encoding="utf-8")

    book_path = repo_dir / "docs" / "context" / "books" / "test-book.md"
    book_path.parent.mkdir(parents=True, exist_ok=True)
    book_path.write_text("# Book Context\nBook structural analysis.", encoding="utf-8")

    job_text_path = repo_dir / "coordination" / "jobs" / "JOB-E2E-001.json"
    job_text_path.parent.mkdir(parents=True, exist_ok=True)
    job_text_path.write_text('{"jobId": "JOB-E2E-001", "status": "in_progress"}', encoding="utf-8")

    handoff_text_path = repo_dir / "coordination" / "handoffs" / "HND-E2E-EXTRACTION-001.md"
    handoff_text_path.parent.mkdir(parents=True, exist_ok=True)
    handoff_text_path.write_text("# Extraction Handoff Summary\n150 pages extracted.", encoding="utf-8")

    contract_path = repo_dir / "schemas" / "agent-handoff.schema.json"
    contract_path.parent.mkdir(parents=True, exist_ok=True)
    contract_path.write_text('{"type": "object"}', encoding="utf-8")

    # Stray unrelated file in repository root
    stray_path = repo_dir / "stray_unrelated_file.md"
    stray_path.write_text("CONFIDENTIAL STRAY UNRELATED CONTENT", encoding="utf-8")

    # 3. Assemble Context Pack via ContextLoader + ContextPackBuilder
    loader = ContextLoader(root=repo_dir)
    builder = ContextPackBuilder(loader=loader)

    metadata = {
        "schemaVersion": "1.0",
        "contextPackId": "CTX-TEST-EDITORIAL-001",
        "jobId": "JOB-E2E-001",
        "agent": "editorial-agent",
        "stage": "editorial",
        "task": {
            "type": "editorial_pass",
            "scope": {
                "bookId": "test-book",
                "pages": [1, 2, 3]
            },
            "parameters": {
                "strictCoverage": True
            }
        },
        "outputContract": "schemas/agent-handoff.schema.json"
    }

    layers = {
        "mandatory": [
            "docs/architecture/constitution.md"
        ],
        "domain": [
            "docs/reference/cataloging-rules.md"
        ],
        "bookContext": [
            "docs/context/books/test-book.md"
        ],
        "jobContext": [
            "coordination/jobs/JOB-E2E-001.json"
        ],
        "handoffContext": [
            "coordination/handoffs/HND-E2E-EXTRACTION-001.md"
        ]
    }

    pack = builder.build(metadata=metadata, layers=layers)

    # Validate Context Pack structure against formal schema
    validate_payload("context-pack.schema.json", pack)

    # 4. Verify minimum sufficient context: paths and loaded contents
    assert pack["mandatory"] == ["docs/architecture/constitution.md"]
    assert pack["domain"] == ["docs/reference/cataloging-rules.md"]
    assert pack["bookContext"] == ["docs/context/books/test-book.md"]
    assert pack["jobContext"] == ["coordination/jobs/JOB-E2E-001.json"]
    assert pack["handoffContext"] == ["coordination/handoffs/HND-E2E-EXTRACTION-001.md"]

    assert "Inviolable rules." in loader.load_text(pack["mandatory"][0])
    assert "Taxonomy definitions." in loader.load_text(pack["domain"][0])
    assert "JOB-E2E-001" in loader.load_text(pack["jobContext"][0])
    assert "150 pages extracted." in loader.load_text(pack["handoffContext"][0])

    # Minimum sufficient context: stray file is strictly excluded from all layers
    all_referenced_paths = [
        p
        for layer_key in ("mandatory", "domain", "bookContext", "jobContext", "handoffContext")
        for p in pack.get(layer_key, [])
    ]
    assert "stray_unrelated_file.md" not in all_referenced_paths


def test_e2e_release_gate_fail_closed(tmp_path: Path):
    """Demonstrate that release stage execution is fail-closed without valid rights evidence."""
    jobs_dir = tmp_path / "jobs"
    job_store = JobStore(root=jobs_dir)
    selector = OrchestratorStateSelector()

    # Create job with all stages through 'qa' passed, 'release' ready
    stage_statuses = {s: "pass" for s in PIPELINE_STAGES}
    stage_statuses["release"] = "ready"

    job = _make_e2e_job_payload(
        job_id="JOB-RELEASE-TEST",
        current_stage="release",
        stage_statuses=stage_statuses
    )
    job_store.create(job)
    loaded_job = job_store.load("JOB-RELEASE-TEST")

    # 1. Missing source manifest -> BLOCKED (fail-closed)
    blocked_selection = selector.select(loaded_job, source_manifest=None)
    assert blocked_selection.action == "BLOCKED"
    assert blocked_selection.code == "SOURCE_MANIFEST_REQUIRED"
    assert blocked_selection.stage == "release"
    assert blocked_selection.agent == "qa-release-agent"

    # 2. Valid source manifest with permitted rights -> ALLOW / RUN_STAGE
    valid_manifest = _make_e2e_source_manifest(
        rights_status="PUBLIC_DOMAIN",
        publication_mode="FULL_TEXT"
    )
    allowed_selection = selector.select(loaded_job, source_manifest=valid_manifest)
    assert allowed_selection.action == "RUN_STAGE"
    assert allowed_selection.code == "ALLOW"
    assert allowed_selection.stage == "release"
    assert allowed_selection.agent == "qa-release-agent"


def test_e2e_human_validation_required_for_done(tmp_path: Path):
    """Demonstrate that status 'approved' or all stages passed cannot bypass human validation (ADR-0002)."""
    jobs_dir = tmp_path / "jobs"
    job_store = JobStore(root=jobs_dir)
    selector = OrchestratorStateSelector()

    all_passed = {s: "pass" for s in PIPELINE_STAGES}
    job = _make_e2e_job_payload(
        job_id="JOB-DONE-TEST",
        status="approved",
        stage_statuses=all_passed,
        current_stage="release"
    )
    job_store.create(job)
    loaded_job = job_store.load("JOB-DONE-TEST")

    # 1. human_validated=False -> HUMAN_REVIEW required
    no_human_selection = selector.select(loaded_job, human_validated=False)
    assert no_human_selection.action == "HUMAN_REVIEW"
    assert no_human_selection.code == "HUMAN_VALIDATION_REQUIRED"

    # 2. human_validated=True -> READY_FOR_DONE
    human_approved_selection = selector.select(loaded_job, human_validated=True)
    assert human_approved_selection.action == "READY_FOR_DONE"
    assert human_approved_selection.code == "ALLOW"


def test_e2e_rejects_operationally_inconsistent_pipeline(tmp_path: Path):
    """Demonstrate that an out-of-order passed stage raises OrchestratorStateError."""
    selector = OrchestratorStateSelector()

    # Inconsistent: source passed, extraction waiting, but editorial passed
    inconsistent_job = _make_e2e_job_payload(
        stage_statuses={
            "source": "pass",
            "extraction": "waiting",
            "editorial": "pass",
        }
    )

    with pytest.raises(OrchestratorStateError) as exc_info:
        selector.select(inconsistent_job)
    assert "editorial" in str(exc_info.value)
    assert "extraction" in str(exc_info.value)


def test_e2e_determinism_and_immutability(tmp_path: Path):
    """Demonstrate that orchestrator selections are 100% deterministic and do not mutate inputs."""
    selector = OrchestratorStateSelector()
    job = _make_e2e_job_payload(stage_statuses={"source": "pass", "extraction": "ready"})
    manifest = _make_e2e_source_manifest()

    job_before = copy.deepcopy(job)
    manifest_before = copy.deepcopy(manifest)

    # 1. Determinism
    s1 = selector.select(job, source_manifest=manifest)
    s2 = selector.select(job, source_manifest=manifest)
    assert s1 == s2
    assert hash(s1) == hash(s2)

    # 2. Immutability
    assert job == job_before
    assert manifest == manifest_before
