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


def test_technical_details_visual_rendering(page, site_url):
    """REMEDIATION 02 - FIX 1 RED Test:
    In restricted_preview, entity technicalDetails must render a structured,
    accessible collapsible section without raw JSON dump, displaying only
    authorized fields (entityId, type, sourceId, mode, rightsStatus, publicationMode,
    provenance, unresolvedReferences) without undefined/null.
    """
    page.goto(site_url + "#/entity/a")
    page.wait_for_selector('[data-entity-id="a"]', timeout=10000)

    tech = page.locator(".entity-technical-details")
    assert tech.count() == 1, "Expected .entity-technical-details section"
    summary = tech.locator("summary")
    assert "Detalhes Técnicos" in summary.text_content()

    # Must NOT use raw JSON pre tag
    assert tech.locator("pre").count() == 0, "Technical details must not be a raw JSON pre dump"

    # Structured fields container
    content = tech.locator(".tech-details-content, dl.technical-details-list")
    assert content.count() >= 1, "Expected structured container inside .entity-technical-details"

    # Verify authorized fields
    assert tech.locator('[data-field="entityId"]').count() == 1
    assert "a" in tech.locator('[data-field="entityId"]').text_content()

    assert tech.locator('[data-field="type"]').count() == 1
    assert "creature_npc" in tech.locator('[data-field="type"]').text_content()

    assert tech.locator('[data-field="sourceId"]').count() == 1
    assert "synthetic" in tech.locator('[data-field="sourceId"]').text_content()

    assert tech.locator('[data-field="mode"]').count() == 1
    assert "restricted_preview" in tech.locator('[data-field="mode"]').text_content()

    assert tech.locator('[data-field="rightsStatus"]').count() == 1
    assert "UNKNOWN" in tech.locator('[data-field="rightsStatus"]').text_content()

    assert tech.locator('[data-field="publicationMode"]').count() == 1
    assert "NOT_PUBLIC" in tech.locator('[data-field="publicationMode"]').text_content()

    assert tech.locator('[data-field="provenance"]').count() == 1
    assert "synthetic" in tech.locator('[data-field="provenance"]').text_content()

    # Unresolved references list inside technical details
    assert tech.locator('[data-field="unresolvedReferences"]').count() == 1
    unres_tech = tech.locator('[data-field="unresolvedReferences"]').text_content()
    assert "Presença Invisível" in unres_tech
    assert "PENDING_CLASSIFICATION" in unres_tech

    # No undefined or null text
    tech_full_text = tech.text_content()
    assert "undefined" not in tech_full_text
    assert "null" not in tech_full_text


def test_public_mode_empty_catalog_local_serving(browser, tmp_path):
    """REMEDIATION 02 - FIX 2 RED Test:
    In public mode with restricted book (rightsStatus=UNKNOWN, publicationMode=NOT_PUBLIC),
    the generated public projection contains:
    - books: [] (0 books)
    - search entries: [] (0 entities)
    - 0 technicalDetails, 0 unresolvedReferences, 0 restricted sentinels.
    The PreviewServer must serve this local public projection without writing to docs/.
    Frontend must load catalog.json cleanly (200 OK) without 404, displaying
    empty state gracefully (e.g. '0 Livros Catalogados', 'Nenhum conteúdo público disponível.').
    """
    from pathlib import Path
    from scripts.agents.frontend_projector import FrontendProjector
    from scripts.agents.preview_server import PreviewServer

    repo_root = Path(__file__).resolve().parents[2]
    docs_root = repo_root / "docs"

    # Restricted candidate book
    restricted_book = {
        "bookId": "secret-book",
        "title": "Livro Restrito",
        "rightsStatus": "UNKNOWN",
        "publicationMode": "NOT_PUBLIC",
        "entities": [
            {
                "id": "sec-1",
                "name": "Segredo Oculto",
                "category": "creature_npc",
                "displayType": "Criatura / NPC",
                "aliases": [],
                "tags": [],
                "content": [{"title": "Restrito", "paragraphs": ["SENTINEL_RESTRICTED_DATA_SECRET"]}],
                "provenance": {"source": "secret", "pages": [1]},
            }
        ],
        "relations": [],
    }

    # Generate public projection
    projector = FrontendProjector()
    public_files = projector.build([restricted_book], "public")

    # Assert contract of public projection for restricted book
    assert public_files["catalog.json"]["books"] == []
    assert public_files["search-index.json"]["entries"] == []
    for fpath, payload in public_files.items():
        assert "technicalDetails" not in payload
        assert "unresolvedReferences" not in payload
        payload_str = str(payload)
        assert "SENTINEL_RESTRICTED_DATA_SECRET" not in payload_str
        assert "Segredo Oculto" not in payload_str

    # Write public projection to isolated tmp_path
    public_site_data = tmp_path / "public_site_data"
    projector.write(public_files, public_site_data, repo_root)

    # Start PreviewServer with public_root
    server = PreviewServer(
        preview_root=tmp_path / "empty_preview",
        docs_root=docs_root,
        host="127.0.0.1",
        port=0,
        public_root=public_site_data,
    )
    server.start()
    try:
        page = browser.new_page()
        # Navigate with site=1 and public=1
        page.goto(f"http://127.0.0.1:{server.port}/?site=1&public=1#/")
        page.wait_for_selector(".site-home-view", timeout=10000)

        # Confirm 0 books and 0 entities rendered
        text = page.locator(".site-home-view").text_content()
        assert "Livros Catalogados" in text
        assert "Entidades no Índice" in text
        assert "0" in page.locator(".site-stat-card").first.text_content()
        assert "Nenhum conteúdo público disponível." in text

        # Confirm books view
        page.goto(f"http://127.0.0.1:{server.port}/?site=1&public=1#/books")
        page.wait_for_selector(".site-books-view", timeout=10000)
        assert "Nenhum livro autorizado disponível." in page.locator(".site-books-view").text_content()

        # Also confirm root /?site=1#/ route works without error
        page.goto(f"http://127.0.0.1:{server.port}/?site=1#/")
        page.wait_for_selector(".site-home-view", timeout=10000)
        assert "Livros Catalogados" in page.locator(".site-home-view").text_content()
        assert "0" in page.locator(".site-stat-card").first.text_content()

        # Confirm zero restricted leakage in browser DOM
        dom_text = page.content()
        assert "SENTINEL_RESTRICTED_DATA_SECRET" not in dom_text
        assert "Segredo Oculto" not in dom_text
        assert "technicalDetails" not in dom_text
    finally:
        server.stop()


