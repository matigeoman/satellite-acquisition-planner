from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.catalog_loader import load_system_catalog
from app.models.enums import (
    PlanningAlgorithm,
    RequestMode,
    ScheduleStatus,
    SensorType,
)
from app.opportunity_loader import load_opportunity_set
from app.planning.cp_sat import (
    CpSatPlannerConfig,
    CpSatScheduler,
    build_cp_sat_schedule,
)
from app.planning.greedy import (
    build_greedy_schedule,
)
from app.request_loader import load_request_set
from app.schedule_loader import (
    load_schedule,
    save_schedule,
)


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

FIXED_CREATED_AT = datetime(
    2026,
    7,
    14,
    22,
    30,
    0,
    tzinfo=timezone.utc,
)


@pytest.fixture(scope="module")
def reference_data():
    catalog = load_system_catalog(
        CATALOG_PATH
    )

    request_set = load_request_set(
        REQUEST_SET_PATH
    )

    opportunity_set = load_opportunity_set(
        OPPORTUNITY_SET_PATH,
        catalog=catalog,
        request_set=request_set,
    )

    return (
        catalog,
        request_set,
        opportunity_set,
    )


@pytest.fixture(scope="module")
def cp_sat_result(reference_data):
    catalog, request_set, opportunity_set = (
        reference_data
    )

    scheduler = CpSatScheduler(
        catalog=catalog,
        request_set=request_set,
        opportunity_set=opportunity_set,
        config=CpSatPlannerConfig(
            max_time_s=30.0,
            num_search_workers=1,
        ),
    )

    schedule = scheduler.build_schedule(
        created_at_utc=FIXED_CREATED_AT,
    )

    return scheduler, schedule


def group_entries_by_request(
    schedule,
) -> dict:
    grouped = defaultdict(list)

    for entry in schedule.active_entries:
        grouped[entry.request_id].append(
            entry
        )

    return grouped


def test_cp_sat_builds_nonempty_schedule(
    cp_sat_result,
) -> None:
    _, schedule = cp_sat_result

    assert schedule.total_acquisitions > 0
    assert schedule.algorithm == PlanningAlgorithm.CP_SAT
    assert schedule.objective_value is not None
    assert schedule.objective_value > 0.0


def test_solver_returns_feasible_or_optimal_status(
    cp_sat_result,
) -> None:
    scheduler, _ = cp_sat_result

    assert scheduler.last_solver_status in {
        "FEASIBLE",
        "OPTIMAL",
    }


def test_example_requests_are_fully_scheduled(
    cp_sat_result,
) -> None:
    _, schedule = cp_sat_result

    assert schedule.status == ScheduleStatus.FEASIBLE
    assert len(schedule.scheduled_request_ids) == 20
    assert schedule.total_acquisitions == 24
    assert schedule.unassigned_request_ids == []


def test_schedule_uses_only_feasible_opportunities(
    reference_data,
    cp_sat_result,
) -> None:
    _, _, opportunity_set = reference_data
    _, schedule = cp_sat_result

    feasible_ids = {
        opportunity.opportunity_id
        for opportunity
        in opportunity_set.feasible_opportunities
    }

    assert all(
        entry.opportunity_id in feasible_ids
        for entry in schedule.active_entries
    )


def test_schedule_entries_match_opportunities(
    reference_data,
    cp_sat_result,
) -> None:
    _, _, opportunity_set = reference_data
    _, schedule = cp_sat_result

    opportunities = {
        opportunity.opportunity_id: opportunity
        for opportunity in opportunity_set.opportunities
    }

    for entry in schedule.active_entries:
        opportunity = opportunities[
            entry.opportunity_id
        ]

        assert entry.request_id == opportunity.request_id
        assert entry.satellite_id == opportunity.satellite_id
        assert entry.sensor_id == opportunity.sensor_id
        assert entry.mode_id == opportunity.mode_id
        assert entry.start_utc == opportunity.start_utc
        assert entry.end_utc == opportunity.end_utc


