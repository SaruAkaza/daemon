# Scale-Out Release A — Acervo 281 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the Daemon Tools catalog and site projection to represent all 281 cataloged books in the restricted preview (`mode=restricted_preview`) with responsive cards, filters, sorting, and dedicated book detail pages (`#/book/:bookId`) featuring the 7-stage pipeline stepper and safe unworked state, while guaranteeing strict fail-closed exclusion in public mode (`mode=public`) without requiring the complete Batch Orchestrator.

**Architecture:** A lightweight, deterministic archive inventory loader (`ArchiveInventoryLoader`) reads the authoritative catalog manifest (`data/index/sources.json`), integrates known processed books from durable stores and runtime, and supplies canonical `ApprovedBook` records to `FrontendProjector`. Every book is classified across two strictly orthogonal axes: pipeline lifecycle status (`WAITING`, `RUNNING`, `BLOCKED`, `NEEDS_HUMAN_REVIEW`, `READY_FOR_HUMAN_APPROVAL`, `DONE`, `FAILED`) and legal/publication governance (`rightsStatus`: `AUTHORIZED`, `PRIVATE`, `PUBLIC_DOMAIN`, `METADATA_ONLY`, `UNKNOWN`; `publicationMode`: `FULL_TEXT`, `SUMMARY_AND_METADATA`, `METADATA_ONLY`, `NOT_PUBLIC`). Unworked books safely project with `WAITING`, `UNKNOWN`, `NOT_PUBLIC`, and entity count `0`. Modular frontend components (`site-model.mjs`, `site-search.mjs`, `site-state.mjs`, `site-ui.mjs`) render the catalog and individual book pages.

**Tech Stack:** Python 3.10+, pytest, standard library `http.server`, vanilla ES modules (`.mjs`), HTML5/CSS3, Node.js test runner (`node --test`), Playwright browser test harness (`pytest tests/frontend/test_site_browser.py`).

**Spec:** `docs/superpowers/specs/2026-09-14-scale-out-acervo-batch-ops-design.md`, commit `117b626cc1bb049f6beeb6498dfa5b7ea511e765`.

---

## Global Constraints

- **PROCESSADO != PUBLICÁVEL**: Technical pipeline completion does not authorize public disclosure.
- `restricted_preview` and `public` are runtime projector execution modes (`mode=restricted_preview` / `mode=public`), never to be confused with canonical `publicationMode`.
- **Fail-Closed Public Projection**: In `mode=public`, any book with `publicationMode == "NOT_PUBLIC"` or `rightsStatus == "UNKNOWN"` is strictly omitted from `catalog.json`, `search-index.json`, and `books/<bookId>.json`. Zero restricted metadata or content leaks to public outputs.
- **RESTRICTED_CONTENT_NEVER_ENTERS_MAIN_WORKTREE**: Restricted books (including *Animalidade*) and untracked previews are never written to `docs/` or versioned directories.
- **Canonical Inventory Authority**: `data/index/sources.json` is the sole authoritative input inventory for the 281 books. The projection is a derived view, never a new canonical store.
- **Dual Orthogonal Axes**:
  - Pipeline Status: `WAITING`, `RUNNING`, `BLOCKED`, `NEEDS_HUMAN_REVIEW`, `READY_FOR_HUMAN_APPROVAL`, `DONE`, `FAILED`.
  - Rights Status: `AUTHORIZED`, `PRIVATE`, `PUBLIC_DOMAIN`, `METADATA_ONLY`, `UNKNOWN`.
  - Publication Mode: `FULL_TEXT`, `SUMMARY_AND_METADATA`, `METADATA_ONLY`, `NOT_PUBLIC`.
- **Zero Hallucination / Zero Invention**: Unworked books strictly display 0 entities, 0 relations, and pending pipeline stages. No fabricated legal status or costs.
- **Pipeline Stepper**: The 7 stages must strictly follow: `Source` -> `Extraction` -> `Editorial` -> `Entities` -> `Relations` -> `Frontend` -> `QA`.
- **No Heavy Orchestrator Dependency**: Release A must be completely implementable and testable on its own, providing immediate user-facing value before Release B (Ops Controller) and Release C (Batch Scheduler).

