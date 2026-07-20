from __future__ import annotations

from datetime import datetime, timedelta, timezone

import plotly.graph_objects as go

from app.integrations.orbits.models import (
    PropagatedState,
    PublicOrbitRecord,
    SatelliteFamily,
    SatelliteGroundTrack,
    TrackedSatellite,
)
from app.tracking import (
    LiveSatelliteState,
    ObserverSite,
    OpticalVisibility,
    OrbitDataQuality,
    SatelliteVisibility,
    SkyTrack,
    TopocentricState,
)
from app.visualization import (
    build_live_ground_map_figure,
    build_sky_map_figure,
)


START = datetime(2026, 7, 20, 12, tzinfo=timezone.utc)


def _satellite() -> TrackedSatellite:
    record = PublicOrbitRecord(
        object_name="ICEYE-TEST",
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
    return TrackedSatellite("SAR-01", SatelliteFamily.ICEYE, record)


def _propagated(index: int = 0) -> PropagatedState:
    return PropagatedState(
        timestamp_utc=START + timedelta(minutes=index),
        latitude_deg=52.0 + index,
        longitude_deg=20.0 + index,
        altitude_km=550.0,
        teme_position_km=(6878.0, 0.0, 0.0),
        teme_velocity_km_s=(0.0, 7.6, 0.0),
    )


def _topocentric(index: int = 0) -> TopocentricState:
    return TopocentricState(
        timestamp_utc=START + timedelta(minutes=index),
        azimuth_deg=45.0 + index * 10.0,
        elevation_deg=30.0 + index * 5.0,
        range_km=900.0 - index * 50.0,
    )


def _live_state() -> LiveSatelliteState:
    return LiveSatelliteState(
        slot_id="SAR-01",
        object_name="ICEYE-TEST",
        norad_cat_id=65001,
        family=SatelliteFamily.ICEYE,
        propagated=_propagated(),
        topocentric=_topocentric(),
        visibility=SatelliteVisibility(
            satellite_illuminated=True,
            observer_sun_elevation_deg=-12.0,
            optical_visibility=OpticalVisibility.VISIBLE,
        ),
        speed_km_s=7.6,
        orbit_data_age_hours=1.0,
        orbit_data_quality=OrbitDataQuality.FRESH,
    )


def test_sky_map_uses_polar_coordinates_and_dark_background() -> None:
    track = SkyTrack(
        slot_id="SAR-01",
        object_name="ICEYE-TEST",
        family=SatelliteFamily.ICEYE,
        samples=tuple(_topocentric(index) for index in range(3)),
    )
    figure = build_sky_map_figure(states=[_live_state()], tracks=[track])

    assert any(isinstance(trace, go.Scatterpolar) for trace in figure.data)
    assert figure.layout.polar.angularaxis.direction == "clockwise"
    assert figure.layout.paper_bgcolor == "#07111f"


def test_live_ground_map_contains_observer_satellite_track_and_footprint() -> None:
    satellite = _satellite()
    track = SatelliteGroundTrack(
        satellite=satellite,
        states=tuple(_propagated(index) for index in range(3)),
    )
    figure = build_live_ground_map_figure(
        observer=ObserverSite("WAT", 52.2532, 20.8997, 110.0),
        states=[_live_state()],
        tracks=[track],
        timestamp_utc=START,
        selected_slot_id="SAR-01",
        footprint_radius_km=75.0,
    )

    names = [trace.name for trace in figure.data]
    assert "SAR-01 · ground track" in names
    assert "Referencyjny footprint" in names
    assert "Terminator" in names
    assert figure.layout.geo.oceancolor == "#071827"
