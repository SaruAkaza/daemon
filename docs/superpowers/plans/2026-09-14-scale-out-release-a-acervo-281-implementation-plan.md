# Scale-Out Release A — Acervo 281 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the Daemon Tools catalog and site projection to represent all 281 cataloged books in the restricted preview (`mode=restricted_preview`) with responsive cards, filters, sorting, and dedicated book detail pages (`#/book/:bookId`) featuring the 7-stage pipeline stepper and safe unworked state, while guaranteeing strict fail-closed exclusion in public mode (`mode=public`) without requiring the complete Batch Orchestrator.

**Architecture:** A lightweight, deterministic archive inventory loader (`ArchiveInventoryLoader`) reads the authoritative catalog manifest (`data/index/sources.json`), integrates existing certified processed book data (such as the *Animalidade* baseline in `data/entities/` and `data/books/animalidade.json`) via `load_processed_books`, and supplies canonical `BookInventoryRecord` items to `FrontendProjector`. Every book is classified across two strictly orthogonal axes: pipeline lifecycle status (`WAITING`, `RUNNING`, `BLOCKED`, `NEEDS_HUMAN_REVIEW`, `READY_FOR_HUMAN_APPROVAL`, `DONE`, `FAILED`) and legal/publication governance (`rightsStatus`: `AUTHORIZED`, `PRIVATE`, `PUBLIC_DOMAIN`, `METADATA_ONLY`, `UNKNOWN`; `publicationMode`: `FULL_TEXT`, `SUMMARY_AND_METADATA`, `METADATA_ONLY`, `NOT_PUBLIC`). Unworked books safely project with `WAITING`, `UNKNOWN`, `NOT_PUBLIC`, `currentStage = null` (rendering all 7 stages as `pending`), and entity count `0`. Modular frontend components (`site-model.mjs`, `site-search.mjs`, `site-state.mjs`, `site-ui.mjs`) render the catalog and individual book pages.

**Tech Stack:** Python 3.10+, pytest, standard library `http.server`, vanilla ES modules (`.mjs`), HTML5/CSS3, Node.js test runner (`node --test`), Playwright browser test harness (`pytest tests/frontend/test_site_browser.py`).

**Spec:** `docs/superpowers/specs/2026-09-14-scale-out-acervo-batch-ops-design.md`, commit `117b626cc1bb049f6beeb6498dfa5b7ea511e765`.

---

## Global Constraints

- **PROCESSADO != PUBLICÁVEL**: Technical pipeline completion does not authorize public disclosure.
- `restricted_preview` and `public` are runtime projector execution modes (`mode=restricted_preview` / `mode=public`), never to be confused with canonical `publicationMode`.
- **Fail-Closed Public Projection**: In `mode=public`, any book with `publicationMode == "NOT_PUBLIC"` or `rightsStatus == "UNKNOWN"` is strictly omitted from `catalog.json`, `search-index.json`, and `books/<bookId>.json`. Zero restricted metadata or content leaks to public outputs.
- **RESTRICTED_CONTENT_NEVER_ENTERS_MAIN_WORKTREE**: Restricted books (including *Animalidade*) and untracked previews are never written to `docs/` or versioned directories.
- **Canonical Inventory Authority**: `data/index/sources.json` is the sole authoritative input inventory for the 281 books (verified: `count: 281` records in file, confirmed in `pipeline.md`, `project-context.md`, `README.md`, and `catalog_loader.py`). The projection is a derived view, never a new canonical store.
- **Rights Authority Inviolability**: `rightsStatus` and `publicationMode` belong strictly to the canonical inventory/rights authority. The operational/processed overlay **never** has authority to modify or escalate rights (e.g., overlay cannot promote `UNKNOWN -> AUTHORIZED` or `NOT_PUBLIC -> FULL_TEXT`). In the absence of declared rights in `sources.json`, fallback is strictly `rightsStatus = UNKNOWN` and `publicationMode = NOT_PUBLIC`. Absence never implies authorization.
- **Processed Books Preservation**: Existing processed books (such as *Animalidade* with its 36 canonical entities in `data/entities/`) are automatically discovered by `load_processed_books` and merged, ensuring zero regression to `WAITING` or 0 entities.
- **Dual Orthogonal Axes Projected in `catalog.json`**:
  - Axis 1 (Pipeline Lifecycle): `pipelineStatus` (`WAITING`, `RUNNING`, `BLOCKED`, `NEEDS_HUMAN_REVIEW`, `READY_FOR_HUMAN_APPROVAL`, `DONE`, `FAILED`) and `currentStage` (`source`, `extraction`, `editorial`, `entities`, `relations`, `frontend`, `qa`, or `null`).
  - Axis 2 (Rights & Publication Governance): `rightsStatus` (`AUTHORIZED`, `PRIVATE`, `PUBLIC_DOMAIN`, `METADATA_ONLY`, `UNKNOWN`) and `publicationMode` (`FULL_TEXT`, `SUMMARY_AND_METADATA`, `METADATA_ONLY`, `NOT_PUBLIC`).
