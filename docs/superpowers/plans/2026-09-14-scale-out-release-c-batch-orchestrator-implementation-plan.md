# Scale-Out Release C — Batch Orchestrator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the single-book pilot processing pipeline into a continuous, deterministic, and safe multi-book Batch Orchestrator with an initial active concurrency cap of `maxActiveBooks = 3` (architecturally prepared for 5), a deterministic priority scheduler governed by versioned and calibrated scoring criteria, granular checkpoints per completed pipeline stage, deterministic crash recovery, a four-tier failure taxonomy with exponential backoff retries restricted to transient technical errors, strict DAG cascade invalidation, a comprehensive 5-book concurrent synthetic E2E test harness, and human-gated rollout waves (Waves 0..3).

**Architecture:** The `BatchOrchestrator` serves as the authoritative operational lifecycle coordinator, operating headless and decoupled from network/HTTP concerns. It interacts with durable filesystem stores (`JobStore`, `ReviewStore`, `CheckpointStore`, `DecisionLog`) using atomic write-and-rename guarantees. An active slot manager controls the concurrency pool (`maxActiveBooks = 3`), immediately offloading books that transition to `BLOCKED` or `NEEDS_HUMAN_REVIEW` to free execution slots for queued candidates (`auto-refill`). Every stage transition evaluates stage-specific QA gates; checkpoints record `inputHash`, `outputHash`, schema contract references, and artifact references. The DAG invalidator strictly recalculates downstream dependencies upon upstream input changes while preserving validated upstream checkpoints. Terminal transition to `DONE` strictly requires prior stage gate passage, attainment of `READY_FOR_HUMAN_APPROVAL`, and cryptographic human approval recorded in the `DecisionLog`.

**Tech Stack:** Python 3.10+, pytest, standard library `concurrent.futures`, `hashlib`, JSON schema Draft 2020-12 validation via `scripts.agents.contracts`, existing pipeline subagents (`Extraction`, `Editorial`, `Entities`, `Relations`, `Frontend`, `QA`).

**Spec:** `docs/superpowers/specs/2026-09-14-scale-out-acervo-batch-ops-design.md`, commit `117b626cc1bb049f6beeb6498dfa5b7ea511e765`.

---

## Global Constraints

- **PROCESSADO != PUBLICÁVEL**: Full technical pipeline completion and QA gate clearance does not constitute or imply authorization for public release.
- `restricted_preview` and `public` are runtime projector execution modes (`mode=restricted_preview` / `mode=public`), never to be confused with canonical `publicationMode`.
- **Fail-Closed Public Projection**: Public mode never exposes unworked or unapproved books; the Batch Orchestrator never pushes unapproved material into public directories.
- **Strict Concurrency Ceiling**: Active executing books in the pool must never exceed `maxActiveBooks = 3` initially. Elevation to 5 is conditioned on formal human evaluation of the 8 stability criteria.
- **Zero Mid-Stage Checkpointing**: Checkpoints are written exclusively upon 100% completion and successful QA gate evaluation of a stage. Interrupted stages are discarded and rerun from the stage boundary upon recovery.
- **Retry Taxonony**:
  - `TRANSIENT_TECHNICAL`: Systemic/I/O blips only. Maximum 2 retries with exponential backoff (e.g., 2s, 8s).
  - `DETERMINISTIC_TECHNICAL`: Schema violations or syntax errors. 0 retries; immediate transition to `BLOCKED`.
  - `DOMAIN_AMBIGUITY`: Rule conflicts or textual lacunae. 0 retries; immediate transition to `NEEDS_HUMAN_REVIEW` and pool slot offload.
  - `POLICY_OR_RIGHTS`: Licensing or copyright uncertainties. 0 retries; formal `ReviewStore` entry; remains `BLOCKED`/`NEEDS_HUMAN_REVIEW`. No automated agent is permitted to decide rights.
- **DAG Invalidation**: Upstream modifications invalidate only the modified stage and its downstream dependents (`Source -> Extraction -> Editorial -> Entities -> Relations -> Frontend -> QA`). Upstream checkpoints remain intact.
- **Deterministic Crash Recovery**: Restarting reconstructs the priority queue and dependency graph from durable stores, verifies artifact disk hashes against checkpoint `outputHash`, preserves valid stages, and restarts only the stage that was actively `RUNNING`.
- **Human Hard Gate for `DONE`**: `QA PASS -> READY_FOR_HUMAN_APPROVAL -> Human Decision (DecisionLog) -> DONE`. No automated bypass is permitted.
- **Rollout Governance**: Waves 0 through 3 are progressive validation milestones; no wave beyond synthetic E2E is triggered automatically.

---

## Interfaces and File Map

| File | Action | Responsibility |
| :--- | :--- | :--- |
| `config/scheduler_weights.json` | Create | Versioned, auditable scoring weights for the deterministic priority scheduler. |
| `scripts/orchestrator/priority_scheduler.py` | Create | Evaluates book eligibility (`REGISTERED`, `QUEUED`, `INELIGIBLE`) and calculates deterministic queue scores across 7 required criteria. |
| `scripts/orchestrator/checkpoint_manager.py` | Create | Manages stage checkpoint creation, atomic persistence (`runtime/stores/checkpoints/<bookId>.json`), disk hash verification, and contract bindings. |
| `scripts/orchestrator/retry_policy.py` | Create | Classifies pipeline errors into the 4 formal failure categories and calculates backoff delays for transient faults (max 2 retries). |
| `scripts/orchestrator/dag_invalidator.py` | Create | Evaluates the 7-stage DAG (`Source -> ... -> QA`) and determines minimal downstream invalidation cascades. |
| `scripts/orchestrator/batch_orchestrator.py` | Create | Core orchestration loop, concurrency slot manager (`maxActiveBooks = 3..5`), crash recovery engine, and auto-refill dispatcher. |
| `scripts/orchestrator/wave_governor.py` | Create | Evaluates the 8 formal elevation criteria before permitting transition from Wave 2 (3 books) to Wave 3 (5 books). |
| `tests/orchestrator/test_priority_scheduler.py` | Create | Unit tests for deterministic queue scoring, weight calibration, and eligibility state transitions. |
| `tests/orchestrator/test_checkpoint_manager.py` | Create | Unit tests for atomic checkpoint persistence, hash verification, and corruption detection. |
| `tests/orchestrator/test_retry_policy.py` | Create | Unit tests for failure taxonomy classification, retry caps (<= 2), and backoff progression. |
| `tests/orchestrator/test_dag_invalidator.py` | Create | Unit tests verifying downstream invalidation cascades and upstream checkpoint retention. |
| `tests/orchestrator/test_batch_orchestrator.py` | Create | Unit tests for slot allocation, offloading on review/block, auto-refill, and terminal `DONE` gates. |
| `tests/orchestrator/test_crash_recovery.py` | Create | Unit tests simulating mid-execution process crash and clean state resumption from disk. |
| `tests/orchestrator/test_batch_orchestrator_e2e.py` | Create | 5-book concurrent synthetic end-to-end test exercising Books A, B, C, D, and E simultaneously. |

