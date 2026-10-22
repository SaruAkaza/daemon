from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

import pytest

from scripts.agents.contracts import ContractValidationError
from scripts.ops.command_audit import CommandAuditLog
from scripts.ops.command_processor import CommandProcessor
from scripts.ops.command_store import CommandStore
from scripts.ops.review_store import DecisionValidationError
from scripts.orchestrator.batch_orchestrator import BatchOrchestrator
from scripts.orchestrator.checkpoint_manager import STAGES, StageExecutor, digest
from scripts.orchestrator.retry_policy import FailureClass, StageFailure
from tests.orchestrator.helpers import command, executors, manifest, pump, run, validate


def engine_for(tmp_path, runner=run, concurrency=3):
    return BatchOrchestrator(tmp_path / "runtime", source_root=tmp_path / "sources",
                             executors=executors(runner), concurrency=concurrency)


def test_final_approval_is_hash_bound_and_does_not_authorize_publication(tmp_path):
    source = manifest(tmp_path / "sources", "a")
    with engine_for(tmp_path) as engine:
        engine.register("a", source)
        pump(engine, lambda: engine.state["books"]["a"]["status"] == "READY_FOR_HUMAN_APPROVAL")
        book = engine.state["books"]["a"]
        review = engine.reviews.get_review(book["reviewId"])
        for actor, snapshot in (("gpt-test", review["snapshotSha256"]), ("human-tester", "f" * 64)):
            with pytest.raises(DecisionValidationError):
                engine.reviews.record_decision({"reviewId": review["reviewId"], "decidedBy": actor,
                                                "decision": "APPROVE", "snapshotSha256": snapshot})
        engine.reviews.record_decision({"reviewId": review["reviewId"], "decidedBy": "human-tester",
                                        "decision": "APPROVE", "snapshotSha256": review["snapshotSha256"]})
        engine.tick()
        assert book["status"] == "APPROVED_PRIVATE"
        job = engine.jobs.load(book["jobId"])
        assert job["status"] == "approved" and job["stages"]["release"] == "waiting"
        assert not engine.gates.evaluate_done(job, human_validated=True).allowed
        assert not engine.gates.evaluate_release(job, source_manifest=source).allowed
    with engine_for(tmp_path) as recovered:
        assert recovered.state["books"]["a"]["status"] == "APPROVED_PRIVATE"


def test_five_book_batch_offloads_failures_and_resumes_validated_prefix(tmp_path):
    calls = []

    def runner(context):
        calls.append((context.book_id, context.stage))
        if context.book_id == "b" and context.stage == "editorial":
            raise StageFailure(FailureClass.DOMAIN_AMBIGUITY, "Ambiguous synthetic edition")
        if context.book_id == "c" and context.stage == "extraction":
            raise ValueError("Deterministic format failure")
        return run(context)

    with engine_for(tmp_path, runner) as engine:
        for book_id in "abcde":
            engine.register(book_id, manifest(tmp_path / "sources", book_id))
        pump(engine, lambda: all(b["status"] in ("READY_FOR_HUMAN_APPROVAL", "NEEDS_HUMAN_REVIEW", "BLOCKED")
                                  for b in engine.state["books"].values()))
        assert engine.state["books"]["b"]["status"] == "NEEDS_HUMAN_REVIEW"
        assert engine.state["books"]["c"]["status"] == "BLOCKED"
        assert calls.count(("c", "extraction")) == 1
        assert all(engine.state["books"][b]["status"] == "READY_FOR_HUMAN_APPROVAL" for b in "ade")
        original = [engine.checkpoints.load("e", s) for s in STAGES]
        command(engine, "e", "REPROCESS_STAGE", {"stage": "ENTITIES"}, "correct-e")
        before = copy.deepcopy(engine.state["books"]["e"]["epochs"])
        command(engine, "e", "REPROCESS_STAGE", {"stage": "ENTITIES"}, "correct-e")
        assert engine.state["books"]["e"]["epochs"] == before
        pump(engine, lambda: engine.state["books"]["e"]["status"] == "READY_FOR_HUMAN_APPROVAL")
        assert [engine.checkpoints.load("e", s) for s in STAGES[:3]] == original[:3]
        assert all(engine.checkpoints.load("e", s)["epoch"] == 1 for s in STAGES[3:])
        assert calls.count(("e", "extraction")) == 1
        assert calls.count(("e", "entities")) == 2
    before_calls = list(calls)
    with engine_for(tmp_path, runner) as recovered:
        recovered.tick()
        assert calls == before_calls
        assert recovered.state["books"]["d"]["status"] == "READY_FOR_HUMAN_APPROVAL"


