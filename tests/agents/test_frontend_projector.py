from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import pytest

from scripts.agents.frontend_projector import FrontendProjector
from scripts.agents.site_view_model import ProjectionError, validate_projection


def synthetic_books() -> list[dict]:
    return [
        {
            "bookId": "synth-book-1",
            "title": "Synthetic Book 1",
            "rightsStatus": "UNKNOWN",
            "publicationMode": "NOT_PUBLIC",
            "groups": [
                {"id": "criaturas", "label": "Criaturas", "entityIds": ["ent-lobo"]}
            ],
            "entities": [
                {
                    "id": "ent-lobo",
                    "name": "Lobo Selvagem",
                    "aliases": ["Canis"],
                    "category": "creature_npc",
                    "source": "synth-book-1",
                    "pages": [1, 2],
                    "entries": ["Um lobo feroz."],
                    "technicalDetails": {"sourceId": "src-1"},
                },
                {
                    "id": "ent-morder",
                    "name": "Morder",
                    "aliases": [],
                    "category": "power_magic",
                    "subtype": "poder",
                    "source": "synth-book-1",
                    "pages": [2],
                    "entries": ["Mordida potente."],
                }
            ],
            "relations": [
                {
                    "id": "rel-1",
                    "type": "CAN_CHOOSE_POWER",
                    "sourceEntityId": "ent-lobo",
                    "targetEntityId": "ent-morder",
                }
            ],
            "unresolvedReferences": [
                {
                    "sourceEntityId": "ent-lobo",
                    "name": "Rapidez",
                    "provenance": {"source": "synth-book-1", "pages": [2]},
                    "status": "UNRESOLVED_PENDING_CROSS_BOOK_LINK",
                }
            ],
            "sources": {},
        }
    ]


def test_missing_target_blocks():
    books = synthetic_books()
    books[0]["relations"][0]["targetEntityId"] = "absent-target-id"
    with pytest.raises(ProjectionError, match="target missing"):
        FrontendProjector().build(books, "restricted_preview")


def test_input_unchanged():
    books = synthetic_books()
    before = deepcopy(books)
    FrontendProjector().build(books, "restricted_preview")
    assert books == before


def test_excluded_endpoint_omits_relation_without_leak():
    # Book 1 is PUBLIC (FULL_TEXT), Book 2 is NOT_PUBLIC
    books = [
        {
            "bookId": "public-book",
            "title": "Public Book",
            "rightsStatus": "AUTHORIZED",
            "publicationMode": "FULL_TEXT",
            "groups": [],
            "entities": [
                {
                    "id": "ent-pub-1",
                    "name": "Herói Público",
                    "aliases": [],
                    "category": "character_option",
                    "source": "public-book",
                    "pages": [10],
                    "entries": ["Herói público."],
                }
            ],
            "relations": [
                {
                    "id": "rel-cross",
                    "type": "REQUIRES",
                    "sourceEntityId": "ent-pub-1",
                    "targetEntityId": "ent-secret-1",
                }
            ],
            "sources": {},
        },
        {
            "bookId": "secret-book",
            "title": "Secret Book",
            "rightsStatus": "UNKNOWN",
            "publicationMode": "NOT_PUBLIC",
            "groups": [],
            "entities": [
                {
                    "id": "ent-secret-1",
                    "name": "Poder Secreto Restrito",
                    "aliases": [],
                    "category": "power_magic",
                    "source": "secret-book",
                    "pages": [5],
                    "entries": ["Segredo restrito."],
                }
            ],
            "relations": [],
            "sources": {},
        },
    ]

    files = FrontendProjector().build(books, "public")
    validate_projection(files)

    # In public mode, secret-book is excluded
    assert "books/secret-book.json" not in files
    assert "books/public-book.json" in files

    # The cross-book relation must be omitted because target endpoint is not visible in public
    pub_book = files["books/public-book.json"]
    assert len(pub_book["relations"]) == 0
    # No secret name or secret ID leaked
    assert "ent-secret-1" not in str(files)
    assert "Poder Secreto Restrito" not in str(files)


