from pathlib import Path

from playwright.sync_api import expect

from scripts.agents.preview_server import PreviewServer
from scripts.agents.frontend_projector import FrontendProjector
from scripts.agents.canonical_json import canonical_json_bytes
from scripts.orchestrator.batch_orchestrator import BatchOrchestrator
from scripts.orchestrator.demo import build_executors, create_sources
from tests.orchestrator.helpers import command, pump
from scripts.orchestrator.real_adapters import build_executors as build_real_executors
from docx import Document
import hashlib
import json


def test_batch_panel_controls_live_engine_and_hash_bound_approval(page, tmp_path):
    runtime = tmp_path / "runtime"
    with BatchOrchestrator(runtime, source_root=runtime, executors=build_executors()) as engine:
        for registration in create_sources(runtime)[:1]:
            engine.register(registration["bookId"], registration["manifest"])
        command(engine, "demo-a", "PAUSE_BOOK")
        server = PreviewServer(runtime / "preview", docs_root=Path("docs"), port=0,
                               runtime_dir=runtime, orchestrator=engine)
        server.start()
        try:
            # Seed only site navigation metadata; the operational queue comes from the engine.
            site_data = runtime / "preview/site-data"
            site_data.mkdir(parents=True)
            for filename, payload in FrontendProjector().build([], "restricted_preview").items():
                (site_data / filename).write_bytes(canonical_json_bytes(payload))
            page.goto(f"http://127.0.0.1:{server.port}/?site=1#/ops/queue")
            expect(page.get_by_role("heading", name="Painel de Controle Operacional — Release C")).to_be_visible()
            expect(page.get_by_text("Demonstração A", exact=True)).to_be_visible()
            expect(page.get_by_text("Erro ao carregar dados do site", exact=False)).to_have_count(0)
            page.get_by_role("button", name="Identificar Operador", exact=True).click()
            page.get_by_label("Identificador do Operador", exact=False).fill("human-browser-tester")
            page.get_by_role("button", name="Confirmar Identidade", exact=False).click()
            page.get_by_role("button", name="Retomar", exact=True).click()
            page.get_by_role("button", name="Confirmar Ação", exact=True).click()
            engine.start()
            expect(page.get_by_text("READY_FOR_HUMAN_APPROVAL", exact=False)).to_be_visible(timeout=15000)
            book = engine.state["books"]["demo-a"]
            page.goto(f"http://127.0.0.1:{server.port}/?site=1#/ops/review/{book['reviewId']}")
            page.get_by_role("button", name="Aprovar Revisão", exact=True).click()
            page.get_by_role("button", name="Confirmar Ação", exact=True).click()
            expect(page.get_by_text("APPROVE", exact=False)).to_be_visible(timeout=10000)
            expect(page.locator('.site-ops-review-detail-view')).to_have_count(1)
            pump(engine, lambda: book["status"] == "APPROVED_PRIVATE")
            assert engine.reviews.decision_logger.read_all_entries()[0]["snapshotSha256"]
            assert engine.jobs.load(book["jobId"])["stages"]["release"] == "waiting"
        finally:
            server.stop()


def test_private_extraction_evidence_download_uses_session_cookie(page, tmp_path):
    source = tmp_path / "source.docx"
    document = Document()
    document.add_paragraph("Documento sintético privado para revisão; Dano 1d6.")
    document.save(source)
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    manifest = {"schemaVersion": "1.0", "sourceId": "fixture-physical", "title": "Teste de extração",
                "path": source.name, "extension": ".docx", "sha256": source_hash,
                "rightsStatus": "UNKNOWN", "visibility": "private", "publicationMode": "NOT_PUBLIC"}
    runtime = tmp_path / "runtime"
    with BatchOrchestrator(runtime, source_root=tmp_path, executors=build_real_executors()) as engine:
        engine.register("fixture-physical", manifest)
        book = engine.state["books"]["fixture-physical"]
        pump(engine, lambda: book["status"] == "NEEDS_HUMAN_REVIEW")
        site_data = runtime / "preview/site-data"
        site_data.mkdir(parents=True)
        for filename, payload in FrontendProjector().build([], "restricted_preview").items():
            (site_data / filename).write_bytes(canonical_json_bytes(payload))
        server = PreviewServer(runtime / "preview", docs_root=Path("docs"), port=0,
                               runtime_dir=runtime, orchestrator=engine)
        server.start()
        try:
            page.goto(f"http://127.0.0.1:{server.port}/?site=1#/ops/review/{book['reviewId']}")
            download_link = page.get_by_role("link", name="Baixar evidência privada: execution-result.json", exact=True)
            expect(download_link).to_be_visible()
            with page.expect_download() as received:
                download_link.click()
            target = tmp_path / "private-review.json"
            received.value.save_as(target)
            evidence = json.loads(target.read_bytes())
            assert evidence["metadata"]["extraction"]["pageCount"] is None
            assert evidence["metadata"]["extraction"]["blocks"][0]["cleanText"].endswith("Dano 1d6.")
            assert evidence["status"] == "VALIDATION_FAILED"
            assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
            assert engine.checkpoints.load("fixture-physical", "extraction") is None
        finally:
            server.stop()
