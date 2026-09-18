import json
import urllib.request
import urllib.error
import pytest

from scripts.agents.preview_server import PreviewServer
from scripts.ops.command_audit import CommandAuditLog
from scripts.ops.command_store import CommandStore
from scripts.ops.hash_chain import IntegrityError
from scripts.ops.review_store import ReviewStore, DecisionValidationError
from scripts.ops.token_manager import TokenManager


def test_complete_ops_lifecycle_e2e(tmp_path):
    preview_root = tmp_path / "preview"
    preview_root.mkdir(parents=True)
    docs_root = tmp_path / "docs"
    docs_root.mkdir(parents=True)
    (docs_root / "index.html").write_text("<html><body>Test</body></html>", encoding="utf-8")

    # 1. Start PreviewServer in restricted_preview mode
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

        # 2. GET / issues same-origin HttpOnly session cookie
        req = urllib.request.Request(f"{base_url}/")
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            cookie_hdr = resp.headers.get("Set-Cookie", "")
            assert "daemon_ops_session=" in cookie_hdr
            assert "HttpOnly" in cookie_hdr
            assert "Path=/api/ops" in cookie_hdr

        cookie_val = cookie_hdr.split(";")[0]

        # 3. GET /api/ops/snapshot returns valid initial operational projection
        req_snap = urllib.request.Request(f"{base_url}/api/ops/snapshot")
        req_snap.add_header("Cookie", cookie_val)
        with urllib.request.urlopen(req_snap) as resp:
            assert resp.status == 200
            snap = json.loads(resp.read().decode("utf-8"))
            assert "controlState" in snap
            assert "commands" in snap
            assert "reviews" in snap

        # 4. Create reviews in ReviewStore: one DOMAIN_AMBIGUITY, one POLICY_OR_RIGHTS
        rs = server.review_store
        assert rs is not None
        rs.create_review({
            "reviewId": "REV-E2E-0001",
            "bookId": "trevas-3ed",
            "stage": "EDITORIAL",
            "category": "DOMAIN_AMBIGUITY",
            "problem": "Conflito terminológico em perícias",
            "evidence": {"term": "armas_brancas"},
            "recommendation": "Aprovar termo canônico",
            "impact": "Médio",
        })
        rs.create_review({
            "reviewId": "REV-E2E-0002",
            "bookId": "demonio-guia",
            "stage": "EDITORIAL",
            "category": "POLICY_OR_RIGHTS",
            "problem": "Verificação de cessão de direitos",
            "evidence": {"clausula": "direitos_autorais"},
            "recommendation": "Aprovar somente com confirmação expressa",
            "impact": "Alto",
        })

        # 5. Submit command for LOW/MEDIUM risk: PAUSE_BOOK
        pause_cmd = {
            "commandId": "CMD-E2E-PAUSE-01",
            "commandType": "PAUSE_BOOK",
            "bookId": "trevas-3ed",
            "payload": {},
            "reason": "Pausa para checagem operacional",
            "operatorId": "operator-alice",
            "confirmation": {"confirmed": True},
        }
        req_pause = urllib.request.Request(
            f"{base_url}/api/ops/commands",
            data=json.dumps(pause_cmd).encode("utf-8"),
            headers={"Content-Type": "application/json", "Cookie": cookie_val},
            method="POST",
        )
        with urllib.request.urlopen(req_pause) as resp:
            assert resp.status == 202

        # 6. Test idempotent resubmission -> 200 OK
        with urllib.request.urlopen(req_pause) as resp:
            assert resp.status == 200

        # 7. Test HIGH risk approval without typedConfirmation -> 400 Bad Request
        bad_high_cmd = {
            "commandId": "CMD-E2E-HIGH-BAD",
            "commandType": "APPROVE_REVIEW",
            "bookId": "demonio-guia",
            "reviewId": "REV-E2E-0002",
            "payload": {},
            "reason": "Aprovando sem digitar ID",
            "operatorId": "operator-alice",
            "confirmation": {"confirmed": True, "typedConfirmation": "wrong-id"},
        }
        req_bad_high = urllib.request.Request(
            f"{base_url}/api/ops/commands",
            data=json.dumps(bad_high_cmd).encode("utf-8"),
            headers={"Content-Type": "application/json", "Cookie": cookie_val},
            method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(req_bad_high)
        assert exc_info.value.code == 400

        # 8. Submit valid HIGH risk approval
        good_high_cmd = {
            "commandId": "CMD-E2E-HIGH-OK01",
            "commandType": "APPROVE_REVIEW",
            "bookId": "demonio-guia",
            "reviewId": "REV-E2E-0002",
            "payload": {},
            "reason": "Autoridade humana expressa concedida",
            "operatorId": "human-alice",
            "confirmation": {"confirmed": True, "typedConfirmation": "demonio-guia"},
        }
        req_good_high = urllib.request.Request(
            f"{base_url}/api/ops/commands",
            data=json.dumps(good_high_cmd).encode("utf-8"),
            headers={"Content-Type": "application/json", "Cookie": cookie_val},
            method="POST",
        )
        with urllib.request.urlopen(req_good_high) as resp:
            assert resp.status == 202

        # 9. Execute worker loop
        count = server.command_processor.process_pending_commands()
        assert count == 2

        # 10. Verify state: trevas-3ed is paused, REV-E2E-0002 is resolved
        ctrl = server.command_store.get_control_state()
        assert "trevas-3ed" in ctrl["pausedBooks"]

        rev_rights = server.review_store.get_review("REV-E2E-0002")
        assert rev_rights["status"] == "RESOLVED"
        assert rev_rights["resolutionAction"] == "APPROVE"

        # 11. Verify hash chain integrity on both audit log and decisions log
        assert server.audit_log.verify_audit_chain() is True
        valid_dec, _, _ = server.review_store.decision_logger.verify_integrity()
        assert valid_dec is True

        # 12. Test SSE streaming endpoint /api/ops/events
        req_events = urllib.request.Request(
            f"{base_url}/api/ops/events",
            headers={"Cookie": cookie_val, "Accept": "text/event-stream"},
        )
        with urllib.request.urlopen(req_events) as resp:
            assert resp.status == 200
            assert "text/event-stream" in resp.headers.get("Content-Type", "")
            data_read = resp.read().decode("utf-8")
            assert len(data_read) > 0

    finally:
        server.stop()


def test_public_mode_isolation_e2e(tmp_path):
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

        # GET / must NOT set any daemon_ops_session cookie
        req = urllib.request.Request(f"{base_url}/")
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            assert "daemon_ops_session" not in resp.headers.get("Set-Cookie", "")

        # All /api/ops/* endpoints strictly return 404
        for endpoint in ("/api/ops/snapshot", "/api/ops/commands", "/api/ops/reviews", "/api/ops/events"):
            with pytest.raises(urllib.error.HTTPError) as exc_info:
                urllib.request.urlopen(f"{base_url}{endpoint}")
            assert exc_info.value.code == 404
    finally:
        server.stop()
