# Scale-Out Release A — Acervo 281 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the Daemon Tools catalog and site projection to represent all 281 cataloged books in the restricted preview (`mode=restricted_preview`) with responsive cards, dual-axis filters, sorting, and dedicated book detail pages (`#/book/:bookId`) featuring the 7-stage pipeline stepper and safe unworked state, while guaranteeing strict fail-closed exclusion in public mode (`mode=public`) without requiring the complete Batch Orchestrator.

**Architecture:** A lightweight, deterministic archive inventory loader (`ArchiveInventoryLoader`) enforces the project's 5-layer separation of authority:
1. **Inventory Authority**: `data/index/sources.json` is the sole canonical inventory authority for the 281 books.
2. **Rights Authority**: Rights fields in `data/index/sources.json` are authoritative, with strict fail-closed fallback (`rightsStatus = UNKNOWN`, `publicationMode = NOT_PUBLIC`). Operational overlays are strictly prohibited from modifying or escalating rights.
3. **Operational Status Authority**: Persisted jobs in `JobStore` (`scripts/agents/job_store.py`) and certified runtime jobs (`.daemon_runtime/jobs/`) are the sole authority for pipeline lifecycle status (`pipelineStatus`) and stage progression (`currentStage`, `stages`). The presence of entity files never implies `READY_FOR_HUMAN_APPROVAL` or `DONE`.
4. **Certified Content Authority**: Certified artifact bundles (`.daemon_runtime/bundles/accepted/`) provide validated entities and relations for restricted preview. The certified pilot baseline for *Animalidade* contains exactly 56 domain entities (`power_magic: 20`, `character_option: 19`, `creature_npc: 17`) approved via `DEC-ANIM-001-ENTITIES-01`. Legacy uncertified files (e.g. 36 records in `data/entities/` from 04/09/2026) are never used as a certified baseline.
5. **Frontend Projection**: `FrontendProjector` creates derived, read-only static views (`catalog.json`, `search-index.json`, `books/<bookId>.json`) strictly enforcing public policy. Restricted content never enters the main worktree (`docs/` or versioned directories).

**Tech Stack:** Python 3.10+, pytest, standard library `http.server`, vanilla ES modules (`.mjs`), HTML5/CSS3, Node.js test runner (`node --test`), Playwright browser test harness (`pytest tests/frontend/test_site_browser.py`).

**Spec:** `docs/superpowers/specs/2026-09-14-scale-out-acervo-batch-ops-design.md`, commit `117b626cc1bb049f6beeb6498dfa5b7ea511e765`.

---

## Global Constraints

- **PROCESSADO != PUBLICÁVEL**: Technical pipeline completion does not authorize public disclosure.
- `restricted_preview` and `public` are runtime projector execution modes (`mode=restricted_preview` / `mode=public`), never to be confused with canonical `publicationMode`.
- **Fail-Closed Public Projection**: In `mode=public`, any book with `publicationMode == "NOT_PUBLIC"` or `rightsStatus == "UNKNOWN"` is strictly omitted from `catalog.json`, `search-index.json`, and `books/<bookId>.json`. Zero restricted metadata or content leaks to public outputs.
- **RESTRICTED_CONTENT_NEVER_ENTERS_MAIN_WORKTREE**: Restricted books (including *Animalidade*) and untracked previews are never written to `docs/` or versioned git directories. Runtime artifacts are accessed read-only in `mode=restricted_preview`.
- **Separation of Authorities**:
  - `data/index/sources.json` = Sole authority for catalog inventory (verified: `count: 281`).
  - Canonical rights contract = Sole authority for legal governance (`rightsStatus`, `publicationMode`).
  - `JobStore` / certified runtime = Sole authority for operational lifecycle (`pipelineStatus`, `currentStage`, `stages`).
  - Accepted runtime bundles = Sole authority for certified domain entities and relations.
  - Frontend projection = Pure derived view; never a canonical store.
- **No Inferred Pipeline Status from Entities**: Presence of entity or text files never authorizes concluding `READY_FOR_HUMAN_APPROVAL`, `DONE`, `QA PASS`, or `Relations PASS`. Unworked books with no certified job record strictly remain `pipelineStatus = "WAITING"`, `currentStage = null`, rendering all 7 stepper stages as `pending`.
- **Zero Provenance Invention**: Missing or unverified `source` provenance in relation records is never defaulted to `animalidade` or any other book. Relations missing provenance are rejected fail-closed.
- **Certified Animalidade Baseline**: The certified pilot baseline for Animalidade consists of exactly 56 entities (`power_magic: 20`, `character_option: 19`, `creature_npc: 17`) located in `.daemon_runtime/bundles/accepted/RB-ANIM-ENTITIES-att1-50691836/artifacts/entities.json`, with operational status tracked in `JOB-ANIM-001.json` (`pipelineStatus: RUNNING`, `currentStage: relations`). The 36 records in `data/entities/` represent a legacy catalog export from 04/09/2026 and are not the certified pilot baseline.
- **Fail-Closed Read Operations**: Malformed or corrupt job files or entity artifacts trigger explicit typed errors (`ArchiveInventoryError`, `ProcessedStateReadError`). Reading errors are never silently caught with `except Exception: continue/pass` nor downgraded to unworked books.
- **Stage Stepper Contract**:
  - `pipelineStatus = "WAITING"` or `currentStage = null`: 7 stages `pending`.
  - `pipelineStatus = "RUNNING"`: stages preceding `currentStage` are `done`, `currentStage` is `active`, subsequent stages are `pending`.
  - `pipelineStatus = "READY_FOR_HUMAN_APPROVAL"`: all 7 pipeline stages are `done` (technical stages complete; human decision pending outside stepper).
  - `pipelineStatus = "DONE"`: all 7 stages are `done`.
  - `pipelineStatus = "BLOCKED"` or `"NEEDS_HUMAN_REVIEW"`: stages preceding `currentStage` are `done`, `currentStage` is `blocked`/`review`, subsequent stages are `pending`.
  - Stages strictly follow: `Source` -> `Extraction` -> `Editorial` -> `Entities` -> `Relations` -> `Frontend` -> `QA`.
- **HTML Injection Safety**: Frontend rendering uses secure text/attribute injection and exported `escapeHtml` helpers. Direct interpolation of raw user or book metadata into HTML strings without escaping is strictly forbidden.

---

## Interfaces and File Map

