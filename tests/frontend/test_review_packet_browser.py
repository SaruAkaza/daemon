from __future__ import annotations

import json

from playwright.sync_api import expect

from scripts.orchestrator.review_packet import build_review_packet, write_packet
from tests.orchestrator.test_review_packet import review_fixture


def test_offline_review_search_pagination_images_and_notes_roundtrip(page, tmp_path):
    source, manifest, evidence, sha = review_fixture(tmp_path, many=True)
    path = write_packet(tmp_path / "review.html", build_review_packet(source, manifest, evidence, evidence_sha256=sha))
    errors, external = [], []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("request", lambda request: external.append(request.url) if request.url.startswith(("http:", "https:")) else None)
    page.goto(path.as_uri())
    expect(page.get_by_role("heading", level=1)).to_have_text(manifest["title"])
    assert page.evaluate("window.pwned") is None
    expect(page.locator(".card")).to_have_count(40)
    page.get_by_role("button", name="Próximos", exact=True).click()
    expect(page.get_by_role("heading", name="Bloco 41", exact=True)).to_be_visible()
    page.get_by_label("Buscar texto ou localizador").fill("Dano 1d6")
    expect(page.locator(".card")).to_have_count(1)
    expect(page.locator(".source-text")).to_contain_text("custo lO; ﬁm.")
    page.get_by_label("Seu nome", exact=True).fill("Revisora sintética")
    page.get_by_label("Documento / edição de referência").fill("PDF de teste")
    page.get_by_label("Numeração usada").select_option("PRINTED_LABEL")
    page.get_by_label("Total de páginas na referência (opcional)").fill("90")
    page.get_by_label("Página ou intervalo na referência").fill("xii–13")
    page.get_by_label("Observação / correção proposta").fill("Conferir a ligatura.")
    page.get_by_label("Conferi este trecho com a referência").check()
    expect(page.locator("#progress")).to_contain_text("1 blocos com página anotada")
    page.get_by_role("button", name="Imagens", exact=True).click()
    expect(page.locator(".card img")).to_have_count(1)
    assert page.locator(".card img").evaluate("image => image.complete && image.naturalWidth > 0")
    expect(page.get_by_role("button", name="Ir ao bloco 4", exact=True)).to_be_visible()
    page.get_by_label("Conferi esta imagem no original").check()
    with page.expect_download() as received:
        page.get_by_role("button", name="Exportar anotações").click()
    draft_path = tmp_path / "draft.json"
    received.value.save_as(draft_path)
    draft = json.loads(draft_path.read_bytes())
    assert draft["status"] == "DRAFT_UNVERIFIED" and draft["evidenceSha256"] == sha
    assert draft["referencePageCount"] == 90 and draft["pageBasis"] == "PRINTED_LABEL"
    assert draft["blockNotes"][0]["pageLabel"] == "xii–13" and draft["mediaNotes"][0]["checked"]
    page.reload()
    page.get_by_label("Importar anotações").set_input_files(draft_path)
    expect(page.locator("#save-status")).to_have_text("Anotações importadas como rascunho.")
    page.get_by_label("Buscar texto ou localizador").fill("Dano 1d6")
    expect(page.get_by_label("Página ou intervalo na referência")).to_have_value("xii–13")
    expect(page.get_by_label("Conferi este trecho com a referência")).to_be_checked()
    expect(page.locator("#progress")).to_contain_text("1/1 imagens conferidas")
    assert errors == [] and external == []
    assert source.read_bytes() and json.loads(evidence.read_bytes())["metadata"]["extraction"]["pageCount"] is None


def test_import_rejects_wrong_source_or_forged_anchor_without_losing_current_notes(page, tmp_path):
    source, manifest, evidence, sha = review_fixture(tmp_path)
    path = write_packet(tmp_path / "review.html", build_review_packet(source, manifest, evidence, evidence_sha256=sha))
    page.goto(path.as_uri())
    page.get_by_label("Buscar texto ou localizador").fill("Dano 1d6")
    page.get_by_label("Página ou intervalo na referência").fill("12")
    with page.expect_download() as received:
        page.get_by_role("button", name="Exportar anotações").click()
    draft_path = tmp_path / "draft.json"
    received.value.save_as(draft_path)
    draft = json.loads(draft_path.read_bytes())
    for key, bad in [("sourceSha256", "0" * 64), ("evidenceSha256", "f" * 64), ("blockNotes", [{**draft["blockNotes"][0], "anchor": "invented"}]), ("blockNotes", draft["blockNotes"] * 2)]:
        candidate = {**draft, key: bad}
        draft_path.write_text(json.dumps(candidate), encoding="utf-8")
        page.get_by_label("Importar anotações").set_input_files(draft_path)
        expect(page.get_by_role("alert")).to_contain_text("Anotações inválidas")
        expect(page.get_by_label("Página ou intervalo na referência")).to_have_value("12")
    # A total count never assigns a page to another block.
    page.get_by_label("Total de páginas na referência (opcional)").fill("90")
    page.get_by_label("Buscar texto ou localizador").fill("window.pwned")
    expect(page.get_by_label("Página ou intervalo na referência")).to_have_value("")
    assert page.evaluate("window.pwned") is None
    page.on("dialog", lambda dialog: dialog.accept())
