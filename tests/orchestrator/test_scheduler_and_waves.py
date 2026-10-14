import json

import pytest

from scripts.ops.review_store import ReviewStore
from scripts.orchestrator.checkpoint_manager import digest
from scripts.orchestrator.priority_scheduler import PriorityScheduler
from scripts.orchestrator.wave_governor import CRITERIA, validate_concurrency


def test_priority_ties_are_stable_and_overrides_change_next_selection():
    scheduler = PriorityScheduler()
    books = [{"bookId": b, "manifest": {"rightsStatus": "UNKNOWN"}, "metadata": {}} for b in "cba"]
    assert [b["bookId"] for b in scheduler.rank(books)] == list("abc")
    books[0]["priorityWeight"] = 200
    assert [b["bookId"] for b in scheduler.rank(books)] == list("cab")
    books[1]["manifest"]["rightsStatus"] = "AUTHORIZED"
    assert scheduler.score(books[1]) > scheduler.score(books[2])


@pytest.mark.parametrize("weights", [{"unexpected": 1}, {"rightsClarity": -1}])
def test_invalid_scheduler_configuration_is_rejected(tmp_path, weights):
    config = json.loads((__import__("pathlib").Path("config/scheduler_weights.json")).read_text())
    config["criteriaWeights"].update(weights)
    path = tmp_path / "weights.json"
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError):
        PriorityScheduler(path)


def test_five_slots_require_complete_evidence_and_hash_bound_human_approval(tmp_path):
    reviews = ReviewStore(tmp_path)
    validate_concurrency(3, reviews)
    with pytest.raises(ValueError):
        validate_concurrency(5, reviews)
    evidence = dict.fromkeys(CRITERIA, True)
    record = {"reviewId": "wave-3", "bookId": "batch-wave-3", "category": "TECHNICAL",
              "reviewKind": "BATCH_WAVE", "evidence": evidence, "snapshotSha256": digest(evidence)}
    reviews.create_review(record)
    with pytest.raises(ValueError, match="human approval"):
        validate_concurrency(5, reviews, "wave-3")
    reviews.record_decision({"reviewId": "wave-3", "decidedBy": "human-tester", "decision": "APPROVE",
                             "snapshotSha256": record["snapshotSha256"]})
    validate_concurrency(5, reviews, "wave-3")
    evidence[CRITERIA[0]] = 1
    reviews.create_review({**record, "reviewId": "wave-invalid", "evidence": evidence,
                           "snapshotSha256": digest(evidence)})
    with pytest.raises(ValueError, match="complete wave evidence"):
        validate_concurrency(5, reviews, "wave-invalid")
