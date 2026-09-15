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


import hashlib

def _sha256_file(path: Path) -> str:
    """Computes SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def resolve_canonical_runtime_dir(repo_or_worktree_root: Path | str | None = None) -> Path:
    """Resolves canonical .daemon_runtime directory with strict 4-tier precedence:
    1. Explicit path argument if provided
    2. DAEMON_RUNTIME_DIR environment variable
    3. Git repository / worktree locator (.git gitdir, .worktrees, or repo root)
    4. Documented default fallback
    """
    # Tier 1: Explicit argument
    if repo_or_worktree_root:
        p = Path(repo_or_worktree_root).resolve()
        if p.name == ".daemon_runtime":
            return p
        if (p / ".daemon_runtime").is_dir():
            return (p / ".daemon_runtime").resolve()
        for cand in [p / ".daemon_runtime", p.parent / ".daemon_runtime", p.parent.parent / ".daemon_runtime", p.parent.parent.parent / ".daemon_runtime"]:
            if (cand / "jobs").is_dir() and (cand / "bundles").is_dir():
                return cand.resolve()
            if (cand / "jobs").is_dir() or (cand / "bundles").is_dir():
                return cand.resolve()
            if cand.is_dir():
                return cand.resolve()
        return p

    # Tier 2: Environment variable
    env_dir = os.environ.get("DAEMON_RUNTIME_DIR")
    if env_dir and env_dir.strip():
        return Path(env_dir.strip()).resolve()

    # Tier 3: Git repository / worktree locator
    bases = [ROOT, Path.cwd()]
    git_path = ROOT / ".git"
    if git_path.is_file():
        try:
            content = git_path.read_text(encoding="utf-8").strip()
            if content.startswith("gitdir:"):
                gd = Path(content[len("gitdir:"):].strip()).resolve()
                bases.append(gd.parent.parent if "worktrees" in gd.parts else gd.parent)
        except Exception:
            pass

    # Pass 3a: Look for runtime directory with both jobs and bundles
    for b in bases:
        curr = b
        while curr and curr.parent != curr:
            cand = curr / ".daemon_runtime"
            if (cand / "jobs").is_dir() and (cand / "bundles").is_dir():
                return cand.resolve()
            curr = curr.parent

    # Pass 3b: Look for runtime directory with jobs or bundles
    for b in bases:
        curr = b
        while curr and curr.parent != curr:
            cand = curr / ".daemon_runtime"
            if (cand / "jobs").is_dir() or (cand / "bundles").is_dir():
                return cand.resolve()
            curr = curr.parent

    # Pass 3c: Look for any existing .daemon_runtime
    for b in bases:
        curr = b
        while curr and curr.parent != curr:
            cand = curr / ".daemon_runtime"
            if cand.is_dir():
                return cand.resolve()
            curr = curr.parent

    # Tier 4: Documented fallback
    if ".worktrees" in ROOT.parts:
        idx = ROOT.parts.index(".worktrees")
        main_repo = Path(*ROOT.parts[:idx])
        return (main_repo.parent / ".daemon_runtime").resolve()
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

    overlay: dict[str, dict[str, Any]] = {}
    if not j_dir.exists():
        return overlay

    job_store = JobStore(j_dir)
    accepted_bundles_dir = r_dir / "bundles" / "accepted"

    # Index accepted bundles by directory name
    available_bundles: dict[str, dict[str, Any]] = {}
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
            bundle_sha = m_data.get("resultManifestSha256") or _sha256_file(manifest_file)
            raw_sha = _sha256_file(manifest_file)
            available_bundles[rb_id] = {
                "bundleDir": b_dir,
                "manifest": m_data,
                "resultBundleId": rb_id,
                "attemptNumber": att_num,
                "stage": stage,
                "bookId": b_id,
                "sha256": bundle_sha,
                "rawSha256": raw_sha,
            }

    # Group jobs by bookId to detect ambiguous multiple jobs without authoritative resolution
    jobs_by_book: dict[str, list[tuple[str, dict[str, Any]]]] = {}
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

        jobs_by_book.setdefault(book_id, []).append((job_id, job_data))

    for book_id, job_list in jobs_by_book.items():
        if len(job_list) > 1:
            job_ids = [j[0] for j in job_list]
            raise ProcessedStateReadError(
                f"Multiple jobs found for bookId '{book_id}' ({job_ids}) without authoritative resolution"
            )

        job_id, job_data = job_list[0]

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

        # Discover certified audit evidence for this book
        audit_dirs = [
            r_dir / "audit" / "pilot" / book_id,
            r_dir / "audit" / book_id,
        ]
        approved_decisions: dict[str, dict[str, Any]] = {}
        active_requests: dict[str, dict[str, Any]] = {}

        for a_dir in audit_dirs:
            if not a_dir.is_dir():
                continue
            # Check decisions
            dec_dir = a_dir / "decisions"
            if dec_dir.is_dir():
                for df in sorted(dec_dir.iterdir()):
                    if not df.name.endswith(".json"):
                        continue
                    try:
                        with open(df, "r", encoding="utf-8") as f:
                            d = json.load(f)
                    except Exception as e:
                        raise ProcessedStateReadError(f"Corrupt decision file {df}: {e}") from e
                    if d.get("decision") in ("APPROVE", "APPROVED") or d.get("status") == "APPROVED":
                        rb_id = d.get("resultBundleId")
                        if rb_id:
                            stg = _extract_stage_from_bundle_id(rb_id) or d.get("stage")
                            if stg:
                                approved_decisions[stg] = {
                                    "bundleId": rb_id,
                                    "manifestHash": d.get("reviewedResultManifestSha256") or d.get("manifestHash"),
                                    "decisionId": d.get("decisionId"),
                                }

            # Check requests
            req_dir = a_dir / "requests"
            if req_dir.is_dir():
                for rf in sorted(req_dir.iterdir()):
                    if not rf.name.endswith(".json"):
                        continue
                    try:
                        with open(rf, "r", encoding="utf-8") as f:
                            r = json.load(f)
                    except Exception as e:
                        raise ProcessedStateReadError(f"Corrupt request file {rf}: {e}") from e
                    rb_id = r.get("resultBundleId") or r.get("bundleId")
                    stg = r.get("stage") or (_extract_stage_from_bundle_id(rb_id) if rb_id else None)
                    if stg and rb_id:
                        active_requests[stg] = {
                            "bundleId": rb_id,
                            "manifestHash": (
                                r.get("reviewedResultManifestSha256")
                                or r.get("resultManifestSha256")
                                or r.get("manifestHash")
                            ),
                            "inputEntitiesBundle": r.get("inputEntitiesBundle"),
                            "requestId": r.get("requestId") or r.get("reviewRequestId"),
                            "status": r.get("status"),
                        }

        # Filter candidate accepted bundles for this book
        book_candidate_bundles = {
            k: v for k, v in available_bundles.items() if v.get("bookId") == book_id
        }

        # 1. Resolve Entities Stage from Certified Lineage
        ent_candidates = [
            k for k, v in book_candidate_bundles.items()
            if v["stage"] == "entities" or (v["bundleDir"] / "artifacts" / "entities.json").exists()
        ]
        chosen_ent_id: str | None = None
        expected_ent_hash: str | None = None

        if "entities" in approved_decisions:
            chosen_ent_id = approved_decisions["entities"]["bundleId"]
            expected_ent_hash = approved_decisions["entities"]["manifestHash"]
        elif "entities" in active_requests:
            chosen_ent_id = active_requests["entities"]["bundleId"]
            expected_ent_hash = active_requests["entities"]["manifestHash"]
        elif len(ent_candidates) == 1:
            chosen_ent_id = ent_candidates[0]
        elif len(ent_candidates) > 1:
            raise ProcessedStateReadError(
                f"Multiple accepted entities bundles for book '{book_id}' ({ent_candidates}) without certified decision or request authority"
            )

        entities: list[dict[str, Any]] = []
        if chosen_ent_id:
            if chosen_ent_id not in book_candidate_bundles:
                raise ProcessedStateReadError(
                    f"Certified entities bundle '{chosen_ent_id}' not found in accepted bundles"
                )
            binfo = book_candidate_bundles[chosen_ent_id]
            if expected_ent_hash and binfo["sha256"] != expected_ent_hash and binfo.get("rawSha256") != expected_ent_hash:
                raise ProcessedStateReadError(
                    f"Manifest hash mismatch for entities bundle '{chosen_ent_id}': expected {expected_ent_hash}, got {binfo['sha256']}"
                )
            b_dir = binfo["bundleDir"]
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

        # 2. Resolve Relations Stage from Certified Lineage & Validate Cross-Stage Lineage
        rel_candidates = [
            k for k, v in book_candidate_bundles.items()
            if v["stage"] == "relations" or (v["bundleDir"] / "artifacts" / "relations.json").exists()
        ]
        chosen_rel_id: str | None = None
        expected_rel_hash: str | None = None
        required_input_ent: str | None = None

        if "relations" in approved_decisions:
            chosen_rel_id = approved_decisions["relations"]["bundleId"]
            expected_rel_hash = approved_decisions["relations"]["manifestHash"]
        elif "relations" in active_requests:
            chosen_rel_id = active_requests["relations"]["bundleId"]
            expected_rel_hash = active_requests["relations"]["manifestHash"]
            required_input_ent = active_requests["relations"].get("inputEntitiesBundle")
        elif len(rel_candidates) == 1:
            chosen_rel_id = rel_candidates[0]
            required_input_ent = book_candidate_bundles[chosen_rel_id]["manifest"].get("inputEntitiesBundle")
        elif len(rel_candidates) > 1:
            raise ProcessedStateReadError(
                f"Multiple accepted relations bundles for book '{book_id}' ({rel_candidates}) without certified decision or request authority"
            )

        relations: list[dict[str, Any]] = []
        if chosen_rel_id:
            if chosen_rel_id not in book_candidate_bundles:
                raise ProcessedStateReadError(
                    f"Certified relations bundle '{chosen_rel_id}' not found in accepted bundles"
                )
            binfo = book_candidate_bundles[chosen_rel_id]
            if expected_rel_hash and binfo["sha256"] != expected_rel_hash and binfo.get("rawSha256") != expected_rel_hash:
                raise ProcessedStateReadError(
                    f"Manifest hash mismatch for relations bundle '{chosen_rel_id}': expected {expected_rel_hash}, got {binfo['sha256']}"
                )

            # Cross-stage lineage validation
            input_ent_ref = required_input_ent or binfo["manifest"].get("inputEntitiesBundle")
            if input_ent_ref and chosen_ent_id and input_ent_ref != chosen_ent_id:
                raise ProcessedStateReadError(
                    f"Cross-stage lineage mismatch: relations bundle '{chosen_rel_id}' requires inputEntitiesBundle '{input_ent_ref}', but certified entities bundle is '{chosen_ent_id}'"
                )

            b_dir = binfo["bundleDir"]
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

