from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Iterable, Mapping

from scripts.agents.context_loader import ContextLoader
from scripts.agents.contracts import validate_payload

CANONICAL_LAYERS: tuple[str, ...] = (
    "mandatory",
    "domain",
    "bookContext",
    "jobContext",
    "handoffContext",
)


class ContextPackBuilderError(RuntimeError):
    """Raised when context pack construction fails due to invalid parameters or structure."""
    pass


class ContextPackBuilder:
    """Deterministic builder of minimum sufficient context packs for specialist agents."""

    def __init__(self, loader: ContextLoader | None = None) -> None:
        self._loader = loader if loader is not None else ContextLoader()

    @property
    def loader(self) -> ContextLoader:
        """The underlying ContextLoader instance."""
        return self._loader

    def build(
        self,
        *,
        metadata: dict[str, Any],
        layers: dict[str, Any],
    ) -> dict[str, Any]:
        """Build and validate a deterministic, minimum sufficient Context Pack.

        Args:
            metadata: Top-level Context Pack properties (contextPackId, jobId, agent, stage, task, outputContract, etc.)
            layers: Mapping of canonical context layers to sequences of repository relative paths.

        Returns:
            A validated Context Pack dictionary compliant with context-pack.schema.json.

        Raises:
            ContextPackBuilderError: If input types are invalid, unknown layers are specified,
                                     or cross-layer path duplicates are detected.
            ContextPathError: If any path is empty, absolute, or attempts traversal.
            ContextNotFoundError: If any referenced file or contract does not exist or is a directory.
            ContextEncodingError: If any referenced file contains invalid UTF-8.
            ContractValidationError: If the resulting pack fails validation against context-pack.schema.json.
        """
        if not isinstance(metadata, dict):
            raise ContextPackBuilderError(
                f"metadata must be a dict, got {type(metadata).__name__}"
            )

        if not isinstance(layers, dict):
            raise ContextPackBuilderError(
                f"layers must be a dict, got {type(layers).__name__}"
            )

        for layer_key in layers:
            if layer_key not in CANONICAL_LAYERS:
                raise ContextPackBuilderError(
                    f"Unknown context layer: '{layer_key}'. Allowed canonical layers are: {CANONICAL_LAYERS}"
                )

        metadata_copy = copy.deepcopy(metadata)
        seen_paths: dict[str, str] = {}
        processed_layers: dict[str, list[str]] = {}

        for layer_name in CANONICAL_LAYERS:
            raw_paths = layers.get(layer_name, [])
            if isinstance(raw_paths, (str, bytes, dict)) or not isinstance(raw_paths, Iterable):
                raise ContextPackBuilderError(
                    f"Layer '{layer_name}' must be an iterable sequence of relative paths, got {type(raw_paths).__name__}"
                )

            layer_unique_paths: list[str] = []
            layer_seen: set[str] = set()

            for item in raw_paths:
                if not isinstance(item, (str, Path)):
                    raise ContextPackBuilderError(
                        f"Path in layer '{layer_name}' must be str or Path, got {type(item).__name__}"
                    )

                # Validate path security and resolve through loader
                self._loader.resolve(item)
                norm_path = Path(item).as_posix()
                # Cross-layer authority collision check
                if norm_path in seen_paths and seen_paths[norm_path] != layer_name:
                    previous_layer = seen_paths[norm_path]
                    raise ContextPackBuilderError(
                        f"Cross-layer path duplicate: '{norm_path}' assigned to multiple layers ('{previous_layer}' and '{layer_name}')"
                    )

                # Same-layer deduplication (preserve first occurrence)
                if norm_path not in layer_seen:
                    layer_seen.add(norm_path)
                    seen_paths[norm_path] = layer_name
                    # Load text via loader to verify existence, file type, and UTF-8 encoding
                    self._loader.load_text(norm_path)
                    layer_unique_paths.append(norm_path)

            processed_layers[layer_name] = layer_unique_paths

        # If outputContract is specified in metadata, verify its existence and readability
        if "outputContract" in metadata_copy and isinstance(metadata_copy["outputContract"], (str, Path)):
            self._loader.load_text(metadata_copy["outputContract"])

        # Construct payload in canonical hierarchy order
        pack: dict[str, Any] = {}
        pack["schemaVersion"] = metadata_copy.get("schemaVersion", "1.0")

        for key in ("contextPackId", "jobId", "agent", "stage"):
            if key in metadata_copy:
                pack[key] = metadata_copy[key]

        for layer_name in CANONICAL_LAYERS:
            pack[layer_name] = processed_layers.get(layer_name, [])

        if "task" in metadata_copy:
            pack["task"] = metadata_copy["task"]

        if "outputContract" in metadata_copy:
            pack["outputContract"] = metadata_copy["outputContract"]

        # Preserve any additional properties from metadata (which schema validation will check)
        for k, v in metadata_copy.items():
            if k not in pack:
                pack[k] = v

        # Validate against context-pack.schema.json
        validate_payload("context-pack.schema.json", pack)

        return pack