---

## Interfaces and File Map

| File | Action | Responsibility |
| :--- | :--- | :--- |
| `scripts/agents/archive_inventory_loader.py` | Create | Loads 281 sources from `data/index/sources.json`, overlays known completed jobs/entities, and constructs canonical `ApprovedBook` inputs. |
| `scripts/agents/frontend_projector.py` | Modify | Extends `catalog.json` book entries with archive metadata (`pipelineStatus`, `currentStage`, `entityCount`, `pageCount`, `categoryHints`, `sizeBytes`) while preserving deterministic projectionId and contract validation. |
| `scripts/agents/site_view_model.py` | Modify | Updates catalog book schema validation in `validate_projection` to support optional operational fields on catalog books. |
| `scripts/agents/frontend_policy.py` | Modify | Preserves strict fail-closed filtering; ensures default unworked books (`UNKNOWN` / `NOT_PUBLIC`) are excluded in `mode=public`. |
| `docs/assets/site-model.mjs` | Modify | Ingests extended catalog metadata and exposes helper lookup methods (`getBook(bookId)`, `getBooks()`). |
| `docs/assets/site-search.mjs` | Modify | Adds catalog filtering by `pipelineStatus`, `publicationMode`, and `categoryHints`. |
| `docs/assets/site-state.mjs` | Modify | Manages archive catalog route parameters, active filters, and sorting preferences. |
| `docs/assets/site-ui.mjs` | Modify | Implements responsive 281-book grid (`renderBooksView`) and individual book detail view (`renderBookDetailView`) with 7-stage visual stepper. |
| `docs/assets/styles.css` | Modify | Styles for book cards, pipeline badges, publication badges, 7-stage stepper, and responsive grid layout. |
| `tests/agents/test_archive_inventory_loader.py` | Create | Unit tests for `ArchiveInventoryLoader` verifying 281 books loading, default states, and overlay resolution. |
| `tests/agents/test_frontend_projector_archive.py` | Create | Unit tests verifying 281 books projection in `restricted_preview` and fail-closed zero-leakage in `public`. |
| `tests/agents/test_frontend_policy_archive.py` | Create | Exhaustive rights/publication matrix tests on archive inventory. |
| `tests/frontend/site-model.test.mjs` | Modify | Node test runner tests for extended catalog metadata and caching. |
| `tests/frontend/site-search.test.mjs` | Modify | Node test runner tests for archive book filtering and sorting. |
| `tests/frontend/test_site_browser.py` | Modify | Playwright browser tests for `#/books` (281 cards, filters, search) and `#/book/:bookId` (stepper, empty state). |

---

## Tasks

### Task 1: Archive Inventory Loader (`scripts/agents/archive_inventory_loader.py`)

**Files:**
- Create: `scripts/agents/archive_inventory_loader.py`
- Create: `tests/agents/test_archive_inventory_loader.py`

**Interfaces:**
```python
class ArchiveInventoryLoader:
    def __init__(self, sources_path: Path | str | None = None, jobs_dir: Path | str | None = None) -> None: ...
    def load_inventory(self, processed_books: dict[str, dict[str, Any]] | None = None) -> list[dict[str, Any]]: ...
    def get_book_by_id(self, book_id: str, processed_books: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]: ...
```