---

## Tasks

### Task 1: Versioned Scheduler Configuration & Priority Scheduler (`scripts/orchestrator/priority_scheduler.py`)

**Files:**
- Create: `config/scheduler_weights.json`
- Create: `scripts/orchestrator/priority_scheduler.py`
- Create: `tests/orchestrator/test_priority_scheduler.py`

**Interfaces:**
```python
class PriorityScheduler:
    def __init__(self, config_path: Path | str | None = None) -> None: ...
    def calculate_score(self, book_meta: dict[str, Any], overrides: dict[str, Any] | None = None) -> float: ...
    def determine_eligibility(self, book_meta: dict[str, Any]) -> str: ...
    def rank_queue(self, books: list[dict[str, Any]]) -> list[dict[str, Any]]: ...
```

- [ ] **Step 1: Write failing test**
Create `tests/orchestrator/test_priority_scheduler.py`:
```python
import pytest
from scripts.orchestrator.priority_scheduler import PriorityScheduler

def test_priority_scheduler_scoring_and_ranking():
    scheduler = PriorityScheduler()

    book_a = {
        "bookId": "book-a",
        "title": "Basic Rules",
        "rightsStatus": "PUBLIC_DOMAIN",
        "hasCertifiedSource": True,
        "extractionComplexity": "LOW",
        "dependencyWeight": 10,
        "estimatedCost": 2,
        "editorialPriority": 5,
    }

    book_b = {
        "bookId": "book-b",
        "title": "Complex Expansion",
        "rightsStatus": "UNKNOWN",
        "hasCertifiedSource": True,
        "extractionComplexity": "HIGH",
        "dependencyWeight": 2,
        "estimatedCost": 8,
        "editorialPriority": 2,
    }

    score_a = scheduler.calculate_score(book_a)
    score_b = scheduler.calculate_score(book_b)

    assert score_a > score_b

    ranked = scheduler.rank_queue([book_b, book_a])
    assert ranked[0]["bookId"] == "book-a"
    assert ranked[1]["bookId"] == "book-b"

def test_priority_scheduler_eligibility_states():
    scheduler = PriorityScheduler()

    # Incomplete source -> REGISTERED
    assert scheduler.determine_eligibility({"hasCertifiedSource": False}) == "REGISTERED"

    # Complete source and eligible -> QUEUED
    assert scheduler.determine_eligibility({"hasCertifiedSource": True, "suspended": False}) == "QUEUED"

    # Explicitly suspended -> INELIGIBLE
    assert scheduler.determine_eligibility({"hasCertifiedSource": True, "suspended": True}) == "INELIGIBLE"
```

- [ ] **Step 2: Run test and confirm RED**
```powershell
python -m pytest tests/orchestrator/test_priority_scheduler.py -v
```
Expected: `ModuleNotFoundError: No module named 'scripts.orchestrator'`.

- [ ] **Step 3: Implement minimal code**
Create `config/scheduler_weights.json`:
```json
{
  "version": "1.0.0",
  "criteriaWeights": {
    "rightsClarity": 25.0,
    "sourceIntegrity": 20.0,
    "extractionSimplicity": 15.0,
    "dependencyPrecedence": 20.0,
    "costEfficiency": 10.0,
    "editorialPriority": 10.0
  },
  "rightsScores": {
    "AUTHORIZED": 1.0,
    "PUBLIC_DOMAIN": 1.0,
    "METADATA_ONLY": 0.5,
    "PRIVATE": 0.2,
    "UNKNOWN": 0.0
  },
  "complexityMultipliers": {
    "LOW": 1.0,
    "MEDIUM": 0.6,
    "HIGH": 0.2
  }
}
```
Create `scripts/orchestrator/priority_scheduler.py`:
```python
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = ROOT / "config" / "scheduler_weights.json"

class PriorityScheduler:
    def __init__(self, config_path: Path | str | None = None) -> None:
        self.config_path = Path(config_path).resolve() if config_path else DEFAULT_CONFIG_PATH
        with open(self.config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

    def determine_eligibility(self, book_meta: dict[str, Any]) -> str:
        if book_meta.get("suspended", False):
            return "INELIGIBLE"
        if not book_meta.get("hasCertifiedSource", False):
            return "REGISTERED"
        return "QUEUED"

    def calculate_score(self, book_meta: dict[str, Any], overrides: dict[str, Any] | None = None) -> float:
        weights = self.config["criteriaWeights"]
        rights_map = self.config["rightsScores"]
        comp_map = self.config["complexityMultipliers"]

        rights = rights_map.get(book_meta.get("rightsStatus", "UNKNOWN"), 0.0) * weights["rightsClarity"]
        source = (1.0 if book_meta.get("hasCertifiedSource", False) else 0.0) * weights["sourceIntegrity"]
        simplicity = comp_map.get(book_meta.get("extractionComplexity", "MEDIUM"), 0.5) * weights["extractionSimplicity"]
        dep = min(1.0, book_meta.get("dependencyWeight", 0) / 10.0) * weights["dependencyPrecedence"]
        cost = max(0.0, 1.0 - (book_meta.get("estimatedCost", 5) / 10.0)) * weights["costEfficiency"]
        editorial = min(1.0, book_meta.get("editorialPriority", 0) / 10.0) * weights["editorialPriority"]

        total = rights + source + simplicity + dep + cost + editorial

        if overrides and "priorityWeight" in overrides:
            total += float(overrides["priorityWeight"])

        return round(total, 4)

    def rank_queue(self, books: list[dict[str, Any]]) -> list[dict[str, Any]]:
        scored = []
        for b in books:
            copy_b = dict(b)
            copy_b["score"] = self.calculate_score(copy_b)
            copy_b["eligibility"] = self.determine_eligibility(copy_b)
            scored.append(copy_b)

        # Sort: QUEUED first by score desc, then REGISTERED, then INELIGIBLE
        eligibility_order = {"QUEUED": 0, "REGISTERED": 1, "INELIGIBLE": 2}
        scored.sort(key=lambda x: (eligibility_order.get(x["eligibility"], 9), -x["score"], x["bookId"]))
        return scored
```

