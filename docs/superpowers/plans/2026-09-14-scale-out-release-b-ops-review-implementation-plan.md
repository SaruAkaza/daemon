# Scale-Out Release B — Ops Controller & Human Review Queue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> **Constraint:** This is a documentation and planning artifact. Execution of tasks must follow formal human approval and proceed strictly in dedicated worktrees with strict TDD.

**Goal:** Deliver the hardened, local-first operational control plane for Daemon Tools, providing a secure, loopback-only Ops Controller integrated directly inside `PreviewServer` with same-origin session-cookie authentication (Windows-first), transactional asynchronous command processing (`POST /api/ops/commands`) with durable idempotency, durable Human Review Queue storage (`ReviewStore`), tamper-evident decision logging (`DecisionLog`), tamper-evident command auditing (`CommandAuditLog`), real-time Server-Sent Events notifications (`GET /api/ops/events`) with `Last-Event-ID` replay and snapshot fallback, server-side risk-proportional confirmation enforcement, and restricted frontend operational views (`#/ops`, `#/ops/queue`, `#/ops/reviews`, `#/ops/review/:reviewId`) with total fail-closed isolation in public mode.

**Architecture:**
The Ops Controller operates as a thin, loopback-only HTTP/SSE transport layer mounted internally within `PreviewServer` when running in `mode="restricted_preview"`. It is completely decoupled from RPG domain rules and Batch Orchestrator scheduling (which belongs to Release C).
- **No Third Server:** Ops routes run on the exact same origin as the preview server. No independent secondary server or port is spawned.
- **Browser Authentication & SSE Compatibility:** Browser JavaScript NEVER reads `.daemon_runtime/ops_token` from disk, NEVER receives file paths, NEVER stores tokens in `localStorage`/`sessionStorage`, and NEVER transmits credentials in URL query strings. Authentication for both `fetch` and native browser `EventSource` is handled via a process-scoped, same-origin, `HttpOnly; SameSite=Strict; Path=/api/ops` session cookie issued by `PreviewServer` upon loading the restricted preview. A separate CLI Bearer token interface exists strictly for local scripts and tooling.
- **Fail-Closed Token Manager:** High-entropy token generation (`secrets.token_urlsafe(32)`). Process-scoped. Windows file ACLs are enforced via Windows native `icacls` (without external pywin32 dependencies); if ACL restriction cannot be applied and verified, the controller fails closed and refuses to start. POSIX environments enforce `chmod 600`. Stale tokens from prior runs are rotated immediately on startup.
- **Durable Idempotency & Truly Asynchronous Processing:** Mutations flow via `POST /api/ops/commands`. The controller validates payload against `schemas/ops-command.schema.json`, verifies server-side risk confirmation, writes command state to `commands.json`, records `ACCEPTED` into `command_audit.jsonl`, and immediately responds with `202 Accepted`. A background worker loop asynchronously executes transitions (`ACCEPTED` -> `RUNNING` -> `SUCCEEDED` / `FAILED` / `BLOCKED`). Re-submitting the same `commandId` with the identical canonical payload returns the existing state without repeating mutations; re-submitting the same `commandId` with a conflicting payload strictly returns `409 Conflict`.
- **No Faking Release C:** Release B does not execute the batch pipeline. Commands persist operational intents (`PAUSE_REQUESTED`, priority overrides in `control_state.json`, `REPROCESS_STAGE` intent, `DEQUEUE_BOOK` queue removal). Real initial states are retrieved from existing stores; state transitions are never fabricated.
- **Human Authority & Tamper-Evident Logs:** Review decisions require an explicit human `operatorId`/`reviewer`; automated agent identities (`AUTOMATED_AGENT_IDENTIFIERS` from `scripts/agents/pilot_review.py`) are strictly rejected. Both `decisions.jsonl` and `command_audit.jsonl` are protected by a tamper-evident SHA-256 hash chain (`prevHash` + `entryHash`).
- **Total Public Fail-Closed Barrier:** In `mode="public"`, `OpsRequestHandler` is never registered, `/api/ops/*` returns `404 Not Found` (fail-closed), operational routes are omitted from the router, and frontend navigation contains zero references to operational controls.

**Tech Stack:** Python 3.10+, pytest, standard library `http.server`, standard library `secrets`, standard library `hashlib`, standard library `subprocess` (for Windows native `icacls`), vanilla ES modules (`.mjs`), HTML5/CSS3, Playwright browser test harness (`pytest tests/frontend/test_site_browser.py`).

**Authoritative Spec:** `docs/superpowers/specs/2026-09-14-scale-out-acervo-batch-ops-design.md`, commit `117b626cc1bb049f6beeb6498dfa5b7ea511e765`.

---

## 1. Global Constraints & Architectural Tenets

1. **PROCESSADO != PUBLICÁVEL**: Technical pipeline completion does not imply or authorize public distribution.
2. **Canonical Runtime Directory (`resolve_canonical_runtime_dir`)**:
   - Release B MUST NOT introduce alternative runtime directories or independent defaults such as `ROOT / "runtime"` or `ROOT / ".daemon_runtime"`.
   - All runtime paths MUST be resolved via `resolve_canonical_runtime_dir(runtime_dir)` as established in `scripts/agents/archive_inventory_loader.py`.
   - Operational directory structure:
     ```text
     <canonical .daemon_runtime>/
         ops/
             stores/
                 reviews.json
                 decisions.jsonl
                 commands.json
                 command_audit.jsonl
                 control_state.json
             ops_token
     ```
   - All operational files remain untracked and strictly ignored by Git.
   - All automated test suites (`tests/ops/`, `tests/frontend/`) execute against synthetic runtimes located in `tmp_path`. The developer's real `.daemon_runtime` is accessed exclusively in separate Local Acceptance procedures.
