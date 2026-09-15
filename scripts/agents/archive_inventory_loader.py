from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from scripts.agents.contracts import ContractValidationError
from scripts.agents.job_store import JobStore

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCES_PATH = ROOT / "data" / "index" / "sources.json"
DEFAULT_JOBS_DIR = ROOT / "coordination" / "jobs"


def resolve_canonical_runtime_dir(repo_or_worktree_root: Path | str | None = None) -> Path:
    """Resolves the canonical .daemon_runtime directory whether running from main repo or isolated worktree."""
    env_dir = os.environ.get("DAEMON_RUNTIME_DIR")
    if env_dir:
        return Path(env_dir).resolve()

    raw_candidates = []
    if repo_or_worktree_root:
        raw_candidates.append(Path(repo_or_worktree_root))
    raw_candidates.extend([
        Path.cwd(),
        Path(__file__).parents[2],
        ROOT,
    ])

    # Pass 1: Find an existing runtime directory containing jobs or bundles
    for base in raw_candidates:
        curr = base
        while curr and curr.parent != curr:
            cand = curr / ".daemon_runtime"
            if (cand / "jobs").is_dir() or (cand / "bundles").is_dir():
                return cand.resolve()
            if curr.name == ".worktrees":
                # Check parent of worktrees container directory
                cand_wt = curr.parent.parent / ".daemon_runtime"
                if (cand_wt / "jobs").is_dir() or (cand_wt / "bundles").is_dir():
                    return cand_wt.resolve()
            curr = curr.parent

    # Pass 2: Fallback to any existing .daemon_runtime directory
    for base in raw_candidates:
        curr = base
        while curr and curr.parent != curr:
            if curr.name == ".worktrees":
                cand = curr.parent.parent / ".daemon_runtime"
                if cand.is_dir():
                    return cand.resolve()
            cand = curr / ".daemon_runtime"
            if cand.is_dir():
                return cand.resolve()
            curr = curr.parent

    # Pass 3: Default layout assumption
    if ".worktrees" in ROOT.parts:
        idx = ROOT.parts.index(".worktrees")
        return (Path(*ROOT.parts[:idx]).parent / ".daemon_runtime").resolve()

    return (ROOT.parent / ".daemon_runtime").resolve()


DEFAULT_RUNTIME_DIR = resolve_canonical_runtime_dir()


class ArchiveInventoryError(RuntimeError):
    """Base error for archive inventory operations."""

    pass


class ProcessedStateReadError(ArchiveInventoryError):
    """Raised when certified operational state or artifact reading fails or artifact is corrupt."""

    pass


def _extract_stage_from_bundle_id(bundle_id: str) -> str | None:
    """Extracts lowercase stage name from standard bundle ID (e.g. RB-ANIM-ENTITIES-att1-50691836 -> entities)."""
    m = re.match(r"^RB-[A-Z0-9]+-([A-Z0-9_]+)-att(\d+)-[a-f0-9]+$", bundle_id, re.IGNORECASE)
    if m:
        return m.group(1).lower()
    return None


