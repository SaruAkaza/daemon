from __future__ import annotations

import json
import os
import shutil
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.agents.canonical_json import (
    canonical_json_bytes,
    compute_input_manifest_hash,
    derive_execution_bundle_id,
    sha256_bytes,
    sha256_file,
)
from scripts.agents.contracts import validate_payload


class ExecutionBundleExporterError(RuntimeError):
    """Raised when bundle export fails due to invalid parameters or filesystem errors."""
    pass


class ExecutionBundleExporter:
    """Exports self-contained, immutable Execution Bundles for manual operator bridge."""

    @staticmethod
    def render_antigravity_instructions(bundle_id: str, request_id: str, contract_name: str) -> str:
        """Renders standard operational guidance for execution in Antigravity."""
        return f"""# ANTIGRAVITY EXECUTION INSTRUCTIONS

## 1. Identificação do Pacote
- **Execution Bundle ID:** `{bundle_id}`
- **Request ID:** `{request_id}`
- **Output Contract:** `{contract_name}`

## 2. Instruções de Execução Manual
1. Inspecione o arquivo `prompt.md` e os arquivos de contexto em `context/` ou anexos em `attachments/`.
2. Execute o modelo ou processe as regras seguindo estritamente o contrato de saída definido em `output-contract.json`.
3. Todos os artefatos de saída gerados devem ser gravados em uma pasta `artifacts/`.
4. Crie o arquivo `execution-result.json` compatível com `execution-result.schema.json` indicando veredicto `ACCEPT`.
5. Crie o manifesto de resultado `result-manifest.json` compatível com `result-bundle.schema.json`.
6. Retorne o diretório completo do pacote de resultados para ingestão no Daemon Tools runtime.
7. **AVISO:** Nunca altere os arquivos originais dentro deste pacote de execução (`{bundle_id}`).
"""

    def export_bundle(
        self,
        request: dict[str, Any],
        attempt: int,
        output_base_dir: Path,
        source_doc: Path | None = None,
    ) -> Path:
        """Exports an immutable Execution Bundle to output_base_dir."""
        if not isinstance(request, dict):
            raise ExecutionBundleExporterError(f"request must be a dict, got {type(request).__name__}")
        if attempt < 1:
            raise ExecutionBundleExporterError(f"attempt must be >= 1, got {attempt}")

        book_id = request.get("bookId")
        request_id = request.get("requestId")
        job_id = request.get("jobId")
        raw_stage = request.get("targetStage", "")
        stage = raw_stage.upper()
        if stage == "FRONTEND":
            stage = "PREVIEW"
        output_schema_name = request.get("outputSchemaName", "")
        task_instruction = request.get("taskInstruction", "")

        if not (book_id and request_id and job_id and stage):
            raise ExecutionBundleExporterError("request is missing required fields (bookId, requestId, jobId, targetStage)")

        output_base_dir = Path(output_base_dir)
        output_base_dir.mkdir(parents=True, exist_ok=True)

        content_seed = canonical_json_bytes({
            "requestId": request_id,
            "jobId": job_id,
            "bookId": book_id,
            "stage": stage,
            "outputSchema": output_schema_name,
            "instruction": task_instruction,
        })
        content_hash = sha256_bytes(content_seed)
        bundle_id = derive_execution_bundle_id(book_id, stage, attempt, content_hash)
        bundle_dir = output_base_dir / bundle_id

        if bundle_dir.exists():
            raise ExecutionBundleExporterError(f"Bundle directory already exists: {bundle_dir}")

        bundle_dir.mkdir(parents=True, exist_ok=False)
        context_dir = bundle_dir / "context"
        context_dir.mkdir(exist_ok=True)
        attachments_dir = bundle_dir / "attachments"
        attachments_dir.mkdir(exist_ok=True)

        # 1. execution-request.json
        req_path = bundle_dir / "execution-request.json"
        req_path.write_bytes(canonical_json_bytes(request))

        # 2. prompt.md
        prompt_path = bundle_dir / "prompt.md"
        prompt_text = request.get("promptText") or task_instruction
        prompt_path.write_text(prompt_text, encoding="utf-8")

        # 3. output-contract.json
        contract_path = bundle_dir / "output-contract.json"
        contract_payload = {"outputSchemaName": output_schema_name}
        # If schema file exists locally, include full schema
        schema_candidate = Path("schemas") / output_schema_name
        if not schema_candidate.exists() and not output_schema_name.endswith(".schema.json"):
            schema_candidate = Path("schemas") / f"{output_schema_name}.schema.json"
        if schema_candidate.exists():
            with open(schema_candidate, encoding="utf-8") as sf:
                contract_payload = json.load(sf)
        contract_path.write_bytes(canonical_json_bytes(contract_payload))

        # 4. attachments
        if source_doc is not None:
            source_doc = Path(source_doc)
            if not source_doc.exists():
                raise ExecutionBundleExporterError(f"source_doc not found: {source_doc}")
            dest_source = attachments_dir / source_doc.name
            shutil.copy2(source_doc, dest_source)

        # 5. ANTIGRAVITY-INSTRUCTIONS.md
        instructions_path = bundle_dir / "ANTIGRAVITY-INSTRUCTIONS.md"
        instructions_text = self.render_antigravity_instructions(bundle_id, request_id, output_schema_name)
        instructions_path.write_text(instructions_text, encoding="utf-8")

        # 6. context-manifest.json
        items = []
        for file_path in [req_path, prompt_path, contract_path, instructions_path]:
            items.append({
                "path": file_path.relative_to(bundle_dir).as_posix(),
                "sha256": sha256_file(file_path),
                "sizeBytes": file_path.stat().st_size,
            })

        for root, _, files in os.walk(attachments_dir):
            for fname in files:
                p = Path(root) / fname
                items.append({
                    "path": p.relative_to(bundle_dir).as_posix(),
                    "sha256": sha256_file(p),
                    "sizeBytes": p.stat().st_size,
                    "description": "Source attachment",
                })

        for root, _, files in os.walk(context_dir):
            for fname in files:
                p = Path(root) / fname
                items.append({
                    "path": p.relative_to(bundle_dir).as_posix(),
                    "sha256": sha256_file(p),
                    "sizeBytes": p.stat().st_size,
                    "description": "Context item",
                })

        items.sort(key=lambda x: x["path"])

        created_at_iso = datetime.now(timezone.utc).isoformat()
        manifest_payload = {
            "bundleId": bundle_id,
            "requestId": request_id,
            "jobId": job_id,
            "stage": stage,
            "bookId": book_id,
            "items": items,
            "createdAt": created_at_iso,
        }
        validate_payload("context-manifest.schema.json", manifest_payload)

        manifest_path = bundle_dir / "context-manifest.json"
        manifest_path.write_bytes(canonical_json_bytes(manifest_payload))

        input_manifest_sha256 = compute_input_manifest_hash(manifest_payload)

        # 7. execution-bundle.json
        envelope_payload = {
            "executionBundleId": bundle_id,
            "requestId": request_id,
            "jobId": job_id,
            "stage": stage,
            "bookId": book_id,
            "attemptNumber": attempt,
            "inputManifestSha256": input_manifest_sha256,
            "executionRequestPath": "execution-request.json",
            "promptPath": "prompt.md",
            "outputContractPath": "output-contract.json",
            "contextManifestPath": "context-manifest.json",
            "instructionsPath": "ANTIGRAVITY-INSTRUCTIONS.md",
            "createdAt": created_at_iso,
        }
        validate_payload("execution-bundle.schema.json", envelope_payload)

        envelope_path = bundle_dir / "execution-bundle.json"
        envelope_path.write_bytes(canonical_json_bytes(envelope_payload))

        # Seal bundle by making files read-only
        for root, _, files in os.walk(bundle_dir):
            for fname in files:
                p = Path(root) / fname
                os.chmod(p, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)

        return bundle_dir
