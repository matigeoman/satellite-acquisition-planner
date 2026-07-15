import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


from app.analysis.planner_comparison import (
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

GREEDY_SCHEDULE_PATH = (
    PROJECT_ROOT
    / "data"
    / "stress_schedule_greedy.json"
)

CP_SAT_SCHEDULE_PATH = (
    PROJECT_ROOT
    / "data"
    / "stress_schedule_cp_sat.json"
)

REPORT_DIRECTORY = (
    PROJECT_ROOT
    / "data"
    / "reports"
)


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

    comparison = build_planner_comparison(
        scenario_id="STRESS-80-800",
        greedy_schedule=greedy_schedule,
        cp_sat_schedule=cp_sat_schedule,
        greedy_analysis=greedy_analysis,
        cp_sat_analysis=cp_sat_analysis,
        cp_sat_solver_status=extract_solver_status(
            cp_sat_schedule.notes
        ),
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
    print(
        f"  Greedy: "
        f"{comparison.greedy.objective_value:.6f}"
    )
    print(
        f"  CP-SAT: "
        f"{comparison.cp_sat.objective_value:.6f}"
    )
    print(
        f"  Różnica: "
        f"{comparison.objective_difference:.6f}"
    )
    print(
        f"  Poprawa: "
        f"{comparison.objective_improvement_pct:.2f}%"
    )
    print()

    print("REALIZACJA ZLECEŃ")
    print(
        f"  Greedy: "
        f"{comparison.greedy.fully_satisfied_requests}"
    )
    print(
        f"  CP-SAT: "
        f"{comparison.cp_sat.fully_satisfied_requests}"
    )
    print(
        f"  Dodatkowo zrealizowane przez CP-SAT: "
        f"{comparison.additional_fully_satisfied_requests}"
    )
    print(
        f"  Redukcja nieprzypisanych: "
        f"{comparison.unassigned_request_reduction}"
    )
    print()

    print("CZAS DZIAŁANIA")
    print(
        f"  Greedy: "
        f"{comparison.greedy.solver_runtime_s:.6f} s"
    )
    print(
        f"  CP-SAT: "
        f"{comparison.cp_sat.solver_runtime_s:.6f} s"
    )

    if runtime_ratio is not None:
        print(
            f"  CP-SAT / Greedy: "
            f"{runtime_ratio:.2f} razy"
        )

    print()
    print(
        f"Status CP-SAT: "
        f"{comparison.cp_sat.solver_status}"
    )
    print()

    print("ZAPISANE PLIKI")

    for report_name, path in paths.items():
        print(
            f"  {report_name}: {path}"
        )


if __name__ == "__main__":
    main()