- **Unworked Book Stage Representation**: Books with `pipelineStatus = "WAITING"` that have never started processing are represented with `currentStage = null`. In the UI, this translates to all 7 pipeline stages (`Source` -> `Extraction` -> `Editorial` -> `Entities` -> `Relations` -> `Frontend` -> `QA`) displaying as `pending` (zero stages displayed as `active`).
- **Zero Hallucination / Zero Invention**: Unworked books strictly display 0 entities, 0 relations, and pending pipeline stages. No fabricated legal status or costs.
- **Pipeline Stepper**: The 7 stages must strictly follow: `Source` -> `Extraction` -> `Editorial` -> `Entities` -> `Relations` -> `Frontend` -> `QA`.
- **No Heavy Orchestrator Dependency**: Release A must be completely implementable and testable on its own, providing immediate user-facing value before Release B (Ops Controller) and Release C (Batch Scheduler).

---

## Interfaces and File Map

| File | Action | Responsibility |
| :--- | :--- | :--- |
| `scripts/agents/archive_inventory_loader.py` | Create | Loads 281 sources from `data/index/sources.json`, integrates processed books via `load_processed_books(data_dir)`, preserves canonical rights, and constructs `BookInventoryRecord` inputs. |
| `scripts/agents/frontend_projector.py` | Modify | Extends `catalog.json` book entries with dual-axis operational metadata (`pipelineStatus`, `rightsStatus`, `publicationMode`, `currentStage`, `entityCount`, `pageCount`, `categoryHints`, `sizeBytes`) while preserving deterministic projectionId and contract validation. |
| `scripts/agents/site_view_model.py` | Modify | Updates catalog book schema validation in `validate_projection` to enforce canonical `rightsStatus` and operational fields on catalog books. |
| `scripts/agents/frontend_policy.py` | Modify | Preserves strict fail-closed filtering; ensures default unworked books (`UNKNOWN` / `NOT_PUBLIC`) are excluded in `mode=public`. |
| `docs/assets/site-model.mjs` | Modify | Ingests extended catalog metadata and exposes helper lookup methods (`getBookMetadata(bookId)`). |
| `docs/assets/site-search.mjs` | Modify | Adds catalog filtering by `pipelineStatus`, `rightsStatus`, `publicationMode`, and `categoryHints`. |
| `docs/assets/site-state.mjs` | Modify | Manages archive catalog route parameters, active dual-axis filters (`bookFilters`), and sorting preferences. |
| `docs/assets/site-ui.mjs` | Modify | Implements responsive 281-book grid (`renderBooksView`), stage state helper (`getStageStates`), and individual book detail view (`renderBookDetailView`) with 7-stage visual stepper. |
| `docs/assets/styles.css` | Modify | Styles for book cards, dual-axis badges (`.site-badge-pipeline`, `.site-badge-rights`, `.site-badge-pub`), 7-stage stepper (`.pending`, `.active`, `.done`), and responsive grid layout. |
| `tests/agents/test_archive_inventory_loader.py` | Create | Unit tests for `ArchiveInventoryLoader` verifying 281 books loading, rights overlay rejection, unworked `currentStage=None`, and processed book retention. |
| `tests/agents/test_frontend_projector_archive.py` | Create | Unit tests verifying dual-axis projection in `restricted_preview` and contract validation. |
| `tests/agents/test_frontend_policy_archive.py` | Create | Synthetic fixture matrix tests for public mode fail-closed policy, plus real inventory leak scan. |
| `tests/frontend/site-model.test.mjs` | Modify | Node test runner tests for extended catalog metadata and caching. |
| `tests/frontend/site-search.test.mjs` | Modify | Node test runner tests for dual-axis filtering and sorting. |
| `tests/frontend/site-ui-books.test.mjs` | Create | Node test runner tests verifying books view controls and dual-axis card badges. |
| `tests/frontend/site-ui-book-detail.test.mjs` | Create | Node test runner tests verifying stepper states (all pending for unworked books, active for running, done for finished). |
| `tests/frontend/test_site_browser.py` | Modify | Playwright browser tests for `#/books` (281 cards, filters, search) and `#/book/:bookId` (stepper, empty state, strict assertions). |

