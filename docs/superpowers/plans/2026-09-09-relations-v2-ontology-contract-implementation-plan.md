# Relations V2 Ontology & Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the approved Relations v2 ontology, explicit collection contracts, semantic compatibility validation, unresolved-reference contracts, historical HAS_POWER migration workflow, and prerequisites for a clean Animalidade Relations Attempt 2.

**Architecture:** Relations v2 separates actual possession from selectable options, keeps JSON Schema responsible for structure, centralizes semantic compatibility in one machine-readable matrix, and enforces semantic rules fail-closed through deterministic validation. Historical relations-v1 remains read-only; unresolved endpoints remain outside the canonical graph.

**Tech Stack:** Python 3, JSON Schema Draft 2020-12, JSON, pytest, existing Daemon agent/pilot infrastructure.

**Spec:** `docs/superpowers/specs/2026-09-09-relations-v2-ontology-contract-design.md`

---

## Global Constraints

1. **DOCUMENTATION ONLY IN THIS AUTHORING RUNBOOK**: This plan authoring step modifies only this implementation plan file. Zero production code, schemas, or data are modified during plan authoring.
2. **RESTRICTED PILOT CONTENT ISOLATION**: *Animalidade* is classified as `rightsStatus = "UNKNOWN"`, `publicationMode = "NOT_PUBLIC"`, `pilotMode = "LOCAL_RESTRICTED"`. No candidate relations, no unresolved payloads, and no derived content from *Animalidade* may enter the main Git worktree (`data/`, `docs/`, `Livros/`). All automated repository tests must strictly use synthetic test fixtures.
3. **FAIL-CLOSED GOVERNANCE**: Any relation type not present in the compatibility matrix, any incompatible category pair, or any dangling reference in canonical `relations.json` must immediately trigger deterministic validation failure.
4. **ATTEMPT 1 IMMUTABILITY**: Result Bundle `RB-ANIM-RELATIONS-att1-8317e31e` is frozen historical evidence with status `NEEDS_REWORK`. It is never modified, deleted, or overwritten.
5. **HUMAN MIGRATION GATE**: Historical data migration operates strictly in two phases. Phase 1 produces an audit-only report. Phase 2 (migration apply) requires an explicit cryptographic human approval decision (`ReviewDecision`).
6. **ZERO UNFINISHED DEFINITIONS**: Every task defines exact paths, exact signatures, exact tests, and exact commands. No deferred, stubbed, or ambiguous definitions are permitted.

---

## Repository Components Map

| Logical Component | Repository Path | Responsibility |
|---|---|---|
| Contract Loading & Schema Validation | `scripts/agents/contracts.py` | Validates payloads against Draft 2020-12 schemas |
| Execution Result Validation | `scripts/agents/execution_validator.py` (`ExecutionResultValidator`) | Technical acceptance authority for execution results |
| Write Scope Validation | `scripts/agents/write_scope.py` (`WriteScopeValidator`) | Enforces `allowedWriteScope` path restrictions |
| Context Pack Construction | `scripts/agents/context_pack_builder.py` (`ContextPackBuilder`) | Builds deterministic, schema-compliant context packs |
| Execution Request Construction | `scripts/agents/execution_request_builder.py` (`ExecutionRequestBuilder`) | Builds provider-neutral execution requests |
| Policy Gate Evaluation | `scripts/agents/gate_engine.py` (`GateEngine`) | Progression rules between pipeline stages |
| Pilot QA Validation | `scripts/agents/pilot_qa_validator.py` (`PilotQAValidator`) | Audits dataset integrity, coverage, and relations |
| Pilot Coordination | `scripts/agents/pilot_coordinator.py` (`PilotCoordinator`) | State machine and lifecycle manager for pilot runs |
| Bundle Packaging | `scripts/agents/bundle_exporter.py` (`ExecutionBundleExporter`) | Packages execution bundles for operator handoff |
| Preview Projection | `scripts/agents/preview_projector.py` (`LocalPreviewProjector`) | Projects pilot data to untracked runtime preview |

---

## Planned File Structure

### Files to Create
- `schemas/relation-collection.schema.json` (Collection contract for array of relation items)
- `schemas/unresolved-relation.schema.json` (Item contract for dangling/external relations)
- `schemas/unresolved-relation-collection.schema.json` (Collection contract for unresolved relations)
- `schemas/relation-compatibility.schema.json` (Schema validating the compatibility matrix)
- `schemas/relation-compatibility-v2.json` (Machine-readable canonical authority for semantic compatibility)
- `docs/reference/relation-compatibility-v2.md` (Explanatory human documentation; canonical authority is the JSON)
- `docs/context/decisions/ADR-0004-relations-v2-ontology-and-contracts.md` (Verified next ADR in repository sequence)
- `scripts/agents/relation_compatibility.py` (`RelationCompatibilityValidator` implementation)
- `scripts/agents/historical_relations_auditor.py` (`HistoricalRelationsAuditor` implementation)
- `scripts/agents/historical_relations_migrator.py` (`HistoricalRelationsMigrator` implementation)
- `tests/agents/test_relation_documentation.py` (Tests validating documentation alignment with V2 ontology)
- `tests/agents/test_relation_schemas.py` (Tests for `relation.schema.json` and `relation-collection.schema.json`)
- `tests/agents/test_unresolved_relation_schemas.py` (Tests for unresolved relation contracts)
- `tests/agents/test_relation_version_binding.py` (Tests for `relationOntologyVersion` across pipeline components)
- `tests/agents/test_relation_compatibility_schema.py` (Tests for matrix schema self-validation)
- `tests/agents/test_relation_compatibility_validator.py` (Tests for matrix validator logic)
- `tests/agents/test_historical_relations_auditor.py` (Tests for historical relation classification)
- `tests/agents/test_historical_relations_migrator.py` (Tests for migration apply engine and human gate)

