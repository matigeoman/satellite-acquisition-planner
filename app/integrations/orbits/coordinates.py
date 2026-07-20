from __future__ import annotations

import math


_WGS84_A_KM = 6378.137
_WGS84_FLATTENING = 1.0 / 298.257223563
_WGS84_E2 = _WGS84_FLATTENING * (2.0 - _WGS84_FLATTENING)


def gmst_radians(julian_date: float) -> float:
    """Przybliżony kąt GMST używany do obrotu TEME → ECEF."""

    centuries = (julian_date - 2451545.0) / 36525.0
    angle_deg = (
        280.46061837
        + 360.98564736629 * (julian_date - 2451545.0)
        + 0.000387933 * centuries**2
        - centuries**3 / 38710000.0
    )
    return math.radians(angle_deg % 360.0)


def teme_to_ecef(
    teme_position_km: tuple[float, float, float],
    julian_date: float,
) -> tuple[float, float, float]:
    """Wykonuje uproszczony obrót TEME do układu związanego z Ziemią."""

    x_teme, y_teme, z_teme = teme_position_km
    theta = gmst_radians(julian_date)
    cosine = math.cos(theta)
    sine = math.sin(theta)
    return (
        cosine * x_teme + sine * y_teme,
        -sine * x_teme + cosine * y_teme,
        z_teme,
    )


def ecef_to_geodetic(
    ecef_position_km: tuple[float, float, float],
) -> tuple[float, float, float]:
    """Konwertuje ECEF na szerokość, długość i wysokość WGS84."""

    x, y, z = ecef_position_km
    longitude = math.atan2(y, x)
    horizontal = math.hypot(x, y)

    if horizontal < 1e-12:
        latitude = math.copysign(math.pi / 2.0, z)
        altitude = abs(z) - _WGS84_A_KM * math.sqrt(1.0 - _WGS84_E2)
    else:
        latitude = math.atan2(z, horizontal * (1.0 - _WGS84_E2))
        altitude = 0.0
        for _ in range(10):
            sine = math.sin(latitude)
            prime_vertical = _WGS84_A_KM / math.sqrt(
                1.0 - _WGS84_E2 * sine * sine
            )
            cosine = math.cos(latitude)
            if abs(cosine) < 1e-12:
                altitude = abs(z) - prime_vertical * (1.0 - _WGS84_E2)
            else:
                altitude = horizontal / cosine - prime_vertical
            denominator = horizontal * (
                1.0
                - _WGS84_E2
                * prime_vertical
                / max(prime_vertical + altitude, 1e-12)
            )
            updated = math.atan2(z, denominator)
            if abs(updated - latitude) < 1e-12:
                latitude = updated
                break
            latitude = updated

    longitude_deg = math.degrees(longitude)
    if longitude_deg > 180.0:
        longitude_deg -= 360.0
    if longitude_deg < -180.0:
        longitude_deg += 360.0

    return math.degrees(latitude), longitude_deg, altitude
