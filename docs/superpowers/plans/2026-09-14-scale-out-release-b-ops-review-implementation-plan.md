# Scale-Out Release B — Ops Controller & Human Review Queue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the local-first operational control plane for Daemon Tools, providing a secure loopback-only Ops Controller with ephemeral session token authentication (Windows-first), transactional asynchronous command processing (`POST /api/ops/commands`) with strong idempotency, durable Human Review Queue storage (`ReviewStore`), tamper-evident human decision logging (`DecisionLog`), append-only command auditing (`CommandAuditLog`), real-time Server-Sent Events notifications (`GET /api/ops/events`) with `Last-Event-ID` replay, and restricted frontend operational views (`#/ops`, `#/ops/queue`, `#/ops/reviews`, `#/ops/review/:reviewId`) featuring risk-proportional confirmation rituals and total fail-closed isolation in public mode.

**Architecture:** The Ops Controller operates as a thin, loopback-only HTTP/SSE transport layer completely decoupled from RPG domain rules and Batch Orchestrator scheduling. Frontend code never interacts with persistent stores directly on the filesystem; all mutations flow via authenticated POST commands returning `202 Accepted` with a tracking `commandId`, while state changes push to the UI over an SSE stream backed by an in-memory ring buffer with snapshot fallback. Operational state is durably anchored in append-only JSON/JSONL stores (`runtime/stores/reviews.json`, `runtime/stores/decisions.jsonl`, `runtime/stores/command_audit.jsonl`). In public mode (`mode=public`), operational routes are absent from the router and all `/api/ops/*` endpoints return `404 Not Found`.

**Tech Stack:** Python 3.10+, pytest, standard library `http.server`, standard library `secrets`, `hashlib`, Windows ACL primitives (`icacls` / `win32security` fallback via pure Python stdlib), vanilla ES modules (`.mjs`), HTML5/CSS3, Playwright browser test harness (`pytest tests/frontend/test_site_browser.py`).

**Spec:** `docs/superpowers/specs/2026-09-14-scale-out-acervo-batch-ops-design.md`, commit `117b626cc1bb049f6beeb6498dfa5b7ea511e765`.

---

## Global Constraints

- **PROCESSADO != PUBLICÁVEL**: Technical processing does not imply or authorize public distribution.
- `restricted_preview` and `public` are runtime execution modes (`mode=restricted_preview` / `mode=public`), never to be confused with canonical `publicationMode`.
- **Total Public Fail-Closed Barrier**: In `mode=public` (static export, production docs, GitHub Pages), the Ops Controller is never started, zero `/api/ops/*` endpoints exist (404 Fail-Closed), and the frontend operational routes (`#/ops/*`) are excluded from navigation and route resolution.
- **Loopback Only**: Server binds strictly to `127.0.0.1` and `::1`. Any external request is immediately dropped or rejected (`403 Forbidden`).
- **Ephemeral Token Security**:
  - Generated cryptographically at runtime (`secrets.token_urlsafe(32)`).
  - Persisted in `.daemon_runtime/ops_token` with owner-restricted permissions (Windows-first file access controls; `chmod 600` on POSIX).
  - `.daemon_runtime/` is strictly ignored by Git and never committed.
- **Frontend Isolation**: The frontend **never reads store files directly** from disk. Reads occur via authenticated HTTP endpoints (`GET /api/ops/snapshot`, `GET /api/ops/events`).
- **Idempotency**: Every command carries a client-generated `commandId`. Repeated submissions return the existing command status (`200 OK` or `202 Accepted`) without repeating actions.
- **Safe Book Actions**:
  - `PAUSE_BOOK`: Safely flags the book to pause at the next stage checkpoint boundary; never aborts executing subagents mid-stream and never blocks other running books.
  - `RESUME_BOOK`: Restores a paused book to eligible queued state, respecting validated checkpoints and stage gates.
  - `PRIORITIZE_BOOK`: Adjusts deterministic queue weight without skipping QA gates or integrity checks.
  - Global `PAUSE_ORCHESTRATOR` is an administrative command and **not an MVP requirement**.
- **Human Authority on Rights and Ambiguities**:
  - Decisions in `POLICY_OR_RIGHTS` and `DOMAIN_AMBIGUITY` are strictly human; automated agents (`AUTOMATED_AGENT_IDENTIFIERS`) are rejected by the validator.
  - Rejection of artifacts or requests for correction record immutable rationale in `DecisionLog`.
- **SSE Non-Authority**: SSE is strictly a reactive notification mechanism; durable disk stores are the source of truth for operational state.

---

## Interfaces and File Map

