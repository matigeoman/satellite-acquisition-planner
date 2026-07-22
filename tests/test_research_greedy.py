from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.planning.config import GreedyPlannerConfig
from app.planning.greedy import GreedyScheduler
from app.services.scenario_service import ScenarioService


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CREATED_AT = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)


def test_research_greedy_is_deterministic_and_reports_heuristic() -> None:
    scenario = ScenarioService(project_root=PROJECT_ROOT).load("EXAMPLE")
    config = GreedyPlannerConfig(
        use_opportunity_cost_heuristic=True,
        use_dynamic_transition_model=True,
    )

    first_scheduler = GreedyScheduler(
        catalog=scenario.catalog,
        request_set=scenario.request_set,
        opportunity_set=scenario.opportunity_set,
        config=config,
    )
    first = first_scheduler.build_schedule(created_at_utc=CREATED_AT)

    second_scheduler = GreedyScheduler(
        catalog=scenario.catalog,
        request_set=scenario.request_set,
        opportunity_set=scenario.opportunity_set,
        config=config,
    )
    second = second_scheduler.build_schedule(created_at_utc=CREATED_AT)

    assert [entry.opportunity_id for entry in first.entries] == [
        entry.opportunity_id for entry in second.entries
    ]
    assert first.objective_value == second.objective_value
    assert first_scheduler._conflict_graph is not None
    assert "koszt utraconych alternatyw" in first.notes
