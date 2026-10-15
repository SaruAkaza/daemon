"""Real extraction and editorial evidence; semantic stages require certified adapters."""
from __future__ import annotations

import hashlib
import json

import fitz

from scripts.agents.application_runtime import ResourceBounds
from scripts.agents.canonical_json import canonical_json_bytes
from scripts.agents.contracts import validate_payload, write_atomic
from scripts.orchestrator.checkpoint_manager import StageContext, StageExecutor, contained_file, digest
from scripts.orchestrator.retry_policy import FailureClass, StageFailure
from scripts.orchestrator.source_extraction import NORMALIZATION_VERSION, extract_source, text_hash

VERSION = f"real-evidence-1.0.0/{NORMALIZATION_VERSION}/pymupdf-{fitz.VersionBind}"


def _envelope(context: StageContext, metadata: dict, issue_codes: list[str], evidence: list[dict]) -> dict:
    request = digest({"bookId": context.book_id, "manifest": context.manifest, "stage": context.stage,
                      "workspace": str(context.workspace.resolve()),
                      "predecessorOutputs": [cp["outputHash"] for cp in context.predecessors]})
    return {"schemaVersion": "2.0", "executionId": f"EXEC-{request}-{context.attempt}",
            "requestId": f"REQ-{request}", "agent": f"{context.stage}-agent", "stage": context.stage,
            "status": "VALIDATION_FAILED" if issue_codes else "SUCCESS", "proposedArtifacts": {},
            "evidence": evidence, "uncertainties": [{"type": code, "description": code} for code in issue_codes],
            "metadata": {"adapterVersion": VERSION, "bookId": context.book_id,
                         "sourceId": context.manifest["sourceId"], "sourceSha256": context.manifest["sha256"].lower(),
                         **metadata}}


def _extraction(context: StageContext) -> dict:
    audit = extract_source(context.source_path, context.manifest)
    evidence = [{"book": context.manifest["sourceId"], "page": block["page"], "section": block["anchor"]}
                for block in audit["blocks"] if block["page"] is not None]
    return _envelope(context, {"extraction": audit}, audit["issueCodes"], evidence)


def _predecessor(context: StageContext, stage: str) -> dict:
    if context.artifact_root is None:
        raise ValueError("Artifact root is required to read validated predecessors")
    matches = [cp for cp in context.predecessors if cp["stage"] == stage]
    if len(matches) != 1 or len(matches[0]["artifactRefs"]) != 1:
        raise ValueError("Missing or ambiguous predecessor artifact")
    relative, ref = next(iter(matches[0]["artifactRefs"].items()))
    if ref["schema"] != "execution-result":
        raise ValueError("Wrong predecessor contract")
    raw = contained_file(context.artifact_root, relative).read_bytes()
    if hashlib.sha256(raw).hexdigest() != ref["sha256"]:
        raise ValueError("Predecessor artifact hash mismatch")
    result = json.loads(raw)
    validate_payload("execution-result", result)
    if (result["stage"] != stage or result["status"] != "SUCCESS"
            or result["metadata"]["bookId"] != context.book_id
            or result["metadata"]["sourceSha256"] != context.manifest["sha256"].lower()):
        raise ValueError("Predecessor is not a certified result for this source")
    return result


def _editorial(context: StageContext) -> dict:
    extracted = _predecessor(context, "extraction")["metadata"]["extraction"]
    destinations = [{"anchor": block["anchor"], "source": context.manifest["sourceId"],
                     "page": block["page"], "cleanTextSha256": text_hash(block["cleanText"]),
                     "destination": "PENDING_CLASSIFICATION" if block["cleanText"].strip() else "BLANK_PAGE"}
                    for block in extracted["blocks"]]
    pending = sum(block["destination"] == "PENDING_CLASSIFICATION" for block in destinations)
    audit = {"version": 1, "pageBasis": extracted["pageBasis"], "pageCount": extracted["pageCount"],
             "blocks": destinations, "pendingClassificationCount": pending}
    issues = ["EDITORIAL_CLASSIFICATION_REQUIRED"] if pending else []
    return _envelope(context, {"editorial": audit}, issues,
                     [{"book": context.manifest["sourceId"], "page": block["page"], "section": block["anchor"]}
                      for block in destinations if block["page"] is not None])


def _produce(context: StageContext) -> dict[str, str]:
    result = _extraction(context) if context.stage == "extraction" else _editorial(context)
    raw = canonical_json_bytes(result)
    if len(raw) > ResourceBounds().max_file_size_bytes:
        raise ValueError("Extraction result resource limit exceeded")
    write_atomic(context.workspace / "execution-result.json", raw)
    return {"execution-result.json": "execution-result"}


def _validate(context: StageContext, payloads: dict) -> None:
    if len(payloads) != 1:
        raise ValueError("A stage must produce exactly one execution result")
    actual = next(iter(payloads.values()))
    expected = _extraction(context) if context.stage == "extraction" else _editorial(context)
    if actual != expected:
        raise ValueError("Extraction/editorial evidence differs from the original source or contract")
    issues = [uncertainty["type"] for uncertainty in expected["uncertainties"]]
    if issues:
        raise StageFailure(FailureClass.DOMAIN_AMBIGUITY,
                           "Revisão necessária: " + ", ".join(issues))


def _unconfigured(context: StageContext) -> dict[str, str]:
    raise StageFailure(FailureClass.DETERMINISTIC_TECHNICAL,
                       f"Executor real de {context.stage} ainda não certificado; não avançar automaticamente")


def build_executors() -> dict[str, StageExecutor]:
    result = {stage: StageExecutor(VERSION, ("execution-result",), _produce, _validate)
              for stage in ("extraction", "editorial")}
    for stage in ("entities", "relations", "frontend", "qa"):
        result[stage] = StageExecutor("unconfigured-1.0.0", ("execution-result",), _unconfigured, _validate)
    return result
