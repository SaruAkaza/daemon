from __future__ import annotations

import pytest

from scripts.agents.frontend_labels import (
    RELATION_LABELS,
    entity_label,
    relation_labels,
)
from scripts.agents.site_view_model import (
    ProjectionError,
    validate_projection,
)


def test_missing_catalog_is_invalid():
    with pytest.raises(ProjectionError, match="catalog.json"):
        validate_projection({})


def test_missing_search_index_is_invalid():
    files = {
        "catalog.json": {
            "siteViewModelVersion": "1",
            "mode": "restricted_preview",
            "projectionId": "abc123sha",
            "books": [],
        }
    }
    with pytest.raises(ProjectionError, match="search-index.json"):
        validate_projection(files)


def test_choose_power_labels():
    assert relation_labels("CAN_CHOOSE_POWER") == (
        "Pode escolher poder",
        "Pode ser escolhido por",
    )


def test_all_canonical_predicates_have_labels():
    expected_predicates = [
        "CAN_CHOOSE_POWER",
        "HAS_POWER",
        "HAS_WEAKNESS",
        "REQUIRES",
        "GRANTS",
        "BELONGS_TO",
        "DERIVED_FROM",
        "APPEARS_IN",
        "MODIFIES",
        "REPLACES",
        "ALTERNATIVE_TO",
        "HAS_SKILL",
        "USES_RULE",
    ]
    for pred in expected_predicates:
        out_lbl, in_lbl = relation_labels(pred)
        assert isinstance(out_lbl, str) and len(out_lbl) > 0
        assert isinstance(in_lbl, str) and len(in_lbl) > 0


def test_unknown_predicate_raises_projection_error():
    with pytest.raises(ProjectionError, match="Unknown predicate"):
        relation_labels("INVENTED_PREDICATE")


def test_entity_labels_known_and_unknown():
    assert entity_label("creature_npc") == "Criatura"
    assert entity_label("power_magic", "poder") == "Poder"
    assert entity_label("power_magic", "magia") == "Magia"
    assert entity_label("character_option", "aprimoramento") == "Aprimoramento"
    assert entity_label("character_option", "fraqueza") == "Fraqueza"

    with pytest.raises(ProjectionError, match="Unknown entity category"):
        entity_label("invented_category")


def test_version_divergence_is_invalid():
    files = {
        "catalog.json": {
            "siteViewModelVersion": "1",
            "mode": "restricted_preview",
            "projectionId": "sha1",
            "books": [],
        },
        "search-index.json": {
            "siteViewModelVersion": "2",
            "mode": "restricted_preview",
            "projectionId": "sha1",
            "entries": [],
        },
    }
    with pytest.raises(ProjectionError, match="siteViewModelVersion"):
        validate_projection(files)


def test_mode_divergence_is_invalid():
    files = {
        "catalog.json": {
            "siteViewModelVersion": "1",
            "mode": "restricted_preview",
            "projectionId": "sha1",
            "books": [],
        },
        "search-index.json": {
            "siteViewModelVersion": "1",
            "mode": "public",
            "projectionId": "sha1",
            "entries": [],
        },
    }
    with pytest.raises(ProjectionError, match="mode"):
        validate_projection(files)


def test_projection_id_divergence_is_invalid():
    files = {
        "catalog.json": {
            "siteViewModelVersion": "1",
            "mode": "restricted_preview",
            "projectionId": "sha1",
            "books": [],
        },
        "search-index.json": {
            "siteViewModelVersion": "1",
            "mode": "restricted_preview",
            "projectionId": "sha2",
            "entries": [],
        },
    }
    with pytest.raises(ProjectionError, match="projectionId"):
        validate_projection(files)


def test_catalog_book_path_invalid():
    bad_paths = ["/absolute/path.json", "../traversal.json", "books\\windows.json", "other/dir.json", "books/wrong.json"]
    for bad in bad_paths:
        files = {
            "catalog.json": {
                "siteViewModelVersion": "1",
                "mode": "restricted_preview",
                "projectionId": "sha1",
                "books": [
                    {
                        "bookId": "synthetic",
                        "title": "Synthetic Book",
                        "publicationMode": "NOT_PUBLIC",
                        "path": bad,
                        "groups": [],
                    }
                ],
            },
            "search-index.json": {
                "siteViewModelVersion": "1",
                "mode": "restricted_preview",
                "projectionId": "sha1",
                "entries": [],
            },
        }
        with pytest.raises(ProjectionError):
            validate_projection(files)


