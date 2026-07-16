import pytest

from app.catalogs import ICEYE_PUBLIC_PROFILE, PLEIADES_NEO_PUBLIC_PROFILE
from app.catalogs.models import ParameterOrigin
from app.models.enums import SensorType


def test_iceye_profile_contains_four_slots_and_nine_modes() -> None:
    profile = ICEYE_PUBLIC_PROFILE

    assert profile.satellite_slots == 4
    assert len(profile.satellite_labels) == 4
    assert profile.sensor.sensor_type == SensorType.SAR
    assert len(profile.imaging_modes) == 9


def test_iceye_dwell_precise_public_parameters() -> None:
    mode = ICEYE_PUBLIC_PROFILE.get_mode(
        "MODE-SAR-ICEYE-DWELL-PRECISE"
    )

    assert mode.nominal_resolution_m == pytest.approx(0.25)
    assert mode.nominal_scene_width_km == pytest.approx(5)
    assert mode.min_acquisition_duration_s == pytest.approx(25)
    assert mode.min_incidence_angle_deg == pytest.approx(20)
    assert mode.max_incidence_angle_deg == pytest.approx(33)


def test_iceye_scan_wide_public_parameters() -> None:
    mode = ICEYE_PUBLIC_PROFILE.get_mode("MODE-SAR-ICEYE-SCAN-WIDE")

    assert mode.nominal_resolution_m == pytest.approx(27)
    assert mode.nominal_scene_width_km == pytest.approx(200)
    assert mode.nominal_scene_length_km == pytest.approx(300)
    assert mode.max_acquisition_duration_s == pytest.approx(84)


def test_pleiades_profile_contains_two_satellites_and_three_products() -> None:
    profile = PLEIADES_NEO_PUBLIC_PROFILE

    assert profile.satellite_slots == 2
    assert profile.satellite_labels == ["Pléiades Neo 3", "Pléiades Neo 4"]
    assert profile.orbit_template.altitude_km == pytest.approx(620)
    assert profile.orbit_template.inclination_deg == pytest.approx(97.9)
    assert len(profile.imaging_modes) == 3


def test_pleiades_panchromatic_parameters() -> None:
    mode = PLEIADES_NEO_PUBLIC_PROFILE.get_mode(
        "MODE-OPT-PLEIADES-NEO-PAN"
    )

    assert mode.nominal_resolution_m == pytest.approx(0.3)
    assert mode.nominal_scene_width_km == pytest.approx(14)
    assert mode.max_off_nadir_deg == pytest.approx(52)


def test_profiles_mark_runtime_public_orbit_data() -> None:
    for profile in (ICEYE_PUBLIC_PROFILE, PLEIADES_NEO_PUBLIC_PROFILE):
        assert any(
            source.origin == ParameterOrigin.PUBLIC_ORBIT_DATA
            for source in profile.parameter_sources
        )
