from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Callable
import uuid

from scripts.agents.canonical_json import canonical_json_bytes
from scripts.agents.contracts import SCHEMAS_DIR, load_schema, validate_payload, write_atomic

STAGES = ("source", "extraction", "editorial", "entities", "relations", "frontend", "qa")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def file_hash(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def contained_file(root: Path, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts or "\\" in relative:
        raise ValueError("Artifact path must be relative and contained")
    path = (root / candidate).resolve()
    path.relative_to(root.resolve())
    if not path.is_file():
        raise ValueError(f"Artifact is missing: {relative}")
    return path


@dataclass(frozen=True)
class StageContext:
    book_id: str
    stage: str
    manifest: dict[str, Any]
    source_path: Path
    workspace: Path
    predecessors: tuple[dict[str, Any], ...]
    attempt: int


@dataclass(frozen=True)
class StageExecutor:
    """Trusted adapter and independent validator, versioned by the integrator.

    run returns relative artifact paths mapped to existing JSON schema names.
    validate checks semantics/provenance and raises on failure. A returned boolean
    or an adapter-provided 'passed' field cannot substitute for this gate.
    """
    version: str
    schemas: tuple[str, ...]
    run: Callable[[StageContext], dict[str, str]]
    validate: Callable[[StageContext, dict[str, Any]], None]

    def fingerprint(self) -> str:
        schemas: dict[str, Any] = {}

        def visit(name: str) -> None:
            name = name.removesuffix(".schema.json")
            if name in schemas:
                return
            schema = load_schema(name)
            schemas[name] = schema

            def references(value: Any) -> None:
                if isinstance(value, dict):
                    ref = value.get("$ref", "")
                    if ref and not ref.startswith("#"):
                        filename = ref.split("#")[0].rsplit("/", 1)[-1]
                        if not (SCHEMAS_DIR / filename).is_file():
                            raise ValueError(f"Unresolved contract dependency: {ref}")
                        visit(filename)
                    for child in value.values():
                        references(child)
                elif isinstance(value, list):
                    for child in value:
                        references(child)
            references(schema)

        if not self.version or not self.schemas or not callable(self.validate) or not callable(self.run):
            raise ValueError("Executor needs a version, artifact schemas and independent validator")
        for name in self.schemas:
            visit(name)
        return digest({"version": self.version, "schemas": schemas})


class CheckpointManager:
    def __init__(self, root: Path) -> None:
        self.root = root

    def path(self, book_id: str, stage: str) -> Path:
        if stage not in STAGES:
            raise ValueError(f"Unknown stage: {stage}")
        return self.root / "checkpoints" / digest(book_id) / f"{stage}.json"

    def load(self, book_id: str, stage: str) -> dict[str, Any] | None:
        path = self.path(book_id, stage)
        if not path.exists():
            return None
        cp = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(cp, dict):
            raise ValueError("Checkpoint must be an object")
        return cp

    def quarantine(self, book_id: str, stage: str) -> None:
        path = self.path(book_id, stage)
        path.rename(path.with_suffix(f".invalid-{uuid.uuid4().hex}.json"))

    def artifacts(self, refs: dict[str, dict[str, str]], executor: StageExecutor) -> dict[str, Any]:
        if not refs:
            raise ValueError("A completed stage must produce validated artifacts")
        payloads = {}
        for relative, ref in refs.items():
            if ref["schema"] not in executor.schemas:
                raise ValueError("Artifact schema is outside the executor contract")
            path = contained_file(self.root, relative)
            # Validate exactly the bytes hashed; the gate never rereads a different snapshot.
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != ref["sha256"]:
                raise ValueError(f"Artifact hash mismatch: {relative}")
            payload = json.loads(raw)
            validate_payload(ref["schema"], payload)
            payloads[relative] = payload
        return payloads

    def verify(self, cp: dict[str, Any], *, book_id: str, stage: str, epoch: int,
               input_hash: str, executor: StageExecutor, context: StageContext) -> None:
        expected = (book_id, stage, epoch, input_hash, executor.fingerprint(), "PASSED")
        actual = tuple(cp.get(k) for k in
                       ("bookId", "stage", "epoch", "inputHash", "contractHash", "status"))
        if actual != expected or cp.get("outputHash") != digest(cp["artifactRefs"]):
            raise ValueError("Checkpoint input, contract, epoch or output is stale")
        workspace = (self.root / cp["workspace"]).resolve()
        workspace.relative_to(self.root.resolve())
        for relative in cp["artifactRefs"]:
            contained_file(self.root, relative).relative_to(workspace)
        if executor.validate(context, self.artifacts(cp["artifactRefs"], executor)) is not None:
            raise ValueError("Gate must return None on acceptance")

    def commit(self, cp: dict[str, Any]) -> None:
        write_atomic(self.path(cp["bookId"], cp["stage"]), canonical_json_bytes(cp))
