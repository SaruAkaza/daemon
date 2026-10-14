from pathlib import Path
import pytest

from scripts.ops.review_store import ReviewStore, DecisionValidationError, ReviewConflictError
from scripts.ops.hash_chain import IntegrityError


def test_review_store_creation_and_listing(tmp_path):
    store = ReviewStore(stores_dir=tmp_path)

    rev1 = store.create_review({
        "reviewId": "REV-001",
        "bookId": "trevas-3ed",
        "stage": "EDITORIAL",
        "category": "DOMAIN_AMBIGUITY",
        "problem": "Divergência de regra",
        "evidence": {"excerptA": "texto 1", "excerptB": "texto 2"},
        "recommendation": "Adotar texto 1",
        "impact": "Altera perícias",
    })

    assert rev1["reviewId"] == "REV-001"
    assert rev1["status"] == "PENDING"
    assert rev1["category"] == "DOMAIN_AMBIGUITY"
    assert rev1["createdAt"] is not None

    rev2 = store.create_review({
        "reviewId": "REV-002",
        "bookId": "demonio-guia",
        "stage": "ENTITIES",
        "category": "POLICY_OR_RIGHTS",
        "problem": "Verificação de licença",
        "evidence": {},
        "recommendation": "Revisar autorização",
        "impact": "Publicação",
    })

    # Listing filters
    pending = store.list_reviews(status="PENDING")
    assert len(pending) == 2

    rights_reviews = store.list_reviews(category="POLICY_OR_RIGHTS")
    assert len(rights_reviews) == 1
    assert rights_reviews[0]["reviewId"] == "REV-002"

    # Duplicate creation rejected
    with pytest.raises(ValueError):
        store.create_review({"reviewId": "REV-001", "category": "TECHNICAL"})


def test_invalid_category_rejected(tmp_path):
    store = ReviewStore(stores_dir=tmp_path)
    with pytest.raises(ValueError) as exc:
        store.create_review({
            "reviewId": "REV-003",
            "bookId": "b1",
            "category": "INVALID_CATEGORY",
            "problem": "test",
        })
    assert "category" in str(exc.value).lower()


def test_human_decision_lifecycle_and_tamper_evident_logging(tmp_path):
    store = ReviewStore(stores_dir=tmp_path)
    store.create_review({
        "reviewId": "REV-100",
        "bookId": "trevas-3ed",
        "stage": "EDITORIAL",
        "category": "DOMAIN_AMBIGUITY",
        "problem": "Texto ambíguo",
        "evidence": {},
        "recommendation": "Aceitar",
        "impact": "Nenhum",
    })

    dec = store.record_decision({
        "decisionId": "DEC-100",
        "reviewId": "REV-100",
        "decidedBy": "human-operator-carlos",
        "decision": "APPROVE",
        "justification": "Confirmado pela errata oficial do autor.",
    })

    assert dec["decisionId"] == "DEC-100"
    assert "entryHash" in dec
    assert len(dec["entryHash"]) == 64

    # Review status updated in store
    rev = store.get_review("REV-100")
    assert rev["status"] == "RESOLVED"
    assert rev["decisionId"] == "DEC-100"
    assert rev["resolutionAction"] == "APPROVE"

    # Tampering with decisions.jsonl is detected
    dec_file = tmp_path / "decisions.jsonl"
    lines = dec_file.read_text(encoding="utf-8").splitlines()
    lines[0] = lines[0].replace("carlos", "mallory")
    dec_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with pytest.raises(IntegrityError):
        store.decision_logger.read_all_entries()


def test_automated_agent_rejected_fail_closed(tmp_path):
    store = ReviewStore(stores_dir=tmp_path)
    store.create_review({
        "reviewId": "REV-200",
        "bookId": "trevas-3ed",
        "stage": "EDITORIAL",
        "category": "DOMAIN_AMBIGUITY",
        "problem": "Texto ambíguo",
        "evidence": {},
        "recommendation": "",
        "impact": "",
    })

    # Model / agent self-approval must fail closed
    for bad_id in ["editorial-agent", "gemini-flash", "llm-review", "claude-subagent"]:
        with pytest.raises(DecisionValidationError) as exc:
            store.record_decision({
                "decisionId": f"DEC-BAD-{bad_id}",
                "reviewId": "REV-200",
                "decidedBy": bad_id,
                "decision": "APPROVE",
                "justification": "Automated resolution",
            })
        assert "not authorized" in str(exc.value) or "agent" in str(exc.value).lower()

    # Review remains PENDING
    assert store.get_review("REV-200")["status"] == "PENDING"


def test_empty_operator_rejected(tmp_path):
    store = ReviewStore(stores_dir=tmp_path)
    store.create_review({
        "reviewId": "REV-201",
        "bookId": "trevas-3ed",
        "stage": "EDITORIAL",
        "category": "TECHNICAL",
        "problem": "Erro",
        "evidence": {},
        "recommendation": "",
        "impact": "",
    })

    with pytest.raises(DecisionValidationError):
        store.record_decision({
            "decisionId": "DEC-201",
            "reviewId": "REV-201",
            "decidedBy": "   ",
            "decision": "APPROVE",
            "justification": "ok",
        })


