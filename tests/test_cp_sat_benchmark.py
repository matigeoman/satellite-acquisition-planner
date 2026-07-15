import csv
from pathlib import Path

import pytest

from app.analysis.cp_sat_benchmark import (
    BENCHMARK_FIELDNAMES,
    BenchmarkReport,
    BenchmarkResult,
    build_benchmark_report,
    export_benchmark_report,
    format_time_limit_label,
)


def make_greedy_result() -> BenchmarkResult:
    return BenchmarkResult(
        algorithm="GREEDY",
        time_limit_s=None,
        solver_status="NOT_APPLICABLE",
        schedule_status="FEASIBLE",
        schedule_id="SCHEDULE-TEST-GREEDY",
        objective_value=100.0,
        fully_satisfied_requests=10,
        partially_satisfied_requests=0,
        unassigned_requests=10,
        mandatory_satisfied_requests=2,
        total_acquisitions=12,
        sar_acquisitions=6,
        optical_acquisitions=6,
        total_duration_s=300.0,
        total_data_volume_mb=5000.0,
        average_selected_quality=0.7,
        average_selected_coverage=0.95,
        satisfaction_ratio=0.5,
        runtime_s=0.01,
        schedule_path="greedy.json",
    )


def make_cp_sat_result(
    *,
    time_limit_s: float,
    objective_value: float,
    fulfilled: int,
    runtime_s: float,
) -> BenchmarkResult:
    return BenchmarkResult(
        algorithm="CP_SAT",
        time_limit_s=time_limit_s,
        solver_status="FEASIBLE",
        schedule_status="FEASIBLE",
        schedule_id=(
            "SCHEDULE-TEST-CP-SAT-"
            f"{format_time_limit_label(time_limit_s)}"
        ),
        objective_value=objective_value,
        fully_satisfied_requests=fulfilled,
        partially_satisfied_requests=0,
        unassigned_requests=20 - fulfilled,
        mandatory_satisfied_requests=2,
        total_acquisitions=fulfilled + 2,
        sar_acquisitions=(fulfilled + 2) // 2,
        optical_acquisitions=(fulfilled + 2) // 2,
        total_duration_s=350.0,
        total_data_volume_mb=5500.0,
        average_selected_quality=0.75,
        average_selected_coverage=0.96,
        satisfaction_ratio=fulfilled / 20.0,
        runtime_s=runtime_s,
        schedule_path=(
            f"cp_sat_{time_limit_s:g}.json"
        ),
    )


@pytest.fixture
def benchmark_report() -> BenchmarkReport:
    return build_benchmark_report(
        scenario_id="TEST-SCENARIO",
        greedy=make_greedy_result(),
        cp_sat_runs=[
            make_cp_sat_result(
                time_limit_s=10.0,
                objective_value=145.0,
                fulfilled=14,
                runtime_s=10.0,
            ),
            make_cp_sat_result(
                time_limit_s=1.0,
                objective_value=120.0,
                fulfilled=12,
                runtime_s=1.0,
            ),
            make_cp_sat_result(
                time_limit_s=5.0,
                objective_value=135.0,
                fulfilled=13,
                runtime_s=5.0,
            ),
        ],
    )


def test_time_limit_label_for_integer() -> None:
    assert format_time_limit_label(
        10.0
    ) == "10S"


def test_time_limit_label_for_fraction() -> None:
    assert format_time_limit_label(
        0.5
    ) == "0P5S"


def test_invalid_time_limit_label_is_rejected() -> None:
    with pytest.raises(ValueError):
        format_time_limit_label(
            0.0
        )


def test_report_sorts_cp_sat_runs(
    benchmark_report,
) -> None:
    assert [
        result.time_limit_s
        for result in benchmark_report.cp_sat_runs
    ] == [
        1.0,
        5.0,
        10.0,
    ]


def test_best_cp_sat_run_is_selected(
    benchmark_report,
) -> None:
    assert (
        benchmark_report
        .best_cp_sat_run
        .time_limit_s
        == 10.0
    )

    assert (
        benchmark_report
        .best_cp_sat_run
        .objective_value
        == 145.0
    )


