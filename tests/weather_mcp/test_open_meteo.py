"""Tests for the Open-Meteo clients, driven by a mock httpx transport."""

from __future__ import annotations

import httpx
import pytest

from weather_mcp.clients.open_meteo import (
    FORECAST_URL,
    GEOCODING_URL,
    OpenMeteoGeocodingClient,
    OpenMeteoWeatherClient,
)
from weather_mcp.domain.errors import LocationNotFoundError, UpstreamWeatherError
from weather_mcp.domain.models import Units

GEO_OK = {
    "results": [
        {
            "name": "London",
            "latitude": 51.5074,
            "longitude": -0.1278,
            "country": "United Kingdom",
            "admin1": "England",
            "timezone": "Europe/London",
        }
    ]
}
WEATHER_OK = {
    "current": {
        "time": "2026-05-30T10:00",
        "temperature_2m": 14.3,
        "wind_speed_10m": 9.4,
        "weather_code": 3,
    },
    "current_units": {"temperature_2m": "°C", "wind_speed_10m": "km/h"},
}


async def test_geocode_resolves_top_match(make_http) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/search"
        assert request.url.params["name"] == "London"
        return httpx.Response(200, json=GEO_OK)

    client = OpenMeteoGeocodingClient(make_http(handler))
    loc = await client.geocode("London")
    assert (loc.name, loc.country, loc.admin1) == ("London", "United Kingdom", "England")
    assert loc.latitude == pytest.approx(51.5074)


async def test_geocode_uses_first_segment_for_qualified_names(make_http) -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["name"] = request.url.params["name"]
        return httpx.Response(200, json=GEO_OK)

    client = OpenMeteoGeocodingClient(make_http(handler))
    await client.geocode("New York, NY")
    assert captured["name"] == "New York"


async def test_geocode_not_found_message_keeps_original_query(make_http) -> None:
    client = OpenMeteoGeocodingClient(make_http(lambda r: httpx.Response(200, json={})))
    with pytest.raises(LocationNotFoundError) as exc:
        await client.geocode("Nowhere, Land")
    assert exc.value.location == "Nowhere, Land"


async def test_geocode_no_results_raises_location_not_found(make_http) -> None:
    client = OpenMeteoGeocodingClient(make_http(lambda r: httpx.Response(200, json={})))
    with pytest.raises(LocationNotFoundError):
        await client.geocode("Atlantis")


async def test_geocode_http_error_raises_upstream(make_http) -> None:
    client = OpenMeteoGeocodingClient(make_http(lambda r: httpx.Response(503)))
    with pytest.raises(UpstreamWeatherError):
        await client.geocode("London")


async def test_current_weather_metric(make_http) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/forecast"
        assert request.url.params["temperature_unit"] == "celsius"
        assert request.url.params["wind_speed_unit"] == "kmh"
        return httpx.Response(200, json=WEATHER_OK)

    client = OpenMeteoWeatherClient(make_http(handler))
    raw = await client.get_current(51.5, -0.12, Units.METRIC)
    assert raw.temperature == pytest.approx(14.3)
    assert raw.temperature_unit == "°C"
    assert raw.wind_speed_unit == "km/h"
    assert raw.weather_code == 3


async def test_current_weather_imperial_sends_right_units(make_http) -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["t"] = request.url.params["temperature_unit"]
        captured["w"] = request.url.params["wind_speed_unit"]
        return httpx.Response(200, json=WEATHER_OK)

    client = OpenMeteoWeatherClient(make_http(handler))
    await client.get_current(40.0, -3.0, Units.IMPERIAL)
    assert captured == {"t": "fahrenheit", "w": "mph"}


async def test_current_weather_http_error_raises_upstream(make_http) -> None:
    client = OpenMeteoWeatherClient(make_http(lambda r: httpx.Response(500)))
    with pytest.raises(UpstreamWeatherError):
        await client.get_current(0.0, 0.0, Units.METRIC)


async def test_current_weather_malformed_payload_raises_upstream(make_http) -> None:
    client = OpenMeteoWeatherClient(make_http(lambda r: httpx.Response(200, json={"current": {}})))
    with pytest.raises(UpstreamWeatherError):
        await client.get_current(0.0, 0.0, Units.METRIC)


async def test_geocode_malformed_result_raises_upstream(make_http) -> None:
    # A result missing latitude/longitude is a degraded upstream response, not "not found".
    payload = {"results": [{"name": "Somewhere"}]}
    client = OpenMeteoGeocodingClient(make_http(lambda r: httpx.Response(200, json=payload)))
    with pytest.raises(UpstreamWeatherError):
        await client.geocode("Somewhere")


def test_urls_are_open_meteo() -> None:
    assert "geocoding-api.open-meteo.com" in GEOCODING_URL
    assert "api.open-meteo.com" in FORECAST_URL
