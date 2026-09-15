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
                                raise ProcessedStateReadError(
                                    f"Relation '{r.get('relationId', 'unknown')}' missing required source provenance or mismatch: '{r_src}' != '{book_id}'"
                                )
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
    def __init__(
        self,
        sources_path: Path | str | None = None,
        jobs_dir: Path | str | None = None,
        runtime_dir: Path | str | None = None,
    ) -> None:
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
        overlay_map = (
            operational_overlay
            if operational_overlay is not None
            else load_certified_pilot_artifacts(self.runtime_dir)
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
                entities = list(overlay.get("entities", []))
                raw_relations = overlay.get("relations", [])
                relations = []
                for r in raw_relations:
                    if not isinstance(r, dict):
                        continue
                    r_src = r.get("source")
                    if not r_src:
                        raise ProcessedStateReadError(
                            f"Relation in overlay for book '{bid}' missing required source provenance"
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
