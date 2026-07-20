from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import isclose

from app.integrations.orbits.models import (
    PropagatedState,
    PublicOrbitRecord,
    SatelliteFamily,
    SatelliteGroundTrack,
    TrackedSatellite,
)
from app.services.orbit_service import PublicConstellationSnapshot
from app.tracking import (
    LiveTrackingService,
    ObserverSite,
    OrbitDataQuality,
    topocentric_from_state,
)


START = datetime(2026, 7, 20, 12, tzinfo=timezone.utc)


def _record() -> PublicOrbitRecord:
    return PublicOrbitRecord(
        object_name="TEST-SAT",
        object_id="2026-001A",
        norad_cat_id=65001,
        epoch_utc=START,
        mean_motion_rev_per_day=15.2,
        eccentricity=0.001,
        inclination_deg=97.8,
        raan_deg=20.0,
        argument_of_pericenter_deg=30.0,
        mean_anomaly_deg=40.0,
        bstar=0.0,
        mean_motion_dot=0.0,
        mean_motion_ddot=0.0,
        element_set_no=1,
        rev_at_epoch=1,
        raw_omm={},
    )


def _state(
    timestamp: datetime,
    latitude: float,
    longitude: float,
    altitude: float = 550.0,
) -> PropagatedState:
    return PropagatedState(
        timestamp_utc=timestamp,
        latitude_deg=latitude,
        longitude_deg=longitude,
        altitude_km=altitude,
        teme_position_km=(6878.0, 0.0, 0.0),
        teme_velocity_km_s=(0.0, 7.6, 0.0),
    )


class FakePropagator:
    def __init__(self) -> None:
        self.satellite = TrackedSatellite(
            slot_id="SAR-01",
            family=SatelliteFamily.ICEYE,
            record=_record(),
        )

    def propagate_record(self, record, timestamp_utc: datetime) -> PropagatedState:
        return _state(timestamp_utc, 52.2532, 20.8997)

    def ground_track(
        self,
        satellite: TrackedSatellite,
        *,
        start_utc: datetime,
        duration: timedelta,
        step: timedelta,
    ) -> SatelliteGroundTrack:
        latitudes = (35.0, 48.0, 52.2532, 56.0, 68.0)
        states = tuple(
            _state(start_utc + step * index, latitude, 20.8997)
            for index, latitude in enumerate(latitudes)
        )
        return SatelliteGroundTrack(satellite=satellite, states=states)


def _snapshot() -> PublicConstellationSnapshot:
    propagator = FakePropagator()
    return PublicConstellationSnapshot(
        generated_at_utc=START,
        satellites=(propagator.satellite,),
        queries=(),
        warnings=(),
    )


def test_topocentric_state_is_zenith_for_same_subpoint() -> None:
    observer = ObserverSite("Test", 0.0, 0.0, 0.0)
    topocentric = topocentric_from_state(
        observer=observer,
        state=_state(START, 0.0, 0.0, altitude=500.0),
    )

    assert isclose(topocentric.elevation_deg, 90.0, abs_tol=1e-7)
    assert isclose(topocentric.range_km, 500.0, abs_tol=1e-6)


def test_live_tracking_builds_current_state_and_pass() -> None:
    service = LiveTrackingService(propagator=FakePropagator())
    observer = ObserverSite("WAT", 52.2532, 20.8997, 110.0)

    states = service.current_states(
        _snapshot(),
        observer=observer,
        timestamp_utc=START,
    )
    passes = service.predict_passes(
        _snapshot(),
        observer=observer,
        start_utc=START,
        duration=timedelta(minutes=10),
        step=timedelta(minutes=1),
        minimum_elevation_deg=5.0,
    )

    assert len(states) == 1
    assert states[0].topocentric.elevation_deg > 89.0
    assert states[0].orbit_data_quality == OrbitDataQuality.FRESH
    assert len(passes) == 1
    assert passes[0].maximum_elevation_deg > 80.0
    assert passes[0].aos_utc < passes[0].maximum_utc < passes[0].los_utc
    assert passes[0].duration_s > 0.0


def test_sky_tracks_keep_samples_for_each_satellite() -> None:
    service = LiveTrackingService(propagator=FakePropagator())
    tracks = service.sky_tracks(
        _snapshot(),
        observer=ObserverSite("WAT", 52.2532, 20.8997, 110.0),
        start_utc=START,
        duration=timedelta(minutes=5),
        step=timedelta(minutes=1),
    )

    assert len(tracks) == 1
    assert tracks[0].slot_id == "SAR-01"
    assert len(tracks[0].samples) == 5
    assert tracks[0].above_horizon_samples
