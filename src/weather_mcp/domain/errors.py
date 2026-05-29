"""Typed domain errors raised by the weather service.

These are the vocabulary the server maps into graceful MCP tool results; they never
leak to the user or the LLM as stack traces.
"""

from __future__ import annotations


class WeatherError(Exception):
    """Base class for weather domain errors."""


class LocationNotFoundError(WeatherError):
    """Geocoding could not resolve the requested location."""

    def __init__(self, query: str) -> None:
        self.query = query
        super().__init__(f"location not found: {query!r}")


class UpstreamWeatherError(WeatherError):
    """An upstream Open-Meteo request failed (network, timeout, or bad status)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
