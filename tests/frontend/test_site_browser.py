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


def test_three_synthetic_predicates_and_bidirectional_routes(page, site_url):
    """Verify in real browser with real HTTP transport:
    - 3 synthetic predicates: HAS_POWER, CAN_CHOOSE_POWER, HAS_WEAKNESS.
    - Outgoing and incoming labels derived from central projector registry.
    - Bi-directional navigation across entities preserving routes.
    - Unresolved reference has no anchor tag.
    - Technical details section exists in restricted preview.
    """
    page.goto(site_url + "#/entity/a")
    page.wait_for_selector('[data-entity-id="a"]', timeout=10000)

    # 1. Outgoing relations on entity a (Lobo):
    # HAS_POWER -> Faro Aguçado
    link_b = page.locator('.site-relations-list a[href="#/entity/b"]')
    assert link_b.count() >= 1
    assert "Faro Aguçado" in link_b.first.text_content()
    assert "Possui poder" in page.text_content(".site-relations-list")

    # CAN_CHOOSE_POWER -> Ataque em Bando
    link_c = page.locator('.site-relations-list a[href="#/entity/c"]')
    assert link_c.count() >= 1
    assert "Ataque em Bando" in link_c.first.text_content()
    assert "Pode escolher poder" in page.text_content(".site-relations-list")

    # HAS_WEAKNESS -> Vulnerabilidade a Fogo
    link_d = page.locator('.site-relations-list a[href="#/entity/d"]')
    assert link_d.count() >= 1
    assert "Vulnerabilidade a Fogo" in link_d.first.text_content()
    assert "Possui fraqueza" in page.text_content(".site-relations-list")

    # 2. Navigate to CAN_CHOOSE_POWER target (Ataque em Bando)
    link_c.first.click()
    page.wait_for_selector('[data-entity-id="c"]', timeout=10000)
    assert page.url.endswith("#/entity/c")
    assert "Ataque em Bando" in page.text_content("h1")

    # Verify incoming relation: "Pode ser escolhido por" -> Lobo
    inc_c = page.locator('.site-relations-list a[href="#/entity/a"]')
    assert inc_c.count() >= 1
    assert "Lobo" in inc_c.first.text_content()
    assert "Pode ser escolhido por" in page.text_content(".site-relations-list")

    # Navigate back to Lobo via incoming relation
    inc_c.first.click()
    page.wait_for_selector('[data-entity-id="a"]', timeout=10000)
    assert page.url.endswith("#/entity/a")

    # 3. Navigate to HAS_WEAKNESS target (Vulnerabilidade a Fogo)
    link_d_again = page.locator('.site-relations-list a[href="#/entity/d"]')
    link_d_again.first.click()
    page.wait_for_selector('[data-entity-id="d"]', timeout=10000)
    assert page.url.endswith("#/entity/d")
    assert "Vulnerabilidade a Fogo" in page.text_content("h1")

    # Verify incoming relation: "É fraqueza de" -> Lobo
    inc_d = page.locator('.site-relations-list a[href="#/entity/a"]')
    assert inc_d.count() >= 1
    assert "Lobo" in inc_d.first.text_content()
    assert "É fraqueza de" in page.text_content(".site-relations-list")

    # 4. Return to entity a and check unresolved reference and technical details
    inc_d.first.click()
    page.wait_for_selector('[data-entity-id="a"]', timeout=10000)
    assert page.locator(".site-unresolved-list").count() >= 1
    assert "Presença Invisível" in page.text_content(".site-unresolved-list")
    assert page.locator(".site-unresolved-list a").count() == 0

    # Technical details in restricted preview
    tech_details = page.locator(".entity-technical-details")
    assert tech_details.count() >= 1
    assert "Detalhes Técnicos" in page.text_content(".entity-technical-details")