| File | Action | Responsibility |
| :--- | :--- | :--- |
| `scripts/ops/token_manager.py` | Create | Generates high-entropy session token, writes to `.daemon_runtime/ops_token` with OS-appropriate permissions (Windows ACLs / POSIX), and validates incoming Bearer tokens. |
| `scripts/ops/review_store.py` | Create | Durable CRUD store for Human Review Queue items (`runtime/stores/reviews.json`) and append-only cryptographic decisions (`runtime/stores/decisions.jsonl`). |
| `scripts/ops/command_audit.py` | Create | Append-only audit logger (`runtime/stores/command_audit.jsonl`) recording every submitted command, parameters, operator reason, and result. |
| `scripts/ops/command_processor.py` | Create | Asynchronous command dispatcher handling `PAUSE_BOOK`, `RESUME_BOOK`, `PRIORITIZE_BOOK`, `APPROVE_REVIEW`, `REJECT_REVIEW`, and `REQUEST_CORRECTION` with strong idempotency. |
| `scripts/ops/event_broadcaster.py` | Create | In-memory SSE broadcaster with circular ring buffer (100 events), `Last-Event-ID` replay, client connection management, and snapshot fallback notification. |
| `scripts/ops/ops_server.py` | Create | Thin loopback HTTP request handler routing `POST /api/ops/commands`, `GET /api/ops/events`, `GET /api/ops/snapshot`, with strict Origin/Host and token validation. |
| `scripts/agents/preview_server.py` | Modify | Integrates Ops Controller routing in `restricted_preview` mode while enforcing strict 404 fail-closed behavior in `public` mode. |
| `docs/assets/site-ops.mjs` | Create | Frontend operational client: handles token management, SSE connection with auto-reconnect, snapshot fetching, and command submission with optimistic feedback. |
| `docs/assets/site-state.mjs` | Modify | Registers operational routes (`#/ops`, `#/ops/queue`, `#/ops/reviews`, `#/ops/review/:reviewId`) only when running in restricted mode. |
| `docs/assets/site-ui.mjs` | Modify | Renders operational dashboard, review queue table, interactive review resolution modal, and risk-proportional confirmation dialogs. |
| `docs/assets/styles.css` | Modify | Styles for operational badges, review evidence diff viewer, confirmation modals, and live SSE connection indicator. |
| `tests/ops/test_token_manager.py` | Create | Unit tests for token generation, permission setting on Windows and POSIX, and token verification. |
| `tests/ops/test_review_store.py` | Create | Unit tests for review creation, retrieval, status transitions, and immutable decision logging with agent rejection. |
| `tests/ops/test_command_processor.py` | Create | Unit tests for command validation, idempotency caching, state transitions, and audit logging. |
| `tests/ops/test_event_broadcaster.py` | Create | Unit tests for SSE event formatting, client registration, buffer replay via `Last-Event-ID`, and buffer overflow fallback. |
| `tests/ops/test_ops_server_security.py` | Create | Unit tests verifying loopback binding, token rejection, invalid Origin rejection, and public mode 404 fail-closed protection. |
| `tests/frontend/test_site_browser.py` | Modify | Playwright browser tests for `#/ops` dashboard, review resolution flow, and risk-proportional confirmation modals. |

---

## Tasks

### Task 1: Ephemeral Token Manager with Windows-First Permissions (`scripts/ops/token_manager.py`)

**Files:**
- Create: `scripts/ops/token_manager.py`
- Create: `tests/ops/test_token_manager.py`

**Interfaces:**
```python
class TokenManager:
    def __init__(self, runtime_dir: Path | str | None = None) -> None: ...
    def initialize_token(self) -> str: ...
    def get_token(self) -> str | None: ...
    def validate_token(self, provided_token: str | None) -> bool: ...
    def cleanup(self) -> None: ...
```

- [ ] **Step 1: Write failing test**
Create `tests/ops/test_token_manager.py`:
```python
from pathlib import Path
import pytest
from scripts.ops.token_manager import TokenManager

def test_token_manager_generates_and_validates_token(tmp_path):
    tm = TokenManager(runtime_dir=tmp_path)
    token = tm.initialize_token()

    assert isinstance(token, str)
    assert len(token) >= 32
    assert (tmp_path / "ops_token").exists()

    # Valid token
    assert tm.validate_token(token) is True
    assert tm.validate_token(f"Bearer {token}") is True

    # Invalid tokens
    assert tm.validate_token("wrong-token") is False
    assert tm.validate_token("") is False
    assert tm.validate_token(None) is False

    tm.cleanup()
    assert not (tmp_path / "ops_token").exists()
```

- [ ] **Step 2: Run test and confirm RED**
```powershell
python -m pytest tests/ops/test_token_manager.py -v
```
Expected: `ModuleNotFoundError: No module named 'scripts.ops'`.

- [ ] **Step 3: Implement minimal code**
Create `scripts/ops/token_manager.py`:
```python
from __future__ import annotations
import os
from pathlib import Path
import secrets
import stat
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_DIR = ROOT / ".daemon_runtime"

class TokenManager:
    def __init__(self, runtime_dir: Path | str | None = None) -> None:
        self.runtime_dir = Path(runtime_dir).resolve() if runtime_dir else DEFAULT_RUNTIME_DIR
        self.token_file = self.runtime_dir / "ops_token"
        self._current_token: str | None = None

    def initialize_token(self) -> str:
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self._current_token = secrets.token_urlsafe(32)

        # Write token file
        with open(self.token_file, "w", encoding="utf-8") as f:
            f.write(self._current_token)

        self._restrict_file_permissions(self.token_file)
        return self._current_token

    def _restrict_file_permissions(self, path: Path) -> None:
        if sys.platform == "win32":
            # Restrict permissions to current user on Windows via icacls
            try:
                username = os.environ.get("USERNAME")
                if username:
                    subprocess.run(
                        ["icacls", str(path), "/inheritance:r", "/grant:r", f"{username}:(R,W)"],
                        capture_output=True,
                        check=False,
                    )
            except Exception:
                pass
        else:
            # POSIX chmod 600
            try:
                path.chmod(stat.S_IRUSR | stat.S_IWUSR)
            except Exception:
                pass

    def get_token(self) -> str | None:
        if self._current_token:
            return self._current_token
        if self.token_file.exists():
            self._current_token = self.token_file.read_text(encoding="utf-8").strip()
            return self._current_token
        return None

    def validate_token(self, provided_token: str | None) -> bool:
        if not provided_token:
            return False
        current = self.get_token()
        if not current:
            return False
        clean = provided_token.strip()
        if clean.lower().startswith("bearer "):
            clean = clean[7:].strip()
        return secrets.compare_digest(clean, current)

    def cleanup(self) -> None:
        self._current_token = None
        if self.token_file.exists():
            try:
                self.token_file.unlink()
            except OSError:
                pass
```