| File | Action | Responsibility |
| :--- | :--- | :--- |
| `scripts/agents/archive_inventory_loader.py` | Create | Loads 281 sources from `data/index/sources.json`, integrates operational status from `JobStore` / certified runtime without rights escalation, enforces fail-closed error handling, and constructs canonical `BookInventoryRecord` inputs. |
| `scripts/agents/frontend_projector.py` | Modify | Extends `catalog.json` book entries with dual-axis operational metadata (`pipelineStatus`, `rightsStatus`, `publicationMode`, `currentStage`, `entityCount`, `pageCount`, `categoryHints`, `sizeBytes`) while preserving deterministic projectionId and contract validation. |
| `scripts/agents/site_view_model.py` | Modify | Updates catalog book schema validation in `validate_projection` to enforce canonical `rightsStatus` and operational fields on catalog books. |
| `scripts/agents/frontend_policy.py` | Modify | Preserves strict fail-closed filtering; ensures default unworked books (`UNKNOWN` / `NOT_PUBLIC`) and partial publication modes are strictly governed in `mode=public`. |
| `docs/assets/site-model.mjs` | Modify | Ingests extended catalog metadata and exposes helper lookup methods (`getBookMetadata(bookId)`). |
| `docs/assets/site-search.mjs` | Modify | Adds catalog filtering by `pipelineStatus`, `rightsStatus`, `publicationMode`, and `categoryHints`. |
| `docs/assets/site-state.mjs` | Modify | Manages archive catalog route parameters, active dual-axis filters (`bookFilters`), and sorting preferences with immutable update helper `setBookFilters`. |
| `docs/assets/site-ui.mjs` | Modify | Implements responsive 281-book grid (`renderBooksView`), card rendering (`createBookCard`), HTML escaping (`escapeHtml`), stage stepper logic (`getStageStates`), and book detail view (`renderBookDetailHtml`, `renderBookDetailView`). |
| `docs/assets/styles.css` | Modify | Styles for book cards (`.site-book-card`), dual-axis badges (`.site-badge-pipeline`, `.site-badge-rights`, `.site-badge-pub`), 7-stage stepper (`.pending`, `.active`, `.done`, `.blocked`), and responsive grid layout. |
| `tests/agents/test_archive_inventory_loader.py` | Create | Unit tests for `ArchiveInventoryLoader` verifying 281 books loading, operational authority integration, rights overlay rejection, zero provenance invention, fail-closed on corrupt artifacts, and unworked `currentStage=None`. |
| `tests/agents/test_frontend_projector_archive.py` | Create | Unit tests verifying dual-axis projection in `restricted_preview` and contract validation. |
| `tests/agents/test_frontend_policy_archive.py` | Create | Controlled synthetic fixture matrix tests validating semantic public exposure (`UNKNOWN+NOT_PUBLIC`, `PRIVATE+NOT_PUBLIC`, `PUBLIC_DOMAIN+FULL_TEXT`, `AUTHORIZED+FULL_TEXT`, `METADATA_ONLY+METADATA_ONLY` content exclusion, `SUMMARY_AND_METADATA`). |
| `tests/frontend/site-model.test.mjs` | Modify | Node test runner tests for extended catalog metadata and caching. |
| `tests/frontend/site-search.test.mjs` | Modify | Node test runner tests for dual-axis filtering and sorting. |
| `tests/frontend/site-state.test.mjs` | Modify | Node test runner tests for `bookFilters` initialization and `setBookFilters` immutable state updates. |
| `tests/frontend/site-ui-books.test.mjs` | Create | Node test runner tests verifying `.site-book-card` container, dual-axis card badges, and HTML escaping against arbitrary markup injection. |
| `tests/frontend/site-ui-book-detail.test.mjs` | Create | Node test runner tests verifying `getStageStates` and `renderBookDetailHtml` across stepper states (all pending for unworked, all done for READY_FOR_HUMAN_APPROVAL and DONE, active for RUNNING), empty state, and metadata visibility. |
| `tests/frontend/test_site_browser.py` | Modify | Playwright browser tests for `#/books` (281 cards, filters, search), `#/book/:bookId` (stepper, empty state, strict assertions), and explicit public fail-closed exclusion test (`mode=public`). |
| `tests/frontend/conftest.py` | Modify | Conftest fixtures supporting multi-book catalog and isolated public serving tests. |

---

## Tasks

### Task 1: Archive Inventory Loader & Operational Authority (`scripts/agents/archive_inventory_loader.py`)

**Files:**
- Create: `scripts/agents/archive_inventory_loader.py`
- Create: `tests/agents/test_archive_inventory_loader.py`

**Interfaces:**
```python
class ArchiveInventoryError(RuntimeError):
    """Base error for archive inventory operations."""
    pass

class ProcessedStateReadError(ArchiveInventoryError):
    """Raised when certified operational state or artifact reading fails or artifact is corrupt."""
    pass

def load_certified_pilot_artifacts(runtime_dir: Path | str | None = None) -> dict[str, dict[str, Any]]: ...

class ArchiveInventoryLoader:
    def __init__(self, sources_path: Path | str | None = None, jobs_dir: Path | str | None = None, runtime_dir: Path | str | None = None) -> None: ...
    def load_inventory(self, operational_overlay: dict[str, dict[str, Any]] | None = None) -> list[dict[str, Any]]: ...
    def get_book_by_id(self, book_id: str, operational_overlay: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]: ...
```

- [ ] **Step 1: Write failing test**
Create `tests/agents/test_archive_inventory_loader.py`:
```python
import json
from pathlib import Path
import pytest
from scripts.agents.archive_inventory_loader import (
    ArchiveInventoryLoader,
    ArchiveInventoryError,
    ProcessedStateReadError,
    load_certified_pilot_artifacts,
)

def test_archive_inventory_loader_loads_281_books_unworked_by_default():
    loader = ArchiveInventoryLoader()
    books = loader.load_inventory()
    assert len(books) == 281
    # Check default fields of an unworked book
    sample = next(b for b in books if b["bookId"] == "4killers")
    assert sample["title"] == "4killers"
    assert sample["pipelineStatus"] == "WAITING"
    assert sample["rightsStatus"] == "UNKNOWN"
    assert sample["publicationMode"] == "NOT_PUBLIC"
    assert sample["entities"] == []
    assert sample["relations"] == []
    assert sample["currentStage"] is None
    assert sample["pageCount"] == 8

def test_archive_inventory_loader_integrates_operational_job_store():
    loader = ArchiveInventoryLoader()
    # Certified operational state from JobStore
    certified_job = {
        "animalidade": {
            "bookId": "animalidade",
            "pipelineStatus": "RUNNING",
            "currentStage": "relations",
            "entities": [{"id": f"ent-{i}", "name": f"Poder {i}", "source": "animalidade"} for i in range(56)],
            "relations": [{"relationId": "r-1", "type": "CAN_CHOOSE_POWER", "sourceEntityId": "ent-1", "targetEntityId": "ent-2", "source": "animalidade"}],
            "groups": [],
        }
    }
    books = loader.load_inventory(operational_overlay=certified_job)
    anim = next(b for b in books if b["bookId"] == "animalidade")
    # Operational fields applied from JobStore:
    assert anim["pipelineStatus"] == "RUNNING"
    assert anim["currentStage"] == "relations"
    assert len(anim["entities"]) == 56
    # Rights must remain strictly canonical:
    assert anim["rightsStatus"] == "UNKNOWN"
    assert anim["publicationMode"] == "NOT_PUBLIC"

def test_archive_inventory_loader_overlay_cannot_modify_rights():
    loader = ArchiveInventoryLoader()
    # Buggy or unauthorized overlay attempting to escalate rights
    hostile_overlay = {
        "4killers": {
            "bookId": "4killers",
            "rightsStatus": "AUTHORIZED",
            "publicationMode": "FULL_TEXT",
            "pipelineStatus": "DONE",
            "currentStage": "qa",
            "entities": [{"id": "ent-1", "name": "Killer", "source": "4killers"}],
        }
    }
    books = loader.load_inventory(operational_overlay=hostile_overlay)
    sample = next(b for b in books if b["bookId"] == "4killers")
    assert sample["pipelineStatus"] == "DONE"
    assert sample["currentStage"] == "qa"
    assert len(sample["entities"]) == 1
    # Rights escalation strictly rejected; canonical values preserved:
    assert sample["rightsStatus"] == "UNKNOWN"
    assert sample["publicationMode"] == "NOT_PUBLIC"

def test_archive_inventory_loader_relation_without_source_fails_closed():
    loader = ArchiveInventoryLoader()
    # Relation with missing or invalid source must never be assigned to animalidade
    bad_overlay = {
        "animalidade": {
            "bookId": "animalidade",
            "pipelineStatus": "RUNNING",
            "currentStage": "relations",
            "entities": [],
            "relations": [{"relationId": "r-bad", "type": "CAN_CHOOSE_POWER", "sourceEntityId": "e1", "targetEntityId": "e2"}],
        }
    }
    with pytest.raises(ProcessedStateReadError, match="missing required source provenance"):
        loader.load_inventory(operational_overlay=bad_overlay)

def test_archive_inventory_loader_corrupt_artifact_fails_closed(tmp_path):
    corrupt_file = tmp_path / "corrupt_job.json"
    corrupt_file.write_text("{malformed json", encoding="utf-8")
    with pytest.raises(ProcessedStateReadError):
        load_certified_pilot_artifacts(runtime_dir=tmp_path)
```

- [ ] **Step 2: Run test and confirm RED**
```powershell
python -m pytest tests/agents/test_archive_inventory_loader.py -v
```
Expected: `ModuleNotFoundError: No module named 'scripts.agents.archive_inventory_loader'`.

