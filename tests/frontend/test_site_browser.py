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


def test_unresolved_references_human_label(page, site_url):
    """FIX 3 RED Test: Verify that main UI displays 'Referência não vinculada'
    along with name, does NOT show raw technical status strings in the primary item,
    has no anchor link, and technical status is only in technical details.
    """
    page.goto(site_url + "#/entity/a")
    page.wait_for_selector('[data-entity-id="a"]', timeout=10000)

    unresolved_item = page.locator(".site-unresolved-list li")
    assert unresolved_item.count() >= 1

    item_text = unresolved_item.first.text_content()
    # 1. Main text must show "Referência não vinculada" and the reference name
    assert "Referência não vinculada" in item_text
    assert "Presença Invisível" in item_text

    # 2. Main text MUST NOT display raw technical status
    assert "PENDING_CLASSIFICATION" not in item_text
    assert "UNRESOLVED_PENDING_CROSS_BOOK_LINK" not in item_text

    # 3. Must not have anchor tag
    assert unresolved_item.locator("a").count() == 0

    # 4. Technical status should appear inside collapsible technical details
    tech_details = page.locator(".entity-technical-details")
    assert tech_details.count() >= 1
    assert "PENDING_CLASSIFICATION" in tech_details.text_content()


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


def test_search_filters_book_and_type(page, site_url):
    """FIX 1 RED Test: Verify Book and Type filters exist on #/search,
    reduce results correctly, combine with query, reset properly,
    and preserve state on layout switch.
    """
    page.goto(site_url + "#/search")
    page.wait_for_selector(".site-search-results", timeout=10000)

    # 1. Verify filter controls exist on search view
    book_filter = page.locator("#siteSearchBookFilter")
    type_filter = page.locator("#siteSearchTypeFilter")
    reset_btn = page.locator("#siteSearchResetFilters")

    assert book_filter.count() == 1
    assert type_filter.count() == 1
    assert reset_btn.count() == 1

    # Verify initial results count is 4 (a, b, c, d)
    initial_cards = page.locator(".site-search-result-card")
    assert initial_cards.count() == 4

    # 2. Filter by Type: "Poder" (should reduce to 2: Faro Aguçado and Ataque em Bando)
    type_filter.select_option(label="Poder")
    page.wait_for_timeout(300)
    assert page.locator(".site-search-result-card").count() == 2
    card_texts = page.locator(".site-search-result-card").all_text_contents()
    assert any("Faro Aguçado" in t for t in card_texts)
    assert any("Ataque em Bando" in t for t in card_texts)
    assert not any("Lobo" in t for t in card_texts)

    # 3. Combine with Query: search for "Ataque" -> should reduce to 1 (Ataque em Bando)
    page.get_by_label("Busca global", exact=True).fill("Ataque")
    page.wait_for_timeout(300)
    assert page.locator(".site-search-result-card").count() == 1
    assert "Ataque em Bando" in page.text_content(".site-search-result-card")

    # 4. Filter by Book as well: "Livro Sintético de Teste" -> still 1
    book_filter.select_option(label="Livro Sintético de Teste")
    page.wait_for_timeout(300)
    assert page.locator(".site-search-result-card").count() == 1

    # 5. Reset filters: clicking reset button restores all results
    reset_btn.click()
    page.wait_for_timeout(300)
    assert page.locator(".site-search-result-card").count() == 4

    # 6. Preserved on layout change
    type_filter.select_option(label="Poder")
    page.wait_for_timeout(300)
    assert page.locator(".site-search-result-card").count() == 2

    # Switch layout to classic
    page.get_by_role("button", name="Preferências", exact=True).click()
    page.get_by_label("Layout", exact=True).select_option("classic")
    page.wait_for_timeout(300)

    # Results and filter state should still be preserved
    assert page.locator(".site-search-result-card").count() == 2
    assert type_filter.input_value() != ""


def test_mobile_spacing_and_no_overflow(page, site_url):
    """FIX 4 RED Test: In mobile viewport (390px and 768px), especially in Advanced layout:
    - Entity rows must have comfortable touch targets (height >= 44px)
    - Item separation/gap between entity rows >= 8px
    - Search result cards have comfortable padding
    - Zero horizontal overflow across 390px, 768px, and 1440px
    """
    viewports = [
        {"width": 390, "height": 844, "is_mobile": True},
        {"width": 768, "height": 1024, "is_mobile": True},
        {"width": 1440, "height": 900, "is_mobile": False},
    ]

    for vp in viewports:
        page.set_viewport_size({"width": vp["width"], "height": vp["height"]})
        page.goto(site_url + "#/entities")
        page.wait_for_selector(".site-entity-items", timeout=10000)

        # Set layout to advanced if not already advanced
        current_layout = page.locator(".site-shell").get_attribute("data-layout")
        if current_layout != "advanced":
            page.get_by_role("button", name="Preferências", exact=True).click()
            page.get_by_label("Layout", exact=True).select_option("advanced")
            page.get_by_role("button", name="Fechar", exact=True).click()
            page.wait_for_timeout(300)

        # 1. Verify touch target height and spacing on mobile
        if vp["is_mobile"]:
            first_row = page.locator(".site-entity-row").first
            box = first_row.bounding_box()
            assert box is not None
            assert box["height"] >= 44, f"Entity row height {box['height']}px is below 44px touch target at {vp['width']}px"

            items_gap = page.evaluate(
                "() => parseFloat(window.getComputedStyle(document.querySelector('.site-entity-items')).gap)"
            )
            assert items_gap >= 8, f"Entity items gap {items_gap}px is below 8px at {vp['width']}px"

        # 2. Verify zero horizontal overflow on entities view
        is_overflowing = page.evaluate(
            "() => document.documentElement.scrollWidth > document.documentElement.clientWidth"
        )
        assert not is_overflowing, f"Horizontal overflow detected on #/entities at {vp['width']}px"

        # 3. Verify zero horizontal overflow on search view
        page.goto(site_url + "#/search")
        page.wait_for_selector(".site-search-results", timeout=10000)
        is_search_overflowing = page.evaluate(
            "() => document.documentElement.scrollWidth > document.documentElement.clientWidth"
        )
        assert not is_search_overflowing, f"Horizontal overflow detected on #/search at {vp['width']}px"