### Files to Modify
- `schemas/relation.schema.json` (Add `CAN_CHOOSE_POWER` and `HAS_WEAKNESS` to type enum)
- `schemas/context-pack.schema.json` (Support optional `relationOntologyVersion`)
- `schemas/execution-request.schema.json` (Support optional `relationOntologyVersion`)
- `scripts/agents/contracts.py` (Support array schema validation and local referencing registry)
- `scripts/agents/execution_validator.py` (Support list payloads for declared collection schemas)
- `scripts/agents/context_pack_builder.py` (Bind `relationOntologyVersion` for relations stage)
- `scripts/agents/execution_request_builder.py` (Bind `relationOntologyVersion` and enforce V2)
- `scripts/agents/pilot_qa_validator.py` (Integrate semantic compatibility checks and unresolved relations)
- `scripts/agents/gate_engine.py` (Integrate semantic relational checks)
- `scripts/agents/prepare_pilot_job.py` (Configure `relation-collection.schema.json` and write scope for relations stage)
- `docs/context/domain/relation-types.md` (Formalize V2 definitions: `HAS_POWER`, `CAN_CHOOSE_POWER`, `HAS_WEAKNESS`)
- `docs/reference/cataloging-rules.md` (Document relations cataloging rules under V2)
- `docs/reference/data-model.md` (Update data model reference with V2 ontology and collection contracts)
- `docs/agents/relations-agent.md` (Update relations agent contract with V2 scope and predicates)
- `tests/agents/test_contracts.py` (Update schema tests to support array schemas)
- `tests/agents/test_execution_validator.py` (Add regression test for Attempt 1 bug)
- `tests/agents/test_pilot_qa_validator.py` (Add compatibility and unresolved relation QA tests)
- `tests/agents/test_gate_engine.py` (Add relation gate evaluation tests)
- `tests/agents/test_prepare_pilot_job.py` (Add test for relations stage configuration)
- `tests/agents/test_pilot_pipeline_e2e.py` (Add synthetic relations stage E2E test)

---

## Implementation Tasks

### Task A: Canonical Relations v2 Documentation + ADR
- **Files**:
  - `docs/context/decisions/ADR-0004-relations-v2-ontology-and-contracts.md` [NEW]
  - `docs/context/domain/relation-types.md` [MODIFY]
  - `docs/reference/cataloging-rules.md` [MODIFY]
  - `docs/reference/data-model.md` [MODIFY]
  - `docs/agents/relations-agent.md` [MODIFY]
  - `tests/agents/test_relation_documentation.py` [NEW]
- **Interfaces**:
  - Markdown documentation files codifying canonical V2 definitions:
    - `HAS_POWER`: "the source entity actually possesses the target power." (actual possession != selectable/available option).
    - `CAN_CHOOSE_POWER`: "the source entity/template is explicitly allowed to select the target power as a build or configuration option." (examples: character creation, character progression, template construction, creature/NPC configuration).
    - `HAS_WEAKNESS`: "the source entity possesses the target weakness, vulnerability, or limitation."
    - Version status: `relations-v1` = historical / read-only; `relations-v2` = mandatory for new execution.
    - Canonical compatibility authority: `schemas/relation-compatibility-v2.json` (machine-readable JSON = canonical authority; markdown = explanatory only).
- **Test**:
  - `tests/agents/test_relation_documentation.py::test_relation_documentation_contains_canonical_ontology_v2`
  - `tests/agents/test_relation_documentation.py::test_adr_0004_exists_and_accepted`
- **RED Command**:
  `pytest tests/agents/test_relation_documentation.py -v`
- **Expected RED Reason**:
  `FileNotFoundError: tests/agents/test_relation_documentation.py does not exist or ADR-0004 not found.`
- **Minimal Implementation**:
  1. Create `tests/agents/test_relation_documentation.py` asserting exact canonical strings across docs and ADR existence.
  2. Create `docs/context/decisions/ADR-0004-relations-v2-ontology-and-contracts.md` with status `Accepted`.
  3. Update `docs/context/domain/relation-types.md` with V2 predicates and versioning rules.
  4. Update `docs/reference/cataloging-rules.md`, `docs/reference/data-model.md`, and `docs/agents/relations-agent.md`.
- **GREEN Command**:
  `pytest tests/agents/test_relation_documentation.py -v`
- **Expected GREEN**:
  `PASSED tests/agents/test_relation_documentation.py::test_relation_documentation_contains_canonical_ontology_v2`  
  `PASSED tests/agents/test_relation_documentation.py::test_adr_0004_exists_and_accepted`
- **Regression Command**:
  `git diff -- docs/`
- **Commit**:
  `docs: formalize relations v2 ontology domain reference and adr-0004`

---

### Task B: Relation Item + Collection Contracts
- **Files**:
  - `schemas/relation.schema.json` [MODIFY]
  - `schemas/relation-collection.schema.json` [NEW]
  - `tests/agents/test_relation_schemas.py` [NEW]
- **Interfaces**:
  - `schemas/relation.schema.json`:
    Add `"CAN_CHOOSE_POWER"` and `"HAS_WEAKNESS"` to `"type"` enum.
  - `schemas/relation-collection.schema.json`:
    Draft 2020-12 schema, `$id: "https://daemon.tools/schemas/relation-collection.schema.json"`, `type: "array"`, `items: { "$ref": "relation.schema.json" }`, `uniqueItems: true`. Empty collection (`[]`) is structurally valid.
