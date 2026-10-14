from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from scripts.agents.execution_profile import ExecutionProfile
from scripts.agents.prompt_renderer import RenderedPrompt


class ExecutionAdapterError(RuntimeError):
    """Raised when an execution adapter encounters a runtime, provider, or communication failure."""
    pass


@dataclass(frozen=True)
class RawExecutionResponse:
    """Immutable response payload returned by an ExecutionAdapter."""
    content: str
    status_code: str  # "OK", "TIMEOUT", "ERROR"
    duration_seconds: float
    raw_metadata: dict[str, Any] = field(default_factory=dict)


class ExecutionAdapter(ABC):
    """Abstract provider-neutral execution adapter interface."""

    @abstractmethod
    def execute(
        self,
        request: dict[str, Any],
        prompt: RenderedPrompt,
        profile: ExecutionProfile,
    ) -> RawExecutionResponse:
        """Execute the prompt against the designated provider/model."""
        pass


class FakeExecutionAdapter(ExecutionAdapter):
    """Deterministic, offline fake execution adapter for unit tests, fixtures, and CI."""

    def __init__(
        self,
        scripted_responses: dict[str, RawExecutionResponse] | None = None,
        default_response: RawExecutionResponse | None = None,
    ) -> None:
        self._scripted_responses = dict(scripted_responses) if scripted_responses else {}
        self._default_response = default_response or RawExecutionResponse(
            content="{}",
            status_code="OK",
            duration_seconds=0.01,
            raw_metadata={"provider": "fake"},
        )

    def execute(
        self,
        request: dict[str, Any],
        prompt: RenderedPrompt,
        profile: ExecutionProfile,
    ) -> RawExecutionResponse:
        req_id = request.get("requestId", "")
        if req_id in self._scripted_responses:
            return self._scripted_responses[req_id]
        return self._default_response
