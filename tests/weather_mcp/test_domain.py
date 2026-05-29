"""Unit tests for the pure domain layer."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from weather_mcp.domain.errors import (
    LocationNotFoundError,
    UpstreamWeatherError,
    WeatherError,
)
from weather_mcp.domain.models import GeocodedLocation, Units, WeatherReport
from weather_mcp.wmo import describe_weather_code


def test_display_name_composes_name_region_country() -> None:
    loc = GeocodedLocation(
        name="London",
        latitude=51.5,
        longitude=-0.12,
        country="United Kingdom",
        admin1="England",
    )
    assert loc.display_name == "London, England, United Kingdom"


def test_display_name_skips_missing_and_redundant_parts() -> None:
    loc = GeocodedLocation(name="Berlin", latitude=52.5, longitude=13.4, admin1="Berlin")
    assert loc.display_name == "Berlin"


def test_models_are_frozen() -> None:
    loc = GeocodedLocation(name="Paris", latitude=48.8, longitude=2.3)
    with pytest.raises(ValidationError):
        loc.name = "Lyon"  # type: ignore[misc]


def test_units_enum_values() -> None:
    assert Units.METRIC.value == "metric"
    assert Units.IMPERIAL.value == "imperial"


def test_weather_report_carries_units() -> None:
    loc = GeocodedLocation(name="Oslo", latitude=59.9, longitude=10.7)
    report = WeatherReport(
        location=loc,
        temperature=3.2,
        temperature_unit="°C",
        wind_speed=11.0,
        wind_speed_unit="km/h",
        description="Overcast",
    )
    assert report.temperature_unit == "°C"
    assert report.location.name == "Oslo"


@pytest.mark.parametrize(
    ("code", "expected"),
    [(0, "Clear sky"), (3, "Overcast"), (61, "Slight rain"), (95, "Thunderstorm")],
)
def test_known_wmo_codes(code: int, expected: str) -> None:
    assert describe_weather_code(code) == expected


def test_unknown_wmo_code_degrades_gracefully() -> None:
    out = describe_weather_code(123)
    assert "Unknown" in out and "123" in out


def test_error_hierarchy() -> None:
    assert issubclass(LocationNotFoundError, WeatherError)
    assert issubclass(UpstreamWeatherError, WeatherError)
    err = LocationNotFoundError("Atlantis")
    assert err.location == "Atlantis"
    assert "Atlantis" in str(err)
