from __future__ import annotations

import mimetypes
import re
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any


class PreviewServer:
    """Local HTTP development server serving static docs with dynamic runtime preview overlay."""

    def __init__(
        self,
        preview_root: Path | str,
        docs_root: Path | str = Path("docs"),
        host: str = "127.0.0.1",
        port: int = 8080,
    ) -> None:
        if host not in ("127.0.0.1", "localhost"):
            raise ValueError(f"Binding to non-loopback interface '{host}' is strictly prohibited.")

        self.host = host
        self.requested_port = port
        self.preview_root = Path(preview_root).resolve()
        self.docs_root = Path(docs_root).resolve()
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None
        self.port = port

    def _make_handler(self):
        preview_root = self.preview_root
        docs_root = self.docs_root

        class PreviewHandler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: Any) -> None:
                # Suppress noisy HTTP logs in test output
                pass

            def do_GET(self) -> None:
                parsed = urllib.parse.urlparse(self.path)
                req_path = urllib.parse.unquote(parsed.path)

                # Path traversal check
                if ".." in req_path.split("/") or "\\" in req_path:
                    self.send_error(400, "Path traversal forbidden")
                    return

                # Check /api/preview/ or /preview/
                match = re.match(r"^/(?:api/)?preview/([a-z0-9-]+)/(.*)$", req_path)
                if match:
                    book_id, subpath = match.group(1), match.group(2)
                    target_file = (preview_root / book_id / subpath).resolve()
                    if not str(target_file).startswith(str(preview_root)):
                        self.send_error(403, "Access forbidden")
                        return

                    if target_file.is_file():
                        content = target_file.read_bytes()
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json; charset=utf-8")
                        self.send_header("Content-Length", str(len(content)))
                        self.send_header("X-Daemon-Local-Preview", "active")
                        self.end_headers()
                        self.wfile.write(content)
                        return
                    else:
                        self.send_error(404, f"Preview file not found: {subpath}")
                        return

                # Static docs serving
                if req_path in ("/", ""):
                    static_file = docs_root / "index.html"
                else:
                    rel_path = req_path.lstrip("/")
                    static_file = (docs_root / rel_path).resolve()

                if not str(static_file).startswith(str(docs_root)):
                    self.send_error(403, "Access forbidden")
                    return

                if static_file.is_file():
                    content = static_file.read_bytes()
                    ctype, _ = mimetypes.guess_type(str(static_file))
                    if not ctype:
                        if static_file.suffix == ".js":
                            ctype = "application/javascript"
                        elif static_file.suffix == ".css":
                            ctype = "text/css"
                        elif static_file.suffix == ".json":
                            ctype = "application/json"
                        else:
                            ctype = "text/plain"

                    self.send_response(200)
                    self.send_header("Content-Type", f"{ctype}; charset=utf-8")
                    self.send_header("Content-Length", str(len(content)))
                    self.end_headers()
                    self.wfile.write(content)
                    return

                self.send_error(404, f"File not found: {req_path}")

        return PreviewHandler

    def start(self) -> None:
        """Starts the server in a background thread."""
        handler_cls = self._make_handler()
        self._server = HTTPServer((self.host, self.requested_port), handler_cls)
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Shuts down and releases socket."""
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    @classmethod
    def run_preview_server(
        cls,
        preview_root: Path | str,
        port: int = 8080,
        host: str = "127.0.0.1",
    ) -> None:
        """Entry point to run the preview server indefinitely in the foreground."""
        server = cls(preview_root=preview_root, port=port, host=host)
        server.start()
        print(f"Daemon Tools Local Preview Server running on http://{host}:{server.port}")
        try:
            while True:
                threading.Event().wait(1.0)
        except KeyboardInterrupt:
            print("\nStopping preview server...")
            server.stop()
