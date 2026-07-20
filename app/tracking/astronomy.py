from __future__ import annotations

from datetime import datetime, timezone
from math import cos, radians, sin, sqrt

from app.integrations.access import solar_elevation_deg
from app.integrations.orbits import PropagatedState
from app.tracking.models import (
    ObserverSite,
    OpticalVisibility,
    SatelliteVisibility,
    TopocentricState,
)


_EARTH_EQUATORIAL_RADIUS_KM = 6378.137


def _julian_date(timestamp_utc: datetime) -> float:
    timestamp = timestamp_utc.astimezone(timezone.utc)
    year = timestamp.year
    month = timestamp.month
    day = (
        timestamp.day
        + (
            timestamp.hour
            + timestamp.minute / 60.0
            + (timestamp.second + timestamp.microsecond / 1_000_000.0) / 3600.0
        )
        / 24.0
    )
    if month <= 2:
        year -= 1
        month += 12
    century = year // 100
    correction = 2 - century + century // 4
    return (
        int(365.25 * (year + 4716))
        + int(30.6001 * (month + 1))
        + day
        + correction
        - 1524.5
    )


def sun_unit_vector_eci(timestamp_utc: datetime) -> tuple[float, float, float]:
    """Przybliżony kierunek Ziemia→Słońce w układzie równikowym."""

    days = _julian_date(timestamp_utc) - 2451545.0
    mean_longitude = radians((280.460 + 0.9856474 * days) % 360.0)
    mean_anomaly = radians((357.528 + 0.9856003 * days) % 360.0)
    ecliptic_longitude = (
        mean_longitude
        + radians(1.915) * sin(mean_anomaly)
        + radians(0.020) * sin(2.0 * mean_anomaly)
    )
    obliquity = radians(23.439 - 0.0000004 * days)
    vector = (
        cos(ecliptic_longitude),
        cos(obliquity) * sin(ecliptic_longitude),
        sin(obliquity) * sin(ecliptic_longitude),
    )
    norm = sqrt(sum(component * component for component in vector))
    return tuple(component / norm for component in vector)


def satellite_is_illuminated(state: PropagatedState) -> bool:
    """Uproszczony cylindryczny model cienia Ziemi."""

    sun = sun_unit_vector_eci(state.timestamp_utc)
    position = state.teme_position_km
    projection = sum(position[index] * sun[index] for index in range(3))
    if projection >= 0.0:
        return True

    squared_norm = sum(component * component for component in position)
    perpendicular_squared = max(0.0, squared_norm - projection * projection)
    return sqrt(perpendicular_squared) > _EARTH_EQUATORIAL_RADIUS_KM


def assess_visibility(
    *,
    observer: ObserverSite,
    propagated: PropagatedState,
    topocentric: TopocentricState,
    darkness_threshold_deg: float = -4.0,
) -> SatelliteVisibility:
    """Łączy elewację, cień Ziemi i jasność lokalnego nieba."""

    observer_sun = solar_elevation_deg(
        timestamp_utc=propagated.timestamp_utc,
        latitude_deg=observer.latitude_deg,
        longitude_deg=observer.longitude_deg,
    )
    illuminated = satellite_is_illuminated(propagated)
    if not topocentric.is_above_horizon:
        status = OpticalVisibility.BELOW_HORIZON
    elif not illuminated:
        status = OpticalVisibility.SATELLITE_IN_SHADOW
    elif observer_sun > darkness_threshold_deg:
        status = OpticalVisibility.SKY_TOO_BRIGHT
    else:
        status = OpticalVisibility.VISIBLE

    return SatelliteVisibility(
        satellite_illuminated=illuminated,
        observer_sun_elevation_deg=observer_sun,
        optical_visibility=status,
    )