def test_pause_boundary_late_reprocess_and_actual_concurrency_cap(tmp_path):
    release = threading.Event()
    started = threading.Event()
    active = 0
    peak = 0
    lock = threading.Lock()

    def runner(context):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
            if active == 3:
                started.set()
        try:
            assert release.wait(10)
            return run(context)
        finally:
            with lock:
                active -= 1

    with engine_for(tmp_path, runner) as engine:
        for book_id in "abcde":
            engine.register(book_id, manifest(tmp_path / "sources", book_id))
        pump(engine, started.is_set)
        command(engine, "a", "PAUSE_BOOK")
        command(engine, "b", "REPROCESS_STAGE", {"stage": "EXTRACTION"})
        for _ in range(3):
            engine.tick()
        assert len(engine._active) == 3 and active == 3
        assert engine.checkpoints.load("a", "extraction") is None
        release.set()
        pump(engine, lambda: engine.state["books"]["a"]["status"] == "PAUSED")
        assert engine.checkpoints.load("a", "extraction")["status"] == "PASSED"
        assert engine.checkpoints.load("a", "editorial") is None
        command(engine, "a", "RESUME_BOOK")
        pump(engine, lambda: all(b["status"] == "READY_FOR_HUMAN_APPROVAL" for b in engine.state["books"].values()))
        assert peak == 3
        assert engine.checkpoints.load("b", "extraction")["epoch"] == 1


@pytest.mark.parametrize("category", list(FailureClass))
def test_retry_taxonomy_and_durable_deadlines(tmp_path, category, monkeypatch):
    attempts = []

    def runner(context):
        attempts.append(context.attempt)
        raise StageFailure(category, "Injected failure")

    monkeypatch.setattr("scripts.orchestrator.batch_orchestrator.time.time", lambda: 100.0)
    with engine_for(tmp_path, runner) as engine:
        engine.register("a", manifest(tmp_path / "sources", "a"))
        pump(engine, lambda: engine.state["books"]["a"]["status"] not in ("QUEUED", "RUNNING"))
        if category != FailureClass.TRANSIENT_TECHNICAL:
            assert attempts == [1]
            for _ in range(3):
                engine.tick()
            assert attempts == [1]
            return
        assert engine.state["books"]["a"]["retryAt"] == 102.0
    with engine_for(tmp_path, runner) as engine:
        engine.tick()
        assert attempts == [1]
        monkeypatch.setattr("scripts.orchestrator.batch_orchestrator.time.time", lambda: 102.0)
        pump(engine, lambda: engine.state["books"]["a"]["retryAt"] == 110.0)
        monkeypatch.setattr("scripts.orchestrator.batch_orchestrator.time.time", lambda: 110.0)
        pump(engine, lambda: engine.state["books"]["a"]["status"] == "BLOCKED")
        assert attempts == [1, 2, 3]


@pytest.mark.parametrize("damage", ["artifact", "checkpoint", "contract", "source"])
def test_recovery_rejects_stale_artifacts_contracts_and_originals(tmp_path, damage):
    source = manifest(tmp_path / "sources", "a")
    with engine_for(tmp_path) as engine:
        engine.register("a", source)
        pump(engine, lambda: engine.state["books"]["a"]["status"] == "READY_FOR_HUMAN_APPROVAL")
        cp = engine.checkpoints.load("a", "entities")
        source_cp = engine.checkpoints.load("a", "source")
        if damage == "artifact":
            (engine.root / next(iter(cp["artifactRefs"]))).write_text("{}")
        elif damage == "checkpoint":
            engine.checkpoints.path("a", "entities").write_text("{")
        elif damage == "source":
            (tmp_path / "sources/a.docx").write_bytes(b"changed source")
    adapters = executors()
    if damage == "contract":
        adapters["entities"] = StageExecutor("test-2", ("entity",), run, validate)
    with BatchOrchestrator(tmp_path / "runtime", source_root=tmp_path / "sources", executors=adapters) as engine:
        book = engine.state["books"]["a"]
        if damage == "source":
            engine.tick()
            assert book["status"] == "BLOCKED" and book["epochs"]["source"] == 1
        else:
            assert book["status"] == "QUEUED" and book["epochs"]["entities"] == 1
            assert engine.checkpoints.load("a", "source") == source_cp
            assert book["epochs"]["editorial"] == 0
            pump(engine, lambda: book["status"] == "READY_FOR_HUMAN_APPROVAL")


