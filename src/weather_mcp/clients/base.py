"""Client interfaces (typing.Protocol) for the two upstream calls.

The `WeatherService` depends on these abstractions, not on the concrete Open-Meteo
implementations (DIP). The same interfaces are implemented by the real HTTP clients and
by the caching decorators.
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel

from weather_mcp.domain.models import GeocodedLocation, Units


class RawCurrentWeather(BaseModel):
    """Boundary DTO: current conditions as fetched, before WMO interpretation.

    Keeps the WMO code unmapped so the service (not the client) owns turning it into a
    human description.
    """

    model_config = {"frozen": True}

    temperature: float
    temperature_unit: str
    wind_speed: float
    wind_speed_unit: str
    weather_code: int
    observed_at: str | None = None


class GeocodingClient(Protocol):
    """Resolve a human-readable location to coordinates."""

    async def geocode(self, location: str) -> GeocodedLocation:
        """Return the best-matching location.

        Raises:
            LocationNotFoundError: when no match is found.
            UpstreamWeatherError: when the upstream request fails.
        """
        ...


class WeatherClient(Protocol):
    """Fetch current weather for coordinates in the requested unit system."""

    async def get_current(
        self, latitude: float, longitude: float, units: Units
    ) -> RawCurrentWeather:
        """Return current conditions.

        Raises:
            UpstreamWeatherError: when the upstream request fails.
        """
        ...