- [ ] **Step 1: Write failing test**
Create `tests/agents/test_archive_inventory_loader.py`:
```python
from pathlib import Path
import pytest
from scripts.agents.archive_inventory_loader import ArchiveInventoryLoader

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
    assert sample["currentStage"] == "source"
    assert sample["pageCount"] == 8

def test_archive_inventory_loader_overlays_processed_book():
    loader = ArchiveInventoryLoader()
    overlay = {
        "animalidade": {
            "bookId": "animalidade",
            "title": "animalidade",
            "pipelineStatus": "DONE",
            "rightsStatus": "UNKNOWN",
            "publicationMode": "NOT_PUBLIC",
            "currentStage": "qa",
            "entities": [{"id": "ent-1", "name": "Garras", "category": "character_option"}],
            "relations": [],
        }
    }
    books = loader.load_inventory(processed_books=overlay)
    assert len(books) == 281
    anim = next(b for b in books if b["bookId"] == "animalidade")
    assert anim["pipelineStatus"] == "DONE"
    assert anim["currentStage"] == "qa"
    assert len(anim["entities"]) == 1
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
DEFAULT_JOBS_DIR = ROOT / "coordination" / "jobs"

class ArchiveInventoryLoader:
    def __init__(self, sources_path: Path | str | None = None, jobs_dir: Path | str | None = None) -> None:
        self.sources_path = Path(sources_path).resolve() if sources_path else DEFAULT_SOURCES_PATH
        self.jobs_dir = Path(jobs_dir).resolve() if jobs_dir else DEFAULT_JOBS_DIR

    def load_inventory(self, processed_books: dict[str, dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        if not self.sources_path.exists():
            raise FileNotFoundError(f"Sources manifest not found: {self.sources_path}")

        with open(self.sources_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        sources = data.get("sources", [])
        result = []
        overlay_map = processed_books or {}

        for src in sources:
            bid = src["id"]
            if bid in overlay_map:
                item = dict(overlay_map[bid])
                # Ensure core metadata from sources is retained if not present in overlay
                item.setdefault("path", src.get("path", ""))
                item.setdefault("extension", src.get("extension", ""))
                item.setdefault("sizeBytes", src.get("sizeBytes", 0))
                item.setdefault("sha256", src.get("sha256", ""))
                item.setdefault("categoryHints", src.get("categoryHints", []))
                item.setdefault("pageCount", src.get("pageCount", 0))
                result.append(item)
            else:
                result.append({
                    "bookId": bid,
                    "title": src.get("title", bid),
                    "pipelineStatus": "WAITING",
                    "rightsStatus": "UNKNOWN",
                    "publicationMode": "NOT_PUBLIC",
                    "currentStage": "source",
                    "path": src.get("path", ""),
                    "extension": src.get("extension", ""),
                    "sizeBytes": src.get("sizeBytes", 0),
                    "sha256": src.get("sha256", ""),
                    "categoryHints": src.get("categoryHints", []),
                    "pageCount": src.get("pageCount", 0),
                    "entities": [],
                    "relations": [],
                    "groups": [],
                })

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
Expected: 2 passed.

- [ ] **Step 5: Run focused regressions**
```powershell
python -m pytest tests/agents -q
```
Expected: All tests pass.

- [ ] **Step 6: Commit**
```powershell
git add scripts/agents/archive_inventory_loader.py tests/agents/test_archive_inventory_loader.py
git commit -m "feat(archive): implement archive inventory loader for 281 cataloged books"
```

---

### Task 2: Site View Model & Frontend Projector Extension for Archive Metadata

**Files:**
- Modify: `scripts/agents/site_view_model.py`
- Modify: `scripts/agents/frontend_projector.py`
- Create: `tests/agents/test_frontend_projector_archive.py`

**Interfaces:**
- `FrontendProjector.build(books: list[dict[str, Any]], mode: str) -> dict[str, dict[str, Any]]` includes operational catalog fields: `pipelineStatus`, `currentStage`, `entityCount`, `pageCount`, `categoryHints`, `sizeBytes`.
- `validate_projection(files: dict[str, dict[str, Any]]) -> None` validates that optional operational fields, when present in `catalog.json` books, conform to expected types.

- [ ] **Step 1: Write failing test**
Create `tests/agents/test_frontend_projector_archive.py`:
```python
import pytest
from scripts.agents.archive_inventory_loader import ArchiveInventoryLoader
from scripts.agents.frontend_projector import FrontendProjector
from scripts.agents.site_view_model import validate_projection