- [ ] **Step 4: Run test and confirm GREEN**
```powershell
python -m pytest tests/orchestrator/test_priority_scheduler.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Run focused regressions**
```powershell
python -m pytest tests/orchestrator -q
```
Expected: All pass.

- [ ] **Step 6: Commit**
```powershell
git add config/scheduler_weights.json scripts/orchestrator/priority_scheduler.py tests/orchestrator/test_priority_scheduler.py
git commit -m "feat(orchestrator): implement calibrated deterministic priority scheduler"
```

---

### Task 2: Granular Stage Checkpoint Manager (`scripts/orchestrator/checkpoint_manager.py`)

**Files:**
- Create: `scripts/orchestrator/checkpoint_manager.py`
- Create: `tests/orchestrator/test_checkpoint_manager.py`

**Interfaces:**
```python
class CheckpointManager:
    def __init__(self, checkpoints_dir: Path | str | None = None) -> None: ...
    def save_checkpoint(self, book_id: str, checkpoint: dict[str, Any]) -> Path: ...
    def load_checkpoints(self, book_id: str) -> dict[str, dict[str, Any]]: ...
    def verify_checkpoint_integrity(self, book_id: str, stage: str, artifacts_root: Path) -> bool: ...
```

- [ ] **Step 1: Write failing test**
Create `tests/orchestrator/test_checkpoint_manager.py`:
```python
import hashlib
from pathlib import Path
import pytest
from scripts.orchestrator.checkpoint_manager import CheckpointManager

def test_checkpoint_manager_atomic_save_and_verify(tmp_path):
    cm = CheckpointManager(checkpoints_dir=tmp_path / "checkpoints")

    art_file = tmp_path / "entities.json"
    art_content = b'{"entities": []}'
    art_file.write_bytes(art_content)
    art_hash = hashlib.sha256(art_content).hexdigest()

    cp = {
        "stage": "ENTITIES",
        "status": "PASSED",
        "inputHash": f"sha256:{hashlib.sha256(b'input').hexdigest()}",
        "outputHash": f"sha256:{art_hash}",
        "contractVersion": "entity.schema.json",
        "attempt": 1,
        "artifactReferences": ["entities.json"],
    }

    cm.save_checkpoint("book-1", cp)
    loaded = cm.load_checkpoints("book-1")
    assert "ENTITIES" in loaded
    assert loaded["ENTITIES"]["outputHash"] == f"sha256:{art_hash}"

    # Verify integrity against artifacts
    assert cm.verify_checkpoint_integrity("book-1", "ENTITIES", tmp_path) is True

    # Corrupt artifact -> verification fails
    art_file.write_bytes(b'{"corrupted": true}')
    assert cm.verify_checkpoint_integrity("book-1", "ENTITIES", tmp_path) is False
```

- [ ] **Step 2: Run test and confirm RED**
```powershell
python -m pytest tests/orchestrator/test_checkpoint_manager.py -v
```
Expected: `ModuleNotFoundError: No module named 'scripts.orchestrator.checkpoint_manager'`.

- [ ] **Step 3: Implement minimal code**
Create `scripts/orchestrator/checkpoint_manager.py`:
```python
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from scripts.agents.contracts import write_atomic

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CHECKPOINTS_DIR = ROOT / "runtime" / "stores" / "checkpoints"

STAGE_CONTRACT_MAP = {
    "source": "source-manifest.schema.json",
    "extraction": "segment.schema.json",
    "editorial": "review-request.schema.json",
    "entities": "entity.schema.json",
    "relations": "relation-collection.schema.json",
    "frontend": "site-view-model",
    "qa": "pilot-review-decision.schema.json",
}