---

## Tasks

### Task 1: Archive Inventory Loader & Rights Boundary (`scripts/agents/archive_inventory_loader.py`)

**Files:**
- Create: `scripts/agents/archive_inventory_loader.py`
- Create: `tests/agents/test_archive_inventory_loader.py`

**Interfaces:**
```python
def load_processed_books(data_dir: Path | str | None = None) -> dict[str, dict[str, Any]]: ...

class ArchiveInventoryLoader:
    def __init__(self, sources_path: Path | str | None = None, data_dir: Path | str | None = None) -> None: ...
    def load_inventory(self, processed_books: dict[str, dict[str, Any]] | None = None) -> list[dict[str, Any]]: ...
    def get_book_by_id(self, book_id: str, processed_books: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]: ...
```

- [ ] **Step 1: Write failing test**
Create `tests/agents/test_archive_inventory_loader.py`:
```python
from pathlib import Path
import pytest
from scripts.agents.archive_inventory_loader import ArchiveInventoryLoader, load_processed_books

def test_archive_inventory_loader_loads_281_books():
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

def test_archive_inventory_loader_integrates_animalidade_without_regression():
    loader = ArchiveInventoryLoader()
    books = loader.load_inventory()
    anim = next(b for b in books if b["bookId"] == "animalidade")
    # Animalidade has extracted entities in data/entities/ and must not regress to WAITING with 0 entities
    assert anim["pipelineStatus"] in ("READY_FOR_HUMAN_APPROVAL", "DONE")
    assert len(anim["entities"]) > 0
    assert anim["currentStage"] in ("qa", "frontend")
    # Rights must remain strictly canonical
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
            "entities": [{"id": "ent-1", "name": "Killer"}],
        }
    }
    books = loader.load_inventory(processed_books=hostile_overlay)
    sample = next(b for b in books if b["bookId"] == "4killers")
    # Operational fields applied:
    assert sample["pipelineStatus"] == "DONE"
    assert sample["currentStage"] == "qa"
    assert len(sample["entities"]) == 1
    # Rights escalation strictly rejected; canonical values preserved:
    assert sample["rightsStatus"] == "UNKNOWN"
    assert sample["publicationMode"] == "NOT_PUBLIC"

def test_archive_inventory_loader_unworked_book_has_none_current_stage():
    loader = ArchiveInventoryLoader()
    sample = loader.get_book_by_id("a-assassina")
    assert sample["pipelineStatus"] == "WAITING"
    assert sample["currentStage"] is None
    assert sample["entities"] == []
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

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCES_PATH = ROOT / "data" / "index" / "sources.json"
DEFAULT_DATA_DIR = ROOT / "data"

def load_processed_books(data_dir: Path | str | None = None) -> dict[str, dict[str, Any]]:
    d_dir = Path(data_dir).resolve() if data_dir else DEFAULT_DATA_DIR
    entities_dir = d_dir / "entities"
    books_dir = d_dir / "books"

    processed: dict[str, dict[str, Any]] = {}
    if not entities_dir.exists():
        return processed

    # Map entities by source
    entities_by_source: dict[str, list[dict[str, Any]]] = {}
    for ef in sorted(entities_dir.glob("*.json")):
        if ef.name in ("relations.json", "unresolved-relations.json"):
            continue
        try:
            with open(ef, "r", encoding="utf-8") as f:
                content = json.load(f)
            items = content if isinstance(content, list) else [content]
            for it in items:
                if isinstance(it, dict):
                    src = it.get("source")
                    if src:
                        entities_by_source.setdefault(src, []).append(it)
        except Exception:
            continue

    # Load relations
    relations_by_source: dict[str, list[dict[str, Any]]] = {}
    rel_file = entities_dir / "relations.json"
    if rel_file.exists():
        try:
            with open(rel_file, "r", encoding="utf-8") as f:
                rcontent = json.load(f)
            ritems = rcontent if isinstance(rcontent, list) else [rcontent]
            for r in ritems:
                if isinstance(r, dict):
                    src = r.get("source", "animalidade")
                    relations_by_source.setdefault(src, []).append(r)
        except Exception:
            pass

    for bid, ents in entities_by_source.items():
        processed[bid] = {
            "bookId": bid,
            "pipelineStatus": "READY_FOR_HUMAN_APPROVAL",
            "currentStage": "qa",
            "entities": ents,
            "relations": relations_by_source.get(bid, []),
            "groups": [],
        }

    return processed

class ArchiveInventoryLoader:
    def __init__(self, sources_path: Path | str | None = None, data_dir: Path | str | None = None) -> None:
        self.sources_path = Path(sources_path).resolve() if sources_path else DEFAULT_SOURCES_PATH
        self.data_dir = Path(data_dir).resolve() if data_dir else DEFAULT_DATA_DIR

    def load_inventory(self, processed_books: dict[str, dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        if not self.sources_path.exists():
            raise FileNotFoundError(f"Sources manifest not found: {self.sources_path}")

        with open(self.sources_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        sources = data.get("sources", [])
        overlay_map = processed_books if processed_books is not None else load_processed_books(self.data_dir)
        result = []

        for src in sources:
            bid = src["id"]
            # Canonical rights and inventory authority
            canonical_title = src.get("title", bid)
            canonical_rights = src.get("rightsStatus") or "UNKNOWN"
            canonical_pub = src.get("publicationMode") or "NOT_PUBLIC"

            # Check if processed data exists
            if bid in overlay_map:
                overlay = overlay_map[bid]
                pipeline_status = overlay.get("pipelineStatus", "READY_FOR_HUMAN_APPROVAL")
                current_stage = overlay.get("currentStage", "qa")
                entities = list(overlay.get("entities", []))
                relations = list(overlay.get("relations", []))
                groups = list(overlay.get("groups", []))
            else:
                pipeline_status = "WAITING"
                current_stage = None
                entities = []
                relations = []
                groups = []

            # Construct canonical BookInventoryRecord
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

    def get_book_by_id(self, book_id: str, processed_books: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
        all_books = self.load_inventory(processed_books)
        for b in all_books:
            if b["bookId"] == book_id:
                return b
        raise KeyError(f"Book '{book_id}' not found in archive inventory")
```