def test_single_requests_have_at_most_one_entry(
    reference_data,
    cp_sat_result,
) -> None:
    _, request_set, _ = reference_data
    _, schedule = cp_sat_result

    grouped = group_entries_by_request(
        schedule
    )

    for request in request_set.active_requests:
        if request.request_mode == RequestMode.SINGLE:
            assert len(
                grouped[request.request_id]
            ) <= 1


def test_dual_optional_requests_use_at_most_one_per_sensor(
    reference_data,
    cp_sat_result,
) -> None:
    _, request_set, _ = reference_data
    _, schedule = cp_sat_result

    grouped = group_entries_by_request(
        schedule
    )

    for request in request_set.active_requests:
        if (
            request.request_mode
            != RequestMode.DUAL_OPTIONAL
        ):
            continue

        entries = grouped[
            request.request_id
        ]

        assert len(entries) <= 2

        sensor_types = [
            entry.sensor_type
            for entry in entries
        ]

        assert len(sensor_types) == len(
            set(sensor_types)
        )


def test_dual_required_requests_are_atomic(
    reference_data,
    cp_sat_result,
) -> None:
    _, request_set, _ = reference_data
    _, schedule = cp_sat_result

    grouped = group_entries_by_request(
        schedule
    )

    for request in request_set.dual_required_requests:
        entries = grouped[
            request.request_id
        ]

        assert len(entries) in {0, 2}

        if entries:
            assert {
                entry.sensor_type
                for entry in entries
            } == {
                SensorType.SAR,
                SensorType.OPTICAL,
            }


def test_mandatory_requests_are_satisfied(
    reference_data,
    cp_sat_result,
) -> None:
    _, request_set, _ = reference_data
    _, schedule = cp_sat_result

    scheduled_ids = set(
        schedule.scheduled_request_ids
    )

    assert all(
        request.request_id in scheduled_ids
        for request in request_set.mandatory_requests
    )


def test_transition_times_are_respected(
    reference_data,
    cp_sat_result,
) -> None:
    catalog, _, _ = reference_data
    _, schedule = cp_sat_result

    for satellite in catalog.satellites:
        sensor = catalog.get_sensor(
            satellite.sensor_id
        )

        transition_time_s = max(
            satellite.minimum_transition_time_s,
            sensor.warmup_time_s
            + sensor.cooldown_time_s,
        )

        entries = sorted(
            [
                entry
                for entry in schedule.active_entries
                if entry.satellite_id
                == satellite.satellite_id
            ],
            key=lambda entry: entry.start_utc,
        )

        for previous, current in zip(
            entries,
            entries[1:],
        ):
            assert (
                current.start_utc
                >= previous.end_utc
                + timedelta(
                    seconds=transition_time_s
                )
            )


def test_memory_limits_are_respected(
    reference_data,
    cp_sat_result,
) -> None:
    catalog, _, _ = reference_data
    _, schedule = cp_sat_result

    for satellite in catalog.satellites:
        generated_data_mb = sum(
            entry.estimated_data_volume_mb
            for entry in schedule.active_entries
            if entry.satellite_id
            == satellite.satellite_id
        )

        planning_limit_mb = (
            satellite.memory_capacity_mb
            * (
                1.0
                - schedule.memory_reserve_ratio
            )
        )

        assert (
            satellite.initial_memory_usage_mb
            + generated_data_mb
            <= planning_limit_mb + 1e-6
        )


def test_acquisition_count_limits_are_respected(
    reference_data,
    cp_sat_result,
) -> None:
    catalog, _, _ = reference_data
    _, schedule = cp_sat_result

    for satellite in catalog.satellites:
        count = sum(
            entry.satellite_id
            == satellite.satellite_id
            for entry in schedule.active_entries
        )

        assert (
            count
            <= satellite.max_acquisitions_per_day
        )


def test_imaging_time_limits_are_respected(
    reference_data,
    cp_sat_result,
) -> None:
    catalog, _, _ = reference_data
    _, schedule = cp_sat_result

    for satellite in catalog.satellites:
        imaging_time_s = sum(
            entry.duration_s
            for entry in schedule.active_entries
            if entry.satellite_id
            == satellite.satellite_id
        )

        assert (
            imaging_time_s
            <= satellite.max_imaging_time_per_day_s
            + 1e-6
        )


