import json
import urllib.request
import urllib.error
import pytest

from scripts.agents.preview_server import PreviewServer


def test_restricted_preview_sets_cookie_and_serves_ops(tmp_path):
    preview_root = tmp_path / "preview"
    preview_root.mkdir(parents=True)
    docs_root = tmp_path / "docs"
    docs_root.mkdir(parents=True)
    (docs_root / "index.html").write_text("<html><body>Preview</body></html>", encoding="utf-8")

    server = PreviewServer(
        preview_root=preview_root,
        docs_root=docs_root,
        port=0,
        mode="restricted_preview",
        runtime_dir=tmp_path,
    )
    server.start()
    try:
        base_url = f"http://127.0.0.1:{server.port}"

        # 1. GET / should set daemon_ops_session cookie with HttpOnly; SameSite=Strict; Path=/api/ops
        req = urllib.request.Request(f"{base_url}/")
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            cookie_hdr = resp.headers.get("Set-Cookie", "")
            assert "daemon_ops_session=" in cookie_hdr
            assert "HttpOnly" in cookie_hdr
            assert "Path=/api/ops" in cookie_hdr

        cookie_val = cookie_hdr.split(";")[0]

        # 2. GET /api/ops/snapshot without cookie returns 401
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(f"{base_url}/api/ops/snapshot")
        assert exc_info.value.code == 401

        # 3. GET /api/ops/snapshot with cookie returns 200
        req_snap = urllib.request.Request(f"{base_url}/api/ops/snapshot")
        req_snap.add_header("Cookie", cookie_val)
        with urllib.request.urlopen(req_snap) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert "controlState" in data
            assert "commands" in data
            assert "reviews" in data
    finally:
        server.stop()


def test_public_mode_strict_404_fail_closed_barrier(tmp_path):
    preview_root = tmp_path / "preview"
    preview_root.mkdir(parents=True)
    docs_root = tmp_path / "docs"
    docs_root.mkdir(parents=True)
    (docs_root / "index.html").write_text("<html><body>Public</body></html>", encoding="utf-8")

    server = PreviewServer(
        preview_root=preview_root,
        docs_root=docs_root,
        port=0,
        mode="public",
        runtime_dir=tmp_path,
    )
    server.start()
    try:
        base_url = f"http://127.0.0.1:{server.port}"

        # 1. GET / does NOT set daemon_ops_session cookie
        req = urllib.request.Request(f"{base_url}/")
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            cookie_hdr = resp.headers.get("Set-Cookie", "")
            assert "daemon_ops_session" not in cookie_hdr

        # 2. Any /api/ops/* path strictly returns 404
        for path in ("/api/ops/snapshot", "/api/ops/commands", "/api/ops/events"):
            with pytest.raises(urllib.error.HTTPError) as exc_info:
                urllib.request.urlopen(f"{base_url}{path}")
            assert exc_info.value.code == 404
    finally:
        server.stop()
