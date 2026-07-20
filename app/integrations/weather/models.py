from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any


class CloudAggregation(StrEnum):
    """Sposób agregacji prognozy zachmurzenia nad obszarem AOI."""

    MAXIMUM = "MAXIMUM"
    PERCENTILE_75 = "PERCENTILE_75"
    MEAN = "MEAN"


@dataclass(frozen=True, slots=True)
class WeatherLocation:
    """Punkt próbkowania prognozy w układzie WGS84."""

    location_id: str
    longitude_deg: float
    latitude_deg: float

    def __post_init__(self) -> None:
        if not self.location_id.strip():
            raise ValueError("location_id nie może być pusty")
        if not -180.0 <= self.longitude_deg <= 180.0:
            raise ValueError("longitude_deg musi należeć do [-180, 180]")
        if not -90.0 <= self.latitude_deg <= 90.0:
            raise ValueError("latitude_deg musi należeć do [-90, 90]")

    def to_dict(self) -> dict[str, Any]:
        return {
            "location_id": self.location_id,
            "longitude_deg": self.longitude_deg,
            "latitude_deg": self.latitude_deg,
        }


@dataclass(frozen=True, slots=True)
class HourlyCloudSample:
    """Jedna godzinowa próbka zachmurzenia Open-Meteo."""

    timestamp_utc: datetime
    cloud_cover_percent: float
    cloud_cover_low_percent: float
    cloud_cover_mid_percent: float
    cloud_cover_high_percent: float

    def __post_init__(self) -> None:
        if self.timestamp_utc.tzinfo is None or self.timestamp_utc.utcoffset() is None:
            raise ValueError("timestamp_utc musi zawierać strefę czasową")
        for field_name, value in (
            ("cloud_cover_percent", self.cloud_cover_percent),
            ("cloud_cover_low_percent", self.cloud_cover_low_percent),
            ("cloud_cover_mid_percent", self.cloud_cover_mid_percent),
            ("cloud_cover_high_percent", self.cloud_cover_high_percent),
        ):
            if not 0.0 <= value <= 100.0:
                raise ValueError(f"{field_name} musi należeć do [0, 100]")

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp_utc": self.timestamp_utc.isoformat(),
            "cloud_cover_percent": self.cloud_cover_percent,
            "cloud_cover_low_percent": self.cloud_cover_low_percent,
            "cloud_cover_mid_percent": self.cloud_cover_mid_percent,
            "cloud_cover_high_percent": self.cloud_cover_high_percent,
        }


@dataclass(frozen=True, slots=True)
class WeatherPointForecast:
    """Prognoza godzinowa przypisana do jednego punktu AOI."""

    location: WeatherLocation
    latitude_deg: float
    longitude_deg: float
    elevation_m: float | None
    timezone_name: str
    samples: tuple[HourlyCloudSample, ...]

    def __post_init__(self) -> None:
        if not self.samples:
            raise ValueError("Prognoza punktowa musi zawierać próbki")
        timestamps = [sample.timestamp_utc for sample in self.samples]
        if timestamps != sorted(timestamps):
            raise ValueError("Próbki prognozy muszą być uporządkowane")

    def to_dict(self) -> dict[str, Any]:
        return {
            "location": self.location.to_dict(),
            "latitude_deg": self.latitude_deg,
            "longitude_deg": self.longitude_deg,
            "elevation_m": self.elevation_m,
            "timezone_name": self.timezone_name,
            "samples": [sample.to_dict() for sample in self.samples],
        }


@dataclass(frozen=True, slots=True)
class WeatherForecastResult:
    """Wynik zapytania do Open-Meteo wraz z informacją o cache."""

    forecasts: tuple[WeatherPointForecast, ...]
    fetched_at_utc: datetime
    request_url: str
    from_cache: bool
    is_stale: bool
    warning: str | None = None

    @property
    def location_count(self) -> int:
        return len(self.forecasts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "forecasts": [forecast.to_dict() for forecast in self.forecasts],
            "fetched_at_utc": self.fetched_at_utc.isoformat(),
            "request_url": self.request_url,
            "from_cache": self.from_cache,
            "is_stale": self.is_stale,
            "warning": self.warning,
        }


@dataclass(frozen=True, slots=True)
class CloudPointValue:
    """Interpolowana wartość zachmurzenia w punkcie AOI."""

    location: WeatherLocation
    cloud_cover_percent: float
    cloud_cover_low_percent: float
    cloud_cover_mid_percent: float
    cloud_cover_high_percent: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "location": self.location.to_dict(),
            "cloud_cover_percent": self.cloud_cover_percent,
            "cloud_cover_low_percent": self.cloud_cover_low_percent,
            "cloud_cover_mid_percent": self.cloud_cover_mid_percent,
            "cloud_cover_high_percent": self.cloud_cover_high_percent,
        }


@dataclass(frozen=True, slots=True)
class WindowCloudAssessment:
    """Ocena zachmurzenia dla jednego geometrycznego okna EO."""

    window_id: str
    assessed_at_utc: datetime
    aggregation: CloudAggregation
    cloud_cover_percent: float
    cloud_cover_low_percent: float
    cloud_cover_mid_percent: float
    cloud_cover_high_percent: float
    point_values: tuple[CloudPointValue, ...]
    max_allowed_cloud_cover_percent: float
    is_cloud_feasible: bool
    source_url: str
    from_cache: bool
    is_stale: bool
    warning: str | None = None

    @property
    def cloud_cover_fraction(self) -> float:
        return self.cloud_cover_percent / 100.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "window_id": self.window_id,
            "assessed_at_utc": self.assessed_at_utc.isoformat(),
            "aggregation": self.aggregation.value,
            "cloud_cover_percent": self.cloud_cover_percent,
            "cloud_cover_low_percent": self.cloud_cover_low_percent,
            "cloud_cover_mid_percent": self.cloud_cover_mid_percent,
            "cloud_cover_high_percent": self.cloud_cover_high_percent,
            "point_values": [value.to_dict() for value in self.point_values],
            "max_allowed_cloud_cover_percent": (
                self.max_allowed_cloud_cover_percent
            ),
            "is_cloud_feasible": self.is_cloud_feasible,
            "source_url": self.source_url,
            "from_cache": self.from_cache,
            "is_stale": self.is_stale,
            "warning": self.warning,
        }
