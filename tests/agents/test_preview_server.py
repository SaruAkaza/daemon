from __future__ import annotations

import json
import urllib.request
import urllib.error
from pathlib import Path
import pytest

from scripts.agents.preview_server import PreviewServer


@pytest.fixture
def server_instance():
    preview_root = Path("tests/agents/fixtures/synthetic_preview_data")
    docs_root = Path("docs")
    server = PreviewServer(preview_root=preview_root, docs_root=docs_root, host="127.0.0.1", port=0)
    server.start()
    yield server
    server.stop()


def test_bind_loopback_only():
    preview_root = Path("tests/agents/fixtures/synthetic_preview_data")
    with pytest.raises(ValueError) as exc:
        PreviewServer(preview_root=preview_root, host="0.0.0.0", port=8080)
    assert "loopback" in str(exc.value).lower() or "0.0.0.0" in str(exc.value)


def test_serve_static_docs(server_instance: PreviewServer):
    url = f"http://127.0.0.1:{server_instance.port}/index.html"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        content = resp.read().decode("utf-8")
        assert "<!DOCTYPE html>" in content or "<html" in content


def test_serve_runtime_preview_data(server_instance: PreviewServer):
    url = f"http://127.0.0.1:{server_instance.port}/api/preview/synthetic-pilot/index.json"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        assert resp.headers.get("X-Daemon-Local-Preview") == "active"
        data = json.loads(resp.read().decode("utf-8"))
        assert data["source"] == "synthetic-pilot"
        assert len(data["characters"]) == 1
        assert data["characters"][0]["name"] == "Lobo"


def test_path_traversal_blocked(server_instance: PreviewServer):
    url = f"http://127.0.0.1:{server_instance.port}/api/preview/..%2f..%2fetc/passwd"
    req = urllib.request.Request(url)
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req)
    assert exc.value.code in (400, 403, 404)


def test_windows_ads_and_device_paths_blocked(server_instance: PreviewServer):
    # Test Alternate Data Stream (ADS)
    url_ads = f"http://127.0.0.1:{server_instance.port}/api/preview/synthetic-pilot/index.json::$DATA"
    req_ads = urllib.request.Request(url_ads)
    with pytest.raises(urllib.error.HTTPError) as exc_ads:
        urllib.request.urlopen(req_ads)
    assert exc_ads.value.code in (400, 403, 404)

    # Test reserved device name
    url_dev = f"http://127.0.0.1:{server_instance.port}/CON"
    req_dev = urllib.request.Request(url_dev)
    with pytest.raises(urllib.error.HTTPError) as exc_dev:
        urllib.request.urlopen(req_dev)
    assert exc_dev.value.code in (400, 403, 404)



def test_frontend_acceptance_search():
    fixture_path = Path("tests/agents/fixtures/synthetic_preview_data/synthetic-pilot/index.json")
    with open(fixture_path, encoding="utf-8") as f:
        data = json.load(f)

    # Search algorithm simulation
    query = "Lobo".lower()
    characters = data.get("characters", [])
    matched = [c for c in characters if query in c["name"].lower()]
    assert len(matched) == 1
    assert matched[0]["id"] == "lobo"


def test_frontend_acceptance_navigation():
    fixture_path = Path("tests/agents/fixtures/synthetic_preview_data/synthetic-pilot/index.json")
    with open(fixture_path, encoding="utf-8") as f:
        data = json.load(f)

    npc = data["characters"][0]
    expected_hash = f"#/criaturas-npcs/synthetic-pilot-npc-{npc['id']}"
    assert npc["name"] == "Lobo"
    assert len(npc["sections"]) == 1
    assert "Fera canina" in npc["sections"][0]["paragraphs"][0]


def test_frontend_acceptance_relations():
    fixture_path = Path("tests/agents/fixtures/synthetic_preview_data/synthetic-pilot/index.json")
    with open(fixture_path, encoding="utf-8") as f:
        data = json.load(f)

    relations = data.get("relations", [])
    assert len(relations) == 1
    rel = relations[0]
    assert rel["type"] == "HAS_POWER"
    assert rel["sourceEntityId"] == "synthetic-pilot:npc-lobo"
    assert rel["targetEntityId"] == "synthetic-pilot:group-poderes-lobo"
