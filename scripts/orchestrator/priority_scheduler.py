from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "config/scheduler_weights.json"


class PriorityScheduler:
    """Versioned, deterministic ranking. Rights affect rank, never authorization."""

    def __init__(self, config_path: Path | str = DEFAULT_CONFIG) -> None:
        self.config = json.loads(Path(config_path).read_text(encoding="utf-8"))
        expected = {"rightsClarity", "sourceIntegrity", "extractionSimplicity",
                    "dependencyPrecedence", "costEfficiency", "editorialPriority"}
        weights = self.config["criteriaWeights"]
        if set(weights) != expected or not self.config.get("version"):
            raise ValueError("Invalid scheduler configuration")
        if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0
               for v in weights.values()) or sum(weights.values()) <= 0:
            raise ValueError("Scheduler weights must be finite and nonnegative")
        for key in ("rightsScores", "complexityMultipliers"):
            if any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1
                   for v in self.config[key].values()):
                raise ValueError("Scheduler scores must be between zero and one")

    def score(self, book: dict[str, Any]) -> float:
        metadata = book.get("metadata", {})

        def normalized(key: str, default: float = 0) -> float:
            value = metadata.get(key, default)
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError(f"Invalid scheduler input: {key}")
            return max(0, min(1, value / 10))

        values = {
            "rightsClarity": self.config["rightsScores"].get(
                (book.get("manifest") or {}).get("rightsStatus", "UNKNOWN"), 0),
            "sourceIntegrity": 1 if book.get("manifest") else 0,
            "extractionSimplicity": self.config["complexityMultipliers"].get(
                metadata.get("complexity", "MEDIUM"), 0),
            "dependencyPrecedence": normalized("dependencyCount"),
            "costEfficiency": 1 - normalized("estimatedCost", 5),
            "editorialPriority": normalized("editorialPriority", 5),
        }
        return round(sum(self.config["criteriaWeights"][k] * v
                         for k, v in values.items()) * book.get("priorityWeight", 100) / 100, 6)

    def rank(self, books: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(books, key=lambda b: (-self.score(b), b["bookId"]))
