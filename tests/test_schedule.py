from copy import deepcopy
from datetime import timedelta

import pytest
from pydantic import ValidationError

from app.models.enums import (
    PlanningAlgorithm,
    ScheduleEntryStatus,
    ScheduleStatus,
    SensorType,
)
from app.models.schedule import Schedule, ScheduleEntry


def valid_sar_entry_data() -> dict:
    return {
        "entry_id": "ENTRY-SAR-001",
        "opportunity_id": "OPP-SAR-001",
        "request_id": "REQ-SAR-001",
        "satellite_id": "SAR-01",
        "sensor_id": "SENSOR-SAR-X",
        "mode_id": "MODE-SAR-HR",
        "sensor_type": "SAR",
        "start_utc": "2026-07-15T06:00:00Z",
        "end_utc": "2026-07-15T06:00:30Z",
        "status": "PLANNED",
        "estimated_data_volume_mb": 750.0,
        "objective_contribution": 8.5,
        "lock_reason": None,
        "notes": None,
    }


def valid_eo_entry_data() -> dict:
    return {
        "entry_id": "ENTRY-EO-001",
        "opportunity_id": "OPP-EO-001",
        "request_id": "REQ-EO-001",
        "satellite_id": "EO-01",
        "sensor_id": "SENSOR-EO-HR",
        "mode_id": "MODE-OPT-PAN",
        "sensor_type": "OPTICAL",
        "start_utc": "2026-07-15T08:00:00Z",
        "end_utc": "2026-07-15T08:00:20Z",
        "status": "PLANNED",
        "estimated_data_volume_mb": 360.0,
        "objective_contribution": 7.0,
        "lock_reason": None,
        "notes": None,
    }


def valid_schedule_data() -> dict:
    return {
        "schedule_id": "SCHEDULE-001",
        "name": "Dobowy harmonogram akwizycji",
        "horizon_start_utc": "2026-07-15T00:00:00Z",
        "horizon_end_utc": "2026-07-16T00:00:00Z",
        "created_at_utc": "2026-07-14T20:00:00Z",
        "algorithm": "GREEDY",
        "status": "FEASIBLE",
        "entries": [
            valid_sar_entry_data(),
            valid_eo_entry_data(),
        ],
        "frozen_until_utc": "2026-07-15T02:00:00Z",
        "memory_reserve_ratio": 0.0,
        "objective_value": 15.5,
        "solver_runtime_s": 0.05,
        "unassigned_request_ids": [
            "REQ-UNASSIGNED-001",
        ],
        "notes": None,
    }


def test_valid_schedule_is_created() -> None:
    schedule = Schedule(**valid_schedule_data())

    assert schedule.algorithm == PlanningAlgorithm.GREEDY
    assert schedule.status == ScheduleStatus.FEASIBLE
    assert schedule.total_acquisitions == 2
    assert schedule.satellites_used == ["EO-01", "SAR-01"]


def test_entry_duration_is_calculated() -> None:
    entry = ScheduleEntry(**valid_sar_entry_data())

    assert entry.duration_s == pytest.approx(30.0)


def test_schedule_summary_is_calculated() -> None:
    schedule = Schedule(**valid_schedule_data())

    assert schedule.total_duration_s == pytest.approx(50.0)
    assert schedule.total_data_volume_mb == pytest.approx(1110.0)
    assert schedule.total_objective_contribution == pytest.approx(15.5)
    assert schedule.scheduled_request_ids == [
        "REQ-EO-001",
        "REQ-SAR-001",
    ]


def test_entry_timestamps_are_normalized_to_utc() -> None:
    data = valid_sar_entry_data()
    data["start_utc"] = "2026-07-15T08:00:00+02:00"
    data["end_utc"] = "2026-07-15T08:00:30+02:00"

    entry = ScheduleEntry(**data)

    assert entry.start_utc.hour == 6
    assert entry.start_utc.utcoffset() == timedelta(0)


def test_invalid_entry_time_window_is_rejected() -> None:
    data = valid_sar_entry_data()
    data["end_utc"] = data["start_utc"]

    with pytest.raises(ValidationError):
        ScheduleEntry(**data)


def test_entry_sensor_type_must_match_platform() -> None:
    data = valid_sar_entry_data()
    data["satellite_id"] = "EO-01"

    with pytest.raises(ValidationError):
        ScheduleEntry(**data)


def test_frozen_entry_requires_lock_reason() -> None:
    data = valid_sar_entry_data()
    data["status"] = "FROZEN"
    data["lock_reason"] = None

    with pytest.raises(ValidationError):
        ScheduleEntry(**data)


def test_planned_entry_rejects_lock_reason() -> None:
    data = valid_sar_entry_data()
    data["status"] = "PLANNED"
    data["lock_reason"] = "Ręczne zablokowanie"

    with pytest.raises(ValidationError):
        ScheduleEntry(**data)


def test_invalid_schedule_horizon_is_rejected() -> None:
    data = valid_schedule_data()
    data["horizon_end_utc"] = data["horizon_start_utc"]

    with pytest.raises(ValidationError):
        Schedule(**data)


