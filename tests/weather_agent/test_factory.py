"""Tests for provider selection via the factory."""

from __future__ import annotations

import pytest

from weather_agent.config import ConfigError, Settings
from weather_agent.providers.anthropic_provider import AnthropicProvider
from weather_agent.providers.factory import build_provider


def _settings(**kwargs) -> Settings:
    # _env_file=None isolates the test from any local .env.
    return Settings(_env_file=None, **kwargs)


def test_builds_anthropic_provider_with_key() -> None:
    provider = build_provider(_settings(llm_provider="anthropic", anthropic_api_key="sk-test"))
    assert isinstance(provider, AnthropicProvider)


def test_missing_api_key_fails_fast() -> None:
    with pytest.raises(ConfigError) as exc:
        build_provider(_settings(llm_provider="anthropic", anthropic_api_key=""))
    assert "ANTHROPIC_API_KEY" in str(exc.value)


def test_unknown_provider_rejected_with_supported_list() -> None:
    with pytest.raises(ConfigError) as exc:
        build_provider(_settings(llm_provider="gemini", anthropic_api_key="x"))
    assert "anthropic" in str(exc.value).lower()


def test_provider_selection_is_case_insensitive() -> None:
    provider = build_provider(_settings(llm_provider="Anthropic", anthropic_api_key="sk-test"))
    assert isinstance(provider, AnthropicProvider)
