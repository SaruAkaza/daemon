from __future__ import annotations

import pytest
from dataclasses import FrozenInstanceError

from scripts.agents.execution_adapter import (
    ExecutionAdapter,
    ExecutionAdapterError,
    FakeExecutionAdapter,
    RawExecutionResponse,
)
from scripts.agents.execution_profile import ExecutionProfile
from scripts.agents.prompt_renderer import RenderedPrompt


@pytest.fixture
def sample_request():
    return {
        "schemaVersion": "2.0",
        "requestId": "REQ-TREVAS-001-EXTRACTION",
        "jobId": "JOB-TREVAS-001",
        "bookId": "trevas-3-0",
        "targetStage": "extraction",
        "assignedAgent": "extraction-agent",
        "allowedWriteScope": ["data/text/trevas-3-0.txt"],
        "executionProfile": "offline-test",
        "contextPack": {
            "schemaVersion": "1.0",
            "contextPackId": "CTX-001",
            "jobId": "JOB-TREVAS-001",
            "agent": "extraction-agent",
            "stage": "extraction",
            "mandatory": [],
            "domain": [],
            "bookContext": [],
            "jobContext": [],
            "handoffContext": [],
            "task": {"type": "extract"},
            "outputContract": "schemas/agent-handoff.schema.json",
        },
        "taskInstruction": "Extract text",
        "outputSchemaName": "agent-handoff.schema.json",
    }


@pytest.fixture
def sample_prompt():
    return RenderedPrompt(
        system_instruction="System prompt",
        user_content="User prompt",
        metadata={"requestId": "REQ-TREVAS-001-EXTRACTION"},
    )


@pytest.fixture
def sample_profile():
    return ExecutionProfile(
        profile_id="offline-test",
        provider="fake",
        model="test-fixture",
    )


def test_fake_adapter_scripted_response(sample_request, sample_prompt, sample_profile):
    scripted = {
        "REQ-TREVAS-001-EXTRACTION": RawExecutionResponse(
            content='{"status": "pass"}',
            status_code="OK",
            duration_seconds=0.05,
            raw_metadata={"mocked": True},
        )
    }
    adapter = FakeExecutionAdapter(scripted_responses=scripted)

    response = adapter.execute(sample_request, sample_prompt, sample_profile)

    assert isinstance(response, RawExecutionResponse)
    assert response.content == '{"status": "pass"}'
    assert response.status_code == "OK"
    assert response.duration_seconds == 0.05
    assert response.raw_metadata == {"mocked": True}


def test_fake_adapter_default_response(sample_prompt, sample_profile):
    unmapped_request = {
        "requestId": "REQ-UNMAPPED-999",
        "jobId": "JOB-002",
        "targetStage": "editorial",
    }
    default_resp = RawExecutionResponse(
        content="Default content",
        status_code="OK",
        duration_seconds=0.01,
    )
    adapter = FakeExecutionAdapter(default_response=default_resp)

    response = adapter.execute(unmapped_request, sample_prompt, sample_profile)
    assert response.content == "Default content"
    assert response.status_code == "OK"


def test_fake_adapter_simulates_timeout_and_error(sample_prompt, sample_profile):
    timeout_req = {"requestId": "REQ-TIMEOUT"}
    error_req = {"requestId": "REQ-ERROR"}

    scripted = {
        "REQ-TIMEOUT": RawExecutionResponse(
            content="",
            status_code="TIMEOUT",
            duration_seconds=300.0,
        ),
        "REQ-ERROR": RawExecutionResponse(
            content="Provider unreachable",
            status_code="ERROR",
            duration_seconds=0.02,
        ),
    }
    adapter = FakeExecutionAdapter(scripted_responses=scripted)

    resp_timeout = adapter.execute(timeout_req, sample_prompt, sample_profile)
    assert resp_timeout.status_code == "TIMEOUT"

    resp_error = adapter.execute(error_req, sample_prompt, sample_profile)
    assert resp_error.status_code == "ERROR"


def test_raw_execution_response_immutability():
    resp = RawExecutionResponse(
        content="data",
        status_code="OK",
        duration_seconds=1.0,
    )
    with pytest.raises(FrozenInstanceError):
        resp.status_code = "ERROR"  # type: ignore


def test_abstract_execution_adapter_cannot_be_instantiated():
    with pytest.raises(TypeError):
        ExecutionAdapter()  # type: ignore
