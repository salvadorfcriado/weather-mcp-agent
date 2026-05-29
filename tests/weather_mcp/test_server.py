"""In-process MCP smoke test: a real ClientSession talks to the FastMCP server."""

from __future__ import annotations

from mcp import types
from mcp.shared.memory import create_connected_server_and_client_session

from weather_mcp.clients.base import RawCurrentWeather
from weather_mcp.domain.errors import LocationNotFoundError
from weather_mcp.domain.models import GeocodedLocation, Units
from weather_mcp.server import build_server
from weather_mcp.service import WeatherService

LONDON = GeocodedLocation(name="London", latitude=51.5, longitude=-0.12, country="UK")
RAW = RawCurrentWeather(
    temperature=12.0,
    temperature_unit="°C",
    wind_speed=8.0,
    wind_speed_unit="km/h",
    weather_code=0,
)


class FakeGeocoder:
    async def geocode(self, location: str) -> GeocodedLocation:
        if location.lower() == "atlantis":
            raise LocationNotFoundError(location)
        return LONDON


class FakeWeather:
    async def get_current(
        self, latitude: float, longitude: float, units: Units
    ) -> RawCurrentWeather:
        return RAW


def _build():
    return build_server(WeatherService(FakeGeocoder(), FakeWeather()))


def _text(result: types.CallToolResult) -> str:
    return " ".join(b.text for b in result.content if isinstance(b, types.TextContent))


async def test_tool_is_discoverable_with_schema() -> None:
    async with create_connected_server_and_client_session(_build()) as client:
        tools = await client.list_tools()
    names = {t.name for t in tools.tools}
    assert "get_current_weather" in names
    tool = next(t for t in tools.tools if t.name == "get_current_weather")
    props = tool.inputSchema["properties"]
    assert "location" in props
    # units is an enum of metric/imperial (possibly via a $ref/$defs — check the values)
    schema_text = str(tool.inputSchema)
    assert "metric" in schema_text and "imperial" in schema_text


async def test_call_known_location_succeeds() -> None:
    async with create_connected_server_and_client_session(_build()) as client:
        result = await client.call_tool("get_current_weather", {"location": "London"})
    assert result.isError is False
    assert "Clear sky" in _text(result)  # WMO 0


async def test_call_unknown_location_returns_tool_error() -> None:
    async with create_connected_server_and_client_session(_build()) as client:
        result = await client.call_tool("get_current_weather", {"location": "Atlantis"})
    assert result.isError is True
    assert "not found" in _text(result).lower()
