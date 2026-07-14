import json
from copy import deepcopy
from datetime import timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.catalog_loader import load_system_catalog
from app.models.opportunity_set import AcquisitionOpportunitySet
from app.opportunity_loader import load_opportunity_set
from app.request_loader import load_request_set


PROJECT_DIRECTORY = Path(__file__).resolve().parents[1]

CATALOG_PATH = (
    PROJECT_DIRECTORY
    / "data"
    / "example_system.json"
)

REQUEST_SET_PATH = (
    PROJECT_DIRECTORY
    / "data"
    / "example_requests.json"
)

OPPORTUNITY_SET_PATH = (
    PROJECT_DIRECTORY
    / "data"
    / "example_opportunities.json"
)


def valid_opportunity_set_data() -> dict:
    return json.loads(
        OPPORTUNITY_SET_PATH.read_text(
            encoding="utf-8",
        )
    )


def load_reference_data():
    catalog = load_system_catalog(
        CATALOG_PATH
    )

    request_set = load_request_set(
        REQUEST_SET_PATH
    )

    return catalog, request_set


def test_example_opportunity_set_is_loaded() -> None:
    opportunity_set = load_opportunity_set(
        OPPORTUNITY_SET_PATH
    )

    assert opportunity_set.opportunity_set_id == (
        "OPPSET-PL-DEMO"
    )
    assert opportunity_set.version == "1.0.0"


def test_opportunity_set_contains_two_hundred_opportunities() -> None:
    opportunity_set = load_opportunity_set(
        OPPORTUNITY_SET_PATH
    )

    assert len(opportunity_set.opportunities) == 200


def test_sensor_type_counts_are_balanced() -> None:
    opportunity_set = load_opportunity_set(
        OPPORTUNITY_SET_PATH
    )

    assert opportunity_set.sensor_type_counts == {
        "SAR": 100,
        "OPTICAL": 100,
    }


def test_satellite_counts_are_balanced() -> None:
    opportunity_set = load_opportunity_set(
        OPPORTUNITY_SET_PATH
    )

    assert opportunity_set.satellite_counts == {
        "SAR-01": 25,
        "SAR-02": 25,
        "SAR-03": 25,
        "SAR-04": 25,
        "EO-01": 50,
        "EO-02": 50,
    }


def test_each_request_has_ten_opportunities() -> None:
    opportunity_set = load_opportunity_set(
        OPPORTUNITY_SET_PATH
    )

    assert len(opportunity_set.request_counts) == 20

    assert set(
        opportunity_set.request_counts.values()
    ) == {10}


def test_set_contains_feasible_and_infeasible_opportunities() -> None:
    opportunity_set = load_opportunity_set(
        OPPORTUNITY_SET_PATH
    )

    assert opportunity_set.feasible_opportunities
    assert opportunity_set.infeasible_opportunities

    assert (
        len(opportunity_set.feasible_opportunities)
        + len(opportunity_set.infeasible_opportunities)
        == 200
    )


def test_get_opportunity_returns_requested_object() -> None:
    opportunity_set = load_opportunity_set(
        OPPORTUNITY_SET_PATH
    )

    opportunity = opportunity_set.get_opportunity(
        "OPP-SAR-0001"
    )

    assert opportunity.opportunity_id == "OPP-SAR-0001"
    assert opportunity.request_id == "REQ-SAR-001"


def test_get_unknown_opportunity_raises_key_error() -> None:
    opportunity_set = load_opportunity_set(
        OPPORTUNITY_SET_PATH
    )

    with pytest.raises(KeyError):
        opportunity_set.get_opportunity(
            "OPP-SAR-9999"
        )


def test_references_validate_against_catalog_and_requests() -> None:
    catalog, request_set = load_reference_data()

    opportunity_set = load_opportunity_set(
        OPPORTUNITY_SET_PATH,
        catalog=catalog,
        request_set=request_set,
    )

    assert len(opportunity_set.opportunities) == 200


def test_duplicate_opportunity_ids_are_rejected() -> None:
    data = valid_opportunity_set_data()

    duplicated_opportunity = deepcopy(
        data["opportunities"][0]
    )

    data["opportunities"].append(
        duplicated_opportunity
    )

    with pytest.raises(ValidationError):
        AcquisitionOpportunitySet(**data)


