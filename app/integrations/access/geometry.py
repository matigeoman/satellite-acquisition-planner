from __future__ import annotations

from datetime import datetime, timezone
from math import acos, asin, atan2, cos, degrees, pi, radians, sin, sqrt

from app.geospatial.aoi import geometry_bounds, geometry_centroid
from app.models.geometry import PointGeometry, TargetGeometry


WGS84_A_KM = 6378.137
WGS84_E2 = 6.69437999014e-3
MEAN_EARTH_RADIUS_KM = 6371.0088


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _norm(vector: tuple[float, float, float]) -> float:
    return sqrt(sum(component * component for component in vector))


def _unit(vector: tuple[float, float, float]) -> tuple[float, float, float]:
    magnitude = _norm(vector)
    if magnitude <= 0.0:
        raise ValueError("Nie można znormalizować wektora zerowego")
    return tuple(component / magnitude for component in vector)


def _dot(
    first: tuple[float, float, float],
    second: tuple[float, float, float],
) -> float:
    return sum(a * b for a, b in zip(first, second))


def _cross(
    first: tuple[float, float, float],
    second: tuple[float, float, float],
) -> tuple[float, float, float]:
    ax, ay, az = first
    bx, by, bz = second
    return (
        ay * bz - az * by,
        az * bx - ax * bz,
        ax * by - ay * bx,
    )


def geodetic_to_ecef(
    latitude_deg: float,
    longitude_deg: float,
    altitude_km: float = 0.0,
) -> tuple[float, float, float]:
    """Konwertuje geodezyjne WGS84 na ECEF w kilometrach."""

    latitude = radians(latitude_deg)
    longitude = radians(longitude_deg)
    sin_latitude = sin(latitude)
    prime_vertical = WGS84_A_KM / sqrt(
        1.0 - WGS84_E2 * sin_latitude * sin_latitude
    )
    x = (prime_vertical + altitude_km) * cos(latitude) * cos(longitude)
    y = (prime_vertical + altitude_km) * cos(latitude) * sin(longitude)
    z = (
        prime_vertical * (1.0 - WGS84_E2) + altitude_km
    ) * sin_latitude
    return x, y, z


def target_look_angles(
    *,
    satellite_latitude_deg: float,
    satellite_longitude_deg: float,
    satellite_altitude_km: float,
    target_latitude_deg: float,
    target_longitude_deg: float,
) -> tuple[float, float]:
    """Zwraca (off-nadir, incidence) dla celu na elipsoidzie WGS84."""

    satellite = geodetic_to_ecef(
        satellite_latitude_deg,
        satellite_longitude_deg,
        satellite_altitude_km,
    )
    target = geodetic_to_ecef(
        target_latitude_deg,
        target_longitude_deg,
        0.0,
    )
    satellite_to_target = tuple(
        target_component - satellite_component
        for target_component, satellite_component in zip(target, satellite)
    )
    target_to_satellite = tuple(-component for component in satellite_to_target)
    nadir = tuple(-component for component in satellite)

    off_nadir = degrees(
        acos(
            _clamp(
                _dot(_unit(satellite_to_target), _unit(nadir)),
                -1.0,
                1.0,
            )
        )
    )

    latitude = radians(target_latitude_deg)
    longitude = radians(target_longitude_deg)
    surface_normal = (
        cos(latitude) * cos(longitude),
        cos(latitude) * sin(longitude),
        sin(latitude),
    )
    incidence = degrees(
        acos(
            _clamp(
                _dot(_unit(target_to_satellite), _unit(surface_normal)),
                -1.0,
                1.0,
            )
        )
    )
    return off_nadir, incidence


def observation_side(
    *,
    previous_satellite_ecef: tuple[float, float, float],
    satellite_ecef: tuple[float, float, float],
    next_satellite_ecef: tuple[float, float, float],
    target_ecef: tuple[float, float, float],
    nadir_threshold_deg: float = 0.5,
) -> str:
    """Określa stronę obserwacji względem przybliżonego kierunku lotu."""

    target_direction = tuple(
        target_component - satellite_component
        for target_component, satellite_component in zip(
            target_ecef,
            satellite_ecef,
        )
    )
    nadir = tuple(-component for component in satellite_ecef)
    off_nadir = degrees(
        acos(
            _clamp(
                _dot(_unit(target_direction), _unit(nadir)),
                -1.0,
                1.0,
            )
        )
    )
    if off_nadir <= nadir_threshold_deg:
        return "NADIR"

    along_track = tuple(
        next_component - previous_component
        for next_component, previous_component in zip(
            next_satellite_ecef,
            previous_satellite_ecef,
        )
    )
    if _norm(along_track) <= 1e-12:
        return "RIGHT"
    right = _cross(_unit(nadir), _unit(along_track))
    side_value = _dot(_unit(target_direction), _unit(right))
    return "RIGHT" if side_value >= 0.0 else "LEFT"