def test_missing_referenced_book_file():
    files = {
        "catalog.json": {
            "siteViewModelVersion": "1",
            "mode": "restricted_preview",
            "projectionId": "sha1",
            "books": [
                {
                    "bookId": "synthetic",
                    "title": "Synthetic Book",
                    "publicationMode": "NOT_PUBLIC",
                    "path": "books/synthetic.json",
                    "groups": [],
                }
            ],
        },
        "search-index.json": {
            "siteViewModelVersion": "1",
            "mode": "restricted_preview",
            "projectionId": "sha1",
            "entries": [],
        },
    }
    with pytest.raises(ProjectionError, match="books/synthetic.json"):
        validate_projection(files)


def test_duplicate_entity_ids_in_same_book():
    files = {
        "catalog.json": {
            "siteViewModelVersion": "1",
            "mode": "restricted_preview",
            "projectionId": "sha1",
            "books": [
                {
                    "bookId": "synthetic",
                    "title": "Synthetic Book",
                    "publicationMode": "NOT_PUBLIC",
                    "path": "books/synthetic.json",
                    "groups": [],
                }
            ],
        },
        "search-index.json": {
            "siteViewModelVersion": "1",
            "mode": "restricted_preview",
            "projectionId": "sha1",
            "entries": [],
        },
        "books/synthetic.json": {
            "siteViewModelVersion": "1",
            "mode": "restricted_preview",
            "projectionId": "sha1",
            "book": {
                "bookId": "synthetic",
                "title": "Synthetic Book",
                "publicationMode": "NOT_PUBLIC",
            },
            "groups": [],
            "entities": [
                {
                    "entityId": "ent-1",
                    "type": "creature_npc",
                    "displayType": "Criatura",
                    "name": "Lobo",
                    "aliases": [],
                    "tags": [],
                    "content": [],
                    "provenance": {"source": "synthetic", "pages": [1]},
                },
                {
                    "entityId": "ent-1",
                    "type": "creature_npc",
                    "displayType": "Criatura",
                    "name": "Lobo Duplicado",
                    "aliases": [],
                    "tags": [],
                    "content": [],
                    "provenance": {"source": "synthetic", "pages": [1]},
                },
            ],
            "relations": [],
        },
    }
    with pytest.raises(ProjectionError, match="Duplicate entityId"):
        validate_projection(files)


def test_public_mode_rejects_technical_details_and_unresolved():
    files_with_tech = {
        "catalog.json": {
            "siteViewModelVersion": "1",
            "mode": "public",
            "projectionId": "sha1",
            "books": [
                {
                    "bookId": "synthetic",
                    "title": "Synthetic Book",
                    "publicationMode": "FULL_TEXT",
                    "path": "books/synthetic.json",
                    "groups": [],
                }
            ],
        },
        "search-index.json": {
            "siteViewModelVersion": "1",
            "mode": "public",
            "projectionId": "sha1",
            "entries": [
                {
                    "entityId": "ent-1",
                    "route": "#/entity/ent-1",
                    "name": "Lobo",
                    "aliases": [],
                    "type": "creature_npc",
                    "displayType": "Criatura",
                    "bookId": "synthetic",
                    "bookTitle": "Synthetic Book",
                    "tags": [],
                    "searchText": "lobo",
                }
            ],
        },
        "books/synthetic.json": {
            "siteViewModelVersion": "1",
            "mode": "public",
            "projectionId": "sha1",
            "book": {
                "bookId": "synthetic",
                "title": "Synthetic Book",
                "publicationMode": "FULL_TEXT",
            },
            "groups": [],
            "entities": [
                {
                    "entityId": "ent-1",
                    "type": "creature_npc",
                    "displayType": "Criatura",
                    "name": "Lobo",
                    "aliases": [],
                    "tags": [],
                    "content": [],
                    "provenance": {"source": "synthetic", "pages": [1]},
                    "technicalDetails": {"internal": True},
                }
            ],
            "relations": [],
        },
    }
    with pytest.raises(ProjectionError, match="technicalDetails"):
        validate_projection(files_with_tech)

    files_with_unresolved = {
        "catalog.json": {
            "siteViewModelVersion": "1",
            "mode": "public",
            "projectionId": "sha1",
            "books": [
                {
                    "bookId": "synthetic",
                    "title": "Synthetic Book",
                    "publicationMode": "FULL_TEXT",
                    "path": "books/synthetic.json",
                    "groups": [],
                }
            ],
        },
        "search-index.json": {
            "siteViewModelVersion": "1",
            "mode": "public",
            "projectionId": "sha1",
            "entries": [
                {
                    "entityId": "ent-1",
                    "route": "#/entity/ent-1",
                    "name": "Lobo",
                    "aliases": [],
                    "type": "creature_npc",
                    "displayType": "Criatura",
                    "bookId": "synthetic",
                    "bookTitle": "Synthetic Book",
                    "tags": [],
                    "searchText": "lobo",
                }
            ],
        },
        "books/synthetic.json": {
            "siteViewModelVersion": "1",
            "mode": "public",
            "projectionId": "sha1",
            "book": {
                "bookId": "synthetic",
                "title": "Synthetic Book",
                "publicationMode": "FULL_TEXT",
            },
            "groups": [],
            "entities": [
                {
                    "entityId": "ent-1",
                    "type": "creature_npc",
                    "displayType": "Criatura",
                    "name": "Lobo",
                    "aliases": [],
                    "tags": [],
                    "content": [],
                    "provenance": {"source": "synthetic", "pages": [1]},
                }
            ],
            "relations": [],
            "unresolvedReferences": [{"name": "Rapidez"}],
        },
    }
    with pytest.raises(ProjectionError, match="unresolvedReferences"):
        validate_projection(files_with_unresolved)


