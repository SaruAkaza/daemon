import pytest
from scripts.agents.archive_inventory_loader import ArchiveInventoryLoader
from scripts.agents.frontend_projector import FrontendProjector
from scripts.agents.site_view_model import validate_projection


def test_frontend_projector_projects_dual_axis_metadata():
    loader = ArchiveInventoryLoader()
    books = loader.load_inventory()
    projector = FrontendProjector()

    files = projector.build(books, mode="restricted_preview")

    assert "catalog.json" in files
    catalog = files["catalog.json"]
    assert len(catalog["books"]) == 281

    # Check unworked entry (4killers)
    fk = next(b for b in catalog["books"] if b["bookId"] == "4killers")
    assert fk["pipelineStatus"] == "WAITING"
    assert fk["rightsStatus"] == "UNKNOWN"
    assert fk["publicationMode"] == "NOT_PUBLIC"
    assert fk["currentStage"] is None
    assert fk["entityCount"] == 0
    assert fk["pageCount"] == 8

    # Strict contract validation passes
    validate_projection(files)
