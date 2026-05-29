"""Caching decorators over the client interfaces.

Open/Closed: caching is added by wrapping a real client, without modifying it or the
`WeatherService`. Because the decorators implement the same Protocols, nothing
downstream can tell the difference (Liskov). Only successful results are cached.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from weather_mcp.clients.base import GeocodingClient, RawCurrentWeather, WeatherClient
from weather_mcp.domain.models import GeocodedLocation, Units


class CachedGeocodingClient:
    """Cache geocoding results for the lifetime of the process (names are stable)."""

    def __init__(self, inner: GeocodingClient) -> None:
        self._inner = inner
        self._cache: dict[str, GeocodedLocation] = {}

    async def geocode(self, location: str) -> GeocodedLocation:
        key = location.strip().lower()
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        result = await self._inner.geocode(location)
        self._cache[key] = result
        return result


class CachedWeatherClient:
    """Cache current weather per (coordinates, units) for a TTL. TTL<=0 disables it."""

    def __init__(
        self,
        inner: WeatherClient,
        ttl_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._inner = inner
        self._ttl = ttl_seconds
        self._clock = clock
        self._cache: dict[tuple[float, float, Units], tuple[float, RawCurrentWeather]] = {}

    async def get_current(
        self, latitude: float, longitude: float, units: Units
    ) -> RawCurrentWeather:
        if self._ttl <= 0:
            return await self._inner.get_current(latitude, longitude, units)

        key = (round(latitude, 4), round(longitude, 4), units)
        now = self._clock()
        cached = self._cache.get(key)
        if cached is not None and now - cached[0] < self._ttl:
            return cached[1]

        result = await self._inner.get_current(latitude, longitude, units)
        self._cache[key] = (now, result)
        return result