- [ ] **Step 4: Run test and confirm GREEN**
```powershell
python -m pytest tests/ops/test_token_manager.py -v
```
Expected: 1 passed.

- [ ] **Step 5: Run focused regressions**
```powershell
python -m pytest tests/ops/test_token_manager.py -q
```
Expected: 1 passed.

- [ ] **Step 6: Commit**
```powershell
git add scripts/ops/token_manager.py tests/ops/test_token_manager.py
git commit -m "feat(ops): implement secure ephemeral session token manager"
```

---

### Task 2: Durable Review Store and Decision Log (`scripts/ops/review_store.py`)

**Files:**
- Create: `scripts/ops/review_store.py`
- Create: `tests/ops/test_review_store.py`

**Interfaces:**
```python
class ReviewStore:
    def __init__(self, store_dir: Path | str | None = None) -> None: ...
    def create_review(self, record: dict[str, Any]) -> dict[str, Any]: ...
    def get_review(self, review_id: str) -> dict[str, Any] | None: ...
    def list_reviews(self, status: str | None = None) -> list[dict[str, Any]]: ...
    def record_decision(self, decision: dict[str, Any]) -> dict[str, Any]: ...
```

- [ ] **Step 1: Write failing test**
Create `tests/ops/test_review_store.py`:
```python
from pathlib import Path
import pytest
from scripts.ops.review_store import ReviewStore, DecisionValidationError

def test_review_store_lifecycle_and_decision_logging(tmp_path):
    store = ReviewStore(store_dir=tmp_path)

    review_data = {
        "reviewId": "REV-001",
        "bookId": "trevas-3ed",
        "stage": "EDITORIAL",
        "reason": "Divergência de custo de atributo",
        "severity": "HIGH",
        "evidence": {"file": "editorial.json", "excerptA": "3 pts", "excerptB": "2 pts"},
        "agentRecommendation": "Adotar tabela",
        "impact": "Altera perícias",
    }

    created = store.create_review(review_data)
    assert created["status"] == "PENDING"
    assert created["createdAt"] is not None

    # Automated agent cannot decide
    with pytest.raises(DecisionValidationError):
        store.record_decision({
            "decisionId": "DEC-001",
            "reviewId": "REV-001",
            "bookId": "trevas-3ed",
            "decidedBy": "editorial-agent",
            "decision": "APPROVE",
            "justification": "Automated resolution",
        })

    # Human decision succeeds
    dec = store.record_decision({
        "decisionId": "DEC-001",
        "reviewId": "REV-001",
        "bookId": "trevas-3ed",
        "decidedBy": "operador-humano-1",
        "decision": "APPROVE",
        "justification": "Regra confirmada pelo manual de erratas",
    })

    assert dec["decisionId"] == "DEC-001"
    rev = store.get_review("REV-001")
    assert rev["status"] == "RESOLVED"
    assert rev["decisionId"] == "DEC-001"
```

- [ ] **Step 2: Run test and confirm RED**
```powershell
python -m pytest tests/ops/test_review_store.py -v
```
Expected: `ModuleNotFoundError: No module named 'scripts.ops.review_store'`.

