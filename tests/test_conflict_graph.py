from __future__ import annotations

from pathlib import Path

from app.planning.config import GreedyPlannerConfig
from app.planning.conflict_graph import build_opportunity_conflict_graph
from app.services.scenario_service import ScenarioService


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_conflict_graph_is_symmetric_and_covers_feasible_opportunities() -> None:
    scenario = ScenarioService(project_root=PROJECT_ROOT).load("EXAMPLE")
    graph = build_opportunity_conflict_graph(
        catalog=scenario.catalog,
        request_set=scenario.request_set,
        opportunity_set=scenario.opportunity_set,
        config=GreedyPlannerConfig(use_dynamic_transition_model=True),
    )

    assert graph.node_count == scenario.feasible_opportunity_count
    assert graph.edge_count > 0
    assert 0.0 <= graph.density <= 1.0

    for opportunity_id in graph.opportunity_ids:
        for neighbor_id in graph.neighbors(opportunity_id):
            assert opportunity_id in graph.neighbors(neighbor_id)

    covered = set().union(*graph.connected_components())
    assert covered == set(graph.opportunity_ids)
    assert sum(graph.reason_counts().values()) >= graph.edge_count


def test_conflict_graph_rejects_unknown_node_lookup() -> None:
    scenario = ScenarioService(project_root=PROJECT_ROOT).load("EXAMPLE")
    graph = build_opportunity_conflict_graph(
        catalog=scenario.catalog,
        request_set=scenario.request_set,
        opportunity_set=scenario.opportunity_set,
        config=GreedyPlannerConfig(),
    )

    try:
        graph.neighbors("NOT-A-NODE")
    except KeyError as error:
        assert "Nieznana okazja grafu" in str(error)
    else:
        raise AssertionError("Oczekiwano KeyError dla nieznanego węzła")
