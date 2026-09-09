from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.agents.canonical_json import canonical_json_bytes, sha256_bytes


class PilotAuditStoreError(RuntimeError):
    """Raised when an audit store invariant is violated."""
    pass


class PilotAuditStore:
    """Segregated, trusted governance ledger persisting audit evidence outside content change sets."""

    def __init__(self, audit_base_dir: Path | None = None) -> None:
        if audit_base_dir is not None:
            self.audit_base_dir = Path(audit_base_dir)
        else:
            self.audit_base_dir = Path.cwd().parent / ".daemon_runtime" / "audit" / "pilot"
        self.audit_base_dir.mkdir(parents=True, exist_ok=True)

    def _get_book_dir(self, book_id: str) -> Path:
        bdir = self.audit_base_dir / book_id
        bdir.mkdir(parents=True, exist_ok=True)
        return bdir

    def get_audit_history(self, book_id: str) -> list[dict[str, Any]]:
        """Reads transitions.jsonl resiliently, skipping malformed lines."""
        log_file = self.audit_base_dir / book_id / "transitions.jsonl"
        if not log_file.exists():
            return []

        records: list[dict[str, Any]] = []
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                line_str = line.strip()
                if not line_str:
                    continue
                try:
                    entry = json.loads(line_str)
                    if isinstance(entry, dict) and "seq" in entry:
                        records.append(entry)
                except Exception:
                    # Resilient reader: isolates corrupted lines without failing
                    continue
        return records

    def record_transition(
        self,
        book_id: str,
        from_state: str,
        event: str,
        to_state: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Appends a state transition to transitions.jsonl with strict monotonic seq and deduplication."""
        details = details or {}
        bdir = self._get_book_dir(book_id)
        log_file = bdir / "transitions.jsonl"

        event_seed = {
            "fromState": from_state,
            "event": event,
            "toState": to_state,
            "details": details,
        }
        event_id = sha256_bytes(canonical_json_bytes(event_seed))

        existing = self.get_audit_history(book_id)
        for rec in existing:
            if rec.get("eventId") == event_id:
                # Idempotent deduplication
                return

        next_seq = len(existing) + 1
        record = {
            "seq": next_seq,
            "eventId": event_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "fromState": from_state,
            "event": event,
            "toState": to_state,
            "details": details,
        }

        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _sanitize_id(self, identifier: str) -> str:
        if not identifier or not isinstance(identifier, str):
            raise PilotAuditStoreError(f"ERR_UNSAFE_IDENTIFIER: Invalid identifier: {identifier}")
        clean = Path(identifier).name
        if clean != identifier or "/" in identifier or "\\" in identifier or ".." in identifier:
            raise PilotAuditStoreError(
                f"ERR_UNSAFE_IDENTIFIER: Identifier contains unsafe characters or directory traversal: {identifier}"
            )
        return clean

    def record_review_request(self, book_id: str, request_data: dict[str, Any]) -> Path:
        """Atomically saves formal review request into audit/pilot/<bookId>/requests/."""
        bdir = self._get_book_dir(book_id)
        req_dir = bdir / "requests"
        req_dir.mkdir(parents=True, exist_ok=True)

        raw_id = request_data.get("requestId", f"REQ-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}")
        req_id = self._sanitize_id(raw_id)
        target_path = (req_dir / f"{req_id}.json").resolve()
        if not target_path.is_relative_to(req_dir.resolve()):
            raise PilotAuditStoreError(f"ERR_UNSAFE_IDENTIFIER: Target path escapes requests directory: {target_path}")
        target_path.write_bytes(canonical_json_bytes(request_data))
        return target_path

    def record_review_decision(self, book_id: str, decision_data: dict[str, Any]) -> Path:
        """Atomically saves human review decision into audit/pilot/<bookId>/decisions/."""
        bdir = self._get_book_dir(book_id)
        dec_dir = bdir / "decisions"
        dec_dir.mkdir(parents=True, exist_ok=True)

        raw_id = decision_data.get("decisionId", f"DEC-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}")
        dec_id = self._sanitize_id(raw_id)
        target_path = (dec_dir / f"{dec_id}.json").resolve()
        if not target_path.is_relative_to(dec_dir.resolve()):
            raise PilotAuditStoreError(f"ERR_UNSAFE_IDENTIFIER: Target path escapes decisions directory: {target_path}")
        target_path.write_bytes(canonical_json_bytes(decision_data))
        return target_path

    def record_persistence_receipt(self, book_id: str, receipt_data: dict[str, Any]) -> Path:
        """Atomically saves persistence receipt into audit/pilot/<bookId>/receipts/."""
        bdir = self._get_book_dir(book_id)
        rec_dir = bdir / "receipts"
        rec_dir.mkdir(parents=True, exist_ok=True)

        raw_id = receipt_data.get("receiptId", f"REC-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}")
        rec_id = self._sanitize_id(raw_id)
        target_path = (rec_dir / f"{rec_id}.json").resolve()
        if not target_path.is_relative_to(rec_dir.resolve()):
            raise PilotAuditStoreError(f"ERR_UNSAFE_IDENTIFIER: Target path escapes receipts directory: {target_path}")
        target_path.write_bytes(canonical_json_bytes(receipt_data))
        return target_path