def _extract_attempt_from_bundle_id(bundle_id: str) -> int:
    """Extracts integer attempt number from bundle ID."""
    m = re.match(r"^RB-[A-Z0-9]+-[A-Z0-9_]+-att(\d+)-[a-f0-9]+$", bundle_id, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return 1


def load_certified_pilot_artifacts(
    runtime_dir: Path | str | None = None,
    jobs_dir: Path | str | None = None,
) -> dict[str, dict[str, Any]]:
    """Loads certified operational state and accepted artifact bundles from runtime store read-only."""
    r_dir = Path(runtime_dir).resolve() if runtime_dir else resolve_canonical_runtime_dir()
    j_dir = Path(jobs_dir).resolve() if jobs_dir else (r_dir / "jobs")
    if not j_dir.exists() and DEFAULT_JOBS_DIR.exists():
        j_dir = DEFAULT_JOBS_DIR

    overlay: dict[str, dict[str, Any]] = {}
    if not j_dir.exists():
        return overlay

    job_store = JobStore(j_dir)
    accepted_bundles_dir = r_dir / "bundles" / "accepted"

    # Index accepted bundles by (book_id, stage, attempt_num)
    accepted_bundles_by_book: dict[str, list[dict[str, Any]]] = {}
    if accepted_bundles_dir.exists():
        for b_dir in sorted(accepted_bundles_dir.iterdir()):
            if not b_dir.is_dir():
                continue
            manifest_file = b_dir / "result-manifest.json"
            if not manifest_file.exists():
                continue
            try:
                with open(manifest_file, "r", encoding="utf-8") as mf:
                    m_data = json.load(mf)
            except Exception as e:
                raise ProcessedStateReadError(f"Corrupt result-manifest.json in bundle {b_dir}: {e}") from e

            b_id = m_data.get("bookId")
            rb_id = m_data.get("resultBundleId", b_dir.name)
            att_num = m_data.get("attemptNumber", _extract_attempt_from_bundle_id(rb_id))
            stage = _extract_stage_from_bundle_id(rb_id)
            if b_id:
                accepted_bundles_by_book.setdefault(b_id, []).append({
                    "bundleDir": b_dir,
                    "manifest": m_data,
                    "resultBundleId": rb_id,
                    "attemptNumber": att_num,
                    "stage": stage,
                })

    for job_id in job_store.list_job_ids():
        try:
            job_data = job_store.load(job_id)
        except ContractValidationError as cve:
            raise ProcessedStateReadError(f"Job '{job_id}' violates agent-job schema: {cve}") from cve
        except Exception as e:
            raise ProcessedStateReadError(f"Failed to load job '{job_id}': {e}") from e

        book_id = job_data.get("bookId")
        if not book_id:
            raise ProcessedStateReadError(f"Job '{job_id}' missing required bookId")

        raw_status = job_data.get("status")
        status_map = {
            "todo": "WAITING",
            "in_progress": "RUNNING",
            "blocked": "BLOCKED",
            "needs_review": "NEEDS_HUMAN_REVIEW",
            "approved": "READY_FOR_HUMAN_APPROVAL",
            "done": "DONE",
        }
        if raw_status not in status_map:
            raise ProcessedStateReadError(f"Unknown job status '{raw_status}' in job '{job_id}'")

        pipeline_status = status_map[raw_status]
        current_stage = job_data.get("currentStage")

        entities: list[dict[str, Any]] = []
        relations: list[dict[str, Any]] = []

        book_bundles = accepted_bundles_by_book.get(book_id, [])

        # Find approved bundle for entities stage
        ent_bundles = [b for b in book_bundles if b["stage"] == "entities" or (b["bundleDir"] / "artifacts" / "entities.json").exists()]
        if ent_bundles:
            # Sort by attemptNumber descending to pick the latest accepted attempt
            ent_bundles.sort(key=lambda x: x["attemptNumber"], reverse=True)
            chosen_ent_bundle = ent_bundles[0]
            b_dir = chosen_ent_bundle["bundleDir"]
            ent_file = b_dir / "artifacts" / "entities.json"
            if not ent_file.exists():
                ent_file = b_dir / "artifacts" / "data" / "entities" / f"{book_id}.json"

            if ent_file.exists():
                try:
                    with open(ent_file, "r", encoding="utf-8") as f:
                        ent_data = json.load(f)
                    raw_ents = ent_data if isinstance(ent_data, list) else [ent_data]
                    for ent in raw_ents:
                        if not isinstance(ent, dict):
                            continue
                        # Validate provenance fail-closed
                        prov = ent.get("provenance")
                        ent_src = (
                            (prov.get("source") if isinstance(prov, dict) else None)
                            or ent.get("source")
                        )
                        ent_pages = (
                            (prov.get("pages") or prov.get("pageRange") if isinstance(prov, dict) else None)
                            or ent.get("pages")
                            or ([ent["page"]] if ent.get("page") else None)
                        )
                        if not ent_src or ent_src != book_id or not ent_pages:
                            raise ProcessedStateReadError(
                                f"Entity '{ent.get('id', 'unknown')}' in bundle {b_dir.name} missing or invalid provenance: source='{ent_src}' pages='{ent_pages}'"
                            )
                        entities.append(ent)
                except ProcessedStateReadError:
                    raise
                except Exception as e:
                    raise ProcessedStateReadError(f"Corrupt entity artifact in bundle {b_dir}: {e}") from e

        # Find approved bundle for relations stage
        rel_bundles = [b for b in book_bundles if b["stage"] == "relations" or (b["bundleDir"] / "artifacts" / "relations.json").exists()]
        if rel_bundles:
            rel_bundles.sort(key=lambda x: x["attemptNumber"], reverse=True)
            chosen_rel_bundle = rel_bundles[0]
            b_dir = chosen_rel_bundle["bundleDir"]
            rel_file = b_dir / "artifacts" / "relations.json"
            if not rel_file.exists():
                rel_file = b_dir / "artifacts" / "data" / "entities" / "relations.json"

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
                            raise ProcessedStateReadError(
                                f"Relation '{r.get('relationId', 'unknown')}' missing required source provenance or mismatch: '{r_src}' != '{book_id}'"
                            )
                        relations.append(r)
                except ProcessedStateReadError:
                    raise
                except Exception as e:
                    raise ProcessedStateReadError(f"Corrupt relation artifact in bundle {b_dir}: {e}") from e

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
    def __init__(
        self,
        sources_path: Path | str | None = None,
        jobs_dir: Path | str | None = None,
        runtime_dir: Path | str | None = None,
        workspace_root: Path | str | None = None,
    ) -> None:
        if sources_path:
            self.sources_path = Path(sources_path).resolve()
        elif workspace_root:
            self.sources_path = (Path(workspace_root).resolve() / "data" / "index" / "sources.json")
        else:
            self.sources_path = DEFAULT_SOURCES_PATH
        self.runtime_dir = Path(runtime_dir).resolve() if runtime_dir else resolve_canonical_runtime_dir(workspace_root)
        self.jobs_dir = Path(jobs_dir).resolve() if jobs_dir else (self.runtime_dir / "jobs")


    def load_inventory(self, operational_overlay: dict[str, dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        if not self.sources_path.exists():
            raise FileNotFoundError(f"Sources manifest not found: {self.sources_path}")

        try:
            with open(self.sources_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            raise ArchiveInventoryError(f"Failed to read sources manifest: {e}") from e

        sources = data.get("sources", [])
        overlay_map = (
            operational_overlay
            if operational_overlay is not None
            else load_certified_pilot_artifacts(runtime_dir=self.runtime_dir, jobs_dir=self.jobs_dir)
        )
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

                raw_entities = overlay.get("entities", [])
                entities = []
                for ent in raw_entities:
                    if not isinstance(ent, dict):
                        continue
                    prov = ent.get("provenance")
                    ent_src = (
                        (prov.get("source") if isinstance(prov, dict) else None)
                        or ent.get("source")
                    )
                    if ent_src and ent_src != bid:
                        raise ProcessedStateReadError(
                            f"Entity '{ent.get('id', 'unknown')}' in overlay has source mismatch: '{ent_src}' != '{bid}'"
                        )
                    entities.append(ent)

                raw_relations = overlay.get("relations", [])
                relations = []
                for r in raw_relations:
                    if not isinstance(r, dict):
                        continue
                    r_src = r.get("source")
                    if not r_src or r_src != bid:
                        raise ProcessedStateReadError(
                            f"Relation in overlay for book '{bid}' missing required source provenance or mismatch: '{r_src}' != '{bid}'"
                        )
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

    def get_book_by_id(
        self, book_id: str, operational_overlay: dict[str, dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        all_books = self.load_inventory(operational_overlay)
        for b in all_books:
            if b["bookId"] == book_id:
                return b
        raise KeyError(f"Book '{book_id}' not found in archive inventory")