- [ ] **Step 3: Implement minimal code**
Create `scripts/agents/archive_inventory_loader.py`:
```python
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

from scripts.agents.job_store import JobStore, JobNotFoundError

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCES_PATH = ROOT / "data" / "index" / "sources.json"
DEFAULT_JOBS_DIR = ROOT / "coordination" / "jobs"
DEFAULT_RUNTIME_DIR = ROOT.parent / ".daemon_runtime"

class ArchiveInventoryError(RuntimeError):
    """Base error for archive inventory operations."""
    pass

class ProcessedStateReadError(ArchiveInventoryError):
    """Raised when certified operational state or artifact reading fails or artifact is corrupt."""
    pass

def load_certified_pilot_artifacts(runtime_dir: Path | str | None = None) -> dict[str, dict[str, Any]]:
    """Loads certified operational state and accepted artifact bundles from runtime store read-only."""
    r_dir = Path(runtime_dir).resolve() if runtime_dir else DEFAULT_RUNTIME_DIR
    if not r_dir.exists():
        return {}

    jobs_dir = r_dir / "jobs"
    accepted_bundles_dir = r_dir / "bundles" / "accepted"
    overlay: dict[str, dict[str, Any]] = {}

    if not jobs_dir.exists():
        return overlay

    for job_file in sorted(jobs_dir.glob("*.json")):
        try:
            with open(job_file, "r", encoding="utf-8") as f:
                job_data = json.load(f)
        except Exception as e:
            raise ProcessedStateReadError(f"Failed to read job file at {job_file}: {e}") from e

        book_id = job_data.get("bookId")
        if not book_id:
            continue

        raw_status = job_data.get("status", "todo")
        status_map = {
            "todo": "WAITING",
            "in_progress": "RUNNING",
            "blocked": "BLOCKED",
            "needs_review": "NEEDS_HUMAN_REVIEW",
            "approved": "READY_FOR_HUMAN_APPROVAL",
            "done": "DONE",
        }
        pipeline_status = status_map.get(raw_status, "WAITING")
        current_stage = job_data.get("currentStage")

        # Load certified entities from accepted bundle if available
        entities: list[dict[str, Any]] = []
        relations: list[dict[str, Any]] = []

        if accepted_bundles_dir.exists():
            for bundle_dir in accepted_bundles_dir.glob(f"RB-*{book_id.upper()}*"):
                ent_file = bundle_dir / "artifacts" / "entities.json"
                if ent_file.exists():
                    try:
                        with open(ent_file, "r", encoding="utf-8") as f:
                            ent_data = json.load(f)
                        entities = ent_data if isinstance(ent_data, list) else [ent_data]
                    except Exception as e:
                        raise ProcessedStateReadError(f"Corrupt entity artifact in bundle {bundle_dir}: {e}") from e

                rel_file = bundle_dir / "artifacts" / "relations.json"
                if rel_file.exists():
                    try:
                        with open(rel_file, "r", encoding="utf-8") as f:
                            rel_data = json.load(f)
                        raw_rels = rel_data if isinstance(rel_data, list) else [rel_data]
                        for r in raw_rels:
                            if not isinstance(r, dict):
                                continue
                            r_src = r.get("source")
                            if not r_src or r_src != book_id:
                                raise ProcessedStateReadError(f"Relation '{r.get('relationId', 'unknown')}' missing required source provenance or mismatch: '{r_src}' != '{book_id}'")
                            relations.append(r)
                    except ProcessedStateReadError:
                        raise
                    except Exception as e:
                        raise ProcessedStateReadError(f"Corrupt relation artifact in bundle {bundle_dir}: {e}") from e

        overlay[book_id] = {
            "bookId": book_id,
            "pipelineStatus": pipeline_status,
            "currentStage": current_stage,
            "entities": entities,
            "relations": relations,
            "groups": [],
        }

    return overlay

class ArchiveInventoryLoader:
    def __init__(self, sources_path: Path | str | None = None, jobs_dir: Path | str | None = None, runtime_dir: Path | str | None = None) -> None:
        self.sources_path = Path(sources_path).resolve() if sources_path else DEFAULT_SOURCES_PATH
        self.jobs_dir = Path(jobs_dir).resolve() if jobs_dir else DEFAULT_JOBS_DIR
        self.runtime_dir = Path(runtime_dir).resolve() if runtime_dir else DEFAULT_RUNTIME_DIR

    def load_inventory(self, operational_overlay: dict[str, dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        if not self.sources_path.exists():
            raise FileNotFoundError(f"Sources manifest not found: {self.sources_path}")

        try:
            with open(self.sources_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            raise ArchiveInventoryError(f"Failed to read sources manifest: {e}") from e

        sources = data.get("sources", [])
        overlay_map = operational_overlay if operational_overlay is not None else load_certified_pilot_artifacts(self.runtime_dir)
        result = []

        for src in sources:
            bid = src["id"]
            canonical_title = src.get("title", bid)
            canonical_rights = src.get("rightsStatus") or "UNKNOWN"
            canonical_pub = src.get("publicationMode") or "NOT_PUBLIC"

            if bid in overlay_map:
                overlay = overlay_map[bid]
                pipeline_status = overlay.get("pipelineStatus", "WAITING")
                current_stage = overlay.get("currentStage")
                entities = list(overlay.get("entities", []))
                raw_relations = overlay.get("relations", [])
                relations = []
                for r in raw_relations:
                    if not isinstance(r, dict):
                        continue
                    r_src = r.get("source")
                    if not r_src:
                        raise ProcessedStateReadError(f"Relation in overlay for book '{bid}' missing required source provenance")
                    relations.append(r)
                groups = list(overlay.get("groups", []))
            else:
                pipeline_status = "WAITING"
                current_stage = None
                entities = []
                relations = []
                groups = []

            rec = {
                "bookId": bid,
                "title": canonical_title,
                "rightsStatus": canonical_rights,
                "publicationMode": canonical_pub,
                "pipelineStatus": pipeline_status,
                "currentStage": current_stage,
                "path": src.get("path", ""),
                "extension": src.get("extension", ""),
                "sizeBytes": src.get("sizeBytes", 0),
                "sha256": src.get("sha256", ""),
                "categoryHints": list(src.get("categoryHints", [])),
                "pageCount": src.get("pageCount", 0),
                "entities": entities,
                "relations": relations,
                "groups": groups,
            }
            result.append(rec)

        result.sort(key=lambda b: b["bookId"])
        return result

    def get_book_by_id(self, book_id: str, operational_overlay: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
        all_books = self.load_inventory(operational_overlay)
        for b in all_books:
            if b["bookId"] == book_id:
                return b
        raise KeyError(f"Book '{book_id}' not found in archive inventory")
```

- [ ] **Step 4: Run test and confirm GREEN**
```powershell
python -m pytest tests/agents/test_archive_inventory_loader.py -v
```
Expected: 5 passed.

- [ ] **Step 5: Run focused regressions**
```powershell
python -m pytest tests/agents -q
```
Expected: All tests pass.

- [ ] **Step 6: Commit**
```powershell
git add scripts/agents/archive_inventory_loader.py tests/agents/test_archive_inventory_loader.py
git commit -m "feat(archive): implement archive inventory loader with operational authority and rights boundary"
```

---

### Task 2: Site View Model & Frontend Projector Dual-Axis Metadata Extension

**Files:**
- Modify: `scripts/agents/site_view_model.py`
- Modify: `scripts/agents/frontend_projector.py`
- Create: `tests/agents/test_frontend_projector_archive.py`

**Interfaces:**
- `FrontendProjector.build(books: list[dict[str, Any]], mode: str) -> dict[str, dict[str, Any]]` projects both operational and governance axes into `catalog.json`:
  `pipelineStatus`, `rightsStatus`, `publicationMode`, `currentStage` (can be `None`), `entityCount`, `pageCount`, `categoryHints`, `sizeBytes`.
- `validate_projection(files: dict[str, dict[str, Any]]) -> None` validates that catalog books contain valid `rightsStatus` (`AUTHORIZED`, `PRIVATE`, `PUBLIC_DOMAIN`, `METADATA_ONLY`, `UNKNOWN`), `publicationMode`, and valid operational fields.

- [ ] **Step 1: Write failing test**
Create `tests/agents/test_frontend_projector_archive.py`:
```python
import pytest
from scripts.agents.archive_inventory_loader import ArchiveInventoryLoader
from scripts.agents.frontend_projector import FrontendProjector
from scripts.agents.site_view_model import validate_projection

def test_frontend_projector_projects_dual_axis_metadata():
    loader = ArchiveInventoryLoader()
    books = loader.load_inventory()
    projector = FrontendProjector()

    files = projector.build(books, mode="restricted_preview")

    assert "catalog.json" in files
    catalog = files["catalog.json"]
    assert len(catalog["books"]) == 281

    # Check unworked entry (4killers)
    fk = next(b for b in catalog["books"] if b["bookId"] == "4killers")
    assert fk["pipelineStatus"] == "WAITING"
    assert fk["rightsStatus"] == "UNKNOWN"
    assert fk["publicationMode"] == "NOT_PUBLIC"
    assert fk["currentStage"] is None
    assert fk["entityCount"] == 0
    assert fk["pageCount"] == 8

    # Strict contract validation passes
    validate_projection(files)
```