def test_duplicate_entry_ids_are_rejected() -> None:
    data = valid_schedule_data()

    second_entry = deepcopy(valid_sar_entry_data())
    second_entry["opportunity_id"] = "OPP-SAR-002"
    second_entry["request_id"] = "REQ-SAR-002"
    second_entry["start_utc"] = "2026-07-15T07:00:00Z"
    second_entry["end_utc"] = "2026-07-15T07:00:30Z"

    data["entries"] = [
        valid_sar_entry_data(),
        second_entry,
    ]

    with pytest.raises(ValidationError):
        Schedule(**data)


def test_duplicate_opportunity_ids_are_rejected() -> None:
    data = valid_schedule_data()

    second_entry = deepcopy(valid_sar_entry_data())
    second_entry["entry_id"] = "ENTRY-SAR-002"
    second_entry["request_id"] = "REQ-SAR-002"
    second_entry["start_utc"] = "2026-07-15T07:00:00Z"
    second_entry["end_utc"] = "2026-07-15T07:00:30Z"

    data["entries"] = [
        valid_sar_entry_data(),
        second_entry,
    ]

    with pytest.raises(ValidationError):
        Schedule(**data)


def test_entry_outside_horizon_is_rejected() -> None:
    data = valid_schedule_data()
    data["entries"][0]["start_utc"] = "2026-07-14T23:59:00Z"
    data["entries"][0]["end_utc"] = "2026-07-15T00:00:30Z"

    with pytest.raises(ValidationError):
        Schedule(**data)


def test_overlapping_entries_for_same_satellite_are_rejected() -> None:
    data = valid_schedule_data()

    second_entry = deepcopy(valid_sar_entry_data())
    second_entry["entry_id"] = "ENTRY-SAR-002"
    second_entry["opportunity_id"] = "OPP-SAR-002"
    second_entry["request_id"] = "REQ-SAR-002"
    second_entry["start_utc"] = "2026-07-15T06:00:20Z"
    second_entry["end_utc"] = "2026-07-15T06:00:50Z"

    data["entries"] = [
        valid_sar_entry_data(),
        second_entry,
    ]

    with pytest.raises(ValidationError):
        Schedule(**data)


def test_overlapping_entries_for_different_satellites_are_allowed() -> None:
    data = valid_schedule_data()

    eo_entry = valid_eo_entry_data()
    eo_entry["start_utc"] = "2026-07-15T06:00:10Z"
    eo_entry["end_utc"] = "2026-07-15T06:00:25Z"

    data["entries"] = [
        valid_sar_entry_data(),
        eo_entry,
    ]

    schedule = Schedule(**data)

    assert schedule.total_acquisitions == 2


def test_adjacent_entries_for_same_satellite_are_allowed() -> None:
    data = valid_schedule_data()

    second_entry = deepcopy(valid_sar_entry_data())
    second_entry["entry_id"] = "ENTRY-SAR-002"
    second_entry["opportunity_id"] = "OPP-SAR-002"
    second_entry["request_id"] = "REQ-SAR-002"
    second_entry["start_utc"] = "2026-07-15T06:00:30Z"
    second_entry["end_utc"] = "2026-07-15T06:01:00Z"

    data["entries"] = [
        valid_sar_entry_data(),
        second_entry,
    ]

    schedule = Schedule(**data)

    assert schedule.total_acquisitions == 2


def test_entry_inside_frozen_window_must_be_frozen() -> None:
    data = valid_schedule_data()

    early_entry = valid_sar_entry_data()
    early_entry["start_utc"] = "2026-07-15T01:00:00Z"
    early_entry["end_utc"] = "2026-07-15T01:00:30Z"

    data["entries"] = [early_entry]

    with pytest.raises(ValidationError):
        Schedule(**data)


def test_frozen_entry_outside_frozen_window_is_rejected() -> None:
    data = valid_schedule_data()

    frozen_entry = valid_sar_entry_data()
    frozen_entry["status"] = "FROZEN"
    frozen_entry["lock_reason"] = "Zamrożony plan operacyjny"

    data["entries"] = [frozen_entry]

    with pytest.raises(ValidationError):
        Schedule(**data)


def test_final_schedule_requires_objective_value() -> None:
    data = valid_schedule_data()
    data["status"] = "FINAL"
    data["objective_value"] = None

    with pytest.raises(ValidationError):
        Schedule(**data)


def test_request_cannot_be_scheduled_and_unassigned() -> None:
    data = valid_schedule_data()
    data["unassigned_request_ids"] = [
        "REQ-SAR-001",
    ]

    with pytest.raises(ValidationError):
        Schedule(**data)


def test_duplicate_unassigned_request_ids_are_rejected() -> None:
    data = valid_schedule_data()
    data["unassigned_request_ids"] = [
        "REQ-UNASSIGNED-001",
        "REQ-UNASSIGNED-001",
    ]

    with pytest.raises(ValidationError):
        Schedule(**data)


def test_cancelled_entry_is_ignored_in_totals() -> None:
    data = valid_schedule_data()
    data["entries"][0]["status"] = "CANCELLED"

    schedule = Schedule(**data)

    assert schedule.total_acquisitions == 1
    assert schedule.total_duration_s == pytest.approx(20.0)
    assert schedule.total_data_volume_mb == pytest.approx(360.0)


def test_unknown_schedule_field_is_rejected() -> None:
    data = valid_schedule_data()
    data["unknown_field"] = 123

    with pytest.raises(ValidationError):
        Schedule(**data)