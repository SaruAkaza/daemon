"""Five synthetic DOCXs and deterministic adapters; no real catalog content."""
from __future__ import annotations

import json
from pathlib import Path

from docx import Document

from scripts.orchestrator.checkpoint_manager import STAGES, StageContext, StageExecutor, file_hash
from scripts.orchestrator.retry_policy import FailureClass, StageFailure


def create_sources(runtime: Path) -> list[dict]:
    source_dir = runtime / "demo-inputs"
    source_dir.mkdir(parents=True, exist_ok=True)
    registrations = []
    for letter in "abcde":
        path = source_dir / f"book-{letter}.docx"
        if not path.exists():
            document = Document()
            document.add_paragraph(f"Documento sintético {letter.upper()} — somente demonstração.")
            document.save(path)
        registrations.append({"bookId": f"demo-{letter}", "manifest": {
            "schemaVersion": "1.0", "sourceId": f"demo-{letter}",
            "title": f"Demonstração {letter.upper()}", "path": str(path.relative_to(runtime)),
            "extension": ".docx", "sha256": file_hash(path), "rightsStatus": "UNKNOWN",
            "visibility": "private", "publicationMode": "NOT_PUBLIC"}})
    return registrations


def run(context: StageContext) -> dict[str, str]:
    if context.book_id == "demo-b" and context.stage == "editorial":
        raise StageFailure(FailureClass.DOMAIN_AMBIGUITY, "Dúvida editorial sintética; exige correção humana")
    if context.book_id == "demo-c" and context.stage == "extraction":
        raise StageFailure(FailureClass.DETERMINISTIC_TECHNICAL, "Falha determinística sintética")
    if context.book_id == "demo-d" and context.stage == "extraction" and context.attempt == 1:
        raise StageFailure(FailureClass.TRANSIENT_TECHNICAL, "Indisponibilidade transitória sintética")
    payload = {"id": context.book_id, "name": context.manifest["title"], "category": "source",
               "source": context.manifest["sourceId"], "page": 1,
               "entries": ["Artefato sintético do motor de filas; não representa catalogação real."]}
    (context.workspace / "result.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return {"result.json": "entity"}


def validate(context: StageContext, payloads: dict) -> None:
    if len(payloads) != 1:
        raise ValueError("Demo requires exactly one artifact")
    for payload in payloads.values():
        if (payload["source"] != context.manifest["sourceId"] or payload.get("page") != 1
                or not payload["entries"] or not payload["entries"][0].startswith("Artefato sintético")):
            raise ValueError("Demo provenance gate failed")


def build_executors() -> dict[str, StageExecutor]:
    return {stage: StageExecutor("demo-1.0.0", ("entity",), run, validate) for stage in STAGES[1:]}
