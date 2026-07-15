from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.models.enums import (
    PlanningAlgorithm,
    ScheduleEntryStatus,
    ScheduleStatus,
)
from app.planning.fixed import FixedOpportunityAssignment
from app.schedule_loader import load_schedule
from app.services.planning_service import PlanningOptions
from app.services.replanning_service import (
    DEFAULT_FREEZE_REASON,
    ReplanningService,
)
from app.services.scenario_service import ScenarioService


PROJECT_ROOT = Path(__file__).resolve().parents[1]

PREVIOUS_SCHEDULE_PATH = (
    PROJECT_ROOT
    / "data"
    / "example_schedule_cp_sat.json"
)

REPLAN_AT = datetime(
    2026,
    7,
    15,
    6,
    0,
    0,
    tzinfo=timezone.utc,
)

FROZEN_UNTIL = datetime(
    2026,
    7,
    15,
    8,
    0,
    0,
    tzinfo=timezone.utc,
)


@pytest.fixture(scope="module")
def example_scenario():
    return ScenarioService(
        project_root=PROJECT_ROOT
    ).load("EXAMPLE")


@pytest.fixture(scope="module")
def previous_schedule():
    return load_schedule(
        PREVIOUS_SCHEDULE_PATH
    )


@pytest.fixture(scope="module")
def cp_sat_replanning_result(
    example_scenario,
    previous_schedule,
):
    return ReplanningService().run(
        scenario=example_scenario,
        previous_schedule=previous_schedule,
        options=PlanningOptions(
            algorithm=PlanningAlgorithm.CP_SAT,
            memory_reserve_ratio=0.0,
            cp_sat_time_limit_s=30.0,
            cp_sat_num_search_workers=1,
        ),
        replan_at_utc=REPLAN_AT,
    )


def test_fixed_assignment_normalizes_values() -> None:
    assignment = FixedOpportunityAssignment(
        opportunity_id="opp-sar-0001",
        status="frozen",
        lock_reason="  blokada operacyjna  ",
    )

    assert assignment.opportunity_id == "OPP-SAR-0001"
    assert assignment.status == ScheduleEntryStatus.FROZEN
    assert assignment.lock_reason == "blokada operacyjna"


def test_frozen_assignment_requires_reason() -> None:
    with pytest.raises(ValueError):
        FixedOpportunityAssignment(
            opportunity_id="OPP-SAR-0001",
            status=ScheduleEntryStatus.FROZEN,
        )


def test_executed_assignment_rejects_reason() -> None:
    with pytest.raises(ValueError):
        FixedOpportunityAssignment(
            opportunity_id="OPP-SAR-0001",
            status=ScheduleEntryStatus.EXECUTED,
            lock_reason="Niepotrzebna blokada",
        )


def test_default_freeze_window_is_two_hours(
    cp_sat_replanning_result,
) -> None:
    assert (
        cp_sat_replanning_result.frozen_until_utc
        == FROZEN_UNTIL
    )
    assert (
        cp_sat_replanning_result.schedule.frozen_until_utc
        == FROZEN_UNTIL
    )


def test_past_entries_become_executed(
    cp_sat_replanning_result,
) -> None:
    executed_entries = [
        entry
        for entry
        in cp_sat_replanning_result.schedule.active_entries
        if entry.status == ScheduleEntryStatus.EXECUTED
    ]

    assert len(executed_entries) == 6
    assert all(
        entry.end_utc <= REPLAN_AT
        for entry in executed_entries
    )
    assert all(
        entry.lock_reason is None
        for entry in executed_entries
    )


def test_near_future_entries_become_frozen(
    cp_sat_replanning_result,
) -> None:
    frozen_entries = [
        entry
        for entry
        in cp_sat_replanning_result.schedule.active_entries
        if entry.status == ScheduleEntryStatus.FROZEN
    ]

    assert len(frozen_entries) == 5
    assert all(
        entry.end_utc > REPLAN_AT
        for entry in frozen_entries
    )
    assert all(
        entry.start_utc < FROZEN_UNTIL
        for entry in frozen_entries
    )
    assert all(
        entry.lock_reason == DEFAULT_FREEZE_REASON
        for entry in frozen_entries
    )


def test_all_fixed_entries_are_preserved(
    cp_sat_replanning_result,
) -> None:
    fixed_ids = {
        assignment.opportunity_id
        for assignment
        in cp_sat_replanning_result.fixed_assignments
    }

    result_ids = {
        entry.opportunity_id
        for entry
        in cp_sat_replanning_result.schedule.active_entries
    }

    assert fixed_ids <= result_ids
    assert cp_sat_replanning_result.fixed_count == 11
    assert cp_sat_replanning_result.executed_count == 6
    assert cp_sat_replanning_result.frozen_count == 5


