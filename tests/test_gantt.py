from pathlib import Path

import pytest
from plotly.graph_objects import Figure

from app.models.enums import PlanningAlgorithm
from app.services.planning_service import (
    PlanningOptions,
    PlanningService,
)
from app.services.scenario_service import (
    ScenarioService,
)
from app.ui.gantt import (
    GANTT_COLUMNS,
    build_gantt_dataframe,
    build_gantt_figure,
)


PROJECT_DIRECTORY = Path(
    __file__
).resolve().parents[1]


@pytest.fixture(scope="module")
def example_scenario():
    return ScenarioService(
        project_root=PROJECT_DIRECTORY
    ).load(
        "EXAMPLE"
    )


@pytest.fixture(scope="module")
def example_result(
    example_scenario,
):
    return PlanningService().run(
        scenario=example_scenario,
        options=PlanningOptions(
            algorithm=PlanningAlgorithm.GREEDY,
            memory_reserve_ratio=0.0,
        ),
        schedule_id="SCHEDULE-GANTT-EXAMPLE",
    )


@pytest.fixture(scope="module")
def blocked_result(
    example_scenario,
):
    return PlanningService().run(
        scenario=example_scenario,
        options=PlanningOptions(
            algorithm=PlanningAlgorithm.GREEDY,
            memory_reserve_ratio=1.0,
        ),
        schedule_id="SCHEDULE-GANTT-BLOCKED",
    )


def test_gantt_dataframe_has_expected_shape(
    example_result,
) -> None:
    dataframe = build_gantt_dataframe(
        example_result
    )

    assert list(
        dataframe.columns
    ) == GANTT_COLUMNS

    assert len(dataframe) == 24


def test_gantt_dataframe_is_chronological(
    example_result,
) -> None:
    dataframe = build_gantt_dataframe(
        example_result
    )

    assert dataframe[
        "start_utc"
    ].is_monotonic_increasing


def test_gantt_durations_match_time_intervals(
    example_result,
) -> None:
    dataframe = build_gantt_dataframe(
        example_result
    )

    calculated_durations = (
        dataframe["end_utc"]
        - dataframe["start_utc"]
    ).dt.total_seconds()

    assert calculated_durations.tolist() == pytest.approx(
        dataframe["duration_s"].tolist()
    )


def test_gantt_figure_contains_all_acquisitions(
    example_result,
) -> None:
    figure = build_gantt_figure(
        example_result
    )

    assert isinstance(
        figure,
        Figure,
    )

    point_count = sum(
        len(trace.x)
        for trace in figure.data
    )

    assert point_count == 24


def test_gantt_figure_filters_satellite(
    example_result,
) -> None:
    dataframe = build_gantt_dataframe(
        example_result
    )

    satellite_id = dataframe.iloc[
        0
    ]["satellite_id"]

    expected_count = int(
        (
            dataframe["satellite_id"]
            == satellite_id
        ).sum()
    )

    figure = build_gantt_figure(
        example_result,
        satellite_ids=[
            satellite_id
        ],
    )

    point_count = sum(
        len(trace.x)
        for trace in figure.data
    )

    assert point_count == expected_count


def test_empty_schedule_builds_empty_gantt(
    blocked_result,
) -> None:
    dataframe = build_gantt_dataframe(
        blocked_result
    )

    assert dataframe.empty

    figure = build_gantt_figure(
        blocked_result
    )

    assert isinstance(
        figure,
        Figure,
    )

    assert len(
        figure.data
    ) == 0

    assert len(
        figure.layout.annotations
    ) == 1