3. **No Third Server (Internal Same-Origin Preview Integration)**:
   - Ops Controller is NOT an independent HTTP server listening on another port.
   - `PreviewServer` remains the single local HTTP server.
   - `OpsRequestHandler` is mounted internally inside `PreviewServer`.
   - In `mode="restricted_preview"`: Ops routes are active on the same origin (e.g. `http://127.0.0.1:8080/api/ops/*`).
   - In `mode="public"`: Ops routes are completely absent; requests to `/api/ops/*` strictly return `404 Not Found`.
4. **Browser Authentication & SSE Compatibility**:
   - Browser JavaScript NEVER accesses filesystem paths or reads `.daemon_runtime/ops_token`.
   - Browser JavaScript NEVER stores credentials in `localStorage` or `sessionStorage`.
   - Credentials NEVER appear in URL query strings (e.g., `?token=...` is strictly forbidden).
   - Upon initial page load in `restricted_preview`, `PreviewServer` establishes a process-ephemeral session and sets an `HttpOnly; SameSite=Strict; Path=/api/ops` cookie.
   - Standard browser `fetch("/api/ops/...")` and native `new EventSource("/api/ops/events")` authenticate transparently via this same-origin session cookie.
   - CLI/curl requests can authenticate via `Authorization: Bearer <token>` reading from `<runtime>/ops/ops_token`.
5. **Fail-Closed Token & Session Security**:
   - Token generated using `secrets.token_urlsafe(32)`.
   - Token is rotated upon each Ops Controller startup.
   - Windows file permissions on `ops_token` are configured with native `icacls` to grant read/write access solely to the current user and strip inheritance. If `icacls` execution fails or permissions cannot be verified, startup is aborted immediately (fail-closed; no `except: pass`).
   - POSIX environments apply `chmod 600` and assert file mode.
   - Token file is removed upon graceful server shutdown.
6. **Typed Command Schema & Canonical Identifiers**:
   - Every operational command must validate against `schemas/ops-command.schema.json`.
   - Command types are canonical SCREAMING_SNAKE_CASE:
     - `PRIORITIZE_BOOK`
     - `PAUSE_BOOK`
     - `RESUME_BOOK`
     - `REPROCESS_STAGE`
     - `DEQUEUE_BOOK`
     - `APPROVE_REVIEW`
     - `REJECT_REVIEW`
     - `REQUEST_CORRECTION`
   - Global `PAUSE_ORCHESTRATOR` is an administrative command and is **not part of the MVP**.
7. **Durable Idempotency & Crash Recovery**:
   - Idempotency is persisted in `commands.json` via atomic replacement (`write_atomic`).
   - Each command stores its canonical payload hash (`canonical_json_bytes` + SHA-256).
   - Resubmission with the exact same `commandId` and payload returns the existing command record (zero duplicate mutations or audit records).
   - Resubmission with the same `commandId` but conflicting payload returns `409 Conflict` (zero mutation).
   - State survives process crashes and restarts.
8. **Asynchronous Command Processing Lifecycle**:
   - `POST /api/ops/commands` validates, persists command state as `ACCEPTED`, records audit entry, and immediately responds with `202 Accepted`.
   - Execution occurs asynchronously via a local processor loop:
     `ACCEPTED` -> `RUNNING` -> `SUCCEEDED` / `FAILED` / `BLOCKED`.
   - All state transitions are durably recorded and broadcast via SSE.
9. **No Faking Release C**:
   - Release B does NOT invoke the Batch Orchestrator or execute pipelines.
   - `PAUSE_BOOK` persists `PAUSE_REQUESTED` intent in `control_state.json`.
   - `RESUME_BOOK` clears pause intent.
   - `PRIORITIZE_BOOK` persists priority overrides in `control_state.json`.
   - `REPROCESS_STAGE` persists stage reprocess intent without running pipelines.
   - `DEQUEUE_BOOK` removes book from operational queue without deleting book sources or certified artifacts.
   - Real previous state is queried from current inventory, never defaulted to `"QUEUED"`.
10. **Human Authority & Tamper-Evident Integrity**:
    - Review decisions strictly require non-empty human operator identity (`decidedBy`/`reviewer`). Automated agents (`AUTOMATED_AGENT_IDENTIFIERS`) are rejected fail-closed.
    - Decisions on `POLICY_OR_RIGHTS` and `DOMAIN_AMBIGUITY` are strictly human; agents cannot authorize rights or publication.
    - `decisions.jsonl` and `command_audit.jsonl` implement SHA-256 tamper-evident hash chaining. Modifications to historical lines trigger an `IntegrityError` upon startup/read.
11. **Server-Side Risk Model**:
    - Risk levels are enforced server-side on `POST /api/ops/commands`:
      - **LOW** (`PRIORITIZE_BOOK`, `PAUSE_BOOK`, `RESUME_BOOK`): Single-action execution.
      - **MEDIUM** (`REPROCESS_STAGE`, `REJECT_REVIEW`, `REQUEST_CORRECTION`, `DEQUEUE_BOOK`): Requires non-empty `reason` and explicit `confirmation=true`.
      - **HIGH** (`POLICY_OR_RIGHTS` approval, broad stage invalidation): Requires non-empty `reason`, typed confirmation matching `bookId`, and human reviewer identity.
12. **Server-Sent Events (SSE) Semantics**:
    - SSE is strictly a reactive push mechanism; durable stores are the source of truth.
    - Monotonic `eventId` sequence within server process.
    - 100-event circular ring buffer.
    - Reconnection via `Last-Event-ID`: if ID is in buffer, replays missing events; if expired or server restarted, emits `snapshot_required` event prompting frontend to fetch `GET /api/ops/snapshot`.
    - Periodic `: keepalive\n\n` comments prevent socket timeouts.
    - Zero credentials or tokens are ever sent over SSE.
13. **Public Fail-Closed Total Barrier**:
    - In `mode="public"`: `/api/ops/*` routes are unregistered (`404 Not Found`).
    - Frontend routes `#/ops/*` are not registered; navigation omits Operations.
    - Public JavaScript never initiates `EventSource` or calls `/api/ops/*`.
    - Protected content (e.g. Animalidade raw data) remains strictly unexposed.

---