def test_real_process_kill_discards_only_interrupted_stage(tmp_path):
    source = manifest(tmp_path / "sources", "d")
    child = r'''
import json, sys, time
from pathlib import Path
from scripts.orchestrator.batch_orchestrator import BatchOrchestrator
from tests.orchestrator.helpers import executors, run
root = Path(sys.argv[1])
def runner(context):
    if context.stage == "editorial":
        (root / "entered-editorial").write_text("ready")
        time.sleep(120)
    return run(context)
engine = BatchOrchestrator(root / "runtime", source_root=root / "sources", executors=executors(runner))
engine.register("d", json.loads(sys.argv[2]))
engine.start()
while True:
    time.sleep(0.02)
'''
    process = subprocess.Popen([sys.executable, "-c", child, str(tmp_path), json.dumps(source)],
                               cwd=Path(__file__).resolve().parents[2])
    try:
        deadline = time.monotonic() + 15
        while not (tmp_path / "entered-editorial").exists() and time.monotonic() < deadline:
            assert process.poll() is None
            time.sleep(0.02)
        assert (tmp_path / "entered-editorial").exists()
    finally:
        process.kill()
        process.wait(timeout=5)
    calls = []

    def runner(context):
        calls.append(context.stage)
        return run(context)

    with engine_for(tmp_path, runner) as recovered:
        assert recovered.state["books"]["d"]["status"] == "QUEUED"
        pump(recovered, lambda: recovered.state["books"]["d"]["status"] == "READY_FOR_HUMAN_APPROVAL")
        assert calls == ["editorial", "entities", "relations", "frontend", "qa"]
        assert recovered.checkpoints.load("d", "editorial")["attempt"] == 2


def test_single_owner_and_corrupt_state_fail_closed(tmp_path):
    with engine_for(tmp_path):
        with pytest.raises(RuntimeError, match="owns"):
            engine_for(tmp_path)
    (tmp_path / "runtime/batch/state.json").write_text("{}")
    with pytest.raises(ValueError, match="corrupt"):
        engine_for(tmp_path)


@pytest.mark.parametrize("fault", ["invalid_schema", "missing_artifact", "escape", "bad_gate", "provenance"])
def test_no_checkpoint_before_artifact_and_independent_gate_validation(tmp_path, fault):
    def runner(context):
        outputs = run(context)
        if fault == "invalid_schema":
            (context.workspace / "result.json").write_text('{"name": "invalid"}')
        elif fault == "missing_artifact":
            (context.workspace / "result.json").unlink()
        elif fault == "escape":
            return {"../outside.json": "entity"}
        elif fault == "provenance":
            data = json.loads((context.workspace / "result.json").read_text())
            data["source"] = "other-book"
            (context.workspace / "result.json").write_text(json.dumps(data))
        return outputs

    adapters = executors(runner)
    if fault == "bad_gate":
        adapters["extraction"] = StageExecutor("test-1", ("entity",), run, lambda c, p: False)
    with BatchOrchestrator(tmp_path / "runtime", source_root=tmp_path / "sources", executors=adapters) as engine:
        engine.register("a", manifest(tmp_path / "sources", "a"))
        pump(engine, lambda: engine.state["books"]["a"]["status"] == "BLOCKED")
        assert engine.checkpoints.load("a", "source") is not None
        assert engine.checkpoints.load("a", "extraction") is None


def test_ops_commands_apply_and_replay_once_with_durable_review_snapshot(tmp_path):
    with engine_for(tmp_path) as engine:
        engine.register("a", manifest(tmp_path / "sources", "a"))
        stores = tmp_path / "runtime/ops/stores"
        processor = CommandProcessor(CommandStore(stores), CommandAuditLog(stores),
                                     engine.reviews, orchestrator=engine)
        cmd = {"commandId": "CMD-pause-booka", "commandType": "PAUSE_BOOK",
               "bookId": "a", "operatorId": "human-tester", "payload": {},
               "reason": "Synthetic control", "confirmation": {"confirmed": True}}
        processor.submit_command(cmd)
        processor.process_pending_commands()
        assert engine.state["books"]["a"]["status"] == "PAUSED"
        assert processor.get_command_status("CMD-pause-booka")["status"] == "SUCCEEDED"
        processor.submit_command(cmd)
        assert processor.process_pending_commands() == 0
        command(engine, "a", "RESUME_BOOK")
        pump(engine, lambda: engine.state["books"]["a"]["status"] == "READY_FOR_HUMAN_APPROVAL")
        review = engine.reviews.get_review(engine.state["books"]["a"]["reviewId"])
        processor.submit_command({**cmd, "commandId": "CMD-approve-booka", "commandType": "APPROVE_REVIEW",
                                  "reviewId": review["reviewId"], "payload": {"snapshotSha256": review["snapshotSha256"]}})
        processor.process_pending_commands()
        engine.tick()
        assert engine.state["books"]["a"]["status"] == "APPROVED_PRIVATE"