def test_policy_or_rights_requires_explicit_justification(tmp_path):
    store = ReviewStore(stores_dir=tmp_path)
    store.create_review({
        "reviewId": "REV-300",
        "bookId": "trevas-3ed",
        "stage": "EDITORIAL",
        "category": "POLICY_OR_RIGHTS",
        "problem": "Direitos",
        "evidence": {},
        "recommendation": "",
        "impact": "",
    })

    with pytest.raises(DecisionValidationError) as exc:
        store.record_decision({
            "decisionId": "DEC-300",
            "reviewId": "REV-300",
            "decidedBy": "human-alice",
            "decision": "APPROVE",
            "justification": "   ",
        })
    assert "justification" in str(exc.value).lower() or "rights" in str(exc.value).lower()


def test_concurrent_double_decision_conflict_prevented(tmp_path):
    store = ReviewStore(stores_dir=tmp_path)
    store.create_review({
        "reviewId": "REV-400",
        "bookId": "trevas-3ed",
        "stage": "EDITORIAL",
        "category": "DOMAIN_AMBIGUITY",
        "problem": "Conflito de regras",
        "evidence": {},
        "recommendation": "",
        "impact": "",
    })

    # First decision succeeds
    store.record_decision({
        "decisionId": "DEC-400-A",
        "reviewId": "REV-400",
        "decidedBy": "human-alice",
        "decision": "APPROVE",
        "justification": "Resolução A",
    })

    # Second decision fails with ReviewConflictError
    with pytest.raises(ReviewConflictError):
        store.record_decision({
            "decisionId": "DEC-400-B",
            "reviewId": "REV-400",
            "decidedBy": "human-bob",
            "decision": "REJECT",
            "justification": "Resolução B",
        })


def test_tampered_decision_log_blocks_store_startup(tmp_path):
    store = ReviewStore(stores_dir=tmp_path)
    store.create_review({
        "reviewId": "REV-500",
        "bookId": "trevas-3ed",
        "stage": "EDITORIAL",
        "category": "TECHNICAL",
        "problem": "Teste tamper",
        "evidence": {},
        "recommendation": "",
        "impact": "",
    })
    store.record_decision({
        "decisionId": "DEC-500",
        "reviewId": "REV-500",
        "decidedBy": "human-alice",
        "decision": "APPROVE",
        "justification": "OK",
    })

    # Tamper with decisions.jsonl
    dec_file = tmp_path / "decisions.jsonl"
    lines = dec_file.read_text(encoding="utf-8").splitlines()
    lines[0] = lines[0].replace("human-alice", "mallory")
    dec_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Creating a new ReviewStore must fail-closed on startup
    from scripts.ops.hash_chain import IntegrityError
    with pytest.raises(IntegrityError):
        ReviewStore(stores_dir=tmp_path)


def test_crash_consistency_reconciliation_between_log_and_snapshot(tmp_path):
    store = ReviewStore(stores_dir=tmp_path)
    store.create_review({
        "reviewId": "REV-600",
        "bookId": "trevas-3ed",
        "stage": "EDITORIAL",
        "category": "TECHNICAL",
        "problem": "Teste crash",
        "evidence": {},
        "recommendation": "",
        "impact": "",
    })
    # Record decision
    store.record_decision({
        "decisionId": "DEC-600",
        "reviewId": "REV-600",
        "decidedBy": "human-alice",
        "decision": "APPROVE",
        "justification": "Aprovado antes de crash",
    })

    # Simulate crash before reviews.json write by reverting reviews.json to PENDING
    from scripts.agents.contracts import write_atomic
    from scripts.agents.canonical_json import canonical_json_bytes
    write_atomic(tmp_path / "reviews.json", canonical_json_bytes({
        "reviews": [{
            "reviewId": "REV-600",
            "bookId": "trevas-3ed",
            "stage": "EDITORIAL",
            "category": "TECHNICAL",
            "problem": "Teste crash",
            "status": "PENDING",
        }]
    }))

    # New ReviewStore boots and reconciles from immutable decision log
    store2 = ReviewStore(stores_dir=tmp_path)
    rev = store2.get_review("REV-600")
    assert rev is not None
    assert rev["status"] == "RESOLVED"
    assert rev["decisionId"] == "DEC-600"
    assert rev["decidedBy"] == "human-alice"

    # Second decision attempt must be rejected
    with pytest.raises(ReviewConflictError):
        store2.record_decision({
            "decisionId": "DEC-600-DUPLICATE",
            "reviewId": "REV-600",
            "decidedBy": "human-bob",
            "decision": "REJECT",
            "justification": "Tentativa indevida",
        })

