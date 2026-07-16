from datetime import datetime, timezone
from pathlib import Path


from _bootstrap import PROJECT_PATHS, PROJECT_ROOT


from app.analysis.scalability_benchmark import (
    ScalabilityRunResult,
    build_scalability_report,
    export_scalability_report,
)
from app.analysis.schedule_report import (
    analyze_schedule,
)
from app.io import load_system_catalog
from app.models.enums import RequestMode
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
from app.scenarios.scalability import (
    build_scalability_source,
    build_scalability_subset,
)
from app.io import save_schedule


CATALOG_PATH = PROJECT_PATHS.scenario("STRESS").catalog

REQUEST_SET_PATH = PROJECT_PATHS.scenario("STRESS").requests

OPPORTUNITY_SET_PATH = PROJECT_PATHS.scenario("STRESS").opportunities

BENCHMARK_DIRECTORY = PROJECT_PATHS.benchmarks / "scalability"

REPORT_DIRECTORY = PROJECT_PATHS.reports

REQUEST_COUNTS = (
    20,
    40,
    60,
    80,
    100,
)

CP_SAT_TIME_LIMIT_S = 10.0
MEMORY_RESERVE_RATIO = 0.15
RANDOM_SEED = 20260716


def main() -> None:
    catalog = load_system_catalog(
        CATALOG_PATH
    )

    stress_request_set = load_request_set(
        REQUEST_SET_PATH
    )

    stress_opportunity_set = load_opportunity_set(
        OPPORTUNITY_SET_PATH,
        catalog=catalog,
        request_set=stress_request_set,
    )

    (
        scalability_request_set,
        scalability_opportunity_set,
    ) = build_scalability_source(
        catalog=catalog,
        request_set=stress_request_set,
        opportunity_set=stress_opportunity_set,
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
        30,
        0,
        tzinfo=timezone.utc,
    )

    results: list[
        ScalabilityRunResult
    ] = []

    print("BENCHMARK SKALOWALNOŚCI")
    print()
    print(
        f"Limit CP-SAT: "
        f"{CP_SAT_TIME_LIMIT_S:g} s"
    )
    print(
        f"Rozmiary: {REQUEST_COUNTS}"
    )
    print()

    for request_count in REQUEST_COUNTS:
        print(
            f"SCENARIUSZ — {request_count} ZLECEŃ"
        )

        (
            request_set,
            opportunity_set,
        ) = build_scalability_subset(
            catalog=catalog,
            request_set=scalability_request_set,
            opportunity_set=scalability_opportunity_set,
            request_count=request_count,
        )

        opportunity_count = len(
            opportunity_set.feasible_opportunities
        )

        selection_variable_count = (
            opportunity_count
        )

        request_variable_count = len(
            request_set.active_requests
        )

        auxiliary_variable_count = sum(
            request.request_mode
            == RequestMode.DUAL_OPTIONAL
            for request in request_set.active_requests
        )

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
            schedule_id=(
                "SCHEDULE-SCALE-GREEDY-"
                f"{request_count:03d}"
            ),
            name=(
                "Benchmark skalowalności Greedy — "
                f"{request_count} zleceń"
            ),
            created_at_utc=created_at,
        )

        greedy_path = (
            BENCHMARK_DIRECTORY
            / (
                f"scale_{request_count:03d}"
                "_greedy.json"
            )
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

        greedy_result = ScalabilityRunResult(
            request_count=request_count,
            opportunity_count=opportunity_count,
            selection_variable_count=(
                selection_variable_count
            ),
            request_variable_count=(
                request_variable_count
            ),
            auxiliary_variable_count=(
                auxiliary_variable_count
            ),
            algorithm="GREEDY",
            time_limit_s=None,
            solver_status="NOT_APPLICABLE",
            schedule_status=(
                greedy_schedule.status.value
            ),
            objective_value=float(
                greedy_schedule.objective_value
                or 0.0
            ),
            fully_satisfied_requests=(
                greedy_analysis
                .fully_satisfied_requests
            ),
            unassigned_requests=(
                greedy_analysis
                .unassigned_requests
            ),
            satisfaction_ratio=(
                greedy_analysis
                .satisfaction_ratio
            ),
            total_acquisitions=(
                greedy_analysis
                .total_acquisitions
            ),
            runtime_s=float(
                greedy_schedule.solver_runtime_s
                or 0.0
            ),
            schedule_path=str(
                greedy_path
            ),
        )

        results.append(
            greedy_result
        )

        print(
            f"  Greedy: "
            f"cel={greedy_result.objective_value:.3f}, "
            f"zlecenia="
            f"{greedy_result.fully_satisfied_requests}, "
            f"czas={greedy_result.runtime_s:.6f} s"
        )

        cp_sat_scheduler = CpSatScheduler(
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
                max_time_s=CP_SAT_TIME_LIMIT_S,
                num_search_workers=1,
                random_seed=RANDOM_SEED,
                log_search_progress=False,
            ),
        )

        cp_sat_schedule = (
            cp_sat_scheduler.build_schedule(
                schedule_id=(
                    "SCHEDULE-SCALE-CP-SAT-"
                    f"{request_count:03d}"
                ),
                name=(
                    "Benchmark skalowalności CP-SAT — "
                    f"{request_count} zleceń"
                ),
                created_at_utc=created_at,
            )
        )

        cp_sat_path = (
            BENCHMARK_DIRECTORY
            / (
                f"scale_{request_count:03d}"
                "_cp_sat.json"
            )
        )

        save_schedule(
            cp_sat_schedule,
            cp_sat_path,
        )

        cp_sat_analysis = analyze_schedule(
            catalog=catalog,
            request_set=request_set,
            opportunity_set=opportunity_set,
            schedule=cp_sat_schedule,
        )

        cp_sat_result = ScalabilityRunResult(
            request_count=request_count,
            opportunity_count=opportunity_count,
            selection_variable_count=(
                selection_variable_count
            ),
            request_variable_count=(
                request_variable_count
            ),
            auxiliary_variable_count=(
                auxiliary_variable_count
            ),
            algorithm="CP_SAT",
            time_limit_s=CP_SAT_TIME_LIMIT_S,
            solver_status=(
                cp_sat_scheduler.last_solver_status
                or "UNKNOWN"
            ),
            schedule_status=(
                cp_sat_schedule.status.value
            ),
            objective_value=float(
                cp_sat_schedule.objective_value
                or 0.0
            ),
            fully_satisfied_requests=(
                cp_sat_analysis
                .fully_satisfied_requests
            ),
            unassigned_requests=(
                cp_sat_analysis
                .unassigned_requests
            ),
            satisfaction_ratio=(
                cp_sat_analysis
                .satisfaction_ratio
            ),
            total_acquisitions=(
                cp_sat_analysis
                .total_acquisitions
            ),
            runtime_s=float(
                cp_sat_schedule.solver_runtime_s
                or 0.0
            ),
            schedule_path=str(
                cp_sat_path
            ),
        )

        results.append(
            cp_sat_result
        )

        if greedy_result.objective_value > 0.0:
            improvement_pct = (
                (
                    cp_sat_result.objective_value
                    - greedy_result.objective_value
                )
                / greedy_result.objective_value
                * 100.0
            )
        else:
            improvement_pct = 0.0

        print(
            f"  CP-SAT: "
            f"cel={cp_sat_result.objective_value:.3f}, "
            f"zlecenia="
            f"{cp_sat_result.fully_satisfied_requests}, "
            f"czas={cp_sat_result.runtime_s:.6f} s, "
            f"status={cp_sat_result.solver_status}"
        )
        print(
            f"  Poprawa celu: "
            f"{improvement_pct:.2f}%"
        )
        print(
            f"  Zmienne binarne — szacunek: "
            f"{cp_sat_result.estimated_boolean_variable_count}"
        )
        print()

    report = build_scalability_report(
        scenario_id="SCALABILITY-20-100",
        results=results,
    )

    paths = export_scalability_report(
        report,
        REPORT_DIRECTORY,
        prefix="scalability_benchmark",
    )

    print("ZAPISANE RAPORTY")

    for report_name, path in paths.items():
        print(
            f"  {report_name}: {path}"
        )


if __name__ == "__main__":
    main()