- [ ] **Step 3: Implement minimal code**
Create `scripts/ops/review_store.py`:
```python
from __future__ import annotations
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from scripts.agents.contracts import write_atomic
from scripts.agents.pilot_review import AUTOMATED_AGENT_IDENTIFIERS

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STORES_DIR = ROOT / "runtime" / "stores"

class DecisionValidationError(ValueError):
    pass

class ReviewStore:
    def __init__(self, store_dir: Path | str | None = None) -> None:
        self.store_dir = Path(store_dir).resolve() if store_dir else DEFAULT_STORES_DIR
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.reviews_file = self.store_dir / "reviews.json"
        self.decisions_file = self.store_dir / "decisions.jsonl"
        self._ensure_files()

    def _ensure_files(self) -> None:
        if not self.reviews_file.exists():
            write_atomic(self.reviews_file, json.dumps({"reviews": []}, indent=2).encode("utf-8"))
        if not self.decisions_file.exists():
            self.decisions_file.touch()

    def _load_reviews(self) -> list[dict[str, Any]]:
        with open(self.reviews_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("reviews", [])

    def _save_reviews(self, reviews: list[dict[str, Any]]) -> None:
        write_atomic(self.reviews_file, json.dumps({"reviews": reviews}, indent=2).encode("utf-8"))

    def create_review(self, record: dict[str, Any]) -> dict[str, Any]:
        reviews = self._load_reviews()
        rid = record["reviewId"]
        if any(r["reviewId"] == rid for r in reviews):
            raise ValueError(f"Review with id '{rid}' already exists")

        new_record = dict(record)
        new_record.setdefault("createdAt", datetime.now(timezone.utc).isoformat())
        new_record["status"] = "PENDING"
        reviews.append(new_record)
        self._save_reviews(reviews)
        return new_record

    def get_review(self, review_id: str) -> dict[str, Any] | None:
        reviews = self._load_reviews()
        for r in reviews:
            if r["reviewId"] == review_id:
                return r
        return None

    def list_reviews(self, status: str | None = None) -> list[dict[str, Any]]:
        reviews = self._load_reviews()
        if status:
            return [r for r in reviews if r["status"] == status]
        return reviews

    def record_decision(self, decision: dict[str, Any]) -> dict[str, Any]:
        decided_by = decision.get("decidedBy", "").strip().lower()
        if not decided_by:
            raise DecisionValidationError("Decision requires a valid 'decidedBy' operator identifier")
        if decided_by in AUTOMATED_AGENT_IDENTIFIERS or any(agent in decided_by for agent in AUTOMATED_AGENT_IDENTIFIERS):
            raise DecisionValidationError(f"Automated agent '{decided_by}' is not authorized to make human review decisions")

        action = decision.get("decision")
        if action not in {"APPROVE", "REJECT", "REQUEST_CORRECTION"}:
            raise DecisionValidationError(f"Invalid decision action: '{action}'")

        review_id = decision.get("reviewId")
        review = self.get_review(review_id)
        if not review:
            raise DecisionValidationError(f"Review '{review_id}' not found")
        if review["status"] != "PENDING":
            raise DecisionValidationError(f"Review '{review_id}' is already resolved")

        dec_record = dict(decision)
        dec_record.setdefault("timestamp", datetime.now(timezone.utc).isoformat())

        # Append to decisions.jsonl
        with open(self.decisions_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(dec_record) + "\n")

        # Update review record
        reviews = self._load_reviews()
        for r in reviews:
            if r["reviewId"] == review_id:
                r["status"] = "RESOLVED"
                r["decisionId"] = dec_record["decisionId"]
                r["resolvedAt"] = dec_record["timestamp"]
                r["resolutionAction"] = action
                break
        self._save_reviews(reviews)

        return dec_record
```

- [ ] **Step 4: Run test and confirm GREEN**
```powershell
python -m pytest tests/ops/test_review_store.py -v
```
Expected: 1 passed.

- [ ] **Step 5: Run focused regressions**
```powershell
python -m pytest tests/ops/test_review_store.py tests/ops/test_token_manager.py -q
```
Expected: All pass.

- [ ] **Step 6: Commit**
```powershell
git add scripts/ops/review_store.py tests/ops/test_review_store.py
git commit -m "feat(ops): implement durable review store and decision log with agent rejection"
```

---

### Task 3: Command Audit Log & Asynchronous Command Processor (`scripts/ops/command_processor.py`)

**Files:**
- Create: `scripts/ops/command_audit.py`
- Create: `scripts/ops/command_processor.py`
- Create: `tests/ops/test_command_processor.py`

**Interfaces:**
```python
class CommandAuditLog:
    def __init__(self, log_path: Path | str | None = None) -> None: ...
    def append_log(self, entry: dict[str, Any]) -> None: ...

class CommandProcessor:
    def __init__(self, audit_log: CommandAuditLog | None = None, review_store: ReviewStore | None = None) -> None: ...
    def submit_command(self, cmd_payload: dict[str, Any]) -> dict[str, Any]: ...
    def get_command_status(self, command_id: str) -> dict[str, Any] | None: ...
```

- [ ] **Step 1: Write failing test**
Create `tests/ops/test_command_processor.py`:
```python
from pathlib import Path
import pytest
from scripts.ops.command_processor import CommandProcessor
from scripts.ops.command_audit import CommandAuditLog

def test_command_processor_idempotency_and_transitions(tmp_path):
    audit = CommandAuditLog(log_path=tmp_path / "command_audit.jsonl")
    proc = CommandProcessor(audit_log=audit)

    cmd = {
        "commandId": "CMD-001",
        "command": "PrioritizeBook",
        "bookId": "demonio-guia",
        "payload": {"priorityWeight": 150},
        "reason": "Teste de priorização",
    }

    # First submission -> ACCEPTED
    res1 = proc.submit_command(cmd)
    assert res1["status"] in ("ACCEPTED", "SUCCEEDED")
    assert res1["commandId"] == "CMD-001"

    # Duplicate submission -> returns cached result without re-executing
    res2 = proc.submit_command(cmd)
    assert res2["commandId"] == "CMD-001"
    assert res2["status"] == res1["status"]

    # Verify audit log entry exists
    assert (tmp_path / "command_audit.jsonl").exists()
```

- [ ] **Step 2: Run test and confirm RED**
```powershell
python -m pytest tests/ops/test_command_processor.py -v
```
Expected: `ModuleNotFoundError: No module named 'scripts.ops.command_processor'`.

