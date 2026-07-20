from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.models.enums import (
    PlanningAlgorithm,
    ScheduleStatus,
)
from app.services.planning_service import (
    PlanningOptions,
    PlanningService,
)
from app.services.scenario_service import (
    ScenarioDefinition,
    ScenarioService,
    build_default_scenario_definitions,
)


PROJECT_DIRECTORY = Path(
    __file__
).resolve().parents[1]

FIXED_CREATED_AT = datetime(
    2026,
    7,
    15,
    23,
    45,
    0,
    tzinfo=timezone.utc,
)


@pytest.fixture(scope="module")
def scenario_service() -> ScenarioService:
    return ScenarioService(
        project_root=PROJECT_DIRECTORY
    )


@pytest.fixture(scope="module")
def example_scenario(
    scenario_service: ScenarioService,
):
    return scenario_service.load(
        "EXAMPLE"
    )


def test_default_definitions_contain_registered_scenarios() -> None:
    definitions = (
        build_default_scenario_definitions(
            PROJECT_DIRECTORY
        )
    )

    assert {
        definition.scenario_id
        for definition in definitions
    } == {
        "EXAMPLE",
        "POLAND_DEMO",
        "STRESS",
    }


def test_scenario_service_lists_known_ids(
    scenario_service: ScenarioService,
) -> None:
    assert scenario_service.scenario_ids == (
        "EXAMPLE",
        "POLAND_DEMO",
        "STRESS",
    )


def test_scenario_id_is_case_insensitive(
    scenario_service: ScenarioService,
) -> None:
    definition = (
        scenario_service.get_definition(
            "example"
        )
    )

    assert (
        definition.scenario_id
        == "EXAMPLE"
    )


def test_unknown_scenario_is_rejected(
    scenario_service: ScenarioService,
) -> None:
    with pytest.raises(KeyError):
        scenario_service.load(
            "UNKNOWN"
        )


def test_example_scenario_is_loaded(
    example_scenario,
) -> None:
    assert (
        example_scenario.scenario_id
        == "EXAMPLE"
    )

    assert (
        example_scenario.active_request_count
        == 20
    )

    assert (
        example_scenario.opportunity_count
        == 200
    )

    assert (
        example_scenario.satellite_count
        == 6
    )


def test_stress_scenario_is_loaded(
    scenario_service: ScenarioService,
) -> None:
    scenario = scenario_service.load(
        "STRESS"
    )

    assert scenario.active_request_count == 80
    assert scenario.opportunity_count == 800
    assert scenario.mandatory_request_count == 4


def test_missing_scenario_files_are_rejected(
    tmp_path: Path,
) -> None:
    definition = ScenarioDefinition(
        scenario_id="MISSING",
        name="Brakujący scenariusz",
        description="Test brakujących plików.",
        catalog_path=(
            tmp_path
            / "catalog.json"
        ),
        request_set_path=(
            tmp_path
            / "requests.json"
        ),
        opportunity_set_path=(
            tmp_path
            / "opportunities.json"
        ),
    )

    service = ScenarioService(
        project_root=tmp_path,
        definitions=[
            definition
        ],
    )

    with pytest.raises(
        FileNotFoundError
    ):
        service.load(
            "MISSING"
        )


def test_duplicate_scenario_ids_are_rejected(
    tmp_path: Path,
) -> None:
    first = ScenarioDefinition(
        scenario_id="DUPLICATE",
        name="Pierwszy",
        description="Pierwszy scenariusz.",
        catalog_path=tmp_path / "a.json",
        request_set_path=tmp_path / "b.json",
        opportunity_set_path=tmp_path / "c.json",
    )

    second = ScenarioDefinition(
        scenario_id="duplicate",
        name="Drugi",
        description="Drugi scenariusz.",
        catalog_path=tmp_path / "d.json",
        request_set_path=tmp_path / "e.json",
        opportunity_set_path=tmp_path / "f.json",
    )

    with pytest.raises(ValueError):
        ScenarioService(
            project_root=tmp_path,
            definitions=[
                first,
                second,
            ],
        )


