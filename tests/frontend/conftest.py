from __future__ import annotations

import json
from pathlib import Path
import pytest

from scripts.agents.canonical_json import canonical_json_bytes, compute_result_manifest_hash
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


def _setup_synthetic_archive_runtime(runtime_dir: Path) -> Path:
    jobs_dir = runtime_dir / "jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    job_data = {
        "schemaVersion": "1.0",
        "jobId": "JOB-ANIM-001",
        "kind": "book_ingestion",
        "bookId": "animalidade",
        "status": "in_progress",
        "createdAt": "2026-09-09T17:12:08.418844+00:00",
        "updatedAt": "2026-09-09T18:56:11.482194+00:00",
        "requestedBy": "human",
        "currentStage": "relations",
        "stages": {
            "source": "pass",
            "extraction": "pass",
            "editorial": "pass",
            "entities": "pass",
            "relations": "ready",
            "frontend": "waiting",
            "qa": "waiting",
            "release": "waiting",
        },
        "humanReviewRequired": False,
        "blockingReasons": [],
        "artifacts": [],
        "history": [],
    }
    (jobs_dir / "JOB-ANIM-001.json").write_text(json.dumps(job_data), encoding="utf-8")

    dec_dir = runtime_dir / "audit" / "pilot" / "animalidade" / "decisions"
    dec_dir.mkdir(parents=True, exist_ok=True)
    req_dir = runtime_dir / "audit" / "pilot" / "animalidade" / "requests"
    req_dir.mkdir(parents=True, exist_ok=True)

    ent_manifest = {
        "bookId": "animalidade",
        "resultBundleId": "RB-ANIM-ENTITIES-att1-50691836",
        "attemptNumber": 1,
    }
    ent_manifest_hash = compute_result_manifest_hash(ent_manifest)
    ent_manifest["resultManifestSha256"] = ent_manifest_hash

    rel_manifest = {
        "bookId": "animalidade",
        "resultBundleId": "RB-ANIM-RELATIONS-att2-3c451b57",
        "attemptNumber": 2,
        "inputEntitiesBundle": "RB-ANIM-ENTITIES-att1-50691836",
    }
    rel_manifest_hash = compute_result_manifest_hash(rel_manifest)
    rel_manifest["resultManifestSha256"] = rel_manifest_hash

    dec_data = {
        "decisionId": "DEC-ANIM-001-ENTITIES-01",
        "decision": "APPROVE",
        "reviewer": "human-evaluator",
        "resultBundleId": "RB-ANIM-ENTITIES-att1-50691836",
        "reviewedResultManifestSha256": ent_manifest_hash,
    }
    (dec_dir / "DEC-ANIM-001-ENTITIES-01.json").write_text(json.dumps(dec_data), encoding="utf-8")

    req_data = {
        "reviewRequestId": "REV-ANIM-001-RELATIONS-02",
        "stage": "relations",
        "attemptNumber": 2,
        "resultBundleId": "RB-ANIM-RELATIONS-att2-3c451b57",
        "inputEntitiesBundle": "RB-ANIM-ENTITIES-att1-50691836",
        "reviewedResultManifestSha256": rel_manifest_hash,
        "status": "NEEDS_HUMAN_REVIEW",
    }
    (req_dir / "REV-ANIM-001-RELATIONS-02.json").write_text(json.dumps(req_data), encoding="utf-8")

    ent_bundle = runtime_dir / "bundles" / "accepted" / "RB-ANIM-ENTITIES-att1-50691836"
    ent_art = ent_bundle / "artifacts"
    ent_art.mkdir(parents=True, exist_ok=True)
    entities = [
        {
            "id": f"ent-anim-{i}",
            "name": f"Poder Animal {i}",
            "category": "character_option",
            "subtype": "poder",
            "displayType": "Poder",
            "provenance": {"source": "animalidade", "pages": [1]},
        }
        for i in range(56)
    ]
    (ent_art / "entities.json").write_text(json.dumps(entities), encoding="utf-8")
    (ent_bundle / "result-manifest.json").write_bytes(canonical_json_bytes(ent_manifest))

    rel_bundle = runtime_dir / "bundles" / "accepted" / "RB-ANIM-RELATIONS-att2-3c451b57"
    rel_art = rel_bundle / "artifacts"
    rel_art.mkdir(parents=True, exist_ok=True)
    relations = [
        {
            "relationId": f"rel-anim-{i}",
            "type": "CAN_CHOOSE_POWER" if i < 108 else "HAS_WEAKNESS",
            "sourceEntityId": "ent-anim-0",
            "targetEntityId": f"ent-anim-{(i % 55) + 1}",
            "source": "animalidade",
        }
        for i in range(164)
    ]
    (rel_art / "relations.json").write_text(json.dumps(relations), encoding="utf-8")
    (rel_bundle / "result-manifest.json").write_bytes(canonical_json_bytes(rel_manifest))

    return runtime_dir


@pytest.fixture(scope="session")
def archive_preview_env(tmp_path_factory):
    runtime_root = tmp_path_factory.mktemp("daemon_archive_runtime")
    preview_root = runtime_root / "preview"
    synthetic_runtime = _setup_synthetic_archive_runtime(runtime_root / "runtime")

    projector = LocalPreviewProjector()
    projector.project_archive_preview(
        workspace_root=Path("."),
        preview_root=preview_root,
        runtime_dir=synthetic_runtime,
    )

    docs_root = Path("docs").resolve()
    server = PreviewServer(preview_root=preview_root, docs_root=docs_root, host="127.0.0.1", port=0)
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