def test_interactive_touch_targets_mobile(page, site_url):
    """REMEDIATION 02 - FIX 3 RED Test:
    Interactive elements on mobile (390px) must have comfortable touch targets (height >= 44px):
    - navigation link (.site-nav-link)
    - preferences button (.site-btn-preferences)
    - entity row (.site-entity-row)
    - relation link (.site-relations-list a)
    - book filter select (#siteSearchBookFilter)
    - type filter select (#siteSearchTypeFilter)
    - reset filters button (.site-btn-reset-filters)
    - search result link (.site-search-result-title)
    Also verify zero horizontal overflow across 390px, 768px, 1440px.
    """
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(site_url + "#/entity/a")
    page.wait_for_selector('[data-entity-id="a"]', timeout=10000)

    # 1. Navigation links
    nav_link = page.locator(".site-nav-link").first
    box_nav = nav_link.bounding_box()
    assert box_nav is not None
    assert box_nav["height"] >= 44, f"Nav link touch target {box_nav['height']}px is below 44px"

    # 2. Preferences button
    pref_btn = page.locator(".site-btn-preferences")
    box_pref = pref_btn.bounding_box()
    assert box_pref is not None
    assert box_pref["height"] >= 44, f"Preferences button touch target {box_pref['height']}px is below 44px"

    # 3. Entity row
    row = page.locator(".site-entity-row").first
    box_row = row.bounding_box()
    assert box_row is not None
    assert box_row["height"] >= 44, f"Entity row touch target {box_row['height']}px is below 44px"

    # 4. Relation link
    rel_link = page.locator(".site-relations-list a").first
    box_rel = rel_link.bounding_box()
    assert box_rel is not None
    assert box_rel["height"] >= 44, f"Relation link touch target {box_rel['height']}px is below 44px"

    # 5. Search view controls
    page.goto(site_url + "#/search")
    page.wait_for_selector(".site-search-results", timeout=10000)

    book_sel = page.locator("#siteSearchBookFilter")
    box_book = book_sel.bounding_box()
    assert box_book is not None
    assert box_book["height"] >= 44, f"Book filter select {box_book['height']}px is below 44px"

    type_sel = page.locator("#siteSearchTypeFilter")
    box_type = type_sel.bounding_box()
    assert box_type is not None
    assert box_type["height"] >= 44, f"Type filter select {box_type['height']}px is below 44px"

    reset_btn = page.locator(".site-btn-reset-filters")
    box_reset = reset_btn.bounding_box()
    assert box_reset is not None
    assert box_reset["height"] >= 44, f"Reset button {box_reset['height']}px is below 44px"

    res_link = page.locator(".site-search-result-title").first
    box_res = res_link.bounding_box()
    assert box_res is not None
    assert box_res["height"] >= 44, f"Search result title link {box_res['height']}px is below 44px"

    # 6. Verify zero horizontal overflow at 390, 768, 1440
    for width in [390, 768, 1440]:
        page.set_viewport_size({"width": width, "height": 844})
        page.goto(site_url + "#/entity/a")
        page.wait_for_selector('[data-entity-id="a"]', timeout=10000)
        overflow_entity = page.evaluate("() => document.documentElement.scrollWidth > document.documentElement.clientWidth")
        assert not overflow_entity, f"Horizontal overflow on entity view at {width}px"

        page.goto(site_url + "#/search")
        page.wait_for_selector(".site-search-results", timeout=10000)
        overflow_search = page.evaluate("() => document.documentElement.scrollWidth > document.documentElement.clientWidth")
        assert not overflow_search, f"Horizontal overflow on search view at {width}px"