def test_frontend_projector_projects_281_books_in_restricted_preview():
    loader = ArchiveInventoryLoader()
    books = loader.load_inventory()
    projector = FrontendProjector()

    files = projector.build(books, mode="restricted_preview")

    assert "catalog.json" in files
    assert "search-index.json" in files
    catalog = files["catalog.json"]
    assert len(catalog["books"]) == 281

    # Check 4killers entry in catalog
    fk = next(b for b in catalog["books"] if b["bookId"] == "4killers")
    assert fk["pipelineStatus"] == "WAITING"
    assert fk["currentStage"] == "source"
    assert fk["entityCount"] == 0
    assert fk["pageCount"] == 8
    assert "books/4killers.json" in files

    # Verify book file
    fk_file = files["books/4killers.json"]
    assert fk_file["book"]["bookId"] == "4killers"
    assert fk_file["entities"] == []
    assert fk_file["relations"] == []

    # Verify contract validation passes
    validate_projection(files)
```

- [ ] **Step 2: Run test and confirm RED**
```powershell
python -m pytest tests/agents/test_frontend_projector_archive.py -v
```
Expected: Failure on assertion `pipelineStatus` or `entityCount` missing in `catalog.json` book entry.

- [ ] **Step 3: Implement minimal code**
Update `scripts/agents/frontend_projector.py` around Step 7 (building `catalog_books`):
```python
        # Step 7: Build catalog books metadata
        catalog_books: list[dict[str, Any]] = []
        for b in allowed_books:
            cat_entry = {
                "bookId": b["bookId"],
                "title": b["title"],
                "publicationMode": b["publicationMode"],
                "path": f"books/{b['bookId']}.json",
                "groups": b.get("groups", []),
                "pipelineStatus": b.get("pipelineStatus", "WAITING"),
                "currentStage": b.get("currentStage", "source"),
                "entityCount": len(b.get("entities", [])),
                "pageCount": b.get("pageCount", 0),
                "categoryHints": list(b.get("categoryHints", [])),
                "sizeBytes": b.get("sizeBytes", 0),
            }
            catalog_books.append(cat_entry)
        catalog_books.sort(key=lambda b: b["bookId"])
```
Update `scripts/agents/site_view_model.py` in `validate_projection` book loop to allow optional archive fields:
```python
        pipeline_status = book.get("pipelineStatus")
        if pipeline_status is not None and not isinstance(pipeline_status, str):
            raise ProjectionError(f"Catalog book '{bid}' has invalid pipelineStatus")
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
git commit -m "feat(projector): enrich catalog with archive operational metadata"
```

---

### Task 3: Fail-Closed Public Protection Test Harness for Archive 281

**Files:**
- Create: `tests/agents/test_frontend_policy_archive.py`

**Interfaces:**
- Test suite validating that `FrontendProjector.build(books, mode="public")` strictly omits all 281 unapproved books, never leaks file paths, and only projects authorized public combinations.

- [ ] **Step 1: Write test suite**
Create `tests/agents/test_frontend_policy_archive.py`:
```python
import pytest
from scripts.agents.archive_inventory_loader import ArchiveInventoryLoader
from scripts.agents.frontend_projector import FrontendProjector
from scripts.agents.site_view_model import validate_projection

def test_archive_public_mode_completely_excludes_unworked_books():
    loader = ArchiveInventoryLoader()
    books = loader.load_inventory()
    projector = FrontendProjector()

    files = projector.build(books, mode="public")

    catalog = files["catalog.json"]
    # Since none of the 281 raw books have AUTHORIZED / FULL_TEXT or METADATA_ONLY,
    # public catalog must contain exactly 0 books
    assert len(catalog["books"]) == 0
    assert len(files["search-index.json"]["entries"]) == 0
    # Exactly catalog.json and search-index.json exist, zero books/<bookId>.json
    assert set(files.keys()) == {"catalog.json", "search-index.json"}
    validate_projection(files)

