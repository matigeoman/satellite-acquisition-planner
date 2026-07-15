from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.models.enums import PlanningAlgorithm
from app.services.comparison_service import (
    PlanningComparisonResult,
    PlanningComparisonService,
)
from app.services.planning_service import PlanningOptions
from app.services.scenario_service import ScenarioService


PROJECT_DIRECTORY = Path(
    __file__
).resolve().parents[1]

FIXED_CREATED_AT = datetime(
    2026,
    7,
    15,
    12,
    0,
    0,
    tzinfo=timezone.utc,
)


@pytest.fixture(scope="module")
def example_scenario():
    return ScenarioService(
        project_root=PROJECT_DIRECTORY
    ).load(
        "EXAMPLE"
    )


@pytest.fixture(scope="module")
def comparison_result(
    example_scenario,
) -> PlanningComparisonResult:
    return PlanningComparisonService().run(
        scenario=example_scenario,
        options=PlanningOptions(
            algorithm=PlanningAlgorithm.GREEDY,
            memory_reserve_ratio=0.0,
            cp_sat_time_limit_s=2.0,
            cp_sat_num_search_workers=1,
        ),
        created_at_utc=FIXED_CREATED_AT,
    )


def test_comparison_contains_expected_algorithms(
    comparison_result,
) -> None:
    assert (
        comparison_result.greedy.algorithm
        == PlanningAlgorithm.GREEDY
    )

    assert (
        comparison_result.cp_sat.algorithm
        == PlanningAlgorithm.CP_SAT
    )


def test_comparison_uses_same_scenario(
    comparison_result,
) -> None:
    assert (
        comparison_result.greedy.scenario.scenario_id
        == "EXAMPLE"
    )

    assert (
        comparison_result.cp_sat.scenario.scenario_id
        == "EXAMPLE"
    )


def test_comparison_uses_same_created_at(
    comparison_result,
) -> None:
    assert (
        comparison_result.greedy.schedule.created_at_utc
        == FIXED_CREATED_AT
    )

    assert (
        comparison_result.cp_sat.schedule.created_at_utc
        == FIXED_CREATED_AT
    )


def test_comparison_schedule_ids_are_valid_and_unique(
    comparison_result,
) -> None:
    assert (
        comparison_result.greedy.schedule.schedule_id
        == "SCHEDULE-COMPARE-EXAMPLE-GREEDY"
    )

    assert (
        comparison_result.cp_sat.schedule.schedule_id
        == "SCHEDULE-COMPARE-EXAMPLE-CP-SAT"
    )


def test_example_comparison_satisfies_all_requests(
    comparison_result,
) -> None:
    assert (
        comparison_result.greedy.fully_satisfied_requests
        == 20
    )

    assert (
        comparison_result.cp_sat.fully_satisfied_requests
        == 20
    )

    assert comparison_result.greedy.unassigned_requests == 0
    assert comparison_result.cp_sat.unassigned_requests == 0


def test_cp_sat_is_not_worse_on_example(
    comparison_result,
) -> None:
    assert (
        comparison_result.cp_sat.objective_value
        >= comparison_result.greedy.objective_value
    )

    assert comparison_result.objective_difference >= 0.0
    assert comparison_result.objective_improvement_pct >= 0.0


def test_comparison_runtime_is_recorded(
    comparison_result,
) -> None:
    assert comparison_result.wall_clock_runtime_s >= 0.0
    assert comparison_result.greedy.wall_clock_runtime_s >= 0.0
    assert comparison_result.cp_sat.wall_clock_runtime_s >= 0.0


def test_naive_comparison_timestamp_is_rejected(
    example_scenario,
) -> None:
    with pytest.raises(ValueError):
        PlanningComparisonService().run(
            scenario=example_scenario,
            options=PlanningOptions(),
            created_at_utc=datetime(
                2026,
                7,
                15,
                12,
                0,
                0,
            ),
        )