def test_opportunity_before_horizon_is_rejected() -> None:
    data = valid_opportunity_set_data()

    data["opportunities"][0]["start_utc"] = (
        "2026-07-14T23:59:00Z"
    )

    with pytest.raises(ValidationError):
        AcquisitionOpportunitySet(**data)


def test_opportunity_after_horizon_is_rejected() -> None:
    data = valid_opportunity_set_data()

    data["opportunities"][0]["end_utc"] = (
        "2026-07-16T00:00:01Z"
    )

    with pytest.raises(ValidationError):
        AcquisitionOpportunitySet(**data)


def test_invalid_horizon_is_rejected() -> None:
    data = valid_opportunity_set_data()

    data["horizon_end_utc"] = (
        data["horizon_start_utc"]
    )

    with pytest.raises(ValidationError):
        AcquisitionOpportunitySet(**data)


def test_naive_horizon_datetime_is_rejected() -> None:
    data = valid_opportunity_set_data()

    data["horizon_start_utc"] = (
        "2026-07-15T00:00:00"
    )

    with pytest.raises(ValidationError):
        AcquisitionOpportunitySet(**data)


def test_horizon_timestamps_are_normalized_to_utc() -> None:
    data = valid_opportunity_set_data()

    data["horizon_start_utc"] = (
        "2026-07-15T02:00:00+02:00"
    )

    data["horizon_end_utc"] = (
        "2026-07-16T02:00:00+02:00"
    )

    opportunity_set = AcquisitionOpportunitySet(
        **data
    )

    assert opportunity_set.horizon_start_utc.hour == 0

    assert (
        opportunity_set.horizon_start_utc.utcoffset()
        == timedelta(0)
    )


def test_missing_opportunity_file_is_rejected(
    tmp_path: Path,
) -> None:
    missing_path = (
        tmp_path
        / "missing.json"
    )

    with pytest.raises(FileNotFoundError):
        load_opportunity_set(missing_path)


def test_directory_path_is_rejected(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError):
        load_opportunity_set(tmp_path)


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
        load_opportunity_set(invalid_path)


def test_missing_request_reference_is_rejected() -> None:
    data = valid_opportunity_set_data()

    data["opportunities"][0]["request_id"] = (
        "REQ-MISSING-001"
    )

    opportunity_set = AcquisitionOpportunitySet(
        **data
    )

    catalog, request_set = load_reference_data()

    with pytest.raises(ValueError):
        opportunity_set.validate_against(
            catalog,
            request_set,
        )


def test_missing_sensor_reference_is_rejected() -> None:
    data = valid_opportunity_set_data()

    data["opportunities"][0]["sensor_id"] = (
        "SENSOR-SAR-MISSING"
    )

    opportunity_set = AcquisitionOpportunitySet(
        **data
    )

    catalog, request_set = load_reference_data()

    with pytest.raises(ValueError):
        opportunity_set.validate_against(
            catalog,
            request_set,
        )


def test_feasible_constraint_violation_is_rejected() -> None:
    data = valid_opportunity_set_data()

    feasible_opportunity = next(
        opportunity
        for opportunity in data["opportunities"]
        if opportunity["is_feasible"]
    )

    feasible_opportunity["coverage_ratio"] = 0.01

    opportunity_set = AcquisitionOpportunitySet(
        **data
    )

    catalog, request_set = load_reference_data()

    with pytest.raises(ValueError):
        opportunity_set.validate_against(
            catalog,
            request_set,
        )


def test_invalid_data_volume_is_rejected() -> None:
    data = valid_opportunity_set_data()

    data["opportunities"][0][
        "estimated_data_volume_mb"
    ] += 100.0

    opportunity_set = AcquisitionOpportunitySet(
        **data
    )

    catalog, request_set = load_reference_data()

    with pytest.raises(ValueError):
        opportunity_set.validate_against(
            catalog,
            request_set,
        )


def test_empty_opportunity_list_is_rejected() -> None:
    data = valid_opportunity_set_data()

    data["opportunities"] = []

    with pytest.raises(ValidationError):
        AcquisitionOpportunitySet(**data)


def test_unknown_opportunity_set_field_is_rejected() -> None:
    data = valid_opportunity_set_data()

    data["unknown_field"] = 123

    with pytest.raises(ValidationError):
        AcquisitionOpportunitySet(**data)