def test_archive_public_mode_permits_only_explicitly_authorized_books():
    loader = ArchiveInventoryLoader()
    books = loader.load_inventory()

    # Artificially authorize one book for public testing
    books[0]["rightsStatus"] = "PUBLIC_DOMAIN"
    books[0]["publicationMode"] = "FULL_TEXT"

    projector = FrontendProjector()
    files = projector.build(books, mode="public")

    catalog = files["catalog.json"]
    assert len(catalog["books"]) == 1
    assert catalog["books"][0]["bookId"] == books[0]["bookId"]
    assert f"books/{books[0]['bookId']}.json" in files
    validate_projection(files)
```

- [ ] **Step 2: Run test and confirm GREEN (verifying existing policy is already strict)**
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
git commit -m "test(policy): verify fail-closed public exclusion across 281 archive books"
```

---

### Task 4: Frontend Catalog Model & Search Updates (`site-model.mjs`, `site-search.mjs`, `site-state.mjs`)

**Files:**
- Modify: `docs/assets/site-model.mjs`
- Modify: `docs/assets/site-search.mjs`
- Modify: `docs/assets/site-state.mjs`
- Modify: `tests/frontend/site-model.test.mjs`
- Modify: `tests/frontend/site-search.test.mjs`

**Interfaces:**
- `site-model.mjs`: `getBookMetadata(bookId)` returns catalog metadata including `pipelineStatus`, `currentStage`, `entityCount`, `pageCount`, `categoryHints`.
- `site-search.mjs`: `filterBooks(books, { query, pipelineStatus, publicationMode, categoryHint, sortBy })` filters and sorts archive books deterministically.
- `site-state.mjs`: manages filter states for books catalog (`bookFilters`).

- [ ] **Step 1: Write failing test**
Update `tests/frontend/site-search.test.mjs`:
```javascript
import test from 'node:test';
import assert from 'node:assert/strict';
import { filterBooks } from '../../docs/assets/site-search.mjs';

test('filterBooks filters by query, pipelineStatus, and sorts', () => {
  const books = [
    { bookId: 'b-zeta', title: 'Zeta Rules', pipelineStatus: 'DONE', publicationMode: 'NOT_PUBLIC', entityCount: 15, pageCount: 50 },
    { bookId: 'a-alpha', title: 'Alpha Guide', pipelineStatus: 'WAITING', publicationMode: 'NOT_PUBLIC', entityCount: 0, pageCount: 10 },
    { bookId: 'c-beta', title: 'Beta Lore', pipelineStatus: 'WAITING', publicationMode: 'NOT_PUBLIC', entityCount: 0, pageCount: 100 },
  ];

  // Filter by pipelineStatus
  const waiting = filterBooks(books, { pipelineStatus: 'WAITING' });
  assert.equal(waiting.length, 2);

  // Filter by query and sort by title
  const filtered = filterBooks(books, { query: 'Alpha' });
  assert.equal(filtered.length, 1);
  assert.equal(filtered[0].bookId, 'a-alpha');

  // Sort by entityCount descending
  const sorted = filterBooks(books, { sortBy: 'entities_desc' });
  assert.equal(sorted[0].bookId, 'b-zeta');
});
```

- [ ] **Step 2: Run test and confirm RED**
```powershell
node --test tests/frontend/site-search.test.mjs
```
Expected: `TypeError: filterBooks is not a function`.