- [ ] **Step 2: Run test and confirm RED**
```powershell
python -m pytest tests/agents/test_frontend_projector_archive.py -v
```
Expected: Failure on `rightsStatus` or `currentStage is None` assertion in `catalog.json`.

- [ ] **Step 3: Implement minimal code**
Update `scripts/agents/frontend_projector.py` in `build()` around Step 7:
```python
        # Step 7: Build catalog books metadata
        catalog_books: list[dict[str, Any]] = []
        for b in filtered_books:
            cat_entry = {
                "bookId": b["bookId"],
                "title": b["title"],
                "rightsStatus": b.get("rightsStatus", "UNKNOWN"),
                "publicationMode": b["publicationMode"],
                "path": f"books/{b['bookId']}.json",
                "groups": b.get("groups", []),
                "pipelineStatus": b.get("pipelineStatus", "WAITING"),
                "currentStage": b.get("currentStage"),
                "entityCount": len(b.get("entities", [])),
                "pageCount": b.get("pageCount", 0),
                "categoryHints": list(b.get("categoryHints", [])),
                "sizeBytes": b.get("sizeBytes", 0),
            }
            catalog_books.append(cat_entry)
        catalog_books.sort(key=lambda b: b["bookId"])
```
Update `scripts/agents/site_view_model.py` in `validate_projection` book loop:
```python
        VALID_RIGHTS = {"AUTHORIZED", "PRIVATE", "PUBLIC_DOMAIN", "METADATA_ONLY", "UNKNOWN"}
        rights_st = book.get("rightsStatus")
        if rights_st is not None and (not isinstance(rights_st, str) or rights_st not in VALID_RIGHTS):
            raise ProjectionError(f"Catalog book '{bid}' has invalid rightsStatus: '{rights_st}'")

        pipeline_status = book.get("pipelineStatus")
        if pipeline_status is not None and not isinstance(pipeline_status, str):
            raise ProjectionError(f"Catalog book '{bid}' has invalid pipelineStatus")

        current_stage = book.get("currentStage")
        if current_stage is not None and not isinstance(current_stage, str):
            raise ProjectionError(f"Catalog book '{bid}' has invalid currentStage")

        entity_count = book.get("entityCount")
        if entity_count is not None and not isinstance(entity_count, int):
            raise ProjectionError(f"Catalog book '{bid}' has invalid entityCount")
```

- [ ] **Step 4: Run test and confirm GREEN**
```powershell
python -m pytest tests/agents/test_frontend_projector_archive.py -v
```
Expected: 1 passed.

- [ ] **Step 5: Run focused regressions**
```powershell
python -m pytest tests/agents -q
```
Expected: All pass.

- [ ] **Step 6: Commit**
```powershell
git add scripts/agents/site_view_model.py scripts/agents/frontend_projector.py tests/agents/test_frontend_projector_archive.py
git commit -m "feat(projector): project dual-axis pipeline and rights metadata to catalog"
```

---

### Task 3: Controlled Synthetic Matrix Tests for Fail-Closed Public Policy

**Files:**
- Create: `tests/agents/test_frontend_policy_archive.py`

**Interfaces:**
- Test suite validating `FrontendProjector.build(books, mode="public")` across the canonical combination matrix without assuming rights of real books.
- Validates semantic content exclusion: `METADATA_ONLY` produces empty entity content blocks and empty relations list; `SUMMARY_AND_METADATA` produces only summary blocks.

- [ ] **Step 1: Write test suite**
Create `tests/agents/test_frontend_policy_archive.py`:
```python
import pytest
from scripts.agents.archive_inventory_loader import ArchiveInventoryLoader
from scripts.agents.frontend_projector import FrontendProjector
from scripts.agents.site_view_model import validate_projection

def test_public_policy_matrix_with_synthetic_fixtures():
    projector = FrontendProjector()

    synthetic_books = [
        # 1. UNKNOWN + NOT_PUBLIC -> excluded
        {"bookId": "s-unknown", "title": "S Unknown", "rightsStatus": "UNKNOWN", "publicationMode": "NOT_PUBLIC", "entities": []},
        # 2. PRIVATE + NOT_PUBLIC -> excluded
        {"bookId": "s-private", "title": "S Private", "rightsStatus": "PRIVATE", "publicationMode": "NOT_PUBLIC", "entities": []},
        # 3. PUBLIC_DOMAIN + FULL_TEXT -> permitted with full content
        {"bookId": "s-pd", "title": "S Public Domain", "rightsStatus": "PUBLIC_DOMAIN", "publicationMode": "FULL_TEXT", "entities": [
            {"id": "e-pd-1", "name": "Entidade PD", "category": "core_rule", "content": [{"title": "C1", "paragraphs": ["Texto integral"]}]}
        ], "relations": [{"relationId": "r-pd-1", "type": "RELATES_TO", "sourceEntityId": "e-pd-1", "targetEntityId": "e-pd-2"}]},
        # 4. AUTHORIZED + FULL_TEXT -> permitted with full content
        {"bookId": "s-auth", "title": "S Authorized", "rightsStatus": "AUTHORIZED", "publicationMode": "FULL_TEXT", "entities": [
            {"id": "e-auth-1", "name": "Entidade Auth", "category": "character_option", "content": [{"title": "C1", "paragraphs": ["Texto"]}]}
        ]},
        # 5. METADATA_ONLY + METADATA_ONLY -> permitted in catalog, but content and relations strictly stripped
        {"bookId": "s-meta", "title": "S Metadata", "rightsStatus": "METADATA_ONLY", "publicationMode": "METADATA_ONLY", "entities": [
            {"id": "e-meta-1", "name": "Entidade Meta", "category": "power_magic", "content": [{"title": "Segredo", "paragraphs": ["Não pode vazar"]}]}
        ], "relations": [{"relationId": "r-meta-1", "type": "HAS_POWER", "sourceEntityId": "e-meta-1", "targetEntityId": "e-meta-2"}]},
        # 6. AUTHORIZED + SUMMARY_AND_METADATA -> permitted with summary only
        {"bookId": "s-summary", "title": "S Summary", "rightsStatus": "AUTHORIZED", "publicationMode": "SUMMARY_AND_METADATA", "entities": [
            {"id": "e-sum-1", "name": "Entidade Sum", "category": "creature_npc", "summary": "Resumo autorizado", "content": [{"title": "Corpo", "paragraphs": ["Texto protegido"]}]}
        ]},
    ]

    files = projector.build(synthetic_books, mode="public")
    catalog = files["catalog.json"]
    projected_ids = {b["bookId"] for b in catalog["books"]}

    # Excluded:
    assert "s-unknown" not in projected_ids
    assert "s-private" not in projected_ids
    assert "books/s-unknown.json" not in files
    assert "books/s-private.json" not in files

    # Permitted in catalog:
    assert "s-pd" in projected_ids
    assert "s-auth" in projected_ids
    assert "s-meta" in projected_ids
    assert "s-summary" in projected_ids
    assert len(catalog["books"]) == 4

    # Semantic check on METADATA_ONLY: content and relations MUST be stripped
    meta_book = files["books/s-meta.json"]
    assert meta_book["entities"][0]["content"] == []
    assert meta_book["relations"] == []

    # Semantic check on SUMMARY_AND_METADATA: only summary block preserved
    sum_book = files["books/s-summary.json"]
    assert len(sum_book["entities"][0]["content"]) == 1
    assert sum_book["entities"][0]["content"][0]["title"] == "Resumo"
    assert sum_book["entities"][0]["content"][0]["paragraphs"] == ["Resumo autorizado"]

    # Semantic check on FULL_TEXT: full content preserved
    pd_book = files["books/s-pd.json"]
    assert len(pd_book["entities"][0]["content"]) == 1
    assert pd_book["entities"][0]["content"][0]["paragraphs"] == ["Texto integral"]
    assert len(pd_book["relations"]) == 1

    validate_projection(files)

def test_real_archive_inventory_fails_closed_without_authorization():
    loader = ArchiveInventoryLoader()
    books = loader.load_inventory()
    projector = FrontendProjector()

    files = projector.build(books, mode="public")
    catalog = files["catalog.json"]

    # In public mode, every projected book must strictly satisfy permitted combinations
    for b in catalog["books"]:
        assert b["publicationMode"] != "NOT_PUBLIC"
        assert b["rightsStatus"] != "UNKNOWN"
```

