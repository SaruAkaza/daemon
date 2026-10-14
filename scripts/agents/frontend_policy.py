from __future__ import annotations

from typing import Any

from scripts.agents.frontend_labels import entity_label
from scripts.agents.gate_engine import PERMITTED_RIGHTS_COMBINATIONS
from scripts.agents.site_view_model import ProjectionError

VALID_MODES = {"restricted_preview", "public"}


def public_combination_allowed(rights_status: str, publication_mode: str) -> bool:
    """Check if the combination of rightsStatus and publicationMode is permitted for public exposure."""
    return (rights_status, publication_mode) in PERMITTED_RIGHTS_COMBINATIONS


def project_allowed_book(book: dict[str, Any], mode: str) -> dict[str, Any] | None:
    """Filter book content and metadata according to rights status, publication mode, and projection mode.

    Returns a clean dictionary containing strictly whitelisted and authorized fields,
    or None if the book is excluded from the current mode.
    Raises ProjectionError on invalid mode or corrupt input structure.
    """
    if mode not in VALID_MODES:
        raise ProjectionError(f"Invalid projection mode: '{mode}' (expected one of {VALID_MODES})")

    if not isinstance(book, dict):
        raise ProjectionError("Book input must be a dictionary")

    book_id = book.get("bookId")
    if not book_id:
        raise ProjectionError("Book missing required bookId")

    rights_status = str(book.get("rightsStatus", "UNKNOWN")).strip()
    publication_mode = str(book.get("publicationMode", "NOT_PUBLIC")).strip()

    # Fail-closed public policy
    if mode == "public":
        if publication_mode == "NOT_PUBLIC":
            return None
        if rights_status == "UNKNOWN":
            return None
        if not public_combination_allowed(rights_status, publication_mode):
            return None

        # Also inspect sources if present: if any source is NOT_PUBLIC or UNKNOWN, block exposure
        sources = book.get("sources", {})
        if isinstance(sources, dict):
            for src_id, src_meta in sources.items():
                if isinstance(src_meta, dict):
                    src_rights = src_meta.get("rightsStatus", rights_status)
                    src_pub = src_meta.get("publicationMode", publication_mode)
                    if src_pub == "NOT_PUBLIC" or src_rights == "UNKNOWN":
                        return None
                    if not public_combination_allowed(src_rights, src_pub):
                        return None

    # Construct clean, strictly whitelisted output dictionary
    projected: dict[str, Any] = {
        "bookId": book_id,
        "title": book.get("title", book_id),
        "rightsStatus": rights_status,
        "publicationMode": publication_mode,
        "pageCount": book.get("pageCount", 0),
        "categoryHints": list(book.get("categoryHints", [])),
        "sizeBytes": book.get("sizeBytes", 0),
        "groups": [],
        "entities": [],
        "relations": [],
    }

    if mode == "restricted_preview":
        projected["pipelineStatus"] = book.get("pipelineStatus", "WAITING")
        projected["currentStage"] = book.get("currentStage")

    # Clean groups
    raw_groups = book.get("groups", [])
    if isinstance(raw_groups, list):
        for g in raw_groups:
            if isinstance(g, dict) and "id" in g and "label" in g:
                projected["groups"].append({
                    "id": str(g["id"]),
                    "label": str(g["label"]),
                    "entityIds": list(g.get("entityIds", [])),
                })

    # Clean and filter entities
    raw_entities = book.get("entities", [])
    if isinstance(raw_entities, list):
        for ent in raw_entities:
            if not isinstance(ent, dict):
                continue

            eid = ent.get("id") or ent.get("entityId")
            if not eid:
                continue

            category = ent.get("category") or ent.get("type", "core_rule")
            subtype = ent.get("subtype")
            display_type = ent.get("displayType") or entity_label(category, subtype)
            name = ent.get("name", "")
            aliases = list(ent.get("aliases", []))
            tags = list(ent.get("tags", []))

            # Build provenance
            raw_prov = ent.get("provenance", {})
            if isinstance(raw_prov, dict) and "source" in raw_prov and "pages" in raw_prov:
                provenance = {
                    "source": str(raw_prov["source"]),
                    "pages": list(raw_prov["pages"]),
                }
            else:
                ent_src = ent.get("source", book_id)
                ent_pages = ent.get("pages") or ([ent["page"]] if ent.get("page") else [1])
                provenance = {
                    "source": str(ent_src),
                    "pages": list(ent_pages),
                }

            # Determine content based on publicationMode and mode
            content: list[dict[str, Any]] = []
            if mode == "public" and publication_mode == "METADATA_ONLY":
                content = []
            elif mode == "public" and publication_mode == "SUMMARY_AND_METADATA":
                summary = ent.get("summary")
                if summary:
                    content = [{"title": "Resumo", "paragraphs": [str(summary)]}]
                else:
                    content = []
            else:
                # FULL_TEXT or restricted_preview
                if "content" in ent and isinstance(ent["content"], list):
                    for blk in ent["content"]:
                        if isinstance(blk, dict) and "title" in blk and "paragraphs" in blk:
                            content.append({
                                "title": str(blk["title"]),
                                "paragraphs": [str(p) for p in blk["paragraphs"]],
                            })
                elif "entries" in ent and isinstance(ent["entries"], list):
                    content = [{
                        "title": "Conteúdo",
                        "paragraphs": [str(e) for e in ent["entries"]],
                    }]

            projected_entity: dict[str, Any] = {
                "entityId": str(eid),
                "type": str(category),
                "displayType": str(display_type),
                "name": str(name),
                "aliases": aliases,
                "tags": tags,
                "content": content,
                "provenance": provenance,
            }

            # technicalDetails only in restricted_preview
            if mode == "restricted_preview":
                src_val = (
                    ent.get("sourceId")
                    or ent.get("source")
                    or book.get("sourceId")
                    or book.get("source")
                    or book_id
                )
                tech_details: dict[str, Any] = {
                    "entityId": str(eid),
                    "type": str(category),
                    "sourceId": str(src_val),
                    "provenance": provenance,
                    "mode": "restricted_preview",
                    "rightsStatus": rights_status,
                    "publicationMode": publication_mode,
                }
                ctx = ent.get("context") or book.get("context")
                if ctx:
                    tech_details["context"] = str(ctx)

                rov = ent.get("relationOntologyVersion") or book.get("relationOntologyVersion")
                if rov:
                    tech_details["relationOntologyVersion"] = str(rov)

                # Merge pre-existing technicalDetails without fabricating absent fields
                if "technicalDetails" in ent and isinstance(ent["technicalDetails"], dict):
                    for k, v in ent["technicalDetails"].items():
                        if k not in tech_details:
                            tech_details[k] = v

                projected_entity["technicalDetails"] = tech_details

            projected["entities"].append(projected_entity)

    # Clean and filter relations
    raw_relations = book.get("relations", [])
    if isinstance(raw_relations, list):
        if mode == "public" and publication_mode == "METADATA_ONLY":
            projected["relations"] = []
        else:
            for rel in raw_relations:
                if not isinstance(rel, dict):
                    continue
                rid = rel.get("relationId") or rel.get("id")
                rtype = rel.get("type")
                src = rel.get("sourceEntityId")
                tgt = rel.get("targetEntityId")
                if not rid or not rtype or not src or not tgt:
                    continue
                clean_rel: dict[str, Any] = {
                    "relationId": str(rid),
                    "type": str(rtype),
                    "sourceEntityId": str(src),
                    "targetEntityId": str(tgt),
                }
                if "outgoingLabel" in rel:
                    clean_rel["outgoingLabel"] = str(rel["outgoingLabel"])
                if "incomingLabel" in rel:
                    clean_rel["incomingLabel"] = str(rel["incomingLabel"])
                projected["relations"].append(clean_rel)

    # unresolvedReferences only in restricted_preview
    if mode == "restricted_preview" and "unresolvedReferences" in book:
        raw_unres = book["unresolvedReferences"]
        if isinstance(raw_unres, list):
            projected["unresolvedReferences"] = []
            for u in raw_unres:
                if isinstance(u, dict) and "name" in u:
                    clean_u: dict[str, Any] = {"name": str(u["name"])}
                    if "sourceEntityId" in u:
                        clean_u["sourceEntityId"] = str(u["sourceEntityId"])
                    if "provenance" in u:
                        clean_u["provenance"] = dict(u["provenance"])
                    if "status" in u:
                        clean_u["status"] = str(u["status"])
                    projected["unresolvedReferences"].append(clean_u)

    return projected
