from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.integrations.access import (
    approximate_coverage_ratio,
    solar_elevation_deg,
    target_look_angles,
)
from app.models.geometry import PointGeometry, PolygonGeometry


def test_nadir_target_has_zero_look_angles() -> None:
    off_nadir, incidence = target_look_angles(
        satellite_latitude_deg=0.0,
        satellite_longitude_deg=0.0,
        satellite_altitude_km=550.0,
        target_latitude_deg=0.0,
        target_longitude_deg=0.0,
    )

    assert off_nadir == pytest.approx(0.0, abs=1e-6)
    assert incidence == pytest.approx(0.0, abs=1e-6)


def test_two_degree_cross_track_offset_matches_sar_range() -> None:
    off_nadir, incidence = target_look_angles(
        satellite_latitude_deg=0.0,
        satellite_longitude_deg=2.0,
        satellite_altitude_km=550.0,
        target_latitude_deg=0.0,
        target_longitude_deg=0.0,
    )

    assert 20.0 < off_nadir < 25.0
    assert 20.0 < incidence < 30.0


def test_point_is_fully_covered_by_any_positive_scene() -> None:
    geometry = PointGeometry(coordinates=(21.0, 52.0))

    assert approximate_coverage_ratio(
        geometry,
        scene_width_km=5.0,
        scene_length_km=5.0,
    ) == 1.0


def test_polygon_coverage_decreases_for_small_scene() -> None:
    geometry = PolygonGeometry(
        coordinates=[
            [
                (0.0, 0.0),
                (1.0, 0.0),
                (1.0, 1.0),
                (0.0, 1.0),
                (0.0, 0.0),
            ]
        ]
    )

    small = approximate_coverage_ratio(
        geometry,
        scene_width_km=10.0,
        scene_length_km=10.0,
    )
    large = approximate_coverage_ratio(
        geometry,
        scene_width_km=150.0,
        scene_length_km=150.0,
    )

    assert 0.0 < small < 0.02
    assert large == pytest.approx(1.0)


def test_solar_elevation_distinguishes_noon_and_midnight() -> None:
    noon = solar_elevation_deg(
        timestamp_utc=datetime(2026, 3, 20, 12, tzinfo=timezone.utc),
        latitude_deg=0.0,
        longitude_deg=0.0,
    )
    midnight = solar_elevation_deg(
        timestamp_utc=datetime(2026, 3, 20, 0, tzinfo=timezone.utc),
        latitude_deg=0.0,
        longitude_deg=0.0,
    )

    assert noon > 85.0
    assert midnight < -85.0
