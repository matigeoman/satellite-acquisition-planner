from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.catalog_loader import load_system_catalog
from app.models.enums import (
    RequestMode,
    ScheduleStatus,
    SensorType,
)
from app.opportunity_loader import load_opportunity_set
from app.planning.greedy import (
    GreedyPlannerConfig,
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
    0,
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
def greedy_schedule(reference_data):
    catalog, request_set, opportunity_set = (
        reference_data
    )

    return build_greedy_schedule(
        catalog=catalog,
        request_set=request_set,
        opportunity_set=opportunity_set,
        created_at_utc=FIXED_CREATED_AT,
    )


def group_entries_by_request(
    schedule,
) -> dict:
    grouped = defaultdict(list)

    for entry in schedule.active_entries:
        grouped[entry.request_id].append(
            entry
        )

    return grouped


def acquisition_score(
    opportunity,
    config: GreedyPlannerConfig,
) -> float:
    return round(
        opportunity.quality_score
        * config.quality_weight
        + opportunity.coverage_ratio
        * config.coverage_weight,
        6,
    )


def request_reward(
    request,
    config: GreedyPlannerConfig,
) -> float:
    reward = (
        request.priority
        * config.priority_weight
    )

    if request.is_mandatory:
        reward += config.mandatory_bonus

    return round(
        reward,
        6,
    )


def test_greedy_builds_nonempty_schedule(
    greedy_schedule,
) -> None:
    assert greedy_schedule.total_acquisitions > 0
    assert greedy_schedule.objective_value is not None
    assert greedy_schedule.objective_value > 0.0


def test_schedule_uses_only_feasible_opportunities(
    reference_data,
    greedy_schedule,
) -> None:
    _, _, opportunity_set = reference_data

    feasible_ids = {
        opportunity.opportunity_id
        for opportunity
        in opportunity_set.feasible_opportunities
    }

    assert all(
        entry.opportunity_id in feasible_ids
        for entry in greedy_schedule.active_entries
    )


def test_schedule_entries_match_opportunities(
    reference_data,
    greedy_schedule,
) -> None:
    _, _, opportunity_set = reference_data

    opportunities = {
        opportunity.opportunity_id: opportunity
        for opportunity in opportunity_set.opportunities
    }

    for entry in greedy_schedule.active_entries:
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
    greedy_schedule,
) -> None:
    _, request_set, _ = reference_data

    grouped = group_entries_by_request(
        greedy_schedule
    )

    for request in request_set.active_requests:
        if request.request_mode == RequestMode.SINGLE:
            assert len(grouped[request.request_id]) <= 1