- [ ] **Step 4: Run test and confirm GREEN**
```powershell
python -m pytest tests/agents/test_archive_inventory_loader.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Run focused regressions**
```powershell
python -m pytest tests/agents -q
```
Expected: All tests pass.

- [ ] **Step 6: Commit**
```powershell
git add scripts/agents/archive_inventory_loader.py tests/agents/test_archive_inventory_loader.py
git commit -m "feat(archive): implement archive inventory loader with rights boundary and processed books integration"
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
    assert "search-index.json" in files
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

    # Check processed entry (animalidade)
    anim = next(b for b in catalog["books"] if b["bookId"] == "animalidade")
    assert anim["pipelineStatus"] in ("READY_FOR_HUMAN_APPROVAL", "DONE")
    assert anim["rightsStatus"] == "UNKNOWN"
    assert anim["publicationMode"] == "NOT_PUBLIC"
    assert anim["entityCount"] > 0

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
        for b in allowed_books:
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
python -m pytest tests/agents/test_site_view_model.py tests/agents/test_frontend_projector.py tests/agents/test_frontend_projector_archive.py -v
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
        # 3. PUBLIC_DOMAIN + FULL_TEXT -> permitted
        {"bookId": "s-pd", "title": "S Public Domain", "rightsStatus": "PUBLIC_DOMAIN", "publicationMode": "FULL_TEXT", "entities": []},
        # 4. AUTHORIZED + FULL_TEXT -> permitted
        {"bookId": "s-auth", "title": "S Authorized", "rightsStatus": "AUTHORIZED", "publicationMode": "FULL_TEXT", "entities": []},
        # 5. METADATA_ONLY + METADATA_ONLY -> permitted
        {"bookId": "s-meta", "title": "S Metadata", "rightsStatus": "METADATA_ONLY", "publicationMode": "METADATA_ONLY", "entities": []},
    ]

    files = projector.build(synthetic_books, mode="public")
    catalog = files["catalog.json"]
    projected_ids = {b["bookId"] for b in catalog["books"]}

    # Excluded:
    assert "s-unknown" not in projected_ids
    assert "s-private" not in projected_ids

    # Permitted:
    assert "s-pd" in projected_ids
    assert "s-auth" in projected_ids
    assert "s-meta" in projected_ids
    assert len(catalog["books"]) == 3
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

