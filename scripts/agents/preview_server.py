from __future__ import annotations

import mimetypes
import re
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any


WINDOWS_RESERVED_NAMES = {
    "con", "prn", "aux", "nul",
    "com1", "com2", "com3", "com4", "com5", "com6", "com7", "com8", "com9",
    "lpt1", "lpt2", "lpt3", "lpt4", "lpt5", "lpt6", "lpt7", "lpt8", "lpt9",
}


def _is_contained(child: Path, parent: Path) -> bool:
    """Validate that child path is strictly contained within parent directory after symlink resolution."""
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _get_content_type(file_path: Path) -> str:
    """Determine MIME content-type with proper UTF-8 charset and JavaScript standard types."""
    suffix = file_path.suffix.lower()
    if suffix in (".js", ".mjs"):
        return "application/javascript; charset=utf-8"
    if suffix == ".json":
        return "application/json; charset=utf-8"
    if suffix == ".css":
        return "text/css; charset=utf-8"
    if suffix in (".html", ".htm"):
        return "text/html; charset=utf-8"
    ctype, _ = mimetypes.guess_type(str(file_path))
    if ctype:
        if "text" in ctype or "javascript" in ctype:
            return f"{ctype}; charset=utf-8"
        return ctype
    return "application/octet-stream"


def _is_unsafe_path(req_path: str) -> bool:
    if "\\" in req_path or ":" in req_path:
        return True
    segments = [s.strip().lower() for s in req_path.split("/") if s.strip()]
    for s in segments:
        if s in ("..", "."):
            return True
        base_name = s.split(".")[0]
        if base_name in WINDOWS_RESERVED_NAMES:
            return True
    return False