def haversine_distance_km(
    first_longitude_deg: float,
    first_latitude_deg: float,
    second_longitude_deg: float,
    second_latitude_deg: float,
) -> float:
    """Odległość po wielkim kole dla szybkich oszacowań AOI."""

    first_latitude = radians(first_latitude_deg)
    second_latitude = radians(second_latitude_deg)
    delta_latitude = second_latitude - first_latitude
    delta_longitude = radians(second_longitude_deg - first_longitude_deg)
    haversine = (
        sin(delta_latitude / 2.0) ** 2
        + cos(first_latitude)
        * cos(second_latitude)
        * sin(delta_longitude / 2.0) ** 2
    )
    central_angle = 2.0 * asin(sqrt(_clamp(haversine, 0.0, 1.0)))
    return MEAN_EARTH_RADIUS_KM * central_angle


def approximate_aoi_extent_km(
    geometry: TargetGeometry,
) -> tuple[float, float]:
    """Zwraca przybliżoną szerokość i wysokość bounding box AOI."""

    if isinstance(geometry, PointGeometry):
        return 0.0, 0.0

    (south, west), (north, east) = geometry_bounds(geometry)
    center_longitude, center_latitude = geometry_centroid(geometry)
    width = haversine_distance_km(
        west,
        center_latitude,
        east,
        center_latitude,
    )
    height = haversine_distance_km(
        center_longitude,
        south,
        center_longitude,
        north,
    )
    return width, height


def approximate_coverage_ratio(
    geometry: TargetGeometry,
    *,
    scene_width_km: float,
    scene_length_km: float,
) -> float:
    """Szacuje część AOI mieszczącą się w prostokątnym footprintcie."""

    if isinstance(geometry, PointGeometry):
        return 1.0

    width, height = approximate_aoi_extent_km(geometry)
    if width <= 0.0 or height <= 0.0:
        return 1.0

    first_orientation = min(1.0, scene_width_km / width) * min(
        1.0,
        scene_length_km / height,
    )
    second_orientation = min(1.0, scene_length_km / width) * min(
        1.0,
        scene_width_km / height,
    )
    return _clamp(max(first_orientation, second_orientation), 0.0, 1.0)


def solar_elevation_deg(
    *,
    timestamp_utc: datetime,
    latitude_deg: float,
    longitude_deg: float,
) -> float:
    """Przybliżona elewacja Słońca według równania NOAA."""

    if timestamp_utc.tzinfo is None or timestamp_utc.utcoffset() is None:
        raise ValueError("timestamp_utc musi zawierać strefę czasową")
    timestamp = timestamp_utc.astimezone(timezone.utc)
    day_of_year = timestamp.timetuple().tm_yday
    fractional_hour = (
        timestamp.hour
        + timestamp.minute / 60.0
        + timestamp.second / 3600.0
        + timestamp.microsecond / 3_600_000_000.0
    )
    gamma = 2.0 * pi / 365.0 * (
        day_of_year - 1 + (fractional_hour - 12.0) / 24.0
    )
    equation_of_time = 229.18 * (
        0.000075
        + 0.001868 * cos(gamma)
        - 0.032077 * sin(gamma)
        - 0.014615 * cos(2.0 * gamma)
        - 0.040849 * sin(2.0 * gamma)
    )
    declination = (
        0.006918
        - 0.399912 * cos(gamma)
        + 0.070257 * sin(gamma)
        - 0.006758 * cos(2.0 * gamma)
        + 0.000907 * sin(2.0 * gamma)
        - 0.002697 * cos(3.0 * gamma)
        + 0.00148 * sin(3.0 * gamma)
    )
    true_solar_minutes = (
        fractional_hour * 60.0 + equation_of_time + 4.0 * longitude_deg
    ) % 1440.0
    hour_angle_deg = true_solar_minutes / 4.0 - 180.0
    latitude = radians(latitude_deg)
    hour_angle = radians(hour_angle_deg)
    cosine_zenith = (
        sin(latitude) * sin(declination)
        + cos(latitude) * cos(declination) * cos(hour_angle)
    )
    zenith = acos(_clamp(cosine_zenith, -1.0, 1.0))
    return 90.0 - degrees(zenith)
