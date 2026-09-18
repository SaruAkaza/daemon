from pathlib import Path
import subprocess
import pytest

from scripts.ops.token_manager import TokenManager


def test_token_entropy_and_generation(tmp_path):
    tm = TokenManager(runtime_dir=tmp_path)
    token = tm.initialize()

    assert isinstance(token, str)
    assert len(token) >= 32
    assert tm.get_token() == token
    assert (tm.ops_dir / "ops_token").is_file()

    tm.cleanup()
    assert not (tm.ops_dir / "ops_token").exists()


def test_session_cookie_derivation_and_validation(tmp_path):
    tm = TokenManager(runtime_dir=tmp_path)
    token = tm.initialize()

    cookie_str = tm.create_session_cookie()
    assert "daemon_ops_session=" in cookie_str
    assert "HttpOnly" in cookie_str
    assert "SameSite=Strict" in cookie_str
    assert "Path=/api/ops" in cookie_str

    # Extract session value
    parts = cookie_str.split(";")[0].strip()
    session_val = parts.split("=")[1]

    # Validate session via Cookie header
    valid_cookie_header = f"other_cookie=123; daemon_ops_session={session_val}"
    assert tm.validate_session(cookie_header=valid_cookie_header, auth_header=None) is True

    # Validate session via Bearer auth header
    assert tm.validate_session(cookie_header=None, auth_header=f"Bearer {token}") is True
    assert tm.validate_session(cookie_header=None, auth_header=f"bearer {token}") is True

    # Invalid cases
    assert tm.validate_session(cookie_header=None, auth_header=None) is False
    assert tm.validate_session(cookie_header="daemon_ops_session=invalid", auth_header=None) is False
    assert tm.validate_session(cookie_header=None, auth_header="Bearer wrong") is False
    assert tm.validate_session(cookie_header=None, auth_header="") is False

    tm.cleanup()


def test_stale_token_rotated_on_reinit(tmp_path):
    tm1 = TokenManager(runtime_dir=tmp_path)
    t1 = tm1.initialize()

    tm2 = TokenManager(runtime_dir=tmp_path)
    t2 = tm2.initialize()

    assert t1 != t2
    assert tm2.get_token() == t2
    assert tm1.validate_session(cookie_header=None, auth_header=f"Bearer {t1}") is False
    assert tm2.validate_session(cookie_header=None, auth_header=f"Bearer {t2}") is True

    tm2.cleanup()


def test_acl_failure_fails_closed(tmp_path, monkeypatch):
    tm = TokenManager(runtime_dir=tmp_path)

    def mock_subprocess_run(*args, **kwargs):
        return subprocess.CompletedProcess(args=args, returncode=1, stderr=b"Access denied")

    monkeypatch.setattr(subprocess, "run", mock_subprocess_run)

    with pytest.raises(RuntimeError) as exc:
        tm.initialize()
    assert "ACL" in str(exc.value) or "permission" in str(exc.value).lower()
