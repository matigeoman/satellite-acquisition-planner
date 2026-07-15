import json
from pathlib import Path

import pytest

from app.models.enums import (
    PlanningAlgorithm,
)
from app.services.planning_service import (
    PlanningOptions,
    PlanningService,
)
from app.services.scenario_service import (
    ScenarioService,
)
from app.ui import (
    REQUEST_STATUS_COLUMNS,
    SATELLITE_USAGE_COLUMNS,
    SCHEDULE_ENTRY_COLUMNS,
    build_planning_metrics,
    build_request_status_dataframe,
    build_satellite_usage_dataframe,
    build_schedule_download_filename,
    build_schedule_entries_dataframe,
    build_schedule_json,
    build_unfulfilled_requests_dataframe,
    format_percent,
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
        schedule_id="SCHEDULE-UI-EXAMPLE",
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
        schedule_id="SCHEDULE-UI-BLOCKED",
    )


def test_planning_metrics_match_example_result(
    example_result,
) -> None:
    metrics = build_planning_metrics(
        example_result
    )

    assert metrics.scenario_id == "EXAMPLE"
    assert metrics.algorithm == "GREEDY"
    assert metrics.total_active_requests == 20
    assert metrics.fully_satisfied_requests == 20
    assert metrics.unassigned_requests == 0
    assert metrics.total_acquisitions == 24
    assert metrics.satisfaction_ratio == 1.0


def test_schedule_entries_dataframe_has_expected_rows(
    example_result,
) -> None:
    dataframe = (
        build_schedule_entries_dataframe(
            example_result
        )
    )

    assert list(
        dataframe.columns
    ) == SCHEDULE_ENTRY_COLUMNS

    assert len(dataframe) == 24

    assert set(
        dataframe["sensor_type"]
    ) == {
        "SAR",
        "OPTICAL",
    }


def test_schedule_entries_are_sorted_chronologically(
    example_result,
) -> None:
    dataframe = (
        build_schedule_entries_dataframe(
            example_result
        )
    )

    assert dataframe[
        "start_utc"
    ].is_monotonic_increasing


def test_request_status_dataframe_contains_all_requests(
    example_result,
) -> None:
    dataframe = (
        build_request_status_dataframe(
            example_result
        )
    )

    assert list(
        dataframe.columns
    ) == REQUEST_STATUS_COLUMNS

    assert len(dataframe) == 20

    assert set(
        dataframe["fulfillment_status"]
    ) == {
        "FULLY_SATISFIED"
    }


def test_example_has_no_unfulfilled_requests(
    example_result,
) -> None:
    dataframe = (
        build_unfulfilled_requests_dataframe(
            example_result
        )
    )

    assert dataframe.empty


def test_satellite_usage_contains_all_satellites(
    example_result,
) -> None:
    dataframe = (
        build_satellite_usage_dataframe(
            example_result
        )
    )

    assert list(
        dataframe.columns
    ) == SATELLITE_USAGE_COLUMNS

    assert len(dataframe) == 6

    assert (
        dataframe[
            "scheduled_acquisitions"
        ].sum()
        == 24
    )


def test_schedule_json_is_valid(
    example_result,
) -> None:
    schedule_json = build_schedule_json(
        example_result
    )

    payload = json.loads(
        schedule_json
    )

    assert (
        payload["schedule_id"]
        == "SCHEDULE-UI-EXAMPLE"
    )

    assert payload["algorithm"] == "GREEDY"

    assert len(
        payload["entries"]
    ) == 24


def test_schedule_download_filename_is_safe(
    example_result,
) -> None:
    filename = (
        build_schedule_download_filename(
            example_result
        )
    )

    assert (
        filename
        == "schedule_ui_example.json"
    )


def test_percent_formatter() -> None:
    assert format_percent(
        0.30634401,
        digits=2,
    ) == "30.63%"


def test_blocked_schedule_has_empty_entry_dataframe(
    blocked_result,
) -> None:
    dataframe = (
        build_schedule_entries_dataframe(
            blocked_result
        )
    )

    assert dataframe.empty

    assert list(
        dataframe.columns
    ) == SCHEDULE_ENTRY_COLUMNS


def test_blocked_schedule_lists_all_requests_as_unfulfilled(
    blocked_result,
) -> None:
    dataframe = (
        build_unfulfilled_requests_dataframe(
            blocked_result
        )
    )

    assert len(dataframe) == 20

    assert set(
        dataframe["fulfillment_status"]
    ) == {
        "UNASSIGNED"
    }