"""Open-Meteo implementations of the client interfaces (async httpx).

The HTTP client is injected so tests can drive these with a mock transport — no live
network. Upstream failures and empty results become typed domain errors.
"""

from __future__ import annotations

import httpx

from weather_mcp.clients.base import RawCurrentWeather
from weather_mcp.domain.errors import LocationNotFoundError, UpstreamWeatherError
from weather_mcp.domain.models import GeocodedLocation, Units

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# Map our unit system onto Open-Meteo query parameters.
_UNIT_PARAMS: dict[Units, dict[str, str]] = {
    Units.METRIC: {"temperature_unit": "celsius", "wind_speed_unit": "kmh"},
    Units.IMPERIAL: {"temperature_unit": "fahrenheit", "wind_speed_unit": "mph"},
}


class OpenMeteoGeocodingClient:
    """Resolve a place name to coordinates via the Open-Meteo geocoding API."""

    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http

    async def geocode(self, location: str) -> GeocodedLocation:
        # Open-Meteo's geocoder matches a single place name; qualifiers like the
        # ", NY" in "New York, NY" yield no results. Search on the first segment and
        # keep the original string for the not-found message.
        search_term = location.split(",")[0].strip() or location
        try:
            resp = await self._http.get(
                GEOCODING_URL,
                params={"name": search_term, "count": 1, "language": "en", "format": "json"},
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            raise UpstreamWeatherError(f"geocoding request failed: {exc}") from exc

        results = data.get("results") or []
        if not results:
            raise LocationNotFoundError(location)

        top = results[0]
        try:
            return GeocodedLocation(
                name=top["name"],
                latitude=top["latitude"],
                longitude=top["longitude"],
                country=top.get("country"),
                admin1=top.get("admin1"),
                timezone=top.get("timezone"),
            )
        except (KeyError, TypeError) as exc:
            raise UpstreamWeatherError(
                f"unexpected geocoding response: missing field {exc}"
            ) from exc


class OpenMeteoWeatherClient:
    """Fetch current weather for coordinates via the Open-Meteo forecast API."""

    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http

    async def get_current(
        self, latitude: float, longitude: float, units: Units
    ) -> RawCurrentWeather:
        params: dict[str, str | float] = {
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,wind_speed_10m,weather_code",
            "timezone": "auto",
            **_UNIT_PARAMS[units],
        }
        try:
            resp = await self._http.get(FORECAST_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            raise UpstreamWeatherError(f"weather request failed: {exc}") from exc

        current = data.get("current") or {}
        unit_labels = data.get("current_units") or {}
        try:
            return RawCurrentWeather(
                temperature=current["temperature_2m"],
                temperature_unit=unit_labels.get("temperature_2m", "°C"),
                wind_speed=current["wind_speed_10m"],
                wind_speed_unit=unit_labels.get("wind_speed_10m", "km/h"),
                weather_code=int(current["weather_code"]),
                observed_at=current.get("time"),
            )
        except KeyError as exc:
            raise UpstreamWeatherError(f"unexpected weather response: missing field {exc}") from exc