- [ ] **Step 2: Run test and confirm GREEN**
```powershell
python -m pytest tests/agents/test_frontend_policy_archive.py -v
```
Expected: 2 passed.

- [ ] **Step 3: Run focused regressions**
```powershell
python -m pytest tests/agents -q
```
Expected: All pass.

- [ ] **Step 4: Commit**
```powershell
git add tests/agents/test_frontend_policy_archive.py
git commit -m "test(policy): verify fail-closed public matrix with controlled synthetic fixtures"
```

---

### Task 4: Frontend Dual-Axis Filtering, Sorting & State Management (`site-model.mjs`, `site-search.mjs`, `site-state.mjs`)

**Files:**
- Modify: `docs/assets/site-model.mjs`
- Modify: `docs/assets/site-search.mjs`
- Modify: `docs/assets/site-state.mjs`
- Modify: `tests/frontend/site-model.test.mjs`
- Modify: `tests/frontend/site-search.test.mjs`
- Modify: `tests/frontend/site-state.test.mjs`

**Interfaces:**
- `site-model.mjs`: `getBookMetadata(bookId)` returns catalog entry with `pipelineStatus`, `rightsStatus`, `publicationMode`, `currentStage`.
- `site-search.mjs`: `filterBooks(books, { query, pipelineStatus, rightsStatus, publicationMode, categoryHint, sortBy })` filters by both axes.
- `site-state.mjs`: `createState` initializes `bookFilters: { query: '', pipelineStatus: 'all', rightsStatus: 'all', publicationMode: 'all', sortBy: 'title_asc' }`; `setBookFilters(state, updates)` updates filters immutably.

- [ ] **Step 1: Write failing tests**
Update `tests/frontend/site-state.test.mjs`:
```javascript
import test from 'node:test';
import assert from 'node:assert/strict';
import { createState, setBookFilters } from '../../docs/assets/site-state.mjs';

test('createState initializes bookFilters with dual-axis defaults', () => {
  const state = createState();
  assert.deepEqual(state.bookFilters, {
    query: '',
    pipelineStatus: 'all',
    rightsStatus: 'all',
    publicationMode: 'all',
    sortBy: 'title_asc',
  });
});

test('setBookFilters updates bookFilters immutably', () => {
  const state = createState();
  const next = setBookFilters(state, { pipelineStatus: 'RUNNING', rightsStatus: 'UNKNOWN' });
  assert.notEqual(state, next);
  assert.equal(next.bookFilters.pipelineStatus, 'RUNNING');
  assert.equal(next.bookFilters.rightsStatus, 'UNKNOWN');
  assert.equal(next.bookFilters.sortBy, 'title_asc');
  assert.equal(state.bookFilters.pipelineStatus, 'all');
});
```

Update `tests/frontend/site-search.test.mjs`:
```javascript
import test from 'node:test';
import assert from 'node:assert/strict';
import { filterBooks } from '../../docs/assets/site-search.mjs';

test('filterBooks filters by rightsStatus and pipelineStatus independently and combined', () => {
  const books = [
    { bookId: 'b1', title: 'Trevas', pipelineStatus: 'DONE', rightsStatus: 'UNKNOWN', publicationMode: 'NOT_PUBLIC', entityCount: 10, pageCount: 50 },
    { bookId: 'b2', title: 'Arkanun', pipelineStatus: 'WAITING', rightsStatus: 'AUTHORIZED', publicationMode: 'FULL_TEXT', entityCount: 0, pageCount: 20 },
    { bookId: 'b3', title: 'Invasao', pipelineStatus: 'WAITING', rightsStatus: 'UNKNOWN', publicationMode: 'NOT_PUBLIC', entityCount: 0, pageCount: 100 },
  ];

  // Filter by pipelineStatus
  assert.equal(filterBooks(books, { pipelineStatus: 'WAITING' }).length, 2);

  // Filter by rightsStatus
  assert.equal(filterBooks(books, { rightsStatus: 'AUTHORIZED' }).length, 1);
  assert.equal(filterBooks(books, { rightsStatus: 'AUTHORIZED' })[0].bookId, 'b2');

  // Combined filter
  assert.equal(filterBooks(books, { pipelineStatus: 'WAITING', rightsStatus: 'UNKNOWN' }).length, 1);
  assert.equal(filterBooks(books, { pipelineStatus: 'WAITING', rightsStatus: 'UNKNOWN' })[0].bookId, 'b3');
});
```

Update `tests/frontend/site-model.test.mjs`:
```javascript
test('getBookMetadata returns dual-axis fields', () => {
  const store = new SiteStore();
  store.catalog = {
    books: [
      { bookId: 'trevas', title: 'Trevas', pipelineStatus: 'DONE', rightsStatus: 'UNKNOWN', publicationMode: 'NOT_PUBLIC', currentStage: 'qa' }
    ]
  };
  const meta = store.getBookMetadata('trevas');
  assert.equal(meta.rightsStatus, 'UNKNOWN');
  assert.equal(meta.pipelineStatus, 'DONE');
  assert.equal(meta.currentStage, 'qa');
});
```

- [ ] **Step 2: Run tests and confirm RED**
```powershell
node --test tests/frontend/site-search.test.mjs tests/frontend/site-model.test.mjs tests/frontend/site-state.test.mjs
```
Expected: Failures on `setBookFilters` not defined, `rightsStatus` filtering, and `getBookMetadata`.

- [ ] **Step 3: Implement minimal code**
In `docs/assets/site-state.mjs`:
```javascript
export function createState(storage = null, initialHash = '#/') {
  const route = initialHash || '#/';
  const routeInfo = parseRoute(route);
  const layout = readSavedLayout(storage);

  return {
    route,
    routeInfo,
    selectedEntityId: routeInfo.kind === 'entity' ? routeInfo.id : null,
    bookId: null,
    query: '',
    type: null,
    layout,
    bookFilters: {
      query: '',
      pipelineStatus: 'all',
      rightsStatus: 'all',
      publicationMode: 'all',
      sortBy: 'title_asc',
    },
  };
}

export function setBookFilters(state, updates = {}) {
  return {
    ...state,
    bookFilters: {
      ...state.bookFilters,
      ...updates,
    },
  };
}
```

In `docs/assets/site-search.mjs`:
```javascript
export function filterBooks(books, {
  query = '',
  pipelineStatus = '',
  rightsStatus = '',
  publicationMode = '',
  categoryHint = '',
  sortBy = 'title_asc',
} = {}) {
  let result = [...books];

  const q = normalizeSearch(query);
  if (q) {
    result = result.filter(b => normalizeSearch(b.title).includes(q) || b.bookId.includes(q));
  }

  if (pipelineStatus && pipelineStatus !== 'all') {
    result = result.filter(b => b.pipelineStatus === pipelineStatus);
  }

  if (rightsStatus && rightsStatus !== 'all') {
    result = result.filter(b => b.rightsStatus === rightsStatus);
  }

  if (publicationMode && publicationMode !== 'all') {
    result = result.filter(b => b.publicationMode === publicationMode);
  }

  if (categoryHint && categoryHint !== 'all') {
    result = result.filter(b => Array.isArray(b.categoryHints) && b.categoryHints.includes(categoryHint));
  }

  if (sortBy === 'title_asc') {
    result.sort((a, b) => a.title.localeCompare(b.title));
  } else if (sortBy === 'title_desc') {
    result.sort((a, b) => b.title.localeCompare(a.title));
  } else if (sortBy === 'entities_desc') {
    result.sort((a, b) => (b.entityCount || 0) - (a.entityCount || 0) || a.title.localeCompare(b.title));
  } else if (sortBy === 'pages_desc') {
    result.sort((a, b) => (b.pageCount || 0) - (a.pageCount || 0) || a.title.localeCompare(b.title));
  }

  return result;
}
```

