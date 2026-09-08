from __future__ import annotations

import copy
import pytest
from dataclasses import FrozenInstanceError

from scripts.agents.context_materializer import MaterializedContext
from scripts.agents.prompt_renderer import (
    PromptRenderer,
    PromptRendererError,
    RenderedPrompt,
)


@pytest.fixture
def sample_execution_request():
    return {
        "schemaVersion": "2.0",
        "requestId": "REQ-JOB-TREVAS-001-EXTRACTION",
        "jobId": "JOB-TREVAS-001",
        "bookId": "trevas-3-0",
        "targetStage": "extraction",
        "assignedAgent": "extraction-agent",
        "allowedWriteScope": [
            "data/text/trevas-3-0.txt",
            "data/handoffs/handoff-extraction.json",
        ],
        "executionProfile": "default-high",
        "contextPack": {
            "schemaVersion": "1.0",
            "contextPackId": "CTX-TREVAS-EXTRACTION-001",
            "jobId": "JOB-TREVAS-001",
            "agent": "extraction-agent",
            "stage": "extraction",
            "mandatory": ["docs/architecture/constitution.md"],
            "domain": ["docs/context/domain/taxonomy.md"],
            "bookContext": ["coordination/books/trevas.md"],
            "jobContext": ["coordination/queue/codex.json"],
            "handoffContext": [],
            "task": {
                "type": "extract_raw_text",
                "scope": {"bookId": "trevas-3-0", "pages": [1, 2, 3]},
                "parameters": {"strictCoverage": True},
            },
            "outputContract": "schemas/agent-handoff.schema.json",
        },
        "taskInstruction": "Extract and clean text from pages 1-3.",
        "outputSchemaName": "agent-handoff.schema.json",
        "timeoutSeconds": 300,
        "metadata": {"test": True},
    }


@pytest.fixture
def sample_materialized_context():
    return MaterializedContext(
        layers={
            "mandatory": (
                {
                    "path": "docs/architecture/constitution.md",
                    "content": "# Constitution\n- Non-invention: Never invent rules.\n- Provenance: Always cite source and page.",
                },
            ),
            "domain": (
                {
                    "path": "docs/context/domain/taxonomy.md",
                    "content": "# Taxonomy\nCanonical definitions.",
                },
            ),
            "bookContext": (
                {
                    "path": "coordination/books/trevas.md",
                    "content": "# Book Context\nTrevas 3.0 metadata.",
                },
            ),
            "jobContext": (
                {
                    "path": "coordination/queue/codex.json",
                    "content": '{"job": "active"}',
                },
            ),
            "handoffContext": (),
            "outputContract": (
                {
                    "path": "schemas/agent-handoff.schema.json",
                    "content": '{"title": "Agent Handoff Schema"}',
                },
            ),
        },
        metadata={
            "contextPackId": "CTX-TREVAS-EXTRACTION-001",
            "jobId": "JOB-TREVAS-001",
            "agent": "extraction-agent",
            "stage": "extraction",
            "schemaVersion": "1.0",
            "task": {
                "type": "extract_raw_text",
                "scope": {"bookId": "trevas-3-0", "pages": [1, 2, 3]},
                "parameters": {"strictCoverage": True},
            },
        },
    )


def test_render_valid_prompt(sample_execution_request, sample_materialized_context):
    renderer = PromptRenderer()
    rendered = renderer.render(
        request=sample_execution_request,
        materialized=sample_materialized_context,
        agent_contract_text="# Extraction Agent Contract\nSpecialized in clean text extraction.",
    )

    assert isinstance(rendered, RenderedPrompt)
    assert isinstance(rendered.system_instruction, str)
    assert isinstance(rendered.user_content, str)
    assert isinstance(rendered.metadata, dict)

    # Check system instruction content
    assert "Extraction Agent Contract" in rendered.system_instruction
    assert "Constitution" in rendered.system_instruction
    assert "Non-invention" in rendered.system_instruction

    # Check user content content
    assert "Extract and clean text from pages 1-3." in rendered.user_content
    assert "Taxonomy" in rendered.user_content
    assert "Book Context" in rendered.user_content
    assert "data/text/trevas-3-0.txt" in rendered.user_content
    assert "Agent Handoff Schema" in rendered.user_content

    # Check metadata
    assert rendered.metadata["requestId"] == "REQ-JOB-TREVAS-001-EXTRACTION"
    assert rendered.metadata["jobId"] == "JOB-TREVAS-001"
    assert rendered.metadata["agent"] == "extraction-agent"
    assert rendered.metadata["stage"] == "extraction"
    assert rendered.metadata["executionProfile"] == "default-high"


def test_render_determinism(sample_execution_request, sample_materialized_context):
    renderer = PromptRenderer()
    r1 = renderer.render(sample_execution_request, sample_materialized_context)
    r2 = renderer.render(sample_execution_request, sample_materialized_context)

    assert r1.system_instruction == r2.system_instruction
    assert r1.user_content == r2.user_content
    assert r1.metadata == r2.metadata


def test_render_immutability(sample_execution_request, sample_materialized_context):
    renderer = PromptRenderer()
    rendered = renderer.render(sample_execution_request, sample_materialized_context)

    with pytest.raises(FrozenInstanceError):
        rendered.system_instruction = "altered"

    with pytest.raises(FrozenInstanceError):
        rendered.user_content = "altered"


def test_render_invalid_request_raises(sample_materialized_context):
    renderer = PromptRenderer()
    with pytest.raises(PromptRendererError) as exc_info:
        renderer.render({"invalid": "request"}, sample_materialized_context)
    assert "validation" in str(exc_info.value).lower() or "schema" in str(exc_info.value).lower()


def test_render_invalid_materialized_raises(sample_execution_request):
    renderer = PromptRenderer()
    with pytest.raises(PromptRendererError):
        renderer.render(sample_execution_request, "not a MaterializedContext")  # type: ignore