def test_planning_options_accept_algorithm_string() -> None:
    options = PlanningOptions(
        algorithm="CP_SAT"
    )

    assert (
        options.algorithm
        == PlanningAlgorithm.CP_SAT
    )


def test_invalid_algorithm_is_rejected() -> None:
    with pytest.raises(ValueError):
        PlanningOptions(
            algorithm="RANDOM"
        )


def test_invalid_memory_reserve_is_rejected() -> None:
    with pytest.raises(ValueError):
        PlanningOptions(
            memory_reserve_ratio=1.1
        )


def test_invalid_cp_sat_time_limit_is_rejected() -> None:
    with pytest.raises(ValueError):
        PlanningOptions(
            cp_sat_time_limit_s=0.0
        )


def test_greedy_service_builds_schedule(
    example_scenario,
) -> None:
    result = PlanningService().run(
        scenario=example_scenario,
        options=PlanningOptions(
            algorithm=PlanningAlgorithm.GREEDY,
            memory_reserve_ratio=0.0,
        ),
        created_at_utc=FIXED_CREATED_AT,
    )

    assert (
        result.algorithm
        == PlanningAlgorithm.GREEDY
    )

    assert (
        result.solver_status
        == "NOT_APPLICABLE"
    )

    assert (
        result.schedule.status
        == ScheduleStatus.FEASIBLE
    )

    assert result.fully_satisfied_requests == 20
    assert result.unassigned_requests == 0
    assert result.total_acquisitions == 24
    assert result.objective_value > 0.0
    assert result.wall_clock_runtime_s >= 0.0


def test_cp_sat_service_builds_schedule(
    example_scenario,
) -> None:
    result = PlanningService().run(
        scenario=example_scenario,
        options=PlanningOptions(
            algorithm=PlanningAlgorithm.CP_SAT,
            memory_reserve_ratio=0.0,
            cp_sat_time_limit_s=2.0,
            cp_sat_num_search_workers=1,
        ),
        created_at_utc=FIXED_CREATED_AT,
    )

    assert (
        result.algorithm
        == PlanningAlgorithm.CP_SAT
    )

    assert result.solver_status in {
        "OPTIMAL",
        "FEASIBLE",
    }

    assert (
        result.schedule.status
        == ScheduleStatus.FEASIBLE
    )

    assert result.fully_satisfied_requests == 20
    assert result.unassigned_requests == 0
    assert result.total_acquisitions == 24
    assert result.objective_value > 0.0


def test_service_uses_custom_schedule_metadata(
    example_scenario,
) -> None:
    result = PlanningService().run(
        scenario=example_scenario,
        options=PlanningOptions(
            algorithm=PlanningAlgorithm.GREEDY,
            memory_reserve_ratio=0.0,
        ),
        schedule_id="SCHEDULE-CUSTOM-001",
        schedule_name="Własny harmonogram",
        created_at_utc=FIXED_CREATED_AT,
    )

    assert (
        result.schedule.schedule_id
        == "SCHEDULE-CUSTOM-001"
    )

    assert (
        result.schedule.name
        == "Własny harmonogram"
    )

    assert (
        result.schedule.created_at_utc
        == FIXED_CREATED_AT
    )


def test_naive_created_at_is_rejected(
    example_scenario,
) -> None:
    with pytest.raises(ValueError):
        PlanningService().run(
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


def test_default_greedy_schedule_id_is_generated() -> None:
    schedule_id = (
        PlanningService.build_schedule_id(
            scenario_id="example",
            algorithm=PlanningAlgorithm.GREEDY,
        )
    )

    assert (
        schedule_id
        == "SCHEDULE-EXAMPLE-GREEDY"
    )


def test_default_cp_sat_schedule_id_is_generated() -> None:
    schedule_id = (
        PlanningService.build_schedule_id(
            scenario_id="stress test",
            algorithm=PlanningAlgorithm.CP_SAT,
        )
    )

    assert (
        schedule_id
        == "SCHEDULE-STRESS-TEST-CP-SAT"
    )