- [ ] **Step 3: Implement minimal code**
Create `scripts/ops/command_audit.py`:
```python
from __future__ import annotations
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_AUDIT_PATH = ROOT / "runtime" / "stores" / "command_audit.jsonl"

class CommandAuditLog:
    def __init__(self, log_path: Path | str | None = None) -> None:
        self.log_path = Path(log_path).resolve() if log_path else DEFAULT_AUDIT_PATH
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.log_path.exists():
            self.log_path.touch()

    def append_log(self, entry: dict[str, Any]) -> None:
        rec = dict(entry)
        rec.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
```

Create `scripts/ops/command_processor.py`:
```python
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any

from scripts.ops.command_audit import CommandAuditLog
from scripts.ops.review_store import ReviewStore

SUPPORTED_COMMANDS = {
    "PrioritizeBook",
    "PauseBook",
    "ResumeBook",
    "ApproveReview",
    "RejectReview",
    "RequestCorrection",
}

class CommandProcessor:
    def __init__(
        self,
        audit_log: CommandAuditLog | None = None,
        review_store: ReviewStore | None = None,
    ) -> None:
        self.audit_log = audit_log or CommandAuditLog()
        self.review_store = review_store or ReviewStore()
        self._commands: dict[str, dict[str, Any]] = {}

    def submit_command(self, cmd_payload: dict[str, Any]) -> dict[str, Any]:
        cid = cmd_payload.get("commandId")
        if not cid:
            raise ValueError("Command requires a non-empty 'commandId'")

        # Idempotency check: if already processed or in-flight, return existing state
        if cid in self._commands:
            return self._commands[cid]

        cmd_type = cmd_payload.get("command")
        if cmd_type not in SUPPORTED_COMMANDS:
            raise ValueError(f"Unsupported command type: '{cmd_type}'")

        book_id = cmd_payload.get("bookId")
        reason = cmd_payload.get("reason", "")
        payload = cmd_payload.get("payload", {})

        record = {
            "commandId": cid,
            "command": cmd_type,
            "bookId": book_id,
            "status": "ACCEPTED",
            "submittedAt": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
            "reason": reason,
        }
        self._commands[cid] = record

        # Execute command handling
        try:
            self._handle_command(cmd_type, book_id, payload, reason, record)
            record["status"] = "SUCCEEDED"
        except Exception as e:
            record["status"] = "FAILED"
            record["error"] = str(e)

        # Audit log
        self.audit_log.append_log({
            "commandId": cid,
            "commandType": cmd_type,
            "bookId": book_id,
            "previousState": "QUEUED",
            "actionPayload": payload,
            "reason": reason,
            "result": record["status"],
            "decisionId": payload.get("decisionId"),
        })

        return record

    def _handle_command(
        self,
        cmd_type: str,
        book_id: str | None,
        payload: dict[str, Any],
        reason: str,
        record: dict[str, Any],
    ) -> None:
        # Handling logic for commands; Batch Orchestrator will bind to these states in Release C
        if cmd_type == "PrioritizeBook":
            record["appliedPriority"] = payload.get("priorityWeight", 100)
        elif cmd_type == "PauseBook":
            record["targetStatus"] = "PAUSED_AT_CHECKPOINT"
        elif cmd_type == "ResumeBook":
            record["targetStatus"] = "RESUMED_QUEUED"
        elif cmd_type in {"ApproveReview", "RejectReview", "RequestCorrection"}:
            rev_id = payload.get("reviewId")
            decision_action = "APPROVE" if cmd_type == "ApproveReview" else "REJECT" if cmd_type == "RejectReview" else "REQUEST_CORRECTION"
            self.review_store.record_decision({
                "decisionId": f"DEC-{record['commandId']}",
                "reviewId": rev_id,
                "bookId": book_id or "unknown",
                "decidedBy": payload.get("decidedBy", "operator"),
                "decision": decision_action,
                "justification": reason,
            })

    def get_command_status(self, command_id: str) -> dict[str, Any] | None:
        return self._commands.get(command_id)
```

- [ ] **Step 4: Run test and confirm GREEN**
```powershell
python -m pytest tests/ops/test_command_processor.py -v
```
Expected: 1 passed.

- [ ] **Step 5: Run focused regressions**
```powershell
python -m pytest tests/ops -q
```
Expected: All pass.

- [ ] **Step 6: Commit**
```powershell
git add scripts/ops/command_audit.py scripts/ops/command_processor.py tests/ops/test_command_processor.py
git commit -m "feat(ops): implement idempotent command processor and append-only audit log"
```

---

### Task 4: Server-Sent Events (SSE) Broadcaster with Buffer Replay (`scripts/ops/event_broadcaster.py`)

**Files:**
- Create: `scripts/ops/event_broadcaster.py`
- Create: `tests/ops/test_event_broadcaster.py`

**Interfaces:**
```python
class EventBroadcaster:
    def __init__(self, buffer_size: int = 100) -> None: ...
    def publish_event(self, event_type: str, data: dict[str, Any]) -> int: ...
    def get_events_since(self, last_event_id: int) -> tuple[list[dict[str, Any]], bool]: ...
    def format_sse_message(self, event_id: int, event_type: str, data: dict[str, Any]) -> str: ...
```

