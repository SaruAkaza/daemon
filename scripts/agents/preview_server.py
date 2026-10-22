from __future__ import annotations

import mimetypes
import queue
import re
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from scripts.ops.command_audit import CommandAuditLog
from scripts.ops.command_processor import CommandProcessor
from scripts.ops.command_store import CommandStore
from scripts.ops.event_broadcaster import EventBroadcaster
from scripts.ops.ops_server import OpsRequestHandler
from scripts.ops.review_store import ReviewStore
from scripts.ops.runtime_locator import get_ops_stores_dir
from scripts.ops.token_manager import TokenManager


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
        mode: str = "restricted_preview",
        runtime_dir: Path | str | None = None,
        orchestrator: Any | None = None,
    ) -> None:
        if host not in ("127.0.0.1", "localhost"):
            raise ValueError(f"Binding to non-loopback interface '{host}' is strictly prohibited.")
        if mode not in ("restricted_preview", "public"):
            raise ValueError(f"Invalid server mode: '{mode}'. Must be 'restricted_preview' or 'public'.")
        if orchestrator is not None and mode != "restricted_preview":
            raise ValueError("Batch execution is available only in restricted_preview mode")
        if orchestrator is not None:
            runtime_dir = runtime_dir if runtime_dir is not None else orchestrator.runtime_dir
            if Path(runtime_dir).resolve() != orchestrator.runtime_dir:
                raise ValueError("Preview and batch must use the same private runtime")

        self.host = host
        self.requested_port = port
        self.preview_root = Path(preview_root).resolve()
        self.docs_root = Path(docs_root).resolve()
        self.public_root = Path(public_root).resolve() if public_root else None
        self.mode = mode
        self.runtime_dir = runtime_dir
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._shutdown_requested = False
        self.port = port

        if self.mode == "restricted_preview":
            stores_dir = orchestrator.reviews.stores_dir if orchestrator else get_ops_stores_dir(runtime_dir)
            self.token_manager = TokenManager(runtime_dir=runtime_dir,
                                             ops_dir=orchestrator.runtime_dir / "ops" if orchestrator else None)
            self.token_manager.initialize()
            self.command_store = CommandStore(stores_dir=stores_dir)
            self.audit_log = CommandAuditLog(stores_dir=stores_dir)
            self.review_store = orchestrator.reviews if orchestrator else ReviewStore(stores_dir=stores_dir)
            self.broadcaster = EventBroadcaster()
            if orchestrator:
                orchestrator.broadcaster = self.broadcaster
            self.command_processor = CommandProcessor(
                command_store=self.command_store,
                audit_log=self.audit_log,
                review_store=self.review_store,
                broadcaster=self.broadcaster,
                orchestrator=orchestrator,
            )
            self.ops_handler = OpsRequestHandler(
                token_manager=self.token_manager,
                command_processor=self.command_processor,
                broadcaster=self.broadcaster,
            )
        else:
            self.token_manager = None
            self.command_store = None
            self.audit_log = None
            self.review_store = None
            self.command_processor = None
            self.broadcaster = None
            self.ops_handler = None

    def _make_handler(self):
        preview_root = self.preview_root
        docs_root = self.docs_root
        public_root = self.public_root
        server_ref = self

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

                # Public mode fail-closed barrier & ops handler routing
                if req_path.startswith("/api/ops"):
                    if server_ref.mode == "public":
                        self.send_error(404, "Not Found")
                        return
                    if not server_ref.ops_handler:
                        self.send_error(404, "Ops handler not configured")
                        return

                    # Real continuous SSE streaming for /api/ops/events
                    if req_path.rstrip("/") == "/api/ops/events":
                        # Authentication check (cookie or bearer)
                        cookie_hdr = self.headers.get("Cookie")
                        auth_hdr = self.headers.get("Authorization")
                        if not server_ref.token_manager.validate_session(cookie_hdr, auth_hdr):
                            self.send_error(401, "Unauthorized")
                            return

                        if self.client_address[0] not in ("127.0.0.1", "::1", "localhost"):
                            self.send_error(403, "Forbidden")
                            return

                        self.send_response(200)
                        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                        self.send_header("Cache-Control", "no-cache, no-transform")
                        self.send_header("Connection", "keep-alive")
                        self.send_header("X-Accel-Buffering", "no")
                        self.end_headers()
                        try:
                            self.wfile.flush()
                        except OSError:
                            return

                        last_event_id_str = self.headers.get("Last-Event-ID")
                        if last_event_id_str:
                            try:
                                last_id = int(last_event_id_str)
                                past_events, needs_snap = server_ref.broadcaster.get_events_since(last_id)
                                if needs_snap:
                                    msg = "event: snapshot_required\ndata: {}\n\n"
                                    self.wfile.write(msg.encode("utf-8"))
                                    self.wfile.flush()
                                else:
                                    for ev in past_events:
                                        msg = server_ref.broadcaster.format_sse_message(ev["id"], ev["type"], ev["data"])
                                        self.wfile.write(msg.encode("utf-8"))
                                    self.wfile.flush()
                            except (ValueError, OSError):
                                pass

                        sub_queue = server_ref.broadcaster.subscribe()
                        try:
                            while not server_ref._shutdown_requested:
                                try:
                                    ev = sub_queue.get(timeout=2.0)
                                    msg = server_ref.broadcaster.format_sse_message(ev["id"], ev["type"], ev["data"])
                                    self.wfile.write(msg.encode("utf-8"))
                                    self.wfile.flush()
                                except queue.Empty:
                                    self.wfile.write(b": keepalive\n\n")
                                    self.wfile.flush()
                        except (BrokenPipeError, ConnectionResetError, OSError):
                            pass
                        finally:
                            server_ref.broadcaster.unsubscribe(sub_queue)
                            self.close_connection = True
                        return

                    headers_dict = {k: v for k, v in self.headers.items()}
                    status_code, resp_headers, resp_body = server_ref.ops_handler.handle_request(
                        method="GET",
                        path=self.path,
                        headers=headers_dict,
                        client_address=self.client_address,
                        body=b"",
                    )
                    self.send_response(status_code)
                    for hk, hv in resp_headers.items():
                        self.send_header(hk, hv)
                    if isinstance(resp_body, bytes):
                        self.send_header("Content-Length", str(len(resp_body)))
                        self.end_headers()
                        self.wfile.write(resp_body)
                    else:
                        self.end_headers()
                    return

                # Check /api/preview/archive/ or /preview/archive/
                match_archive = re.match(r"^/(?:api/)?preview/archive/(.*)$", req_path)
                if match_archive:
                    subpath = match_archive.group(1)
                    archive_root = (preview_root / "site-data").resolve()
                    target_file = (archive_root / subpath).resolve()
                    if not target_file.is_file() and subpath.startswith("site-data/"):
                        target_file = (archive_root / subpath[len("site-data/"):]).resolve()

                    if not _is_contained(target_file, archive_root):
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
                        self.send_error(404, f"Archive preview file not found: {subpath}")
                        return

                # Check /api/preview/<book_id>/ or /preview/<book_id>/
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

                    # Strict individual book containment
                    if not _is_contained(target_file, book_dir):
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
                    archive_root = (preview_root / "site-data").resolve()
                    target_file = (archive_root / subpath).resolve()

                    if _is_contained(target_file, archive_root) and target_file.is_file():
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
                        pub_target = (effective_public / "site-data" / subpath).resolve()
                        if not pub_target.is_file():
                            pub_target = (effective_public / subpath).resolve()

                        if _is_contained(pub_target, effective_public) and pub_target.is_file():
                            content = pub_target.read_bytes()
                            ctype = _get_content_type(pub_target)
                            self.send_response(200)
                            self.send_header("Content-Type", ctype)
                            self.send_header("Content-Length", str(len(content)))
                            self.send_header("X-Daemon-Public-Preview", "active")
                            self.end_headers()
                            self.wfile.write(content)
                            return

                    self.send_error(404, f"Site data asset not found: {subpath}")
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
                    if server_ref.mode == "restricted_preview" and server_ref.token_manager and "html" in ctype:
                        cookie_val = server_ref.token_manager.create_session_cookie()
                        self.send_header("Set-Cookie", cookie_val)
                    self.end_headers()
                    self.wfile.write(content)
                    return

                self.send_error(404, f"File not found: {req_path}")

            def do_POST(self) -> None:
                parsed = urllib.parse.urlparse(self.path)
                req_path = urllib.parse.unquote(parsed.path)

                if _is_unsafe_path(req_path):
                    self.send_error(400, "Path traversal or unsafe path forbidden")
                    return

                if req_path.startswith("/api/ops"):
                    if server_ref.mode == "public":
                        self.send_error(404, "Not Found")
                        return
                    if not server_ref.ops_handler:
                        self.send_error(404, "Ops handler not configured")
                        return

                    cl_header = self.headers.get("Content-Length")
                    if cl_header is None:
                        content_length = 0
                    else:
                        try:
                            content_length = int(cl_header.strip())
                            if content_length < 0:
                                self.send_error(400, "Invalid Content-Length")
                                return
                        except ValueError:
                            self.send_error(400, "Invalid Content-Length")
                            return

                    from scripts.ops.ops_server import MAX_PAYLOAD_SIZE
                    if content_length > MAX_PAYLOAD_SIZE:
                        self.send_error(413, "Payload Too Large: maximum body size is 64KB")
                        return

                    body = self.rfile.read(content_length) if content_length > 0 else b""
                    headers_dict = {k: v for k, v in self.headers.items()}
                    status_code, resp_headers, resp_body = server_ref.ops_handler.handle_request(
                        method="POST",
                        path=req_path,
                        headers=headers_dict,
                        client_address=self.client_address,
                        body=body,
                    )
                    self.send_response(status_code)
                    for hk, hv in resp_headers.items():
                        self.send_header(hk, hv)
                    if isinstance(resp_body, bytes):
                        self.send_header("Content-Length", str(len(resp_body)))
                        self.end_headers()
                        self.wfile.write(resp_body)
                    else:
                        self.end_headers()
                    return

                self.send_error(404, "Not Found")

        return PreviewHandler

    def start(self) -> None:
        """Starts the server in a background thread."""
        self._shutdown_requested = False
        handler_cls = self._make_handler()
        self._server = ThreadingHTTPServer((self.host, self.requested_port), handler_cls)
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        if self.mode == "restricted_preview" and self.command_processor:
            self.command_processor.start_worker()

    def stop(self) -> None:
        """Shuts down and releases socket."""
        self._shutdown_requested = True
        if self.command_processor:
            self.command_processor.stop_worker()
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        if self.token_manager:
            self.token_manager.cleanup()

    @classmethod
    def run_preview_server(
        cls,
        preview_root: Path | str | None = None,
        port: int = 8080,
        host: str = "127.0.0.1",
        public_root: Path | str | None = None,
        project_archive: bool = False,
        runtime_dir: Path | str | None = None,
        workspace_root: Path | str | None = None,
        mode: str = "restricted_preview",
    ) -> None:
        """Entry point to run the preview server indefinitely in the foreground."""
        from scripts.agents.archive_inventory_loader import resolve_canonical_runtime_dir

        ws_root = Path(workspace_root).resolve() if workspace_root else Path(__file__).parents[2].resolve()

        if preview_root is None:
            canonical_rt = resolve_canonical_runtime_dir(runtime_dir)
            p_root = (canonical_rt / "preview").resolve()
        else:
            p_root = Path(preview_root).resolve()

        if project_archive:
            from scripts.agents.preview_projector import LocalPreviewProjector
            projector = LocalPreviewProjector()
            projector.project_archive_preview(
                workspace_root=ws_root,
                preview_root=p_root,
                runtime_dir=runtime_dir,
            )

        server = cls(
            preview_root=p_root,
            port=port,
            host=host,
            public_root=public_root,
            mode=mode,
            runtime_dir=runtime_dir,
        )
        server.start()
        print(f"Daemon Tools Local Preview Server running on http://{host}:{server.port} (mode: {mode})")
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            print("\nStopping preview server...")
            server.stop()


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Daemon Tools Local Preview Server for Acervo 281")
    parser.add_argument("--preview-root", type=str, default=None, help="Root directory for preview")
    parser.add_argument("--public-root", type=str, default=None, help="Root directory for public projection")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on (default: 8080)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host interface (default: 127.0.0.1)")
    parser.add_argument("--project-archive", action="store_true", default=False, help="Project Acervo 281 preview before starting server")
    parser.add_argument("--runtime-dir", type=str, default=None, help="Path to .daemon_runtime")
    parser.add_argument("--workspace-root", type=str, default=None, help="Path to repository workspace root")
    parser.add_argument(
        "--mode",
        type=str,
        choices=["restricted_preview", "public"],
        default="restricted_preview",
        help="Server mode (default: restricted_preview)",
    )
    args = parser.parse_args(argv)

    PreviewServer.run_preview_server(
        preview_root=args.preview_root,
        port=args.port,
        host=args.host,
        public_root=args.public_root,
        project_archive=args.project_archive,
        runtime_dir=args.runtime_dir,
        workspace_root=args.workspace_root,
        mode=args.mode,
    )
    return 0


if __name__ == "__main__":
    main()
