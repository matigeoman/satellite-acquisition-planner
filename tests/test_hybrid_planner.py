from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.models.enums import PlanningAlgorithm
from app.planning.config import HybridPlannerConfig
from app.planning.greedy import GreedyScheduler
from app.planning.hybrid import HybridScheduler
from app.services.scenario_service import ScenarioService


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CREATED_AT = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)


def test_hybrid_preserves_its_greedy_incumbent() -> None:
    scenario = ScenarioService(project_root=PROJECT_ROOT).load("EXAMPLE")
    config = HybridPlannerConfig(
        max_time_s=0.5,
        num_search_workers=1,
        max_neighborhoods=2,
        neighborhood_request_limit=8,
        use_dynamic_transition_model=False,
    )
    greedy = GreedyScheduler(
        catalog=scenario.catalog,
        request_set=scenario.request_set,
        opportunity_set=scenario.opportunity_set,
        config=config.greedy_config(),
    ).build_schedule(created_at_utc=CREATED_AT)

    scheduler = HybridScheduler(
        catalog=scenario.catalog,
        request_set=scenario.request_set,
        opportunity_set=scenario.opportunity_set,
        config=config,
    )
    hybrid = scheduler.build_schedule(created_at_utc=CREATED_AT)

    assert hybrid.algorithm == PlanningAlgorithm.HYBRID
    assert float(hybrid.objective_value or 0.0) >= float(
        greedy.objective_value or 0.0
    )
    assert scheduler.initial_objective_value == float(
        greedy.objective_value or 0.0
    )
    assert scheduler.conflict_graph is not None
    assert "Gorsze rozwiązania nie są przyjmowane" in hybrid.notes