- [ ] **Step 1: Write failing test**
Create `tests/ops/test_event_broadcaster.py`:
```python
import pytest
from scripts.ops.event_broadcaster import EventBroadcaster

def test_event_broadcaster_publishes_and_replays_via_last_event_id():
    b = EventBroadcaster(buffer_size=5)

    id1 = b.publish_event("job.updated", {"bookId": "a", "status": "RUNNING"})
    id2 = b.publish_event("queue.changed", {"count": 10})
    id3 = b.publish_event("review.created", {"reviewId": "REV-1"})

    assert id1 == 1
    assert id2 == 2
    assert id3 == 3

    # Replay from event 1
    events, needs_snapshot = b.get_events_since(1)
    assert needs_snapshot is False
    assert len(events) == 2
    assert events[0]["id"] == 2
    assert events[1]["id"] == 3

    # Format SSE
    msg = b.format_sse_message(id1, "job.updated", {"bookId": "a"})
    assert "id: 1\n" in msg
    assert "event: job.updated\n" in msg
    assert 'data: {"bookId": "a"}\n\n' in msg
```

- [ ] **Step 2: Run test and confirm RED**
```powershell
python -m pytest tests/ops/test_event_broadcaster.py -v
```
Expected: `ModuleNotFoundError: No module named 'scripts.ops.event_broadcaster'`.

- [ ] **Step 3: Implement minimal code**
Create `scripts/ops/event_broadcaster.py`:
```python
from __future__ import annotations
from collections import deque
import json
import threading
from typing import Any

class EventBroadcaster:
    def __init__(self, buffer_size: int = 100) -> None:
        self.buffer_size = buffer_size
        self._counter = 0
        self._lock = threading.Lock()
        self._history: deque[dict[str, Any]] = deque(maxlen=buffer_size)

    def publish_event(self, event_type: str, data: dict[str, Any]) -> int:
        with self._lock:
            self._counter += 1
            eid = self._counter
            event_record = {
                "id": eid,
                "event": event_type,
                "data": data,
            }
            self._history.append(event_record)
            return eid

    def get_events_since(self, last_event_id: int) -> tuple[list[dict[str, Any]], bool]:
        with self._lock:
            if not self._history:
                return [], False

            oldest_id = self._history[0]["id"]
            if last_event_id < oldest_id - 1:
                # Buffer gap: client is too far behind, requires full snapshot
                return [], True

            events = [e for e in self._history if e["id"] > last_event_id]
            return events, False

    @staticmethod
    def format_sse_message(event_id: int, event_type: str, data: dict[str, Any]) -> str:
        payload = json.dumps(data, separators=(",", ":"))
        return f"id: {event_id}\nevent: {event_type}\ndata: {payload}\n\n"
```

- [ ] **Step 4: Run test and confirm GREEN**
```powershell
python -m pytest tests/ops/test_event_broadcaster.py -v
```
Expected: 1 passed.

- [ ] **Step 5: Run focused regressions**
```powershell
python -m pytest tests/ops -q
```
Expected: All pass.

- [ ] **Step 6: Commit**
```powershell
git add scripts/ops/event_broadcaster.py tests/ops/test_event_broadcaster.py
git commit -m "feat(ops): implement SSE event broadcaster with Last-Event-ID replay buffer"
```

---

### Task 5: Ops Controller Loopback Server & Preview Integration (`scripts/ops/ops_server.py`)

**Files:**
- Create: `scripts/ops/ops_server.py`
- Modify: `scripts/agents/preview_server.py`
- Create: `tests/ops/test_ops_server_security.py`
- Create: `tests/agents/test_preview_server_ops_barrier.py`

**Interfaces:**
- `OpsServer`: handles loopback requests for `/api/ops/commands`, `/api/ops/events`, and `/api/ops/snapshot`.
- `PreviewServer`: delegates `/api/ops/*` to `OpsServer` when `mode == "restricted_preview"`; strictly returns `404 Not Found` when `mode == "public"`.

- [ ] **Step 1: Write failing test**
Create `tests/ops/test_ops_server_security.py`:
```python
import json
from pathlib import Path
import pytest
from scripts.ops.token_manager import TokenManager
from scripts.ops.command_processor import CommandProcessor
from scripts.ops.event_broadcaster import EventBroadcaster
from scripts.ops.ops_server import OpsRequestHandler

def test_ops_server_rejects_missing_or_invalid_token(tmp_path):
    tm = TokenManager(runtime_dir=tmp_path)
    valid_token = tm.initialize_token()

    handler = OpsRequestHandler(
        token_manager=tm,
        command_processor=CommandProcessor(),
        broadcaster=EventBroadcaster(),
    )

    # Missing token -> 401
    code, _, body = handler.dispatch("POST", "/api/ops/commands", headers={}, body=b"{}")
    assert code == 401

    # Valid token -> 200 or 202
    cmd = {"commandId": "C-1", "command": "PauseBook", "bookId": "a"}
    headers = {"Authorization": f"Bearer {valid_token}", "Content-Type": "application/json"}
    code, _, body = handler.dispatch("POST", "/api/ops/commands", headers=headers, body=json.dumps(cmd).encode("utf-8"))
    assert code == 202
```

- [ ] **Step 2: Run test and confirm RED**
```powershell
python -m pytest tests/ops/test_ops_server_security.py -v
```
Expected: `ModuleNotFoundError: No module named 'scripts.ops.ops_server'`.

