"""Entrypoint: build the cached clients → service → FastMCP server, run over stdio.

Configuration is read from the environment (the agent launches this as a subprocess and
passes the environment through). No LLM key is needed here — Open-Meteo is keyless.
"""

from __future__ import annotations

import os

import httpx

from weather_mcp.clients.cache import CachedGeocodingClient, CachedWeatherClient
from weather_mcp.clients.open_meteo import OpenMeteoGeocodingClient, OpenMeteoWeatherClient
from weather_mcp.server import build_server
from weather_mcp.service import WeatherService

_HTTP_TIMEOUT = 10.0


def build_weather_service(cache_ttl_seconds: float) -> WeatherService:
    """Compose the real Open-Meteo clients, wrapped in caching decorators."""
    http = httpx.AsyncClient(
        timeout=_HTTP_TIMEOUT,
        headers={"User-Agent": "weather-mcp-agent/0.1 (exercise)"},
    )
    geocoder = CachedGeocodingClient(OpenMeteoGeocodingClient(http))
    weather = CachedWeatherClient(OpenMeteoWeatherClient(http), ttl_seconds=cache_ttl_seconds)
    return WeatherService(geocoder, weather)


def main() -> None:
    cache_ttl = float(os.getenv("WEATHER_CACHE_TTL_SECONDS", "600"))
    service = build_weather_service(cache_ttl_seconds=cache_ttl)
    server = build_server(service)
    server.run()  # stdio transport by default


if __name__ == "__main__":
    main()
