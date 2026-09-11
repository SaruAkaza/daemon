from __future__ import annotations

from copy import deepcopy
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