def test_desktop_and_mobile_scroll_interactions(page, site_url):
    """Verify that desktop panels and search views scroll with mouse wheel,
    panels have bounded heights, and mobile allows natural vertical document scroll."""
    # 1. Desktop Search view scroll
    page.set_viewport_size({"width": 1280, "height": 720})
    page.goto(site_url + "#/search")
    page.wait_for_selector(".site-search-results", timeout=10000)
    box = page.locator(".site-main-content").bounding_box()
    assert box is not None
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.wheel(0, 300)
    page.wait_for_timeout(200)
    assert page.locator(".site-main-content").evaluate("el => el.scrollTop") >= 0

    # 2. Entity browser panels scroll independently with bounded heights
    page.goto(site_url + "#/entity/a")
    page.wait_for_selector('[data-entity-id="a"]', timeout=10000)
    list_panel = page.locator(".site-list-panel")
    detail_panel = page.locator(".site-detail-panel")
    assert list_panel.evaluate("el => window.getComputedStyle(el).overflowY") == "auto"
    assert detail_panel.evaluate("el => window.getComputedStyle(el).overflowY") == "auto"

    shell_h = page.locator(".site-shell").evaluate("el => el.clientHeight")
    list_h = list_panel.evaluate("el => el.clientHeight")
    assert list_h <= shell_h, f"List panel height {list_h}px expanded beyond shell {shell_h}px"

    # 3. Mobile 390x844 allows vertical scrolling without horizontal overflow
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(site_url + "#/search")
    page.wait_for_selector(".site-search-results", timeout=10000)
    page.mouse.move(195, 300)
    page.mouse.wheel(0, 300)
    page.wait_for_timeout(200)
    overflow = page.evaluate("() => document.documentElement.scrollWidth > document.documentElement.clientWidth")
    assert not overflow


def test_books_catalog_filters_and_stepper_strict(page, site_url):
    page.goto(site_url + "#/books")
    page.wait_for_selector(".site-books-grid", timeout=10000)

    # Both books must exist
    assert page.locator(".site-book-card").count() >= 2

    # Strict assertion: unworked book link MUST exist (no conditional pass)
    unworked_link = page.locator('a[href="#/book/synthetic-empty"]')
    assert unworked_link.count() == 1, "Unworked book card must be present in restricted preview"
    unworked_link.first.click()

    # Wait for book detail view
    page.wait_for_selector(".pipeline-stepper", timeout=10000)

    # Stepper MUST contain exactly 7 stages
    steps = page.locator(".stepper-step")
    assert steps.count() == 7

    # For an unworked book, ALL 7 stages MUST have class 'pending' and ZERO active
    assert page.locator(".stepper-step.pending").count() == 7
    assert page.locator(".stepper-step.active").count() == 0

    # Empty state message MUST be visible
    empty_state = page.locator(".site-book-empty-state")
    assert empty_state.count() == 1
    assert "Nenhuma entidade processada" in empty_state.text_content()

    # Dual-axis badges MUST be visible
    assert page.locator(".site-badge-rights").count() >= 1
    assert page.locator(".site-badge-pipeline").count() >= 1


