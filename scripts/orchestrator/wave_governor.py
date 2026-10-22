from __future__ import annotations

from typing import Any

from scripts.ops.review_store import ReviewStore, validate_human_operator
from scripts.orchestrator.checkpoint_manager import digest

CRITERIA = (
    "zero_store_corruption", "zero_restricted_leakage", "zero_file_collisions",
    "zero_progress_loss", "retries_within_bounds", "review_queue_clarity",
    "cascade_invalidation_exact", "human_review_load_sustainable",
)


def validate_concurrency(limit: int, reviews: ReviewStore,
                         evidence_review_id: str | None = None) -> None:
    if type(limit) is not int or not 1 <= limit <= 5:
        raise ValueError("Concurrency must be an integer between one and five")
    if limit <= 3:
        return
    review = reviews.get_review(evidence_review_id or "") or {}
    evidence: dict[str, Any] = review.get("evidence", {})
    if (review.get("reviewKind") != "BATCH_WAVE" or set(evidence) != set(CRITERIA)
            or any(value is not True for value in evidence.values())
            or review.get("snapshotSha256") != digest(evidence)):
        raise ValueError("More than three slots requires complete wave evidence")
    decisions = reviews.decision_logger.read_all_entries()
    matching = [d for d in decisions if d.get("reviewId") == evidence_review_id and d.get("decision") == "APPROVE"
                and d.get("reviewKind") == "BATCH_WAVE"
                and d.get("bookId") == review.get("bookId")
                and d.get("snapshotSha256") == digest(evidence)]
    if not matching:
        raise ValueError("Wave evidence requires a recorded human approval")
    validate_human_operator(matching[0].get("decidedBy"))