- [ ] **Step 3: Implement minimal code**
Create `scripts/ops/ops_server.py`:
```python
from __future__ import annotations
import json
from typing import Any

from scripts.ops.command_processor import CommandProcessor
from scripts.ops.event_broadcaster import EventBroadcaster
from scripts.ops.token_manager import TokenManager

class OpsRequestHandler:
    def __init__(
        self,
        token_manager: TokenManager,
        command_processor: CommandProcessor,
        broadcaster: EventBroadcaster,
    ) -> None:
        self.token_manager = token_manager
        self.command_processor = command_processor
        self.broadcaster = broadcaster

    def dispatch(
        self,
        method: str,
        path: str,
        headers: dict[str, str],
        body: bytes,
    ) -> tuple[int, dict[str, str], bytes]:
        # Validate authentication
        auth_header = headers.get("Authorization") or headers.get("authorization")
        if not self.token_manager.validate_token(auth_header):
            return 401, {"Content-Type": "application/json"}, json.dumps({"error": "Unauthorized: invalid or missing ops token"}).encode("utf-8")

        if path == "/api/ops/commands" and method == "POST":
            ctype = headers.get("Content-Type") or headers.get("content-type") or ""
            if "application/json" not in ctype:
                return 400, {"Content-Type": "application/json"}, json.dumps({"error": "Content-Type must be application/json"}).encode("utf-8")
            try:
                cmd_data = json.loads(body.decode("utf-8"))
                result = self.command_processor.submit_command(cmd_data)
                self.broadcaster.publish_event("command.updated", result)
                return 202, {"Content-Type": "application/json"}, json.dumps(result).encode("utf-8")
            except Exception as e:
                return 400, {"Content-Type": "application/json"}, json.dumps({"error": str(e)}).encode("utf-8")

        if path == "/api/ops/snapshot" and method == "GET":
            reviews = self.command_processor.review_store.list_reviews()
            snapshot = {
                "activeJobs": 0,
                "maxActiveBooks": 3,
                "pendingReviews": reviews,
            }
            return 200, {"Content-Type": "application/json"}, json.dumps(snapshot).encode("utf-8")

        return 404, {"Content-Type": "application/json"}, json.dumps({"error": "Not Found"}).encode("utf-8")
```
Modify `scripts/agents/preview_server.py` to route `/api/ops/*` in `restricted_preview` and reject with 404 in `public`:
```python
        # Check ops route barrier
        if self.path.startswith("/api/ops"):
            if self.server.mode != "restricted_preview":
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"Not Found: Ops routes unavailable in public mode")
                return
            # Delegate to OpsRequestHandler...
```

- [ ] **Step 4: Run test and confirm GREEN**
```powershell
python -m pytest tests/ops/test_ops_server_security.py -v
```
Expected: 1 passed.

- [ ] **Step 5: Write public mode fail-closed barrier test**
Create `tests/agents/test_preview_server_ops_barrier.py` to verify that starting `PreviewServer` in `public` mode strictly returns `404` for any `/api/ops/*` request.
- [ ] **Step 6: Commit**
```powershell
git add scripts/ops/ops_server.py scripts/agents/preview_server.py tests/ops/test_ops_server_security.py tests/agents/test_preview_server_ops_barrier.py
git commit -m "feat(ops): implement ops loopback controller and preview server fail-closed barrier"
```

---

### Task 6: Frontend Operational Client & Route Configuration (`docs/assets/site-ops.mjs`)

**Files:**
- Create: `docs/assets/site-ops.mjs`
- Modify: `docs/assets/site-state.mjs`
- Modify: `docs/assets/styles.css`
- Modify: `tests/frontend/site-state.test.mjs`

**Interfaces:**
- `site-ops.mjs`: manages SSE stream (`EventSource`), authentication token storage, command dispatch (`postCommand`), and real-time state subscribers.
- `site-state.mjs`: registers `#/ops`, `#/ops/queue`, `#/ops/reviews`, `#/ops/review/:reviewId` only if `mode === 'restricted_preview'`.

