from __future__ import annotations

from datetime import datetime, timedelta, timezone

import plotly.graph_objects as go

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
from app.visualization import build_plotly_globe_scene


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
        request_id="REQ-PLOTLY-01",
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
    points = tuple(
        AccessPathPoint(
            timestamp_utc=START + timedelta(minutes=index),
            satellite_latitude_deg=50.0 + index * 0.2,
            satellite_longitude_deg=18.0 + index * 0.3,
            satellite_altitude_km=550.0,
            off_nadir_angle_deg=25.0,
            incidence_angle_deg=30.0,
            sun_elevation_deg=None,
        )
        for index in range(1, 3)
    )
    window = GeometricAccessWindow(
        window_id="WINDOW-REQ-PLOTLY-01-SAR-01-001",
        request_id="REQ-PLOTLY-01",
        satellite_id="SAR-01",
        satellite_name="ICEYE-X99",
        norad_cat_id=65001,
        family=SatelliteFamily.ICEYE,
        sensor_type=SensorType.SAR,
        mode_id="MODE-SAR-ICEYE-STRIP",
        mode_name="Strip",
        start_utc=START + timedelta(minutes=1),
        end_utc=START + timedelta(minutes=2),
        peak_utc=START + timedelta(minutes=1),
        observation_side=ObservationSide.RIGHT,
        duration_s=60.0,
        coverage_ratio=1.0,
        minimum_off_nadir_deg=24.0,
        maximum_off_nadir_deg=27.0,
        minimum_incidence_angle_deg=29.0,
        maximum_incidence_angle_deg=32.0,
        peak_sun_elevation_deg=None,
        orbit_epoch_utc=START,
        sample_count=2,
        path=points,
    )
    return AccessCalculationResult(
        request_id="REQ-PLOTLY-01",
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


def test_operational_globe_has_visible_earth_configuration() -> None:
    scene = build_plotly_globe_scene(tracks=[_track()])

    geo = scene.operational_figure.layout.geo
    assert geo.projection.type == "orthographic"
    assert geo.showland is True
    assert geo.showocean is True
    assert geo.showframe is True
    assert geo.oceancolor == "#071a2c"


def test_operational_globe_contains_ground_track_satellite_and_aoi() -> None:
    scene = build_plotly_globe_scene(
        tracks=[_track()],
        requests=[_request()],
        focus_utc=START + timedelta(minutes=2),
    )

    names = [trace.name for trace in scene.operational_figure.data]
    assert "SAR-01 · ground track" in names
    assert "SAR-01 · pozycja" in names
    assert "AOI · REQ-PLOTLY-01" in names
    assert scene.satellite_count == 1
    assert scene.request_count == 1
    assert scene.focus_utc == START + timedelta(minutes=2)


def test_operational_globe_contains_access_window() -> None:
    scene = build_plotly_globe_scene(
        tracks=[_track()],
        requests=[_request()],
        access_result=_access_result(),
    )

    names = [trace.name for trace in scene.operational_figure.data]
    assert "Okna dostępu" in names
    assert scene.access_window_count == 1


def test_spatial_figure_contains_earth_surface_and_orbit() -> None:
    scene = build_plotly_globe_scene(
        tracks=[_track()],
        show_orbits_3d=True,
    )

    assert any(isinstance(trace, go.Surface) for trace in scene.spatial_figure.data)
    assert any(
        isinstance(trace, go.Scatter3d) and trace.name == "SAR-01 · orbita"
        for trace in scene.spatial_figure.data
    )
    assert scene.spatial_figure.layout.scene.aspectmode == "data"


def test_plotly_scene_does_not_require_mapbox_or_cesium() -> None:
    scene = build_plotly_globe_scene(tracks=[_track()])
    payload = scene.operational_figure.to_json().lower()

    assert "mapbox" not in payload
    assert "cesium" not in payload
    assert "orthographic" in payload


def test_plotly_legend_is_disabled_and_globe_uses_full_domain() -> None:
    scene = build_plotly_globe_scene(
        tracks=[_track()],
        requests=[_request()],
        access_result=_access_result(),
    )

    assert scene.operational_figure.layout.showlegend is False
    assert scene.spatial_figure.layout.showlegend is False
    assert tuple(scene.operational_figure.layout.geo.domain.x) == (0.0, 1.0)
    assert tuple(scene.operational_figure.layout.geo.domain.y) == (0.0, 1.0)
    assert scene.operational_figure.layout.geo.projection.scale == 1.1