- [ ] **Step 3: Run full agent regressions**
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

### Task 4: Frontend Dual-Axis Filtering, Sorting & Metadata Retrieval (`site-model.mjs`, `site-search.mjs`, `site-state.mjs`)

**Files:**
- Modify: `docs/assets/site-model.mjs`
- Modify: `docs/assets/site-search.mjs`
- Modify: `docs/assets/site-state.mjs`
- Modify: `tests/frontend/site-model.test.mjs`
- Modify: `tests/frontend/site-search.test.mjs`

**Interfaces:**
- `site-model.mjs`: `getBookMetadata(bookId)` returns catalog entry with `pipelineStatus`, `rightsStatus`, `publicationMode`, `currentStage`.
- `site-search.mjs`: `filterBooks(books, { query, pipelineStatus, rightsStatus, publicationMode, categoryHint, sortBy })` filters by both axes.
- `site-state.mjs`: manages `bookFilters` (`pipelineStatus`, `rightsStatus`, `publicationMode`).

- [ ] **Step 1: Write failing tests**
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
node --test tests/frontend/site-search.test.mjs tests/frontend/site-model.test.mjs
```
Expected: Failures on `rightsStatus` filtering and `getBookMetadata`.

- [ ] **Step 3: Implement minimal code**
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
In `docs/assets/site-state.mjs`:
Update state initializer to include `bookFilters: { query: '', pipelineStatus: 'all', rightsStatus: 'all', publicationMode: 'all', sortBy: 'title_asc' }`.

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
git add docs/assets/site-model.mjs docs/assets/site-search.mjs docs/assets/site-state.mjs tests/frontend/site-model.test.mjs tests/frontend/site-search.test.mjs
git commit -m "feat(frontend): implement dual-axis catalog filtering, sorting, and metadata retrieval"
```

---

### Task 5: Acervo 281 UI — Cards, Dual-Axis Badges, and Filter Controls (`site-ui.mjs`, `styles.css`)

**Files:**
- Create: `tests/frontend/site-ui-books.test.mjs`
- Modify: `docs/assets/site-ui.mjs`
- Modify: `docs/assets/styles.css`

**Interfaces:**
- `createBookCard(book)` in `site-ui.mjs`: builds `.site-book-card` with title, `.site-badge-pipeline` (`data-status`), `.site-badge-rights` (`data-rights`), and `.site-badge-pub` (`data-mode`).
- `renderBooksView()` in `site-ui.mjs`: builds the complete responsive catalog view with dual-axis dropdowns.

- [ ] **Step 1: Write failing test**
Create `tests/frontend/site-ui-books.test.mjs`:
```javascript
import test from 'node:test';
import assert from 'node:assert/strict';
import { createBookCard } from '../../docs/assets/site-ui.mjs';

test('createBookCard renders dual-axis badges for pipeline and rights', () => {
  const book = {
    bookId: 'animalidade',
    title: 'Animalidade',
    pipelineStatus: 'READY_FOR_HUMAN_APPROVAL',
    rightsStatus: 'UNKNOWN',
    publicationMode: 'NOT_PUBLIC',
    currentStage: 'qa',
    entityCount: 36,
    pageCount: 13,
  };

  const cardHtml = createBookCard(book);
  assert.match(cardHtml, /site-badge-pipeline/);
  assert.match(cardHtml, /data-status="READY_FOR_HUMAN_APPROVAL"/);
  assert.match(cardHtml, /site-badge-rights/);
  assert.match(cardHtml, /data-rights="UNKNOWN"/);
  assert.match(cardHtml, /site-badge-pub/);
  assert.match(cardHtml, /data-mode="NOT_PUBLIC"/);
  assert.match(cardHtml, /36 entidades/);
});
```

