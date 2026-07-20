from __future__ import annotations

from datetime import datetime, timezone
from math import asin, atan2, cos, degrees, hypot, pi, radians, sin, sqrt

from app.integrations.orbits import PropagatedState
from app.tracking.models import ObserverSite, TopocentricState


_WGS84_A_KM = 6378.137
_WGS84_FLATTENING = 1.0 / 298.257223563
_WGS84_E2 = _WGS84_FLATTENING * (2.0 - _WGS84_FLATTENING)
_EARTH_RADIUS_KM = 6371.0088


def geodetic_to_ecef(
    latitude_deg: float,
    longitude_deg: float,
    altitude_km: float = 0.0,
) -> tuple[float, float, float]:
    """Konwertuje współrzędne geodezyjne WGS84 na ECEF w kilometrach."""

    latitude = radians(latitude_deg)
    longitude = radians(longitude_deg)
    sine = sin(latitude)
    cosine = cos(latitude)
    prime_vertical = _WGS84_A_KM / sqrt(1.0 - _WGS84_E2 * sine * sine)
    return (
        (prime_vertical + altitude_km) * cosine * cos(longitude),
        (prime_vertical + altitude_km) * cosine * sin(longitude),
        (prime_vertical * (1.0 - _WGS84_E2) + altitude_km) * sine,
    )


def _enu_components(
    *,
    observer: ObserverSite,
    satellite_ecef_km: tuple[float, float, float],
) -> tuple[float, float, float]:
    observer_ecef = geodetic_to_ecef(
        observer.latitude_deg,
        observer.longitude_deg,
        observer.altitude_m / 1000.0,
    )
    dx = satellite_ecef_km[0] - observer_ecef[0]
    dy = satellite_ecef_km[1] - observer_ecef[1]
    dz = satellite_ecef_km[2] - observer_ecef[2]

    latitude = radians(observer.latitude_deg)
    longitude = radians(observer.longitude_deg)
    east = -sin(longitude) * dx + cos(longitude) * dy
    north = (
        -sin(latitude) * cos(longitude) * dx
        - sin(latitude) * sin(longitude) * dy
        + cos(latitude) * dz
    )
    up = (
        cos(latitude) * cos(longitude) * dx
        + cos(latitude) * sin(longitude) * dy
        + sin(latitude) * dz
    )
    return east, north, up


def topocentric_from_state(
    *,
    observer: ObserverSite,
    state: PropagatedState,
    next_state: PropagatedState | None = None,
) -> TopocentricState:
    """Wyznacza azymut, elewację, odległość i opcjonalną prędkość radialną."""

    satellite_ecef = geodetic_to_ecef(
        state.latitude_deg,
        state.longitude_deg,
        state.altitude_km,
    )
    east, north, up = _enu_components(
        observer=observer,
        satellite_ecef_km=satellite_ecef,
    )
    horizontal = hypot(east, north)
    distance = sqrt(horizontal * horizontal + up * up)
    if distance <= 0.0:
        raise ValueError("Odległość obserwator–satelita musi być dodatnia")

    azimuth = degrees(atan2(east, north)) % 360.0
    elevation = degrees(asin(max(-1.0, min(1.0, up / distance))))

    range_rate: float | None = None
    if next_state is not None:
        delta_s = (next_state.timestamp_utc - state.timestamp_utc).total_seconds()
        if delta_s > 0.0:
            next_ecef = geodetic_to_ecef(
                next_state.latitude_deg,
                next_state.longitude_deg,
                next_state.altitude_km,
            )
            next_east, next_north, next_up = _enu_components(
                observer=observer,
                satellite_ecef_km=next_ecef,
            )
            next_distance = sqrt(
                next_east * next_east
                + next_north * next_north
                + next_up * next_up
            )
            range_rate = (next_distance - distance) / delta_s

    return TopocentricState(
        timestamp_utc=state.timestamp_utc,
        azimuth_deg=azimuth,
        elevation_deg=elevation,
        range_km=distance,
        range_rate_km_s=range_rate,
    )


def interpolate_threshold_crossing(
    first: TopocentricState,
    second: TopocentricState,
    *,
    threshold_deg: float,
) -> TopocentricState:
    """Liniowo interpoluje moment przecięcia progu elewacji."""

    denominator = second.elevation_deg - first.elevation_deg
    if abs(denominator) < 1e-12:
        fraction = 0.5
    else:
        fraction = (threshold_deg - first.elevation_deg) / denominator
    fraction = max(0.0, min(1.0, fraction))

    duration = second.timestamp_utc - first.timestamp_utc
    timestamp = first.timestamp_utc + duration * fraction

    delta_azimuth = (second.azimuth_deg - first.azimuth_deg + 540.0) % 360.0 - 180.0
    azimuth = (first.azimuth_deg + delta_azimuth * fraction) % 360.0
    distance = first.range_km + (second.range_km - first.range_km) * fraction
    if first.range_rate_km_s is None or second.range_rate_km_s is None:
        range_rate = None
    else:
        range_rate = (
            first.range_rate_km_s
            + (second.range_rate_km_s - first.range_rate_km_s) * fraction
        )

    return TopocentricState(
        timestamp_utc=timestamp,
        azimuth_deg=azimuth,
        elevation_deg=threshold_deg,
        range_km=distance,
        range_rate_km_s=range_rate,
    )


def spherical_circle(
    *,
    center_latitude_deg: float,
    center_longitude_deg: float,
    radius_km: float,
    samples: int = 96,
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Buduje przybliżony okrąg na powierzchni Ziemi."""

    if radius_km <= 0.0:
        raise ValueError("radius_km musi być dodatnie")
    if samples < 12:
        raise ValueError("samples musi wynosić co najmniej 12")

    angular_distance = radius_km / _EARTH_RADIUS_KM
    center_latitude = radians(center_latitude_deg)
    center_longitude = radians(center_longitude_deg)
    latitudes: list[float] = []
    longitudes: list[float] = []
    for index in range(samples + 1):
        bearing = 2.0 * pi * index / samples
        latitude = asin(
            sin(center_latitude) * cos(angular_distance)
            + cos(center_latitude) * sin(angular_distance) * cos(bearing)
        )
        longitude = center_longitude + atan2(
            sin(bearing) * sin(angular_distance) * cos(center_latitude),
            cos(angular_distance) - sin(center_latitude) * sin(latitude),
        )
        latitudes.append(degrees(latitude))
        longitudes.append((degrees(longitude) + 540.0) % 360.0 - 180.0)
    return tuple(longitudes), tuple(latitudes)


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Czas musi zawierać strefę czasową")
    return value.astimezone(timezone.utc)
