from __future__ import annotations

import json
from pathlib import Path
import pytest

from scripts.agents.canonical_json import canonical_json_bytes
from scripts.agents.frontend_projector import FrontendProjector
from scripts.agents.preview_projector import LocalPreviewProjector
from scripts.agents.preview_server import PreviewServer


@pytest.fixture(scope="session")
def site_preview_env(tmp_path_factory):
    runtime_root = tmp_path_factory.mktemp("daemon_site_runtime")
    preview_root = runtime_root / "preview"
    book_id = "synthetic"
    target_dir = preview_root / book_id
    target_dir.mkdir(parents=True)

    # 1. Generate synthetic ApprovedBook
    approved_book = {
        "bookId": book_id,
        "title": "Livro Sintético de Teste",
        "rightsStatus": "UNKNOWN",
        "publicationMode": "NOT_PUBLIC",
        "entities": [
            {
                "id": "a",
                "name": "Lobo",
                "category": "creature_npc",
                "displayType": "Criatura / NPC",
                "aliases": ["Canis"],
                "tags": ["selvagem", "fera"],
                "content": [
                    {
                        "title": "Descrição",
                        "paragraphs": ["Fera canina selvagem que habita florestas antigas."],
                    }
                ],
                "provenance": {"source": "synthetic", "pages": [10]},
                "technicalDetails": {"rawHash": "aabbcc112233"},
            },
            {
                "id": "b",
                "name": "Faro Aguçado",
                "category": "character_option",
                "subtype": "poder",
                "displayType": "Poder",
                "aliases": [],
                "tags": ["sentido"],
                "content": [
                    {
                        "title": "Efeito de Regra",
                        "paragraphs": ["Concede +20% em testes de Rastrear pelo olfato."],
                    }
                ],
                "provenance": {"source": "synthetic", "pages": [15]},
            },
            {
                "id": "c",
                "name": "Ataque em Bando",
                "category": "character_option",
                "subtype": "poder",
                "displayType": "Poder",
                "aliases": [],
                "tags": ["tática"],
                "content": [
                    {
                        "title": "Descrição",
                        "paragraphs": ["Bônus para ataques coordenados em grupo."],
                    }
                ],
                "provenance": {"source": "synthetic", "pages": [16]},
            },
            {
                "id": "d",
                "name": "Vulnerabilidade a Fogo",
                "category": "character_option",
                "subtype": "aprimoramento",
                "displayType": "Aprimoramento",
                "aliases": [],
                "tags": ["fraqueza"],
                "content": [
                    {
                        "title": "Descrição",
                        "paragraphs": ["Recebe o dobro de dano por fogo."],
                    }
                ],
                "provenance": {"source": "synthetic", "pages": [18]},
            },
        ],
        "relations": [
            {
                "relationId": "rel-01",
                "type": "HAS_POWER",
                "sourceEntityId": "a",
                "targetEntityId": "b",
            },
            {
                "relationId": "rel-02",
                "type": "CAN_CHOOSE_POWER",
                "sourceEntityId": "a",
                "targetEntityId": "c",
            },
            {
                "relationId": "rel-03",
                "type": "HAS_WEAKNESS",
                "sourceEntityId": "a",
                "targetEntityId": "d",
            },
        ],
        "groups": [
            {
                "id": "grupo-poderes",
                "label": "Poderes Caninos",
                "entityIds": ["b"],
            }
        ],
        "unresolvedReferences": [
            {
                "name": "Presença Invisível",
                "sourceEntityId": "a",
                "status": "PENDING_CLASSIFICATION",
            }
        ],
    }

    unworked_book = {
        "bookId": "synthetic-empty",
        "title": "Livro Sintético Vazio",
        "rightsStatus": "UNKNOWN",
        "publicationMode": "NOT_PUBLIC",
        "pipelineStatus": "WAITING",
        "currentStage": None,
        "entities": [],
        "relations": [],
        "groups": [],
    }

    # 2. Build Site View Model
    projector = FrontendProjector()
    site_files = projector.build([approved_book, unworked_book], "restricted_preview")
    site_data_dir = target_dir / "site-data"
    for rel_path, content in site_files.items():
        dest = site_data_dir / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(canonical_json_bytes(content))

    # 3. Write legacy index.json for backwards compatibility
    legacy_index = {
        "source": book_id,
        "bookId": book_id,
        "title": "Livro Sintético",
        "characters": [
            {
                "id": "lobo",
                "name": "Lobo",
                "sections": [{"id": "ficha", "title": "Ficha", "paragraphs": ["Fera canina."]}]
            }
        ],
        "entities": approved_book["entities"],
        "relations": approved_book["relations"],
    }
    (target_dir / "index.json").write_bytes(canonical_json_bytes(legacy_index))

    # 4. Start PreviewServer
    docs_root = Path("docs").resolve()
    server = PreviewServer(
        preview_root=preview_root,
        docs_root=docs_root,
        host="127.0.0.1",
        port=0,
        runtime_dir=runtime_root,
    )
    server.start()

    yield {
        "server": server,
        "port": server.port,
        "base_url": f"http://127.0.0.1:{server.port}",
        "site_url": f"http://127.0.0.1:{server.port}/?site=1&preview=synthetic",
    }

    server.stop()