def test_dequeue_finishes_boundary_without_starting_next_stage(tmp_path):
    release = threading.Event()

    def runner(context):
        assert release.wait(10)
        return run(context)

    with engine_for(tmp_path, runner) as engine:
        engine.register("a", manifest(tmp_path / "sources", "a"))
        pump(engine, lambda: engine.state["books"]["a"]["attempts"]["extraction"] == 1)
        command(engine, "a", "DEQUEUE_BOOK")
        release.set()
        pump(engine, lambda: engine.state["books"]["a"]["status"] == "REGISTERED")
        assert engine.checkpoints.load("a", "extraction") is not None
        assert engine.checkpoints.load("a", "editorial") is None
        assert not engine.snapshot()["activeBooks"]


def test_stale_human_review_cannot_approve_reprocessed_book(tmp_path):
    with engine_for(tmp_path) as engine:
        engine.register("a", manifest(tmp_path / "sources", "a"))
        pump(engine, lambda: engine.state["books"]["a"]["status"] == "READY_FOR_HUMAN_APPROVAL")
        old_id = engine.state["books"]["a"]["reviewId"]
        command(engine, "a", "REPROCESS_STAGE", {"stage": "QA"})
        assert engine.reviews.get_review(old_id)["status"] == "SUPERSEDED"
        with pytest.raises(ValueError, match="obsolete"):
            engine.validate_review(old_id)
        with pytest.raises(RuntimeError):
            engine.reviews.record_decision({"reviewId": old_id, "decidedBy": "human-tester", "decision": "APPROVE"})
        pump(engine, lambda: engine.state["books"]["a"]["status"] == "READY_FOR_HUMAN_APPROVAL")
        assert engine.state["books"]["a"]["reviewId"] != old_id


def test_missing_manifest_suspension_and_private_runtime_boundaries(tmp_path):
    with engine_for(tmp_path) as engine:
        engine.register("no-source")
        engine.register("suspended", manifest(tmp_path / "sources", "suspended"), metadata={"suspended": True})
        engine.tick()
        assert engine.state["books"]["no-source"]["status"] == "REGISTERED"
        assert engine.state["books"]["suspended"]["status"] == "INELIGIBLE"
        assert engine.snapshot()["activeBooks"] == []
        bad = manifest(tmp_path / "sources", "bad")
        bad["path"] = "../sources/bad.docx"
        with pytest.raises(ValueError, match="contained"):
            engine.register("bad", bad)
    target = tmp_path / "outside"
    target.mkdir()
    (tmp_path / "runtime/batch").rename(tmp_path / "old-batch")
    (tmp_path / "runtime/batch").symlink_to(target, target_is_directory=True)
    with pytest.raises(ValueError):
        engine_for(tmp_path)
    assert list(target.iterdir()) == []


def test_public_server_cannot_attach_batch_engine(tmp_path):
    from scripts.agents.preview_server import PreviewServer
    with engine_for(tmp_path) as engine:
        with pytest.raises(ValueError, match="restricted_preview"):
            PreviewServer(tmp_path / "preview", mode="public", runtime_dir=engine.runtime_dir,
                          orchestrator=engine)


def test_preview_uses_exact_batch_runtime_when_ancestor_has_another_runtime(tmp_path):
    from scripts.agents.preview_server import PreviewServer
    existing = tmp_path / ".daemon_runtime/ops"
    existing.mkdir(parents=True)
    token = existing / "ops_token"
    token.write_text("sentinel-existing-runtime")
    with engine_for(tmp_path) as engine:
        server = PreviewServer(tmp_path / "preview", port=0, runtime_dir=engine.runtime_dir, orchestrator=engine)
        try:
            server.start()
            assert server.token_manager.ops_dir == engine.runtime_dir / "ops"
            assert server.command_store.stores_dir == engine.reviews.stores_dir
            assert server.review_store is engine.reviews
        finally:
            server.stop()
    assert token.read_text() == "sentinel-existing-runtime"
