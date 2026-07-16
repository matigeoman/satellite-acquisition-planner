from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.integrations.access.models import (
    AccessCalculationResult,
    AccessPathPoint,
    GeometricAccessWindow,
)
from app.integrations.orbits.models import (
    PropagatedState,
    PublicOrbitRecord,
    SatelliteFamily,
    SatelliteGroundTrack,
    TrackedSatellite,
)
from app.models.enums import ObservationSide, RequestMode, SensorType
from app.models.geometry import PointGeometry
from app.models.request import ObservationRequest
from app.ui.components.cesium_globe import build_cesium_html
from app.visualization import build_cesium_scene


START = datetime(2026, 7, 16, 10, tzinfo=timezone.utc)


def _record() -> PublicOrbitRecord:
    return PublicOrbitRecord(
        object_name="ICEYE-X99",
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


def _track() -> SatelliteGroundTrack:
    satellite = TrackedSatellite(
        slot_id="SAR-01",
        family=SatelliteFamily.ICEYE,
        record=_record(),
    )
    states = tuple(
        PropagatedState(
            timestamp_utc=START + timedelta(minutes=index),
            latitude_deg=50.0 + index * 0.2,
            longitude_deg=18.0 + index * 0.3,
            altitude_km=550.0,
            teme_position_km=(6800.0, 0.0, 0.0),
            teme_velocity_km_s=(0.0, 7.5, 0.0),
        )
        for index in range(4)
    )
    return SatelliteGroundTrack(satellite=satellite, states=states)


def _request() -> ObservationRequest:
    return ObservationRequest(
        request_id="REQ-CESIUM-01",
        name="Warszawa",
        geometry=PointGeometry(coordinates=(21.0122, 52.2297)),
        priority=8,
        earliest_start_utc=START,
        latest_end_utc=START + timedelta(hours=1),
        request_mode=RequestMode.SINGLE,
        requested_sensor_types=[SensorType.SAR],
        max_resolution_m=1.0,
        minimum_coverage_ratio=0.9,
        max_incidence_angle_deg=45.0,
        max_off_nadir_deg=45.0,
    )


def _access_result() -> AccessCalculationResult:
    point = AccessPathPoint(
        timestamp_utc=START + timedelta(minutes=1),
        satellite_latitude_deg=50.2,
        satellite_longitude_deg=18.3,
        satellite_altitude_km=550.0,
        off_nadir_angle_deg=25.0,
        incidence_angle_deg=30.0,
        sun_elevation_deg=None,
    )
    window = GeometricAccessWindow(
        window_id="WINDOW-REQ-CESIUM-01-SAR-01-001",
        request_id="REQ-CESIUM-01",
        satellite_id="SAR-01",
        satellite_name="ICEYE-X99",
        norad_cat_id=65001,
        family=SatelliteFamily.ICEYE,
        sensor_type=SensorType.SAR,
        mode_id="MODE-SAR-ICEYE-STRIP",
        mode_name="Strip",
        start_utc=START + timedelta(seconds=30),
        end_utc=START + timedelta(minutes=2),
        peak_utc=point.timestamp_utc,
        observation_side=ObservationSide.RIGHT,
        duration_s=90.0,
        coverage_ratio=1.0,
        minimum_off_nadir_deg=24.0,
        maximum_off_nadir_deg=27.0,
        minimum_incidence_angle_deg=29.0,
        maximum_incidence_angle_deg=32.0,
        peak_sun_elevation_deg=None,
        orbit_epoch_utc=START,
        sample_count=1,
        path=(point,),
    )
    return AccessCalculationResult(
        request_id="REQ-CESIUM-01",
        request_name="Warszawa",
        generated_at_utc=START,
        calculation_start_utc=START,
        calculation_end_utc=START + timedelta(minutes=3),
        propagation_step_s=60.0,
        evaluated_satellites=1,
        evaluated_modes=1,
        windows=(window,),
        warnings=(),
    )


def test_cesium_scene_contains_clock_satellite_and_aoi() -> None:
    scene = build_cesium_scene(
        tracks=[_track()],
        requests=[_request()],
    )

    packets = {packet["id"]: packet for packet in scene.packets}
    assert "document" in packets
    assert "satellite-SAR-01" in packets
    assert "groundtrack-SAR-01-01" in packets
    assert "subsatellite-SAR-01" in packets
    ground_track = packets["groundtrack-SAR-01-01"]["polyline"]
    assert ground_track["clampToGround"] is False
    assert 25000.0 in ground_track["positions"]["cartographicDegrees"]
    assert "path" not in packets["satellite-SAR-01"]
    assert "aoi-REQ-CESIUM-01" in packets
    assert packets["document"]["clock"]["range"] == "LOOP_STOP"
    assert scene.satellite_count == 1
    assert scene.request_count == 1


def test_cesium_scene_adds_access_beam_with_availability() -> None:
    scene = build_cesium_scene(
        tracks=[_track()],
        requests=[_request()],
        access_result=_access_result(),
    )

    access_packets = [
        packet for packet in scene.packets if packet["id"].startswith("access-")
    ]
    assert len(access_packets) == 1
    assert "polyline" in access_packets[0]
    assert "ellipse" in access_packets[0]
    assert "/" in access_packets[0]["availability"]
    assert scene.access_window_count == 1


def test_cesium_html_contains_pinned_renderer_and_embedded_czml() -> None:
    scene = build_cesium_scene(
        tracks=[_track()],
        requests=[_request()],
    )

    rendered = build_cesium_html(scene, height_px=650)

    assert "cesium@1.130.0" in rendered
    assert "CzmlDataSource.load" in rendered
    assert "satellite-SAR-01" in rendered
    assert "baseLayer: false" in rendered
    assert 'viewer.scene.globe.show = false' in rendered
    assert 'id: "offline-earth"' in rendered
    assert "ImageMaterialProperty" in rendered
    assert "data:image/jpeg;base64," in rendered
    assert "flyToBoundingSphere" in rendered
    assert "Pokaż Ziemię" in rendered


def test_cesium_scene_can_enable_full_3d_orbit() -> None:
    scene = build_cesium_scene(
        tracks=[_track()],
        show_orbits_3d=True,
        show_ground_tracks=False,
    )

    packets = {packet["id"]: packet for packet in scene.packets}
    assert "path" in packets["satellite-SAR-01"]
    assert not any(packet_id.startswith("groundtrack-") for packet_id in packets)
