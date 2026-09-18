from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import threading
from typing import Any

from scripts.agents.contracts import validate_payload
from scripts.ops.command_audit import CommandAuditLog
from scripts.ops.command_store import CommandStore, CommandConflictError
from scripts.ops.review_store import ReviewStore

MEDIUM_RISK_COMMANDS = {
    "REPROCESS_STAGE",
    "REJECT_REVIEW",
    "REQUEST_CORRECTION",
    "DEQUEUE_BOOK",
}


class RiskValidationError(ValueError):
    """Raised when an operational command fails server-side risk validation rules."""
    pass


class CommandProcessor:
    """Asynchronous command processor enforcing server-side risk model and auditability."""

    def __init__(
        self,
        command_store: CommandStore | None = None,
        audit_log: CommandAuditLog | None = None,
        review_store: ReviewStore | None = None,
    ) -> None:
        self.command_store = command_store if command_store is not None else CommandStore()
        self.audit_log = audit_log if audit_log is not None else CommandAuditLog()
        self.review_store = review_store
        self._lock = threading.RLock()

    def _validate_risk(self, cmd_payload: dict[str, Any]) -> None:
        cmd_type = cmd_payload.get("commandType", "")
        reason = str(cmd_payload.get("reason") or "").strip()
        confirmation = cmd_payload.get("confirmation") or {}
        if not isinstance(confirmation, dict):
            raise RiskValidationError("Confirmation must be an object with boolean 'confirmed'")

        confirmed = confirmation.get("confirmed", False)

        # 1. Check for HIGH-risk: Any review decision on POLICY_OR_RIGHTS
        if cmd_type in ("APPROVE_REVIEW", "REJECT_REVIEW", "REQUEST_CORRECTION"):
            review_id = cmd_payload.get("reviewId") or cmd_payload.get("payload", {}).get("reviewId")
            target_review = None
            if self.review_store and review_id:
                target_review = self.review_store.get_review(review_id)

            category = (target_review.get("category") if target_review else None) or cmd_payload.get("payload", {}).get("category")
            if category == "POLICY_OR_RIGHTS":
                if not reason:
                    raise RiskValidationError("Non-empty reason required for high-risk operation")
                if not confirmed:
                    raise RiskValidationError("Confirmation required for high-risk operation")
                typed_conf = str(confirmation.get("typedConfirmation") or "").strip()
                expected_target = (target_review.get("bookId") if target_review else None) or cmd_payload.get("bookId") or ""
                if not typed_conf or typed_conf != expected_target:
                    raise RiskValidationError(
                        f"typedConfirmation '{typed_conf}' must match bookId '{expected_target}' for high-risk operation"
                    )
                return

        # 2. Check for MEDIUM-risk
        if cmd_type in MEDIUM_RISK_COMMANDS:
            if not reason:
                raise RiskValidationError(f"Non-empty reason required for medium-risk command '{cmd_type}'")
            if not confirmed:
                raise RiskValidationError(f"Confirmation required for medium-risk command '{cmd_type}'")
            return

        # 3. LOW-risk operations
        if not confirmed:
            raise RiskValidationError(f"Confirmation required for command '{cmd_type}'")

    def submit_command(self, cmd_payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
        """Validate against schema & risk model, persist intent idempotently.
        
        Returns:
            (record, 202) on initial acceptance
            (record, 200) on idempotent duplicate submission
        """
        # 1. Strict schema validation
        validate_payload("ops-command.schema.json", cmd_payload)

        # 2. Server-side risk validation
        self._validate_risk(cmd_payload)

        # 3. Durable idempotent persistence
        record, is_dup = self.command_store.save_command_intent(cmd_payload)
        if is_dup:
            return record, 200

        # 4. Audit logging of newly accepted command
        self.audit_log.append(
            "COMMAND_ACCEPTED",
            {
                "commandId": record["commandId"],
                "commandType": record["commandType"],
                "operatorId": record["operatorId"],
                "bookId": record.get("bookId"),
                "reviewId": record.get("reviewId"),
            },
        )
        return record, 202

    def process_pending_commands(self) -> int:
        """Worker execution loop processing all pending ACCEPTED commands."""
        with self._lock:
            all_cmds = self.command_store.list_commands()
            pending = [c for c in all_cmds if c.get("status") == "ACCEPTED"]
            processed_count = 0

            for cmd in pending:
                cid = cmd["commandId"]
                cmd_type = cmd.get("commandType")
                self.command_store.update_command_status(cid, "RUNNING")

                try:
                    result_data = self._execute_command(cmd)
                    self.command_store.update_command_status(cid, "SUCCEEDED", result=result_data)
                    self.audit_log.append(
                        "COMMAND_SUCCEEDED",
                        {
                            "commandId": cid,
                            "commandType": cmd_type,
                            "operatorId": cmd.get("operatorId"),
                            "result": result_data,
                        },
                    )
                    processed_count += 1
                except Exception as e:
                    self.command_store.update_command_status(cid, "FAILED", error=str(e))
                    self.audit_log.append(
                        "COMMAND_FAILED",
                        {
                            "commandId": cid,
                            "commandType": cmd_type,
                            "operatorId": cmd.get("operatorId"),
                            "error": str(e),
                        },
                    )
                    processed_count += 1

            return processed_count

    def _execute_command(self, cmd: dict[str, Any]) -> dict[str, Any]:
        cmd_type = cmd.get("commandType")
        book_id = cmd.get("bookId")
        payload = cmd.get("payload") or {}

        if cmd_type == "PAUSE_BOOK":
            if not book_id:
                raise ValueError("PAUSE_BOOK requires bookId")
            paused = list(self.command_store.get_control_state().get("pausedBooks", []))
            if book_id not in paused:
                paused.append(book_id)
                self.command_store.set_control_override("pausedBooks", paused)
            return {"bookId": book_id, "action": "paused"}

        elif cmd_type == "RESUME_BOOK":
            if not book_id:
                raise ValueError("RESUME_BOOK requires bookId")
            paused = list(self.command_store.get_control_state().get("pausedBooks", []))
            if book_id in paused:
                paused.remove(book_id)
                self.command_store.set_control_override("pausedBooks", paused)
            return {"bookId": book_id, "action": "resumed"}

        elif cmd_type == "PRIORITIZE_BOOK":
            if not book_id:
                raise ValueError("PRIORITIZE_BOOK requires bookId")
            overrides = dict(self.command_store.get_control_state().get("priorityOverrides", {}))
            weight = payload.get("priorityWeight", 100)
            overrides[book_id] = weight
            self.command_store.set_control_override("priorityOverrides", overrides)
            return {"bookId": book_id, "priorityWeight": weight}

        elif cmd_type == "REPROCESS_STAGE":
            if not book_id:
                raise ValueError("REPROCESS_STAGE requires bookId")
            stage = payload.get("stage")
            reprocesses = dict(self.command_store.get_control_state().get("reprocessIntents", {}))
            reprocesses[book_id] = {
                "stage": stage,
                "requestedAt": datetime.now(timezone.utc).isoformat(),
            }
            self.command_store.set_control_override("reprocessIntents", reprocesses)
            return {"bookId": book_id, "stage": stage}

        elif cmd_type == "DEQUEUE_BOOK":
            if not book_id:
                raise ValueError("DEQUEUE_BOOK requires bookId")
            paused = list(self.command_store.get_control_state().get("pausedBooks", []))
            if book_id in paused:
                paused.remove(book_id)
                self.command_store.set_control_override("pausedBooks", paused)
            overrides = dict(self.command_store.get_control_state().get("priorityOverrides", {}))
            if book_id in overrides:
                del overrides[book_id]
                self.command_store.set_control_override("priorityOverrides", overrides)
            return {"bookId": book_id, "action": "dequeued"}

        elif cmd_type in ("APPROVE_REVIEW", "REJECT_REVIEW", "REQUEST_CORRECTION"):
            if not self.review_store:
                raise RuntimeError("ReviewStore is required to process review commands")
            rev_id = cmd.get("reviewId") or payload.get("reviewId")
            if not rev_id:
                raise ValueError(f"{cmd_type} requires reviewId")

            action = (
                "APPROVE"
                if cmd_type == "APPROVE_REVIEW"
                else ("REJECT" if cmd_type == "REJECT_REVIEW" else "REQUEST_CORRECTION")
            )
            dec_payload = {
                "reviewId": rev_id,
                "decidedBy": cmd.get("operatorId"),
                "decision": action,
                "justification": cmd.get("reason", ""),
            }
            dec_record = self.review_store.record_decision(dec_payload)
            return {"reviewId": rev_id, "decision": action, "decisionId": dec_record.get("decisionId")}

        else:
            raise ValueError(f"Unsupported command type '{cmd_type}'")

    def get_command_status(self, command_id: str) -> dict[str, Any] | None:
        """Retrieve current status of a command."""
        return self.command_store.get_command(command_id)