## 2. Schema Contracts & Data Interfaces

### 2.1 `schemas/ops-command.schema.json`
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://daemon.tools/schemas/ops-command.schema.json",
  "title": "Ops Command Contract",
  "description": "Canonical typed command contract for Daemon Tools operational control plane.",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "commandId",
    "commandType",
    "payload",
    "reason",
    "operatorId",
    "confirmation"
  ],
  "properties": {
    "commandId": {
      "type": "string",
      "pattern": "^CMD-[A-Za-z0-9_-]{8,32}$"
    },
    "commandType": {
      "type": "string",
      "enum": [
        "PRIORITIZE_BOOK",
        "PAUSE_BOOK",
        "RESUME_BOOK",
        "REPROCESS_STAGE",
        "DEQUEUE_BOOK",
        "APPROVE_REVIEW",
        "REJECT_REVIEW",
        "REQUEST_CORRECTION"
      ]
    },
    "bookId": {
      "type": "string",
      "minLength": 1
    },
    "reviewId": {
      "type": "string",
      "minLength": 1
    },
    "payload": {
      "type": "object"
    },
    "reason": {
      "type": "string"
    },
    "operatorId": {
      "type": "string",
      "minLength": 1
    },
    "confirmation": {
      "type": "object",
      "required": ["confirmed"],
      "properties": {
        "confirmed": { "type": "boolean" },
        "typedConfirmation": { "type": "string" }
      }
    },
    "submittedAt": {
      "type": "string",
      "format": "date-time"
    }
  }
}
```

### 2.2 Tamper-Evident Hash Chain Algorithm
For append-only logs (`decisions.jsonl`, `command_audit.jsonl`):
1. The genesis entry uses `prevHash = "0" * 64`.
2. Each subsequent entry receives the `entryHash` of the immediately preceding line as its `prevHash`.
3. The `entryHash` is computed deterministically:
   $$\text{entryHash} = \text{SHA-256}(\text{canonical\_json\_bytes}(\{\dots\text{record without entryHash}, \text{"prevHash"}: \text{prevHash}\}))$$
4. Any line addition, modification, or reordering invalidates the chain and causes `IntegrityError`.

---

## 3. Interfaces and File Map

| File | Action | Responsibility |
| :--- | :--- | :--- |
| `schemas/ops-command.schema.json` | Create | JSON Schema Draft 2020-12 contract for operational commands. |
| `scripts/ops/runtime_locator.py` | Create | Canonical runtime directory resolution delegating to `resolve_canonical_runtime_dir()`. |
| `scripts/ops/token_manager.py` | Create | High-entropy process token generation, fail-closed Windows `icacls` / POSIX `chmod 600` permissions, session cookie generation and verification. |
| `scripts/ops/hash_chain.py` | Create | SHA-256 tamper-evident chain calculation, appending, and full log verification utilities. |
| `scripts/ops/review_store.py` | Create | Durable review CRUD store (`reviews.json`), tamper-evident decision log (`decisions.jsonl`), in-process mutex locking, agent rejection. |
| `scripts/ops/command_store.py` | Create | Durable command state store (`commands.json`), control state (`control_state.json`), payload hashing, idempotency validation. |
| `scripts/ops/command_audit.py` | Create | Append-only tamper-evident command audit logger (`command_audit.jsonl`). |
| `scripts/ops/command_processor.py` | Create | Asynchronous command handler, 202 Accepted ingestion, transition worker loop, server-side risk validator, intent persistence for Release B. |
| `scripts/ops/event_broadcaster.py` | Create | In-memory SSE broadcaster, 100-event ring buffer, monotonic IDs, `Last-Event-ID` replay, `snapshot_required` fallback, keepalive comments. |
| `scripts/ops/ops_server.py` | Create | Loopback request dispatcher for `/api/ops/*`, same-origin cookie check, CLI Bearer token validation, Host/Origin validation, body limits. |
| `scripts/agents/preview_server.py` | Modify | Mounts `OpsRequestHandler` in `restricted_preview` mode, sets HttpOnly session cookie on preview entry, enforces strict 404 in `public` mode. |
| `docs/assets/site-ops.mjs` | Create | Frontend operational client (cookie-authenticated, zero token in JS, SSE lifecycle, snapshot fallback, command posting with risk ritual helpers). |
| `docs/assets/site-state.mjs` | Modify | Registers operational routes (`#/ops`, `#/ops/queue`, `#/ops/reviews`, `#/ops/review/:reviewId`) exclusively in restricted mode; redirects to `#/` in public mode. |
| `docs/assets/site-ui.mjs` | Modify | Renders operational dashboard, review queue, diff evidence viewer with safe DOM APIs (`textContent`), risk confirmation modals. |
| `docs/assets/styles.css` | Modify | Styles for operational badges, review diff tables, confirmation modals, SSE live status indicator. |
| `tests/ops/test_store_foundations.py` | Create | Tests for canonical runtime resolution, store initialization, and hash chaining. |
| `tests/ops/test_token_manager.py` | Create | Tests for token entropy, fail-closed ACL enforcement, session cookie derivation, and stale token cleanup. |
| `tests/ops/test_review_store.py` | Create | Tests for review lifecycle, tamper-evident decision logging, automated agent rejection, concurrent decision conflict prevention. |
| `tests/ops/test_command_store.py` | Create | Tests for durable idempotency, payload hash mismatch 409 conflict, crash recovery across restarts. |
| `tests/ops/test_command_processor.py` | Create | Tests for asynchronous lifecycle (ACCEPTED -> RUNNING -> SUCCEEDED), server-side risk verification, Release B intent persistence. |
| `tests/ops/test_event_broadcaster.py` | Create | Tests for monotonic IDs, ring buffer replay, snapshot fallback on overflow/stale ID, keepalive comments. |
| `tests/ops/test_ops_server_security.py` | Create | Tests for loopback binding, session cookie auth, CLI Bearer auth, Origin/Host validation, 404 barrier in public mode. |
| `tests/agents/test_preview_server_ops_barrier.py` | Create | Tests verifying preview server integration and fail-closed public mode isolation. |
| `tests/frontend/site-ops.test.mjs` | Create | Node tests for frontend ops client, SSE reconnect handling, snapshot fallback. |
| `tests/frontend/site-state.test.mjs` | Modify | Tests verifying operational routes active in restricted mode and strictly absent in public mode. |
| `tests/frontend/test_site_browser.py` | Modify | Playwright browser tests for operational dashboard, review resolution, risk confirmation modals, public mode absence. |

---

## 4. Implementation Tasks

### Task 1: Schemas, Runtime Locator & Store Foundations

**Files:**
- Create: `schemas/ops-command.schema.json`
- Create: `scripts/ops/runtime_locator.py`
- Create: `scripts/ops/hash_chain.py`
- Create: `tests/ops/test_store_foundations.py`

**Interfaces:**
```python
# scripts/ops/runtime_locator.py
def get_ops_runtime_dir(runtime_dir: Path | str | None = None) -> Path: ...
def get_ops_stores_dir(runtime_dir: Path | str | None = None) -> Path: ...

# scripts/ops/hash_chain.py
class IntegrityError(RuntimeError): ...

class HashChainLogger:
    def __init__(self, log_path: Path) -> None: ...
    def append_entry(self, record: dict[str, Any]) -> dict[str, Any]: ...
    def verify_integrity(self) -> tuple[bool, int, str]: ...
    def read_all_entries(self) -> list[dict[str, Any]]: ...
```

- [ ] **Step 1: Write failing test (`tests/ops/test_store_foundations.py`)**
  - Verify `get_ops_runtime_dir()` returns `<canonical .daemon_runtime>/ops`.
  - Verify `schemas/ops-command.schema.json` validates valid command and rejects missing `commandId` or unknown `commandType`.
  - Verify `HashChainLogger` calculates deterministic SHA-256 chain and raises `IntegrityError` if a historical line is modified.
- [ ] **Step 2: Run test and confirm RED**
  ```powershell
  python -m pytest tests/ops/test_store_foundations.py -v
  ```
- [ ] **Step 3: Implement minimal code**
  - Implement `schemas/ops-command.schema.json`.
  - Implement `scripts/ops/runtime_locator.py` importing `resolve_canonical_runtime_dir`.
  - Implement `scripts/ops/hash_chain.py` using `canonical_json_bytes` and `sha256_bytes`.
- [ ] **Step 4: Run test and confirm GREEN**
  ```powershell
  python -m pytest tests/ops/test_store_foundations.py -v
  ```
- [ ] **Step 5: Run focused regressions**
  ```powershell
  python -m pytest tests/ops/test_store_foundations.py -q
  ```
- [ ] **Step 6: Commit**
  ```powershell
  git add schemas/ops-command.schema.json scripts/ops/runtime_locator.py scripts/ops/hash_chain.py tests/ops/test_store_foundations.py
  git commit -m "feat(ops): implement ops command schema, canonical runtime locator, and hash chain foundations"
  ```

---

### Task 2: Ephemeral Token Manager & Session Cookie Security

**Files:**
- Create: `scripts/ops/token_manager.py`
- Create: `tests/ops/test_token_manager.py`

**Interfaces:**
```python
class TokenManager:
    def __init__(self, runtime_dir: Path | str | None = None) -> None: ...
    def initialize(self) -> str: ...
    def get_token(self) -> str | None: ...
    def create_session_cookie(self) -> str: ...
    def validate_session(self, cookie_header: str | None, auth_header: str | None) -> bool: ...
    def cleanup(self) -> None: ...
```

- [ ] **Step 1: Write failing test (`tests/ops/test_token_manager.py`)**
  - Test token entropy (at least 32 urlsafe bytes).
  - Test file permission restriction: on Windows, verifies `icacls` invocation; if permissions cannot be applied, `initialize()` raises `RuntimeError` (fail-closed).
  - Test session cookie generation and verification (`HttpOnly`, `SameSite=Strict`).
  - Test validation succeeds with valid session cookie OR valid `Bearer <token>`.
  - Test rejection of missing, empty, or forged credentials.
  - Test stale token rotation on process restart.
- [ ] **Step 2: Run test and confirm RED**
  ```powershell
  python -m pytest tests/ops/test_token_manager.py -v
  ```
- [ ] **Step 3: Implement minimal code (`scripts/ops/token_manager.py`)**
  - Use `secrets.token_urlsafe(32)`.
  - Implement Windows `icacls` configuration with strict error checking (fail-closed).
  - Derive HMAC session token for cookie validation.
  - Implement cleanup unlinking `ops_token`.
- [ ] **Step 4: Run test and confirm GREEN**
  ```powershell
  python -m pytest tests/ops/test_token_manager.py -v
  ```
- [ ] **Step 5: Run focused regressions**
  ```powershell
  python -m pytest tests/ops/test_token_manager.py tests/ops/test_store_foundations.py -q
  ```
- [ ] **Step 6: Commit**
  ```powershell
  git add scripts/ops/token_manager.py tests/ops/test_token_manager.py
  git commit -m "feat(ops): implement fail-closed token manager and same-origin session security"
  ```

---

### Task 3: Durable Review Store & Tamper-Evident Decision Log

**Files:**
- Create: `scripts/ops/review_store.py`
- Create: `tests/ops/test_review_store.py`

**Interfaces:**
```python
class DecisionValidationError(ValueError): ...
class ReviewConflictError(RuntimeError): ...

class ReviewStore:
    def __init__(self, stores_dir: Path | str | None = None) -> None: ...
    def create_review(self, record: dict[str, Any]) -> dict[str, Any]: ...
    def get_review(self, review_id: str) -> dict[str, Any] | None: ...
    def list_reviews(self, status: str | None = None, category: str | None = None) -> list[dict[str, Any]]: ...
    def record_decision(self, decision: dict[str, Any]) -> dict[str, Any]: ...
```

- [ ] **Step 1: Write failing test (`tests/ops/test_review_store.py`)**
  - Test creation of review item with `category` in `{"DOMAIN_AMBIGUITY", "POLICY_OR_RIGHTS", "TECHNICAL"}`.
  - Test human decision records successfully into `reviews.json` (atomic write) and `decisions.jsonl` (hash-chained).
  - Test automated agent identities (`AUTOMATED_AGENT_IDENTIFIERS`) fail closed with `DecisionValidationError`.
  - Test missing/empty `decidedBy` fails closed with `DecisionValidationError`.
  - Test concurrent resolution attempts on the same review: exactly one succeeds, second raises `ReviewConflictError`.
  - Test `POLICY_OR_RIGHTS` review strictly requires human reviewer and non-empty justification.
- [ ] **Step 2: Run test and confirm RED**
  ```powershell
  python -m pytest tests/ops/test_review_store.py -v
  ```
- [ ] **Step 3: Implement minimal code (`scripts/ops/review_store.py`)**
  - Integrate `write_atomic` and `HashChainLogger`.
  - Import `AUTOMATED_AGENT_IDENTIFIERS` from `scripts.agents.pilot_review`.
  - Implement thread-safe file lock on `reviews.json` mutations.
- [ ] **Step 4: Run test and confirm GREEN**
  ```powershell
  python -m pytest tests/ops/test_review_store.py -v
  ```
- [ ] **Step 5: Run focused regressions**
  ```powershell
  python -m pytest tests/ops/test_review_store.py tests/ops/test_token_manager.py -q
  ```
- [ ] **Step 6: Commit**
  ```powershell
  git add scripts/ops/review_store.py tests/ops/test_review_store.py
  git commit -m "feat(ops): implement durable review store and tamper-evident decision log"
  ```

---

### Task 4: Durable Command Store & Tamper-Evident Audit Log

**Files:**
- Create: `scripts/ops/command_store.py`
- Create: `scripts/ops/command_audit.py`
- Create: `tests/ops/test_command_store.py`

**Interfaces:**
```python
# scripts/ops/command_store.py
class CommandConflictError(RuntimeError): ...

class CommandStore:
    def __init__(self, stores_dir: Path | str | None = None) -> None: ...
    def save_command_intent(self, cmd_payload: dict[str, Any]) -> tuple[dict[str, Any], bool]: ...
    def update_command_status(self, command_id: str, status: str, result: dict[str, Any] | None = None, error: str | None = None) -> dict[str, Any]: ...
    def get_command(self, command_id: str) -> dict[str, Any] | None: ...
    def get_control_state(self) -> dict[str, Any]: ...
    def set_control_override(self, key: str, value: Any) -> None: ...

# scripts/ops/command_audit.py
class CommandAuditLog:
    def __init__(self, stores_dir: Path | str | None = None) -> None: ...
    def log_action(self, entry: dict[str, Any]) -> dict[str, Any]: ...
    def verify_audit_chain(self) -> bool: ...
```

- [ ] **Step 1: Write failing test (`tests/ops/test_command_store.py`)**
  - Test command persistence in `commands.json`.
  - Test idempotency: resubmission with same `commandId` and same payload returns existing command with `is_duplicate=True`.
  - Test conflict: resubmission with same `commandId` and different payload raises `CommandConflictError`.
  - Test crash recovery: save command, re-instantiate `CommandStore`, verify command and control state are fully recovered.
  - Test audit log: actions appended to `command_audit.jsonl` with valid tamper-evident hash chain.
- [ ] **Step 2: Run test and confirm RED**
  ```powershell
  python -m pytest tests/ops/test_command_store.py -v
  ```
- [ ] **Step 3: Implement minimal code**
  - Implement `CommandStore` computing canonical payload hash (`canonical_json_bytes` + `sha256_bytes`).
  - Implement `CommandAuditLog` delegating to `HashChainLogger`.
- [ ] **Step 4: Run test and confirm GREEN**
  ```powershell
  python -m pytest tests/ops/test_command_store.py -v
  ```
- [ ] **Step 5: Run focused regressions**
  ```powershell
  python -m pytest tests/ops/test_command_store.py tests/ops/test_review_store.py -q
  ```
- [ ] **Step 6: Commit**
  ```powershell
  git add scripts/ops/command_store.py scripts/ops/command_audit.py tests/ops/test_command_store.py
  git commit -m "feat(ops): implement durable command store, idempotency validator, and audit log"
  ```

---

### Task 5: Asynchronous Command Processor with Durable Idempotency & Server-Side Risk Model

**Files:**
- Create: `scripts/ops/command_processor.py`
- Create: `tests/ops/test_command_processor.py`

**Interfaces:**
```python
class RiskValidationError(ValueError): ...

class CommandProcessor:
    def __init__(
        self,
        command_store: CommandStore | None = None,
        audit_log: CommandAuditLog | None = None,
        review_store: ReviewStore | None = None,
    ) -> None: ...
    def submit_command(self, cmd_payload: dict[str, Any]) -> tuple[dict[str, Any], int]: ...
    def process_pending_commands(self) -> int: ...
    def get_command_status(self, command_id: str) -> dict[str, Any] | None: ...
```

- [ ] **Step 1: Write failing test (`tests/ops/test_command_processor.py`)**
  - Test `submit_command` returns HTTP status `202 Accepted` and status `ACCEPTED` without executing handlers synchronously.
  - Test server-side risk validation:
    - `PRIORITIZE_BOOK` (LOW): accepted with simple submission.
    - `REPROCESS_STAGE` (MEDIUM): rejected if `reason` is empty or `confirmation.confirmed` is false.
    - `APPROVE_REVIEW` for `POLICY_OR_RIGHTS` (HIGH): rejected if typed confirmation does not match `bookId`.
  - Test asynchronous worker loop: `process_pending_commands()` transitions `ACCEPTED` -> `RUNNING` -> `SUCCEEDED`.
  - Test Release B intent persistence: `PAUSE_BOOK` writes `PAUSE_REQUESTED` into control state without faking execution.
  - Test `APPROVE_REVIEW` executes human decision in `ReviewStore` with explicit operator identity.
- [ ] **Step 2: Run test and confirm RED**
  ```powershell
  python -m pytest tests/ops/test_command_processor.py -v
  ```
- [ ] **Step 3: Implement minimal code (`scripts/ops/command_processor.py`)**
  - Validate against `schemas/ops-command.schema.json`.
  - Enforce server-side risk verification rules.
  - Record audit log on `ACCEPTED` and on terminal states (`SUCCEEDED`/`FAILED`).
  - Implement handler dispatching for Release B operational intents.
- [ ] **Step 4: Run test and confirm GREEN**
  ```powershell
  python -m pytest tests/ops/test_command_processor.py -v
  ```
- [ ] **Step 5: Run focused regressions**
  ```powershell
  python -m pytest tests/ops/test_command_processor.py tests/ops/test_command_store.py -q
  ```
- [ ] **Step 6: Commit**
  ```powershell
  git add scripts/ops/command_processor.py tests/ops/test_command_processor.py
  git commit -m "feat(ops): implement asynchronous command processor with server-side risk validation"
  ```

---

### Task 6: Server-Sent Events Broadcaster with Ring Buffer & Snapshot Fallback

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
    def format_keepalive(self) -> str: ...
```

- [ ] **Step 1: Write failing test (`tests/ops/test_event_broadcaster.py`)**
  - Test monotonic event IDs across publishes.
  - Test replay via `Last-Event-ID` when within circular buffer (100 items).
  - Test snapshot fallback: returns `needs_snapshot=True` if `Last-Event-ID` is older than oldest retained item or 0 on restart.
  - Test SSE wire formatting (`id: ...\nevent: ...\ndata: ...\n\n`).
  - Test keepalive comment formatting (`: keepalive\n\n`).
  - Test that secret tokens never appear in event payloads.
- [ ] **Step 2: Run test and confirm RED**
  ```powershell
  python -m pytest tests/ops/test_event_broadcaster.py -v
  ```
- [ ] **Step 3: Implement minimal code (`scripts/ops/event_broadcaster.py`)**
  - Thread-safe deque with maxlen=100.
  - Snapshot fallback detection.
  - JSON serialization without whitespace.
- [ ] **Step 4: Run test and confirm GREEN**
  ```powershell
  python -m pytest tests/ops/test_event_broadcaster.py -v
  ```
- [ ] **Step 5: Run focused regressions**
  ```powershell
  python -m pytest tests/ops/test_event_broadcaster.py -q
  ```
- [ ] **Step 6: Commit**
  ```powershell
  git add scripts/ops/event_broadcaster.py tests/ops/test_event_broadcaster.py
  git commit -m "feat(ops): implement SSE broadcaster with ring buffer replay and snapshot fallback"
  ```

---

### Task 7: Ops Request Handler & Preview Server Integration with Public Fail-Closed Barrier

**Files:**
- Create: `scripts/ops/ops_server.py`
- Modify: `scripts/agents/preview_server.py`
- Create: `tests/ops/test_ops_server_security.py`
- Create: `tests/agents/test_preview_server_ops_barrier.py`

**Interfaces:**
```python
# scripts/ops/ops_server.py
class OpsRequestHandler:
    def __init__(
        self,
        token_manager: TokenManager,
        command_processor: CommandProcessor,
        broadcaster: EventBroadcaster,
        allowed_hosts: set[str] | None = None,
    ) -> None: ...
    def handle_request(
        self,
        method: str,
        path: str,
        headers: dict[str, str],
        client_address: tuple[str, int],
        body: bytes,
    ) -> tuple[int, dict[str, str], bytes | Iterator[bytes]]: ...
```

- [ ] **Step 1: Write failing tests**
  - `tests/ops/test_ops_server_security.py`:
    - Non-loopback client IP (e.g. `192.168.1.50`) -> `403 Forbidden`.
    - Host header spoofing / DNS rebinding (Host: `malicious.com`) -> `403 Forbidden`.
    - Missing session cookie and missing Bearer header -> `401 Unauthorized`.
    - Valid session cookie -> `202 Accepted` for `POST /api/ops/commands`.
    - Conflicting payload with existing `commandId` -> `409 Conflict`.
    - Large body (> 64KB) -> `413 Payload Too Large`.
  - `tests/agents/test_preview_server_ops_barrier.py`:
    - Start `PreviewServer` in `mode="restricted_preview"`: `/api/ops/snapshot` returns 200/401, sets session cookie on `/`.
    - Start `PreviewServer` in `mode="public"`: `/api/ops/commands`, `/api/ops/events`, `/api/ops/snapshot` strictly return `404 Not Found`.
- [ ] **Step 2: Run tests and confirm RED**
  ```powershell
  python -m pytest tests/ops/test_ops_server_security.py tests/agents/test_preview_server_ops_barrier.py -v
  ```
- [ ] **Step 3: Implement minimal code**
  - Implement `OpsRequestHandler` with loopback check, Host/Origin validation, body size capping, and same-origin cookie parsing.
  - Mount `OpsRequestHandler` inside `PreviewServer.do_GET`, `do_POST` when `self.server.mode == "restricted_preview"`.
  - In `PreviewServer`, issue `Set-Cookie: daemon_ops_session=...; HttpOnly; SameSite=Strict; Path=/api/ops` on restricted preview requests.
  - Enforce strict `404 Not Found` for any `/api/ops/*` path in `mode="public"`.
- [ ] **Step 4: Run tests and confirm GREEN**
  ```powershell
  python -m pytest tests/ops/test_ops_server_security.py tests/agents/test_preview_server_ops_barrier.py -v
  ```
- [ ] **Step 5: Run focused regressions**
  ```powershell
  python -m pytest tests/ops -q
  python -m pytest tests/agents/test_preview_server*.py -q
  ```
- [ ] **Step 6: Commit**
  ```powershell
  git add scripts/ops/ops_server.py scripts/agents/preview_server.py tests/ops/test_ops_server_security.py tests/agents/test_preview_server_ops_barrier.py
  git commit -m "feat(ops): mount secure ops request handler in preview server with public fail-closed barrier"
  ```

---

### Task 8: Frontend Operational Client, Views & Risk-Proportional Confirmation Modals

**Files:**
- Create: `docs/assets/site-ops.mjs`
- Modify: `docs/assets/site-state.mjs`
- Modify: `docs/assets/site-ui.mjs`
- Modify: `docs/assets/styles.css`
- Create: `tests/frontend/site-ops.test.mjs`
- Modify: `tests/frontend/site-state.test.mjs`

**Interfaces:**
```javascript
// docs/assets/site-ops.mjs
export class OpsClient {
  constructor({ baseUrl = '' } = {}) { ... }
  async fetchSnapshot() { ... }
  connectEvents({ onEvent, onSnapshotRequired }) { ... }
  async submitCommand({ commandType, bookId, reviewId, payload, reason, operatorId, confirmation }) { ... }
}
```

- [ ] **Step 1: Write failing frontend unit tests**
  - `tests/frontend/site-state.test.mjs`:
    - In `mode === 'restricted_preview'`: routes `#/ops`, `#/ops/queue`, `#/ops/reviews`, `#/ops/review/:reviewId` resolve correctly.
    - In `mode === 'public'`: `#/ops` routes resolve to fallback `#/` and are excluded from navigation.
  - `tests/frontend/site-ops.test.mjs`:
    - `OpsClient` sends same-origin credentials (`credentials: 'same-origin'`).
    - Does NOT store token in `localStorage`, `sessionStorage`, or window.
    - Listens for `snapshot_required` SSE event and triggers full snapshot reload.
- [ ] **Step 2: Run tests and confirm RED**
  ```powershell
  node --test tests/frontend/*.test.mjs
  ```
- [ ] **Step 3: Implement minimal frontend code**
  - Create `docs/assets/site-ops.mjs`.
  - Update `docs/assets/site-state.mjs` to register ops routes only in restricted mode.
  - Update `docs/assets/site-ui.mjs` to render operational dashboard, review queue, diff viewer with `textContent`, and risk-proportional confirmation modals (low, medium, high).
  - Update `docs/assets/styles.css` with operational dashboard and modal styles.
- [ ] **Step 4: Run tests and confirm GREEN**
  ```powershell
  node --test tests/frontend/*.test.mjs
  node --check docs/assets/app.js
  node --check docs/assets/site-ui.mjs
  ```
- [ ] **Step 5: Commit**
  ```powershell
  git add docs/assets/site-ops.mjs docs/assets/site-state.mjs docs/assets/site-ui.mjs docs/assets/styles.css tests/frontend/site-ops.test.mjs tests/frontend/site-state.test.mjs
  git commit -m "feat(frontend): implement operational client views and risk-proportional confirmation modals"
  ```

---

### Task 9: Public Mode Isolation, Full Regression & End-to-End Browser Verification

**Files:**
- Modify: `tests/frontend/test_site_browser.py`
- Create: `tests/ops/test_ops_e2e.py`

**Interfaces:**
- Comprehensive Playwright tests verifying:
  - Restricted mode dashboard loads, displays 281 total books, live counters.
  - Review queue opens, shows discrepancies, submits approval via modal.
  - F5 reload restores state from snapshot cleanly.
  - Public mode: navigating to `#/ops` immediately redirects to `#/`; zero Operations menu items visible; direct `fetch('/api/ops/snapshot')` returns 404.
  - Full project regression suites.

- [ ] **Step 1: Write E2E browser tests in `tests/frontend/test_site_browser.py`**
  ```python
  def test_ops_panel_and_review_resolution_restricted(page, site_url):
      # Tests restricted preview ops panel and review resolution
      ...

  def test_ops_panel_strictly_blocked_in_public_mode(page, public_site_url):
      # Asserts #/ops redirects to #/ and /api/ops/* returns 404
      ...
  ```
- [ ] **Step 2: Run tests and confirm GREEN**
  ```powershell
  python -m pytest tests/frontend/test_site_browser.py -q
  python -m pytest tests/ops/test_ops_e2e.py -v
  ```
- [ ] **Step 3: Run full automated regression suite**
  ```powershell
  python -m pytest tests/ops -q
  python -m pytest tests/agents -q
  python -m pytest tests/frontend/test_site_browser.py -q
  node --test tests/frontend/*.test.mjs
  python -m pytest -q
  python scripts/validate_data.py
  python scripts/check_book_coverage.py
  node --check docs/assets/app.js
  node --check docs/assets/site-ui.mjs
  ```
- [ ] **Step 4: Commit**
  ```powershell
  git add tests/frontend/test_site_browser.py tests/ops/test_ops_e2e.py
  git commit -m "test(ops): verify complete ops controller and public isolation E2E"
  ```

---

## 5. Required Test Matrix

The following test matrix must be fully covered by automated unit and integration tests:

| Domain | Test Identifier | Expected Behavior |
| :--- | :--- | :--- |
| **TOKEN** | `test_token_entropy` | Generates >= 32 urlsafe characters with high cryptographic entropy. |
| **TOKEN** | `test_token_acl_enforcement` | Configures owner-only permissions via `icacls` (Windows) or `chmod 600` (POSIX). |
| **TOKEN** | `test_token_acl_failure_aborts` | Failure to apply or verify ACL raises exception and halts Ops Controller (fail-closed). |
| **TOKEN** | `test_token_stale_rotation` | Old token file is replaced with a fresh token upon server restart. |
| **TOKEN** | `test_no_browser_token_exposure` | Token string never appears in HTML, DOM, client scripts, localStorage, or query params. |
| **AUTH** | `test_auth_missing_session` | Request to `/api/ops/*` without session cookie or Bearer header returns 401. |
| **AUTH** | `test_auth_invalid_session` | Forged or expired session cookie returns 401. |
| **AUTH** | `test_auth_invalid_origin` | Cross-origin request with mismatched `Origin` header returns 403 Forbidden. |
| **AUTH** | `test_auth_invalid_host` | Request with external/unknown `Host` header returns 403 Forbidden. |
| **AUTH** | `test_auth_non_loopback` | Connection from non-loopback IP (not 127.0.0.1 or ::1) returns 403 Forbidden. |
| **AUTH** | `test_auth_public_mode_404` | Any `/api/ops/*` call when server is in `public` mode returns 404 Not Found. |
| **IDEMPOTENCY** | `test_idempotency_same_payload` | Submitting existing `commandId` with identical payload returns cached command without side effects. |
| **IDEMPOTENCY** | `test_idempotency_conflicting_payload` | Submitting existing `commandId` with different payload returns 409 Conflict. |
| **IDEMPOTENCY** | `test_idempotency_survives_restart` | Command deduplication remains strictly effective after stopping and restarting the process. |
| **COMMAND** | `test_command_lifecycle_transitions` | State moves `ACCEPTED` -> `RUNNING` -> `SUCCEEDED` / `FAILED` with persisted transitions. |
| **COMMAND** | `test_command_schema_validation` | Malformed command payloads or invalid enum values fail closed with 400 Bad Request. |
| **AUDIT** | `test_audit_append_only_chain` | Every command appends to `command_audit.jsonl` with correct previous hash linkage. |
| **AUDIT** | `test_audit_tamper_detection` | Tampering with any historical line in audit log raises `IntegrityError` on startup. |
| **AUDIT** | `test_audit_no_token_leakage` | Session cookies and tokens are scrubbed and never recorded in audit payloads. |
| **REVIEWS** | `test_review_human_decision_only` | Review approval succeeds with valid human operator ID. |
| **REVIEWS** | `test_review_automated_agent_rejected` | Decision bearing agent name from `AUTOMATED_AGENT_IDENTIFIERS` is rejected fail-closed. |
| **REVIEWS** | `test_review_double_decision_prevented` | Second concurrent decision on same review ID returns conflict; exactly one decision recorded. |
| **REVIEWS** | `test_review_rights_requires_justification`| `POLICY_OR_RIGHTS` review strictly requires non-empty justification and typed confirmation. |
| **SSE** | `test_sse_monotonic_ids` | Event IDs strictly increment as integer sequence during process lifetime. |
| **SSE** | `test_sse_buffer_replay` | Reconnection with valid `Last-Event-ID` within buffer replays missed events in order. |
| **SSE** | `test_sse_snapshot_required_on_overflow`| Stale `Last-Event-ID` beyond ring buffer emits `snapshot_required` event. |
| **SSE** | `test_sse_keepalive_comments` | Broadcaster emits `: keepalive\n\n` comments to prevent connection drops. |
| **SSE** | `test_sse_no_secrets` | Stream events contain zero authentication tokens or private session cookies. |
| **RISK** | `test_risk_low_command` | `PAUSE_BOOK` executes with basic valid command payload. |
| **RISK** | `test_risk_medium_missing_reason` | `REPROCESS_STAGE` without reason fails with 400 Bad Request. |
| **RISK** | `test_risk_high_missing_typed_confirm` | Rights modification without exact typed `bookId` fails with 400 Bad Request. |
| **PUBLIC** | `test_public_routes_unregistered` | Router does not recognize `#/ops/*` routes in public mode, redirecting to `#/`. |
| **PUBLIC** | `test_public_ui_omits_ops` | Public navigation bar and dashboard render zero operational controls or review links. |
| **RESTART** | `test_restart_state_reconstruction` | After server crash, active intents, reviews, decisions, and audit history reload fully intact. |

---

## 6. Verification Plan & Local Acceptance

### 6.1 Automated CI/Local Test Commands
All commands below must execute cleanly against synthetic test fixtures:
```powershell
# 1. Ops Unit and Security Test Suites
python -m pytest tests/ops -q

# 2. Agent and Preview Pipeline Suites
python -m pytest tests/agents -q

# 3. Frontend Playwright Browser Tests
python -m pytest tests/frontend/test_site_browser.py -q

# 4. Frontend Node Test Suites
node --test tests/frontend/*.test.mjs

# 5. Full Repository Test Suite
python -m pytest -q

# 6. Data Integrity & Book Coverage Gates
python scripts/validate_data.py
python scripts/check_book_coverage.py

# 7. JavaScript Syntax & ESM Validation
node --check docs/assets/app.js
node --check docs/assets/site-ui.mjs
node --check docs/assets/site-ops.mjs
```

### 6.2 Local Acceptance Protocol (Isolated Manual Verification)
Executed separately using the local development runtime:
1. Start `PreviewServer` in restricted mode:
   ```powershell
   python scripts/agents/preview_server.py --mode restricted_preview --port 8080
   ```
2. Navigate to `http://127.0.0.1:8080/#/ops`:
   - Verify 7 global counters are displayed (`Total Catalogado: 281`, etc.).
   - Verify session cookie `daemon_ops_session` is present with `HttpOnly; SameSite=Strict`.
   - Verify browser console and `localStorage` contain zero token strings.
3. Submit a `PauseBook` command via UI:
   - Verify optimistic card update.
   - Verify `202 Accepted` response in Network tab.
   - Verify SSE receives `command.updated` event.
4. Navigate to `http://127.0.0.1:8080/#/ops/reviews`:
   - Open pending review item.
   - Attempt approval with agent name -> verify rejected.
   - Approve with human name and justification -> verify item moves to `RESOLVED` in UI and `decisions.jsonl`.
5. Start `PreviewServer` in public mode:
   ```powershell
   python scripts/agents/preview_server.py --mode public --port 8081
   ```
6. Verify public isolation:
   - Navigating to `http://127.0.0.1:8081/#/ops` immediately redirects to `#/`.
   - `curl http://127.0.0.1:8081/api/ops/snapshot` returns `404 Not Found`.