def test_dual_optional_requests_use_at_most_one_per_sensor(
    reference_data,
    greedy_schedule,
) -> None:
    _, request_set, _ = reference_data

    grouped = group_entries_by_request(
        greedy_schedule
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
    greedy_schedule,
) -> None:
    _, request_set, _ = reference_data

    grouped = group_entries_by_request(
        greedy_schedule
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


def test_transition_times_are_respected(
    reference_data,
    greedy_schedule,
) -> None:
    catalog, _, _ = reference_data

    for satellite in catalog.satellites:
        sensor = catalog.get_sensor(
            satellite.sensor_id
        )

        required_transition_s = max(
            satellite.minimum_transition_time_s,
            sensor.warmup_time_s
            + sensor.cooldown_time_s,
        )

        entries = sorted(
            [
                entry
                for entry in greedy_schedule.active_entries
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
                    seconds=required_transition_s
                )
            )


def test_memory_limits_are_respected(
    reference_data,
    greedy_schedule,
) -> None:
    catalog, _, _ = reference_data

    reserve_ratio = (
        greedy_schedule.memory_reserve_ratio
    )

    for satellite in catalog.satellites:
        generated_data_mb = sum(
            entry.estimated_data_volume_mb
            for entry in greedy_schedule.active_entries
            if entry.satellite_id
            == satellite.satellite_id
        )

        memory_limit_mb = (
            satellite.memory_capacity_mb
            * (1.0 - reserve_ratio)
        )

        assert (
            satellite.initial_memory_usage_mb
            + generated_data_mb
            <= memory_limit_mb + 1e-6
        )


def test_acquisition_count_limits_are_respected(
    reference_data,
    greedy_schedule,
) -> None:
    catalog, _, _ = reference_data

    for satellite in catalog.satellites:
        count = sum(
            entry.satellite_id
            == satellite.satellite_id
            for entry in greedy_schedule.active_entries
        )

        assert (
            count
            <= satellite.max_acquisitions_per_day
        )


def test_imaging_time_limits_are_respected(
    reference_data,
    greedy_schedule,
) -> None:
    catalog, _, _ = reference_data

    for satellite in catalog.satellites:
        imaging_time_s = sum(
            entry.duration_s
            for entry in greedy_schedule.active_entries
            if entry.satellite_id
            == satellite.satellite_id
        )

        assert (
            imaging_time_s
            <= satellite.max_imaging_time_per_day_s
            + 1e-6
        )


def test_objective_value_matches_entries(
    greedy_schedule,
) -> None:
    expected_value = round(
        sum(
            entry.objective_contribution
            for entry in greedy_schedule.active_entries
        ),
        6,
    )

    assert greedy_schedule.objective_value == pytest.approx(
        expected_value
    )


def test_single_request_reward_is_added_once(
    reference_data,
    greedy_schedule,
) -> None:
    _, request_set, opportunity_set = reference_data

    config = GreedyPlannerConfig()

    grouped = group_entries_by_request(
        greedy_schedule
    )

    request = next(
        request
        for request in request_set.active_requests
        if (
            request.request_mode == RequestMode.SINGLE
            and grouped[request.request_id]
        )
    )

    entry = grouped[
        request.request_id
    ][0]

    opportunity = opportunity_set.get_opportunity(
        entry.opportunity_id
    )

    expected_contribution = (
        request_reward(request, config)
        + acquisition_score(opportunity, config)
    )

    assert entry.objective_contribution == pytest.approx(
        expected_contribution
    )


def test_dual_required_reward_is_added_once(
    reference_data,
    greedy_schedule,
) -> None:
    _, request_set, opportunity_set = reference_data

    config = GreedyPlannerConfig()

    grouped = group_entries_by_request(
        greedy_schedule
    )

    request = next(
        request
        for request in request_set.dual_required_requests
        if len(grouped[request.request_id]) == 2
    )

    entries = grouped[
        request.request_id
    ]

    opportunities = [
        opportunity_set.get_opportunity(
            entry.opportunity_id
        )
        for entry in entries
    ]

    expected_total = (
        request_reward(request, config)
        + sum(
            acquisition_score(
                opportunity,
                config,
            )
            for opportunity in opportunities
        )
    )

    actual_total = sum(
        entry.objective_contribution
        for entry in entries
    )

    assert actual_total == pytest.approx(
        expected_total
    )


def test_dual_optional_second_acquisition_uses_bonus(
    reference_data,
    greedy_schedule,
) -> None:
    _, request_set, opportunity_set = reference_data

    config = GreedyPlannerConfig()

    grouped = group_entries_by_request(
        greedy_schedule
    )

    request = next(
        request
        for request in request_set.active_requests
        if (
            request.request_mode
            == RequestMode.DUAL_OPTIONAL
            and len(grouped[request.request_id]) == 2
        )
    )

    entries = grouped[
        request.request_id
    ]

    opportunities = [
        opportunity_set.get_opportunity(
            entry.opportunity_id
        )
        for entry in entries
    ]

    expected_total = (
        request_reward(request, config)
        + sum(
            acquisition_score(
                opportunity,
                config,
            )
            for opportunity in opportunities
        )
        + config.dual_optional_second_bonus
    )

    actual_total = sum(
        entry.objective_contribution
        for entry in entries
    )

    assert actual_total == pytest.approx(
        expected_total
    )


def test_unassigned_requests_are_not_scheduled(
    greedy_schedule,
) -> None:
    assert not (
        set(greedy_schedule.unassigned_request_ids)
        & set(greedy_schedule.scheduled_request_ids)
    )


def test_horizon_matches_request_set(
    reference_data,
    greedy_schedule,
) -> None:
    _, request_set, _ = reference_data

    assert (
        greedy_schedule.horizon_start_utc
        == request_set.horizon_start_utc
    )

    assert (
        greedy_schedule.horizon_end_utc
        == request_set.horizon_end_utc
    )


def test_greedy_is_deterministic(
    reference_data,
    greedy_schedule,
) -> None:
    catalog, request_set, opportunity_set = (
        reference_data
    )

    second_schedule = build_greedy_schedule(
        catalog=catalog,
        request_set=request_set,
        opportunity_set=opportunity_set,
        created_at_utc=FIXED_CREATED_AT,
    )

    first_ids = [
        entry.opportunity_id
        for entry in greedy_schedule.entries
    ]

    second_ids = [
        entry.opportunity_id
        for entry in second_schedule.entries
    ]

    assert first_ids == second_ids

    assert (
        greedy_schedule.objective_value
        == second_schedule.objective_value
    )


def test_full_memory_reserve_blocks_all_entries(
    reference_data,
) -> None:
    catalog, request_set, opportunity_set = (
        reference_data
    )

    schedule = build_greedy_schedule(
        catalog=catalog,
        request_set=request_set,
        opportunity_set=opportunity_set,
        config=GreedyPlannerConfig(
            memory_reserve_ratio=1.0
        ),
        schedule_id="SCHEDULE-GREEDY-NOMEM",
        created_at_utc=FIXED_CREATED_AT,
    )

    assert schedule.total_acquisitions == 0
    assert schedule.objective_value == pytest.approx(0.0)
    assert len(schedule.unassigned_request_ids) == 20


def test_full_memory_reserve_marks_schedule_infeasible(
    reference_data,
) -> None:
    catalog, request_set, opportunity_set = (
        reference_data
    )

    schedule = build_greedy_schedule(
        catalog=catalog,
        request_set=request_set,
        opportunity_set=opportunity_set,
        config=GreedyPlannerConfig(
            memory_reserve_ratio=1.0
        ),
        schedule_id="SCHEDULE-GREEDY-INFEASIBLE",
        created_at_utc=FIXED_CREATED_AT,
    )

    assert schedule.status == ScheduleStatus.INFEASIBLE


def test_invalid_memory_reserve_is_rejected() -> None:
    with pytest.raises(ValueError):
        GreedyPlannerConfig(
            memory_reserve_ratio=1.1
        )


def test_negative_weight_is_rejected() -> None:
    with pytest.raises(ValueError):
        GreedyPlannerConfig(
            priority_weight=-1.0
        )


def test_negative_dual_optional_bonus_is_rejected() -> None:
    with pytest.raises(ValueError):
        GreedyPlannerConfig(
            dual_optional_second_bonus=-1.0
        )


def test_schedule_save_and_load_roundtrip(
    tmp_path: Path,
    greedy_schedule,
) -> None:
    schedule_path = (
        tmp_path
        / "schedule.json"
    )

    save_schedule(
        greedy_schedule,
        schedule_path,
    )

    loaded_schedule = load_schedule(
        schedule_path
    )

    assert (
        loaded_schedule.schedule_id
        == greedy_schedule.schedule_id
    )

    assert (
        loaded_schedule.model_dump(mode="json")
        == greedy_schedule.model_dump(mode="json")
    )


def test_missing_schedule_file_is_rejected(
    tmp_path: Path,
) -> None:
    missing_path = (
        tmp_path
        / "missing.json"
    )

    with pytest.raises(FileNotFoundError):
        load_schedule(
            missing_path
        )


def test_invalid_schedule_json_is_rejected(
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
        load_schedule(
            invalid_path
        )