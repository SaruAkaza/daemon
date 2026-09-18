from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import threading
from typing import Any

from scripts.agents.canonical_json import canonical_json_bytes
from scripts.agents.contracts import write_atomic
from scripts.agents.pilot_review import AUTOMATED_AGENT_IDENTIFIERS
from scripts.ops.hash_chain import HashChainLogger
from scripts.ops.runtime_locator import get_ops_stores_dir

VALID_CATEGORIES = {"DOMAIN_AMBIGUITY", "POLICY_OR_RIGHTS", "TECHNICAL"}
VALID_DECISION_ACTIONS = {"APPROVE", "REJECT", "REQUEST_CORRECTION"}


class DecisionValidationError(ValueError):
    """Raised when review decision validation fails."""
    pass


class ReviewConflictError(RuntimeError):
    """Raised when a review has already been resolved or has concurrent conflict."""
    pass


class ReviewStore:
    """Durable CRUD store for Human Review Queue and tamper-evident decision log."""

    def __init__(self, stores_dir: Path | str | None = None) -> None:
        self.stores_dir = Path(stores_dir).resolve() if stores_dir else get_ops_stores_dir()
        self.stores_dir.mkdir(parents=True, exist_ok=True)
        self.reviews_file = self.stores_dir / "reviews.json"
        self.decisions_file = self.stores_dir / "decisions.jsonl"
        self.decision_logger = HashChainLogger(self.decisions_file)
        self._lock = threading.RLock()
        self._ensure_files()
        self._reconcile_with_decision_log()

    def _ensure_files(self) -> None:
        if not self.reviews_file.exists():
            write_atomic(self.reviews_file, canonical_json_bytes({"reviews": []}))

    def _load_reviews(self) -> list[dict[str, Any]]:
        if not self.reviews_file.exists():
            return []
        with open(self.reviews_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("reviews", [])

    def _save_reviews(self, reviews: list[dict[str, Any]]) -> None:
        write_atomic(self.reviews_file, canonical_json_bytes({"reviews": reviews}))

    def _reconcile_with_decision_log(self) -> None:
        """Reconciles reviews.json snapshot against immutable decision log."""
        with self._lock:
            decisions = self.decision_logger.read_all_entries()
            if not decisions:
                return
            reviews = self._load_reviews()
            dirty = False
            for dec in decisions:
                rev_id = dec.get("reviewId")
                matched = False
                for r in reviews:
                    if r["reviewId"] == rev_id:
                        matched = True
                        if r.get("status") != "RESOLVED" or r.get("decisionId") != dec.get("decisionId"):
                            r["status"] = "RESOLVED"
                            r["decisionId"] = dec.get("decisionId")
                            r["resolutionAction"] = dec.get("decision")
                            r["decidedBy"] = dec.get("decidedBy")
                            r["resolvedAt"] = dec.get("timestamp")
                            dirty = True
                        break
                if not matched:
                    reviews.append({
                        "reviewId": rev_id,
                        "bookId": dec.get("bookId"),
                        "stage": "EDITORIAL",
                        "category": dec.get("category", "TECHNICAL"),
                        "problem": "Reconciled from immutable decision log",
                        "status": "RESOLVED",
                        "decisionId": dec.get("decisionId"),
                        "resolutionAction": dec.get("decision"),
                        "decidedBy": dec.get("decidedBy"),
                        "resolvedAt": dec.get("timestamp"),
                    })
                    dirty = True
            if dirty:
                self._save_reviews(reviews)

    def create_review(self, record: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            reviews = self._load_reviews()
            rid = record.get("reviewId")
            if not rid:
                raise ValueError("Review record requires a non-empty 'reviewId'")
            if any(r["reviewId"] == rid for r in reviews):
                raise ValueError(f"Review with id '{rid}' already exists")

            category = record.get("category")
            if category not in VALID_CATEGORIES:
                raise ValueError(f"Invalid review category '{category}'. Must be one of {VALID_CATEGORIES}")

            rec = dict(record)
            rec.setdefault("createdAt", datetime.now(timezone.utc).isoformat())
            rec["status"] = "PENDING"
            reviews.append(rec)
            self._save_reviews(reviews)
            return rec

    def get_review(self, review_id: str) -> dict[str, Any] | None:
        with self._lock:
            reviews = self._load_reviews()
            for r in reviews:
                if r["reviewId"] == review_id:
                    return r
            return None

    def list_reviews(self, status: str | None = None, category: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            reviews = self._load_reviews()
            result = reviews
            if status:
                result = [r for r in result if r.get("status") == status]
            if category:
                result = [r for r in result if r.get("category") == category]
            return result

    def record_decision(self, decision: dict[str, Any]) -> dict[str, Any]:
        decided_by = str(decision.get("decidedBy") or decision.get("reviewer") or "").strip()
        if not decided_by:
            raise DecisionValidationError("Decision requires a non-empty operator identifier")

        decided_by_lower = decided_by.lower()
        if decided_by_lower in AUTOMATED_AGENT_IDENTIFIERS or any(
            agt in decided_by_lower for agt in ("-agent", "llm", "gemini", "claude", "gpt")
        ):
            raise DecisionValidationError(
                f"Automated agent '{decided_by}' is not authorized to make human review decisions"
            )

        action = decision.get("decision")
        if action not in VALID_DECISION_ACTIONS:
            raise DecisionValidationError(
                f"Invalid decision action '{action}'. Must be one of {VALID_DECISION_ACTIONS}"
            )

        review_id = decision.get("reviewId")
        if not review_id:
            raise DecisionValidationError("Decision requires a 'reviewId'")

        with self._lock:
            # First check immutable decision log directly
            existing_decisions = self.decision_logger.read_all_entries()
            for d in existing_decisions:
                if d.get("reviewId") == review_id:
                    raise ReviewConflictError(
                        f"Review '{review_id}' already has an immutable decision recorded in decision log"
                    )

            reviews = self._load_reviews()
            target_rev = None
            for r in reviews:
                if r["reviewId"] == review_id:
                    target_rev = r
                    break

            if not target_rev:
                raise DecisionValidationError(f"Review '{review_id}' not found")
            if target_rev["status"] != "PENDING":
                raise ReviewConflictError(f"Review '{review_id}' has already been resolved")

            justification = str(decision.get("justification") or decision.get("reviewNotes") or "").strip()
            if target_rev.get("category") == "POLICY_OR_RIGHTS" and not justification:
                raise DecisionValidationError("POLICY_OR_RIGHTS reviews strictly require non-empty justification")

            dec_id = str(decision.get("decisionId") or f"DEC-{review_id}").strip()
            timestamp = decision.get("timestamp") or datetime.now(timezone.utc).isoformat()

            dec_record = {
                "decisionId": dec_id,
                "reviewId": review_id,
                "bookId": target_rev.get("bookId"),
                "decidedBy": decided_by,
                "decision": action,
                "justification": justification,
                "category": target_rev.get("category"),
                "timestamp": timestamp,
            }

            appended_dec = self.decision_logger.append_entry(dec_record)

            target_rev["status"] = "RESOLVED"
            target_rev["decisionId"] = dec_id
            target_rev["resolvedAt"] = timestamp
            target_rev["resolutionAction"] = action
            target_rev["decidedBy"] = decided_by

            self._save_reviews(reviews)
            return appended_dec