- [ ] **Step 2: Run test and confirm RED**
```powershell
node --test tests/frontend/site-ui-books.test.mjs
```
Expected: `TypeError: createBookCard is not a function`.

- [ ] **Step 3: Implement minimal code in `site-ui.mjs` and `styles.css`**
Export `createBookCard` in `docs/assets/site-ui.mjs`:
```javascript
export function createBookCard(b) {
  const stageText = b.currentStage ? `Estágio: ${b.currentStage}` : 'Não iniciado';
  return `
    <div class="site-book-card" data-book-id="${b.bookId}">
      <a href="#/book/${b.bookId}" class="site-book-title">${b.title}</a>
      <div class="site-card-badges">
        <span class="site-badge site-badge-pipeline" data-status="${b.pipelineStatus}">${b.pipelineStatus}</span>
        <span class="site-badge site-badge-rights" data-rights="${b.rightsStatus}">${b.rightsStatus}</span>
        <span class="site-badge site-badge-pub" data-mode="${b.publicationMode}">${b.publicationMode}</span>
      </div>
      <div class="site-card-meta">
        <span class="site-card-stage">${stageText}</span>
        <span class="site-card-count">${b.entityCount || 0} entidades</span>
        <span class="site-card-pages">${b.pageCount || 0} págs</span>
      </div>
    </div>
  `;
}
```
Update `renderBooksView` to utilize `createBookCard` and add dropdown filters for `pipelineStatus` and `rightsStatus`.
Add badge styling in `docs/assets/styles.css`:
```css
.site-badge-rights[data-rights="AUTHORIZED"],
.site-badge-rights[data-rights="PUBLIC_DOMAIN"] { background: #1b5e20; color: #fff; }
.site-badge-rights[data-rights="UNKNOWN"] { background: #424242; color: #e0e0e0; }
.site-badge-pipeline[data-status="WAITING"] { background: #37474f; color: #cfd8dc; }
.site-badge-pipeline[data-status="READY_FOR_HUMAN_APPROVAL"] { background: #e65100; color: #fff; }
.site-badge-pipeline[data-status="DONE"] { background: #2e7d32; color: #fff; }
```

- [ ] **Step 4: Run test and confirm GREEN**
```powershell
node --test tests/frontend/site-ui-books.test.mjs
```
Expected: 1 passed.

- [ ] **Step 5: Run focused regressions**
```powershell
node --test tests/frontend/*.test.mjs
node --check docs/assets/app.js
```
Expected: All pass.

- [ ] **Step 6: Commit**
```powershell
git add docs/assets/site-ui.mjs docs/assets/styles.css tests/frontend/site-ui-books.test.mjs
git commit -m "feat(frontend): implement dual-axis book cards and catalog filter controls"
```

---

### Task 6: 7-Stage Pipeline Stepper & Unworked Book Page (`#/book/:bookId`)

**Files:**
- Create: `tests/frontend/site-ui-book-detail.test.mjs`
- Modify: `docs/assets/site-ui.mjs`
- Modify: `docs/assets/styles.css`

**Interfaces:**
- `getStageStates(pipelineStatus: string, currentStage: string | null)`: returns list of `{ stage, state }` where state is `'pending'`, `'active'`, or `'done'`.
- `renderBookDetailView(bookId)`: renders 7-stage visual stepper, metadata card, and empty state banner when `entityCount === 0`.

