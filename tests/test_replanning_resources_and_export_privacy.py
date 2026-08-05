from datetime import datetime, timezone
from pathlib import Path

from app.integrations.orbits.models import PropagatedState
from app.models.enums import PlanningAlgorithm
from app.schedule_loader import load_schedule
from app.services.planning_service import PlanningOptions
from app.services.replanning_service import ReplanningService
from app.services.scenario_service import ScenarioService


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PREVIOUS_SCHEDULE_PATH = (
    PROJECT_ROOT
    / "data"
    / "reference_schedules"
    / "example"
    / "cp_sat.json"
)
REPLAN_AT = datetime(2026, 7, 15, 6, 0, tzinfo=timezone.utc)


def test_replanning_preserves_dynamic_memory_and_downlink_outputs() -> None:
    scenario = ScenarioService(project_root=PROJECT_ROOT).load("EXAMPLE")
    previous_schedule = load_schedule(PREVIOUS_SCHEDULE_PATH)
    options = PlanningOptions(
        algorithm=PlanningAlgorithm.GREEDY,
        memory_reserve_ratio=0.0,
        enable_downlink_planning=True,
        require_full_downlink=True,
        allow_simultaneous_imaging_downlink=False,
        downlink_capacity_reserve_ratio=0.10,
    )

    result = ReplanningService().run(
        scenario=scenario,
        previous_schedule=previous_schedule,
        options=options,
        replan_at_utc=REPLAN_AT,
    )

    assert result.planning_result.options.enable_downlink_planning
    assert result.planning_result.options.require_full_downlink
    assert result.schedule.downlink_entries
    assert result.schedule.resource_summaries
    assert result.schedule.memory_timeline


def test_orbit_export_removes_windows_local_path() -> None:
    state = PropagatedState(
        timestamp_utc=REPLAN_AT,
        latitude_deg=52.0,
        longitude_deg=21.0,
        altitude_km=600.0,
        teme_position_km=(1.0, 2.0, 3.0),
        teme_velocity_km_s=(4.0, 5.0, 6.0),
        eop_source=(
            r"C:\Users\Example\Desktop\satplan\data\EOP-All-v1.1.txt"
        ),
    )

    payload = state.to_dict()

    assert payload["eop_source"] == "EOP-All-v1.1.txt"
    assert "C:\\" not in payload["eop_source"]
    assert "Users" not in payload["eop_source"]


def test_orbit_export_removes_posix_local_path() -> None:
    state = PropagatedState(
        timestamp_utc=REPLAN_AT,
        latitude_deg=52.0,
        longitude_deg=21.0,
        altitude_km=600.0,
        teme_position_km=(1.0, 2.0, 3.0),
        teme_velocity_km_s=(4.0, 5.0, 6.0),
        eop_source="/home/example/satplan/data/EOP-All-v1.1.txt",
    )

    assert state.to_dict()["eop_source"] == "EOP-All-v1.1.txt"
