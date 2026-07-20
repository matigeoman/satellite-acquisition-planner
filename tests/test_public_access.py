from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.catalogs import ICEYE_PUBLIC_PROFILE, PLEIADES_NEO_PUBLIC_PROFILE
from app.integrations.access import GeometricAccessCalculator
from app.integrations.orbits import (
    PropagatedState,
    PublicOrbitRecord,
    SatelliteFamily,
    SatelliteGroundTrack,
    TrackedSatellite,
)
from app.models.enums import RequestMode, SensorType
from app.models.geometry import PointGeometry
from app.models.request import ObservationRequest


def _record(name: str, norad: int) -> PublicOrbitRecord:
    epoch = datetime(2026, 7, 16, 0, tzinfo=timezone.utc)
    return PublicOrbitRecord(
        object_name=name,
        object_id="2026-001A",
        norad_cat_id=norad,
        epoch_utc=epoch,
        mean_motion_rev_per_day=15.2,
        eccentricity=0.001,
        inclination_deg=97.8,
        raan_deg=10.0,
        argument_of_pericenter_deg=0.0,
        mean_anomaly_deg=0.0,
        bstar=0.0,
        mean_motion_dot=0.0,
        mean_motion_ddot=0.0,
        element_set_no=1,
        rev_at_epoch=1,
        raw_omm={},
    )


def _state(
    timestamp: datetime,
    *,
    longitude: float,
    latitude: float = 0.0,
    altitude: float = 550.0,
) -> PropagatedState:
    return PropagatedState(
        timestamp_utc=timestamp,
        latitude_deg=latitude,
        longitude_deg=longitude,
        altitude_km=altitude,
        teme_position_km=(0.0, 0.0, 0.0),
        teme_velocity_km_s=(0.0, 0.0, 0.0),
    )


def _request(sensor_type: SensorType, start: datetime) -> ObservationRequest:
    return ObservationRequest(
        request_id=f"REQ-TEST-{sensor_type.value}",
        name="Test access",
        geometry=PointGeometry(coordinates=(0.0, 0.0)),
        priority=8,
        earliest_start_utc=start,
        latest_end_utc=start + timedelta(minutes=2),
        request_mode=RequestMode.SINGLE,
        requested_sensor_types=[sensor_type],
        max_resolution_m=1.0,
        minimum_coverage_ratio=1.0,
        max_cloud_cover=0.2 if sensor_type == SensorType.OPTICAL else None,
        max_incidence_angle_deg=40.0 if sensor_type == SensorType.SAR else None,
        max_off_nadir_deg=45.0,
    )


def test_optical_nadir_track_creates_daylight_window() -> None:
    start = datetime(2026, 3, 20, 12, tzinfo=timezone.utc)
    satellite = TrackedSatellite(
        slot_id="EO-01",
        family=SatelliteFamily.PLEIADES_NEO,
        record=_record("PLEIADES NEO 3", 49001),
    )
    track = SatelliteGroundTrack(
        satellite=satellite,
        states=(
            _state(start, longitude=-0.1, altitude=620.0),
            _state(start + timedelta(seconds=30), longitude=0.0, altitude=620.0),
            _state(start + timedelta(seconds=60), longitude=0.1, altitude=620.0),
        ),
    )

    result = GeometricAccessCalculator().calculate(
        request=_request(SensorType.OPTICAL, start),
        tracks=(track,),
        iceye_profile=ICEYE_PUBLIC_PROFILE,
        pleiades_profile=PLEIADES_NEO_PUBLIC_PROFILE,
        calculation_start_utc=start,
        calculation_end_utc=start + timedelta(minutes=2),
        step=timedelta(seconds=30),
        selected_mode_ids={"MODE-OPT-PLEIADES-NEO-PAN"},
    )

    assert len(result.windows) == 1
    window = result.windows[0]
    assert window.satellite_id == "EO-01"
    assert window.peak_sun_elevation_deg is not None
    assert window.peak_sun_elevation_deg > 80.0
    assert window.coverage_ratio == 1.0


def test_optical_night_track_is_rejected() -> None:
    start = datetime(2026, 3, 20, 0, tzinfo=timezone.utc)
    satellite = TrackedSatellite(
        slot_id="EO-01",
        family=SatelliteFamily.PLEIADES_NEO,
        record=_record("PLEIADES NEO 3", 49001),
    )
    track = SatelliteGroundTrack(
        satellite=satellite,
        states=(
            _state(start, longitude=-0.1, altitude=620.0),
            _state(start + timedelta(seconds=30), longitude=0.0, altitude=620.0),
            _state(start + timedelta(seconds=60), longitude=0.1, altitude=620.0),
        ),
    )

    result = GeometricAccessCalculator().calculate(
        request=_request(SensorType.OPTICAL, start),
        tracks=(track,),
        iceye_profile=ICEYE_PUBLIC_PROFILE,
        pleiades_profile=PLEIADES_NEO_PUBLIC_PROFILE,
        calculation_start_utc=start,
        calculation_end_utc=start + timedelta(minutes=2),
        step=timedelta(seconds=30),
        selected_mode_ids={"MODE-OPT-PLEIADES-NEO-PAN"},
    )

    assert not result.windows


def test_iceye_offset_track_creates_sar_window() -> None:
    start = datetime(2026, 7, 16, 12, tzinfo=timezone.utc)
    satellite = TrackedSatellite(
        slot_id="SAR-01",
        family=SatelliteFamily.ICEYE,
        record=_record("ICEYE-X99", 65001),
    )
    track = SatelliteGroundTrack(
        satellite=satellite,
        states=(
            _state(start, longitude=1.9),
            _state(start + timedelta(seconds=30), longitude=2.0),
            _state(start + timedelta(seconds=60), longitude=2.1),
        ),
    )

    result = GeometricAccessCalculator().calculate(
        request=_request(SensorType.SAR, start),
        tracks=(track,),
        iceye_profile=ICEYE_PUBLIC_PROFILE,
        pleiades_profile=PLEIADES_NEO_PUBLIC_PROFILE,
        calculation_start_utc=start,
        calculation_end_utc=start + timedelta(minutes=2),
        step=timedelta(seconds=30),
        selected_mode_ids={"MODE-SAR-ICEYE-SPOT"},
    )

    assert len(result.windows) == 1
    window = result.windows[0]
    assert 20.0 <= window.minimum_incidence_angle_deg <= 40.0
    assert window.peak_sun_elevation_deg is None
    assert "publicznych GP/OMM" in window.notes[0]