- [ ] **Step 1: Write failing test**
Create `tests/frontend/site-ui-book-detail.test.mjs`:
```javascript
import test from 'node:test';
import assert from 'node:assert/strict';
import { getStageStates } from '../../docs/assets/site-ui.mjs';

test('getStageStates returns all 7 stages as pending for unworked book', () => {
  const stages = getStageStates('WAITING', null);
  assert.equal(stages.length, 7);
  for (const s of stages) {
    assert.equal(s.state, 'pending');
  }
});

test('getStageStates marks stages correctly for in-progress and completed books', () => {
  // In-progress at editorial
  const inProgress = getStageStates('RUNNING', 'editorial');
  assert.equal(inProgress.find(s => s.stage === 'Source').state, 'done');
  assert.equal(inProgress.find(s => s.stage === 'Extraction').state, 'done');
  assert.equal(inProgress.find(s => s.stage === 'Editorial').state, 'active');
  assert.equal(inProgress.find(s => s.stage === 'Entities').state, 'pending');
  assert.equal(inProgress.find(s => s.stage === 'QA').state, 'pending');

  // Completed book
  const doneStages = getStageStates('DONE', 'qa');
  for (const s of doneStages) {
    assert.equal(s.state, 'done');
  }
});
```

- [ ] **Step 2: Run test and confirm RED**
```powershell
node --test tests/frontend/site-ui-book-detail.test.mjs
```
Expected: `TypeError: getStageStates is not a function`.

- [ ] **Step 3: Implement minimal code in `site-ui.mjs` and `styles.css`**
Export `getStageStates` in `docs/assets/site-ui.mjs`:
```javascript
export const PIPELINE_STAGES = [
  'Source', 'Extraction', 'Editorial', 'Entities', 'Relations', 'Frontend', 'QA'
];

export function getStageStates(pipelineStatus, currentStage) {
  if (pipelineStatus === 'DONE') {
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
  return PIPELINE_STAGES.map((s, idx) => {
    if (idx < curIdx) return { stage: s, state: 'done' };
    if (idx === curIdx) return { stage: s, state: 'active' };
    return { stage: s, state: 'pending' };
  });
}
```
Update `renderBookDetailView` in `site-ui.mjs` to render the `.pipeline-stepper` using `getStageStates`, and when `bookData.entities.length === 0`, display the empty state banner:
```javascript
`<div class="site-book-empty-state">
  <p>Nenhuma entidade processada para este livro ainda. O livro encontra-se na fila de processamento.</p>
</div>`
```
Add stepper styling in `docs/assets/styles.css`:
```css
.pipeline-stepper { display: flex; gap: 8px; margin: 16px 0; }
.stepper-step { padding: 6px 12px; border-radius: 4px; font-size: 0.85rem; font-weight: 500; }
.stepper-step.pending { background: #263238; color: #78909c; border: 1px dashed #455a64; }
.stepper-step.active { background: #0277bd; color: #fff; animation: pulse 2s infinite; }
.stepper-step.done { background: #2e7d32; color: #fff; }
```

- [ ] **Step 4: Run test and confirm GREEN**
```powershell
node --test tests/frontend/site-ui-book-detail.test.mjs
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
git add docs/assets/site-ui.mjs docs/assets/styles.css tests/frontend/site-ui-book-detail.test.mjs
git commit -m "feat(frontend): implement 7-stage pipeline stepper and unworked book detail view"
```

---

### Task 7: Strict Browser E2E Tests for Acervo 281 & Regression Suite

**Files:**
- Modify: `tests/frontend/test_site_browser.py`
- Modify: `tests/frontend/conftest.py`

**Interfaces:**
- Strict browser tests in `tests/frontend/test_site_browser.py` without conditional passes (`if count > 0:` is strictly forbidden):
  - Strictly asserts unworked book card exists.
  - Strictly asserts navigation to `#/book/:bookId`.
  - Strictly asserts all 7 stepper steps are `.pending` for unworked book.
  - Strictly asserts empty state message is present.
  - Strictly asserts zero unworked books or restricted data leak in public mode.

- [ ] **Step 1: Update `tests/frontend/conftest.py` with synthetic multi-book catalog**
Add a second synthetic book with 0 entities, `pipelineStatus="WAITING"`, `currentStage=None`:
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

    # Strict assertion: unworked book link MUST exist (no if statement!)
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
git commit -m "test(browser): enforce strict assertions for archive catalog and 7-stage stepper"
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
4. Node frontend tests for model, search, and UI components:
   `node --test tests/frontend/*.test.mjs`
5. Strict Playwright browser E2E tests:
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
