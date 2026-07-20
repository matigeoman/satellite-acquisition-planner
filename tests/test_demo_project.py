from __future__ import annotations

from pathlib import Path

from app.demo import DEMO_STATE_KEY, DemoProjectService
from app.models.enums import PlanningAlgorithm
from app.projects.history import PROJECT_METADATA_STATE_KEY, SCHEDULE_HISTORY_STATE_KEY
from app.projects.service import (
    ACCESS_RESULT_STATE_KEY,
    AOI_STATE_KEY,
    BENCHMARK_RESULT_STATE_KEY,
    CUSTOM_REQUESTS_STATE_KEY,
    OPPORTUNITY_BUILDS_STATE_KEY,
    ORBIT_SNAPSHOT_STATE_KEY,
    PLANNING_RESULT_STATE_KEY,
    REPLANNING_RESULT_STATE_KEY,
)
from app.services import PlanningService, ScenarioService


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_demo_project_builds_and_replaces_public_session_state() -> None:
    service = DemoProjectService(
        scenario_service=ScenarioService(project_root=PROJECT_ROOT),
        planning_service=PlanningService(),
    )
    result = service.build(algorithm=PlanningAlgorithm.GREEDY)

    assert result.scenario.scenario_id == "EXAMPLE"
    assert result.scenario.satellite_count == 6
    assert result.request_count == 20
    assert result.opportunity_count == 200
    assert result.acquisition_count > 0

    state: dict[str, object] = {
        ORBIT_SNAPSHOT_STATE_KEY: object(),
        ACCESS_RESULT_STATE_KEY: object(),
        OPPORTUNITY_BUILDS_STATE_KEY: object(),
        REPLANNING_RESULT_STATE_KEY: object(),
        BENCHMARK_RESULT_STATE_KEY: object(),
    }
    service.apply_to_state(state, result)

    assert len(state[CUSTOM_REQUESTS_STATE_KEY]) == 20
    assert state[PLANNING_RESULT_STATE_KEY] is result.planning_result
    assert AOI_STATE_KEY in state
    assert len(state[SCHEDULE_HISTORY_STATE_KEY]) == 1
    assert state[PROJECT_METADATA_STATE_KEY].project_id == "PROJECT-POLAND-DEMO"
    assert state[DEMO_STATE_KEY]["scenario_id"] == "EXAMPLE"
    assert ORBIT_SNAPSHOT_STATE_KEY not in state
    assert ACCESS_RESULT_STATE_KEY not in state
    assert OPPORTUNITY_BUILDS_STATE_KEY not in state
    assert REPLANNING_RESULT_STATE_KEY not in state
    assert BENCHMARK_RESULT_STATE_KEY not in state