def test_no_new_planned_entry_is_inside_frozen_window(
    cp_sat_replanning_result,
) -> None:
    assert all(
        entry.status
        in {
            ScheduleEntryStatus.EXECUTED,
            ScheduleEntryStatus.FROZEN,
        }
        for entry
        in cp_sat_replanning_result.schedule.active_entries
        if entry.start_utc < FROZEN_UNTIL
    )


def test_cp_sat_replanning_is_feasible(
    cp_sat_replanning_result,
) -> None:
    assert (
        cp_sat_replanning_result.schedule.algorithm
        == PlanningAlgorithm.CP_SAT
    )
    assert (
        cp_sat_replanning_result.schedule.status
        == ScheduleStatus.FEASIBLE
    )
    assert cp_sat_replanning_result.solver_status in {
        "FEASIBLE",
        "OPTIMAL",
    }
    assert (
        cp_sat_replanning_result.schedule.total_acquisitions
        == 24
    )


def test_cp_sat_keeps_optimal_future_for_example(
    cp_sat_replanning_result,
) -> None:
    assert cp_sat_replanning_result.added_opportunity_ids == []
    assert cp_sat_replanning_result.removed_opportunity_ids == []
    assert len(
        cp_sat_replanning_result
        .unchanged_replannable_opportunity_ids
    ) == 13


def test_greedy_replanning_supports_same_frozen_window(
    example_scenario,
    previous_schedule,
) -> None:
    result = ReplanningService().run(
        scenario=example_scenario,
        previous_schedule=previous_schedule,
        options=PlanningOptions(
            algorithm=PlanningAlgorithm.GREEDY,
            memory_reserve_ratio=0.0,
        ),
        replan_at_utc=REPLAN_AT,
    )

    assert result.schedule.algorithm == PlanningAlgorithm.GREEDY
    assert result.solver_status == "NOT_APPLICABLE"
    assert result.schedule.status == ScheduleStatus.FEASIBLE
    assert result.fixed_count == 11
    assert len(result.added_opportunity_ids) == 7
    assert len(result.removed_opportunity_ids) == 7


def test_freeze_boundary_is_clipped_to_horizon_end(
    example_scenario,
    previous_schedule,
) -> None:
    replan_at = datetime(
        2026,
        7,
        15,
        23,
        30,
        tzinfo=timezone.utc,
    )

    result = ReplanningService().run(
        scenario=example_scenario,
        previous_schedule=previous_schedule,
        options=PlanningOptions(
            algorithm=PlanningAlgorithm.CP_SAT,
            memory_reserve_ratio=0.0,
            cp_sat_time_limit_s=30.0,
            cp_sat_num_search_workers=1,
        ),
        replan_at_utc=replan_at,
        freeze_duration=timedelta(hours=2),
    )

    assert (
        result.frozen_until_utc
        == example_scenario.request_set.horizon_end_utc
    )


def test_naive_replan_time_is_rejected(
    example_scenario,
    previous_schedule,
) -> None:
    with pytest.raises(ValueError):
        ReplanningService().run(
            scenario=example_scenario,
            previous_schedule=previous_schedule,
            options=PlanningOptions(),
            replan_at_utc=datetime(
                2026,
                7,
                15,
                6,
                0,
                0,
            ),
        )


def test_replan_time_outside_horizon_is_rejected(
    example_scenario,
    previous_schedule,
) -> None:
    with pytest.raises(ValueError):
        ReplanningService().run(
            scenario=example_scenario,
            previous_schedule=previous_schedule,
            options=PlanningOptions(),
            replan_at_utc=datetime(
                2026,
                7,
                16,
                1,
                0,
                tzinfo=timezone.utc,
            ),
        )


def test_nonpositive_freeze_duration_is_rejected(
    example_scenario,
    previous_schedule,
) -> None:
    with pytest.raises(ValueError):
        ReplanningService().run(
            scenario=example_scenario,
            previous_schedule=previous_schedule,
            options=PlanningOptions(),
            replan_at_utc=REPLAN_AT,
            freeze_duration=timedelta(0),
        )


def test_unknown_schedule_opportunity_is_rejected(
    example_scenario,
    previous_schedule,
) -> None:
    first_entry = previous_schedule.entries[0]

    invalid_entry = first_entry.model_copy(
        update={
            "opportunity_id": "OPP-UNKNOWN-001",
            "entry_id": "ENTRY-UNKNOWN-001",
        }
    )

    invalid_schedule = previous_schedule.model_copy(
        update={
            "entries": [
                invalid_entry,
                *previous_schedule.entries[1:],
            ]
        }
    )

    with pytest.raises(ValueError):
        ReplanningService().run(
            scenario=example_scenario,
            previous_schedule=invalid_schedule,
            options=PlanningOptions(),
            replan_at_utc=REPLAN_AT,
        )
