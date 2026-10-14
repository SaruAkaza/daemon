from __future__ import annotations

import hashlib
import json
from pathlib import Path
import time

from scripts.orchestrator.batch_orchestrator import BatchOrchestrator
from scripts.orchestrator.checkpoint_manager import STAGES, StageContext, StageExecutor


def manifest(root: Path, book_id: str) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{book_id}.docx"
    path.write_bytes(f"synthetic source {book_id}".encode())
    return {"schemaVersion": "1.0", "sourceId": book_id, "title": book_id,
            "path": path.name, "extension": ".docx", "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "rightsStatus": "UNKNOWN", "visibility": "private", "publicationMode": "NOT_PUBLIC"}


def run(context: StageContext) -> dict:
    artifact = {"id": context.book_id.lower(), "name": context.book_id, "category": "source",
                "source": context.manifest["sourceId"], "entries": ["Synthetic test artifact"], "page": 1}
    (context.workspace / "result.json").write_text(json.dumps(artifact), encoding="utf-8")
    return {"result.json": "entity"}


def validate(context: StageContext, payloads: dict) -> None:
    if len(payloads) != 1:
        raise ValueError("Wrong artifact count")
    for payload in payloads.values():
        if payload["source"] != context.manifest["sourceId"] or payload.get("page") != 1:
            raise ValueError("Synthetic provenance gate rejected the artifact")


def executors(runner=run, version="test-1") -> dict:
    return {stage: StageExecutor(version, ("entity",), runner, validate) for stage in STAGES[1:]}


def pump(engine: BatchOrchestrator, predicate, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        engine.tick()
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError(f"Engine did not reach expected state: {engine.snapshot()}")


def command(engine, book_id, kind, payload=None, command_id=None):
    return engine.apply_command({"commandId": command_id or f"{book_id}-{kind}-{time.time_ns()}",
                                 "commandType": kind, "bookId": book_id, "payload": payload or {},
                                 "operatorId": "human-tester", "reason": "Synthetic correction"})
