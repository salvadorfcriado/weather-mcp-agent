"""Domain value objects (pydantic): GeocodedLocation, WeatherReport.

Pure domain — no knowledge of MCP, HTTP, or Open-Meteo wire formats.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class Units(StrEnum):
    """Measurement system the caller asked for.

    ``metric`` yields °C and km/h; ``imperial`` yields °F and mph. The concrete unit
    labels are taken from the upstream response, not hard-coded here.
    """

    METRIC = "metric"
    IMPERIAL = "imperial"


class GeocodedLocation(BaseModel):
    """A human-readable place resolved to coordinates plus identifying context."""

    model_config = {"frozen": True}

    name: str
    latitude: float
    longitude: float
    country: str | None = None
    admin1: str | None = None
    timezone: str | None = None

    @property
    def display_name(self) -> str:
        """Human label, e.g. ``"London, England, United Kingdom"``."""
        parts = [self.name]
        if self.admin1 and self.admin1 != self.name:
            parts.append(self.admin1)
        if self.country:
            parts.append(self.country)
        return ", ".join(parts)


class WeatherReport(BaseModel):
    """Current conditions at a resolved location, with units."""

    model_config = {"frozen": True}

    location: GeocodedLocation
    temperature: float
    temperature_unit: str
    wind_speed: float
    wind_speed_unit: str
    description: str
    observed_at: str | None = None