- **Tests**:
  - `tests/agents/test_relation_schemas.py::test_relation_item_schema_accepts_valid_item`
  - `tests/agents/test_relation_schemas.py::test_relation_item_schema_accepts_v2_predicates`
  - `tests/agents/test_relation_schemas.py::test_relation_item_schema_rejects_array`
  - `tests/agents/test_relation_schemas.py::test_relation_collection_schema_accepts_valid_array`
  - `tests/agents/test_relation_schemas.py::test_relation_collection_schema_rejects_single_object`
  - `tests/agents/test_relation_schemas.py::test_relation_collection_schema_rejects_invalid_member`
  - `tests/agents/test_relation_schemas.py::test_relation_collection_schema_accepts_empty_array`
- **RED Command**:
  `pytest tests/agents/test_relation_schemas.py -v`
- **Expected RED Reason**:
  `FileNotFoundError: schemas/relation-collection.schema.json does not exist or CAN_CHOOSE_POWER not in enum.`
- **Minimal Implementation**:
  1. Add `"CAN_CHOOSE_POWER"` and `"HAS_WEAKNESS"` to `schemas/relation.schema.json` `type.enum`.
  2. Create `schemas/relation-collection.schema.json`.
  3. Implement `tests/agents/test_relation_schemas.py`.
- **GREEN Command**:
  `pytest tests/agents/test_relation_schemas.py -v`
- **Expected GREEN**:
  `7 passed in tests/agents/test_relation_schemas.py`
- **Regression Command**:
  `pytest tests/agents/test_contracts.py -v`
- **Commit**:
  `feat(schemas): add relation-collection schema and update relation predicates`

---

### Task C: Unresolved Relation Contracts
- **Files**:
  - `schemas/unresolved-relation.schema.json` [NEW]
  - `schemas/unresolved-relation-collection.schema.json` [NEW]
  - `tests/agents/test_unresolved_relation_schemas.py` [NEW]
- **Interfaces**:
  - `schemas/unresolved-relation.schema.json`:
    Draft 2020-12 schema, `type: "object"`, `additionalProperties: false`.
    Required: `["sourceEntityId", "candidateRelationType", "rawReferenceText", "sourcePage", "sourceParagraph", "reason", "status"]`.
    `status` enum: `["UNRESOLVED_PENDING_CROSS_BOOK_LINK", "UNRESOLVED_AMBIGUOUS_NAME", "UNRESOLVED_MISSING_TARGET"]`.
  - `schemas/unresolved-relation-collection.schema.json`:
    `type: "array"`, `items: { "$ref": "unresolved-relation.schema.json" }`, `uniqueItems: true`.
- **Tests**:
  - `tests/agents/test_unresolved_relation_schemas.py::test_unresolved_relation_valid_item`
  - `tests/agents/test_unresolved_relation_schemas.py::test_unresolved_relation_missing_evidence_rejected`
  - `tests/agents/test_unresolved_relation_schemas.py::test_unresolved_relation_missing_source_id_rejected`
  - `tests/agents/test_unresolved_relation_schemas.py::test_unresolved_relation_collection_valid`
  - `tests/agents/test_unresolved_relation_schemas.py::test_unresolved_relation_collection_rejects_invalid_item`
- **RED Command**:
  `pytest tests/agents/test_unresolved_relation_schemas.py -v`
- **Expected RED Reason**:
  `FileNotFoundError: schemas/unresolved-relation.schema.json does not exist.`
- **Minimal Implementation**:
  1. Create `schemas/unresolved-relation.schema.json`.
  2. Create `schemas/unresolved-relation-collection.schema.json`.
  3. Implement `tests/agents/test_unresolved_relation_schemas.py`.
- **GREEN Command**:
  `pytest tests/agents/test_unresolved_relation_schemas.py -v`
- **Expected GREEN**:
  `5 passed in tests/agents/test_unresolved_relation_schemas.py`
- **Regression Command**:
  `pytest tests/agents/test_relation_schemas.py tests/agents/test_unresolved_relation_schemas.py -v`
- **Commit**:
  `feat(schemas): introduce unresolved relation item and collection contracts`

---

### Task D: Relations v2 Version Binding
- **Files**:
  - `schemas/context-pack.schema.json` [MODIFY]
  - `schemas/execution-request.schema.json` [MODIFY]
  - `scripts/agents/context_pack_builder.py` [MODIFY]
  - `scripts/agents/execution_request_builder.py` [MODIFY]
  - `tests/agents/test_relation_version_binding.py` [NEW]
- **Interfaces**:
  - Property `relationOntologyVersion`: string, enum `["relations-v1", "relations-v2"]` in `context-pack.schema.json` and `execution-request.schema.json`.
  - `ContextPackBuilder.build(..., relation_ontology_version="relations-v2")`:
    If `stage == "relations"`, validates that `relationOntologyVersion` is set to `"relations-v2"`.
  - `ExecutionRequestBuilder.build_request(..., relation_ontology_version="relations-v2")`:
    If `targetStage == "relations"`, mandates `relation_ontology_version == "relations-v2"`. Rejects `"relations-v1"` with `ExecutionRequestBuilderError`.
- **Tests**:
  - `tests/agents/test_relation_version_binding.py::test_relations_stage_requires_v2_for_new_execution`
  - `tests/agents/test_relation_version_binding.py::test_relations_stage_rejects_v1_for_new_execution`
  - `tests/agents/test_relation_version_binding.py::test_non_relations_stage_ignores_relation_ontology_version`
- **RED Command**:
  `pytest tests/agents/test_relation_version_binding.py -v`
- **Expected RED Reason**:
  `ExecutionRequestBuilder does not accept relation_ontology_version parameter.`
- **Minimal Implementation**:
  1. Add `relationOntologyVersion` to `schemas/context-pack.schema.json` and `schemas/execution-request.schema.json`.
  2. Update `ContextPackBuilder.build()` to accept and validate `relation_ontology_version`.
  3. Update `ExecutionRequestBuilder.build_request()` to enforce `relation_ontology_version == "relations-v2"` for stage `relations`.
  4. Implement `tests/agents/test_relation_version_binding.py`.
