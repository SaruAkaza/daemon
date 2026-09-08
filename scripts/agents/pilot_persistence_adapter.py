from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts.agents.application_coordinator import ApplicationCoordinator
from scripts.agents.application_policy import ApplicationPolicy
from scripts.agents.application_result import ApplicationResult
from scripts.agents.application_runtime import ApplicationRuntimeConfig
from scripts.agents.change_set import ChangeSetBuilder
from scripts.agents.change_set_applier import ChangeSetApplier
from scripts.agents.content_validator import ContentValidator
from scripts.agents.contracts import validate_payload
from scripts.agents.execution_validator import ExecutionValidationVerdict
from scripts.agents.patch_applier import PatchApplier
from scripts.agents.precondition_validator import PreconditionValidator
from scripts.agents.staging_manager import StagingManager


class PilotPersistenceAdapter:
    """Adapts pilot candidate artifacts to V2.1 ApplicationCoordinator targeting RestrictedPilotWorkspace."""

    def apply_pilot_artifacts(
        self,
        workspace_root: Path,
        staging_root: Path,
        proposed_artifacts: list[dict[str, Any]],
        review_decision: dict[str, Any],
    ) -> ApplicationResult:
        """Invokes V2.1 ApplicationCoordinator to persist pilot artifacts safely into workspace_root."""
        req_id = review_decision.get("requestId", "unknown")
        if review_decision.get("decision") != "APPROVE":
            res = ApplicationResult(
                change_set_id="cs-blocked-unapproved",
                request_id=req_id,
                status="BLOCKED",
                applied_operations=(),
                blocked_operations=(),
                failure_code="ERR_REVIEW_REQUIRED",
                reasons=(f"Review decision is not APPROVE: {review_decision.get('decision')}",),
                applied_at=None,
                duration_ms=0.0,
                journal=None,
                metadata={},
            )
            validate_payload("application-result.schema.json", res.to_dict())
            return res

        workspace_root = Path(workspace_root).resolve()
        staging_root = Path(staging_root).resolve()
        audit_root = staging_root.parent / "audit" / "pilot"

        config = ApplicationRuntimeConfig.create(
            repository_root=workspace_root,
            staging_root=staging_root,
            audit_root=audit_root,
        )

        allowed_scope = [art["path"] for art in proposed_artifacts]
        artifacts_dict = {art["path"]: art.get("content", "") for art in proposed_artifacts}

        request = {
            "schemaVersion": "2.0",
            "requestId": req_id,
            "jobId": "JOB-PILOT-001",
            "bookId": "animalidade",
            "targetStage": "extraction",
            "assignedAgent": "extraction-agent",
            "allowedWriteScope": allowed_scope,
            "executionProfile": "manual-antigravity",
            "contextPack": {
                "schemaVersion": "1.0",
                "contextPackId": f"CTX-{req_id}",
                "jobId": "JOB-PILOT-001",
                "agent": "extraction-agent",
                "stage": "extraction",
                "mandatory": ["docs/architecture/constitution.md"],
                "domain": ["docs/context/domain/taxonomy.md"],
                "bookContext": ["coordination/books/animalidade.md"],
                "jobContext": ["coordination/queue/codex.json"],
                "handoffContext": [],
                "task": {
                    "type": "persist_pilot_artifacts",
                    "sourceType": "docx",
                    "sourcePath": "Livros/word/feito/animalidade.docx",
                },
                "outputContract": "schemas/raw-text-block.schema.json",
            },
            "taskInstruction": "Persist pilot artifacts via V2.1",
            "outputSchemaName": "raw-text-block.schema.json",
        }

        result = {
            "schemaVersion": "2.0",
            "executionId": f"EXEC-{req_id}-01",
            "requestId": req_id,
            "agent": "extraction-agent",
            "stage": "extraction",
            "status": "SUCCESS",
            "proposedArtifacts": artifacts_dict,
            "evidence": [{"book": "animalidade", "page": 1}],
            "uncertainties": [],
        }

        verdict = ExecutionValidationVerdict(
            verdict="ACCEPT",
            code="VALID_OK",
            reasons=(),
            details={},
        )

        builder = ChangeSetBuilder(repository_root=workspace_root)
        policy = ApplicationPolicy(config=config)
        content_validator = ContentValidator(config.resource_bounds)
        precondition_validator = PreconditionValidator(config, policy, content_validator)
        patch_applier = PatchApplier()
        staging_manager = StagingManager(config)
        applier = ChangeSetApplier(
            config=config,
            precondition_validator=precondition_validator,
            patch_applier=patch_applier,
            staging_manager=staging_manager,
        )
        coordinator = ApplicationCoordinator(
            config=config,
            builder=builder,
            policy=policy,
            applier=applier,
        )

        return coordinator.coordinate_application(request, result, verdict)
