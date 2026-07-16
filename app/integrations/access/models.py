from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.integrations.orbits import SatelliteFamily
from app.models.enums import ObservationSide, SensorType


@dataclass(frozen=True, slots=True)
class AccessPathPoint:
    """Punkt śladu naziemnego należący do jednego okna dostępu."""

    timestamp_utc: datetime
    satellite_latitude_deg: float
    satellite_longitude_deg: float
    satellite_altitude_km: float
    off_nadir_angle_deg: float
    incidence_angle_deg: float
    sun_elevation_deg: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp_utc": self.timestamp_utc.isoformat(),
            "satellite_latitude_deg": self.satellite_latitude_deg,
            "satellite_longitude_deg": self.satellite_longitude_deg,
            "satellite_altitude_km": self.satellite_altitude_km,
            "off_nadir_angle_deg": self.off_nadir_angle_deg,
            "incidence_angle_deg": self.incidence_angle_deg,
            "sun_elevation_deg": self.sun_elevation_deg,
        }


@dataclass(frozen=True, slots=True)
class GeometricAccessWindow:
    """Ciągły przedział spełniający publiczny model geometrii sensora."""

    window_id: str
    request_id: str
    satellite_id: str
    satellite_name: str
    norad_cat_id: int
    family: SatelliteFamily
    sensor_type: SensorType
    mode_id: str
    mode_name: str
    start_utc: datetime
    end_utc: datetime
    peak_utc: datetime
    observation_side: ObservationSide
    duration_s: float
    coverage_ratio: float
    minimum_off_nadir_deg: float
    maximum_off_nadir_deg: float
    minimum_incidence_angle_deg: float
    maximum_incidence_angle_deg: float
    peak_sun_elevation_deg: float | None
    orbit_epoch_utc: datetime
    sample_count: int
    path: tuple[AccessPathPoint, ...]
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "window_id": self.window_id,
            "request_id": self.request_id,
            "satellite_id": self.satellite_id,
            "satellite_name": self.satellite_name,
            "norad_cat_id": self.norad_cat_id,
            "family": self.family.value,
            "sensor_type": self.sensor_type.value,
            "mode_id": self.mode_id,
            "mode_name": self.mode_name,
            "start_utc": self.start_utc.isoformat(),
            "end_utc": self.end_utc.isoformat(),
            "peak_utc": self.peak_utc.isoformat(),
            "observation_side": self.observation_side.value,
            "duration_s": self.duration_s,
            "coverage_ratio": self.coverage_ratio,
            "minimum_off_nadir_deg": self.minimum_off_nadir_deg,
            "maximum_off_nadir_deg": self.maximum_off_nadir_deg,
            "minimum_incidence_angle_deg": (
                self.minimum_incidence_angle_deg
            ),
            "maximum_incidence_angle_deg": (
                self.maximum_incidence_angle_deg
            ),
            "peak_sun_elevation_deg": self.peak_sun_elevation_deg,
            "orbit_epoch_utc": self.orbit_epoch_utc.isoformat(),
            "sample_count": self.sample_count,
            "path": [point.to_dict() for point in self.path],
            "notes": list(self.notes),
        }


@dataclass(frozen=True, slots=True)
class AccessCalculationResult:
    """Wynik wyznaczania okien dla jednego zlecenia."""

    request_id: str
    request_name: str
    generated_at_utc: datetime
    calculation_start_utc: datetime
    calculation_end_utc: datetime
    propagation_step_s: float
    evaluated_satellites: int
    evaluated_modes: int
    windows: tuple[GeometricAccessWindow, ...]
    warnings: tuple[str, ...]

    @property
    def satellite_ids_with_access(self) -> tuple[str, ...]:
        return tuple(sorted({window.satellite_id for window in self.windows}))

    @property
    def mode_ids_with_access(self) -> tuple[str, ...]:
        return tuple(sorted({window.mode_id for window in self.windows}))

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "request_name": self.request_name,
            "generated_at_utc": self.generated_at_utc.isoformat(),
            "calculation_start_utc": self.calculation_start_utc.isoformat(),
            "calculation_end_utc": self.calculation_end_utc.isoformat(),
            "propagation_step_s": self.propagation_step_s,
            "evaluated_satellites": self.evaluated_satellites,
            "evaluated_modes": self.evaluated_modes,
            "windows": [window.to_dict() for window in self.windows],
            "warnings": list(self.warnings),
        }
