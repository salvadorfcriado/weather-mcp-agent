"""Tests for WeatherService orchestration, with fake clients (no network)."""

from __future__ import annotations

import pytest

from weather_mcp.clients.base import RawCurrentWeather
from weather_mcp.domain.errors import LocationNotFoundError, UpstreamWeatherError
from weather_mcp.domain.models import GeocodedLocation, Units
from weather_mcp.service import WeatherService

LONDON = GeocodedLocation(
    name="London", latitude=51.5, longitude=-0.12, country="United Kingdom", admin1="England"
)
RAW = RawCurrentWeather(
    temperature=12.0,
    temperature_unit="°C",
    wind_speed=8.0,
    wind_speed_unit="km/h",
    weather_code=3,
    observed_at="2026-05-30T10:00",
)


class FakeGeocoder:
    def __init__(self, result: GeocodedLocation | None = None, error: Exception | None = None):
        self._result = result
        self._error = error

    async def geocode(self, location: str) -> GeocodedLocation:
        if self._error:
            raise self._error
        assert self._result is not None
        return self._result


class FakeWeather:
    def __init__(self, result: RawCurrentWeather | None = None, error: Exception | None = None):
        self._result = result
        self._error = error

    async def get_current(
        self, latitude: float, longitude: float, units: Units
    ) -> RawCurrentWeather:
        if self._error:
            raise self._error
        assert self._result is not None
        return self._result


async def test_get_current_weather_maps_to_domain() -> None:
    service = WeatherService(FakeGeocoder(result=LONDON), FakeWeather(result=RAW))
    report = await service.get_current_weather("London", Units.METRIC)
    assert report.location.display_name == "London, England, United Kingdom"
    assert report.temperature == 12.0
    assert report.temperature_unit == "°C"
    assert report.description == "Overcast"  # WMO code 3
    assert report.observed_at == "2026-05-30T10:00"


async def test_location_not_found_propagates() -> None:
    service = WeatherService(
        FakeGeocoder(error=LocationNotFoundError("Atlantis")), FakeWeather(result=RAW)
    )
    with pytest.raises(LocationNotFoundError):
        await service.get_current_weather("Atlantis")


async def test_upstream_error_propagates() -> None:
    service = WeatherService(
        FakeGeocoder(result=LONDON), FakeWeather(error=UpstreamWeatherError("boom"))
    )
    with pytest.raises(UpstreamWeatherError):
        await service.get_current_weather("London")
