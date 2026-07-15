import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


from app.analysis.schedule_report import (
    analyze_schedule,
    export_schedule_analysis,
)
from app.catalog_loader import load_system_catalog
from app.opportunity_loader import load_opportunity_set
from app.planning.cp_sat import (
    CpSatPlannerConfig,
    CpSatScheduler,
)
from app.planning.greedy import (
    GreedyPlannerConfig,
    build_greedy_schedule,
)
from app.request_loader import load_request_set
from app.schedule_loader import save_schedule


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

GREEDY_OUTPUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "stress_schedule_greedy.json"
)

CP_SAT_OUTPUT_PATH = (
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

    created_at = datetime(
        2026,
        7,
        15,
        22,
        0,
        0,
        tzinfo=timezone.utc,
    )

    greedy_schedule = build_greedy_schedule(
        catalog=catalog,
        request_set=request_set,
        opportunity_set=opportunity_set,
        config=GreedyPlannerConfig(
            memory_reserve_ratio=0.15,
            priority_weight=10.0,
            quality_weight=3.0,
            coverage_weight=2.0,
            mandatory_bonus=100.0,
            dual_optional_second_bonus=5.0,
        ),
        schedule_id="SCHEDULE-STRESS-GREEDY",
        name="Stresowy harmonogram Greedy",
        created_at_utc=created_at,
    )

    cp_sat_scheduler = CpSatScheduler(
        catalog=catalog,
        request_set=request_set,
        opportunity_set=opportunity_set,
        config=CpSatPlannerConfig(
            memory_reserve_ratio=0.15,
            priority_weight=10.0,
            quality_weight=3.0,
            coverage_weight=2.0,
            mandatory_bonus=100.0,
            dual_optional_second_bonus=5.0,
            force_mandatory_requests=True,
            max_time_s=30.0,
            num_search_workers=1,
            random_seed=20260716,
        ),
    )

    cp_sat_schedule = cp_sat_scheduler.build_schedule(
        schedule_id="SCHEDULE-STRESS-CP-SAT",
        name="Stresowy harmonogram CP-SAT",
        created_at_utc=created_at,
    )

    save_schedule(
        greedy_schedule,
        GREEDY_OUTPUT_PATH,
    )

    save_schedule(
        cp_sat_schedule,
        CP_SAT_OUTPUT_PATH,
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

    export_schedule_analysis(
        greedy_analysis,
        REPORT_DIRECTORY,
        prefix="stress_greedy",
    )

    export_schedule_analysis(
        cp_sat_analysis,
        REPORT_DIRECTORY,
        prefix="stress_cp_sat",
    )

    greedy_objective = (
        greedy_schedule.objective_value
        or 0.0
    )

    cp_sat_objective = (
        cp_sat_schedule.objective_value
        or 0.0
    )

    objective_difference = (
        cp_sat_objective
        - greedy_objective
    )

    if greedy_objective > 0.0:
        improvement_ratio = (
            objective_difference
            / greedy_objective
        )
    else:
        improvement_ratio = 0.0

    additional_fully_satisfied_requests = (
        cp_sat_analysis.fully_satisfied_requests
        - greedy_analysis.fully_satisfied_requests
    )

    print("PORÓWNANIE SCENARIUSZA STRESOWEGO")
    print()

    print("GREEDY")
    print(
        f"  Status: "
        f"{greedy_schedule.status.value}"
    )
    print(
        f"  Zrealizowane zlecenia: "
        f"{greedy_analysis.fully_satisfied_requests}"
    )
    print(
        f"  Częściowo zrealizowane: "
        f"{greedy_analysis.partially_satisfied_requests}"
    )
    print(
        f"  Nieprzypisane: "
        f"{greedy_analysis.unassigned_requests}"
    )
    print(
        f"  Akwizycje: "
        f"{greedy_schedule.total_acquisitions}"
    )
    print(
        f"  Funkcja celu: "
        f"{greedy_objective:.6f}"
    )
    print(
        f"  Czas: "
        f"{greedy_schedule.solver_runtime_s:.6f} s"
    )
    print()

    print("CP-SAT")
    print(
        f"  Status solvera: "
        f"{cp_sat_scheduler.last_solver_status}"
    )
    print(
        f"  Status harmonogramu: "
        f"{cp_sat_schedule.status.value}"
    )
    print(
        f"  Zrealizowane zlecenia: "
        f"{cp_sat_analysis.fully_satisfied_requests}"
    )
    print(
        f"  Częściowo zrealizowane: "
        f"{cp_sat_analysis.partially_satisfied_requests}"
    )
    print(
        f"  Nieprzypisane: "
        f"{cp_sat_analysis.unassigned_requests}"
    )
    print(
        f"  Akwizycje: "
        f"{cp_sat_schedule.total_acquisitions}"
    )
    print(
        f"  Funkcja celu: "
        f"{cp_sat_objective:.6f}"
    )
    print(
        f"  Czas: "
        f"{cp_sat_schedule.solver_runtime_s:.6f} s"
    )
    print()

    print("RÓŻNICA")
    print(
        f"  CP-SAT - Greedy: "
        f"{objective_difference:.6f}"
    )
    print(
        f"  Poprawa względna: "
        f"{improvement_ratio:.2%}"
    )
    print(
        f"  Dodatkowo zrealizowane zlecenia: "
        f"{additional_fully_satisfied_requests}"
    )
    print()

    print("ZAPISANE HARMONOGRAMY")
    print(
        f"  Greedy: {GREEDY_OUTPUT_PATH}"
    )
    print(
        f"  CP-SAT: {CP_SAT_OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()