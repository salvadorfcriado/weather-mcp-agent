"""Provider selection by env var (Strategy + Factory).

Adding a provider means registering one more adapter behind the `LLMProvider` port —
no change to the agent, gateway, or frontends (OCP). Anthropic ships here; further
providers (e.g. OpenAI) are documented in SOLUTION.md as the extension point.
"""

from __future__ import annotations

from weather_agent.config import ConfigError, Settings
from weather_agent.providers.anthropic_provider import AnthropicProvider
from weather_agent.providers.base import LLMProvider

_SUPPORTED = ("anthropic",)


def build_provider(settings: Settings) -> LLMProvider:
    provider = settings.llm_provider.strip().lower()

    if provider == "anthropic":
        if not settings.anthropic_api_key:
            raise ConfigError(
                "ANTHROPIC_API_KEY is not set. Add it to your environment or .env "
                "(see .env.example)."
            )
        return AnthropicProvider(api_key=settings.anthropic_api_key, model=settings.anthropic_model)

    raise ConfigError(
        f"Unsupported LLM_PROVIDER={settings.llm_provider!r}. "
        f"Supported providers: {', '.join(_SUPPORTED)}."
    )