- [ ] **Step 1: Write failing test in `tests/frontend/site-state.test.mjs`**
Verify route parsing recognizes `#/ops` in restricted mode, but redirects/falls back to `#/` in public mode.
- [ ] **Step 2: Run test and confirm RED**
```powershell
node --test tests/frontend/site-state.test.mjs
```
- [ ] **Step 3: Implement `site-ops.mjs` and update `site-state.mjs`**
Create `docs/assets/site-ops.mjs`:
```javascript
export class OpsClient {
  constructor({ baseUrl = '', token = null } = {}) {
    this.baseUrl = baseUrl;
    this.token = token;
    this.listeners = new Set();
    this.eventSource = null;
  }

  subscribe(callback) {
    this.listeners.add(callback);
    return () => this.listeners.delete(callback);
  }

  notify(event) {
    for (const cb of this.listeners) {
      try { cb(event); } catch (err) { console.error(err); }
    }
  }

  async sendCommand(command, bookId, payload = {}, reason = '') {
    const commandId = 'CMD-' + Math.random().toString(36).substring(2, 11);
    const body = { commandId, command, bookId, payload, reason };
    const res = await fetch(`${this.baseUrl}/api/ops/commands`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${this.token}`,
      },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      throw new Error(`Command failed with status ${res.status}`);
    }
    return await res.json();
  }
}
```
- [ ] **Step 4: Run test and confirm GREEN**
```powershell
node --test tests/frontend/site-state.test.mjs
```
Expected: All pass.
- [ ] **Step 5: Commit**
```powershell
git add docs/assets/site-ops.mjs docs/assets/site-state.mjs tests/frontend/site-state.test.mjs
git commit -m "feat(frontend): implement ops client and restricted operational routing"
```

---

### Task 7: Operational UI Dashboard & Risk-Proportional Confirmation Modals (`docs/assets/site-ui.mjs`)

**Files:**
- Modify: `docs/assets/site-ui.mjs`
- Modify: `docs/assets/styles.css`

**Interfaces:**
- `renderOpsDashboard()`: renders 7 global counters (`Total Catalogado: 281`, `Ativos`, `Aguardando`, `Revisões Pendentes`, `Bloqueados`, `Prontos para Aprovação`, `Concluídos`).
- `renderOpsReviews()`: table of human reviews with status, severity badge, and action button.
- `renderReviewDetailModal(reviewId)`: compares `excerptA` vs `excerptB`, displays agent recommendation, and provides Approve, Reject, and Request Correction buttons with reason field.
- Risk-Proportional Modals:
  - Low Risk (`PauseBook`, `ResumeBook`): single-click toggle.
  - Medium Risk (Reject Review, Request Correction): requires text justification.
  - High Risk (Rights changes): requires explicit typed confirmation of `bookId`.

- [ ] **Step 1: Implement UI methods in `docs/assets/site-ui.mjs`**
- [ ] **Step 2: Add styles in `docs/assets/styles.css` for operational dashboard and modals**
- [ ] **Step 3: Verify syntax integrity**
```powershell
node --check docs/assets/app.js
```
Expected: Exit code 0.
- [ ] **Step 4: Commit**
```powershell
git add docs/assets/site-ui.mjs docs/assets/styles.css
git commit -m "feat(frontend): implement operational dashboard views and confirmation modals"
```

---

### Task 8: Browser Test Harness for Operations & Human Review E2E

**Files:**
- Modify: `tests/frontend/test_site_browser.py`

**Interfaces:**
- Browser tests verifying:
  - `#/ops` dashboard counters display.
  - Navigating to `#/ops/reviews`.
  - Opening a review item and submitting an approval.
  - Verifying public mode suppresses `#/ops` and redirects to `#/`.

- [ ] **Step 1: Write browser test in `tests/frontend/test_site_browser.py`**
```python
def test_ops_panel_and_review_resolution_browser(page, site_url):
    page.goto(site_url + "#/ops")
    page.wait_for_selector(".site-ops-dashboard", timeout=10000)

    assert "Painel Operacional" in page.text_content("h1")
    assert "Total Catalogado" in page.text_content(".site-ops-counters")

    # Navigate to reviews
    page.goto(site_url + "#/ops/reviews")
    page.wait_for_selector(".site-ops-reviews-table", timeout=10000)
    assert "Fila Central de Revisão Humana" in page.text_content("h1")
```
- [ ] **Step 2: Run test and confirm GREEN**
```powershell
python -m pytest tests/frontend/test_site_browser.py -q
```
Expected: All pass.
- [ ] **Step 3: Run full regression suite**
```powershell
python -m pytest tests/ops -q
python -m pytest tests/agents -q
node --test tests/frontend/site-model.test.mjs tests/frontend/site-search.test.mjs tests/frontend/site-state.test.mjs
python scripts/validate_data.py
python scripts/check_book_coverage.py
node --check docs/assets/app.js
```
Expected: All pass.
- [ ] **Step 4: Commit**
```powershell
git add tests/frontend/test_site_browser.py
git commit -m "test(browser): verify operational dashboard and human review queue E2E"
```

---

## Verification Plan

### Automated Tests
1. Unit tests for token manager: `python -m pytest tests/ops/test_token_manager.py -v`
2. Unit tests for review store & decision log: `python -m pytest tests/ops/test_review_store.py -v`
3. Unit tests for command processor: `python -m pytest tests/ops/test_command_processor.py -v`
4. Unit tests for SSE broadcaster: `python -m pytest tests/ops/test_event_broadcaster.py -v`
5. Unit tests for security and fail-closed public barriers: `python -m pytest tests/ops/test_ops_server_security.py tests/agents/test_preview_server_ops_barrier.py -v`
6. Frontend node tests: `node --test tests/frontend/site-state.test.mjs`
7. Browser E2E tests: `python -m pytest tests/frontend/test_site_browser.py -q`
8. Global regressions:
   `python -m pytest tests/agents -q`
   `python scripts/validate_data.py`
   `python scripts/check_book_coverage.py`
   `node --check docs/assets/app.js`

### Manual Verification
- Start local preview in `restricted_preview` mode.
- Access `#/ops` in browser; verify token is picked up from `.daemon_runtime/ops_token`.
- Submit a `PauseBook` command; verify `202 Accepted` and optimistic card update.
- Verify that opening `#/ops` in `mode=public` immediately redirects to `#/` and produces 404 for any direct `/api/ops/*` curl.