@pytest.fixture
def site_url(site_preview_env):
    return site_preview_env["site_url"]


@pytest.fixture(scope="session")
def scroll_site_url(tmp_path_factory):
    runtime_root = tmp_path_factory.mktemp("scroll_site")
    preview_root = runtime_root / "preview"
    book_id = "scroll-synthetic"
    entities = [
        {
            "id": f"scroll-{index:03d}",
            "name": f"Entrada sintética {index:03d}",
            "category": "core_rule",
            "provenance": {"source": book_id, "pages": [1]},
            "content": [{
                "title": "Conteúdo sintético",
                "paragraphs": (
                    [f"Parágrafo sintético {number}: texto para conferir acesso ao conteúdo longo." for number in range(80)]
                    + ["Fim do conteúdo sintético"]
                    if index == 0 else ["Entrada sintética para teste de navegação."]
                ),
            }],
        }
        for index in range(96)
    ]
    files = FrontendProjector().build([{
        "bookId": book_id,
        "title": "Livro sintético longo",
        "rightsStatus": "UNKNOWN",
        "publicationMode": "NOT_PUBLIC",
        "entities": entities,
        "relations": [],
    }], "restricted_preview")
    site_data_dir = preview_root / book_id / "site-data"
    for relative_path, payload in files.items():
        destination = site_data_dir / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(canonical_json_bytes(payload))
    server = PreviewServer(
        preview_root=preview_root,
        docs_root=Path("docs").resolve(),
        host="127.0.0.1",
        port=0,
        runtime_dir=runtime_root,
    )
    server.start()
    try:
        yield f"http://127.0.0.1:{server.port}/?site=1&preview={book_id}"
    finally:
        server.stop()


@pytest.fixture(scope="session")
def archive_preview_env(tmp_path_factory, certified_archive_runtime):
    runtime_root = tmp_path_factory.mktemp("daemon_archive_runtime")
    preview_root = runtime_root / "preview"
    synthetic_runtime = certified_archive_runtime

    projector = LocalPreviewProjector()
    projector.project_archive_preview(
        workspace_root=Path("."),
        preview_root=preview_root,
        runtime_dir=synthetic_runtime,
    )

    docs_root = Path("docs").resolve()
    server = PreviewServer(preview_root=preview_root, docs_root=docs_root, host="127.0.0.1", port=0, runtime_dir=runtime_root)
    server.start()

    yield {
        "server": server,
        "port": server.port,
        "base_url": f"http://127.0.0.1:{server.port}",
        "site_url": f"http://127.0.0.1:{server.port}/?site=1",
    }

    server.stop()


@pytest.fixture
def archive_site_url(archive_preview_env):
    return archive_preview_env["site_url"]


@pytest.fixture(scope="session")
def public_preview_env(tmp_path_factory):
    runtime_root = tmp_path_factory.mktemp("daemon_public_runtime")
    preview_root = runtime_root / "preview"
    preview_root.mkdir(parents=True)
    public_root = runtime_root / "public"
    public_root.mkdir(parents=True)

    # Write minimal public site-data catalog so site boots
    site_data = public_root / "site-data"
    site_data.mkdir(parents=True)
    cat = {
        "schemaVersion": "1.0",
        "projectionId": "proj-pub-001",
        "generationTimestamp": "2026-09-14T00:00:00Z",
        "mode": "public",
        "books": [],
    }
    s_idx = {
        "schemaVersion": "1.0",
        "projectionId": "proj-pub-001",
        "generationTimestamp": "2026-09-14T00:00:00Z",
        "mode": "public",
        "entries": [],
    }
    (site_data / "catalog.json").write_bytes(canonical_json_bytes(cat))
    (site_data / "search-index.json").write_bytes(canonical_json_bytes(s_idx))

    docs_root = Path("docs").resolve()
    server = PreviewServer(
        preview_root=preview_root,
        docs_root=docs_root,
        host="127.0.0.1",
        port=0,
        public_root=public_root,
        mode="public",
        runtime_dir=runtime_root,
    )
    server.start()

    yield {
        "server": server,
        "port": server.port,
        "base_url": f"http://127.0.0.1:{server.port}",
        "site_url": f"http://127.0.0.1:{server.port}/?site=1&public=1",
    }

    server.stop()


@pytest.fixture
def public_site_url(public_preview_env):
    return public_preview_env["site_url"]

