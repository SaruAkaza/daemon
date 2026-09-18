from __future__ import annotations

import hashlib
import hmac
from http.cookies import SimpleCookie
import os
from pathlib import Path
import secrets
import stat
import subprocess
import sys

from scripts.ops.runtime_locator import get_ops_runtime_dir


class TokenManager:
    """Manages high-entropy process-scoped tokens, Windows/POSIX file permissions, and session cookies."""

    def __init__(self, runtime_dir: Path | str | None = None) -> None:
        self.ops_dir = get_ops_runtime_dir(runtime_dir)
        self.token_file = self.ops_dir / "ops_token"
        self._token: str | None = None
        self._session_secret: str = secrets.token_hex(32)

    def initialize(self) -> str:
        self.ops_dir.mkdir(parents=True, exist_ok=True)
        token = secrets.token_urlsafe(32)

        if self.token_file.exists():
            try:
                self.token_file.unlink()
            except OSError:
                pass

        self.token_file.write_text(token, encoding="utf-8")
        self._restrict_permissions(self.token_file)
        self._token = token
        return token

    def _restrict_permissions(self, path: Path) -> None:
        if sys.platform == "win32":
            username = os.environ.get("USERNAME")
            if not username:
                raise RuntimeError("USERNAME environment variable missing on Windows; cannot restrict token ACL.")
            cmd = ["icacls", str(path), "/inheritance:r", "/grant:r", f"{username}:(R,W)"]
            try:
                res = subprocess.run(cmd, capture_output=True, text=True, check=False)
                if res.returncode != 0:
                    raise RuntimeError(f"Failed to apply ACL with icacls (code {res.returncode}): {res.stderr}")
            except Exception as e:
                raise RuntimeError(f"Failed to configure file ACL on Windows: {e}") from e
        else:
            try:
                path.chmod(stat.S_IRUSR | stat.S_IWUSR)
                mode = path.stat().st_mode & 0o777
                if mode != 0o600:
                    raise RuntimeError(f"Failed to restrict file permissions on POSIX: {oct(mode)}")
            except Exception as e:
                raise RuntimeError(f"Failed to configure file permissions on POSIX: {e}") from e

    def get_token(self) -> str | None:
        if self.token_file.is_file():
            try:
                self._token = self.token_file.read_text(encoding="utf-8").strip()
                return self._token
            except OSError:
                pass
        return self._token

    def _derive_session_value(self, token: str) -> str:
        return hmac.new(self._session_secret.encode("utf-8"), token.encode("utf-8"), hashlib.sha256).hexdigest()

    def create_session_cookie(self) -> str:
        token = self.get_token()
        if not token:
            raise RuntimeError("Cannot create session cookie: token is not initialized.")
        val = self._derive_session_value(token)
        return f"daemon_ops_session={val}; HttpOnly; SameSite=Strict; Path=/api/ops"

    def validate_session(self, cookie_header: str | None, auth_header: str | None) -> bool:
        token = self.get_token()
        if not token:
            return False

        # Check session cookie
        if cookie_header:
            try:
                cookie = SimpleCookie()
                cookie.load(cookie_header)
                if "daemon_ops_session" in cookie:
                    provided_val = cookie["daemon_ops_session"].value
                    expected_val = self._derive_session_value(token)
                    if secrets.compare_digest(provided_val, expected_val):
                        return True
            except Exception:
                pass

        # Check Bearer authorization header
        if auth_header:
            clean = auth_header.strip()
            if clean.lower().startswith("bearer "):
                provided_token = clean[7:].strip()
                if secrets.compare_digest(provided_token, token):
                    return True

        return False

    def cleanup(self) -> None:
        self._token = None
        if self.token_file.exists():
            try:
                self.token_file.unlink()
            except OSError:
                pass