- [ ] **Step 3: Implement minimal code**
In `docs/assets/site-search.mjs`:
```javascript
export function filterBooks(books, { query = '', pipelineStatus = '', publicationMode = '', categoryHint = '', sortBy = 'title_asc' } = {}) {
  let result = [...books];

  const q = normalizeSearch(query);
  if (q) {
    result = result.filter(b => normalizeSearch(b.title).includes(q) || b.bookId.includes(q));
  }

  if (pipelineStatus && pipelineStatus !== 'all') {
    result = result.filter(b => b.pipelineStatus === pipelineStatus);
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
In `docs/assets/site-model.mjs`: add helper `getBookMetadata(bookId)`:
```javascript
getBookMetadata(bookId) {
  if (!this.catalog || !Array.isArray(this.catalog.books)) return null;
  return this.catalog.books.find(b => b.bookId === bookId) || null;
}
```

- [ ] **Step 4: Run test and confirm GREEN**
```powershell
node --test tests/frontend/site-search.test.mjs tests/frontend/site-model.test.mjs
```
Expected: All pass.

- [ ] **Step 5: Run focused regressions**
```powershell
node --test tests/frontend/site-model.test.mjs tests/frontend/site-search.test.mjs tests/frontend/site-state.test.mjs
```
Expected: All pass.

- [ ] **Step 6: Commit**
```powershell
git add docs/assets/site-model.mjs docs/assets/site-search.mjs docs/assets/site-state.mjs tests/frontend/site-search.test.mjs
git commit -m "feat(frontend): add archive book filtering, sorting, and metadata retrieval"
```

---

### Task 5: Acervo 281 UI — Responsive Cards, Filters, and Layouts (`site-ui.mjs`, `styles.css`)

**Files:**
- Modify: `docs/assets/site-ui.mjs`
- Modify: `docs/assets/styles.css`

**Interfaces:**
- `renderBooksView()` in `site-ui.mjs` renders:
  - Header with total count (e.g. "Acervo (281 livros)")
  - Filter bar: search input, pipeline status dropdown (`all`, `WAITING`, `RUNNING`, `BLOCKED`, `NEEDS_HUMAN_REVIEW`, `READY_FOR_HUMAN_APPROVAL`, `DONE`, `FAILED`), publication mode dropdown, sort dropdown (`title_asc`, `title_desc`, `entities_desc`, `pages_desc`).
  - Card elements: `.site-book-card` with `.site-book-title`, `.site-badge-pipeline` (`data-status`), `.site-badge-pub` (`data-mode`), current stage indicator, entity count badge, page count.

- [ ] **Step 1: Implement UI rendering in `docs/assets/site-ui.mjs`**
Update `renderBooksView` in `docs/assets/site-ui.mjs` to render the controls and enriched cards with live filtering.
- [ ] **Step 2: Add styles in `docs/assets/styles.css`**
Add styles for `.site-books-controls`, `.site-book-card`, `.site-badge-pipeline[data-status="WAITING"]` (neutral gray), `[data-status="RUNNING"]` (blue), `[data-status="BLOCKED"]` (red), `[data-status="NEEDS_HUMAN_REVIEW"]` (amber), `[data-status="DONE"]` (green), and responsive grid layout (`grid-template-columns: repeat(auto-fill, minmax(280px, 1fr))`).
- [ ] **Step 3: Validate syntax and integrity**
```powershell
node --check docs/assets/app.js
```
Expected: Exit code 0.
- [ ] **Step 4: Commit**
```powershell
git add docs/assets/site-ui.mjs docs/assets/styles.css
git commit -m "feat(frontend): implement 281-book responsive grid and filter controls"
```

---

### Task 6: Individual Book Page (`#/book/:bookId`) with 7-Stage Pipeline Stepper

**Files:**
- Modify: `docs/assets/site-ui.mjs`
- Modify: `docs/assets/styles.css`

**Interfaces:**
- `renderBookDetailView(bookId)` in `site-ui.mjs`:
  - Visual 7-stage stepper: `Source` -> `Extraction` -> `Editorial` -> `Entities` -> `Relations` -> `Frontend` -> `QA`.
  - Stage state indicators: completed (`done`), active (`active`), pending (`pending`).
  - Metadata panel: title, pipeline status, publication mode, source path, page count, size, category hints.
  - Entities & Relations summary: when `entityCount === 0`, renders clean info banner: *"Nenhuma entidade processada para este livro ainda. O livro encontra-se na fila de processamento."*
  - When entities exist, renders links to entities.

- [ ] **Step 1: Implement book detail view and stepper in `docs/assets/site-ui.mjs`**
In `renderBookDetailView`, retrieve both book file data (`store.loadBook(bookId)`) and catalog metadata (`store.getBookMetadata(bookId)`). Render the stepper container `.pipeline-stepper` with 7 stages and metadata card.
- [ ] **Step 2: Add stepper styles in `docs/assets/styles.css`**
Define `.pipeline-stepper`, `.stepper-step`, `.stepper-step.done`, `.stepper-step.active`, `.stepper-step.pending`.
- [ ] **Step 3: Validate syntax**
```powershell
node --check docs/assets/app.js
```
Expected: Exit code 0.
- [ ] **Step 4: Commit**
```powershell
git add docs/assets/site-ui.mjs docs/assets/styles.css
git commit -m "feat(frontend): implement 7-stage pipeline stepper and book detail view"
```