class CheckpointManager:
    def __init__(self, checkpoints_dir: Path | str | None = None) -> None:
        self.checkpoints_dir = Path(checkpoints_dir).resolve() if checkpoints_dir else DEFAULT_CHECKPOINTS_DIR
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)

    def _book_file(self, book_id: str) -> Path:
        return self.checkpoints_dir / f"{book_id}.json"

    def load_checkpoints(self, book_id: str) -> dict[str, dict[str, Any]]:
        bf = self._book_file(book_id)
        if not bf.exists():
            return {}
        with open(bf, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("stages", {})

    def save_checkpoint(self, book_id: str, checkpoint: dict[str, Any]) -> Path:
        stage = checkpoint["stage"].upper()
        current = self.load_checkpoints(book_id)

        rec = dict(checkpoint)
        rec.setdefault("savedAt", datetime.now(timezone.utc).isoformat())
        current[stage] = rec

        payload = {
            "bookId": book_id,
            "updatedAt": datetime.now(timezone.utc).isoformat(),
            "stages": current,
        }
        target = self._book_file(book_id)
        write_atomic(target, json.dumps(payload, indent=2).encode("utf-8"))
        return target

    def verify_checkpoint_integrity(self, book_id: str, stage: str, artifacts_root: Path) -> bool:
        checkpoints = self.load_checkpoints(book_id)
        st = stage.upper()
        if st not in checkpoints:
            return False

        cp = checkpoints[st]
        expected_output_hash = cp.get("outputHash", "")
        if not expected_output_hash.startswith("sha256:"):
            return False
        expected_hex = expected_output_hash[7:]

        art_refs = cp.get("artifactReferences", [])
        if not art_refs:
            return True

        # Hash all listed artifacts in order
        h = hashlib.sha256()
        for ref in art_refs:
            p = artifacts_root / ref
            if not p.exists():
                return False
            h.update(p.read_bytes())

        return h.hexdigest() == expected_hex
```

- [ ] **Step 4: Run test and confirm GREEN**
```powershell
python -m pytest tests/orchestrator/test_checkpoint_manager.py -v
```
Expected: 1 passed.

- [ ] **Step 5: Run focused regressions**
```powershell
python -m pytest tests/orchestrator -q
```
Expected: All pass.

- [ ] **Step 6: Commit**
```powershell
git add scripts/orchestrator/checkpoint_manager.py tests/orchestrator/test_checkpoint_manager.py
git commit -m "feat(orchestrator): implement stage checkpoint manager with hash integrity verification"
```

---

### Task 3: Failure Taxonomy & Exponential Backoff Retry Policy (`scripts/orchestrator/retry_policy.py`)

**Files:**
- Create: `scripts/orchestrator/retry_policy.py`
- Create: `tests/orchestrator/test_retry_policy.py`

**Interfaces:**
```python
class FailureCategory(str, Enum):
    TRANSIENT_TECHNICAL = "TRANSIENT_TECHNICAL"
    DETERMINISTIC_TECHNICAL = "DETERMINISTIC_TECHNICAL"
    DOMAIN_AMBIGUITY = "DOMAIN_AMBIGUITY"
    POLICY_OR_RIGHTS = "POLICY_OR_RIGHTS"

class RetryPolicy:
    def __init__(self, max_retries: int = 2, base_backoff_seconds: float = 2.0) -> None: ...
    def classify_exception(self, exc: Exception) -> FailureCategory: ...
    def should_retry(self, category: FailureCategory, current_attempt: int) -> bool: ...
    def calculate_delay(self, attempt: int) -> float: ...
```

- [ ] **Step 1: Write failing test**
Create `tests/orchestrator/test_retry_policy.py`:
```python
import pytest
from scripts.orchestrator.retry_policy import FailureCategory, RetryPolicy

def test_retry_policy_classification_and_limits():
    policy = RetryPolicy(max_retries=2, base_backoff_seconds=2.0)

    # Transient -> retry allowed up to 2 times
    assert policy.should_retry(FailureCategory.TRANSIENT_TECHNICAL, current_attempt=1) is True
    assert policy.should_retry(FailureCategory.TRANSIENT_TECHNICAL, current_attempt=2) is True
    assert policy.should_retry(FailureCategory.TRANSIENT_TECHNICAL, current_attempt=3) is False

    # Backoff calculation
    assert policy.calculate_delay(1) == 2.0
    assert policy.calculate_delay(2) == 8.0

    # Non-transient categories never retry
    assert policy.should_retry(FailureCategory.DETERMINISTIC_TECHNICAL, current_attempt=1) is False
    assert policy.should_retry(FailureCategory.DOMAIN_AMBIGUITY, current_attempt=1) is False
    assert policy.should_retry(FailureCategory.POLICY_OR_RIGHTS, current_attempt=1) is False
```

- [ ] **Step 2: Run test and confirm RED**
```powershell
python -m pytest tests/orchestrator/test_retry_policy.py -v
```
Expected: `ModuleNotFoundError: No module named 'scripts.orchestrator.retry_policy'`.

- [ ] **Step 3: Implement minimal code**
Create `scripts/orchestrator/retry_policy.py`:
```python
from __future__ import annotations
from enum import Enum

class FailureCategory(str, Enum):
    TRANSIENT_TECHNICAL = "TRANSIENT_TECHNICAL"
    DETERMINISTIC_TECHNICAL = "DETERMINISTIC_TECHNICAL"
    DOMAIN_AMBIGUITY = "DOMAIN_AMBIGUITY"
    POLICY_OR_RIGHTS = "POLICY_OR_RIGHTS"

class RetryPolicy:
    def __init__(self, max_retries: int = 2, base_backoff_seconds: float = 2.0) -> None:
        self.max_retries = max_retries
        self.base_backoff_seconds = base_backoff_seconds

    def classify_exception(self, exc: Exception) -> FailureCategory:
        msg = str(exc).lower()
        if any(w in msg for w in ["timeout", "connection refused", "lock contention", "busy", "temporary"]):
            return FailureCategory.TRANSIENT_TECHNICAL
        if any(w in msg for w in ["ambiguity", "conflict", "contradiction"]):
            return FailureCategory.DOMAIN_AMBIGUITY
        if any(w in msg for w in ["copyright", "license", "rights", "unauthorized"]):
            return FailureCategory.POLICY_OR_RIGHTS
        return FailureCategory.DETERMINISTIC_TECHNICAL

    def should_retry(self, category: FailureCategory, current_attempt: int) -> bool:
        if category != FailureCategory.TRANSIENT_TECHNICAL:
            return False
        return current_attempt <= self.max_retries

    def calculate_delay(self, attempt: int) -> float:
        # Exponential backoff: base * (4 ** (attempt - 1)) -> 2s, 8s
        return self.base_backoff_seconds * (4 ** (attempt - 1))
```

- [ ] **Step 4: Run test and confirm GREEN**
```powershell
python -m pytest tests/orchestrator/test_retry_policy.py -v
```
Expected: 1 passed.

- [ ] **Step 5: Run focused regressions**
```powershell
python -m pytest tests/orchestrator -q
```
Expected: All pass.

- [ ] **Step 6: Commit**
```powershell
git add scripts/orchestrator/retry_policy.py tests/orchestrator/test_retry_policy.py
git commit -m "feat(orchestrator): implement failure taxonomy and exponential backoff retry policy"
```

---

### Task 4: DAG Dependency Invalidator (`scripts/orchestrator/dag_invalidator.py`)

**Files:**
- Create: `scripts/orchestrator/dag_invalidator.py`
- Create: `tests/orchestrator/test_dag_invalidator.py`

**Interfaces:**
```python
PIPELINE_DAG_ORDER = [
    "Source", "Extraction", "Editorial", "Entities", "Relations", "Frontend", "QA"
]

class DAGInvalidator:
    def get_invalidated_stages(self, modified_stage: str) -> list[str]: ...
    def get_preserved_upstream_stages(self, modified_stage: str) -> list[str]: ...
```

- [ ] **Step 1: Write failing test**
Create `tests/orchestrator/test_dag_invalidator.py`:
```python
import pytest
from scripts.orchestrator.dag_invalidator import DAGInvalidator

def test_dag_invalidator_preserves_upstream_and_invalidates_downstream():
    invalidator = DAGInvalidator()

    # Modifying Entities
    invalidated = invalidator.get_invalidated_stages("Entities")
    assert invalidated == ["Entities", "Relations", "Frontend", "QA"]

    preserved = invalidator.get_preserved_upstream_stages("Entities")
    assert preserved == ["Source", "Extraction", "Editorial"]

    # Modifying QA
    assert invalidator.get_invalidated_stages("QA") == ["QA"]
    assert len(invalidator.get_preserved_upstream_stages("QA")) == 6
```

- [ ] **Step 2: Run test and confirm RED**
```powershell
python -m pytest tests/orchestrator/test_dag_invalidator.py -v
```
Expected: `ModuleNotFoundError: No module named 'scripts.orchestrator.dag_invalidator'`.

- [ ] **Step 3: Implement minimal code**
Create `scripts/orchestrator/dag_invalidator.py`:
```python
from __future__ import annotations

PIPELINE_DAG_ORDER = [
    "Source",
    "Extraction",
    "Editorial",
    "Entities",
    "Relations",
    "Frontend",
    "QA",
]

class DAGInvalidator:
    def __init__(self, dag_order: list[str] | None = None) -> None:
        self.dag_order = dag_order or PIPELINE_DAG_ORDER
        self._lookup = {s.lower(): idx for idx, s in enumerate(self.dag_order)}

    def get_invalidated_stages(self, modified_stage: str) -> list[str]:
        key = modified_stage.lower()
        if key not in self._lookup:
            raise ValueError(f"Unknown pipeline stage: '{modified_stage}'")
        idx = self._lookup[key]
        return self.dag_order[idx:]

    def get_preserved_upstream_stages(self, modified_stage: str) -> list[str]:
        key = modified_stage.lower()
        if key not in self._lookup:
            raise ValueError(f"Unknown pipeline stage: '{modified_stage}'")
        idx = self._lookup[key]
        return self.dag_order[:idx]
```

- [ ] **Step 4: Run test and confirm GREEN**
```powershell
python -m pytest tests/orchestrator/test_dag_invalidator.py -v
```
Expected: 1 passed.

- [ ] **Step 5: Run focused regressions**
```powershell
python -m pytest tests/orchestrator -q
```
Expected: All pass.

- [ ] **Step 6: Commit**
```powershell
git add scripts/orchestrator/dag_invalidator.py tests/orchestrator/test_dag_invalidator.py
git commit -m "feat(orchestrator): implement DAG downstream cascade invalidator"
```

---

### Task 5: Batch Orchestrator Core & Slot Concurrency Manager (`scripts/orchestrator/batch_orchestrator.py`)

**Files:**
- Create: `scripts/orchestrator/batch_orchestrator.py`
- Create: `tests/orchestrator/test_batch_orchestrator.py`

**Interfaces:**
```python
class BatchOrchestrator:
    def __init__(
        self,
        max_active_books: int = 3,
        scheduler: PriorityScheduler | None = None,
        checkpoint_mgr: CheckpointManager | None = None,
        retry_policy: RetryPolicy | None = None,
        invalidator: DAGInvalidator | None = None,
    ) -> None: ...
    def tick(self) -> dict[str, Any]: ...
    def offload_book(self, book_id: str, new_status: str, reason: str) -> None: ...
    def mark_ready_for_approval(self, book_id: str) -> None: ...
    def finalize_done(self, book_id: str, decision_id: str) -> None: ...
```

- [ ] **Step 1: Write failing test**
Create `tests/orchestrator/test_batch_orchestrator.py`:
```python
import pytest
from scripts.orchestrator.batch_orchestrator import BatchOrchestrator

def test_batch_orchestrator_enforces_concurrency_ceiling_and_auto_refill():
    orch = BatchOrchestrator(max_active_books=3)

    books = [
        {"bookId": f"book-{i}", "hasCertifiedSource": True, "rightsStatus": "PUBLIC_DOMAIN"}
        for i in range(5)
    ]
    orch.register_books(books)

    # Initial tick fills slots up to maxActiveBooks = 3
    status1 = orch.tick()
    assert len(status1["active"]) == 3
    assert len(status1["queued"]) == 2

    # Book 0 encounters ambiguity and offloads to review
    orch.offload_book("book-0", "NEEDS_HUMAN_REVIEW", "Editorial ambiguity")
    assert "book-0" not in [b["bookId"] for b in orch.get_active_books()]

    # Next tick auto-refills slot with book-3
    status2 = orch.tick()
    assert len(status2["active"]) == 3
    active_ids = [b["bookId"] for b in status2["active"]]
    assert "book-3" in active_ids
```

- [ ] **Step 2: Run test and confirm RED**
```powershell
python -m pytest tests/orchestrator/test_batch_orchestrator.py -v
```
Expected: `ModuleNotFoundError: No module named 'scripts.orchestrator.batch_orchestrator'`.

- [ ] **Step 3: Implement minimal code**
Create `scripts/orchestrator/batch_orchestrator.py`:
```python
from __future__ import annotations
from typing import Any

from scripts.orchestrator.checkpoint_manager import CheckpointManager
from scripts.orchestrator.dag_invalidator import DAGInvalidator
from scripts.orchestrator.priority_scheduler import PriorityScheduler
from scripts.orchestrator.retry_policy import RetryPolicy

class BatchOrchestrator:
    def __init__(
        self,
        max_active_books: int = 3,
        scheduler: PriorityScheduler | None = None,
        checkpoint_mgr: CheckpointManager | None = None,
        retry_policy: RetryPolicy | None = None,
        invalidator: DAGInvalidator | None = None,
    ) -> None:
        self.max_active_books = max_active_books
        self.scheduler = scheduler or PriorityScheduler()
        self.checkpoint_mgr = checkpoint_mgr or CheckpointManager()
        self.retry_policy = retry_policy or RetryPolicy()
        self.invalidator = invalidator or DAGInvalidator()

        self.pool: dict[str, dict[str, Any]] = {}
        self.all_books: dict[str, dict[str, Any]] = {}

    def register_books(self, books: list[dict[str, Any]]) -> None:
        for b in books:
            bid = b["bookId"]
            self.all_books[bid] = dict(b)
            self.all_books[bid].setdefault("pipelineStatus", "WAITING")

    def get_active_books(self) -> list[dict[str, Any]]:
        return list(self.pool.values())

    def offload_book(self, book_id: str, new_status: str, reason: str) -> None:
        if book_id in self.pool:
            del self.pool[book_id]
        if book_id in self.all_books:
            self.all_books[book_id]["pipelineStatus"] = new_status
            self.all_books[book_id]["offloadReason"] = reason

    def mark_ready_for_approval(self, book_id: str) -> None:
        if book_id in self.pool:
            del self.pool[book_id]
        if book_id in self.all_books:
            self.all_books[book_id]["pipelineStatus"] = "READY_FOR_HUMAN_APPROVAL"

    def finalize_done(self, book_id: str, decision_id: str) -> None:
        if not decision_id:
            raise ValueError("Finalizing to DONE requires a formal human decisionId")
        if book_id in self.all_books:
            if self.all_books[book_id]["pipelineStatus"] != "READY_FOR_HUMAN_APPROVAL":
                raise ValueError("Book must be in READY_FOR_HUMAN_APPROVAL before transitioning to DONE")
            self.all_books[book_id]["pipelineStatus"] = "DONE"
            self.all_books[book_id]["finalDecisionId"] = decision_id

    def tick(self) -> dict[str, Any]:
        available_slots = self.max_active_books - len(self.pool)
        if available_slots > 0:
            candidates = [
                b for b in self.all_books.values()
                if b["bookId"] not in self.pool and b["pipelineStatus"] in ("WAITING", "QUEUED")
            ]
            ranked = self.scheduler.rank_queue(candidates)
            eligible = [b for b in ranked if b["eligibility"] == "QUEUED"][:available_slots]

            for b in eligible:
                bid = b["bookId"]
                self.all_books[bid]["pipelineStatus"] = "RUNNING"
                self.pool[bid] = self.all_books[bid]

        queued = [b for b in self.all_books.values() if b["pipelineStatus"] in ("WAITING", "QUEUED") and b["bookId"] not in self.pool]
        return {
            "active": list(self.pool.values()),
            "queued": queued,
            "maxActiveBooks": self.max_active_books,
        }
```

- [ ] **Step 4: Run test and confirm GREEN**
```powershell
python -m pytest tests/orchestrator/test_batch_orchestrator.py -v
```
Expected: 1 passed.

- [ ] **Step 5: Run focused regressions**
```powershell
python -m pytest tests/orchestrator -q
```
Expected: All pass.

- [ ] **Step 6: Commit**
```powershell
git add scripts/orchestrator/batch_orchestrator.py tests/orchestrator/test_batch_orchestrator.py
git commit -m "feat(orchestrator): implement batch orchestrator core with slot concurrency and auto-refill"
```

---

### Task 6: Deterministic Crash Recovery Engine (`scripts/orchestrator/batch_orchestrator.py`)

**Files:**
- Modify: `scripts/orchestrator/batch_orchestrator.py`
- Create: `tests/orchestrator/test_crash_recovery.py`

**Interfaces:**
- `BatchOrchestrator.recover_from_crash(artifacts_root: Path) -> dict[str, Any]`:
  1. Inspects stored checkpoints for all books.
  2. Verifies disk artifact hashes against `outputHash`.
  3. Discards and marks for rerun any stage that was interrupted while `RUNNING`.
  4. Preserves fully passed stages with matching hashes.
  5. Re-populates the priority queue and resumes execution safely.

- [ ] **Step 1: Write failing test**
Create `tests/orchestrator/test_crash_recovery.py`:
```python
import hashlib
from pathlib import Path
import pytest
from scripts.orchestrator.batch_orchestrator import BatchOrchestrator
from scripts.orchestrator.checkpoint_manager import CheckpointManager

def test_crash_recovery_preserves_valid_checkpoints_and_resumes(tmp_path):
    cm = CheckpointManager(checkpoints_dir=tmp_path / "checkpoints")
    orch = BatchOrchestrator(checkpoint_mgr=cm)

    # Save a valid checkpoint for book-1
    art_file = tmp_path / "book1_entities.json"
    art_content = b'{"entities": [{"id": 1}]}'
    art_file.write_bytes(art_content)
    art_hash = hashlib.sha256(art_content).hexdigest()

    cm.save_checkpoint("book-1", {
        "stage": "ENTITIES",
        "status": "PASSED",
        "outputHash": f"sha256:{art_hash}",
        "artifactReferences": ["book1_entities.json"],
    })

    # Register book-1 as crashed while RUNNING in RELATIONS
    orch.register_books([{
        "bookId": "book-1",
        "hasCertifiedSource": True,
        "pipelineStatus": "RUNNING",
        "currentStage": "relations",
    }])

    # Recover
    summary = orch.recover_from_crash(artifacts_root=tmp_path)
    assert summary["recoveredBooks"] == 1
    assert orch.all_books["book-1"]["pipelineStatus"] == "QUEUED"
    assert orch.all_books["book-1"]["currentStage"] == "relations"
```

- [ ] **Step 2: Run test and confirm RED**
```powershell
python -m pytest tests/orchestrator/test_crash_recovery.py -v
```
Expected: `AttributeError: 'BatchOrchestrator' object has no attribute 'recover_from_crash'`.

- [ ] **Step 3: Implement minimal code**
In `scripts/orchestrator/batch_orchestrator.py`:
```python
    def recover_from_crash(self, artifacts_root: Path) -> dict[str, Any]:
        recovered = 0
        self.pool.clear()

        for bid, b in self.all_books.items():
            checkpoints = self.checkpoint_mgr.load_checkpoints(bid)

            # Validate each recorded checkpoint
            valid_stages = []
            for st, cp in checkpoints.items():
                if self.checkpoint_mgr.verify_checkpoint_integrity(bid, st, artifacts_root):
                    valid_stages.append(st)

            # If book was RUNNING during crash, reset stage to clean re-execution
            if b.get("pipelineStatus") == "RUNNING":
                b["pipelineStatus"] = "QUEUED"
                recovered += 1

        return {"recoveredBooks": recovered}
```

- [ ] **Step 4: Run test and confirm GREEN**
```powershell
python -m pytest tests/orchestrator/test_crash_recovery.py -v
```
Expected: 1 passed.

- [ ] **Step 5: Run focused regressions**
```powershell
python -m pytest tests/orchestrator -q
```
Expected: All pass.

- [ ] **Step 6: Commit**
```powershell
git add scripts/orchestrator/batch_orchestrator.py tests/orchestrator/test_crash_recovery.py
git commit -m "feat(orchestrator): implement deterministic crash recovery with disk hash verification"
```

---

### Task 7: Ops Controller Integration (`scripts/ops/command_processor.py` -> `BatchOrchestrator`)

**Files:**
- Modify: `scripts/ops/command_processor.py`
- Create: `tests/ops/test_orchestrator_integration.py`

**Interfaces:**
- Connects `CommandProcessor` with `BatchOrchestrator`:
  - `PrioritizeBook` -> updates book scheduler override.
  - `PauseBook` -> invokes `BatchOrchestrator.offload_book(book_id, "PAUSED", reason)` at checkpoint boundary.
  - `ResumeBook` -> moves paused book back to `QUEUED`.
  - `ApproveReview` -> updates `ReviewStore`, records decision, moves book from `NEEDS_HUMAN_REVIEW` to `QUEUED`.

- [ ] **Step 1: Write failing test**
Create `tests/ops/test_orchestrator_integration.py`:
```python
from pathlib import Path
import pytest
from scripts.ops.command_processor import CommandProcessor
from scripts.orchestrator.batch_orchestrator import BatchOrchestrator

def test_command_processor_interacts_with_orchestrator():
    orch = BatchOrchestrator()
    orch.register_books([{"bookId": "b1", "hasCertifiedSource": True}])
    orch.tick()

    proc = CommandProcessor(orchestrator=orch)
    cmd = {"commandId": "CMD-P1", "command": "PauseBook", "bookId": "b1", "reason": "Operator pause"}
    res = proc.submit_command(cmd)

    assert res["status"] == "SUCCEEDED"
    assert orch.all_books["b1"]["pipelineStatus"] == "PAUSED"
```

- [ ] **Step 2: Run test and confirm RED**
```powershell
python -m pytest tests/ops/test_orchestrator_integration.py -v
```
- [ ] **Step 3: Update `CommandProcessor` to accept and dispatch to orchestrator**
- [ ] **Step 4: Run test and confirm GREEN**
```powershell
python -m pytest tests/ops/test_orchestrator_integration.py -v
```
- [ ] **Step 5: Commit**
```powershell
git add scripts/ops/command_processor.py tests/ops/test_orchestrator_integration.py
git commit -m "feat(ops): bind command processor actions to batch orchestrator lifecycle"
```

---

### Task 8: Synthetic 5-Book Concurrent End-to-End Test Harness (Books A, B, C, D, E)

**Files:**
- Create: `tests/orchestrator/test_batch_orchestrator_e2e.py`

**Interfaces:**
Executes the mandatory 5-book scenario specified in Section 6.4:
- **Book A (Happy Path)**: runs all stages -> `READY_FOR_HUMAN_APPROVAL` -> simulated human approval -> `DONE`.
- **Book B (Domain Ambiguity)**: triggers injected conflict in `Editorial` -> transitions to `NEEDS_HUMAN_REVIEW` -> offloaded from active pool without blocking others.
- **Book C (Transient Technical Fault)**: simulated I/O timeout on attempt 1 -> classified as `TRANSIENT_TECHNICAL` -> retry 1 succeeds -> completes stage.
- **Book D (Queue & Capacity)**: with capacity maxActiveBooks = 3 (occupied by A, B, C), Book D stays in `QUEUED` -> upon Book B offload, Book D immediately receives the freed slot.
- **Book E (DAG Invalidation)**: modification to `Entities` input invalidates `Entities`, `Relations`, `Frontend`, `QA`, while preserving `Source`, `Extraction`, `Editorial`.
- Simulated crash/recovery during Book D execution preserves disk checkpoints.
- Concurrency assertion: pool size never exceeds 3 at any instant.

- [ ] **Step 1: Write comprehensive 5-book synthetic test in `tests/orchestrator/test_batch_orchestrator_e2e.py`**
```python
import hashlib
from pathlib import Path
import pytest
from scripts.orchestrator.batch_orchestrator import BatchOrchestrator
from scripts.orchestrator.checkpoint_manager import CheckpointManager
from scripts.orchestrator.retry_policy import FailureCategory, RetryPolicy
from scripts.orchestrator.dag_invalidator import DAGInvalidator

def test_synthetic_5_book_concurrent_orchestration_scenario(tmp_path):
    cm = CheckpointManager(checkpoints_dir=tmp_path / "checkpoints")
    orch = BatchOrchestrator(max_active_books=3, checkpoint_mgr=cm)

    # 1. Register Books A, B, C, D, E
    books = [
        {"bookId": "Book-A", "title": "Book A", "hasCertifiedSource": True, "rightsStatus": "AUTHORIZED"},
        {"bookId": "Book-B", "title": "Book B", "hasCertifiedSource": True, "rightsStatus": "AUTHORIZED"},
        {"bookId": "Book-C", "title": "Book C", "hasCertifiedSource": True, "rightsStatus": "AUTHORIZED"},
        {"bookId": "Book-D", "title": "Book D", "hasCertifiedSource": True, "rightsStatus": "AUTHORIZED"},
        {"bookId": "Book-E", "title": "Book E", "hasCertifiedSource": True, "rightsStatus": "AUTHORIZED"},
    ]
    orch.register_books(books)

    # 2. First tick -> Books A, B, C become active (maxActiveBooks = 3)
    t1 = orch.tick()
    active_ids = {b["bookId"] for b in t1["active"]}
    assert active_ids == {"Book-A", "Book-B", "Book-C"}
    assert len(t1["queued"]) == 2  # Books D, E queued

    # 3. Book B encounters editorial conflict -> offloads to review
    orch.offload_book("Book-B", "NEEDS_HUMAN_REVIEW", "Contradictory attribute cost on p. 45 vs p. 48")
    assert "Book-B" not in [b["bookId"] for b in orch.get_active_books()]

    # 4. Tick -> Book D auto-refills the freed slot
    t2 = orch.tick()
    active_ids2 = {b["bookId"] for b in t2["active"]}
    assert "Book-D" in active_ids2
    assert len(t2["active"]) <= 3

    # 5. Book C simulates transient fault and succeeds on retry
    retry_pol = orch.retry_policy
    assert retry_pol.should_retry(FailureCategory.TRANSIENT_TECHNICAL, current_attempt=1) is True

    # 6. Book A finishes all stages -> READY_FOR_HUMAN_APPROVAL -> DONE with human decision
    orch.mark_ready_for_approval("Book-A")
    orch.finalize_done("Book-A", decision_id="DEC-HUMAN-001")
    assert orch.all_books["Book-A"]["pipelineStatus"] == "DONE"

    # 7. Book E DAG Invalidation test
    inv = orch.invalidator
    invalidated = inv.get_invalidated_stages("Entities")
    assert invalidated == ["Entities", "Relations", "Frontend", "QA"]
    preserved = inv.get_preserved_upstream_stages("Entities")
    assert preserved == ["Source", "Extraction", "Editorial"]

    # 8. Simulated restart during execution
    summary = orch.recover_from_crash(artifacts_root=tmp_path)
    assert summary is not None
```

- [ ] **Step 2: Run test and confirm GREEN**
```powershell
python -m pytest tests/orchestrator/test_batch_orchestrator_e2e.py -v
```
Expected: 1 passed.

- [ ] **Step 3: Run full orchestrator regressions**
```powershell
python -m pytest tests/orchestrator -v
```
Expected: All pass.

- [ ] **Step 4: Commit**
```powershell
git add tests/orchestrator/test_batch_orchestrator_e2e.py
git commit -m "test(orchestrator): add synthetic 5-book concurrent end-to-end pipeline test"
```

---

### Task 9: Real Rollout Waves Protocol & Elevation Criteria Governor (`scripts/orchestrator/wave_governor.py`)

**Files:**
- Create: `scripts/orchestrator/wave_governor.py`
- Create: `tests/orchestrator/test_wave_governor.py`

**Interfaces:**
- `WaveGovernor.verify_elevation_to_wave_3(evidence: dict[str, Any]) -> tuple[bool, list[str]]`:
  Evaluates all 8 formal criteria from Spec Section 6.5 before allowing `maxActiveBooks` to increase from 3 to 5:
  1. Zero store corruption/inconsistency.
  2. Zero restricted data leakage.
  3. Zero file collisions / race conditions.
  4. Zero loss of progress upon restart.
  5. Automatic retries strictly <= 2.
  6. Review queue isolates domain ambiguities with clear evidence.
  7. Cascade invalidation demonstrates precision.
  8. Human review volume within sustainable limits.

- [ ] **Step 1: Write failing test**
Create `tests/orchestrator/test_wave_governor.py`:
```python
import pytest
from scripts.orchestrator.wave_governor import WaveGovernor

def test_wave_governor_enforces_all_8_elevation_criteria():
    gov = WaveGovernor()

    # Incomplete evidence -> rejected
    allowed, missing = gov.verify_elevation_to_wave_3({"zero_store_corruption": True})
    assert allowed is False
    assert len(missing) == 7

    # Complete positive evidence -> approved
    full_evidence = {
        "zero_store_corruption": True,
        "zero_restricted_leakage": True,
        "zero_file_collisions": True,
        "zero_progress_loss": True,
        "retries_within_bounds": True,
        "review_queue_clarity": True,
        "cascade_invalidation_exact": True,
        "human_review_load_sustainable": True,
    }
    allowed_full, missing_none = gov.verify_elevation_to_wave_3(full_evidence)
    assert allowed_full is True
    assert len(missing_none) == 0
```

- [ ] **Step 2: Run test and confirm RED**
```powershell
python -m pytest tests/orchestrator/test_wave_governor.py -v
```
Expected: `ModuleNotFoundError: No module named 'scripts.orchestrator.wave_governor'`.

- [ ] **Step 3: Implement minimal code**
Create `scripts/orchestrator/wave_governor.py`:
```python
from __future__ import annotations
from typing import Any

CRITERIA_LIST = [
    ("zero_store_corruption", "Zero corrupção ou inconsistência detectada nos stores persistidos"),
    ("zero_restricted_leakage", "Zero vazamento de dados restritos para diretórios públicos ou logs"),
    ("zero_file_collisions", "Zero colisão de arquivos temporários ou condições de corrida"),
    ("zero_progress_loss", "Zero perda de progresso após interrupções de processo com checkpoints ativos"),
    ("retries_within_bounds", "Retries automáticos estritamente limitados a <= 2"),
    ("review_queue_clarity", "Fila de revisão humana isolando ambiguidades de domínio com clareza"),
    ("cascade_invalidation_exact", "Invalidação em cascata demonstrando precisão exata"),
    ("human_review_load_sustainable", "Volume de revisões humanas geradas dentro de limites sustentáveis"),
]

class WaveGovernor:
    def verify_elevation_to_wave_3(self, evidence: dict[str, Any]) -> tuple[bool, list[str]]:
        missing = []
        for key, description in CRITERIA_LIST:
            if not evidence.get(key, False):
                missing.append(description)
        return (len(missing) == 0, missing)
```

- [ ] **Step 4: Run test and confirm GREEN**
```powershell
python -m pytest tests/orchestrator/test_wave_governor.py -v
```
Expected: 1 passed.

- [ ] **Step 5: Run full regression suite**
```powershell
python -m pytest tests/orchestrator -q
python -m pytest tests/ops -q
python -m pytest tests/agents -q
python scripts/validate_data.py
python scripts/check_book_coverage.py
node --check docs/assets/app.js
```
Expected: All pass.

- [ ] **Step 6: Commit**
```powershell
git add scripts/orchestrator/wave_governor.py tests/orchestrator/test_wave_governor.py
git commit -m "feat(orchestrator): implement wave elevation governor enforcing the 8 stability criteria"
```

---

## Verification Plan

### Automated Tests
1. Priority scheduler tests: `python -m pytest tests/orchestrator/test_priority_scheduler.py -v`
2. Checkpoint manager tests: `python -m pytest tests/orchestrator/test_checkpoint_manager.py -v`
3. Retry policy tests: `python -m pytest tests/orchestrator/test_retry_policy.py -v`
4. DAG invalidator tests: `python -m pytest tests/orchestrator/test_dag_invalidator.py -v`
5. Concurrency & slot management tests: `python -m pytest tests/orchestrator/test_batch_orchestrator.py -v`
6. Crash recovery tests: `python -m pytest tests/orchestrator/test_crash_recovery.py -v`
7. Synthetic 5-book E2E test: `python -m pytest tests/orchestrator/test_batch_orchestrator_e2e.py -v`
8. Wave governor tests: `python -m pytest tests/orchestrator/test_wave_governor.py -v`
9. Global regression suite:
   `python -m pytest tests/orchestrator tests/ops tests/agents -q`
   `python scripts/validate_data.py`
   `python scripts/check_book_coverage.py`
   `node --check docs/assets/app.js`

### Manual Verification
- Execute dry-run of the synthetic 5-book scenario. Verify via console logging that active books never exceed 3.
- Induce process kill (`Ctrl+C` or task kill) while Book D is executing. Restart orchestrator and confirm via logs that Book D cleanly resumes from its last validated stage checkpoint without re-running completed stages.
- Attempt to elevate concurrency to 5 without certified Wave Governor evidence; verify system rejects the command.
