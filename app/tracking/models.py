from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from app.integrations.orbits import PropagatedState, SatelliteFamily


class OrbitDataQuality(StrEnum):
    """Heurystyczna ocena wieku elementów orbitalnych."""

    FRESH = "FRESH"
    ACCEPTABLE = "ACCEPTABLE"
    STALE = "STALE"
    VERY_STALE = "VERY_STALE"


class OpticalVisibility(StrEnum):
    """Uproszczona ocena widoczności optycznej satelity."""

    VISIBLE = "VISIBLE"
    BELOW_HORIZON = "BELOW_HORIZON"
    SATELLITE_IN_SHADOW = "SATELLITE_IN_SHADOW"
    SKY_TOO_BRIGHT = "SKY_TOO_BRIGHT"


@dataclass(frozen=True, slots=True)
class ObserverSite:
    """Lokalizacja obserwatora w układzie WGS84."""

    name: str
    latitude_deg: float
    longitude_deg: float
    altitude_m: float = 0.0

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Nazwa lokalizacji obserwatora nie może być pusta")
        if not -90.0 <= self.latitude_deg <= 90.0:
            raise ValueError("latitude_deg musi należeć do zakresu [-90, 90]")
        if not -180.0 <= self.longitude_deg <= 180.0:
            raise ValueError("longitude_deg musi należeć do zakresu [-180, 180]")
        if not -500.0 <= self.altitude_m <= 10000.0:
            raise ValueError("altitude_m musi należeć do zakresu [-500, 10000]")

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "latitude_deg": self.latitude_deg,
            "longitude_deg": self.longitude_deg,
            "altitude_m": self.altitude_m,
        }


@dataclass(frozen=True, slots=True)
class TopocentricState:
    """Położenie satelity względem lokalnego horyzontu obserwatora."""

    timestamp_utc: datetime
    azimuth_deg: float
    elevation_deg: float
    range_km: float
    range_rate_km_s: float | None = None

    @property
    def is_above_horizon(self) -> bool:
        return self.elevation_deg >= 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp_utc": self.timestamp_utc.isoformat(),
            "azimuth_deg": self.azimuth_deg,
            "elevation_deg": self.elevation_deg,
            "range_km": self.range_km,
            "range_rate_km_s": self.range_rate_km_s,
        }


@dataclass(frozen=True, slots=True)
class SatelliteVisibility:
    """Warunki oświetlenia satelity i nieba nad obserwatorem."""

    satellite_illuminated: bool
    observer_sun_elevation_deg: float
    optical_visibility: OpticalVisibility

    @property
    def is_optically_visible(self) -> bool:
        return self.optical_visibility == OpticalVisibility.VISIBLE

    def to_dict(self) -> dict[str, Any]:
        return {
            "satellite_illuminated": self.satellite_illuminated,
            "observer_sun_elevation_deg": self.observer_sun_elevation_deg,
            "optical_visibility": self.optical_visibility.value,
        }


@dataclass(frozen=True, slots=True)
class LiveSatelliteState:
    """Kompletny stan jednego obiektu w wybranej chwili."""

    slot_id: str
    object_name: str
    norad_cat_id: int
    family: SatelliteFamily
    propagated: PropagatedState
    topocentric: TopocentricState
    visibility: SatelliteVisibility
    speed_km_s: float
    orbit_data_age_hours: float
    orbit_data_quality: OrbitDataQuality

    def to_dict(self) -> dict[str, Any]:
        return {
            "slot_id": self.slot_id,
            "object_name": self.object_name,
            "norad_cat_id": self.norad_cat_id,
            "family": self.family.value,
            "propagated": self.propagated.to_dict(),
            "topocentric": self.topocentric.to_dict(),
            "visibility": self.visibility.to_dict(),
            "speed_km_s": self.speed_km_s,
            "orbit_data_age_hours": self.orbit_data_age_hours,
            "orbit_data_quality": self.orbit_data_quality.value,
        }


@dataclass(frozen=True, slots=True)
class SkyTrack:
    """Przewidywana trajektoria jednego satelity na lokalnej mapie nieba."""

    slot_id: str
    object_name: str
    family: SatelliteFamily
    samples: tuple[TopocentricState, ...]

    @property
    def above_horizon_samples(self) -> tuple[TopocentricState, ...]:
        return tuple(sample for sample in self.samples if sample.is_above_horizon)


@dataclass(frozen=True, slots=True)
class PassPrediction:
    """Jeden ciągły przelot powyżej zadanego progu elewacji."""

    slot_id: str
    object_name: str
    norad_cat_id: int
    family: SatelliteFamily
    aos_utc: datetime
    maximum_utc: datetime
    los_utc: datetime
    aos_azimuth_deg: float
    maximum_elevation_deg: float
    los_azimuth_deg: float
    minimum_range_km: float
    satellite_illuminated_at_maximum: bool
    observer_sun_elevation_at_maximum_deg: float
    optical_visibility_at_maximum: OpticalVisibility

    @property
    def duration_s(self) -> float:
        return (self.los_utc - self.aos_utc).total_seconds()

    @property
    def duration_minutes(self) -> float:
        return self.duration_s / 60.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "slot_id": self.slot_id,
            "object_name": self.object_name,
            "norad_cat_id": self.norad_cat_id,
            "family": self.family.value,
            "aos_utc": self.aos_utc.isoformat(),
            "maximum_utc": self.maximum_utc.isoformat(),
            "los_utc": self.los_utc.isoformat(),
            "aos_azimuth_deg": self.aos_azimuth_deg,
            "maximum_elevation_deg": self.maximum_elevation_deg,
            "los_azimuth_deg": self.los_azimuth_deg,
            "minimum_range_km": self.minimum_range_km,
            "duration_s": self.duration_s,
            "satellite_illuminated_at_maximum": (
                self.satellite_illuminated_at_maximum
            ),
            "observer_sun_elevation_at_maximum_deg": (
                self.observer_sun_elevation_at_maximum_deg
            ),
            "optical_visibility_at_maximum": (
                self.optical_visibility_at_maximum.value
            ),
        }


@dataclass(frozen=True, slots=True)
class LiveTrackingSnapshot:
    """Stan konstelacji i prognoza lokalnych przelotów."""

    observer: ObserverSite
    timestamp_utc: datetime
    satellites: tuple[LiveSatelliteState, ...]
    sky_tracks: tuple[SkyTrack, ...]
    passes: tuple[PassPrediction, ...]

    @property
    def above_horizon_count(self) -> int:
        return sum(item.topocentric.is_above_horizon for item in self.satellites)

    @property
    def optically_visible_count(self) -> int:
        return sum(item.visibility.is_optically_visible for item in self.satellites)
