import json
from copy import deepcopy
from datetime import timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.models.request_set import ObservationRequestSet
from app.request_loader import load_request_set


PROJECT_DIRECTORY = Path(__file__).resolve().parents[1]

REQUEST_SET_PATH = (
    PROJECT_DIRECTORY
    / "data"
    / "example_requests.json"
)


def valid_request_set_data() -> dict:
    return json.loads(
        REQUEST_SET_PATH.read_text(
            encoding="utf-8",
        )
    )


def test_example_request_set_is_loaded() -> None:
    request_set = load_request_set(
        REQUEST_SET_PATH
    )

    assert request_set.request_set_id == "REQSET-PL-DEMO"
    assert request_set.version == "1.0.0"


def test_request_set_contains_twenty_requests() -> None:
    request_set = load_request_set(
        REQUEST_SET_PATH
    )

    assert len(request_set.requests) == 20
    assert len(request_set.active_requests) == 20


def test_request_mode_counts_are_correct() -> None:
    request_set = load_request_set(
        REQUEST_SET_PATH
    )

    assert request_set.request_mode_counts == {
        "SINGLE": 16,
        "DUAL_OPTIONAL": 2,
        "DUAL_REQUIRED": 2,
    }


def test_geometry_type_counts_are_correct() -> None:
    request_set = load_request_set(
        REQUEST_SET_PATH
    )

    assert request_set.geometry_type_counts == {
        "Point": 12,
        "Polygon": 8,
    }


def test_sensor_demand_counts_are_correct() -> None:
    request_set = load_request_set(
        REQUEST_SET_PATH
    )

    assert len(
        request_set.requests_requiring_sar
    ) == 12

    assert len(
        request_set.requests_requiring_optical
    ) == 12


def test_mandatory_request_count_is_correct() -> None:
    request_set = load_request_set(
        REQUEST_SET_PATH
    )

    assert len(request_set.mandatory_requests) == 4
    assert len(request_set.dual_required_requests) == 2


def test_get_request_returns_requested_object() -> None:
    request_set = load_request_set(
        REQUEST_SET_PATH
    )

    request = request_set.get_request(
        "REQ-SAR-003"
    )

    assert request.request_id == "REQ-SAR-003"
    assert request.name == "Obserwacja SAR Krakowa"


def test_get_unknown_request_raises_key_error() -> None:
    request_set = load_request_set(
        REQUEST_SET_PATH
    )

    with pytest.raises(KeyError):
        request_set.get_request(
            "REQ-MISSING-001"
        )


def test_all_requests_are_inside_horizon() -> None:
    request_set = load_request_set(
        REQUEST_SET_PATH
    )

    for request in request_set.requests:
        assert (
            request.earliest_start_utc
            >= request_set.horizon_start_utc
        )
        assert (
            request.latest_end_utc
            <= request_set.horizon_end_utc
        )


def test_duplicate_request_ids_are_rejected() -> None:
    data = valid_request_set_data()

    duplicated_request = deepcopy(
        data["requests"][0]
    )

    data["requests"].append(
        duplicated_request
    )

    with pytest.raises(ValidationError):
        ObservationRequestSet(**data)


def test_request_before_horizon_is_rejected() -> None:
    data = valid_request_set_data()

    data["requests"][0][
        "earliest_start_utc"
    ] = "2026-07-14T23:00:00Z"

    with pytest.raises(ValidationError):
        ObservationRequestSet(**data)


def test_request_after_horizon_is_rejected() -> None:
    data = valid_request_set_data()

    data["requests"][0][
        "latest_end_utc"
    ] = "2026-07-16T01:00:00Z"

    with pytest.raises(ValidationError):
        ObservationRequestSet(**data)


def test_invalid_horizon_is_rejected() -> None:
    data = valid_request_set_data()

    data["horizon_end_utc"] = (
        data["horizon_start_utc"]
    )

    with pytest.raises(ValidationError):
        ObservationRequestSet(**data)


def test_naive_horizon_datetime_is_rejected() -> None:
    data = valid_request_set_data()

    data["horizon_start_utc"] = (
        "2026-07-15T00:00:00"
    )

    with pytest.raises(ValidationError):
        ObservationRequestSet(**data)


def test_horizon_timestamps_are_normalized_to_utc() -> None:
    data = valid_request_set_data()

    data["horizon_start_utc"] = (
        "2026-07-15T02:00:00+02:00"
    )
    data["horizon_end_utc"] = (
        "2026-07-16T02:00:00+02:00"
    )

    request_set = ObservationRequestSet(
        **data
    )

    assert request_set.horizon_start_utc.hour == 0
    assert (
        request_set.horizon_start_utc.utcoffset()
        == timedelta(0)
    )


def test_missing_request_file_is_rejected(
    tmp_path: Path,
) -> None:
    missing_path = (
        tmp_path
        / "missing.json"
    )

    with pytest.raises(FileNotFoundError):
        load_request_set(missing_path)


def test_directory_path_is_rejected(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError):
        load_request_set(tmp_path)


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
        load_request_set(invalid_path)


def test_empty_request_list_is_rejected() -> None:
    data = valid_request_set_data()
    data["requests"] = []

    with pytest.raises(ValidationError):
        ObservationRequestSet(**data)


def test_unknown_request_set_field_is_rejected() -> None:
    data = valid_request_set_data()
    data["unknown_field"] = 123

    with pytest.raises(ValidationError):
        ObservationRequestSet(**data)