from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
import copy
from datetime import datetime, timezone
import fcntl
import json
from pathlib import Path
import threading
import time
from typing import Any
import uuid

from scripts.agents.canonical_json import canonical_json_bytes
from scripts.agents.contracts import validate_payload, write_atomic
from scripts.agents.gate_engine import GateEngine, PIPELINE_STAGES
from scripts.agents.job_store import JobStore
from scripts.ops.review_store import ReviewStore, validate_human_operator
from scripts.orchestrator.checkpoint_manager import (
    CheckpointManager, STAGES, StageContext, StageExecutor, contained_file, digest, file_hash,
)
from scripts.orchestrator.dag_invalidator import affected_stages
from scripts.orchestrator.priority_scheduler import PriorityScheduler
from scripts.orchestrator.retry_policy import FailureClass, StageFailure, retry_delay
from scripts.orchestrator.wave_governor import validate_concurrency


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _source_run(context: StageContext) -> dict[str, str]:
    write_atomic(context.workspace / "manifest.json", canonical_json_bytes(context.manifest))
    return {"manifest.json": "source-manifest"}


def _source_validate(context: StageContext, payloads: dict[str, Any]) -> None:
    if list(payloads.values()) != [context.manifest]:
        raise ValueError("Source artifact must preserve the registered manifest")
    if file_hash(context.source_path) != context.manifest["sha256"].lower():
        raise ValueError("Original source differs from its registered SHA-256")