In `docs/assets/site-model.mjs`:
```javascript
getBookMetadata(bookId) {
  if (!this.catalog || !Array.isArray(this.catalog.books)) return null;
  return this.catalog.books.find(b => b.bookId === bookId) || null;
}
```

- [ ] **Step 4: Run tests and confirm GREEN**
```powershell
node --test tests/frontend/site-search.test.mjs tests/frontend/site-model.test.mjs tests/frontend/site-state.test.mjs
```
Expected: All pass.

- [ ] **Step 5: Run focused regressions**
```powershell
node --test tests/frontend/*.test.mjs
```
Expected: All pass.

- [ ] **Step 6: Commit**
```powershell
git add docs/assets/site-model.mjs docs/assets/site-search.mjs docs/assets/site-state.mjs tests/frontend/site-model.test.mjs tests/frontend/site-search.test.mjs tests/frontend/site-state.test.mjs
git commit -m "feat(frontend): implement dual-axis catalog filtering, sorting, and state management"
```

---

### Task 5: Acervo 281 UI — Safe Cards, Dual-Axis Badges, and Filter Controls (`site-ui.mjs`, `styles.css`)

**Files:**
- Create: `tests/frontend/site-ui-books.test.mjs`
- Modify: `docs/assets/site-ui.mjs`
- Modify: `docs/assets/styles.css`

**Interfaces:**
- `escapeHtml(str)` in `site-ui.mjs`: sanitizes special characters (`&`, `<`, `>`, `"`, `'`) to prevent arbitrary markup injection.
- `createBookCard(book)` in `site-ui.mjs`: builds `.site-book-card` container with safely escaped title, link, `.site-badge-pipeline` (`data-status`), `.site-badge-rights` (`data-rights`), and `.site-badge-pub` (`data-mode`).
- `renderBooksView()` in `site-ui.mjs`: builds the complete responsive catalog view with dual-axis dropdowns.

- [ ] **Step 1: Write failing test**
Create `tests/frontend/site-ui-books.test.mjs`:
```javascript
import test from 'node:test';
import assert from 'node:assert/strict';
import { createBookCard, escapeHtml } from '../../docs/assets/site-ui.mjs';

test('escapeHtml sanitizes special characters against markup injection', () => {
  const raw = '<script>alert("xss")</script> & \'Trevas\'';
  const escaped = escapeHtml(raw);
  assert.equal(escaped, '&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt; &amp; &#39;Trevas&#39;');
});

test('createBookCard renders .site-book-card with dual-axis badges and safe escaping', () => {
  const book = {
    bookId: 'animalidade',
    title: '<Animalidade & Feras>',
    pipelineStatus: 'RUNNING',
    rightsStatus: 'UNKNOWN',
    publicationMode: 'NOT_PUBLIC',
    currentStage: 'relations',
    entityCount: 56,
    pageCount: 13,
  };

  const cardHtml = createBookCard(book);
  // Must render .site-book-card container
  assert.match(cardHtml, /<div class="site-book-card"/);
  assert.match(cardHtml, /data-book-id="animalidade"/);
  // Must render correct link
  assert.match(cardHtml, /href="#\/book\/animalidade"/);
  // Must escape special characters in title
  assert.match(cardHtml, /&lt;Animalidade &amp; Feras&gt;/);
  assert.doesNotMatch(cardHtml, /<Animalidade/);
  // Badges
  assert.match(cardHtml, /class="site-badge site-badge-pipeline" data-status="RUNNING"/);
  assert.match(cardHtml, /class="site-badge site-badge-rights" data-rights="UNKNOWN"/);
  assert.match(cardHtml, /class="site-badge site-badge-pub" data-mode="NOT_PUBLIC"/);
  assert.match(cardHtml, /56 entidades/);
});
```

- [ ] **Step 2: Run test and confirm RED**
```powershell
node --test tests/frontend/site-ui-books.test.mjs
```
Expected: `TypeError: createBookCard is not a function`.

- [ ] **Step 3: Implement minimal code in `site-ui.mjs` and `styles.css`**
Export `escapeHtml` and `createBookCard` in `docs/assets/site-ui.mjs`:
```javascript
export function escapeHtml(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

export function createBookCard(b) {
  const safeId = encodeURIComponent(b.bookId || '');
  const safeTitle = escapeHtml(b.title || safeId);
  const safePipeline = escapeHtml(b.pipelineStatus || 'WAITING');
  const safeRights = escapeHtml(b.rightsStatus || 'UNKNOWN');
  const safePub = escapeHtml(b.publicationMode || 'NOT_PUBLIC');
  const stageText = b.currentStage ? `Estágio: ${escapeHtml(b.currentStage)}` : 'Não iniciado';
  const entityCount = Number.isInteger(b.entityCount) ? b.entityCount : 0;
  const pageCount = Number.isInteger(b.pageCount) ? b.pageCount : 0;

  return `
    <div class="site-book-card" data-book-id="${safeId}">
      <a href="#/book/${safeId}" class="site-book-title">${safeTitle}</a>
      <div class="site-card-badges">
        <span class="site-badge site-badge-pipeline" data-status="${safePipeline}">${safePipeline}</span>
        <span class="site-badge site-badge-rights" data-rights="${safeRights}">${safeRights}</span>
        <span class="site-badge site-badge-pub" data-mode="${safePub}">${safePub}</span>
      </div>
      <div class="site-card-meta">
        <span class="site-card-stage">${stageText}</span>
        <span class="site-card-count">${entityCount} entidades</span>
        <span class="site-card-pages">${pageCount} págs</span>
      </div>
    </div>
  `.trim();
}
```
Update `renderBooksView` in `docs/assets/site-ui.mjs` to utilize `createBookCard` and add dropdown filters for `pipelineStatus` and `rightsStatus`.
Add badge styling in `docs/assets/styles.css`:
```css
.site-book-card { display: flex; flex-direction: column; padding: 16px; border: 1px solid #37474f; border-radius: 6px; background: #1a2327; }
.site-badge-rights[data-rights="AUTHORIZED"],
.site-badge-rights[data-rights="PUBLIC_DOMAIN"] { background: #1b5e20; color: #fff; }
.site-badge-rights[data-rights="UNKNOWN"] { background: #424242; color: #e0e0e0; }
.site-badge-pipeline[data-status="WAITING"] { background: #37474f; color: #cfd8dc; }
.site-badge-pipeline[data-status="RUNNING"] { background: #0277bd; color: #fff; }
.site-badge-pipeline[data-status="READY_FOR_HUMAN_APPROVAL"] { background: #e65100; color: #fff; }
.site-badge-pipeline[data-status="DONE"] { background: #2e7d32; color: #fff; }
.site-badge-pipeline[data-status="BLOCKED"] { background: #c62828; color: #fff; }
```

- [ ] **Step 4: Run test and confirm GREEN**
```powershell
node --test tests/frontend/site-ui-books.test.mjs
```
Expected: 2 passed.

- [ ] **Step 5: Run focused regressions**
```powershell
node --test tests/frontend/*.test.mjs
node --check docs/assets/app.js
```
Expected: All pass.

- [ ] **Step 6: Commit**
```powershell
git add docs/assets/site-ui.mjs docs/assets/styles.css tests/frontend/site-ui-books.test.mjs
git commit -m "feat(frontend): implement safe dual-axis book cards and catalog filter controls"
```

---

### Task 6: 7-Stage Pipeline Stepper & Book Detail View (`#/book/:bookId`)

**Files:**
- Create: `tests/frontend/site-ui-book-detail.test.mjs`
- Modify: `docs/assets/site-ui.mjs`
- Modify: `docs/assets/styles.css`

**Interfaces:**
- `getStageStates(pipelineStatus: string, currentStage: string | null)`: returns list of `{ stage, state }` where state is `'pending'`, `'active'`, `'done'`, or `'blocked'`.
  - `WAITING` or `null`: 7 pending.
  - `RUNNING`: stages before current are `'done'`, current is `'active'`, subsequent are `'pending'`.
  - `READY_FOR_HUMAN_APPROVAL` or `DONE`: all 7 stages are `'done'`.
  - `BLOCKED` or `NEEDS_HUMAN_REVIEW`: stages before current are `'done'`, current is `'blocked'`, subsequent are strictly `'pending'`.