def test_deterministic_projection_id_and_ordering():
    books_a = synthetic_books()
    books_b = synthetic_books()

    files_a = FrontendProjector().build(books_a, "restricted_preview")
    files_b = FrontendProjector().build(books_b, "restricted_preview")

    assert files_a["catalog.json"]["projectionId"] == files_b["catalog.json"]["projectionId"]
    assert files_a == files_b


def test_unresolved_separated_in_preview_and_absent_in_public():
    books = synthetic_books()
    # In preview: unresolvedReferences exists
    preview_files = FrontendProjector().build(books, "restricted_preview")
    validate_projection(preview_files)
    book_preview = preview_files["books/synth-book-1.json"]
    assert "unresolvedReferences" in book_preview
    assert len(book_preview["unresolvedReferences"]) == 1
    assert book_preview["unresolvedReferences"][0]["name"] == "Rapidez"

    # In public: since books is NOT_PUBLIC, 0 books are public
    public_files = FrontendProjector().build(books, "public")
    validate_projection(public_files)
    assert len(public_files["catalog.json"]["books"]) == 0
    assert "books/synth-book-1.json" not in public_files


def test_write_rejects_repo_or_docs_directory(tmp_path: Path):
    projector = FrontendProjector()
    books = synthetic_books()
    files = projector.build(books, "restricted_preview")

    repo_root = tmp_path / "fake_repo"
    repo_root.mkdir()
    docs_dir = repo_root / "docs" / "site-data"

    # Target inside repo
    with pytest.raises(ProjectionError, match="inside repository|forbidden 'docs' segment"):
        projector.write(files, docs_dir, repo_root)

    # Target containing docs
    outside_docs = tmp_path / "outside" / "Docs" / "site-data"
    with pytest.raises(ProjectionError, match="inside repository|forbidden 'docs' segment"):
        projector.write(files, outside_docs, repo_root)


def test_write_rejects_existing_nonempty_destination(tmp_path: Path):
    projector = FrontendProjector()
    books = synthetic_books()
    files = projector.build(books, "restricted_preview")

    repo_root = tmp_path / "fake_repo"
    repo_root.mkdir()
    target = tmp_path / "external_preview" / "site-data"
    target.mkdir(parents=True)
    (target / "existing_file.txt").write_text("old data", encoding="utf-8")

    with pytest.raises(ProjectionError, match="already exists|non-empty"):
        projector.write(files, target, repo_root)


def test_write_atomic_success(tmp_path: Path):
    projector = FrontendProjector()
    books = synthetic_books()
    files = projector.build(books, "restricted_preview")

    repo_root = tmp_path / "fake_repo"
    repo_root.mkdir()
    target = tmp_path / "external_preview" / "site-data"

    out_path = projector.write(files, target, repo_root)
    assert out_path == target.resolve()
    assert (target / "catalog.json").is_file()
    assert (target / "search-index.json").is_file()
    assert (target / "books" / "synth-book-1.json").is_file()


