from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class UnknownProfileError(KeyError):
    """Raised when an execution profile cannot be found in the registry."""
    pass


@dataclass(frozen=True)
class ExecutionProfile:
    """Immutable configuration for an execution profile."""
    profile_id: str
    provider: str  # "antigravity", "fake", "mock"
    model: str     # "gemini-3.7-high", "gemini-2.5-flash", "test-fixture"
    timeout_seconds: int = 300
    parameters: dict[str, Any] = field(default_factory=dict)


class ProfileRegistry:
    """Registry mapping profile_id strings to ExecutionProfile instances."""

    def __init__(self, profiles: dict[str, ExecutionProfile] | None = None) -> None:
        self._profiles: dict[str, ExecutionProfile] = {}
        if profiles:
            for prof in profiles.values():
                self.register(prof)

    def get_profile(self, profile_id: str) -> ExecutionProfile:
        if profile_id not in self._profiles:
            raise UnknownProfileError(f"Unknown execution profile: '{profile_id}'")
        return self._profiles[profile_id]

    def register(self, profile: ExecutionProfile) -> None:
        if not isinstance(profile, ExecutionProfile):
            raise TypeError(f"profile must be an ExecutionProfile instance, got {type(profile).__name__}")
        self._profiles[profile.profile_id] = profile

    def list_profiles(self) -> list[str]:
        return sorted(self._profiles.keys())


def get_default_registry() -> ProfileRegistry:
    """Returns the default ProfileRegistry configured with standard provider profiles."""
    registry = ProfileRegistry()
    registry.register(
        ExecutionProfile(
            profile_id="default-high",
            provider="antigravity",
            model="gemini-3.7-high",
            timeout_seconds=300,
            parameters={"thinkingLevel": "high"},
        )
    )
    registry.register(
        ExecutionProfile(
            profile_id="default-fast",
            provider="antigravity",
            model="gemini-2.5-flash",
            timeout_seconds=120,
            parameters={"thinkingLevel": "medium"},
        )
    )
    registry.register(
        ExecutionProfile(
            profile_id="offline-test",
            provider="fake",
            model="test-fixture",
            timeout_seconds=30,
            parameters={},
        )
    )
    return registry