- **GREEN Command**:
  `pytest tests/agents/test_relation_version_binding.py -v`
- **Expected GREEN**:
  `3 passed in tests/agents/test_relation_version_binding.py`
- **Regression Command**:
  `pytest tests/agents/test_context_pack_builder.py tests/agents/test_execution_contracts.py -v`
- **Commit**:
  `feat(agents): enforce relations-v2 ontology version binding in execution requests`

---

### Task E: Compatibility Matrix Contracts
- **Files**:
  - `schemas/relation-compatibility.schema.json` [NEW]
  - `schemas/relation-compatibility-v2.json` [NEW]
  - `docs/reference/relation-compatibility-v2.md` [NEW]
  - `tests/agents/test_relation_compatibility_schema.py` [NEW]
- **Interfaces**:
  - `schemas/relation-compatibility.schema.json`:
    Validates matrix schema: `version: "2.0.0"`, `ontologyVersion: "relations-v2"`, `rules` array of `(relationType, allowedSourceCategories, allowedTargetCategories, allowedTargetSubtypes, semanticMeaning)`.
  - `schemas/relation-compatibility-v2.json`:
    Machine-readable canonical authority containing all approved triplets.
  - `docs/reference/relation-compatibility-v2.md`:
    Explanatory markdown documentation declaring: `machine-readable JSON = canonical authority`, `markdown = explanatory only`.
- **Tests**:
  - `tests/agents/test_relation_compatibility_schema.py::test_compatibility_matrix_self_validates`
  - `tests/agents/test_relation_compatibility_schema.py::test_compatibility_matrix_contains_all_canonical_predicates`
  - `tests/agents/test_relation_compatibility_schema.py::test_compatibility_matrix_uses_valid_entity_categories`
- **RED Command**:
  `pytest tests/agents/test_relation_compatibility_schema.py -v`
- **Expected RED Reason**:
  `FileNotFoundError: schemas/relation-compatibility-v2.json does not exist.`
- **Minimal Implementation**:
  1. Create `schemas/relation-compatibility.schema.json`.
  2. Create `schemas/relation-compatibility-v2.json` with all valid triplets derived from `entity.schema.json` categories.
  3. Create `docs/reference/relation-compatibility-v2.md` referencing the canonical JSON.
  4. Implement `tests/agents/test_relation_compatibility_schema.py`.
- **GREEN Command**:
  `pytest tests/agents/test_relation_compatibility_schema.py -v`
- **Expected GREEN**:
  `3 passed in tests/agents/test_relation_compatibility_schema.py`
- **Regression Command**:
  `pytest tests/agents/test_contracts.py -v`
- **Commit**:
  `feat(schemas): establish machine-readable relations compatibility matrix v2`

---

### Task F: Compatibility Matrix Loader/Validator
- **Files**:
  - `scripts/agents/relation_compatibility.py` [NEW]
  - `tests/agents/test_relation_compatibility_validator.py` [NEW]
- **Interfaces**:
  - Class `RelationCompatibilityValidator`:
    - `__init__(self, matrix_path: Path | None = None)`
    - `validate_relation(self, relation: dict[str, Any], source_entity: dict[str, Any], target_entity: dict[str, Any]) -> CompatibilityVerdict`
    - `validate_relation_item(self, relation: dict[str, Any], entities_by_id: dict[str, dict[str, Any]]) -> CompatibilityVerdict`
  - Dataclass `CompatibilityVerdict(frozen=True)`:
    - `allowed: bool`
    - `code: str` (`"COMPATIBLE"`, `"ERR_UNKNOWN_PREDICATE"`, `"ERR_INCOMPATIBLE_CATEGORIES"`, `"ERR_INCOMPATIBLE_SUBTYPE"`, `"ERR_SOURCE_NOT_FOUND"`, `"ERR_TARGET_NOT_FOUND"`)
    - `reasons: tuple[str, ...]`
- **Tests**:
  - `tests/agents/test_relation_compatibility_validator.py::test_can_choose_power_compatible`
  - `tests/agents/test_relation_compatibility_validator.py::test_has_power_compatible`
  - `tests/agents/test_relation_compatibility_validator.py::test_has_weakness_compatible`
  - `tests/agents/test_relation_compatibility_validator.py::test_has_weakness_with_wrong_subtype_rejected`
  - `tests/agents/test_relation_compatibility_validator.py::test_unknown_relation_type_rejected_fail_closed`
  - `tests/agents/test_relation_compatibility_validator.py::test_missing_source_or_target_rejected`
- **RED Command**:
  `pytest tests/agents/test_relation_compatibility_validator.py -v`
- **Expected RED Reason**:
  `ModuleNotFoundError: No module named 'scripts.agents.relation_compatibility'`
- **Minimal Implementation**:
  1. Implement `scripts/agents/relation_compatibility.py` loading `schemas/relation-compatibility-v2.json` and checking triplets fail-closed.
  2. Implement `tests/agents/test_relation_compatibility_validator.py`.
- **GREEN Command**:
  `pytest tests/agents/test_relation_compatibility_validator.py -v`
- **Expected GREEN**:
  `6 passed in tests/agents/test_relation_compatibility_validator.py`
- **Regression Command**:
  `pytest tests/agents/test_relation_compatibility_schema.py tests/agents/test_relation_compatibility_validator.py -v`
- **Commit**:
  `feat(agents): implement deterministic RelationCompatibilityValidator`

---

### Task G: Integrate Semantic Validation (QA + GateEngine)
- **Files**:
  - `scripts/agents/pilot_qa_validator.py` [MODIFY]
  - `scripts/agents/gate_engine.py` [MODIFY]
  - `tests/agents/test_pilot_qa_validator.py` [MODIFY]
  - `tests/agents/test_gate_engine.py` [MODIFY]
