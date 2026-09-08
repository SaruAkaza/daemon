from __future__ import annotations

import json
import re
from typing import Any

from scripts.agents.contracts import ContractValidationError, validate_payload
from scripts.agents.execution_adapter import RawExecutionResponse


class RepairExhaustedError(RuntimeError):
    """Raised when raw response cannot be repaired structurally."""
    pass


class StructuralRepairEngine:
    """Deterministic, non-semantic mechanical parser and repair engine for raw execution responses."""

    def __init__(self) -> None:
        pass

    def parse_and_repair(
        self,
        raw_response: RawExecutionResponse,
        request: dict[str, Any],
    ) -> dict[str, Any]:
        """Deterministically parses raw text to ExecutionResult, applying at most 1 mechanical structural repair.

        Zero provider calls, zero semantic hallucination/invention.
        """
        req_id = request.get("requestId", "UNKNOWN_REQUEST")
        agent = request.get("assignedAgent", "unknown-agent")
        stage = request.get("targetStage", "unknown-stage")
        duration = getattr(raw_response, "duration_seconds", 0.0)

        # 1. Handle non-OK status codes directly
        if raw_response.status_code == "TIMEOUT":
            result_payload = {
                "schemaVersion": "2.0",
                "executionId": f"EXEC-{req_id}-TIMEOUT",
                "requestId": req_id,
                "agent": agent,
                "stage": stage,
                "status": "TIMEOUT",
                "proposedArtifacts": {},
                "evidence": [],
                "uncertainties": [
                    {
                        "type": "TIMEOUT",
                        "description": f"Execution timed out after {duration:.2f}s.",
                    }
                ],
                "rawResponse": raw_response.content,
                "metadata": {"durationSeconds": duration},
            }
            validate_payload("execution-result.schema.json", result_payload)
            return result_payload

        if raw_response.status_code == "ERROR":
            result_payload = {
                "schemaVersion": "2.0",
                "executionId": f"EXEC-{req_id}-ERROR",
                "requestId": req_id,
                "agent": agent,
                "stage": stage,
                "status": "ERROR",
                "proposedArtifacts": {},
                "evidence": [],
                "uncertainties": [
                    {
                        "type": "PROVIDER_ERROR",
                        "description": f"Provider error during execution: {raw_response.content}",
                    }
                ],
                "rawResponse": raw_response.content,
                "metadata": {"durationSeconds": duration},
            }
            validate_payload("execution-result.schema.json", result_payload)
            return result_payload

        # 2. Status is OK: parse JSON with 1 mechanical repair attempt
        content = raw_response.content.strip()
        parsed: dict[str, Any] | None = None

        # Attempt 0: direct JSON parse
        try:
            val = json.loads(content)
            if isinstance(val, dict):
                parsed = val
        except Exception:
            pass

        # Attempt 1: deterministic mechanical cleanup (strip markdown fences, isolate JSON object)
        if parsed is None:
            cleaned = content

            # Remove markdown code block delimiters (```json ... ``` or ``` ... ```)
            if "```" in cleaned:
                match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
                if match:
                    cleaned = match.group(1).strip()

            # If still not starting with '{' and ending with '}', extract outermost JSON object
            if not (cleaned.startswith("{") and cleaned.endswith("}")):
                first_brace = cleaned.find("{")
                last_brace = cleaned.rfind("}")
                if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                    cleaned = cleaned[first_brace : last_brace + 1].strip()

            try:
                val = json.loads(cleaned)
                if isinstance(val, dict):
                    parsed = val
            except Exception:
                parsed = None

        # If still failed, mechanical repair is exhausted
        if parsed is None:
            result_payload = {
                "schemaVersion": "2.0",
                "executionId": f"EXEC-{req_id}-REPAIR-FAILED",
                "requestId": req_id,
                "agent": agent,
                "stage": stage,
                "status": "REPAIR_FAILED",
                "proposedArtifacts": {},
                "evidence": [],
                "uncertainties": [
                    {
                        "type": "JSON_PARSE_FAILURE",
                        "description": "Failed to extract valid JSON payload from model response.",
                    }
                ],
                "rawResponse": raw_response.content,
                "metadata": {"durationSeconds": duration},
            }
            validate_payload("execution-result.schema.json", result_payload)
            return result_payload

        # 3. Assemble and normalize into standard ExecutionResult
        execution_id = parsed.get("executionId") or f"EXEC-{req_id}-01"
        status = parsed.get("status")
        if status not in ["SUCCESS", "VALIDATION_FAILED", "REPAIR_FAILED", "TIMEOUT", "ERROR"]:
            status = "SUCCESS"

        proposed_artifacts = parsed.get("proposedArtifacts")
        if not isinstance(proposed_artifacts, dict):
            proposed_artifacts = {}

        evidence = parsed.get("evidence")
        if not isinstance(evidence, list):
            evidence = []

        uncertainties = parsed.get("uncertainties")
        if not isinstance(uncertainties, list):
            uncertainties = []

        result_payload = {
            "schemaVersion": "2.0",
            "executionId": str(execution_id),
            "requestId": req_id,
            "agent": agent,
            "stage": stage,
            "status": status,
            "proposedArtifacts": proposed_artifacts,
            "evidence": evidence,
            "uncertainties": uncertainties,
            "rawResponse": raw_response.content,
            "metadata": {"durationSeconds": duration},
        }

        # Validate against schema
        try:
            validate_payload("execution-result.schema.json", result_payload)
        except ContractValidationError as e:
            result_payload["status"] = "VALIDATION_FAILED"
            result_payload["uncertainties"].append({
                "type": "SCHEMA_VALIDATION_ERROR",
                "description": str(e),
            })
            validate_payload("execution-result.schema.json", result_payload)

        return result_payload
