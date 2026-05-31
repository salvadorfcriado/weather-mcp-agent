"""FastMCP server wiring — the thin MCP transport adapter.

Holds no business logic: it registers `get_current_weather`, delegates to the
`WeatherService`, and maps typed domain errors into graceful MCP tool errors. The
tool's type hints + docstring generate the MCP input schema and description.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from weather_mcp.domain.errors import LocationNotFoundError, UpstreamWeatherError
from weather_mcp.domain.models import Units, WeatherReport
from weather_mcp.service import WeatherService


def _report_to_dict(report: WeatherReport) -> dict[str, Any]:
    return {
        "location": report.location.display_name,
        "temperature": report.temperature,
        "temperature_unit": report.temperature_unit,
        "wind_speed": report.wind_speed,
        "wind_speed_unit": report.wind_speed_unit,
        "conditions": report.description,
        "observed_at": report.observed_at,
    }


def build_server(
    service: WeatherService,
    *,
    lifespan: Callable[[FastMCP], AbstractAsyncContextManager[None]] | None = None,
) -> FastMCP:
    """Create a FastMCP server exposing the weather tool over the given service.

    An optional ``lifespan`` lets the caller manage resources (e.g. close the shared
    HTTP client) around the server's run.
    """
    mcp = FastMCP("weather", lifespan=lifespan)

    @mcp.tool()
    async def get_current_weather(location: str, units: Units = Units.METRIC) -> dict[str, Any]:
        """Get the CURRENT weather conditions for a named place.

        Use when the user asks about current weather, temperature, or wind for a city or
        place (e.g. "weather in London", "is it windy in Tokyo right now?"). Do NOT use
        for multi-day forecasts, historical weather, or weather alerts.

        Args:
            location: A human-readable place name, e.g. "London" or "New York, NY".
            units: "metric" (°C, km/h) or "imperial" (°F, mph). Defaults to metric.
        """
        try:
            report = await service.get_current_weather(location, units)
        except LocationNotFoundError as exc:
            raise ToolError(
                f"Location not found: {location!r}. Try a more specific name "
                "(e.g. include the country or region)."
            ) from exc
        except UpstreamWeatherError as exc:
            raise ToolError(f"Weather service unavailable: {exc}") from exc
        return _report_to_dict(report)

    return mcp
