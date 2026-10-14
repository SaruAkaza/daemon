from __future__ import annotations

import re
from typing import Any


class ProjectionError(ValueError):
    """Raised when a projection violates the Site View Model contract."""
    pass


VALID_MODES = {"restricted_preview", "public"}
EXPECTED_VERSION = "1"
BOOK_PATH_PATTERN = re.compile(r"^books/([a-z0-9-]+)\.json$")


def validate_projection(files: dict[str, dict[str, Any]]) -> None:
    """Validate that files strictly conform to the Site View Model contract.

    Fails-closed on any schema divergence, missing files, referential errors,
    invalid paths, or unauthorized technical details in public mode.
    """
    if "catalog.json" not in files:
        raise ProjectionError("Missing catalog.json in projection files")

    if "search-index.json" not in files:
        raise ProjectionError("Missing search-index.json in projection files")

    catalog = files["catalog.json"]
    if not isinstance(catalog, dict):
        raise ProjectionError("catalog.json must be a JSON object")

    target_version = catalog.get("siteViewModelVersion")
    if target_version != EXPECTED_VERSION:
        raise ProjectionError(
            f"Invalid or unsupported siteViewModelVersion: '{target_version}' (expected '{EXPECTED_VERSION}')"
        )

    mode = catalog.get("mode")
    if mode not in VALID_MODES:
        raise ProjectionError(f"Invalid projection mode: '{mode}' (expected one of {VALID_MODES})")

    projection_id = catalog.get("projectionId")
    if not projection_id or not isinstance(projection_id, str):
        raise ProjectionError("Missing or invalid projectionId in catalog.json")

    # Validate version, mode, and projectionId consistency across all files
    for filename, payload in files.items():
        if not isinstance(payload, dict):
            raise ProjectionError(f"File '{filename}' must contain a JSON object")
        if payload.get("siteViewModelVersion") != target_version:
            raise ProjectionError(
                f"File '{filename}' has mismatched siteViewModelVersion: '{payload.get('siteViewModelVersion')}' vs '{target_version}'"
            )
        if payload.get("mode") != mode:
            raise ProjectionError(
                f"File '{filename}' has mismatched mode: '{payload.get('mode')}' vs '{mode}'"
            )
        if payload.get("projectionId") != projection_id:
            raise ProjectionError(
                f"File '{filename}' has mismatched projectionId: '{payload.get('projectionId')}' vs '{projection_id}'"
            )

    # 1. Validate catalog.json structure
    books = catalog.get("books")
    if not isinstance(books, list):
        raise ProjectionError("catalog.json 'books' property must be a list")

    catalog_book_ids = set()
    catalog_book_paths = set()

    for book in books:
        if not isinstance(book, dict):
            raise ProjectionError("catalog.json book entry must be an object")
        bid = book.get("bookId")
        title = book.get("title")
        pub_mode = book.get("publicationMode")
        path = book.get("path")
        groups = book.get("groups")

        if not bid or not isinstance(bid, str):
            raise ProjectionError("Catalog book missing valid bookId")
        if not title or not isinstance(title, str):
            raise ProjectionError(f"Catalog book '{bid}' missing valid title")
        if not pub_mode or not isinstance(pub_mode, str):
            raise ProjectionError(f"Catalog book '{bid}' missing valid publicationMode")
        if not isinstance(groups, list):
            raise ProjectionError(f"Catalog book '{bid}' groups must be a list")

        if not path or not isinstance(path, str):
            raise ProjectionError(f"Catalog book '{bid}' missing valid path")

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

        page_count = book.get("pageCount")
        if page_count is not None and not isinstance(page_count, int):
            raise ProjectionError(f"Catalog book '{bid}' has invalid pageCount")

        # Security & Path Containment: must be books/<bookId>.json
        match = BOOK_PATH_PATTERN.match(path)
        if not match or match.group(1) != bid or "\\" in path or ".." in path or path.startswith("/"):
            raise ProjectionError(
                f"Invalid book path '{path}' for bookId '{bid}'. Must be strictly 'books/{bid}.json'"
            )

        if bid in catalog_book_ids:
            raise ProjectionError(f"Duplicate bookId in catalog: '{bid}'")
        catalog_book_ids.add(bid)

        if path not in files:
            raise ProjectionError(f"Referenced book file '{path}' not found in projection files")
        catalog_book_paths.add(path)

    # 2. Validate search-index.json structure
    search_index = files["search-index.json"]
    entries = search_index.get("entries")
    if not isinstance(entries, list):
        raise ProjectionError("search-index.json 'entries' must be a list")

    index_entity_ids = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ProjectionError("Search index entry must be an object")
        eid = entry.get("entityId")
        route = entry.get("route")
        name = entry.get("name")
        aliases = entry.get("aliases")
        type_ = entry.get("type")
        display_type = entry.get("displayType")
        entry_book_id = entry.get("bookId")
        tags = entry.get("tags")
        search_text = entry.get("searchText")

        if not eid or not isinstance(eid, str):
            raise ProjectionError("Search index entry missing valid entityId")
        if route != f"#/entity/{eid}":
            raise ProjectionError(f"Search index entry '{eid}' invalid route: '{route}' (expected '#/entity/{eid}')")
        if not name or not isinstance(name, str):
            raise ProjectionError(f"Search index entry '{eid}' missing name")
        if not isinstance(aliases, list):
            raise ProjectionError(f"Search index entry '{eid}' aliases must be a list")
        if not type_ or not isinstance(type_, str):
            raise ProjectionError(f"Search index entry '{eid}' missing type")
        if not display_type or not isinstance(display_type, str):
            raise ProjectionError(f"Search index entry '{eid}' missing displayType")
        if entry_book_id not in catalog_book_ids:
            raise ProjectionError(f"Search index entry '{eid}' points to unknown bookId '{entry_book_id}'")
        if not isinstance(tags, list):
            raise ProjectionError(f"Search index entry '{eid}' tags must be a list")
        if search_text is None or not isinstance(search_text, str):
            raise ProjectionError(f"Search index entry '{eid}' missing searchText")

        if eid in index_entity_ids:
            raise ProjectionError(f"Duplicate entityId in search index: '{eid}'")
        index_entity_ids.add(eid)

    # 3. Validate each book file
    all_entity_ids = set()
    all_relation_ids = set()

    for path, book_file in files.items():
        if path in ("catalog.json", "search-index.json"):
            continue

        if path not in catalog_book_paths:
            raise ProjectionError(f"Unexpected file in projection: '{path}'")

        book_meta = book_file.get("book")
        if not isinstance(book_meta, dict):
            raise ProjectionError(f"File '{path}' missing 'book' metadata object")

        file_book_id = book_meta.get("bookId")
        if f"books/{file_book_id}.json" != path:
            raise ProjectionError(f"File '{path}' has mismatched book.bookId '{file_book_id}'")

        groups = book_file.get("groups")
        if not isinstance(groups, list):
            raise ProjectionError(f"File '{path}' groups must be a list")

        entities = book_file.get("entities")
        if not isinstance(entities, list):
            raise ProjectionError(f"File '{path}' entities must be a list")

        relations = book_file.get("relations")
        if not isinstance(relations, list):
            raise ProjectionError(f"File '{path}' relations must be a list")

        # Public mode restrictions
        if mode == "public":
            if "unresolvedReferences" in book_file:
                raise ProjectionError(f"Public mode file '{path}' contains forbidden 'unresolvedReferences'")
            if "technicalDetails" in book_file:
                raise ProjectionError(f"Public mode file '{path}' contains forbidden 'technicalDetails'")

        # Validate entities in book
        for entity in entities:
            if not isinstance(entity, dict):
                raise ProjectionError(f"Entity in '{path}' must be an object")

            eid = entity.get("entityId")
            etype = entity.get("type")
            display_type = entity.get("displayType")
            ename = entity.get("name")
            aliases = entity.get("aliases")
            tags = entity.get("tags")
            content = entity.get("content")
            provenance = entity.get("provenance")

            if not eid or not isinstance(eid, str):
                raise ProjectionError(f"Entity in '{path}' missing valid entityId")
            if not etype or not isinstance(etype, str):
                raise ProjectionError(f"Entity '{eid}' in '{path}' missing valid type")
            if not display_type or not isinstance(display_type, str):
                raise ProjectionError(f"Entity '{eid}' in '{path}' missing valid displayType")
            if not ename or not isinstance(ename, str):
                raise ProjectionError(f"Entity '{eid}' in '{path}' missing valid name")
            if not isinstance(aliases, list):
                raise ProjectionError(f"Entity '{eid}' in '{path}' aliases must be a list")
            if not isinstance(tags, list):
                raise ProjectionError(f"Entity '{eid}' in '{path}' tags must be a list")
            if not isinstance(content, list):
                raise ProjectionError(f"Entity '{eid}' in '{path}' content must be a list")
            for block in content:
                if not isinstance(block, dict) or "title" not in block or "paragraphs" not in block:
                    raise ProjectionError(f"Entity '{eid}' content block missing required title/paragraphs")
                if not isinstance(block["paragraphs"], list):
                    raise ProjectionError(f"Entity '{eid}' content block paragraphs must be a list")

            if not isinstance(provenance, dict) or "source" not in provenance or "pages" not in provenance:
                raise ProjectionError(f"Entity '{eid}' in '{path}' missing valid provenance (source and pages)")
            if not isinstance(provenance["pages"], list):
                raise ProjectionError(f"Entity '{eid}' in '{path}' provenance.pages must be a list")

            if mode == "public" and "technicalDetails" in entity:
                raise ProjectionError(f"Public mode entity '{eid}' contains forbidden 'technicalDetails'")

            if eid in all_entity_ids:
                raise ProjectionError(f"Duplicate entityId across projection: '{eid}'")
            all_entity_ids.add(eid)

        # Validate relations in book
        for relation in relations:
            if not isinstance(relation, dict):
                raise ProjectionError(f"Relation in '{path}' must be an object")

            rid = relation.get("relationId")
            rtype = relation.get("type")
            src_id = relation.get("sourceEntityId")
            tgt_id = relation.get("targetEntityId")
            out_lbl = relation.get("outgoingLabel")
            in_lbl = relation.get("incomingLabel")

            if not rid or not isinstance(rid, str):
                raise ProjectionError(f"Relation in '{path}' missing relationId")
            if not rtype or not isinstance(rtype, str):
                raise ProjectionError(f"Relation '{rid}' missing type")
            if not src_id or not isinstance(src_id, str):
                raise ProjectionError(f"Relation '{rid}' missing sourceEntityId")
            if not tgt_id or not isinstance(tgt_id, str):
                raise ProjectionError(f"Relation '{rid}' missing targetEntityId")
            if not out_lbl or not isinstance(out_lbl, str):
                raise ProjectionError(f"Relation '{rid}' missing outgoingLabel")
            if not in_lbl or not isinstance(in_lbl, str):
                raise ProjectionError(f"Relation '{rid}' missing incomingLabel")

            if rid in all_relation_ids:
                raise ProjectionError(f"Duplicate relationId in book '{path}': '{rid}'")
            all_relation_ids.add(rid)

        # Validate unresolvedReferences if in restricted_preview
        if "unresolvedReferences" in book_file:
            unres = book_file["unresolvedReferences"]
            if not isinstance(unres, list):
                raise ProjectionError(f"File '{path}' unresolvedReferences must be a list")
            for u in unres:
                if not isinstance(u, dict) or "name" not in u:
                    raise ProjectionError(f"Unresolved reference in '{path}' missing required name")
