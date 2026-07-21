from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest

from app.analysis.algorithm_benchmark import (
    AlgorithmBenchmarkConfig,
    AlgorithmBenchmarkResult,
    BenchmarkRunRecord,
    build_benchmark_pairs,
    build_benchmark_summary,
)
from app.scenarios.scalability import build_scalability_source
from app.services.benchmark_service import AlgorithmBenchmarkService
from app.services.scenario_service import ScenarioService
from app.ui.benchmark_view import (
    build_benchmark_export_zip,
    build_benchmark_improvement_figure,
    build_benchmark_objective_figure,
    build_benchmark_rejections_figure,
    build_benchmark_runtime_figure,
    build_benchmark_satisfaction_figure,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _record(
    *,
    algorithm: str,
    repetition: int = 1,
    limit: float | None = None,
    objective: float = 100.0,
    runtime: float = 1.0,
    fulfilled: int = 8,
    error: str = "",
) -> BenchmarkRunRecord:
    return BenchmarkRunRecord(
        request_count=10,
        repetition=repetition,
        algorithm=algorithm,
        time_limit_s=limit,
        random_seed=100 + repetition,
        opportunity_count=100,
        feasible_opportunity_count=100,
        estimated_boolean_variable_count=112,
        solver_status="OPTIMAL" if not error else "ERROR",
        schedule_status="FEASIBLE" if not error else "ERROR",
        objective_value=objective,
        fully_satisfied_requests=fulfilled,
        partially_satisfied_requests=0,
        unassigned_requests=10 - fulfilled,
        mandatory_satisfied_requests=1,
        satisfaction_ratio=fulfilled / 10,
        total_acquisitions=fulfilled,
        sar_acquisitions=fulfilled // 2,
        optical_acquisitions=fulfilled - fulfilled // 2,
        total_duration_s=80.0,
        total_data_volume_mb=500.0,
        average_selected_quality=0.8,
        runtime_s=runtime,
        transition_rejections=1,
        memory_rejections=2,
        acquisition_limit_rejections=3,
        imaging_time_rejections=4,
        dual_separation_rejections=5,
        error_message=error,
    )


def _result(
    records: tuple[BenchmarkRunRecord, ...],
    *,
    limits: tuple[float, ...],
) -> AlgorithmBenchmarkResult:
    now = datetime.now(timezone.utc)
    return AlgorithmBenchmarkResult(
        base_scenario_id="TEST",
        config=AlgorithmBenchmarkConfig(
            request_counts=(10,),
            cp_sat_time_limits_s=limits,
        ),
        run_records=records,
        pair_records=build_benchmark_pairs(records),
        summary_records=build_benchmark_summary(records),
        started_at_utc=now,
        completed_at_utc=now,
        wall_clock_runtime_s=1.0,
    )


def test_config_normalizes_counts_and_limits() -> None:
    config = AlgorithmBenchmarkConfig(
        request_counts=(100, 20, 100, 50),
        cp_sat_time_limits_s=(5.0, 1.0, 5.0),
        repetitions=2,
    )

    assert config.request_counts == (20, 50, 100)
    assert config.cp_sat_time_limits_s == (1.0, 5.0)
    assert config.expected_run_count == 18
    assert config.estimated_cp_sat_budget_s == 36.0


def test_config_rejects_more_than_500_requests() -> None:
    with pytest.raises(ValueError, match="500"):
        AlgorithmBenchmarkConfig(request_counts=(501,))


def test_pairs_and_summary_compare_cp_sat_to_greedy() -> None:
    records = (
        _record(algorithm="GREEDY", objective=100.0, runtime=0.1),
        _record(
            algorithm="CP_SAT",
            limit=2.0,
            objective=120.0,
            runtime=2.0,
            fulfilled=9,
        ),
    )

    pairs = build_benchmark_pairs(records)
    summary = build_benchmark_summary(records)

    assert len(pairs) == 1
    assert pairs[0].objective_difference == pytest.approx(20.0)
    assert pairs[0].objective_improvement_pct == pytest.approx(20.0)
    assert pairs[0].runtime_ratio == pytest.approx(20.0)
    assert len(summary) == 2


def test_failed_cp_sat_is_kept_without_numeric_comparison() -> None:
    records = (
        _record(algorithm="GREEDY"),
        _record(algorithm="CP_SAT", limit=0.5, error="UNKNOWN"),
    )

    pair = build_benchmark_pairs(records)[0]

    assert pair.cp_sat_successful is False
    assert pair.objective_difference is None
    assert pair.cp_sat_objective_value is None


def test_scalability_source_supports_500_requests() -> None:
    scenario = ScenarioService(project_root=PROJECT_ROOT).load("STRESS")

    request_set, opportunity_set = build_scalability_source(
        catalog=scenario.catalog,
        request_set=scenario.request_set,
        opportunity_set=scenario.opportunity_set,
        target_request_count=500,
    )

    assert len(request_set.active_requests) == 500
    assert len(opportunity_set.opportunities) == 5000
    opportunity_set.validate_against(scenario.catalog, request_set)


def test_service_runs_small_real_benchmark() -> None:
    scenario = ScenarioService(project_root=PROJECT_ROOT).load("STRESS")
    result = AlgorithmBenchmarkService().run(
        base_scenario=scenario,
        config=AlgorithmBenchmarkConfig(
            request_counts=(20,),
            repetitions=1,
            cp_sat_time_limits_s=(0.2,),
            use_dynamic_transition_model=False,
        ),
    )

    assert len(result.run_records) == 2
    assert len(result.pair_records) == 1
    assert result.successful_run_count == 2
    assert {record.algorithm for record in result.run_records} == {
        "GREEDY",
        "CP_SAT",
    }


def test_export_zip_contains_research_files() -> None:
    config = AlgorithmBenchmarkConfig(
        request_counts=(10,),
        cp_sat_time_limits_s=(2.0,),
    )
    records = (
        _record(algorithm="GREEDY"),
        _record(algorithm="CP_SAT", limit=2.0, objective=110.0),
    )
    now = datetime.now(timezone.utc)
    result = AlgorithmBenchmarkResult(
        base_scenario_id="TEST",
        config=config,
        run_records=records,
        pair_records=build_benchmark_pairs(records),
        summary_records=build_benchmark_summary(records),
        started_at_utc=now,
        completed_at_utc=now,
        wall_clock_runtime_s=2.0,
    )

    archive = ZipFile(BytesIO(build_benchmark_export_zip(result)))

    assert set(archive.namelist()) == {
        "benchmark_runs.csv",
        "benchmark_pairs.csv",
        "benchmark_summary.csv",
        "benchmark_results.json",
        "benchmark_charts.html",
    }


def test_service_reuses_one_seed_across_cp_sat_time_limits() -> None:
    scenario = ScenarioService(project_root=PROJECT_ROOT).load("STRESS")
    result = AlgorithmBenchmarkService().run(
        base_scenario=scenario,
        config=AlgorithmBenchmarkConfig(
            request_counts=(10,),
            repetitions=1,
            cp_sat_time_limits_s=(0.05, 0.1),
            use_dynamic_transition_model=False,
        ),
    )

    assert len(result.run_records) == 3
    assert len({record.random_seed for record in result.run_records}) == 1
    assert {record.random_seed for record in result.pair_records} == {
        result.run_records[0].random_seed
    }


def test_single_request_count_uses_readable_bar_charts() -> None:
    records = (
        _record(algorithm="GREEDY", objective=100.0, runtime=0.1),
        _record(algorithm="CP_SAT", limit=2.0, objective=99.0, runtime=2.0),
        _record(algorithm="CP_SAT", limit=5.0, objective=103.0, runtime=5.0),
        _record(algorithm="CP_SAT", limit=10.0, objective=105.0, runtime=10.0),
    )
    result = _result(records, limits=(2.0, 5.0, 10.0))

    for figure in (
        build_benchmark_runtime_figure(result),
        build_benchmark_objective_figure(result),
        build_benchmark_satisfaction_figure(result),
        build_benchmark_improvement_figure(result),
    ):
        assert figure.data
        assert all(trace.type == "bar" for trace in figure.data)
        assert "10 zleceń" in figure.layout.title.text

    improvement = build_benchmark_improvement_figure(result)
    assert improvement.layout.shapes
    assert {value for trace in improvement.data for value in trace.x} == {
        "CP-SAT 2s",
        "CP-SAT 5s",
        "CP-SAT 10s",
    }


def test_rejection_chart_uses_stacked_variant_bars_without_zero_series() -> None:
    records = (
        _record(algorithm="GREEDY"),
        _record(algorithm="CP_SAT", limit=2.0),
    )
    result = _result(records, limits=(2.0,))

    figure = build_benchmark_rejections_figure(result)

    assert figure.data
    assert figure.layout.barmode == "stack"
    assert any(
        "Liczba zleceń: 10" in annotation.text
        for annotation in figure.layout.annotations
    )
    assert all(
        all(float(value) > 0.0 for value in trace.y)
        for trace in figure.data
    )
