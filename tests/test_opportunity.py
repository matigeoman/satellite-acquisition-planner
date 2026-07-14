from datetime import timedelta

import pytest
from pydantic import ValidationError

from app.models.enums import (
    ObservationSide,
    OpportunitySourceType,
    SensorType,
)
from app.models.opportunity import AcquisitionOpportunity


def valid_sar_opportunity_data() -> dict:
    return {
        "opportunity_id": "OPP-SAR-001",
        "request_id": "REQ-SAR-001",
        "satellite_id": "SAR-01",
        "sensor_id": "SENSOR-SAR-X",
        "mode_id": "MODE-SAR-HR",
        "sensor_type": "SAR",
        "start_utc": "2026-07-15T06:00:00Z",
        "end_utc": "2026-07-15T06:00:30Z",
        "observation_side": "RIGHT",
        "off_nadir_angle_deg": 30.0,
        "incidence_angle_deg": 35.0,
        "cloud_cover": None,
        "sun_elevation_deg": None,
        "coverage_ratio": 1.0,
        "quality_score": 0.95,
        "estimated_data_volume_mb": 750.0,
        "is_feasible": True,
        "infeasibility_reasons": [],
        "source_type": "SYNTHETIC",
        "source_reference": None,
        "notes": None,
    }


def valid_optical_opportunity_data() -> dict:
    return {
        "opportunity_id": "OPP-EO-001",
        "request_id": "REQ-EO-001",
        "satellite_id": "EO-01",
        "sensor_id": "SENSOR-EO-HR",
        "mode_id": "MODE-OPT-PAN",
        "sensor_type": "OPTICAL",
        "start_utc": "2026-07-15T08:00:00Z",
        "end_utc": "2026-07-15T08:00:20Z",
        "observation_side": "NADIR",
        "off_nadir_angle_deg": 0.0,
        "incidence_angle_deg": None,
        "cloud_cover": 0.2,
        "sun_elevation_deg": 35.0,
        "coverage_ratio": 0.9,
        "quality_score": 0.85,
        "estimated_data_volume_mb": 360.0,
        "is_feasible": True,
        "infeasibility_reasons": [],
        "source_type": "SYNTHETIC",
        "source_reference": None,
        "notes": None,
    }


def test_valid_sar_opportunity_is_created() -> None:
    opportunity = AcquisitionOpportunity(
        **valid_sar_opportunity_data()
    )

    assert opportunity.sensor_type == SensorType.SAR
    assert opportunity.observation_side == ObservationSide.RIGHT
    assert opportunity.source_type == OpportunitySourceType.SYNTHETIC


def test_duration_is_calculated() -> None:
    opportunity = AcquisitionOpportunity(
        **valid_sar_opportunity_data()
    )

    assert opportunity.duration_s == pytest.approx(30.0)


def test_memory_cost_is_calculated() -> None:
    opportunity = AcquisitionOpportunity(
        **valid_sar_opportunity_data()
    )

    assert opportunity.memory_cost_mb == pytest.approx(750.0)


def test_valid_opportunity_is_available_for_planning() -> None:
    opportunity = AcquisitionOpportunity(
        **valid_sar_opportunity_data()
    )

    assert opportunity.is_available_for_planning is True


def test_valid_optical_opportunity_is_created() -> None:
    opportunity = AcquisitionOpportunity(
        **valid_optical_opportunity_data()
    )

    assert opportunity.sensor_type == SensorType.OPTICAL
    assert opportunity.cloud_cover == pytest.approx(0.2)
    assert opportunity.sun_elevation_deg == pytest.approx(35.0)


def test_timestamps_are_normalized_to_utc() -> None:
    data = valid_sar_opportunity_data()
    data["start_utc"] = "2026-07-15T08:00:00+02:00"
    data["end_utc"] = "2026-07-15T08:00:30+02:00"

    opportunity = AcquisitionOpportunity(**data)

    assert opportunity.start_utc.hour == 6
    assert opportunity.start_utc.utcoffset() == timedelta(0)


