import csv
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest

from app.analysis.planner_comparison import (
    COMPARISON_FIELDNAMES,
    build_planner_comparison,
    export_planner_comparison,
    extract_solver_status,
)
from app.analysis.schedule_report import (
    analyze_schedule,
)
from app.catalog_loader import load_system_catalog
from app.opportunity_loader import load_opportunity_set
from app.request_loader import load_request_set
from app.schedule_loader import load_schedule


PROJECT_DIRECTORY = Path(__file__).resolve().parents[1]

CATALOG_PATH = (
    PROJECT_DIRECTORY
    / "data"
    / "scenarios"
    / "stress"
    / "system.json"
)

REQUEST_SET_PATH = (
    PROJECT_DIRECTORY
    / "data"
    / "scenarios"
    / "stress"
    / "requests.json"
)

OPPORTUNITY_SET_PATH = (
    PROJECT_DIRECTORY
    / "data"
    / "scenarios"
    / "stress"
    / "opportunities.json"
)

GREEDY_SCHEDULE_PATH = (
    PROJECT_DIRECTORY
    / "data"
    / "reference_schedules"
    / "stress"
    / "greedy.json"
)

CP_SAT_SCHEDULE_PATH = (
    PROJECT_DIRECTORY
    / "data"
    / "reference_schedules"
    / "stress"
    / "cp_sat.json"
)


@pytest.fixture(scope="module")
def comparison_inputs():
    catalog = load_system_catalog(
        CATALOG_PATH
    )

    request_set = load_request_set(
        REQUEST_SET_PATH
    )

    opportunity_set = load_opportunity_set(
        OPPORTUNITY_SET_PATH,
        catalog=catalog,
        request_set=request_set,
    )

    greedy_schedule = load_schedule(
        GREEDY_SCHEDULE_PATH
    )

    cp_sat_schedule = load_schedule(
        CP_SAT_SCHEDULE_PATH
    )

    greedy_analysis = analyze_schedule(
        catalog=catalog,
        request_set=request_set,
        opportunity_set=opportunity_set,
        schedule=greedy_schedule,
    )

    cp_sat_analysis = analyze_schedule(
        catalog=catalog,
        request_set=request_set,
        opportunity_set=opportunity_set,
        schedule=cp_sat_schedule,
    )

    return {
        "greedy_schedule": greedy_schedule,
        "cp_sat_schedule": cp_sat_schedule,
        "greedy_analysis": greedy_analysis,
        "cp_sat_analysis": cp_sat_analysis,
    }


@pytest.fixture(scope="module")
def comparison(comparison_inputs):
    return build_planner_comparison(
        scenario_id="STRESS-TEST",
        **comparison_inputs,
    )


def test_comparison_contains_expected_algorithms(
    comparison,
) -> None:
    assert comparison.greedy.algorithm == "GREEDY"
    assert comparison.cp_sat.algorithm == "CP_SAT"


def test_objective_difference_is_calculated(
    comparison,
) -> None:
    expected = (
        comparison.cp_sat.objective_value
        - comparison.greedy.objective_value
    )

    assert comparison.objective_difference == pytest.approx(
        expected
    )


def test_cp_sat_objective_is_better(
    comparison,
) -> None:
    assert comparison.objective_difference > 0.0
    assert comparison.objective_improvement_pct > 0.0


def test_cp_sat_satisfies_more_requests(
    comparison,
) -> None:
    assert (
        comparison
        .additional_fully_satisfied_requests
        > 0
    )


def test_cp_sat_reduces_unassigned_requests(
    comparison,
) -> None:
    assert (
        comparison.unassigned_request_reduction
        > 0
    )


def test_runtime_ratio_is_calculated(
    comparison,
) -> None:
    assert comparison.runtime_ratio is not None
    assert comparison.runtime_ratio > 1.0


def test_csv_rows_contain_two_algorithms(
    comparison,
) -> None:
    rows = comparison.csv_rows()

    assert len(rows) == 2

    assert {
        row["algorithm"]
        for row in rows
    } == {
        "GREEDY",
        "CP_SAT",
    }


def test_cp_sat_csv_row_contains_improvement(
    comparison,
) -> None:
    cp_sat_row = next(
        row
        for row in comparison.csv_rows()
        if row["algorithm"] == "CP_SAT"
    )

    assert (
        cp_sat_row[
            "objective_difference_vs_greedy"
        ]
        > 0.0
    )

    assert (
        cp_sat_row[
            "fully_satisfied_difference_vs_greedy"
        ]
        > 0
    )


def test_solver_status_is_extracted() -> None:
    notes = (
        "Harmonogram wygenerowany przez CP-SAT. "
        "Status solvera: FEASIBLE."
    )

    assert extract_solver_status(
        notes
    ) == "FEASIBLE"


def test_export_creates_csv_and_three_charts(
    tmp_path: Path,
    comparison,
) -> None:
    paths = export_planner_comparison(
        comparison,
        tmp_path,
    )

    assert set(paths) == {
        "comparison_csv",
        "objective_chart",
        "fulfilled_chart",
        "runtime_chart",
    }

    assert all(
        path.exists()
        for path in paths.values()
    )


def test_exported_charts_are_not_empty(
    tmp_path: Path,
    comparison,
) -> None:
    paths = export_planner_comparison(
        comparison,
        tmp_path,
    )

    chart_paths = [
        paths["objective_chart"],
        paths["fulfilled_chart"],
        paths["runtime_chart"],
    ]

    assert all(
        path.stat().st_size > 0
        for path in chart_paths
    )


def test_exported_csv_has_expected_header(
    tmp_path: Path,
    comparison,
) -> None:
    paths = export_planner_comparison(
        comparison,
        tmp_path,
    )

    with paths["comparison_csv"].open(
        encoding="utf-8-sig",
        newline="",
    ) as file:
        reader = csv.DictReader(file)

        assert reader.fieldnames == (
            COMPARISON_FIELDNAMES
        )


def test_different_horizons_are_rejected(
    comparison_inputs,
) -> None:
    cp_sat_schedule = (
        comparison_inputs[
            "cp_sat_schedule"
        ].model_copy(
            update={
                "horizon_end_utc": (
                    comparison_inputs[
                        "cp_sat_schedule"
                    ].horizon_end_utc
                    + timedelta(hours=1)
                )
            }
        )
    )

    with pytest.raises(ValueError):
        build_planner_comparison(
            scenario_id="INVALID-HORIZON",
            greedy_schedule=(
                comparison_inputs[
                    "greedy_schedule"
                ]
            ),
            cp_sat_schedule=cp_sat_schedule,
            greedy_analysis=(
                comparison_inputs[
                    "greedy_analysis"
                ]
            ),
            cp_sat_analysis=(
                comparison_inputs[
                    "cp_sat_analysis"
                ]
            ),
        )


def test_different_request_counts_are_rejected(
    comparison_inputs,
) -> None:
    invalid_analysis = replace(
        comparison_inputs[
            "cp_sat_analysis"
        ],
        total_active_requests=79,
    )

    with pytest.raises(ValueError):
        build_planner_comparison(
            scenario_id="INVALID-REQUEST-COUNT",
            greedy_schedule=(
                comparison_inputs[
                    "greedy_schedule"
                ]
            ),
            cp_sat_schedule=(
                comparison_inputs[
                    "cp_sat_schedule"
                ]
            ),
            greedy_analysis=(
                comparison_inputs[
                    "greedy_analysis"
                ]
            ),
            cp_sat_analysis=invalid_analysis,
        )