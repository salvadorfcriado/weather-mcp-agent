"""Tests for the caching decorators (cache hit, TTL expiry, TTL=0 disables)."""

from __future__ import annotations

from weather_mcp.clients.base import RawCurrentWeather
from weather_mcp.clients.cache import CachedGeocodingClient, CachedWeatherClient
from weather_mcp.domain.models import GeocodedLocation, Units

LOC = GeocodedLocation(name="London", latitude=51.5, longitude=-0.12, country="UK")
RAW = RawCurrentWeather(
    temperature=14.0,
    temperature_unit="°C",
    wind_speed=9.0,
    wind_speed_unit="km/h",
    weather_code=3,
)


class CountingGeocoder:
    def __init__(self) -> None:
        self.calls = 0

    async def geocode(self, location: str) -> GeocodedLocation:
        self.calls += 1
        return LOC


class CountingWeather:
    def __init__(self) -> None:
        self.calls = 0

    async def get_current(
        self, latitude: float, longitude: float, units: Units
    ) -> RawCurrentWeather:
        self.calls += 1
        return RAW


async def test_geocoding_cached_after_first_call() -> None:
    inner = CountingGeocoder()
    client = CachedGeocodingClient(inner)
    await client.geocode("London")
    await client.geocode("london")  # case/space-insensitive key
    await client.geocode("  London ")
    assert inner.calls == 1


async def test_weather_cache_hit_within_ttl() -> None:
    inner = CountingWeather()
    now = [1000.0]
    client = CachedWeatherClient(inner, ttl_seconds=600, clock=lambda: now[0])
    await client.get_current(51.5, -0.12, Units.METRIC)
    now[0] += 300
    await client.get_current(51.5, -0.12, Units.METRIC)
    assert inner.calls == 1


async def test_weather_cache_expires_after_ttl() -> None:
    inner = CountingWeather()
    now = [1000.0]
    client = CachedWeatherClient(inner, ttl_seconds=600, clock=lambda: now[0])
    await client.get_current(51.5, -0.12, Units.METRIC)
    now[0] += 601
    await client.get_current(51.5, -0.12, Units.METRIC)
    assert inner.calls == 2


async def test_weather_cache_keyed_by_units() -> None:
    inner = CountingWeather()
    client = CachedWeatherClient(inner, ttl_seconds=600, clock=lambda: 0.0)
    await client.get_current(51.5, -0.12, Units.METRIC)
    await client.get_current(51.5, -0.12, Units.IMPERIAL)
    assert inner.calls == 2


async def test_weather_ttl_zero_disables_cache() -> None:
    inner = CountingWeather()
    client = CachedWeatherClient(inner, ttl_seconds=0)
    await client.get_current(51.5, -0.12, Units.METRIC)
    await client.get_current(51.5, -0.12, Units.METRIC)
    assert inner.calls == 2
