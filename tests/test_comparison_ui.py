from pathlib import Path

import pytest
from plotly.graph_objects import Figure

from app.models.enums import PlanningAlgorithm
from app.services.comparison_service import (
    PlanningComparisonService,
)
from app.services.planning_service import PlanningOptions
from app.services.scenario_service import ScenarioService
from app.ui.comparison import (
    COMPARISON_SUMMARY_COLUMNS,
    REQUEST_COMPARISON_COLUMNS,
    build_comparison_gantt_dataframe,
    build_comparison_gantt_figure,
    build_comparison_metrics,
    build_comparison_summary_dataframe,
    build_objective_comparison_figure,
    build_request_comparison_dataframe,
    build_request_counts_comparison_figure,
)


PROJECT_DIRECTORY = Path(
    __file__
).resolve().parents[1]


@pytest.fixture(scope="module")
def comparison_result():
    scenario = ScenarioService(
        project_root=PROJECT_DIRECTORY
    ).load(
        "EXAMPLE"
    )

    return PlanningComparisonService().run(
        scenario=scenario,
        options=PlanningOptions(
            algorithm=PlanningAlgorithm.GREEDY,
            memory_reserve_ratio=0.0,
            cp_sat_time_limit_s=2.0,
            cp_sat_num_search_workers=1,
        ),
    )


def test_comparison_metrics_match_results(
    comparison_result,
) -> None:
    metrics = build_comparison_metrics(
        comparison_result
    )

    assert (
        metrics.greedy_objective
        == comparison_result.greedy.objective_value
    )

    assert (
        metrics.cp_sat_objective
        == comparison_result.cp_sat.objective_value
    )

    assert metrics.greedy_fully_satisfied == 20
    assert metrics.cp_sat_fully_satisfied == 20


def test_summary_dataframe_contains_two_algorithms(
    comparison_result,
) -> None:
    dataframe = build_comparison_summary_dataframe(
        comparison_result
    )

    assert list(
        dataframe.columns
    ) == COMPARISON_SUMMARY_COLUMNS

    assert dataframe[
        "algorithm"
    ].tolist() == [
        "Greedy",
        "CP-SAT",
    ]


def test_request_comparison_contains_all_requests(
    comparison_result,
) -> None:
    dataframe = build_request_comparison_dataframe(
        comparison_result
    )

    assert list(
        dataframe.columns
    ) == REQUEST_COMPARISON_COLUMNS

    assert len(dataframe) == 20


def test_request_comparison_has_valid_outcomes(
    comparison_result,
) -> None:
    dataframe = build_request_comparison_dataframe(
        comparison_result
    )

    assert set(
        dataframe["status_outcome"]
    ).issubset(
        {
            "CP_SAT_BETTER",
            "GREEDY_BETTER",
            "SAME_STATUS",
        }
    )

    assert set(
        dataframe["selection_relation"]
    ).issubset(
        {
            "NEITHER",
            "GREEDY_ONLY",
            "CP_SAT_ONLY",
            "BOTH_SAME",
            "BOTH_DIFFERENT",
        }
    )


def test_objective_figure_is_created(
    comparison_result,
) -> None:
    figure = build_objective_comparison_figure(
        comparison_result
    )

    assert isinstance(
        figure,
        Figure,
    )

    point_count = sum(
        len(trace.x)
        for trace in figure.data
    )

    assert point_count == 2


def test_request_counts_figure_is_created(
    comparison_result,
) -> None:
    figure = build_request_counts_comparison_figure(
        comparison_result
    )

    assert isinstance(
        figure,
        Figure,
    )

    point_count = sum(
        len(trace.x)
        for trace in figure.data
    )

    assert point_count == 6


def test_comparison_gantt_contains_both_algorithms(
    comparison_result,
) -> None:
    dataframe = build_comparison_gantt_dataframe(
        comparison_result
    )

    assert set(
        dataframe["algorithm"]
    ) == {
        "Greedy",
        "CP-SAT",
    }

    assert len(dataframe) == (
        comparison_result.greedy.total_acquisitions
        + comparison_result.cp_sat.total_acquisitions
    )


def test_comparison_gantt_figure_contains_all_entries(
    comparison_result,
) -> None:
    figure = build_comparison_gantt_figure(
        comparison_result
    )

    assert isinstance(
        figure,
        Figure,
    )

    point_count = sum(
        len(trace.x)
        for trace in figure.data
    )

    assert point_count == (
        comparison_result.greedy.total_acquisitions
        + comparison_result.cp_sat.total_acquisitions
    )
