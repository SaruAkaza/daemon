import json
import pytest

from scripts.ops.command_audit import CommandAuditLog
from scripts.ops.command_processor import CommandProcessor
from scripts.ops.command_store import CommandStore
from scripts.ops.event_broadcaster import EventBroadcaster
from scripts.ops.ops_server import OpsRequestHandler
from scripts.ops.review_store import ReviewStore
from scripts.ops.token_manager import TokenManager


@pytest.fixture
def ops_env(tmp_path):
    tm = TokenManager(runtime_dir=tmp_path)
    tm.initialize()
    cs = CommandStore(stores_dir=tmp_path)
    audit = CommandAuditLog(stores_dir=tmp_path)
    rs = ReviewStore(stores_dir=tmp_path)
    proc = CommandProcessor(command_store=cs, audit_log=audit, review_store=rs)
    bc = EventBroadcaster()
    handler = OpsRequestHandler(
        token_manager=tm,
        command_processor=proc,
        broadcaster=bc,
    )
    cookie_str = tm.create_session_cookie().split(";")[0]  # daemon_ops_session=...
    return {
        "tm": tm,
        "cs": cs,
        "audit": audit,
        "rs": rs,
        "proc": proc,
        "bc": bc,
        "handler": handler,
        "cookie": cookie_str,
        "token": tm.get_token(),
    }


def test_non_loopback_client_ip_forbidden(ops_env):
    handler = ops_env["handler"]
    code, headers, body = handler.handle_request(
        method="GET",
        path="/api/ops/snapshot",
        headers={"host": "127.0.0.1:8080", "cookie": ops_env["cookie"]},
        client_address=("192.168.1.50", 45678),
        body=b"",
    )
    assert code == 403
    assert b"Forbidden" in body


def test_host_header_spoofing_forbidden(ops_env):
    handler = ops_env["handler"]
    code, headers, body = handler.handle_request(
        method="GET",
        path="/api/ops/snapshot",
        headers={"host": "malicious-site.com", "cookie": ops_env["cookie"]},
        client_address=("127.0.0.1", 45678),
        body=b"",
    )
    assert code == 403
    assert b"Forbidden" in body


def test_origin_header_spoofing_forbidden(ops_env):
    handler = ops_env["handler"]
    code, headers, body = handler.handle_request(
        method="GET",
        path="/api/ops/snapshot",
        headers={
            "host": "127.0.0.1:8080",
            "origin": "http://evil-attacker.com",
            "cookie": ops_env["cookie"],
        },
        client_address=("127.0.0.1", 45678),
        body=b"",
    )
    assert code == 403
    assert b"Forbidden" in body


def test_missing_auth_returns_401(ops_env):
    handler = ops_env["handler"]
    code, headers, body = handler.handle_request(
        method="GET",
        path="/api/ops/snapshot",
        headers={"host": "127.0.0.1:8080"},
        client_address=("127.0.0.1", 45678),
        body=b"",
    )
    assert code == 401
    assert b"Unauthorized" in body


def test_valid_cookie_allows_post_command_202(ops_env):
    handler = ops_env["handler"]
    cmd_data = {
        "commandId": "CMD-SEC-00000001",
        "commandType": "PAUSE_BOOK",
        "bookId": "trevas-3ed",
        "payload": {},
        "reason": "Test security command",
        "operatorId": "alice",
        "confirmation": {"confirmed": True},
    }
    code, headers, body = handler.handle_request(
        method="POST",
        path="/api/ops/commands",
        headers={
            "host": "127.0.0.1:8080",
            "origin": "http://127.0.0.1:8080",
            "content-type": "application/json",
            "cookie": ops_env["cookie"],
        },
        client_address=("127.0.0.1", 45678),
        body=json.dumps(cmd_data).encode("utf-8"),
    )
    assert code == 202
    resp_json = json.loads(body.decode("utf-8"))
    assert resp_json["status"] == "ACCEPTED"
    assert resp_json["commandId"] == "CMD-SEC-00000001"


def test_exact_origin_port_mismatch_forbidden(ops_env):
    handler = ops_env["handler"]
    cmd_data = {
        "commandId": "CMD-SEC-PORT-01",
        "commandType": "PAUSE_BOOK",
        "bookId": "trevas-3ed",
        "payload": {},
        "reason": "Origin port mismatch attack",
        "operatorId": "alice",
        "confirmation": {"confirmed": True},
    }
    code, headers, body = handler.handle_request(
        method="POST",
        path="/api/ops/commands",
        headers={
            "host": "127.0.0.1:8080",
            "origin": "http://127.0.0.1:9999",
            "content-type": "application/json",
            "cookie": ops_env["cookie"],
        },
        client_address=("127.0.0.1", 45678),
        body=json.dumps(cmd_data).encode("utf-8"),
    )
    assert code == 403
    assert b"Origin does not match" in body
    assert ops_env["cs"].get_command("CMD-SEC-PORT-01") is None