def test_public_projection_gate_six_criteria_and_leak_detection():
    """Verify the 6 security criteria of the Public Projection Gate:
    1. Rights + explicit authorization: only AUTHORIZED books enter public projection.
    2. publicationMode limits: FULL_TEXT has content, METADATA_ONLY strips content, NOT_PUBLIC excluded.
    3. Absence of restricted content in all outputs: zero sentinels, IDs, or names in any file.
    4. Absence of unresolved references and technical details in all public outputs.
    5. Absence of broken relations and excluded endpoints: dangling relations safely omitted.
    6. Contract consistency: valid Site View Model schema, mode='public', matching projectionId.
    """
    books = [
        # Book 1: Fully authorized, full text
        {
            "bookId": "pub-full-book",
            "title": "Livro Público Completo",
            "rightsStatus": "AUTHORIZED",
            "publicationMode": "FULL_TEXT",
            "groups": [{"id": "grp-herois", "label": "Heróis", "entityIds": ["ent-pub-hero"]}],
            "entities": [
                {
                    "id": "ent-pub-hero",
                    "name": "Herói Solar",
                    "aliases": ["Paladino da Luz"],
                    "category": "character_option",
                    "subtype": "classe",
                    "source": "pub-full-book",
                    "pages": [10, 11],
                    "entries": ["Guerreiro sagrado imbuído de poder solar."],
                    "technicalDetails": {"secretInternalHash": "TECH_HASH_DEADBEEF_999"},
                },
                {
                    "id": "ent-pub-power",
                    "name": "Chama Sagrada",
                    "aliases": [],
                    "category": "power_magic",
                    "subtype": "poder",
                    "source": "pub-full-book",
                    "pages": [12],
                    "entries": ["Explosão de chamas celestiais."],
                },
            ],
            "relations": [
                {
                    "id": "rel-pub-internal",
                    "type": "HAS_POWER",
                    "sourceEntityId": "ent-pub-hero",
                    "targetEntityId": "ent-pub-power",
                },
                {
                    "id": "rel-cross-to-restricted",
                    "type": "CAN_CHOOSE_POWER",
                    "sourceEntityId": "ent-pub-hero",
                    "targetEntityId": "ent-sentinel-restricted-1",
                },
            ],
            "unresolvedReferences": [
                {
                    "sourceEntityId": "ent-pub-hero",
                    "name": "Referência Pública Não Vinculada",
                    "provenance": {"source": "pub-full-book", "pages": [13]},
                    "status": "UNRESOLVED_PENDING",
                }
            ],
            "sources": {},
        },
        # Book 2: Authorized, metadata only (must strip content)
        {
            "bookId": "pub-meta-book",
            "title": "Livro de Metadados",
            "rightsStatus": "AUTHORIZED",
            "publicationMode": "METADATA_ONLY",
            "groups": [],
            "entities": [
                {
                    "id": "ent-pub-meta-item",
                    "name": "Item Apenas Metadado",
                    "aliases": ["MetaItem"],
                    "category": "item",
                    "source": "pub-meta-book",
                    "pages": [5],
                    "entries": ["Texto detalhado do item que DEVE ser removido em METADATA_ONLY."],
                }
            ],
            "relations": [],
            "sources": {},
        },
        # Book 3: Restricted book (UNKNOWN / NOT_PUBLIC) - sentinel book
        {
            "bookId": "secret-restricted-book",
            "title": "Livro Restrito Desconhecido",
            "rightsStatus": "UNKNOWN",
            "publicationMode": "NOT_PUBLIC",
            "groups": [],
            "entities": [
                {
                    "id": "ent-sentinel-restricted-1",
                    "name": "Criatura Secreta Guardiã",
                    "aliases": ["Guardião das Trevas"],
                    "category": "creature_npc",
                    "source": "secret-restricted-book",
                    "pages": [100],
                    "entries": ["Texto ultrassecreto que jamais deve ser publicado."],
                    "technicalDetails": {"classified": True},
                }
            ],
            "relations": [],
            "unresolvedReferences": [
                {
                    "sourceEntityId": "ent-sentinel-restricted-1",
                    "name": "Referência Secreta Não Vinculada",
                    "provenance": {"source": "secret-restricted-book", "pages": [101]},
                    "status": "UNRESOLVED_CLASSIFIED",
                }
            ],
            "sources": {},
        },
        # Book 4: Explicitly rejected book (REJECTED / FULL_TEXT) - must NOT be published
        {
            "bookId": "rejected-book",
            "title": "Livro Rejeitado Por Direitos",
            "rightsStatus": "REJECTED",
            "publicationMode": "FULL_TEXT",
            "groups": [],
            "entities": [
                {
                    "id": "ent-rejected-item",
                    "name": "Item Rejeitado",
                    "category": "item",
                    "source": "rejected-book",
                    "pages": [1],
                    "entries": ["Não autorizado."],
                }
            ],
            "relations": [],
            "sources": {},
        },
    ]

    projector = FrontendProjector()
    files = projector.build(books, mode="public")

    # Item 6: Contract consistency
    validate_projection(files)
    assert files["catalog.json"]["mode"] == "public"
    proj_id = files["catalog.json"]["projectionId"]
    assert proj_id
    for path_key, file_data in files.items():
        assert file_data["projectionId"] == proj_id, f"File {path_key} has inconsistent projectionId"

    # Item 1: Rights + explicit authorization
    catalog_books = {b["bookId"]: b for b in files["catalog.json"]["books"]}
    assert "pub-full-book" in catalog_books
    assert "pub-meta-book" in catalog_books
    assert "secret-restricted-book" not in catalog_books, "UNKNOWN / NOT_PUBLIC book must be excluded"
    assert "rejected-book" not in catalog_books, "REJECTED book must be excluded"
    assert "books/secret-restricted-book.json" not in files
    assert "books/rejected-book.json" not in files

    # Item 2: publicationMode limits
    pub_full = files["books/pub-full-book.json"]
    pub_meta = files["books/pub-meta-book.json"]

    # FULL_TEXT retains full text paragraphs
    hero_ent = next(e for e in pub_full["entities"] if e["entityId"] == "ent-pub-hero")
    assert hero_ent["content"][0]["paragraphs"] == ["Guerreiro sagrado imbuído de poder solar."]

    # METADATA_ONLY strips content paragraphs
    meta_ent = next(e for e in pub_meta["entities"] if e["entityId"] == "ent-pub-meta-item")
    assert meta_ent["content"] == [], "METADATA_ONLY must have empty content"
    # Search index for METADATA_ONLY still indexes name/aliases/tags
    search_entries = {e["entityId"]: e for e in files["search-index.json"]["entries"]}
    assert "ent-pub-meta-item" in search_entries
    assert "Texto detalhado do item que DEVE ser removido" not in search_entries["ent-pub-meta-item"]["searchText"]

    # Item 3: Absence of restricted content in all outputs (complete sentinel sweep)
    sentinels = [
        "secret-restricted-book",
        "Livro Restrito Desconhecido",
        "ent-sentinel-restricted-1",
        "Criatura Secreta Guardiã",
        "Guardião das Trevas",
        "Texto ultrassecreto que jamais deve ser publicado.",
        "Referência Secreta Não Vinculada",
        "rejected-book",
        "Livro Rejeitado Por Direitos",
        "ent-rejected-item",
        "Item Rejeitado",
        "TECH_HASH_DEADBEEF_999",
    ]
    for path_key, file_data in files.items():
        serialized = json.dumps(file_data, ensure_ascii=False)
        for s in sentinels:
            assert s not in serialized, f"CRITICAL LEAK: Sentinel '{s}' found in public file '{path_key}'"

    # Item 4: Absence of unresolved references and technical details
    for path_key, file_data in files.items():
        assert "unresolvedReferences" not in file_data, f"File '{path_key}' contains unresolvedReferences in public mode"
        if "entities" in file_data:
            for ent in file_data["entities"]:
                assert "technicalDetails" not in ent, f"Entity '{ent['entityId']}' contains technicalDetails in public mode"

    # Item 5: Absence of broken relations and excluded endpoints
    # The cross-book relation rel-cross-to-restricted points to ent-sentinel-restricted-1, which is excluded.
    # It must be omitted cleanly.
    assert len(pub_full["relations"]) == 1
    rel = pub_full["relations"][0]
    assert rel["relationId"] == "rel-pub-internal"
    assert rel["sourceEntityId"] == "ent-pub-hero"
    assert rel["targetEntityId"] == "ent-pub-power"
    assert rel["outgoingLabel"] == "Possui poder"
    assert rel["incomingLabel"] == "É possuído por"

    # All remaining relations in every public book have both endpoints visible in public entities
    all_public_entity_ids = set(search_entries.keys())
    for path_key, file_data in files.items():
        for r in file_data.get("relations", []):
            assert r["sourceEntityId"] in all_public_entity_ids
            assert r["targetEntityId"] in all_public_entity_ids