def test_objective_value_matches_entries(
    cp_sat_result,
) -> None:
    _, schedule = cp_sat_result

    expected_value = round(
        sum(
            entry.objective_contribution
            for entry in schedule.active_entries
        ),
        6,
    )

    assert schedule.objective_value == pytest.approx(
        expected_value
    )


def test_cp_sat_is_not_worse_than_greedy(
    reference_data,
    cp_sat_result,
) -> None:
    catalog, request_set, opportunity_set = (
        reference_data
    )

    _, cp_sat_schedule = cp_sat_result

    greedy_schedule = build_greedy_schedule(
        catalog=catalog,
        request_set=request_set,
        opportunity_set=opportunity_set,
        created_at_utc=FIXED_CREATED_AT,
    )

    assert (
        cp_sat_schedule.objective_value
        >= greedy_schedule.objective_value
        - 1e-6
    )


def test_cp_sat_is_deterministic(
    reference_data,
    cp_sat_result,
) -> None:
    catalog, request_set, opportunity_set = (
        reference_data
    )

    _, first_schedule = cp_sat_result

    second_schedule = build_cp_sat_schedule(
        catalog=catalog,
        request_set=request_set,
        opportunity_set=opportunity_set,
        config=CpSatPlannerConfig(
            max_time_s=30.0,
            num_search_workers=1,
            random_seed=20260715,
        ),
        schedule_id="SCHEDULE-CP-SAT-002",
        created_at_utc=FIXED_CREATED_AT,
    )

    first_ids = [
        entry.opportunity_id
        for entry in first_schedule.entries
    ]

    second_ids = [
        entry.opportunity_id
        for entry in second_schedule.entries
    ]

    assert first_ids == second_ids

    assert (
        first_schedule.objective_value
        == second_schedule.objective_value
    )


def test_full_memory_reserve_makes_model_infeasible(
    reference_data,
) -> None:
    catalog, request_set, opportunity_set = (
        reference_data
    )

    scheduler = CpSatScheduler(
        catalog=catalog,
        request_set=request_set,
        opportunity_set=opportunity_set,
        config=CpSatPlannerConfig(
            memory_reserve_ratio=1.0,
            max_time_s=10.0,
        ),
    )

    schedule = scheduler.build_schedule(
        schedule_id="SCHEDULE-CP-SAT-NOMEM",
        created_at_utc=FIXED_CREATED_AT,
    )

    assert scheduler.last_solver_status == "INFEASIBLE"
    assert schedule.status == ScheduleStatus.INFEASIBLE
    assert schedule.total_acquisitions == 0
    assert len(schedule.unassigned_request_ids) == 20


def test_invalid_memory_reserve_is_rejected() -> None:
    with pytest.raises(ValueError):
        CpSatPlannerConfig(
            memory_reserve_ratio=1.1
        )


def test_invalid_time_limit_is_rejected() -> None:
    with pytest.raises(ValueError):
        CpSatPlannerConfig(
            max_time_s=0.0
        )


def test_invalid_worker_count_is_rejected() -> None:
    with pytest.raises(ValueError):
        CpSatPlannerConfig(
            num_search_workers=0
        )


def test_invalid_objective_scale_is_rejected() -> None:
    with pytest.raises(ValueError):
        CpSatPlannerConfig(
            objective_scale=0
        )


def test_negative_weight_is_rejected() -> None:
    with pytest.raises(ValueError):
        CpSatPlannerConfig(
            quality_weight=-1.0
        )


def test_schedule_save_and_load_roundtrip(
    tmp_path: Path,
    cp_sat_result,
) -> None:
    _, schedule = cp_sat_result

    schedule_path = (
        tmp_path
        / "cp_sat_schedule.json"
    )

    save_schedule(
        schedule,
        schedule_path,
    )

    loaded_schedule = load_schedule(
        schedule_path
    )

    assert (
        loaded_schedule.model_dump(mode="json")
        == schedule.model_dump(mode="json")
    )