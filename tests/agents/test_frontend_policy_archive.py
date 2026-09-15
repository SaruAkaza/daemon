import pytest
from scripts.agents.archive_inventory_loader import ArchiveInventoryLoader
from scripts.agents.frontend_projector import FrontendProjector
from scripts.agents.site_view_model import validate_projection


def test_public_policy_matrix_with_synthetic_fixtures():
    projector = FrontendProjector()

    synthetic_books = [
        # 1. UNKNOWN + NOT_PUBLIC -> excluded
        {
            "bookId": "s-unknown",
            "title": "S Unknown",
            "rightsStatus": "UNKNOWN",
            "publicationMode": "NOT_PUBLIC",
            "entities": [],
        },
        # 2. PRIVATE + NOT_PUBLIC -> excluded
        {
            "bookId": "s-private",
            "title": "S Private",
            "rightsStatus": "PRIVATE",
            "publicationMode": "NOT_PUBLIC",
            "entities": [],
        },
        # 3. PUBLIC_DOMAIN + FULL_TEXT -> permitted with full content
        {
            "bookId": "s-pd",
            "title": "S Public Domain",
            "rightsStatus": "PUBLIC_DOMAIN",
            "publicationMode": "FULL_TEXT",
            "entities": [
                {
                    "id": "e-pd-1",
                    "name": "Entidade PD",
                    "category": "core_rule",
                    "content": [{"title": "C1", "paragraphs": ["Texto integral"]}],
                },
                {
                    "id": "e-pd-2",
                    "name": "Entidade PD 2",
                    "category": "core_rule",
                    "content": [{"title": "C2", "paragraphs": ["Texto 2"]}],
                },
            ],
            "relations": [
                {
                    "relationId": "r-pd-1",
                    "type": "REQUIRES",
                    "sourceEntityId": "e-pd-1",
                    "targetEntityId": "e-pd-2",
                }
            ],
        },
        # 4. AUTHORIZED + FULL_TEXT -> permitted with full content
        {
            "bookId": "s-auth",
            "title": "S Authorized",
            "rightsStatus": "AUTHORIZED",
            "publicationMode": "FULL_TEXT",
            "entities": [
                {
                    "id": "e-auth-1",
                    "name": "Entidade Auth",
                    "category": "character_option",
                    "content": [{"title": "C1", "paragraphs": ["Texto"]}],
                }
            ],
        },
        # 5. METADATA_ONLY + METADATA_ONLY -> permitted in catalog, but content and relations strictly stripped
        {
            "bookId": "s-meta",
            "title": "S Metadata",
            "rightsStatus": "METADATA_ONLY",
            "publicationMode": "METADATA_ONLY",
            "entities": [
                {
                    "id": "e-meta-1",
                    "name": "Entidade Meta",
                    "category": "power_magic",
                    "content": [{"title": "Segredo", "paragraphs": ["Não pode vazar"]}],
                },
                {
                    "id": "e-meta-2",
                    "name": "Entidade Meta 2",
                    "category": "power_magic",
                    "content": [{"title": "Segredo 2", "paragraphs": ["Não pode vazar 2"]}],
                },
            ],
            "relations": [
                {
                    "relationId": "r-meta-1",
                    "type": "HAS_POWER",
                    "sourceEntityId": "e-meta-1",
                    "targetEntityId": "e-meta-2",
                }
            ],
        },
        # 6. AUTHORIZED + SUMMARY_AND_METADATA -> permitted with summary only
        {
            "bookId": "s-summary",
            "title": "S Summary",
            "rightsStatus": "AUTHORIZED",
            "publicationMode": "SUMMARY_AND_METADATA",
            "entities": [
                {
                    "id": "e-sum-1",
                    "name": "Entidade Sum",
                    "category": "creature_npc",
                    "summary": "Resumo autorizado",
                    "content": [{"title": "Corpo", "paragraphs": ["Texto protegido"]}],
                }
            ],
        },
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
