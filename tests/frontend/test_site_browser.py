from __future__ import annotations

import pytest


def test_layout_preserves_entity_and_search(page, site_url):
    page.goto(site_url + "#/entity/a")
    page.wait_for_selector('[data-entity-id="a"]', timeout=10000)

    # Perform search
    page.get_by_label("Busca global", exact=True).fill("Lobo")

    # Open Preferences modal/panel
    page.get_by_role("button", name="Preferências", exact=True).click()

    # Change layout to classic
    page.get_by_label("Layout", exact=True).select_option("classic")

    # Assert navigation and search are preserved
    assert page.url.endswith("#/entity/a")
    assert page.get_by_label("Busca global", exact=True).input_value() == "Lobo"
    assert page.locator('[data-entity-id="a"]').count() >= 1

    # Reload page to test persistence of layout
    page.reload()
    page.wait_for_selector('[data-layout="classic"]', timeout=10000)
    assert page.locator('[data-layout="classic"]').count() == 1


def test_site_navigation_and_relations(page, site_url):
    page.goto(site_url + "#/entity/a")
    page.wait_for_selector('[data-entity-id="a"]', timeout=10000)

    # Verify entity name and display type
    assert "Lobo" in page.text_content("h1")
    assert "Criatura / NPC" in page.text_content(".entity-display-type")

    # Verify relation to Faro Aguçado
    relation_link = page.locator('a[href="#/entity/b"]')
    assert relation_link.count() >= 1

    # Click relation link to navigate to Faro Aguçado
    relation_link.first.click()
    page.wait_for_selector('[data-entity-id="b"]', timeout=10000)
    assert page.url.endswith("#/entity/b")
    assert "Faro Aguçado" in page.text_content("h1")

    # Verify unresolved reference is visible in preview mode
    page.goto(site_url + "#/entity/a")
    page.wait_for_selector('[data-entity-id="a"]', timeout=10000)
    assert "Presença Invisível" in page.text_content("body")


def test_routes_navigation(page, site_url):
    # Books route
    page.goto(site_url + "#/books")
    page.wait_for_selector(".site-books-grid", timeout=10000)
    assert "Livro Sintético de Teste" in page.text_content("body")

    # Entities route
    page.goto(site_url + "#/entities")
    page.wait_for_selector(".site-entity-items", timeout=10000)
    assert page.locator(".site-entity-row").count() >= 2

    # Search route
    page.goto(site_url + "#/search")
    page.wait_for_selector(".site-search-results", timeout=10000)
    assert "Busca de Entidades" in page.text_content("h1")

    # Not found route
    page.goto(site_url + "#/invalid/route")
    page.wait_for_selector(".site-not-found", timeout=10000)
    assert "Página Não Encontrada" in page.text_content("h1")


def test_unresolved_references_have_no_anchor_links(page, site_url):
    page.goto(site_url + "#/entity/a")
    page.wait_for_selector('[data-entity-id="a"]', timeout=10000)

    # Check unresolved references list
    unresolved_item = page.locator(".site-unresolved-list li")
    assert unresolved_item.count() >= 1
    # Confirm it does NOT contain an anchor link
    assert unresolved_item.locator("a").count() == 0


def test_responsive_viewports(page, site_url):
    viewports = [
        {"width": 390, "height": 844},   # Mobile
        {"width": 768, "height": 1024},  # Tablet
        {"width": 1440, "height": 900},  # Desktop
    ]

    for vp in viewports:
        page.set_viewport_size(vp)
        page.goto(site_url + "#/entity/a")
        page.wait_for_selector('[data-entity-id="a"]', timeout=10000)
        assert page.locator('[data-entity-id="a"]').is_visible()

