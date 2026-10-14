from __future__ import annotations

import pytest

from scripts.agents.frontend_policy import project_allowed_book
from scripts.agents.site_view_model import ProjectionError


def test_unknown_not_public_is_excluded_in_public():
    book = {
        "bookId": "synthetic",
        "title": "Synthetic Book",
        "rightsStatus": "UNKNOWN",
        "publicationMode": "NOT_PUBLIC",
        "entities": [
            {
                "id": "ent-1",
                "name": "Lobo",
                "category": "creature_npc",
                "source": "synthetic",
                "pages": [1],
                "entries": ["Texto secreto restrito."],
            }
        ],
        "relations": [],
        "sources": {},
    }
    assert project_allowed_book(book, "public") is None


def test_unknown_with_permissive_mode_is_excluded_in_public():
    book = {
        "bookId": "synthetic",
        "title": "Synthetic Book",
        "rightsStatus": "UNKNOWN",
        "publicationMode": "FULL_TEXT",
        "entities": [],
        "relations": [],
        "sources": {},
    }
    assert project_allowed_book(book, "public") is None


def test_not_public_with_authorized_is_excluded_in_public():
    book = {
        "bookId": "synthetic",
        "title": "Synthetic Book",
        "rightsStatus": "AUTHORIZED",
        "publicationMode": "NOT_PUBLIC",
        "entities": [],
        "relations": [],
        "sources": {},
    }
    assert project_allowed_book(book, "public") is None


def test_restricted_preview_allows_unknown_not_public():
    book = {
        "bookId": "synthetic",
        "title": "Synthetic Book",
        "rightsStatus": "UNKNOWN",
        "publicationMode": "NOT_PUBLIC",
        "entities": [
            {
                "id": "ent-1",
                "name": "Lobo",
                "category": "creature_npc",
                "source": "synthetic",
                "pages": [1],
                "entries": ["Texto de preview local."],
            }
        ],
        "relations": [],
        "unresolvedReferences": [{"name": "Rapidez", "source": "synthetic"}],
        "sources": {},
    }
    projected = project_allowed_book(book, "restricted_preview")
    assert projected is not None
    assert projected["bookId"] == "synthetic"
    assert len(projected["entities"]) == 1
    assert "unresolvedReferences" in projected


def test_summary_and_metadata_strips_full_text():
    book = {
        "bookId": "synthetic",
        "title": "Synthetic Book",
        "rightsStatus": "AUTHORIZED",
        "publicationMode": "SUMMARY_AND_METADATA",
        "entities": [
            {
                "id": "ent-1",
                "name": "Lobo",
                "category": "creature_npc",
                "source": "synthetic",
                "pages": [1],
                "summary": "Resumo autorizado do lobo.",
                "entries": ["Texto integral que não deve vazar."],
            }
        ],
        "relations": [],
        "sources": {},
    }
    projected = project_allowed_book(book, "public")
    assert projected is not None
    ent = projected["entities"][0]
    # Content must contain summary, not entries
    assert len(ent["content"]) == 1
    assert ent["content"][0]["title"] == "Resumo"
    assert "Resumo autorizado" in ent["content"][0]["paragraphs"][0]
    assert "Texto integral que não deve vazar" not in str(ent["content"])


def test_metadata_only_strips_content_and_relations():
    book = {
        "bookId": "synthetic",
        "title": "Synthetic Book",
        "rightsStatus": "AUTHORIZED",
        "publicationMode": "METADATA_ONLY",
        "entities": [
            {
                "id": "ent-1",
                "name": "Lobo",
                "category": "creature_npc",
                "source": "synthetic",
                "pages": [1],
                "summary": "Resumo que deve ser omitido em METADATA_ONLY.",
                "entries": ["Texto integral."],
            }
        ],
        "relations": [
            {
                "id": "rel-1",
                "type": "CAN_CHOOSE_POWER",
                "sourceEntityId": "ent-1",
                "targetEntityId": "ent-1",
            }
        ],
        "sources": {},
    }
    projected = project_allowed_book(book, "public")
    assert projected is not None
    ent = projected["entities"][0]
    assert ent["content"] == []
    assert projected["relations"] == []


def test_public_mode_omits_unresolved_and_technical_details():
    book = {
        "bookId": "synthetic",
        "title": "Synthetic Book",
        "rightsStatus": "AUTHORIZED",
        "publicationMode": "FULL_TEXT",
        "entities": [
            {
                "id": "ent-1",
                "name": "Lobo",
                "category": "creature_npc",
                "source": "synthetic",
                "pages": [1],
                "entries": ["Texto completo."],
                "technicalDetails": {"sourceId": "src-1", "internalSecret": 123},
            }
        ],
        "relations": [],
        "unresolvedReferences": [{"name": "Rapidez"}],
        "sources": {},
    }
    projected = project_allowed_book(book, "public")
    assert projected is not None
    assert "unresolvedReferences" not in projected
    ent = projected["entities"][0]
    assert "technicalDetails" not in ent


def test_invalid_mode_raises_projection_error():
    book = {
        "bookId": "synthetic",
        "title": "Synthetic Book",
        "rightsStatus": "AUTHORIZED",
        "publicationMode": "FULL_TEXT",
        "entities": [],
        "relations": [],
        "sources": {},
    }
    with pytest.raises(ProjectionError, match="Invalid projection mode"):
        project_allowed_book(book, "unsupported_mode")


def test_sentinels_never_leak_in_any_field():
    sentinel = "SECRET_SENTINEL_XYZ_999"
    book = {
        "bookId": "synthetic",
        "title": "Synthetic Book",
        "rightsStatus": "AUTHORIZED",
        "publicationMode": "FULL_TEXT",
        "secret_field": sentinel,
        "internal_notes": sentinel,
        "entities": [
            {
                "id": "ent-1",
                "name": "Lobo",
                "category": "creature_npc",
                "source": "synthetic",
                "pages": [1],
                "entries": ["Texto normal."],
                "leaked_dict": {sentinel: True},
                "unapproved_list": [sentinel],
            }
        ],
        "relations": [],
        "sources": {},
    }
    projected = project_allowed_book(book, "public")
    assert projected is not None
    assert sentinel not in str(projected)