- **Interfaces**:
  - In `PilotQAValidator.validate_dataset(workspace_root, book_id, expected_pages)`:
    - Integrates `RelationCompatibilityValidator`. For each relation in `relations.json`, checks `validator.validate_relation_item(rel, entities_by_id)`. Appends error on incompatibility.
    - Audits `unresolved-relations.json` (if present) against `unresolved-relation-collection.schema.json`. Confirms target does not point to local known entities.
  - In `GateEngine`:
    - Relational gate consumes `RelationCompatibilityValidator` to evaluate stage completion without duplicate if-trees.
- **Tests**:
  - `tests/agents/test_pilot_qa_validator.py::test_qa_validator_accepts_compatible_v2_relations`
  - `tests/agents/test_pilot_qa_validator.py::test_qa_validator_rejects_incompatible_relation_pair`
  - `tests/agents/test_pilot_qa_validator.py::test_qa_validator_validates_unresolved_relations_file`
  - `tests/agents/test_gate_engine.py::test_gate_engine_evaluates_relation_compatibility`
- **RED Command**:
  `pytest tests/agents/test_pilot_qa_validator.py -k "compatible_v2" -v`
- **Expected RED Reason**:
  `QA validator does not reject incompatible relation category pairs.`
- **Minimal Implementation**:
  1. Integrate `RelationCompatibilityValidator` into `PilotQAValidator.validate_dataset()`.
  2. Integrate unresolved relations file schema validation into `PilotQAValidator`.
  3. Integrate compatibility validation into `GateEngine.evaluate_stage_completion()`.
  4. Update tests in `tests/agents/test_pilot_qa_validator.py` and `tests/agents/test_gate_engine.py`.
- **GREEN Command**:
  `pytest tests/agents/test_pilot_qa_validator.py tests/agents/test_gate_engine.py -v`
- **Expected GREEN**:
  `All tests passed in test_pilot_qa_validator.py and test_gate_engine.py`
- **Regression Command**:
  `pytest tests/agents/ -v`
- **Commit**:
  `feat(qa): integrate semantic compatibility and unresolved relation validation into QA gates`

---

### Task H: ExecutionResultValidator Collection Regression
- **Files**:
  - `scripts/agents/contracts.py` [MODIFY]
  - `scripts/agents/execution_validator.py` [MODIFY]
  - `tests/agents/test_contracts.py` [MODIFY]
  - `tests/agents/test_execution_validator.py` [MODIFY]
- **Interfaces**:
  - In `scripts/agents/contracts.py`:
    - `validate_payload(schema_name: str, payload: Any) -> None`:
      Loads schema. Inspects `schema.get("type")`. If `schema["type"] == "array"`, validates `isinstance(payload, list)`. If `schema["type"] == "object"`, validates `isinstance(payload, dict)`.
      Constructs `referencing.Registry` from all schemas in `SCHEMAS_DIR` so that `$ref: "relation.schema.json"` resolves locally without network access.
  - In `scripts/agents/execution_validator.py`:
    - Lines 120-140: passes `parsed_artifact` (dict or list) to `validate_payload(output_schema_name, parsed_artifact)` without assuming dict.
- **Tests**:
  - `tests/agents/test_execution_validator.py::test_regression_attempt_1_item_schema_rejects_array_with_error`
  - `tests/agents/test_execution_validator.py::test_regression_attempt_1_collection_schema_accepts_array`
- **RED Command**:
  `pytest tests/agents/test_execution_validator.py -k "test_regression_attempt_1" -v`
- **Expected RED Reason**:
  `ContractValidationError: Payload to validate against 'relation-collection.schema.json' must be a dict, got list.`
- **Minimal Implementation**:
  1. Update `scripts/agents/contracts.py` `validate_payload` to allow list payloads when schema `type == "array"` and wire `referencing.Registry`.
  2. Update `tests/agents/test_contracts.py` to support array schemas in `SCHEMAS`.
  3. Add regression tests to `tests/agents/test_execution_validator.py`.
- **GREEN Command**:
  `pytest tests/agents/test_execution_validator.py -k "test_regression_attempt_1" -v`
- **Expected GREEN**:
  `2 passed in tests/agents/test_execution_validator.py`
- **Regression Command**:
  `pytest tests/agents/test_contracts.py tests/agents/test_execution_validator.py -v`
- **Commit**:
  `fix(contracts): support array collection schemas in validate_payload and resolve regression`

---

### Task I: Relations ExecutionRequest / OutputContract Binding
- **Files**:
  - `scripts/agents/prepare_pilot_job.py` [MODIFY]
  - `tests/agents/test_prepare_pilot_job.py` [MODIFY]
- **Interfaces**:
  - In `scripts/agents/prepare_pilot_job.py`:
    - For `targetStage == "relations"`:
      - `outputSchemaName = "relation-collection.schema.json"`
      - `contextPack["outputContract"] = "schemas/relation-collection.schema.json"`
      - `allowedWriteScope = ["data/entities/relations.json", "data/entities/unresolved-relations.json"]`
      - `relationOntologyVersion = "relations-v2"`
- **Tests**:
  - `tests/agents/test_prepare_pilot_job.py::test_prepare_relations_job_sets_collection_schema_and_write_scope`
- **RED Command**:
  `pytest tests/agents/test_prepare_pilot_job.py -k "test_prepare_relations_job" -v`
- **Expected RED Reason**:
  `AssertionError: outputSchemaName is 'relation.schema.json', expected 'relation-collection.schema.json'.`
