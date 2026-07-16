from datetime import datetime, timezone
from pathlib import Path


from _bootstrap import PROJECT_ROOT


from app.analysis.cp_sat_benchmark import (
    build_benchmark_report,
    build_benchmark_result,
    export_benchmark_report,
    format_time_limit_label,
)
from app.analysis.schedule_report import (
    analyze_schedule,
)
from app.io import load_system_catalog
from app.io import load_opportunity_set
from app.planning.cp_sat import (
    CpSatPlannerConfig,
    CpSatScheduler,
)
from app.planning.greedy import (
    GreedyPlannerConfig,
    build_greedy_schedule,
)
from app.io import load_request_set
from app.io import save_schedule


CATALOG_PATH = (
    PROJECT_ROOT
    / "data"
    / "stress_system.json"
)

REQUEST_SET_PATH = (
    PROJECT_ROOT
    / "data"
    / "stress_requests.json"
)

OPPORTUNITY_SET_PATH = (
    PROJECT_ROOT
    / "data"
    / "stress_opportunities.json"
)

BENCHMARK_DIRECTORY = (
    PROJECT_ROOT
    / "data"
    / "benchmarks"
)

REPORT_DIRECTORY = (
    PROJECT_ROOT
    / "data"
    / "reports"
)

TIME_LIMITS_S = (
    1.0,
    5.0,
    10.0,
    30.0,
)

MEMORY_RESERVE_RATIO = 0.15
RANDOM_SEED = 20260716


def main() -> None:
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

    BENCHMARK_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    created_at = datetime(
        2026,
        7,
        15,
        23,
        0,
        0,
        tzinfo=timezone.utc,
    )

    print("BENCHMARK GREEDY VS CP-SAT")
    print()

    greedy_schedule = build_greedy_schedule(
        catalog=catalog,
        request_set=request_set,
        opportunity_set=opportunity_set,
        config=GreedyPlannerConfig(
            memory_reserve_ratio=(
                MEMORY_RESERVE_RATIO
            ),
            priority_weight=10.0,
            quality_weight=3.0,
            coverage_weight=2.0,
            mandatory_bonus=100.0,
            dual_optional_second_bonus=5.0,
        ),
        schedule_id="SCHEDULE-BENCHMARK-GREEDY",
        name="Benchmark stresowy Greedy",
        created_at_utc=created_at,
    )

    greedy_path = (
        BENCHMARK_DIRECTORY
        / "stress_benchmark_greedy.json"
    )

    save_schedule(
        greedy_schedule,
        greedy_path,
    )

    greedy_analysis = analyze_schedule(
        catalog=catalog,
        request_set=request_set,
        opportunity_set=opportunity_set,
        schedule=greedy_schedule,
    )

    greedy_result = build_benchmark_result(
        schedule=greedy_schedule,
        analysis=greedy_analysis,
        solver_status="NOT_APPLICABLE",
        time_limit_s=None,
        schedule_path=greedy_path,
    )

    print("GREEDY")
    print(
        f"  Funkcja celu: "
        f"{greedy_result.objective_value:.6f}"
    )
    print(
        f"  Zrealizowane zlecenia: "
        f"{greedy_result.fully_satisfied_requests}"
    )
    print(
        f"  Czas: "
        f"{greedy_result.runtime_s:.6f} s"
    )
    print()

    cp_sat_results = []

    for time_limit_s in TIME_LIMITS_S:
        label = format_time_limit_label(
            time_limit_s
        )

        schedule_id = (
            f"SCHEDULE-BENCHMARK-CP-SAT-{label}"
        )

        scheduler = CpSatScheduler(
            catalog=catalog,
            request_set=request_set,
            opportunity_set=opportunity_set,
            config=CpSatPlannerConfig(
                memory_reserve_ratio=(
                    MEMORY_RESERVE_RATIO
                ),
                priority_weight=10.0,
                quality_weight=3.0,
                coverage_weight=2.0,
                mandatory_bonus=100.0,
                dual_optional_second_bonus=5.0,
                force_mandatory_requests=True,
                max_time_s=time_limit_s,
                num_search_workers=1,
                random_seed=RANDOM_SEED,
                log_search_progress=False,
            ),
        )

        print(
            f"CP-SAT — limit {time_limit_s:g} s"
        )

        schedule = scheduler.build_schedule(
            schedule_id=schedule_id,
            name=(
                "Benchmark stresowy CP-SAT — "
                f"limit {time_limit_s:g} s"
            ),
            created_at_utc=created_at,
        )

        schedule_path = (
            BENCHMARK_DIRECTORY
            / (
                "stress_benchmark_cp_sat_"
                f"{label.lower()}.json"
            )
        )

        save_schedule(
            schedule,
            schedule_path,
        )

        analysis = analyze_schedule(
            catalog=catalog,
            request_set=request_set,
            opportunity_set=opportunity_set,
            schedule=schedule,
        )

        result = build_benchmark_result(
            schedule=schedule,
            analysis=analysis,
            solver_status=(
                scheduler.last_solver_status
                or "UNKNOWN"
            ),
            time_limit_s=time_limit_s,
            schedule_path=schedule_path,
        )

        cp_sat_results.append(
            result
        )

        print(
            f"  Status: "
            f"{result.solver_status}"
        )
        print(
            f"  Funkcja celu: "
            f"{result.objective_value:.6f}"
        )
        print(
            f"  Zrealizowane zlecenia: "
            f"{result.fully_satisfied_requests}"
        )
        print(
            f"  Nieprzypisane: "
            f"{result.unassigned_requests}"
        )
        print(
            f"  Czas: "
            f"{result.runtime_s:.6f} s"
        )
        print()

    report = build_benchmark_report(
        scenario_id="STRESS-80-800",
        greedy=greedy_result,
        cp_sat_runs=cp_sat_results,
    )

    report_paths = export_benchmark_report(
        report,
        REPORT_DIRECTORY,
        prefix="cp_sat_benchmark",
    )

    best = report.best_cp_sat_run

    print("NAJLEPSZY WYNIK")
    print(
        f"  Limit czasu: "
        f"{best.time_limit_s:g} s"
    )
    print(
        f"  Status: "
        f"{best.solver_status}"
    )
    print(
        f"  Funkcja celu: "
        f"{best.objective_value:.6f}"
    )
    print(
        f"  Zrealizowane zlecenia: "
        f"{best.fully_satisfied_requests}"
    )
    print(
        f"  Poprawa względem Greedy: "
        f"{report.best_objective_improvement_pct:.2f}%"
    )
    print()

    print("ZAPISANE RAPORTY")

    for report_name, path in report_paths.items():
        print(
            f"  {report_name}: {path}"
        )


if __name__ == "__main__":
    main()