from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from scripts.agents.context_loader import ContextLoader, ContextLoaderError
from scripts.agents.contracts import ContractValidationError, validate_payload


class ContextMaterializationError(RuntimeError):
    """Raised when context materialization fails due to schema violations, missing files, or I/O errors."""
    pass


@dataclass(frozen=True)
class MaterializedContext:
    """Immutable in-memory representation of dereferenced Context Pack layers."""
    layers: dict[str, tuple[dict[str, str], ...]]  # layer_name -> tuple of {"path": str, "content": str}
    metadata: dict[str, Any]


class ContextMaterializer:
    """Deterministic, side-effect-free component that dereferences file paths from a validated Context Pack."""

    def __init__(self, loader: ContextLoader | None = None) -> None:
        self.loader = loader or ContextLoader()

    def materialize(self, context_pack: dict[str, Any]) -> MaterializedContext:
        """Dereferences file paths from a validated Context Pack into in-memory contents.

        Raises:
            ContextMaterializationError: If context_pack is invalid or any referenced file cannot be read.
        """
        if not isinstance(context_pack, dict):
            raise ContextMaterializationError(
                f"context_pack must be a dict, got {type(context_pack).__name__}"
            )

        try:
            validate_payload("context-pack.schema.json", context_pack)
        except ContractValidationError as e:
            raise ContextMaterializationError(f"Context Pack failed schema validation: {e}") from e

        list_layers = ["mandatory", "domain", "bookContext", "jobContext", "handoffContext"]
        materialized_layers: dict[str, tuple[dict[str, str], ...]] = {}

        for layer_name in list_layers:
            paths = context_pack.get(layer_name, [])
            loaded_items: list[dict[str, str]] = []
            for p in paths:
                try:
                    content = self.loader.load_text(p)
                    loaded_items.append({"path": str(p), "content": content})
                except ContextLoaderError as e:
                    raise ContextMaterializationError(
                        f"Failed loading file '{p}' for layer '{layer_name}': {e}"
                    ) from e
                except Exception as e:
                    raise ContextMaterializationError(
                        f"Unexpected error loading file '{p}' for layer '{layer_name}': {e}"
                    ) from e
            materialized_layers[layer_name] = tuple(loaded_items)

        output_contract = context_pack.get("outputContract")
        if output_contract:
            try:
                content = self.loader.load_text(output_contract)
                materialized_layers["outputContract"] = ({"path": str(output_contract), "content": content},)
            except ContextLoaderError as e:
                raise ContextMaterializationError(
                    f"Failed loading output contract file '{output_contract}': {e}"
                ) from e
            except Exception as e:
                raise ContextMaterializationError(
                    f"Unexpected error loading output contract file '{output_contract}': {e}"
                ) from e
        else:
            materialized_layers["outputContract"] = ()

        metadata: dict[str, Any] = {
            "contextPackId": context_pack.get("contextPackId"),
            "jobId": context_pack.get("jobId"),
            "agent": context_pack.get("agent"),
            "stage": context_pack.get("stage"),
            "schemaVersion": context_pack.get("schemaVersion"),
            "task": copy.deepcopy(context_pack.get("task")),
        }

        return MaterializedContext(
            layers=materialized_layers,
            metadata=metadata,
        )