def test_content_type_non_json_returns_415(ops_env):
    handler = ops_env["handler"]
    cmd_data = {
        "commandId": "CMD-SEC-CTYPE-01",
        "commandType": "PAUSE_BOOK",
        "bookId": "trevas-3ed",
        "payload": {},
        "reason": "Non json content-type",
        "operatorId": "alice",
        "confirmation": {"confirmed": True},
    }
    for bad_ct in ("text/plain", "application/x-www-form-urlencoded", "multipart/form-data"):
        code, headers, body = handler.handle_request(
            method="POST",
            path="/api/ops/commands",
            headers={
                "host": "127.0.0.1:8080",
                "origin": "http://127.0.0.1:8080",
                "content-type": bad_ct,
                "cookie": ops_env["cookie"],
            },
            client_address=("127.0.0.1", 45678),
            body=json.dumps(cmd_data).encode("utf-8"),
        )
        assert code == 415
        assert b"Unsupported Media Type" in body
        assert ops_env["cs"].get_command("CMD-SEC-CTYPE-01") is None


def test_csrf_attack_rejected_zero_mutation(ops_env):
    handler = ops_env["handler"]
    cmd_data = {
        "commandId": "CMD-CSRF-001",
        "commandType": "PAUSE_BOOK",
        "bookId": "trevas-3ed",
        "payload": {},
        "reason": "CSRF attempt with form/plain",
        "operatorId": "alice",
        "confirmation": {"confirmed": True},
    }
    # Attacker tries from different port with text/plain body
    code, headers, body = handler.handle_request(
        method="POST",
        path="/api/ops/commands",
        headers={
            "host": "127.0.0.1:8080",
            "origin": "http://127.0.0.1:9999",
            "content-type": "text/plain",
            "cookie": ops_env["cookie"],
        },
        client_address=("127.0.0.1", 45678),
        body=json.dumps(cmd_data).encode("utf-8"),
    )
    assert code == 403
    assert ops_env["cs"].get_command("CMD-CSRF-001") is None
    assert "CMD-CSRF-001" not in [e.get("commandId") for e in ops_env["audit"].read_all_actions()]


def test_cli_bearer_without_origin_allowed(ops_env):
    handler = ops_env["handler"]
    cmd_data = {
        "commandId": "CMD-BEARER-001",
        "commandType": "PAUSE_BOOK",
        "bookId": "trevas-3ed",
        "payload": {},
        "reason": "CLI bearer operation without browser origin",
        "operatorId": "cli-operator",
        "confirmation": {"confirmed": True},
    }
    code, headers, body = handler.handle_request(
        method="POST",
        path="/api/ops/commands",
        headers={
            "host": "127.0.0.1:8080",
            "authorization": f"Bearer {ops_env['token']}",
            "content-type": "application/json",
        },
        client_address=("127.0.0.1", 45678),
        body=json.dumps(cmd_data).encode("utf-8"),
    )
    assert code == 202
    assert ops_env["cs"].get_command("CMD-BEARER-001") is not None


def test_conflicting_command_payload_returns_409(ops_env):
    handler = ops_env["handler"]
    cmd_data = {
        "commandId": "CMD-CONFLICT-001",
        "commandType": "PAUSE_BOOK",
        "bookId": "trevas-3ed",
        "payload": {},
        "reason": "Initial",
        "operatorId": "alice",
        "confirmation": {"confirmed": True},
    }
    code1, _, _ = handler.handle_request(
        method="POST",
        path="/api/ops/commands",
        headers={
            "host": "127.0.0.1:8080",
            "origin": "http://127.0.0.1:8080",
            "content-type": "application/json",
            "cookie": ops_env["cookie"],
        },
        client_address=("127.0.0.1", 45678),
        body=json.dumps(cmd_data).encode("utf-8"),
    )
    assert code1 == 202

    cmd_diff = dict(cmd_data)
    cmd_diff["reason"] = "Different reason causing conflict"
    code2, _, body2 = handler.handle_request(
        method="POST",
        path="/api/ops/commands",
        headers={
            "host": "127.0.0.1:8080",
            "origin": "http://127.0.0.1:8080",
            "content-type": "application/json",
            "cookie": ops_env["cookie"],
        },
        client_address=("127.0.0.1", 45678),
        body=json.dumps(cmd_diff).encode("utf-8"),
    )
    assert code2 == 409
    assert b"conflict" in body2.lower()


def test_payload_too_large_returns_413(ops_env):
    handler = ops_env["handler"]
    large_body = b"x" * (65 * 1024)  # 65KB > 64KB limit
    code, headers, body = handler.handle_request(
        method="POST",
        path="/api/ops/commands",
        headers={
            "host": "127.0.0.1:8080",
            "origin": "http://127.0.0.1:8080",
            "content-type": "application/json",
            "cookie": ops_env["cookie"],
        },
        client_address=("127.0.0.1", 45678),
        body=large_body,
    )
    assert code == 413
    assert b"Payload Too Large" in body