---

### Task 7: Browser Tests for Acervo 281 & Regression Suite

**Files:**
- Modify: `tests/frontend/test_site_browser.py`
- Modify: `tests/frontend/conftest.py`

**Interfaces:**
- Browser test in `tests/frontend/test_site_browser.py`:
  - Tests `#/books` displaying synthetic multi-book catalog.
  - Tests filtering books by pipeline status and search query.
  - Tests clicking book card to navigate to `#/book/:bookId`.
  - Tests 7-stage stepper presentation and empty state when entities == 0.

- [ ] **Step 1: Update `tests/frontend/conftest.py` with synthetic multi-book catalog**
Add a second synthetic book with 0 entities and `pipelineStatus="WAITING"` to test the unworked book view.
- [ ] **Step 2: Write browser test functions in `tests/frontend/test_site_browser.py`**
```python
def test_books_catalog_filters_and_stepper(page, site_url):
    page.goto(site_url + "#/books")
    page.wait_for_selector(".site-books-grid", timeout=10000)

    # Verify both synthetic books are rendered
    assert page.locator(".site-book-card").count() >= 2

    # Filter by search
    page.locator("#bookSearchInput").fill("Sintético")
    assert page.locator(".site-book-card").count() >= 1

    # Navigate to unworked book
    unworked_link = page.locator('a[href="#/book/synthetic-empty"]')
    if unworked_link.count() > 0:
        unworked_link.first.click()
        page.wait_for_selector(".pipeline-stepper", timeout=10000)
        assert "Source" in page.text_content(".pipeline-stepper")
        assert "QA" in page.text_content(".pipeline-stepper")
```
- [ ] **Step 3: Run browser tests and confirm GREEN**
```powershell
python -m pytest tests/frontend/test_site_browser.py -q
```
Expected: All browser tests pass.
- [ ] **Step 4: Run full regression suite**
```powershell
python -m pytest tests/agents -q
node --test tests/frontend/site-model.test.mjs tests/frontend/site-search.test.mjs tests/frontend/site-state.test.mjs
python scripts/validate_data.py
python scripts/check_book_coverage.py
node --check docs/assets/app.js
```
Expected: All pass.
- [ ] **Step 5: Commit**
```powershell
git add tests/frontend/test_site_browser.py tests/frontend/conftest.py
git commit -m "test(browser): add E2E tests for archive catalog grid, filters, and book stepper"
```

---

## Verification Plan

### Automated Tests
1. Unit tests for archive inventory loader:
   `python -m pytest tests/agents/test_archive_inventory_loader.py -v`
2. Unit tests for archive projection:
   `python -m pytest tests/agents/test_frontend_projector_archive.py -v`
3. Fail-closed policy tests:
   `python -m pytest tests/agents/test_frontend_policy_archive.py -v`
4. Node frontend tests:
   `node --test tests/frontend/site-model.test.mjs tests/frontend/site-search.test.mjs tests/frontend/site-state.test.mjs`
5. Browser E2E tests:
   `python -m pytest tests/frontend/test_site_browser.py -q`
6. Global regression suite:
   `python -m pytest tests/agents -q`
   `python scripts/validate_data.py`
   `python scripts/check_book_coverage.py`
   `node --check docs/assets/app.js`

### Manual Verification
- Launch local preview server (`PreviewServer`) in `restricted_preview` mode.
- Navigate to `#/books` in browser; verify all 281 books appear in grid with responsive card layout.
- Filter by status and search by book title; verify smooth client-side filtering.
- Click an unworked book card; verify clean page with 7-stage stepper and 0 entities.
- Verify in `mode=public` that zero unworked books or restricted data appear.
