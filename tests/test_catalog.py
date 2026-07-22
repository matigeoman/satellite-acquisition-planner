import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.catalog_loader import load_system_catalog
from app.models.catalog import SystemCatalog
from app.models.enums import SensorType


PROJECT_DIRECTORY = Path(__file__).resolve().parents[1]

CATALOG_PATH = (
    PROJECT_DIRECTORY
    / "data"
    / "scenarios"
    / "example"
    / "system.json"
)


def valid_catalog_data() -> dict:
    return json.loads(
        CATALOG_PATH.read_text(
            encoding="utf-8",
        )
    )


def test_example_catalog_is_loaded() -> None:
    catalog = load_system_catalog(CATALOG_PATH)

    assert catalog.catalog_id == "CATALOG-PL-MODEL"
    assert catalog.version == "1.3.0"


def test_catalog_has_expected_object_counts() -> None:
    catalog = load_system_catalog(CATALOG_PATH)

    assert len(catalog.orbits) == 2
    assert len(catalog.sensors) == 2
    assert len(catalog.imaging_modes) == 6
    assert len(catalog.satellites) == 6
    assert len(catalog.active_satellites) == 6
    assert len(catalog.ground_stations) == 2


def test_catalog_has_expected_constellation_counts() -> None:
    catalog = load_system_catalog(CATALOG_PATH)

    assert catalog.constellation_counts == {
        "CONST-SAR": 4,
        "CONST-EO": 2,
    }


def test_sar_constellation_has_expected_phases() -> None:
    catalog = load_system_catalog(CATALOG_PATH)

    phases = sorted(
        satellite.phase_angle_deg
        for satellite in catalog.satellites
        if satellite.constellation_id == "CONST-SAR"
    )

    assert phases == [
        0.0,
        90.0,
        180.0,
        270.0,
    ]


def test_eo_constellation_has_expected_phases() -> None:
    catalog = load_system_catalog(CATALOG_PATH)

    phases = sorted(
        satellite.phase_angle_deg
        for satellite in catalog.satellites
        if satellite.constellation_id == "CONST-EO"
    )

    assert phases == [
        0.0,
        180.0,
    ]


def test_catalog_contains_sar_and_optical_sensors() -> None:
    catalog = load_system_catalog(CATALOG_PATH)

    sensor_types = {
        sensor.sensor_type
        for sensor in catalog.sensors
    }

    assert sensor_types == {
        SensorType.SAR,
        SensorType.OPTICAL,
    }


def test_satellite_references_can_be_resolved() -> None:
    catalog = load_system_catalog(CATALOG_PATH)

    for satellite in catalog.satellites:
        orbit = catalog.get_orbit(
            satellite.orbit_id
        )
        sensor = catalog.get_sensor(
            satellite.sensor_id
        )

        assert orbit.orbit_id == satellite.orbit_id
        assert sensor.sensor_id == satellite.sensor_id


def test_get_satellite_returns_requested_object() -> None:
    catalog = load_system_catalog(CATALOG_PATH)

    satellite = catalog.get_satellite("SAR-03")

    assert satellite.satellite_id == "SAR-03"
    assert satellite.phase_angle_deg == pytest.approx(180.0)


def test_get_unknown_satellite_raises_key_error() -> None:
    catalog = load_system_catalog(CATALOG_PATH)

    with pytest.raises(KeyError):
        catalog.get_satellite("SAR-99")


def test_get_ground_station_returns_requested_object() -> None:
    catalog = load_system_catalog(CATALOG_PATH)

    station = catalog.get_ground_station("GS-WARSAW")

    assert station.name == "Warsaw Mission Ground Station"


def test_get_unknown_ground_station_raises_key_error() -> None:
    catalog = load_system_catalog(CATALOG_PATH)

    with pytest.raises(KeyError):
        catalog.get_ground_station("GS-UNKNOWN")


def test_missing_catalog_file_is_rejected(
    tmp_path: Path,
) -> None:
    missing_path = (
        tmp_path
        / "missing.json"
    )

    with pytest.raises(FileNotFoundError):
        load_system_catalog(missing_path)


def test_invalid_json_is_rejected(
    tmp_path: Path,
) -> None:
    invalid_path = (
        tmp_path
        / "invalid.json"
    )

    invalid_path.write_text(
        "{invalid-json",
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        load_system_catalog(invalid_path)


def test_duplicate_orbit_ids_are_rejected() -> None:
    data = valid_catalog_data()

    duplicated_orbit = deepcopy(
        data["orbits"][0]
    )

    data["orbits"].append(duplicated_orbit)

    with pytest.raises(ValidationError):
        SystemCatalog(**data)


def test_duplicate_sensor_ids_are_rejected() -> None:
    data = valid_catalog_data()

    data["sensors"][1]["sensor_id"] = (
        data["sensors"][0]["sensor_id"]
    )

    with pytest.raises(ValidationError):
        SystemCatalog(**data)


def test_duplicate_satellite_ids_are_rejected() -> None:
    data = valid_catalog_data()

    duplicated_satellite = deepcopy(
        data["satellites"][0]
    )

    data["satellites"].append(
        duplicated_satellite
    )

    with pytest.raises(ValidationError):
        SystemCatalog(**data)


def test_duplicate_mode_ids_are_rejected() -> None:
    data = valid_catalog_data()

    data["sensors"][1]["imaging_modes"][0][
        "mode_id"
    ] = data["sensors"][0]["imaging_modes"][0][
        "mode_id"
    ]

    with pytest.raises(ValidationError):
        SystemCatalog(**data)


def test_missing_orbit_reference_is_rejected() -> None:
    data = valid_catalog_data()

    data["satellites"][0]["orbit_id"] = (
        "ORB-SAR-MISSING"
    )

    with pytest.raises(ValidationError):
        SystemCatalog(**data)


def test_missing_sensor_reference_is_rejected() -> None:
    data = valid_catalog_data()

    data["satellites"][0]["sensor_id"] = (
        "SENSOR-SAR-MISSING"
    )

    with pytest.raises(ValidationError):
        SystemCatalog(**data)


def test_duplicate_phase_in_constellation_is_rejected() -> None:
    data = valid_catalog_data()

    data["satellites"][1]["phase_angle_deg"] = 360.0

    with pytest.raises(ValidationError):
        SystemCatalog(**data)


def test_sensor_identifier_must_match_sensor_type() -> None:
    data = valid_catalog_data()

    data["sensors"][1]["sensor_id"] = (
        "SENSOR-SAR-OPTICAL"
    )

    with pytest.raises(ValidationError):
        SystemCatalog(**data)


def test_unknown_catalog_field_is_rejected() -> None:
    data = valid_catalog_data()

    data["unknown_field"] = 123

    with pytest.raises(ValidationError):
        SystemCatalog(**data)