class PreviewServer:
    """Local HTTP development server serving static docs with dynamic runtime preview overlay."""

    def __init__(
        self,
        preview_root: Path | str,
        docs_root: Path | str = Path("docs"),
        host: str = "127.0.0.1",
        port: int = 8080,
        public_root: Path | str | None = None,
    ) -> None:
        if host not in ("127.0.0.1", "localhost"):
            raise ValueError(f"Binding to non-loopback interface '{host}' is strictly prohibited.")

        self.host = host
        self.requested_port = port
        self.preview_root = Path(preview_root).resolve()
        self.docs_root = Path(docs_root).resolve()
        self.public_root = Path(public_root).resolve() if public_root else None
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None
        self.port = port

    def _make_handler(self):
        preview_root = self.preview_root
        docs_root = self.docs_root
        public_root = self.public_root

        class PreviewHandler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: Any) -> None:
                # Suppress noisy HTTP logs in test output
                pass

            def do_GET(self) -> None:
                parsed = urllib.parse.urlparse(self.path)
                req_path = urllib.parse.unquote(parsed.path)

                # Path traversal and Windows ADS / device check
                if _is_unsafe_path(req_path):
                    self.send_error(400, "Path traversal or unsafe path forbidden")
                    return

                # Check /api/preview/ or /preview/
                match = re.match(r"^/(?:api/)?preview/([a-z0-9-]+)/(.*)$", req_path)
                if match:
                    book_id, subpath = match.group(1), match.group(2)
                    book_dir = (preview_root / book_id).resolve()
                    target_file = (book_dir / subpath).resolve()

                    if not target_file.is_file() and subpath.startswith("site-data/"):
                        rel_sub = subpath[len("site-data/"):]
                        cand = (book_dir / rel_sub).resolve()
                        if cand.is_file():
                            target_file = cand

                    if not target_file.is_file() and book_id == "archive":
                        cand1 = (preview_root / "site-data" / subpath).resolve()
                        if cand1.is_file():
                            target_file = cand1
                        elif subpath.startswith("site-data/"):
                            cand2 = (preview_root / subpath).resolve()
                            if cand2.is_file():
                                target_file = cand2

                    if not _is_contained(target_file, preview_root):
                        self.send_error(403, "Access forbidden")
                        return

                    if target_file.is_file():
                        content = target_file.read_bytes()
                        ctype = _get_content_type(target_file)
                        self.send_response(200)
                        self.send_header("Content-Type", ctype)
                        self.send_header("Content-Length", str(len(content)))
                        self.send_header("X-Daemon-Local-Preview", "active")
                        self.end_headers()
                        self.wfile.write(content)
                        return
                    else:
                        self.send_error(404, f"Preview file not found: {subpath}")
                        return

                # Check /api/public/ or /public/
                match_pub = re.match(r"^/(?:api/)?public/(.*)$", req_path)
                if match_pub:
                    subpath = match_pub.group(1)
                    effective_public = public_root
                    if not effective_public:
                        cand = (preview_root / "public").resolve()
                        if cand.is_dir():
                            effective_public = cand

                    if not effective_public or not effective_public.is_dir():
                        self.send_error(404, "Public projection root not configured")
                        return

                    target_file = (effective_public / subpath).resolve()
                    if not target_file.is_file() and subpath.startswith("site-data/"):
                        rel_sub = subpath[len("site-data/"):]
                        target_file = (effective_public / rel_sub).resolve()
                    if not target_file.is_file():
                        target_file = (effective_public / "site-data" / subpath).resolve()

                    if not _is_contained(target_file, effective_public):
                        self.send_error(403, "Access forbidden")
                        return

                    if target_file.is_file():
                        content = target_file.read_bytes()
                        ctype = _get_content_type(target_file)
                        self.send_response(200)
                        self.send_header("Content-Type", ctype)
                        self.send_header("Content-Length", str(len(content)))
                        self.send_header("X-Daemon-Public-Preview", "active")
                        self.end_headers()
                        self.wfile.write(content)
                        return
                    else:
                        self.send_error(404, f"Public file not found: {subpath}")
                        return

                # Check /assets/site-data/ (serve from local preview_root if present, else public_root)
                match_assets_data = re.match(r"^/assets/site-data/(.*)$", req_path)
                if match_assets_data:
                    subpath = match_assets_data.group(1)

                    # 1. Local restricted preview root
                    target_file = (preview_root / "site-data" / subpath).resolve()
                    if not target_file.is_file():
                        target_file = (preview_root / subpath).resolve()

                    if target_file.is_file() and _is_contained(target_file, preview_root):
                        content = target_file.read_bytes()
                        ctype = _get_content_type(target_file)
                        self.send_response(200)
                        self.send_header("Content-Type", ctype)
                        self.send_header("Content-Length", str(len(content)))
                        self.send_header("X-Daemon-Local-Preview", "active")
                        self.end_headers()
                        self.wfile.write(content)
                        return

                    # 2. Public projection root if configured
                    effective_public = public_root
                    if not effective_public:
                        cand = (preview_root / "public").resolve()
                        if cand.is_dir():
                            effective_public = cand

                    if effective_public and effective_public.is_dir():
                        target_file = (effective_public / subpath).resolve()
                        if not target_file.is_file():
                            target_file = (effective_public / "site-data" / subpath).resolve()

                        if target_file.is_file() and _is_contained(target_file, effective_public):
                            content = target_file.read_bytes()
                            ctype = _get_content_type(target_file)
                            self.send_response(200)
                            self.send_header("Content-Type", ctype)
                            self.send_header("Content-Length", str(len(content)))
                            self.send_header("X-Daemon-Public-Preview", "active")
                            self.end_headers()
                            self.wfile.write(content)
                            return

                # Static docs serving
                if req_path in ("/", ""):
                    static_file = (docs_root / "index.html").resolve()
                else:
                    rel_path = req_path.lstrip("/")
                    static_file = (docs_root / rel_path).resolve()

                if not _is_contained(static_file, docs_root):
                    self.send_error(403, "Access forbidden")
                    return

                if static_file.is_file():
                    content = static_file.read_bytes()
                    ctype = _get_content_type(static_file)
                    self.send_response(200)
                    self.send_header("Content-Type", ctype)
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
        public_root: Path | str | None = None,
    ) -> None:
        """Entry point to run the preview server indefinitely in the foreground."""
        server = cls(preview_root=preview_root, port=port, host=host, public_root=public_root)
        server.start()
        print(f"Daemon Tools Local Preview Server running on http://{host}:{server.port}")
        try:
            while True:
                threading.Event().wait(1.0)
        except KeyboardInterrupt:
            print("\nStopping preview server...")
            server.stop()
