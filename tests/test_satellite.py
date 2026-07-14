import pytest
from pydantic import ValidationError

from app.models.enums import SatelliteSourceType, SatelliteStatus
from app.models.satellite import Satellite


def valid_sar_satellite_data() -> dict:
    return {
        "satellite_id": "SAR-01",
        "name": "Satelita SAR 01",
        "constellation_id": "CONST-SAR",
        "orbit_id": "ORB-SAR-01",
        "sensor_id": "SENSOR-SAR-X",
        "phase_angle_deg": 0.0,
        "memory_capacity_mb": 256000.0,
        "initial_memory_usage_mb": 10000.0,
        "minimum_transition_time_s": 90.0,
        "max_acquisitions_per_day": 30,
        "max_imaging_time_per_day_s": 3600.0,
        "status": "ACTIVE",
        "source_type": "MODEL",
        "source_reference": None,
        "notes": None,
    }


def valid_eo_satellite_data() -> dict:
    return {
        "satellite_id": "EO-01",
        "name": "Satelita optyczny 01",
        "constellation_id": "CONST-EO",
        "orbit_id": "ORB-EO-01",
        "sensor_id": "SENSOR-EO-HR",
        "phase_angle_deg": 180.0,
        "memory_capacity_mb": 512000.0,
        "initial_memory_usage_mb": 0.0,
        "minimum_transition_time_s": 60.0,
        "max_acquisitions_per_day": 40,
        "max_imaging_time_per_day_s": 3600.0,
        "status": "ACTIVE",
        "source_type": "MODEL",
        "source_reference": None,
        "notes": None,
    }


def test_valid_sar_satellite_is_created() -> None:
    satellite = Satellite(**valid_sar_satellite_data())

    assert satellite.satellite_id == "SAR-01"
    assert satellite.status == SatelliteStatus.ACTIVE
    assert satellite.source_type == SatelliteSourceType.MODEL
    assert satellite.is_available_for_planning is True


def test_valid_eo_satellite_is_created() -> None:
    satellite = Satellite(**valid_eo_satellite_data())

    assert satellite.satellite_id == "EO-01"
    assert satellite.constellation_id == "CONST-EO"
    assert satellite.phase_angle_deg == pytest.approx(180.0)


def test_available_memory_is_calculated() -> None:
    satellite = Satellite(**valid_sar_satellite_data())

    assert satellite.available_memory_mb == pytest.approx(246000.0)


def test_phase_angle_is_normalized() -> None:
    data = valid_sar_satellite_data()
    data["phase_angle_deg"] = 450.0

    satellite = Satellite(**data)

    assert satellite.phase_angle_deg == pytest.approx(90.0)


def test_negative_phase_angle_is_normalized() -> None:
    data = valid_sar_satellite_data()
    data["phase_angle_deg"] = -90.0

    satellite = Satellite(**data)

    assert satellite.phase_angle_deg == pytest.approx(270.0)


def test_invalid_satellite_id_is_rejected() -> None:
    data = valid_sar_satellite_data()
    data["satellite_id"] = "SAR1"

    with pytest.raises(ValidationError):
        Satellite(**data)


def test_memory_usage_cannot_exceed_capacity() -> None:
    data = valid_sar_satellite_data()
    data["initial_memory_usage_mb"] = 300000.0

    with pytest.raises(ValidationError):
        Satellite(**data)


def test_zero_memory_capacity_is_rejected() -> None:
    data = valid_sar_satellite_data()
    data["memory_capacity_mb"] = 0.0

    with pytest.raises(ValidationError):
        Satellite(**data)


def test_sar_satellite_rejects_eo_constellation() -> None:
    data = valid_sar_satellite_data()
    data["constellation_id"] = "CONST-EO"

    with pytest.raises(ValidationError):
        Satellite(**data)


def test_eo_satellite_rejects_sar_sensor() -> None:
    data = valid_eo_satellite_data()
    data["sensor_id"] = "SENSOR-SAR-X"

    with pytest.raises(ValidationError):
        Satellite(**data)


def test_public_data_requires_source_reference() -> None:
    data = valid_sar_satellite_data()
    data["source_type"] = "PUBLIC_DATA"
    data["source_reference"] = None

    with pytest.raises(ValidationError):
        Satellite(**data)


def test_unknown_field_is_rejected() -> None:
    data = valid_sar_satellite_data()
    data["unknown_field"] = 123

    with pytest.raises(ValidationError):
        Satellite(**data)