def test_invalid_time_window_is_rejected() -> None:
    data = valid_sar_opportunity_data()
    data["end_utc"] = data["start_utc"]

    with pytest.raises(ValidationError):
        AcquisitionOpportunity(**data)


def test_sensor_type_must_match_satellite() -> None:
    data = valid_sar_opportunity_data()
    data["satellite_id"] = "EO-01"

    with pytest.raises(ValidationError):
        AcquisitionOpportunity(**data)


def test_sensor_type_must_match_sensor_id() -> None:
    data = valid_sar_opportunity_data()
    data["sensor_id"] = "SENSOR-EO-HR"

    with pytest.raises(ValidationError):
        AcquisitionOpportunity(**data)


def test_sensor_type_must_match_mode_id() -> None:
    data = valid_sar_opportunity_data()
    data["mode_id"] = "MODE-OPT-PAN"

    with pytest.raises(ValidationError):
        AcquisitionOpportunity(**data)


def test_sar_opportunity_requires_incidence_angle() -> None:
    data = valid_sar_opportunity_data()
    data["incidence_angle_deg"] = None

    with pytest.raises(ValidationError):
        AcquisitionOpportunity(**data)


def test_sar_opportunity_rejects_cloud_cover() -> None:
    data = valid_sar_opportunity_data()
    data["cloud_cover"] = 0.3

    with pytest.raises(ValidationError):
        AcquisitionOpportunity(**data)


def test_sar_opportunity_rejects_nadir_side() -> None:
    data = valid_sar_opportunity_data()
    data["observation_side"] = "NADIR"

    with pytest.raises(ValidationError):
        AcquisitionOpportunity(**data)


def test_optical_opportunity_requires_cloud_cover() -> None:
    data = valid_optical_opportunity_data()
    data["cloud_cover"] = None

    with pytest.raises(ValidationError):
        AcquisitionOpportunity(**data)


def test_optical_opportunity_requires_sun_elevation() -> None:
    data = valid_optical_opportunity_data()
    data["sun_elevation_deg"] = None

    with pytest.raises(ValidationError):
        AcquisitionOpportunity(**data)


def test_optical_opportunity_rejects_incidence_angle() -> None:
    data = valid_optical_opportunity_data()
    data["incidence_angle_deg"] = 30.0

    with pytest.raises(ValidationError):
        AcquisitionOpportunity(**data)


def test_infeasible_opportunity_requires_reason() -> None:
    data = valid_sar_opportunity_data()
    data["is_feasible"] = False
    data["infeasibility_reasons"] = []

    with pytest.raises(ValidationError):
        AcquisitionOpportunity(**data)


def test_feasible_opportunity_rejects_reasons() -> None:
    data = valid_sar_opportunity_data()
    data["is_feasible"] = True
    data["infeasibility_reasons"] = [
        "Przekroczony limit kąta",
    ]

    with pytest.raises(ValidationError):
        AcquisitionOpportunity(**data)


def test_valid_infeasible_opportunity_is_created() -> None:
    data = valid_sar_opportunity_data()
    data["is_feasible"] = False
    data["infeasibility_reasons"] = [
        "Przekroczony limit kąta",
    ]

    opportunity = AcquisitionOpportunity(**data)

    assert opportunity.is_available_for_planning is False


def test_external_source_requires_reference() -> None:
    data = valid_sar_opportunity_data()
    data["source_type"] = "STK"
    data["source_reference"] = None

    with pytest.raises(ValidationError):
        AcquisitionOpportunity(**data)


def test_naive_datetime_is_rejected() -> None:
    data = valid_sar_opportunity_data()
    data["start_utc"] = "2026-07-15T06:00:00"

    with pytest.raises(ValidationError):
        AcquisitionOpportunity(**data)


def test_invalid_opportunity_id_is_rejected() -> None:
    data = valid_sar_opportunity_data()
    data["opportunity_id"] = "opportunity 1"

    with pytest.raises(ValidationError):
        AcquisitionOpportunity(**data)


def test_unknown_field_is_rejected() -> None:
    data = valid_sar_opportunity_data()
    data["unknown_field"] = 123

    with pytest.raises(ValidationError):
        AcquisitionOpportunity(**data)