from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path
import time

from scripts.agents.preview_server import PreviewServer
from scripts.orchestrator.batch_orchestrator import BatchOrchestrator


def main() -> int:
    parser = argparse.ArgumentParser(description="Motor privado da Release C (Linux/POSIX)")
    parser.add_argument("--runtime-dir", type=Path, required=True, help="Diretório privado fora do repositório")
    parser.add_argument("--demo", action="store_true", help="Cinco documentos sintéticos; não processa o acervo")
    parser.add_argument("--registry", type=Path, help="JSON privado com bookId, manifest e metadata opcionais")
    parser.add_argument("--adapters", help="Factory Python confiável no formato modulo:funcao")
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--serve", action="store_true", help="Servir painel autenticado em loopback")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--wave-review-id")
    args = parser.parse_args()
    if args.demo and any((args.registry, args.adapters, args.source_root)):
        parser.error("--demo não aceita registry/adapters/source-root")
    if not args.demo and not all((args.registry, args.adapters, args.source_root)):
        parser.error("Informe --demo ou registry/adapters/source-root explícitos")
    runtime = args.runtime_dir.resolve()
    project = Path(__file__).resolve().parents[2]
    if runtime == project or project in runtime.parents:
        parser.error("O runtime precisa ficar fora do checkout")
    if args.demo:
        from scripts.orchestrator.demo import build_executors, create_sources
        adapters = build_executors()
        registrations = create_sources(runtime)
        source_root = runtime
    else:
        module_name, factory_name = args.adapters.split(":", 1)
        adapters = getattr(importlib.import_module(module_name), factory_name)()
        registrations = json.loads(args.registry.read_text(encoding="utf-8"))
        source_root = args.source_root
    with BatchOrchestrator(runtime, source_root=source_root, executors=adapters,
                           concurrency=args.concurrency, evidence_review_id=args.wave_review_id) as engine:
        for registration in registrations:
            if registration["bookId"] not in engine.state["books"]:
                engine.register(registration["bookId"], registration.get("manifest"),
                                metadata=registration.get("metadata"))
        server = None
        try:
            if args.serve:
                site_data = runtime / "preview/site-data"
                site_data.mkdir(parents=True, exist_ok=True)
                for filename, key in (("catalog.json", "books"), ("search-index.json", "entries")):
                    path = site_data / filename
                    if not path.exists():
                        path.write_text(json.dumps({"schemaVersion": "1.0", "mode": "restricted_preview",
                                                    key: []}), encoding="utf-8")
                server = PreviewServer(runtime / "preview", docs_root=project / "docs", port=args.port,
                                       runtime_dir=runtime, orchestrator=engine)
                server.start()
                print(f"Painel privado: http://127.0.0.1:{server.port}/?site=1#/ops", flush=True)
            engine.start()
            while True:
                if engine.fatal_error:
                    raise RuntimeError(engine.fatal_error)
                snapshot = engine.snapshot()
                if args.demo and not args.serve and all(b["pipelineStatus"] not in
                    ("RUNNING", "QUEUED", "RETRY_WAIT") for b in snapshot["books"]):
                    print(json.dumps(snapshot, ensure_ascii=False, indent=2))
                    return 0
                time.sleep(0.1)
        except KeyboardInterrupt:
            return 0
        finally:
            if server:
                server.stop()


if __name__ == "__main__":
    raise SystemExit(main())