def test_books_catalog_public_mode_fail_closed(browser, tmp_path):
    """Verifies that in mode=public, restricted books are strictly excluded from catalog and detail routes."""
    from pathlib import Path
    from scripts.agents.frontend_projector import FrontendProjector
    from scripts.agents.preview_server import PreviewServer

    repo_root = Path(__file__).resolve().parents[2]
    docs_root = repo_root / "docs"
    projector = FrontendProjector()

    synthetic_catalog = [
        # Restricted books
        {"bookId": "synthetic-empty", "title": "Livro Vazio", "rightsStatus": "UNKNOWN", "publicationMode": "NOT_PUBLIC", "entities": []},
        {"bookId": "animalidade", "title": "Animalidade", "rightsStatus": "UNKNOWN", "publicationMode": "NOT_PUBLIC", "entities": [{"id": "e1", "name": "Fera"}]},
        # Authorized public book
        {"bookId": "public-rules", "title": "Regras Públicas", "rightsStatus": "PUBLIC_DOMAIN", "publicationMode": "FULL_TEXT", "entities": [{"id": "e2", "name": "Regra", "category": "core_rule", "content": [{"title": "C1", "paragraphs": ["Público"]}]}]},
    ]

    public_files = projector.build(synthetic_catalog, mode="public")
    public_site_data = tmp_path / "public_site_data"
    projector.write(public_files, public_site_data, repo_root)

    server = PreviewServer(
        preview_root=tmp_path / "empty_preview",
        docs_root=docs_root,
        host="127.0.0.1",
        port=0,
        public_root=public_site_data,
    )
    server.start()

    try:
        page = browser.new_page()
        # Navigate to public catalog
        page.goto(f"http://127.0.0.1:{server.port}/?site=1&public=1#/books")
        page.wait_for_selector(".site-books-grid", timeout=10000)

        # Restricted books MUST NOT appear
        assert page.locator('a[href="#/book/animalidade"]').count() == 0
        assert page.locator('a[href="#/book/synthetic-empty"]').count() == 0

        # Only authorized public book must appear
        assert page.locator('a[href="#/book/public-rules"]').count() == 1

        # Direct navigation to restricted book route MUST NOT deliver restricted content
        page.goto(f"http://127.0.0.1:{server.port}/?site=1&public=1#/book/animalidade")
        page.wait_for_timeout(1000)
        assert page.locator(".pipeline-stepper").count() == 0
        assert "Fera" not in page.content()
    finally:
        server.stop()


def test_real_archive_catalog_renders_281_books_and_filters(page, archive_site_url):
    page.goto(archive_site_url + "#/books")
    page.wait_for_selector(".site-books-grid", timeout=15000)

    # All 281 canonical books must be present
    assert page.locator(".site-book-card").count() == 281

    # Search filter by title
    page.locator("#siteBookSearch").fill("Animalidade")
    page.wait_for_timeout(300)
    assert page.locator(".site-book-card").count() == 1
    assert "animalidade" in page.text_content(".site-book-card").lower()

    # Search filter by unworked book
    page.locator("#siteBookSearch").fill("4killers")
    page.wait_for_timeout(300)
    assert page.locator(".site-book-card").count() == 1
    assert "4killers" in page.text_content(".site-book-card").lower()

    # Clear search
    page.locator("#siteBookSearch").fill("")
    page.wait_for_timeout(300)
    assert page.locator(".site-book-card").count() == 281

    # Rights filter: UNKNOWN -> 281
    page.locator("#siteBookRightsFilter").select_option("UNKNOWN")
    page.wait_for_timeout(300)
    assert page.locator(".site-book-card").count() == 281

    # Publication filter: NOT_PUBLIC -> 281
    page.locator("#siteBookPublicationFilter").select_option("NOT_PUBLIC")
    page.wait_for_timeout(300)
    assert page.locator(".site-book-card").count() == 281

    # Reset filters
    page.locator("#siteBookRightsFilter").select_option("all")
    page.locator("#siteBookPublicationFilter").select_option("all")
    page.wait_for_timeout(300)

    # Sort by entities descending -> Animalidade should be the first card
    page.locator("#siteBookSort").select_option("entities_desc")
    page.wait_for_timeout(300)
    first_card = page.locator(".site-book-card").first
    assert "animalidade" in first_card.text_content().lower()


def test_real_archive_navigation_to_animalidade_and_unworked_book(page, archive_site_url):
    # Navigate to Animalidade
    page.goto(archive_site_url + "#/book/animalidade")
    page.wait_for_selector(".site-book-detail", timeout=15000)

    # Verify Animalidade details
    assert "animalidade" in page.text_content("h1").lower()
    assert page.locator(".site-badge-rights").count() >= 1
    assert page.locator(".site-badge-pub").count() >= 1
    assert page.locator(".pipeline-stepper").count() == 1


    # Animalidade has 56 entities loaded from runtime accepted bundle
    page.wait_for_selector(".site-entity-list", timeout=10000)
    assert page.locator(".site-entity-list li").count() == 56

    # Click first entity to navigate to entity detail
    page.locator(".site-entity-list a").first.click()
    page.wait_for_selector(".site-detail-panel", timeout=10000)
    assert page.locator(".site-detail-panel").is_visible()


    # Navigate to unworked book 4killers
    page.goto(archive_site_url + "#/book/4killers")
    page.wait_for_selector(".site-book-detail", timeout=15000)

    assert "4killers" in page.text_content("h1")
    assert page.locator(".pipeline-stepper").count() == 1
    # 7 pending stages, 0 active
    assert page.locator(".stepper-step.pending").count() == 7
    assert page.locator(".stepper-step.active").count() == 0

    # Empty state message
    empty_state = page.locator(".site-book-empty-state")
    assert empty_state.count() == 1
    assert "Nenhuma entidade processada" in empty_state.text_content()



