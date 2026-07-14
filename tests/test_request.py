from datetime import timedelta

import pytest
from pydantic import ValidationError

from app.models.enums import (
    RequestMode,
    RequestStatus,
    SensorType,
)
from app.models.geometry import (
    PointGeometry,
    PolygonGeometry,
)
from app.models.request import ObservationRequest


def valid_single_sar_request_data() -> dict:
    return {
        "request_id": "REQ-SAR-001",
        "name": "Obserwacja SAR Warszawy",
        "geometry": {
            "type": "Point",
            "coordinates": [21.0122, 52.2297],
        },
        "priority": 8,
        "earliest_start_utc": "2026-07-15T00:00:00Z",
        "latest_end_utc": "2026-07-15T12:00:00Z",
        "request_mode": "SINGLE",
        "requested_sensor_types": ["SAR"],
        "max_resolution_m": 1.0,
        "minimum_coverage_ratio": 1.0,
        "max_cloud_cover": None,
        "max_incidence_angle_deg": 45.0,
        "max_off_nadir_deg": 50.0,
        "status": "ACTIVE",
        "is_mandatory": False,
        "external_reference": "ORDER-001",
        "notes": None,
    }


def valid_single_optical_request_data() -> dict:
    data = valid_single_sar_request_data()

    data.update(
        {
            "request_id": "REQ-EO-001",
            "name": "Obserwacja optyczna Gdańska",
            "geometry": {
                "type": "Point",
                "coordinates": [18.6466, 54.3520],
            },
            "requested_sensor_types": ["OPTICAL"],
            "max_resolution_m": 0.5,
            "max_cloud_cover": 0.3,
            "max_incidence_angle_deg": None,
        }
    )

    return data


def valid_dual_required_request_data() -> dict:
    data = valid_single_sar_request_data()

    data.update(
        {
            "request_id": "REQ-DUAL-001",
            "name": "Podwójna obserwacja obszaru",
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [19.0, 52.0],
                        [20.0, 52.0],
                        [20.0, 53.0],
                        [19.0, 52.0],
                    ]
                ],
            },
            "request_mode": "DUAL_REQUIRED",
            "requested_sensor_types": [
                "SAR",
                "OPTICAL",
            ],
            "max_cloud_cover": 0.4,
        }
    )

    return data


def test_valid_single_sar_request_is_created() -> None:
    request = ObservationRequest(
        **valid_single_sar_request_data()
    )

    assert request.request_mode == RequestMode.SINGLE
    assert request.requested_sensor_types == [SensorType.SAR]
    assert request.status == RequestStatus.ACTIVE
    assert isinstance(request.geometry, PointGeometry)


def test_valid_single_optical_request_is_created() -> None:
    request = ObservationRequest(
        **valid_single_optical_request_data()
    )

    assert request.requires_optical is True
    assert request.requires_sar is False
    assert request.max_cloud_cover == pytest.approx(0.3)


def test_valid_dual_required_request_is_created() -> None:
    request = ObservationRequest(
        **valid_dual_required_request_data()
    )

    assert request.requires_sar is True
    assert request.requires_optical is True
    assert request.minimum_required_acquisitions == 2


def test_polygon_geometry_is_parsed() -> None:
    request = ObservationRequest(
        **valid_dual_required_request_data()
    )

    assert isinstance(request.geometry, PolygonGeometry)


def test_timestamps_are_normalized_to_utc() -> None:
    data = valid_single_sar_request_data()
    data["earliest_start_utc"] = (
        "2026-07-15T02:00:00+02:00"
    )

    request = ObservationRequest(**data)

    assert request.earliest_start_utc.hour == 0
    assert request.earliest_start_utc.utcoffset() == timedelta(0)


def test_invalid_time_window_is_rejected() -> None:
    data = valid_single_sar_request_data()
    data["latest_end_utc"] = data["earliest_start_utc"]

    with pytest.raises(ValidationError):
        ObservationRequest(**data)


def test_single_mode_rejects_two_sensor_types() -> None:
    data = valid_single_sar_request_data()
    data["requested_sensor_types"] = [
        "SAR",
        "OPTICAL",
    ]
    data["max_cloud_cover"] = 0.4

    with pytest.raises(ValidationError):
        ObservationRequest(**data)


def test_dual_optional_requires_both_sensor_types() -> None:
    data = valid_single_sar_request_data()
    data["request_mode"] = "DUAL_OPTIONAL"

    with pytest.raises(ValidationError):
        ObservationRequest(**data)


def test_duplicate_sensor_types_are_rejected() -> None:
    data = valid_single_sar_request_data()
    data["requested_sensor_types"] = [
        "SAR",
        "SAR",
    ]

    with pytest.raises(ValidationError):
        ObservationRequest(**data)


def test_optical_request_requires_cloud_limit() -> None:
    data = valid_single_optical_request_data()
    data["max_cloud_cover"] = None

    with pytest.raises(ValidationError):
        ObservationRequest(**data)


def test_sar_only_request_rejects_cloud_limit() -> None:
    data = valid_single_sar_request_data()
    data["max_cloud_cover"] = 0.2

    with pytest.raises(ValidationError):
        ObservationRequest(**data)


def test_optical_only_request_rejects_incidence_angle() -> None:
    data = valid_single_optical_request_data()
    data["max_incidence_angle_deg"] = 30.0

    with pytest.raises(ValidationError):
        ObservationRequest(**data)


def test_priority_outside_range_is_rejected() -> None:
    data = valid_single_sar_request_data()
    data["priority"] = 11

    with pytest.raises(ValidationError):
        ObservationRequest(**data)


def test_naive_datetime_is_rejected() -> None:
    data = valid_single_sar_request_data()
    data["earliest_start_utc"] = "2026-07-15T00:00:00"

    with pytest.raises(ValidationError):
        ObservationRequest(**data)


def test_acquisition_limits_depend_on_request_mode() -> None:
    single_request = ObservationRequest(
        **valid_single_sar_request_data()
    )
    dual_request = ObservationRequest(
        **valid_dual_required_request_data()
    )

    assert single_request.minimum_required_acquisitions == 1
    assert single_request.maximum_allowed_acquisitions == 1

    assert dual_request.minimum_required_acquisitions == 2
    assert dual_request.maximum_allowed_acquisitions == 2


def test_invalid_request_id_is_rejected() -> None:
    data = valid_single_sar_request_data()
    data["request_id"] = "request 1"

    with pytest.raises(ValidationError):
        ObservationRequest(**data)


def test_unknown_field_is_rejected() -> None:
    data = valid_single_sar_request_data()
    data["unknown_field"] = 123

    with pytest.raises(ValidationError):
        ObservationRequest(**data)