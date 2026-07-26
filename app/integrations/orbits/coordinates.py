from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum

from app.integrations.orbits.eop import EopDataKind, EopRangeError, EopTable


_WGS84_A_KM = 6378.137
_WGS84_FLATTENING = 1.0 / 298.257223563
_WGS84_E2 = _WGS84_FLATTENING * (2.0 - _WGS84_FLATTENING)
_ARCSEC_TO_RAD = math.pi / (180.0 * 3600.0)


class EarthFixedTransformQuality(StrEnum):
    """Jakość transformacji TEME do układu związanego z Ziemią."""

    EOP_OBSERVED = "EOP_OBSERVED"
    EOP_PREDICTED = "EOP_PREDICTED"
    UTC_GMST_APPROX = "UTC_GMST_APPROX"


@dataclass(frozen=True, slots=True)
class EarthFixedPosition:
    """Pozycja TEME przeliczona do Earth Fixed wraz z metadanymi."""

    position_km: tuple[float, float, float]
    frame: str
    quality: EarthFixedTransformQuality
    eop_source: str | None = None

    @property
    def eop_applied(self) -> bool:
        return self.quality != EarthFixedTransformQuality.UTC_GMST_APPROX


def julian_date_utc(timestamp_utc: datetime) -> float:
    """Zwraca datę juliańską UTC dla świadomego czasu ``datetime``."""

    if timestamp_utc.tzinfo is None or timestamp_utc.utcoffset() is None:
        raise ValueError("timestamp_utc musi zawierać strefę czasową")
    timestamp = timestamp_utc.astimezone(timezone.utc)
    year = timestamp.year
    month = timestamp.month
    day = timestamp.day
    fraction = (
        timestamp.hour
        + timestamp.minute / 60.0
        + (timestamp.second + timestamp.microsecond / 1_000_000.0) / 3600.0
    ) / 24.0
    return (
        367.0 * year
        - math.floor(7.0 * (year + math.floor((month + 9.0) / 12.0)) * 0.25)
        + math.floor(275.0 * month / 9.0)
        + day
        + 1721013.5
        + fraction
    )


def gmst_radians(julian_date_ut1: float) -> float:
    """Kąt GMST według konwencji Vallado/IAU-82 dla daty UT1."""

    centuries = (julian_date_ut1 - 2451545.0) / 36525.0
    seconds = (
        -6.2e-6 * centuries**3
        + 0.093104 * centuries**2
        + (876600.0 * 3600.0 + 8640184.812866) * centuries
        + 67310.54841
    )
    angle = (seconds * math.pi / 43200.0) % (2.0 * math.pi)
    return angle if angle >= 0.0 else angle + 2.0 * math.pi


def _teme_to_pef(
    teme_position_km: tuple[float, float, float],
    julian_date_ut1: float,
) -> tuple[float, float, float]:
    x_teme, y_teme, z_teme = teme_position_km
    theta = gmst_radians(julian_date_ut1)
    cosine = math.cos(theta)
    sine = math.sin(theta)
    return (
        cosine * x_teme + sine * y_teme,
        -sine * x_teme + cosine * y_teme,
        z_teme,
    )


def _pef_to_itrf(
    pef_position_km: tuple[float, float, float],
    *,
    polar_motion_x_arcsec: float,
    polar_motion_y_arcsec: float,
) -> tuple[float, float, float]:
    """Stosuje macierz ruchu bieguna Vallado ``Wᵀ``: PEF → ITRF."""

    xp = polar_motion_x_arcsec * _ARCSEC_TO_RAD
    yp = polar_motion_y_arcsec * _ARCSEC_TO_RAD
    cos_x = math.cos(xp)
    sin_x = math.sin(xp)
    cos_y = math.cos(yp)
    sin_y = math.sin(yp)

    # Macierz W z Vallado. Do przejścia PEF -> ITRF używane jest W^T.
    w00, w01, w02 = cos_x, 0.0, -sin_x
    w10, w11, w12 = sin_x * sin_y, cos_y, cos_x * sin_y
    w20, w21, w22 = sin_x * cos_y, -sin_y, cos_x * cos_y
    x_pef, y_pef, z_pef = pef_position_km
    return (
        w00 * x_pef + w10 * y_pef + w20 * z_pef,
        w01 * x_pef + w11 * y_pef + w21 * z_pef,
        w02 * x_pef + w12 * y_pef + w22 * z_pef,
    )


def teme_to_earth_fixed(
    teme_position_km: tuple[float, float, float],
    timestamp_utc: datetime,
    *,
    eop_table: EopTable | None = None,
    strict_eop: bool = False,
) -> EarthFixedPosition:
    """Konwertuje TEME do ITRF2020 lub jawnego przybliżenia GMST/UTC.

    Gdy dostępna jest tabela EOP, funkcja interpoluje ``UT1-UTC`` oraz ruch
    bieguna ``xp/yp`` i wykonuje standardowe przejście TEME → PEF → ITRF.
    Bez EOP zachowuje kompatybilny tryb przybliżony oparty na GMST z UTC.
    """

    if timestamp_utc.tzinfo is None or timestamp_utc.utcoffset() is None:
        raise ValueError("timestamp_utc musi zawierać strefę czasową")
    timestamp = timestamp_utc.astimezone(timezone.utc)
    jd_utc = julian_date_utc(timestamp)
    if eop_table is None:
        return EarthFixedPosition(
            position_km=_teme_to_pef(teme_position_km, jd_utc),
            frame="PEF_APPROX",
            quality=EarthFixedTransformQuality.UTC_GMST_APPROX,
        )

    try:
        eop = eop_table.interpolate(timestamp)
    except EopRangeError:
        if strict_eop:
            raise
        return EarthFixedPosition(
            position_km=_teme_to_pef(teme_position_km, jd_utc),
            frame="PEF_APPROX",
            quality=EarthFixedTransformQuality.UTC_GMST_APPROX,
            eop_source=eop_table.source_name,
        )

    jd_ut1 = jd_utc + eop.ut1_minus_utc_s / 86400.0
    pef = _teme_to_pef(teme_position_km, jd_ut1)
    itrf = _pef_to_itrf(
        pef,
        polar_motion_x_arcsec=eop.polar_motion_x_arcsec,
        polar_motion_y_arcsec=eop.polar_motion_y_arcsec,
    )
    quality = (
        EarthFixedTransformQuality.EOP_PREDICTED
        if eop.kind == EopDataKind.PREDICTED
        else EarthFixedTransformQuality.EOP_OBSERVED
    )
    return EarthFixedPosition(
        position_km=itrf,
        frame=eop_table.frame,
        quality=quality,
        eop_source=eop_table.source_name,
    )


def teme_to_ecef(
    teme_position_km: tuple[float, float, float],
    julian_date: float,
) -> tuple[float, float, float]:
    """Kompatybilny tryb uproszczony TEME → PEF bez danych EOP."""

    return _teme_to_pef(teme_position_km, julian_date)


def ecef_to_geodetic(
    ecef_position_km: tuple[float, float, float],
) -> tuple[float, float, float]:
    """Konwertuje ECEF/ITRF na szerokość, długość i wysokość WGS84."""

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


__all__ = [
    "EarthFixedPosition",
    "EarthFixedTransformQuality",
    "ecef_to_geodetic",
    "gmst_radians",
    "julian_date_utc",
    "teme_to_earth_fixed",
    "teme_to_ecef",
]
