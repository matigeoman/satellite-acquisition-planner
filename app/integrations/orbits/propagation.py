from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sgp4 import omm
from sgp4.api import SGP4_ERRORS, Satrec, jday

from app.integrations.orbits.coordinates import (
    ecef_to_geodetic,
    teme_to_ecef,
)
from app.integrations.orbits.models import (
    PropagatedState,
    PublicOrbitRecord,
    SatelliteGroundTrack,
    TrackedSatellite,
)


class OrbitPropagationError(RuntimeError):
    """Błąd propagacji SGP4 lub konwersji pozycji."""


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Czas propagacji musi zawierać strefę czasową")
    return value.astimezone(timezone.utc)


class Sgp4OrbitPropagator:
    """Propagator GP/OMM oparty na standardowym modelu SGP4/WGS-72."""

    @staticmethod
    def build_satrec(record: PublicOrbitRecord) -> Satrec:
        satellite = Satrec()
        try:
            omm.initialize(satellite, record.to_omm_fields())
        except Exception as error:
            raise OrbitPropagationError(
                f"Nie można zainicjalizować SGP4 dla {record.object_name}: {error}"
            ) from error
        return satellite

    @staticmethod
    def _propagate_satrec(
        *,
        satellite: Satrec,
        record: PublicOrbitRecord,
        timestamp_utc: datetime,
    ) -> PropagatedState:
        timestamp = _as_utc(timestamp_utc)
        second = timestamp.second + timestamp.microsecond / 1_000_000.0
        jd, fraction = jday(
            timestamp.year,
            timestamp.month,
            timestamp.day,
            timestamp.hour,
            timestamp.minute,
            second,
        )
        error_code, position, velocity = satellite.sgp4(jd, fraction)
        if error_code != 0:
            message = SGP4_ERRORS.get(error_code, "nieznany błąd SGP4")
            raise OrbitPropagationError(
                f"SGP4 {record.object_name}: {message} (kod {error_code})"
            )

        teme_position = tuple(float(value) for value in position)
        teme_velocity = tuple(float(value) for value in velocity)
        ecef = teme_to_ecef(teme_position, jd + fraction)
        latitude, longitude, altitude = ecef_to_geodetic(ecef)
        return PropagatedState(
            timestamp_utc=timestamp,
            latitude_deg=latitude,
            longitude_deg=longitude,
            altitude_km=altitude,
            teme_position_km=teme_position,
            teme_velocity_km_s=teme_velocity,
        )

    def propagate_record(
        self,
        record: PublicOrbitRecord,
        timestamp_utc: datetime,
    ) -> PropagatedState:
        return self._propagate_satrec(
            satellite=self.build_satrec(record),
            record=record,
            timestamp_utc=timestamp_utc,
        )

    def ground_track(
        self,
        satellite: TrackedSatellite,
        *,
        start_utc: datetime,
        duration: timedelta,
        step: timedelta,
    ) -> SatelliteGroundTrack:
        if duration.total_seconds() <= 0:
            raise ValueError("duration musi być dodatnie")
        if step.total_seconds() <= 0:
            raise ValueError("step musi być dodatni")

        start = _as_utc(start_utc)
        end = start + duration
        satrec = self.build_satrec(satellite.record)
        states: list[PropagatedState] = []
        timestamp = start
        while timestamp <= end:
            states.append(
                self._propagate_satrec(
                    satellite=satrec,
                    record=satellite.record,
                    timestamp_utc=timestamp,
                )
            )
            timestamp += step

        return SatelliteGroundTrack(
            satellite=satellite,
            states=tuple(states),
        )