- `renderBookDetailHtml({ book, catalogMeta, entities })`: renders complete book detail container (`.site-book-detail`), 7-stage visual stepper (`.pipeline-stepper`), metadata card, and empty state banner (`.site-book-empty-state`) when `entities.length === 0`.

- [ ] **Step 1: Write failing test**
Create `tests/frontend/site-ui-book-detail.test.mjs`:
```javascript
import test from 'node:test';
import assert from 'node:assert/strict';
import { getStageStates, renderBookDetailHtml } from '../../docs/assets/site-ui.mjs';

test('getStageStates returns all 7 stages as pending for unworked book', () => {
  const stages = getStageStates('WAITING', null);
  assert.equal(stages.length, 7);
  for (const s of stages) {
    assert.equal(s.state, 'pending');
  }
});

test('getStageStates returns all 7 stages as done for READY_FOR_HUMAN_APPROVAL and DONE', () => {
  const readyStages = getStageStates('READY_FOR_HUMAN_APPROVAL', 'qa');
  assert.equal(readyStages.length, 7);
  readyStages.forEach(s => assert.equal(s.state, 'done'));

  const doneStages = getStageStates('DONE', 'qa');
  assert.equal(doneStages.length, 7);
  doneStages.forEach(s => assert.equal(s.state, 'done'));
});

test('getStageStates marks stages correctly for in-progress and blocked books', () => {
  // In-progress at editorial: Source and Extraction done, Editorial active, rest pending
  const inProgress = getStageStates('RUNNING', 'editorial');
  assert.equal(inProgress.find(s => s.stage === 'Source').state, 'done');
  assert.equal(inProgress.find(s => s.stage === 'Extraction').state, 'done');
  assert.equal(inProgress.find(s => s.stage === 'Editorial').state, 'active');
  assert.equal(inProgress.find(s => s.stage === 'Entities').state, 'pending');
  assert.equal(inProgress.find(s => s.stage === 'Relations').state, 'pending');
  assert.equal(inProgress.find(s => s.stage === 'QA').state, 'pending');

  // Blocked at relations: preceding done, Relations blocked, subsequent strictly pending
  const blocked = getStageStates('BLOCKED', 'relations');
  assert.equal(blocked.find(s => s.stage === 'Editorial').state, 'done');
  assert.equal(blocked.find(s => s.stage === 'Entities').state, 'done');
  assert.equal(blocked.find(s => s.stage === 'Relations').state, 'blocked');
  assert.equal(blocked.find(s => s.stage === 'Frontend').state, 'pending');
  assert.equal(blocked.find(s => s.stage === 'QA').state, 'pending');
});

test('renderBookDetailHtml renders unworked book with 7 pending stages and empty state', () => {
  const catalogMeta = {
    bookId: 'synthetic-empty',
    title: 'Livro Sintético Vazio',
    pipelineStatus: 'WAITING',
    rightsStatus: 'UNKNOWN',
    publicationMode: 'NOT_PUBLIC',
    currentStage: null,
  };
  const html = renderBookDetailHtml({ book: { title: 'Livro Sintético Vazio' }, catalogMeta, entities: [] });

  assert.match(html, /<div class="site-book-detail"/);
  assert.match(html, /class="pipeline-stepper"/);
  // All 7 steps must be pending
  const pendingMatches = html.match(/stepper-step pending/g) || [];
  assert.equal(pendingMatches.length, 7);
  // Empty state must be visible
  assert.match(html, /class="site-book-empty-state"/);
  assert.match(html, /Nenhuma entidade processada para este livro ainda/);
  // Dual-axis badges visible
  assert.match(html, /data-status="WAITING"/);
  assert.match(html, /data-rights="UNKNOWN"/);
});

test('renderBookDetailHtml renders processed book with all 7 done stages and entity list', () => {
  const catalogMeta = {
    bookId: 'animalidade',
    title: 'Animalidade',
    pipelineStatus: 'READY_FOR_HUMAN_APPROVAL',
    rightsStatus: 'UNKNOWN',
    publicationMode: 'NOT_PUBLIC',
    currentStage: 'qa',
  };
  const entities = [{ entityId: 'ent-1', name: 'Garras', displayType: 'Poder' }];
  const html = renderBookDetailHtml({ book: { title: 'Animalidade' }, catalogMeta, entities });

  const doneMatches = html.match(/stepper-step done/g) || [];
  assert.equal(doneMatches.length, 7);
  assert.doesNotMatch(html, /site-book-empty-state/);
  assert.match(html, /class="site-entity-list"/);
  assert.match(html, /Garras/);
});
```

- [ ] **Step 2: Run test and confirm RED**
```powershell
node --test tests/frontend/site-ui-book-detail.test.mjs
```
Expected: `TypeError: getStageStates is not a function`.

- [ ] **Step 3: Implement minimal code in `site-ui.mjs` and `styles.css`**
Export `PIPELINE_STAGES`, `getStageStates`, and `renderBookDetailHtml` in `docs/assets/site-ui.mjs`:
```javascript
export const PIPELINE_STAGES = [
  'Source', 'Extraction', 'Editorial', 'Entities', 'Relations', 'Frontend', 'QA'
];

export function getStageStates(pipelineStatus, currentStage) {
  if (pipelineStatus === 'DONE' || pipelineStatus === 'READY_FOR_HUMAN_APPROVAL') {
    return PIPELINE_STAGES.map(s => ({ stage: s, state: 'done' }));
  }
  if (!currentStage || pipelineStatus === 'WAITING') {
    return PIPELINE_STAGES.map(s => ({ stage: s, state: 'pending' }));
  }
  const curLower = currentStage.toLowerCase();
  const stagesLower = PIPELINE_STAGES.map(s => s.toLowerCase());
  const curIdx = stagesLower.indexOf(curLower);
  if (curIdx === -1) {
    return PIPELINE_STAGES.map(s => ({ stage: s, state: 'pending' }));
  }

  const activeState = (pipelineStatus === 'BLOCKED' || pipelineStatus === 'NEEDS_HUMAN_REVIEW') ? 'blocked' : 'active';

  return PIPELINE_STAGES.map((s, idx) => {
    if (idx < curIdx) return { stage: s, state: 'done' };
    if (idx === curIdx) return { stage: s, state: activeState };
    return { stage: s, state: 'pending' };
  });
}

export function renderBookDetailHtml({ book, catalogMeta, entities = [] }) {
  const meta = catalogMeta || {};
  const safeTitle = escapeHtml(book.title || meta.title || 'Livro');
  const safePipeline = escapeHtml(meta.pipelineStatus || 'WAITING');
  const safeRights = escapeHtml(meta.rightsStatus || 'UNKNOWN');
  const safePub = escapeHtml(meta.publicationMode || 'NOT_PUBLIC');

  const stageStates = getStageStates(safePipeline, meta.currentStage || null);
  const stepperHtml = `
    <div class="pipeline-stepper">
      ${stageStates.map(s => `<span class="stepper-step ${s.state}">${escapeHtml(s.stage)}</span>`).join('')}
    </div>
  `;

  let contentHtml = '';
  if (entities.length === 0) {
    contentHtml = `
      <div class="site-book-empty-state">
        <p>Nenhuma entidade processada para este livro ainda. O livro encontra-se na fila de processamento.</p>
      </div>
    `;
  } else {
    contentHtml = `
      <h2>Entidades deste Livro (${entities.length})</h2>
      <ul class="site-entity-list">
        ${entities.map(e => `<li><a href="#/entity/${encodeURIComponent(e.entityId)}">${escapeHtml(e.name)} (${escapeHtml(e.displayType)})</a></li>`).join('')}
      </ul>
    `;
  }

  return `
    <div class="site-book-detail">
      <h1>${safeTitle}</h1>
      <div class="site-card-badges">
        <span class="site-badge site-badge-pipeline" data-status="${safePipeline}">${safePipeline}</span>
        <span class="site-badge site-badge-rights" data-rights="${safeRights}">${safeRights}</span>
        <span class="site-badge site-badge-pub" data-mode="${safePub}">${safePub}</span>
      </div>
      ${stepperHtml}
      ${contentHtml}
    </div>
  `.trim();
}
```
Update `renderBookDetailView` in `site-ui.mjs` to render the view using `renderBookDetailHtml`.
Add stepper styling in `docs/assets/styles.css`:
```css
.pipeline-stepper { display: flex; gap: 8px; margin: 16px 0; flex-wrap: wrap; }
.stepper-step { padding: 6px 12px; border-radius: 4px; font-size: 0.85rem; font-weight: 500; }
.stepper-step.pending { background: #263238; color: #78909c; border: 1px dashed #455a64; }
.stepper-step.active { background: #0277bd; color: #fff; animation: pulse 2s infinite; }
.stepper-step.done { background: #2e7d32; color: #fff; }
.stepper-step.blocked { background: #c62828; color: #fff; }
.site-book-empty-state { padding: 24px; border: 1px dashed #455a64; border-radius: 6px; background: #1c2529; color: #b0bec5; text-align: center; margin: 16px 0; }
```

