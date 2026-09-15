from __future__ import annotations

import json
from pathlib import Path
import pytest

from scripts.agents.canonical_json import canonical_json_bytes
from scripts.agents.frontend_projector import FrontendProjector
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
    server = PreviewServer(preview_root=preview_root, docs_root=docs_root, host="127.0.0.1", port=0)
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
