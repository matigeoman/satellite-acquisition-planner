from __future__ import annotations

from pathlib import Path

from app.demo import DEMO_STATE_KEY, DemoProjectService
from app.models.enums import PlanningAlgorithm, RequestMode, SensorType
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


def _service() -> DemoProjectService:
    return DemoProjectService(
        scenario_service=ScenarioService(project_root=PROJECT_ROOT),
        planning_service=PlanningService(),
    )


def test_demo_project_builds_complete_offline_state() -> None:
    service = _service()
    result = service.build(algorithm=PlanningAlgorithm.GREEDY)

    assert result.scenario.scenario_id == "POLAND_DEMO"
    assert result.scenario.satellite_count == 6
    assert result.request_count == 50
    assert result.opportunity_count == 500
    assert result.acquisition_count > 0
    assert result.access_window_count >= 3
    assert result.horizon_hours == 48.0
    assert len(result.orbit_snapshot.satellites) == 6

    state: dict[str, object] = {
        ORBIT_SNAPSHOT_STATE_KEY: object(),
        ACCESS_RESULT_STATE_KEY: object(),
        OPPORTUNITY_BUILDS_STATE_KEY: object(),
        REPLANNING_RESULT_STATE_KEY: object(),
        BENCHMARK_RESULT_STATE_KEY: object(),
    }
    service.apply_to_state(state, result)

    assert len(state[CUSTOM_REQUESTS_STATE_KEY]) == 50
    assert state[PLANNING_RESULT_STATE_KEY] is result.planning_result
    assert state[ORBIT_SNAPSHOT_STATE_KEY] is result.orbit_snapshot
    assert state[ACCESS_RESULT_STATE_KEY] is result.access_result
    assert AOI_STATE_KEY in state
    assert len(state[SCHEDULE_HISTORY_STATE_KEY]) == 1
    assert state[PROJECT_METADATA_STATE_KEY].project_id == "PROJECT-POLAND-DEMO"
    assert state[DEMO_STATE_KEY]["scenario_id"] == "POLAND_DEMO"
    assert state[DEMO_STATE_KEY]["horizon_hours"] == 48.0
    assert state[DEMO_STATE_KEY]["access_window_count"] >= 3
    assert OPPORTUNITY_BUILDS_STATE_KEY not in state
    assert REPLANNING_RESULT_STATE_KEY not in state
    assert BENCHMARK_RESULT_STATE_KEY not in state


def test_poland_demo_has_varied_windows_and_sensor_modes() -> None:
    scenario = ScenarioService(project_root=PROJECT_ROOT).load("POLAND_DEMO")
    requests = scenario.request_set.requests
    durations_h = {
        round(
            (request.latest_end_utc - request.earliest_start_utc).total_seconds()
            / 3600.0,
            1,
        )
        for request in requests
    }

    assert len(requests) == 50
    assert min(durations_h) <= 2.0
    assert max(durations_h) == 48.0
    assert len(durations_h) >= 8
    assert sum(request.request_mode == RequestMode.SINGLE for request in requests) == 40
    assert sum(request.request_mode == RequestMode.DUAL_OPTIONAL for request in requests) == 5
    assert sum(request.request_mode == RequestMode.DUAL_REQUIRED for request in requests) == 5
    assert sum(request.requested_sensor_types == [SensorType.SAR] for request in requests) == 20
    assert sum(
        request.requested_sensor_types == [SensorType.OPTICAL]
        for request in requests
    ) == 20


def test_demo_artifacts_are_present_and_valid_json() -> None:
    directory = PROJECT_ROOT / "examples" / "poland_demo"
    expected = {
        "README.md",
        "access_windows.json",
        "aoi.geojson",
        "benchmark_result.json",
        "demo_report.html",
        "opportunities.json",
        "orbits_omm.json",
        "requests.json",
        "schedule_cp_sat.json",
        "schedule_greedy.json",
        "stk_validation.json",
        "system.json",
    }

    assert expected <= {path.name for path in directory.iterdir()}
