from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any

from common import DATA_DIR, ROOT, slugify, read_json, write_json


WORK_DIR = DATA_DIR / "work"
REPORTS_DIR = ROOT / "docs" / "reports" / "granular"


KIT_RE = re.compile(r"\bkits?\b|kits?\s+de\s+personagem|novo\s+kit|novos\s+kits", re.IGNORECASE)
MAGIC_PATH_RE = re.compile(
    r"Caminhos?\s+da\s+Magia|Caminhos?\s*:|Focus|Foco\s+em\s+Caminho|Formas?\s+e\s+Caminhos?|"
    r"Entender/|Criar/|Controlar/|Rituais?|Tempo de Conjura",
    re.IGNORECASE,
)
CREATURE_RE = re.compile(r"\bCON\s+\d+.*\bFR\s+\d+|\bDEX\s+\d+.*\bAGI\s+\d+|#\s*Ataques|\bPVs?\s+\d+", re.IGNORECASE | re.DOTALL)
CLASS_STRONG_RE = re.compile(
    r"poderes?\s+de\s+classe|uma\s+classe\s+rara|nova\s+classe|classe\s+de\s+personagem|"
    r"personagens\s+dessa\s+classe|monges\s+s[aã]o\s+uma\s+classe",
    re.IGNORECASE,
)
PROFESSION_RE = re.compile(r"\bprofiss[aã]o\b|\bprofiss[oõ]es\b|\barqu[eé]tipos?\b|\barquetipos?\b", re.IGNORECASE)
MECHANIC_RE = re.compile(
    r"\bCusto\s*:|\bPer[ií]cias?\s*:|\bAprimoramentos?\s*:|\bRequer\s*:|\bRestri[cç][oõ]es?\s*:|"
    r"\b\d+[º°]\s*N[ií]vel|\bPontos Her[oó]icos\b",
    re.IGNORECASE,
)
LORE_FALSE_POSITIVE_RE = re.compile(r"classe social|classe m[eé]dia|classe dominante|luta entre classes", re.IGNORECASE)


def classify_candidate(candidate: dict[str, Any]) -> tuple[str, str]:
    if candidate.get("source") == "livrodomal":
        return "kit", "Livro do Mal apresenta estes blocos como novos kits"
    context = candidate.get("context", "")
    line = candidate.get("matchedLine", "")
    haystack = f"{line}\n{context}"
    if LORE_FALSE_POSITIVE_RE.search(haystack):
        return "lore", "uso social/historico de classe"
    if KIT_RE.search(haystack):
        return "kit", "bloco rotulado como kit"
    if MAGIC_PATH_RE.search(haystack):
        return "power_magic", "caminho/focus/ritual de magia"
    if CREATURE_RE.search(haystack):
        return "creature_npc", "ficha ou bloco de criatura/npc"
    if CLASS_STRONG_RE.search(haystack) and MECHANIC_RE.search(haystack):
        return "promote_class", "sinal forte de classe com mecanica"
    if PROFESSION_RE.search(haystack) and MECHANIC_RE.search(haystack):
        return "review_class_candidate", "profissao/arquetipo com mecanica, requer leitura"
    if CLASS_STRONG_RE.search(haystack):
        return "review_class_candidate", "sinal de classe sem bloco mecanico suficiente"
    return "lore", "mencao fraca ou contextual"


def main() -> None:
    candidates = read_json(WORK_DIR / "class-profession-archetype-path-candidates.json", [])
    if not isinstance(candidates, list):
        raise SystemExit("Candidate file is not a list.")

    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        bucket, reason = classify_candidate(candidate)
        enriched = {**candidate, "bucket": bucket, "bucketReason": reason}
        buckets[bucket].append(enriched)

    ordered = {
        bucket: sorted(items, key=lambda item: (item.get("source", ""), item.get("page") or 0, item.get("matchedLine", "")))
        for bucket, items in sorted(buckets.items())
    }
    write_json(WORK_DIR / "class-candidate-buckets.json", ordered)

    source_counts = {
        bucket: Counter(item.get("source") for item in items).most_common()
        for bucket, items in ordered.items()
    }
    write_json(WORK_DIR / "class-candidate-bucket-summary.json", source_counts)

    lines = [
        "# Class candidate refinement",
        "",
        "Triagem conservadora dos candidatos de classe/profissao/arquetipo/caminho nas 190 fontes validadas.",
        "",
        "| Bucket | Count | Meaning |",
        "| --- | ---: | --- |",
    ]
    labels = {
        "promote_class": "promover para classes",
        "review_class_candidate": "revisar como possivel classe",
        "kit": "manter fora de classes; tratar em kits",
        "power_magic": "mandar para poderes/magias",
        "creature_npc": "mandar para criaturas/NPCs",
        "lore": "manter como lore/contexto",
    }
    for bucket in ["promote_class", "review_class_candidate", "kit", "power_magic", "creature_npc", "lore"]:
        lines.append(f"| `{bucket}` | {len(ordered.get(bucket, []))} | {labels[bucket]} |")

    lines.extend(["", "## Promote class candidates", ""])
    for item in ordered.get("promote_class", [])[:80]:
        name = slugify(item.get("matchedLine", ""))[:80]
        lines.append(f"- `{item.get('source')}` p.{item.get('page')}: {item.get('matchedLine')} ({name})")

    lines.extend(["", "## Review class candidates", ""])
    for item in ordered.get("review_class_candidate", [])[:80]:
        lines.append(f"- `{item.get('source')}` p.{item.get('page')}: {item.get('matchedLine')}")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / "class-candidate-refinement.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("Class candidate buckets:")
    for bucket in ["promote_class", "review_class_candidate", "kit", "power_magic", "creature_npc", "lore"]:
        print(f"- {bucket}: {len(ordered.get(bucket, []))}")


if __name__ == "__main__":
    main()