- **Minimal Implementation**:
  1. Update `prepare_pilot_job.py` to configure `outputSchemaName = "relation-collection.schema.json"` and `allowedWriteScope` for the `relations` stage.
  2. Implement test in `tests/agents/test_prepare_pilot_job.py`.
- **GREEN Command**:
  `pytest tests/agents/test_prepare_pilot_job.py -k "test_prepare_relations_job" -v`
- **Expected GREEN**:
  `PASSED tests/agents/test_prepare_pilot_job.py::test_prepare_relations_job_sets_collection_schema_and_write_scope`
- **Regression Command**:
  `pytest tests/agents/test_prepare_pilot_job.py -v`
- **Commit**:
  `feat(pilot): bind relation-collection schema and write scope in relations execution requests`

---

### Task J: Synthetic Relations E2E
- **Files**:
  - `tests/agents/test_pilot_pipeline_e2e.py` [MODIFY]
- **Interfaces**:
  - Test functions in `tests/agents/test_pilot_pipeline_e2e.py`:
    - `test_full_pilot_pipeline_relations_stage_success(hermetic_pipeline_env)`:
      Uses synthetic entities, constructs Relations ExecutionRequest V2, exports execution bundle, simulates result bundle with 1 `HAS_POWER`, 1 `CAN_CHOOSE_POWER`, 1 `HAS_WEAKNESS`, 1 unresolved reference in `unresolved-relations.json`. Verifies `ExecutionResultValidator` returns `ACCEPT`, Pilot QA passes, preview projects correctly.
    - `test_full_pilot_pipeline_relations_stage_fail_closed(hermetic_pipeline_env)`:
      Simulates result bundle with invalid triplet or dangling reference. Verifies fail-closed rejection (`BLOCKED` or QA error).
    - **Isolation Rule**: Zero real content from *Animalidade* is used.
- **Tests**:
  - `tests/agents/test_pilot_pipeline_e2e.py::test_full_pilot_pipeline_relations_stage_success`
  - `tests/agents/test_pilot_pipeline_e2e.py::test_full_pilot_pipeline_relations_stage_fail_closed`
- **RED Command**:
  `pytest tests/agents/test_pilot_pipeline_e2e.py -k "relations_stage" -v`
- **Expected RED Reason**:
  `NameError: test_full_pilot_pipeline_relations_stage_success does not exist.`
- **Minimal Implementation**:
  1. Add both tests to `tests/agents/test_pilot_pipeline_e2e.py` using isolated synthetic fixtures.
- **GREEN Command**:
  `pytest tests/agents/test_pilot_pipeline_e2e.py -k "relations_stage" -v`
- **Expected GREEN**:
  `2 passed in tests/agents/test_pilot_pipeline_e2e.py`
- **Regression Command**:
  `pytest tests/agents/test_pilot_pipeline_e2e.py -v`
- **Commit**:
  `test(pilot): add synthetic end-to-end pipeline test for relations v2 stage`

---

### Task K: Full Relations v2 Regression Verification
- **Files**: None (Verification Gate)
- **Interfaces**:
  Execute full automated test baseline across the repository:
  1. `pytest tests/agents/ -v`
  2. `pytest tests/ -v`
  3. `python -m py_compile scripts/agents/*.py`
  4. `node --check docs/assets/app.js`
  5. `git status --short` (confirm main worktree is clean, zero drift)
- **RED Command**:
  N/A (Verification task)
- **GREEN Command**:
  `pytest tests/agents/ -v`
- **Expected GREEN**:
  `All test suites in tests/agents/ pass with 100% success.`
- **Commit**:
  `chore: verify full relations v2 regression test baseline`

---

### Task L: Historical HAS_POWER AUDIT-ONLY
- **Files**:
  - `scripts/agents/historical_relations_auditor.py` [NEW]
  - `tests/agents/test_historical_relations_auditor.py` [NEW]
- **Interfaces**:
  - Class `HistoricalRelationsAuditor`:
    - `__init__(self, data_root: Path)`
    - `audit_relations(self, relations: list[dict[str, Any]], entities_by_id: dict[str, Any]) -> AuditReport`
    - Classification taxonomy:
      - `CONFIRMED_ACTUAL_POSSESSION`: source evidence confirms direct active possession.
      - `CONFIRMED_SELECTABLE_OPTION`: source evidence demonstrates menu of options, point-buy costs, or selectable lists.
      - `AMBIGUOUS`: text evidence does not clearly distinguish possession from option.
      - `INVALID_OR_UNSUPPORTED`: dangling IDs or schema violations.
  - Dataclass `AuditReport`:
    - `total_relations: int`
    - `classified_counts: dict[str, int]`
    - `records: list[AuditRecord]`
    - `sha256_hash: str`
  - Invariant: Read-only. Never mutates disk data.
- **Tests**:
  - `tests/agents/test_historical_relations_auditor.py::test_auditor_classifies_confirmed_possession`
  - `tests/agents/test_historical_relations_auditor.py::test_auditor_classifies_selectable_option`
  - `tests/agents/test_historical_relations_auditor.py::test_auditor_flags_ambiguous_without_mutating`
- **RED Command**:
  `pytest tests/agents/test_historical_relations_auditor.py -v`
- **Expected RED Reason**:
  `ModuleNotFoundError: No module named 'scripts.agents.historical_relations_auditor'`
- **Minimal Implementation**:
  1. Implement `scripts/agents/historical_relations_auditor.py`.
  2. Implement `tests/agents/test_historical_relations_auditor.py`.
- **GREEN Command**:
  `pytest tests/agents/test_historical_relations_auditor.py -v`
- **Expected GREEN**:
  `3 passed in tests/agents/test_historical_relations_auditor.py`
- **Regression Command**:
  `pytest tests/agents/ -v`
- **Commit**:
  `feat(audit): implement read-only HistoricalRelationsAuditor`