def test_positive_complete_projection_set():
    files = {
        "catalog.json": {
            "siteViewModelVersion": "1",
            "mode": "restricted_preview",
            "projectionId": "sha_valid_123",
            "books": [
                {
                    "bookId": "synthetic",
                    "title": "Synthetic Book",
                    "publicationMode": "NOT_PUBLIC",
                    "path": "books/synthetic.json",
                    "groups": [
                        {"id": "criaturas", "label": "Criaturas", "entityIds": ["ent-1"]}
                    ],
                }
            ],
        },
        "search-index.json": {
            "siteViewModelVersion": "1",
            "mode": "restricted_preview",
            "projectionId": "sha_valid_123",
            "entries": [
                {
                    "entityId": "ent-1",
                    "route": "#/entity/ent-1",
                    "name": "Lobo",
                    "aliases": ["Canis lupus"],
                    "type": "creature_npc",
                    "displayType": "Criatura",
                    "bookId": "synthetic",
                    "bookTitle": "Synthetic Book",
                    "tags": ["animal", "floresta"],
                    "searchText": "lobo canis lupus",
                }
            ],
        },
        "books/synthetic.json": {
            "siteViewModelVersion": "1",
            "mode": "restricted_preview",
            "projectionId": "sha_valid_123",
            "book": {
                "bookId": "synthetic",
                "title": "Synthetic Book",
                "publicationMode": "NOT_PUBLIC",
            },
            "groups": [
                {"id": "criaturas", "label": "Criaturas", "entityIds": ["ent-1"]}
            ],
            "entities": [
                {
                    "entityId": "ent-1",
                    "type": "creature_npc",
                    "displayType": "Criatura",
                    "name": "Lobo",
                    "aliases": ["Canis lupus"],
                    "tags": ["animal", "floresta"],
                    "content": [
                        {"title": "Descrição", "paragraphs": ["Um grande canídeo selvagem."]}
                    ],
                    "provenance": {"source": "synthetic", "pages": [1, 2]},
                    "technicalDetails": {"sourceId": "synthetic-src-1"},
                }
            ],
            "relations": [
                {
                    "relationId": "rel-1",
                    "type": "CAN_CHOOSE_POWER",
                    "sourceEntityId": "ent-1",
                    "targetEntityId": "ent-1",
                    "outgoingLabel": "Pode escolher poder",
                    "incomingLabel": "Pode ser escolhido por",
                }
            ],
            "unresolvedReferences": [
                {
                    "sourceEntityId": "ent-1",
                    "name": "Rapidez",
                    "provenance": {"source": "synthetic", "pages": [2]},
                    "status": "UNRESOLVED_PENDING_CROSS_BOOK_LINK",
                }
            ],
        },
    }
    validate_projection(files)