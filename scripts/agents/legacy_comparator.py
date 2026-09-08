from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LegacyDiscrepancy:
    """Represents a concrete divergence in values between extracted and legacy entities."""
    entity_id: str
    field_path: str
    extracted_value: Any
    legacy_value: Any
    source_citation: str


@dataclass(frozen=True)
class LegacyComparisonResult:
    """Deterministic comparison outcome produced without LLM interpretation."""
    verdict: str  # SEMANTIC_EQUIVALENT | STRUCTURAL_DIFFERENCE_ONLY | SEMANTIC_DIFFERENCE | NO_LEGACY_REFERENCE
    equivalent_count: int
    structural_diff_count: int
    semantic_diff_count: int
    new_entities_count: int
    discrepancies: list[LegacyDiscrepancy]


class LegacyComparator:
    """Deterministic, non-LLM comparator contrasting extracted entities with legacy records."""

    @staticmethod
    def _normalize(val: Any) -> Any:
        if isinstance(val, str):
            return val.strip()
        return val

    @classmethod
    def _get_leaves(cls, obj: Any, prefix: str = "", top_level: bool = True) -> list[tuple[str, Any]]:
        leaves = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                if top_level and k in ("schemaVersion", "provenance", "source", "sourcePath", "page"):
                    continue
                sub_prefix = f"{prefix}.{k}" if prefix else k
                leaves.extend(cls._get_leaves(v, sub_prefix, top_level=False))
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                sub_prefix = f"{prefix}[{i}]"
                leaves.extend(cls._get_leaves(item, sub_prefix, top_level=False))
        else:
            leaves.append((prefix, cls._normalize(obj)))
        return leaves

    def compare_entities(
        self,
        extracted_entities: list[dict[str, Any]],
        legacy_entities: list[dict[str, Any]],
    ) -> LegacyComparisonResult:
        """Deterministically compares extracted entities against legacy records."""
        legacy_map: dict[str, dict[str, Any]] = {}
        for leg in legacy_entities:
            lid = leg.get("id") or leg.get("name")
            if lid:
                legacy_map[lid] = leg

        discrepancies: list[LegacyDiscrepancy] = []
        equivalent_count = 0
        structural_diff_count = 0
        semantic_diff_count = 0
        new_entities_count = 0

        for ext in extracted_entities:
            eid = ext.get("id") or ext.get("name")
            if not eid or eid not in legacy_map:
                new_entities_count += 1
                continue

            leg = legacy_map[eid]
            source_cit = str(ext.get("source") or ext.get("provenance", {}).get("bookId", "unknown"))

            ext_leaves = dict(self._get_leaves(ext))
            leg_leaves = dict(self._get_leaves(leg))

            entity_discrepancies: list[LegacyDiscrepancy] = []

            # 1. Compare common direct paths
            for p, ext_val in ext_leaves.items():
                if p in leg_leaves:
                    leg_val = leg_leaves[p]
                    if ext_val != leg_val:
                        entity_discrepancies.append(
                            LegacyDiscrepancy(
                                entity_id=eid,
                                field_path=p,
                                extracted_value=ext_val,
                                legacy_value=leg_val,
                                source_citation=source_cit,
                            )
                        )

            # 2. Compare matching terminal keys when structure differs
            ext_terminals = {p.split(".")[-1]: (p, v) for p, v in ext_leaves.items()}
            leg_terminals = {p.split(".")[-1]: (p, v) for p, v in leg_leaves.items()}
            for k, (ext_p, ext_v) in ext_terminals.items():
                if k in leg_terminals:
                    leg_p, leg_v = leg_terminals[k]
                    if ext_p not in leg_leaves and ext_v != leg_v:
                        # Value discrepancy across structural difference
                        entity_discrepancies.append(
                            LegacyDiscrepancy(
                                entity_id=eid,
                                field_path=ext_p,
                                extracted_value=ext_v,
                                legacy_value=leg_v,
                                source_citation=source_cit,
                            )
                        )

            if entity_discrepancies:
                semantic_diff_count += 1
                discrepancies.extend(entity_discrepancies)
            elif ext_leaves == leg_leaves:
                equivalent_count += 1
            else:
                structural_diff_count += 1

        # Verdict assignment
        if semantic_diff_count > 0:
            verdict = "SEMANTIC_DIFFERENCE"
        elif equivalent_count == 0 and structural_diff_count == 0 and new_entities_count > 0:
            verdict = "NO_LEGACY_REFERENCE"
        elif structural_diff_count > 0:
            verdict = "STRUCTURAL_DIFFERENCE_ONLY"
        else:
            verdict = "SEMANTIC_EQUIVALENT"

        return LegacyComparisonResult(
            verdict=verdict,
            equivalent_count=equivalent_count,
            structural_diff_count=structural_diff_count,
            semantic_diff_count=semantic_diff_count,
            new_entities_count=new_entities_count,
            discrepancies=discrepancies,
        )
