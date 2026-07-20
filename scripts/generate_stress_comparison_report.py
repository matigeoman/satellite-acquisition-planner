from _bootstrap import PROJECT_PATHS


from app.analysis.planner_comparison import (
    build_planner_comparison,
    export_planner_comparison,
    extract_solver_status,
)
from app.analysis.schedule_report import (
    analyze_schedule,
)
from app.io import load_system_catalog
from app.io import load_opportunity_set
from app.io import load_request_set
from app.io import load_schedule


CATALOG_PATH = PROJECT_PATHS.scenario("STRESS").catalog

REQUEST_SET_PATH = PROJECT_PATHS.scenario("STRESS").requests

OPPORTUNITY_SET_PATH = PROJECT_PATHS.scenario("STRESS").opportunities

GREEDY_SCHEDULE_PATH = PROJECT_PATHS.reference_schedule(
    scenario_id="STRESS", algorithm_value="GREEDY"
)

CP_SAT_SCHEDULE_PATH = PROJECT_PATHS.reference_schedule(
    scenario_id="STRESS", algorithm_value="CP_SAT"
)

REPORT_DIRECTORY = PROJECT_PATHS.reports


def main() -> None:
    catalog = load_system_catalog(CATALOG_PATH)

    request_set = load_request_set(REQUEST_SET_PATH)

    opportunity_set = load_opportunity_set(
        OPPORTUNITY_SET_PATH,
        catalog=catalog,
        request_set=request_set,
    )

    greedy_schedule = load_schedule(GREEDY_SCHEDULE_PATH)

    cp_sat_schedule = load_schedule(CP_SAT_SCHEDULE_PATH)

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

    comparison = build_planner_comparison(
        scenario_id="STRESS-80-800",
        greedy_schedule=greedy_schedule,
        cp_sat_schedule=cp_sat_schedule,
        greedy_analysis=greedy_analysis,
        cp_sat_analysis=cp_sat_analysis,
        cp_sat_solver_status=extract_solver_status(cp_sat_schedule.notes),
    )

    paths = export_planner_comparison(
        comparison,
        REPORT_DIRECTORY,
        prefix="stress_comparison",
    )

    runtime_ratio = comparison.runtime_ratio

    print("RAPORT PORÓWNAWCZY GREEDY VS CP-SAT")
    print()

    print("FUNKCJA CELU")
    print(f"  Greedy: {comparison.greedy.objective_value:.6f}")
    print(f"  CP-SAT: {comparison.cp_sat.objective_value:.6f}")
    print(f"  Różnica: {comparison.objective_difference:.6f}")
    print(f"  Poprawa: {comparison.objective_improvement_pct:.2f}%")
    print()

    print("REALIZACJA ZLECEŃ")
    print(f"  Greedy: {comparison.greedy.fully_satisfied_requests}")
    print(f"  CP-SAT: {comparison.cp_sat.fully_satisfied_requests}")
    print(
        f"  Dodatkowo zrealizowane przez CP-SAT: "
        f"{comparison.additional_fully_satisfied_requests}"
    )
    print(f"  Redukcja nieprzypisanych: {comparison.unassigned_request_reduction}")
    print()

    print("CZAS DZIAŁANIA")
    print(f"  Greedy: {comparison.greedy.solver_runtime_s:.6f} s")
    print(f"  CP-SAT: {comparison.cp_sat.solver_runtime_s:.6f} s")

    if runtime_ratio is not None:
        print(f"  CP-SAT / Greedy: {runtime_ratio:.2f} razy")

    print()
    print(f"Status CP-SAT: {comparison.cp_sat.solver_status}")
    print()

    print("ZAPISANE PLIKI")

    for report_name, path in paths.items():
        print(f"  {report_name}: {path}")


if __name__ == "__main__":
    main()