---

### Task M: Execute AUDIT ONLY + HUMAN STOP
- **Files**:
  - `docs/reports/historical-relations-v2-audit-report.json` [NEW]
- **Action**:
  1. Run `python -m scripts.agents.historical_relations_auditor` across historical tracked relations datasets.
  2. Write output to `docs/reports/historical-relations-v2-audit-report.json`.
  3. Compute and record SHA-256 hash of the report.
  4. Commit report.

```
================================================================================
>>> HARD STOP 1: HUMAN REVIEW REQUIRED <<<
DO NOT PROCEED TO TASK N / TASK O WITHOUT EXPLICIT OPERATOR APPROVAL.
Operator must inspect docs/reports/historical-relations-v2-audit-report.json,
verify classified records, and sign off via a ReviewDecision artifact.
================================================================================
```

---

### Task N: Migration Apply Engine
- **Files**:
  - `scripts/agents/historical_relations_migrator.py` [NEW]
  - `tests/agents/test_historical_relations_migrator.py` [NEW]
- **Interfaces**:
  - Class `HistoricalRelationsMigrator`:
    - `__init__(self, approval_decision_path: Path, audit_report_path: Path)`
    - `apply_migration(self, target_relations_file: Path, dry_run: bool = True) -> MigrationResult`
    - Security gates:
      - Validates that `approval_decision` exists and has `status == "APPROVED"`.
      - Validates that `audit_report` SHA-256 matches hash cited in approval decision.
      - Blocks if any unapproved transformation or `AMBIGUOUS` record is present.
      - Converts approved `CONFIRMED_SELECTABLE_OPTION` records to `CAN_CHOOSE_POWER`.
      - Keeps `CONFIRMED_ACTUAL_POSSESSION` as `HAS_POWER`.
      - Atomic write with backup journal.
- **Tests**:
  - `tests/agents/test_historical_relations_migrator.py::test_migrator_blocks_without_human_approval`
  - `tests/agents/test_historical_relations_migrator.py::test_migrator_blocks_on_hash_mismatch`
  - `tests/agents/test_historical_relations_migrator.py::test_migrator_applies_approved_conversions_atomically`
- **RED Command**:
  `pytest tests/agents/test_historical_relations_migrator.py -v`
- **Expected RED Reason**:
  `ModuleNotFoundError: No module named 'scripts.agents.historical_relations_migrator'`
- **Minimal Implementation**:
  1. Implement `scripts/agents/historical_relations_migrator.py`.
  2. Implement `tests/agents/test_historical_relations_migrator.py`.
- **GREEN Command**:
  `pytest tests/agents/test_historical_relations_migrator.py -v`
- **Expected GREEN**:
  `3 passed in tests/agents/test_historical_relations_migrator.py`
- **Regression Command**:
  `pytest tests/agents/test_historical_relations_auditor.py tests/agents/test_historical_relations_migrator.py -v`
- **Commit**:
  `feat(migration): implement fail-closed HistoricalRelationsMigrator`

---

### Task O: MIGRATION APPLY HUMAN-GATED OPERATION
- **Precondition**:
  Explicit human approval decision exists, verifying the audit report SHA-256 hash.
- **Action**:
  1. Execute `HistoricalRelationsMigrator.apply_migration(dry_run=False)`.
  2. Validate resulting files against `relation-collection.schema.json` and `relation-compatibility-v2.json`.
  3. Record migration execution report in `docs/reports/historical-relations-migration-result.json`.
- **Commit**:
  `chore(migration): apply approved relations v2 migration transformations`

---

### Task P: Post-Migration Global Verification
- **Files**: None (Verification Gate)
- **Interfaces**:
  1. Verify zero unapproved `HAS_POWER` records remaining in migrated datasets.
  2. Verify all relations validate against `relation-collection.schema.json` and `relation-compatibility-v2.json`.
  3. Run full test suite: `pytest tests/`
  4. Run data validation: `python scripts/validate_data.py` (if present).
  5. Verify clean git status: `git status --short`.
- **GREEN Command**:
  `pytest tests/ -v`
- **Expected GREEN**:
  `All tests pass across repository.`
- **Commit**:
  `chore: verify post-migration global repository baseline`

---

### Task Q: Relations Attempt 1 Historical State
- **Files**: None (Audit Record Verification)
- **Action**:
  1. Verify `RB-ANIM-RELATIONS-att1-8317e31e` remains completely unmodified in runtime audit store.
  2. Confirm manifest SHA-256 remains `abd2f243d4936101d229ef96cdfdc044f7d75729dc67dfdc18675178dcc16ad2`.
  3. Ensure attempt status in audit store is recorded as `NEEDS_REWORK` under `relations-v1`.
- **Regression Command**:
  `python -c "from scripts.agents.pilot_audit_store import PilotAuditStore; print(PilotAuditStore().get_attempt('animalidade', 1)['state'])"`
- **Commit**:
  `docs(audit): confirm attempt 1 historical preservation as immutable needs_rework`

---

### Task R: Prepare Animalidade Relations Attempt 2
- **Files**:
  - Runtime request: `REQ-ANIM-001-RELATIONS-02`
  - Runtime context pack: `CTX-REQ-ANIM-001-RELATIONS-02`
  - Runtime execution bundle: `EB-ANIM-RELATIONS-att2-*`
- **Prerequisites**:
  - Tasks A through Q completed and verified.
  - V2 schemas and validator in place.
  - Migration complete and verified.
