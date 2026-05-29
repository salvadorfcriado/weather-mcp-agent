"""WeatherService: the server-side orchestrator.

Geocode → fetch current weather → map to a `WeatherReport`, owning the WMO
code→description step. Depends on the client interfaces, never on HTTP or wire formats.
"""

from __future__ import annotations

from weather_mcp.clients.base import GeocodingClient, WeatherClient
from weather_mcp.domain.models import Units, WeatherReport
from weather_mcp.wmo import describe_weather_code


class WeatherService:
    def __init__(self, geocoder: GeocodingClient, weather: WeatherClient) -> None:
        self._geocoder = geocoder
        self._weather = weather

    async def get_current_weather(
        self, location: str, units: Units = Units.METRIC
    ) -> WeatherReport:
        """Resolve the location and return its current weather.

        Raises:
            LocationNotFoundError: when the location cannot be resolved.
            UpstreamWeatherError: when an upstream request fails.
        """
        resolved = await self._geocoder.geocode(location)
        raw = await self._weather.get_current(resolved.latitude, resolved.longitude, units)
        return WeatherReport(
            location=resolved,
            temperature=raw.temperature,
            temperature_unit=raw.temperature_unit,
            wind_speed=raw.wind_speed,
            wind_speed_unit=raw.wind_speed_unit,
            description=describe_weather_code(raw.weather_code),
            observed_at=raw.observed_at,
        )