- [ ] **Step 4: Run test and confirm GREEN**
```powershell
node --test tests/frontend/site-ui-book-detail.test.mjs
```
Expected: 4 passed.

- [ ] **Step 5: Run focused regressions**
```powershell
node --test tests/frontend/*.test.mjs
node --check docs/assets/app.js
```
Expected: All pass.

- [ ] **Step 6: Commit**
```powershell
git add docs/assets/site-ui.mjs docs/assets/styles.css tests/frontend/site-ui-book-detail.test.mjs
git commit -m "feat(frontend): implement 7-stage pipeline stepper and safe book detail view"
```

---

### Task 7: Strict Browser E2E Tests (Restricted Preview & Public Fail-Closed)

**Files:**
- Modify: `tests/frontend/test_site_browser.py`
- Modify: `tests/frontend/conftest.py`

**Interfaces:**
- Strict browser tests in `tests/frontend/test_site_browser.py` without conditional skips (`if count > 0:` is strictly forbidden):
  - `test_books_catalog_filters_and_stepper_strict`: verifies multi-book rendering, navigation to unworked book, 7 pending stages, empty state, and dual badges.
  - `test_books_catalog_public_mode_fail_closed`: serves public projection, verifies zero NOT_PUBLIC/UNKNOWN cards exist in public mode, and verifies restricted routes return not-found/error with zero data leak.

- [ ] **Step 1: Update `tests/frontend/conftest.py` with synthetic multi-book catalog**
Add a second synthetic unworked book with 0 entities, `pipelineStatus="WAITING"`, `currentStage=None`:
```python
    unworked_book = {
        "bookId": "synthetic-empty",
        "title": "Livro Sintético Vazio",
        "rightsStatus": "UNKNOWN",
        "publicationMode": "NOT_PUBLIC",
        "pipelineStatus": "WAITING",
        "currentStage": None,
        "entities": [],
        "relations": [],
        "groups": [],
    }
```

- [ ] **Step 2: Write strict browser test functions in `tests/frontend/test_site_browser.py`**
```python
def test_books_catalog_filters_and_stepper_strict(page, site_url):
    page.goto(site_url + "#/books")
    page.wait_for_selector(".site-books-grid", timeout=10000)

    # Both books must exist
    assert page.locator(".site-book-card").count() >= 2

    # Strict assertion: unworked book link MUST exist (no conditional pass)
    unworked_link = page.locator('a[href="#/book/synthetic-empty"]')
    assert unworked_link.count() == 1, "Unworked book card must be present in restricted preview"
    unworked_link.first.click()

    # Wait for book detail view
    page.wait_for_selector(".pipeline-stepper", timeout=10000)

    # Stepper MUST contain exactly 7 stages
    steps = page.locator(".stepper-step")
    assert steps.count() == 7

    # For an unworked book, ALL 7 stages MUST have class 'pending' and ZERO active
    assert page.locator(".stepper-step.pending").count() == 7
    assert page.locator(".stepper-step.active").count() == 0

    # Empty state message MUST be visible
    empty_state = page.locator(".site-book-empty-state")
    assert empty_state.count() == 1
    assert "Nenhuma entidade processada" in empty_state.text_content()

    # Dual-axis badges MUST be visible
    assert page.locator(".site-badge-rights").count() >= 1
    assert page.locator(".site-badge-pipeline").count() >= 1

def test_books_catalog_public_mode_fail_closed(browser, tmp_path):
    """Verifies that in mode=public, restricted books are strictly excluded from catalog and detail routes."""
    from scripts.agents.frontend_projector import FrontendProjector
    from scripts.agents.preview_server import PreviewServer

    repo_root = Path(__file__).resolve().parents[2]
    projector = FrontendProjector()

    synthetic_catalog = [
        # Restricted books
        {"bookId": "synthetic-empty", "title": "Livro Vazio", "rightsStatus": "UNKNOWN", "publicationMode": "NOT_PUBLIC", "entities": []},
        {"bookId": "animalidade", "title": "Animalidade", "rightsStatus": "UNKNOWN", "publicationMode": "NOT_PUBLIC", "entities": [{"id": "e1", "name": "Fera"}]},
        # Authorized public book
        {"bookId": "public-rules", "title": "Regras Públicas", "rightsStatus": "PUBLIC_DOMAIN", "publicationMode": "FULL_TEXT", "entities": [{"id": "e2", "name": "Regra", "category": "core_rule", "content": [{"title": "C1", "paragraphs": ["Público"]}]}]},
    ]

    public_files = projector.build(synthetic_catalog, mode="public")
    public_site_data = tmp_path / "public_site_data"
    projector.write(public_files, public_site_data, repo_root)

    server = PreviewServer(port=0, root=repo_root, public_root=public_site_data)
    server.start()

    try:
        page = browser.new_page()
        # Navigate to public catalog
        page.goto(f"http://127.0.0.1:{server.port}/?site=1&public=1#/books")
        page.wait_for_selector(".site-books-grid", timeout=10000)

        # Restricted books MUST NOT appear
        assert page.locator('a[href="#/book/animalidade"]').count() == 0
        assert page.locator('a[href="#/book/synthetic-empty"]').count() == 0

        # Only authorized public book must appear
        assert page.locator('a[href="#/book/public-rules"]').count() == 1

        # Direct navigation to restricted book route MUST NOT deliver restricted content
        page.goto(f"http://127.0.0.1:{server.port}/?site=1&public=1#/book/animalidade")
        page.wait_for_timeout(1000)
        assert page.locator(".pipeline-stepper").count() == 0
        assert "Fera" not in page.content()
    finally:
        server.stop()
```

- [ ] **Step 3: Run browser tests and confirm GREEN**
```powershell
python -m pytest tests/frontend/test_site_browser.py -q
```
Expected: All browser tests pass.

- [ ] **Step 4: Run full regression suite**
```powershell
python -m pytest tests/agents -q
node --test tests/frontend/*.test.mjs
python scripts/validate_data.py
python scripts/check_book_coverage.py
node --check docs/assets/app.js
```
Expected: All pass.

- [ ] **Step 5: Commit**
```powershell
git add tests/frontend/test_site_browser.py tests/frontend/conftest.py
git commit -m "test(browser): enforce strict assertions and public fail-closed browser test"
```

---

## Verification Plan

### Automated Tests
1. Unit tests for archive inventory loader and rights boundaries:
   `python -m pytest tests/agents/test_archive_inventory_loader.py -v`
2. Unit tests for dual-axis archive projection:
   `python -m pytest tests/agents/test_frontend_projector_archive.py -v`
3. Controlled synthetic fixture fail-closed policy tests:
   `python -m pytest tests/agents/test_frontend_policy_archive.py -v`
4. Node frontend tests for model, search, state, cards, and UI detail components:
   `node --test tests/frontend/*.test.mjs`
5. Strict Playwright browser E2E tests (including public fail-closed test):
   `python -m pytest tests/frontend/test_site_browser.py -q`
6. Global regression suite:
   `python -m pytest tests/agents -q`
   `python scripts/validate_data.py`
   `python scripts/check_book_coverage.py`
   `node --check docs/assets/app.js`

### Manual Verification
- Launch local preview server (`PreviewServer`) in `restricted_preview` mode.
- Navigate to `#/books` in browser; verify all 281 books appear in grid with responsive card layout.
- Verify that both `pipelineStatus` and `rightsStatus` badges are displayed on cards.
- Filter by status and search by book title; verify smooth client-side filtering.
- Click an unworked book card; verify clean page with 7-stage stepper (all stages pending) and empty state banner.
- Click a processed book (*Animalidade*); verify entities are displayed and stages are marked completed.
- Verify in `mode=public` that zero unworked books or restricted data appear.