- **Action**:
  1. Build new ExecutionRequest `REQ-ANIM-001-RELATIONS-02` with:
     - `bookId = "animalidade"`
     - `targetStage = "relations"`
     - `relationOntologyVersion = "relations-v2"`
     - `outputSchemaName = "relation-collection.schema.json"`
     - `contextPack.outputContract = "schemas/relation-collection.schema.json"`
     - `allowedWriteScope = ["data/entities/relations.json", "data/entities/unresolved-relations.json"]`
  2. Export Execution Bundle `EB-ANIM-RELATIONS-att2-*`.
  3. Seal bundle as read-only.
- **Commit**:
  `chore(pilot): prepare and seal animalidade relations attempt 2 execution bundle`

---

### Task S: Relations Attempt 2 Execution / Human Boundary
- **Action**:
  1. Execute Relations Agent in isolated runtime workspace (`.daemon_runtime/workspaces/pilot/animalidade/`).
  2. Expected semantic extraction:
     - `HAS_POWER`: 0 relations.
     - `CAN_CHOOSE_POWER`: 107 relations.
     - `HAS_WEAKNESS`: explicit innate weaknesses.
     - `unresolved-relations.json`: 1 record (*Rapidez* in *Garras de Sharikan*).
  3. Package Result Bundle `RB-ANIM-RELATIONS-att2-*`.
  4. Run `ExecutionResultValidator.validate()`.

```
================================================================================
>>> HARD STOP 2: HUMAN REVIEW REQUIRED <<<
DO NOT PROCEED TO FRONTEND STAGE OR PUBLICATION.
Operator must inspect Result Bundle RB-ANIM-RELATIONS-att2-*, verify
CAN_CHOOSE_POWER assignments, confirm zero HAS_POWER, confirm unresolved Rapidez,
and issue a formal ReviewDecision before any frontend integration.
================================================================================
```

---

## Spec Requirement Coverage Mapping

| Spec Requirement (from `2026-09-09-relations-v2-ontology-contract-design.md`) | Plan Task |
|---|---|
| 1.1 Technical Contract Gap Resolution (`relation-collection.schema.json`) | Task B, Task H, Task I |
| 1.2 Semantic Ontology Gap Resolution (`actual possession != selectable option`) | Task A, Task E, Task F, Task S |
| 2.1 Formalize Collection Contract | Task B, Task H |
| 2.1 Canonical Compatibility Authority (`schemas/relation-compatibility-v2.json`) | Task E, Task F |
| 2.1 Refine `HAS_POWER` (actual possession) | Task A, Task E, Task L, Task S |
| 2.1 Introduce `CAN_CHOOSE_POWER` (selectable build/configuration option) | Task A, Task B, Task E, Task S |
| 2.1 Introduce `HAS_WEAKNESS` (innate limitation / vulnerability) | Task A, Task B, Task E, Task S |
| 2.1 Reject `CAN_CHOOSE_WEAKNESS` under YAGNI | Task A, Task E |
| 2.1 Isolate Unresolved References in `unresolved-relations.json` | Task C, Task G, Task S |
| 2.1 Two-Phase Migration (Audit-Only -> Human Gate -> Apply) | Task L, Task M, Task N, Task O |
| 2.1 Preserve Result Bundle Attempt 1 Immutability (`NEEDS_REWORK`) | Task Q |
| 2.1 Restricted Pilot Content Isolation (`UNKNOWN`, `NOT_PUBLIC`, `LOCAL_RESTRICTED`) | Global Constraints, Task J, Task S |
| 4.0 Semantic Versioning Model (`relations-v1` read-only, `relations-v2` mandatory) | Task A, Task D |
| 5.3 Explicit Schema Binding in Validator (no heuristics / no guessing) | Task H, Task I |
| 6.2 Declarative Compatibility Matrix Structure & Types | Task E, Task F |
| 7.2 Fail-Closed Semantic Validation | Task F, Task G, Task J |
| 11.4 Mandatory Regression Test for Attempt 1 Bug | Task H |
| 11.5 Synthetic E2E Pipeline Test Expansion | Task J |
| 12.1 Repository ADR Sequence (`verified next ADR = ADR-0004`) | Task A |
| 13.0 16-Step Design Implementation Sequence | Tasks A through S |
| 14.0 Version 2 Success Criteria Fulfillment | Task K, Task P, Task S |

**Uncovered Requirements**: 0.

---

## Type & Interface Consistency Review

- **Schema Names**:
  - `schemas/relation.schema.json` (Item contract)
  - `schemas/relation-collection.schema.json` (Collection contract)
  - `schemas/unresolved-relation.schema.json` (Unresolved item contract)
  - `schemas/unresolved-relation-collection.schema.json` (Unresolved collection contract)
  - `schemas/relation-compatibility.schema.json` (Compatibility schema)
  - `schemas/relation-compatibility-v2.json` (Canonical compatibility data matrix)
- **Classes**:
  - `ExecutionResultValidator` in `scripts/agents/execution_validator.py`
  - `WriteScopeValidator` in `scripts/agents/write_scope.py`
  - `ContextPackBuilder` in `scripts/agents/context_pack_builder.py`
  - `ExecutionRequestBuilder` in `scripts/agents/execution_request_builder.py`
  - `GateEngine` in `scripts/agents/gate_engine.py`
  - `PilotQAValidator` in `scripts/agents/pilot_qa_validator.py`
  - `RelationCompatibilityValidator` in `scripts/agents/relation_compatibility.py`
  - `HistoricalRelationsAuditor` in `scripts/agents/historical_relations_auditor.py`
  - `HistoricalRelationsMigrator` in `scripts/agents/historical_relations_migrator.py`
  - `LocalPreviewProjector` in `scripts/agents/preview_projector.py`
- **Relation Predicates**:
  - `HAS_POWER` (actual possession)
  - `CAN_CHOOSE_POWER` (selectable build/configuration option)
  - `HAS_WEAKNESS` (actual weakness possession)
- **Version Identifier**:
  - `relationOntologyVersion = "relations-v2"`