class BatchOrchestrator:
    """Single owner of a private runtime, with bounded concurrent stage workers.

    No built-in semantic extractor and no public publisher. Integrators must
    supply versioned executors and independent gates for extraction through QA.
    Final technical approval is APPROVED_PRIVATE; canonical release stays waiting.
    """

    def __init__(self, runtime_dir: Path | str, *, source_root: Path | str,
                 executors: dict[str, StageExecutor], concurrency: int = 3,
                 evidence_review_id: str | None = None) -> None:
        self.runtime_dir = Path(runtime_dir).resolve()
        project_root = Path(__file__).resolve().parents[2]
        if self.runtime_dir == project_root or project_root in self.runtime_dir.parents:
            raise ValueError("Batch runtime must be outside the repository")
        for relative in ("batch", "jobs", "ops/stores"):
            (self.runtime_dir / relative).resolve().relative_to(self.runtime_dir)
        self.root = (self.runtime_dir / "batch").resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._lease = (self.root / "owner.lock").open("a+b")
        try:
            fcntl.flock(self._lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self._lease.close()
            raise RuntimeError("Another batch engine owns this runtime") from None
        self._closed = False
        self._lock = threading.RLock()
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None
        self._running = False
        self.fatal_error: str | None = None
        self.broadcaster: Any | None = None
        self._last_snapshot_hash: str | None = None
        self._active: dict[str, tuple[Future, dict[str, Any]]] = {}
        try:
            self.source_root = Path(source_root).resolve()
            self.executors = dict(executors)
            if set(self.executors) != set(STAGES[1:]):
                raise ValueError("Explicit executors required for extraction through QA")
            self.executors["source"] = StageExecutor(
                "1.0.0", ("source-manifest",), _source_run, _source_validate)
            for executor in self.executors.values():
                executor.fingerprint()
            self.reviews = ReviewStore(self.runtime_dir / "ops/stores")
            validate_concurrency(concurrency, self.reviews, evidence_review_id)
            self.concurrency = concurrency
            self.scheduler = PriorityScheduler()
            self.checkpoints = CheckpointManager(self.root)
            self.jobs = JobStore(self.runtime_dir / "jobs")
            self.gates = GateEngine()
            self.state_path = self.root / "state.json"
            self.state = (json.loads(self.state_path.read_text(encoding="utf-8"))
                          if self.state_path.exists() else
                          {"version": 1, "books": {}, "commands": {}})
            self._validate_state()
            self._pool = ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix="DaemonBatch")
            self._recover()
            self._save()
        except Exception:
            if hasattr(self, "_pool"):
                self._pool.shutdown(wait=True)
            self._lease.close()
            self._closed = True
            raise

    def _validate_state(self) -> None:
        if (self.state.get("version") != 1 or not isinstance(self.state.get("books"), dict)
                or not isinstance(self.state.get("commands"), dict)):
            raise ValueError("Unsupported or corrupt batch state")
        valid_statuses = {"REGISTERED", "INELIGIBLE", "QUEUED", "RUNNING", "RETRY_WAIT",
                          "PAUSED", "BLOCKED", "NEEDS_HUMAN_REVIEW",
                          "READY_FOR_HUMAN_APPROVAL", "APPROVED_PRIVATE"}
        for key, book in self.state["books"].items():
            if book["bookId"] != key or book["status"] not in valid_statuses:
                raise ValueError("Corrupt book identity or status")
            if set(book["epochs"]) != set(STAGES) or set(book["attempts"]) != set(STAGES):
                raise ValueError("Corrupt stage counters")
            if any(type(v) is not int or v < 0 for v in
                   (*book["epochs"].values(), *book["attempts"].values())):
                raise ValueError("Invalid stage counters")
            self.jobs.load(book["jobId"])
            if book["manifest"]:
                validate_payload("source-manifest", book["manifest"])

    def _save(self) -> None:
        write_atomic(self.state_path, canonical_json_bytes(self.state))

    def _source_path(self, book: dict[str, Any]) -> Path:
        manifest = book["manifest"]
        validate_payload("source-manifest", manifest)
        path = contained_file(self.source_root, manifest["path"])
        if path.suffix.lower() != manifest["extension"]:
            raise ValueError("Source extension differs from the manifest")
        if file_hash(path) != manifest["sha256"].lower():
            raise ValueError("Source hash differs from the manifest; register a reviewed revision")
        return path

    def _context(self, book: dict[str, Any], stage: str, workspace: Path,
                 prefix: list[dict[str, Any]], attempt: int) -> StageContext:
        return StageContext(book["bookId"], stage, copy.deepcopy(book["manifest"]),
                            self._source_path(book), workspace, tuple(copy.deepcopy(prefix)), attempt)

    def _input_hash(self, book: dict[str, Any], prefix: list[dict[str, Any]]) -> str:
        return digest({"manifest": book["manifest"],
                       "predecessor": prefix[-1]["outputHash"] if prefix else None})

    def _invalidate(self, book: dict[str, Any], stage: str, reason: str) -> None:
        for affected in affected_stages(stage):
            book["epochs"][affected] += 1
            book["attempts"][affected] = 0
        book.update(status="QUEUED", retryAt=0, reviewId=None, failure=None,
                    invalidatedAt=now(), invalidationReason=reason)
        self._save()  # Epochs fence off both durable checkpoints and late worker results.

    def _prefix(self, book: dict[str, Any]) -> list[dict[str, Any]]:
        prefix: list[dict[str, Any]] = []
        for stage in STAGES:
            try:
                cp = self.checkpoints.load(book["bookId"], stage)
            except (ValueError, UnicodeError):
                self.checkpoints.quarantine(book["bookId"], stage)
                self._invalidate(book, stage, "Malformed checkpoint quarantined")
                break
            try:
                if not cp or cp.get("epoch") != book["epochs"][stage]:
                    break
                workspace = (self.root / cp["workspace"]).resolve()
                workspace.relative_to(self.root)
                context = self._context(book, stage, workspace, prefix, cp["attempt"])
                self.checkpoints.verify(cp, book_id=book["bookId"], stage=stage,
                                        epoch=book["epochs"][stage],
                                        input_hash=self._input_hash(book, prefix),
                                        executor=self.executors[stage], context=context)
            except Exception as exc:
                self._invalidate(book, stage, f"Checkpoint rejected: {exc}")
                break
            prefix.append(cp)
        return prefix

    def _sync_job(self, book: dict[str, Any], prefix: list[dict[str, Any]]) -> None:
        job = self.jobs.load(book["jobId"])
        for stage in PIPELINE_STAGES:
            job["stages"][stage] = "pass" if stage in STAGES[:len(prefix)] else "waiting"
        stage = STAGES[len(prefix)] if len(prefix) < len(STAGES) else "release"
        book["currentStage"] = stage
        book["completedStages"] = len(prefix)
        job["currentStage"] = stage
        status = book["status"]
        job["humanReviewRequired"] = status in ("NEEDS_HUMAN_REVIEW", "READY_FOR_HUMAN_APPROVAL")
        job["blockingReasons"] = [book["failure"]] if book.get("failure") else []
        job["artifacts"] = [str(self.root / path) for cp in prefix for path in cp["artifactRefs"]]
        job["status"] = {"BLOCKED": "blocked", "NEEDS_HUMAN_REVIEW": "needs_review",
                         "READY_FOR_HUMAN_APPROVAL": "needs_review", "APPROVED_PRIVATE": "approved",
                         "RUNNING": "in_progress"}.get(status, "todo")
        if status == "RUNNING":
            job["stages"][stage] = "running"
        elif status == "BLOCKED":
            job["stages"][stage] = "blocked"
        elif job["humanReviewRequired"]:
            job["stages"][stage] = "human_review"
        job["updatedAt"] = now()
        self.jobs.update(job)

    def register(self, book_id: str, manifest: dict[str, Any] | None = None,
                 *, metadata: dict[str, Any] | None = None, requested_by: str = "batch") -> None:
        with self._lock:
            self._ensure_open()
            if not isinstance(book_id, str) or not book_id.strip() or book_id in self.state["books"]:
                raise ValueError("Book identifier must be nonempty and unique")
            metadata = copy.deepcopy(metadata or {})
            status = "INELIGIBLE" if metadata.get("suspended") else ("QUEUED" if manifest else "REGISTERED")
            book = {"bookId": book_id, "jobId": f"BATCH-{digest(book_id)[:24]}",
                    "manifest": copy.deepcopy(manifest), "metadata": metadata, "status": status,
                    "epochs": dict.fromkeys(STAGES, 0), "attempts": dict.fromkeys(STAGES, 0),
                    "priorityWeight": 100, "retryAt": 0, "paused": False, "dequeued": False,
                    "reviewId": None, "failure": None, "registeredAt": now()}
            if manifest:
                self._source_path(book)
            self.scheduler.score(book)
            stamp = now()
            job = {"schemaVersion": "1.0", "jobId": book["jobId"], "kind": "book_ingestion",
                   "bookId": book_id, "status": "todo", "createdAt": stamp, "updatedAt": stamp,
                   "requestedBy": requested_by, "currentStage": "source",
                   "stages": dict.fromkeys(PIPELINE_STAGES, "waiting"), "humanReviewRequired": False,
                   "blockingReasons": [], "artifacts": [],
                   "history": [{"timestamp": stamp, "event": "batch_registered"}]}
            # An interrupted registration may leave this harmless job; reuse only its own ID.
            if book["jobId"] in self.jobs.list_job_ids():
                existing = self.jobs.load(book["jobId"])
                if existing["bookId"] != book_id:
                    raise ValueError("Job identifier collision")
            else:
                self.jobs.create(job)
            self.state["books"][book_id] = book
            self._save()
            self._wake.set()

    def update_manifest(self, book_id: str, manifest: dict[str, Any]) -> None:
        """Explicit source revision; never infer a replacement from an altered file."""
        with self._lock:
            book = self.state["books"][book_id]
            candidate = {**book, "manifest": copy.deepcopy(manifest)}
            self._source_path(candidate)
            book["manifest"] = candidate["manifest"]
            self._invalidate(book, "source", "Explicit source manifest revision")
            self._sync_job(book, [])

    def _review(self, book: dict[str, Any], stage: str, kind: str,
                prefix: list[dict[str, Any]], category: str, message: str) -> None:
        snapshot = digest({"bookId": book["bookId"], "manifest": book["manifest"],
                           "epochs": book["epochs"], "checkpoints": prefix, "kind": kind})
        review_id = f"BATCH-{snapshot}"
        if not self.reviews.get_review(review_id):
            self.reviews.create_review({"reviewId": review_id, "bookId": book["bookId"],
                                        "stage": stage, "category": category, "reviewKind": kind,
                                        "snapshotSha256": snapshot, "summary": message, "problem": message,
                                        "evidence": {"snapshotSha256": snapshot,
                                                     "checkpoints": [{k: cp[k] for k in
                                                        ("stage", "inputHash", "outputHash", "contractHash", "artifactRefs")}
                                                                     for cp in prefix]},
                                        "artifactRefs": [p for cp in prefix for p in cp["artifactRefs"]]})
        book["reviewId"] = review_id

    def _complete(self, book: dict[str, Any], prefix: list[dict[str, Any]]) -> None:
        if book["status"] != "APPROVED_PRIVATE":
            book["status"] = "READY_FOR_HUMAN_APPROVAL"
            self._review(book, "qa", "BATCH_FINAL", prefix, "TECHNICAL",
                         "Validar resultados privados das sete etapas. A publicação exige outro gate.")

    def _recover(self) -> None:
        for book in self.state["books"].values():
            if not book["manifest"]:
                continue
            prefix = self._prefix(book)
            if book["status"] == "APPROVED_PRIVATE":
                # Re-establish approval from the immutable human log, not the mutable state flag.
                book["status"] = "READY_FOR_HUMAN_APPROVAL"
            if book["status"] == "RUNNING":
                # Incomplete work never becomes a checkpoint. The attempt budget survives crashes.
                book["status"] = "QUEUED"
            if book["dequeued"]:
                book["status"] = "REGISTERED"
            elif book["paused"] and book["status"] in ("QUEUED", "RETRY_WAIT"):
                book["status"] = "PAUSED"
            if len(prefix) == len(STAGES) and book["status"] in (
                "RUNNING", "QUEUED", "READY_FOR_HUMAN_APPROVAL", "APPROVED_PRIVATE"
            ):
                self._complete(book, prefix)
            elif len(prefix) < len(STAGES) and book["status"] in ("APPROVED_PRIVATE", "READY_FOR_HUMAN_APPROVAL"):
                book["status"] = "QUEUED"
            self._sync_job(book, prefix)
        self._decisions()
        self._retire_obsolete_reviews()

    def _retire_obsolete_reviews(self) -> None:
        for review in self.reviews.list_reviews(status="PENDING"):
            if review.get("reviewKind") not in ("BATCH_FINAL", "BATCH_CORRECTION"):
                continue
            book = self.state["books"].get(review.get("bookId"))
            if book and review["reviewId"] != book["reviewId"]:
                self.reviews.supersede_review(review["reviewId"], "Batch inputs or requested stage changed")

    def validate_review(self, review_id: str) -> None:
        with self._lock:
            review = self.reviews.get_review(review_id) or {}
            if review.get("reviewKind") not in ("BATCH_FINAL", "BATCH_CORRECTION"):
                return
            book = self.state["books"].get(review.get("bookId"))
            if not book or book["reviewId"] != review_id:
                raise ValueError("This batch review is obsolete")
            prefix = self._prefix(book)
            if book["reviewId"] != review_id:
                self._sync_job(book, prefix)
                raise ValueError("Review artifacts changed; reprocessing required")
            if review.get("reviewKind") == "BATCH_FINAL" and len(prefix) != len(STAGES):
                raise ValueError("Final review requires all seven validated checkpoints")

    def apply_command(self, command: dict[str, Any]) -> dict[str, Any]:
        """Called only by the existing authenticated/risk-validated Ops processor."""
        with self._lock:
            self._ensure_open()
            cid = command["commandId"]
            command_hash = digest({k: command.get(k) for k in
                                   ("commandType", "bookId", "payload", "operatorId", "reason")})
            existing = self.state["commands"].get(cid)
            if existing:
                if existing["hash"] != command_hash:
                    raise ValueError("Batch command identifier conflict")
                return copy.deepcopy(existing["result"])
            book = self.state["books"][command["bookId"]]
            kind = command["commandType"]
            payload = command.get("payload") or {}
            if kind == "PAUSE_BOOK":
                book["paused"] = True
                if book["bookId"] not in self._active and book["status"] in ("QUEUED", "RETRY_WAIT"):
                    book["status"] = "PAUSED"
            elif kind == "RESUME_BOOK":
                book["paused"] = False
                if book["status"] == "PAUSED":
                    book["status"] = "RETRY_WAIT" if book["retryAt"] > time.time() else "QUEUED"
            elif kind == "PRIORITIZE_BOOK":
                weight = payload["priorityWeight"]
                if type(weight) is not int or not 1 <= weight <= 200:
                    raise ValueError("Priority weight must be 1..200")
                book["priorityWeight"] = weight
            elif kind == "DEQUEUE_BOOK":
                book.update(dequeued=True, paused=False)
                if book["bookId"] not in self._active:
                    book["status"] = "REGISTERED"
            elif kind == "REPROCESS_STAGE":
                stage = str(payload["stage"]).lower()
                # Epoch changes and command receipt are committed together for replay safety.
                for affected in affected_stages(stage):
                    book["epochs"][affected] += 1
                    book["attempts"][affected] = 0
                book.update(status="QUEUED", retryAt=0, reviewId=None, failure=None,
                            dequeued=False, invalidatedAt=now(), invalidationReason=command.get("reason"))
            else:
                raise ValueError(f"Unsupported batch command: {kind}")
            result = {"bookId": book["bookId"], "action": kind, "status": book["status"],
                      "boundaryPending": book["bookId"] in self._active}
            self.state["commands"][cid] = {"hash": command_hash, "result": result}
            self._save()
            self._retire_obsolete_reviews()
            self._wake.set()
            return copy.deepcopy(result)

    def _execute(self, context: StageContext, executor: StageExecutor) -> dict[str, Any]:
        outputs = executor.run(context)
        refs = {}
        for relative, schema in outputs.items():
            path = contained_file(context.workspace, relative)
            refs[str(path.relative_to(self.root))] = {"schema": schema, "sha256": file_hash(path)}
        payloads = self.checkpoints.artifacts(refs, executor)
        if executor.validate(context, payloads) is not None:
            raise ValueError("Gate must raise on rejection and return None on acceptance")
        return refs

    def _failure(self, book: dict[str, Any], task: dict[str, Any], exc: Exception,
                 prefix: list[dict[str, Any]]) -> None:
        category = exc.category if isinstance(exc, StageFailure) else FailureClass.DETERMINISTIC_TECHNICAL
        book["failure"] = str(exc)
        book["failureClass"] = category.value
        delay = retry_delay(category, task["attempt"])
        if delay is not None:
            book.update(status="RETRY_WAIT", retryAt=time.time() + delay)
        elif category in (FailureClass.DOMAIN_AMBIGUITY, FailureClass.POLICY_OR_RIGHTS):
            book["status"] = "NEEDS_HUMAN_REVIEW"
            self._review(book, task["stage"], "BATCH_CORRECTION", prefix, category.value, str(exc))
        else:
            book["status"] = "BLOCKED"

    def _collect(self) -> None:
        for book_id, (future, task) in list(self._active.items()):
            if not future.done():
                continue
            del self._active[book_id]
            book = self.state["books"][book_id]
            if task["epoch"] != book["epochs"][task["stage"]]:
                continue  # A late result from reprocessing cannot revalidate obsolete work.
            prefix = self._prefix(book)
            if task["epoch"] != book["epochs"][task["stage"]]:
                continue
            try:
                refs = future.result()
                executor = self.executors[task["stage"]]
                if (self._input_hash(book, prefix) != task["inputHash"]
                        or executor.fingerprint() != task["contractHash"]):
                    self._invalidate(book, task["stage"], "Inputs changed during execution")
                    continue
                cp = {**task, "artifactRefs": refs, "outputHash": digest(refs),
                      "status": "PASSED", "completedAt": now()}
                context = self._context(book, task["stage"], self.root / task["workspace"], prefix, task["attempt"])
                self.checkpoints.verify(cp, book_id=book_id, stage=task["stage"], epoch=task["epoch"],
                                        input_hash=task["inputHash"], executor=executor, context=context)
                self.checkpoints.commit(cp)  # Recovery can discover this before state/job updates.
                prefix.append(cp)
                book.update(status="QUEUED", retryAt=0, failure=None)
                if len(prefix) == len(STAGES):
                    self._complete(book, prefix)
            except Exception as exc:
                self._failure(book, task, exc, prefix)
            if book["dequeued"]:
                book["status"] = "REGISTERED"
            elif book["paused"] and book["status"] in ("QUEUED", "RETRY_WAIT"):
                book["status"] = "PAUSED"
            self._sync_job(book, prefix)

    def _decisions(self) -> None:
        decisions = {d["reviewId"]: d for d in self.reviews.decision_logger.read_all_entries()}
        for book in self.state["books"].values():
            if book["status"] != "READY_FOR_HUMAN_APPROVAL":
                continue
            decision = decisions.get(book["reviewId"])
            if not decision:
                continue
            validate_human_operator(decision.get("decidedBy"))
            prefix = self._prefix(book)
            if len(prefix) != len(STAGES):
                self._sync_job(book, prefix)
                continue
            review = self.reviews.get_review(book["reviewId"]) or {}
            snapshot = digest({"bookId": book["bookId"], "manifest": book["manifest"],
                               "epochs": book["epochs"], "checkpoints": prefix, "kind": "BATCH_FINAL"})
            if (decision.get("snapshotSha256") != snapshot or review.get("snapshotSha256") != snapshot
                    or decision.get("bookId") != book["bookId"] or decision.get("reviewKind") != "BATCH_FINAL"):
                raise ValueError("Human decision does not match the current batch snapshot")
            book["status"] = "APPROVED_PRIVATE" if decision["decision"] == "APPROVE" else "BLOCKED"
            if book["status"] == "BLOCKED":
                book["failure"] = f"Human decision: {decision['decision']}"
            self._sync_job(book, prefix)

    def tick(self) -> None:
        with self._lock:
            self._ensure_open()
            self._collect()
            self._decisions()
            self._retire_obsolete_reviews()
            eligible = [b for b in self.state["books"].values() if b["manifest"]
                        and not b["paused"] and not b["dequeued"] and not b["metadata"].get("suspended")
                        and b["status"] in ("QUEUED", "RETRY_WAIT")
                        and b["retryAt"] <= time.time() and b["bookId"] not in self._active]
            for book in self.scheduler.rank(eligible):
                if len(self._active) >= self.concurrency:
                    break
                prefix = self._prefix(book)
                if len(prefix) == len(STAGES):
                    self._complete(book, prefix)
                    self._sync_job(book, prefix)
                    continue
                stage = STAGES[len(prefix)]
                executor = self.executors[stage]
                attempt = book["attempts"][stage] + 1
                if attempt > 3:
                    book.update(status="BLOCKED", failure="Interrupted attempt budget exhausted; explicit reprocessing required")
                    self._sync_job(book, prefix)
                    continue
                workspace = self.root / "attempts" / digest(book["bookId"]) / stage / uuid.uuid4().hex
                workspace.mkdir(parents=True)
                try:
                    context = self._context(book, stage, workspace, prefix, attempt)
                    self._sync_job(book, prefix)
                    gate = self.gates.evaluate_stage_entry(self.jobs.load(book["jobId"]), stage)
                    if not gate.allowed:
                        raise ValueError(gate.code)
                except Exception as exc:
                    book.update(status="BLOCKED", failure=str(exc))
                    self._sync_job(book, prefix)
                    continue
                book["attempts"][stage] = attempt
                book["status"] = "RUNNING"
                task = {"bookId": book["bookId"], "stage": stage, "epoch": book["epochs"][stage],
                        "inputHash": self._input_hash(book, prefix), "contractHash": executor.fingerprint(),
                        "attempt": attempt, "workspace": str(workspace.relative_to(self.root)), "startedAt": now()}
                self._save()  # Attempt receipt is durable before the worker starts.
                future = self._pool.submit(self._execute, context, executor)
                self._active[book["bookId"]] = (future, task)
                self._sync_job(book, prefix)
            self._save()

    def _publish_snapshot(self) -> None:
        if self.broadcaster:
            snapshot = self.snapshot()
            snapshot_hash = digest(snapshot)
            if snapshot_hash != self._last_snapshot_hash:
                self.broadcaster.publish_event("batch_updated", snapshot)
                self._last_snapshot_hash = snapshot_hash

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {"concurrency": self.concurrency, "activeBooks": sorted(self._active),
                    "schedulerVersion": self.scheduler.config["version"], "fatalError": self.fatal_error,
                    "books": [{"bookId": b["bookId"], "title": (b["manifest"] or {}).get("title", b["bookId"]),
                               "pipelineStatus": b["status"], "priorityWeight": b["priorityWeight"],
                               "score": self.scheduler.score(b), "reviewId": b["reviewId"],
                               "currentStage": b.get("currentStage", "source"),
                               "completedStages": b.get("completedStages", 0),
                               "failure": b.get("failure"), "retryAt": b["retryAt"],
                               "paused": b["paused"], "dequeued": b["dequeued"]}
                              for b in self.scheduler.rank(list(self.state["books"].values()))]}

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("Batch engine is closed")
        if self.fatal_error:
            raise RuntimeError(f"Batch engine stopped: {self.fatal_error}")

    def start(self) -> None:
        with self._lock:
            self._ensure_open()
            if self._thread and self._thread.is_alive():
                return
            self._running = True
            self._thread = threading.Thread(target=self._loop, daemon=True, name="DaemonBatchControl")
            self._thread.start()

    def _loop(self) -> None:
        while self._running:
            try:
                self.tick()
                self._publish_snapshot()
            except Exception as exc:
                self.fatal_error = str(exc)
                self._running = False  # A corrupt store is visible and fails closed.
                self._publish_snapshot()
                break
            self._wake.wait(0.1)
            self._wake.clear()

    def close(self) -> None:
        if self._closed:
            return
        self._running = False
        self._wake.set()
        if self._thread:
            self._thread.join()
        self._pool.shutdown(wait=True)
        with self._lock:
            try:
                self._collect()
                self._save()
            finally:
                self._closed = True
                self._lease.close()

    def __enter__(self) -> BatchOrchestrator:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