def test_best_improvement_is_calculated(
    benchmark_report,
) -> None:
    assert (
        benchmark_report.best_objective_difference
        == pytest.approx(45.0)
    )

    assert (
        benchmark_report
        .best_objective_improvement_pct
        == pytest.approx(45.0)
    )


def test_csv_contains_greedy_and_all_cp_sat_runs(
    benchmark_report,
) -> None:
    rows = benchmark_report.csv_rows()

    assert len(rows) == 4

    assert rows[0]["algorithm"] == "GREEDY"

    assert [
        row["time_limit_s"]
        for row in rows[1:]
    ] == [
        1.0,
        5.0,
        10.0,
    ]


def test_cp_sat_csv_row_contains_differences(
    benchmark_report,
) -> None:
    best_row = benchmark_report.csv_rows()[-1]

    assert (
        best_row[
            "objective_difference_vs_greedy"
        ]
        == pytest.approx(45.0)
    )

    assert (
        best_row[
            "fulfilled_difference_vs_greedy"
        ]
        == 4
    )

    assert (
        best_row[
            "unassigned_reduction_vs_greedy"
        ]
        == 4
    )


def test_duplicate_time_limits_are_rejected() -> None:
    duplicate = make_cp_sat_result(
        time_limit_s=5.0,
        objective_value=130.0,
        fulfilled=13,
        runtime_s=5.0,
    )

    with pytest.raises(ValueError):
        build_benchmark_report(
            scenario_id="DUPLICATE-LIMIT",
            greedy=make_greedy_result(),
            cp_sat_runs=[
                duplicate,
                duplicate,
            ],
        )


def test_empty_scenario_id_is_rejected() -> None:
    with pytest.raises(ValueError):
        build_benchmark_report(
            scenario_id=" ",
            greedy=make_greedy_result(),
            cp_sat_runs=[
                make_cp_sat_result(
                    time_limit_s=1.0,
                    objective_value=120.0,
                    fulfilled=12,
                    runtime_s=1.0,
                )
            ],
        )


def test_greedy_cannot_have_time_limit() -> None:
    with pytest.raises(ValueError):
        BenchmarkResult(
            algorithm="GREEDY",
            time_limit_s=1.0,
            solver_status="NOT_APPLICABLE",
            schedule_status="FEASIBLE",
            schedule_id="SCHEDULE-INVALID",
            objective_value=1.0,
            fully_satisfied_requests=1,
            partially_satisfied_requests=0,
            unassigned_requests=0,
            mandatory_satisfied_requests=0,
            total_acquisitions=1,
            sar_acquisitions=1,
            optical_acquisitions=0,
            total_duration_s=1.0,
            total_data_volume_mb=1.0,
            average_selected_quality=1.0,
            average_selected_coverage=1.0,
            satisfaction_ratio=1.0,
            runtime_s=0.1,
            schedule_path="invalid.json",
        )


def test_export_creates_csv_and_charts(
    tmp_path: Path,
    benchmark_report,
) -> None:
    paths = export_benchmark_report(
        benchmark_report,
        tmp_path,
    )

    assert set(paths) == {
        "csv",
        "objective_chart",
        "fulfilled_chart",
        "runtime_chart",
    }

    assert all(
        path.exists()
        for path in paths.values()
    )

    assert all(
        path.stat().st_size > 0
        for path in paths.values()
    )


def test_exported_csv_has_expected_header(
    tmp_path: Path,
    benchmark_report,
) -> None:
    paths = export_benchmark_report(
        benchmark_report,
        tmp_path,
    )

    with paths["csv"].open(
        encoding="utf-8-sig",
        newline="",
    ) as file:
        reader = csv.DictReader(
            file
        )

        assert reader.fieldnames == (
            BENCHMARK_FIELDNAMES
        )

        rows = list(
            reader
        )

    assert len(rows) == 4