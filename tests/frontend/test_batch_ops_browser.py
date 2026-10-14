from pathlib import Path

from playwright.sync_api import expect

from scripts.agents.preview_server import PreviewServer
from scripts.orchestrator.batch_orchestrator import BatchOrchestrator
from scripts.orchestrator.demo import build_executors, create_sources
from tests.orchestrator.helpers import command, pump


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
            (site_data / "catalog.json").write_text('{"schemaVersion":"1.0","mode":"restricted_preview","books":[]}')
            (site_data / "search-index.json").write_text('{"schemaVersion":"1.0","mode":"restricted_preview","entries":[]}')
            page.goto(f"http://127.0.0.1:{server.port}/?site=1#/ops/queue")
            expect(page.get_by_role("heading", name="Painel de Controle Operacional — Release C")).to_be_visible()
            expect(page.get_by_text("Demonstração A", exact=True)).to_be_visible()
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
