"""Application settings, loaded from the environment (no secrets in code).

Reads from process env and an optional `.env`. `.env.example` is the committed template.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigError(RuntimeError):
    """Raised when configuration is missing or invalid (fail fast, clear message)."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_provider: str = "anthropic"

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-4-5"

    agent_max_iterations: int = 8
    weather_cache_ttl_seconds: float = 600.0
    log_level: str = "INFO"
