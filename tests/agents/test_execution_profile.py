from __future__ import annotations

import pytest
from dataclasses import FrozenInstanceError

from scripts.agents.execution_profile import (
    ExecutionProfile,
    ProfileRegistry,
    UnknownProfileError,
    get_default_registry,
)


def test_default_registry_contains_standard_profiles():
    registry = get_default_registry()
    profiles = registry.list_profiles()
    assert "default-high" in profiles
    assert "default-fast" in profiles
    assert "offline-test" in profiles

    high = registry.get_profile("default-high")
    assert high.profile_id == "default-high"
    assert high.provider in ("antigravity", "fake", "mock")
    assert high.model != ""

    offline = registry.get_profile("offline-test")
    assert offline.provider == "fake"


def test_unknown_profile_raises():
    registry = get_default_registry()
    with pytest.raises(UnknownProfileError):
        registry.get_profile("non-existent-profile")


def test_custom_profile_registration():
    registry = ProfileRegistry()
    assert registry.list_profiles() == []

    custom = ExecutionProfile(
        profile_id="custom-profile-1",
        provider="fake",
        model="custom-model-x",
        timeout_seconds=60,
        parameters={"temperature": 0.0},
    )
    registry.register(custom)

    retrieved = registry.get_profile("custom-profile-1")
    assert retrieved == custom
    assert retrieved.timeout_seconds == 60
    assert retrieved.parameters == {"temperature": 0.0}
    assert registry.list_profiles() == ["custom-profile-1"]


def test_profile_immutability():
    profile = ExecutionProfile(
        profile_id="test-immutability",
        provider="fake",
        model="test-model",
    )
    with pytest.raises(FrozenInstanceError):
        profile.provider = "other"  # type: ignore

    with pytest.raises(FrozenInstanceError):
        profile.model = "other"  # type: ignore


def test_register_invalid_profile_type():
    registry = ProfileRegistry()
    with pytest.raises(TypeError):
        registry.register("not an ExecutionProfile")  # type: ignore
