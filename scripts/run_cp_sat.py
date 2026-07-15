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
from app.request_loader import load_request_set
from app.schedule_loader import (
    load_schedule,
    save_schedule,
)


CATALOG_PATH = (
    PROJECT_ROOT
    / "data"
    / "example_system.json"
)

REQUEST_SET_PATH = (
    PROJECT_ROOT
    / "data"
    / "example_requests.json"
)

OPPORTUNITY_SET_PATH = (
    PROJECT_ROOT
    / "data"
    / "example_opportunities.json"
)

GREEDY_SCHEDULE_PATH = (
    PROJECT_ROOT
    / "data"
    / "example_schedule_greedy.json"
)

OUTPUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "example_schedule_cp_sat.json"
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

    config = CpSatPlannerConfig(
        memory_reserve_ratio=0.0,
        priority_weight=10.0,
        quality_weight=3.0,
        coverage_weight=2.0,
        mandatory_bonus=100.0,
        dual_optional_second_bonus=5.0,
        force_mandatory_requests=True,
        max_time_s=30.0,
        num_search_workers=1,
        random_seed=20260715,
    )

    scheduler = CpSatScheduler(
        catalog=catalog,
        request_set=request_set,
        opportunity_set=opportunity_set,
        config=config,
    )

    schedule = scheduler.build_schedule(
        schedule_id="SCHEDULE-CP-SAT-001",
        name="Przykładowy dobowy harmonogram CP-SAT",
        created_at_utc=datetime(
            2026,
            7,
            14,
            22,
            30,
            0,
            tzinfo=timezone.utc,
        ),
    )

    save_schedule(
        schedule,
        OUTPUT_PATH,
    )

    analysis = analyze_schedule(
        catalog=catalog,
        request_set=request_set,
        opportunity_set=opportunity_set,
        schedule=schedule,
    )

    report_paths = export_schedule_analysis(
        analysis,
        REPORT_DIRECTORY,
        prefix="cp_sat",
    )

    print("CP-SAT SCHEDULER")
    print()

    print(
        f"Status solvera: "
        f"{scheduler.last_solver_status}"
    )
    print(
        f"Status harmonogramu: "
        f"{schedule.status.value}"
    )
    print(
        f"Zaplanowane akwizycje: "
        f"{schedule.total_acquisitions}"
    )
    print(
        f"Zaplanowane zlecenia: "
        f"{len(schedule.scheduled_request_ids)}"
    )
    print(
        f"Nieprzypisane zlecenia: "
        f"{len(schedule.unassigned_request_ids)}"
    )
    print(
        f"Łączny czas obrazowania: "
        f"{schedule.total_duration_s:.3f} s"
    )
    print(
        f"Łączny rozmiar danych: "
        f"{schedule.total_data_volume_mb:.3f} MB"
    )
    print(
        f"Wartość funkcji celu: "
        f"{schedule.objective_value:.6f}"
    )
    print(
        f"Czas działania solvera: "
        f"{schedule.solver_runtime_s:.6f} s"
    )

    if GREEDY_SCHEDULE_PATH.exists():
        greedy_schedule = load_schedule(
            GREEDY_SCHEDULE_PATH
        )

        greedy_objective = (
            greedy_schedule.objective_value
            or 0.0
        )

        cp_sat_objective = (
            schedule.objective_value
            or 0.0
        )

        difference = (
            cp_sat_objective
            - greedy_objective
        )

        print()
        print("PORÓWNANIE Z GREEDY")
        print(
            f"Greedy: "
            f"{greedy_objective:.6f}"
        )
        print(
            f"CP-SAT: "
            f"{cp_sat_objective:.6f}"
        )
        print(
            f"Różnica CP-SAT - Greedy: "
            f"{difference:.6f}"
        )

    print()
    print("UŻYTE SATELITY")

    for satellite_id in schedule.satellites_used:
        count = sum(
            entry.satellite_id == satellite_id
            for entry in schedule.active_entries
        )

        print(
            f"  {satellite_id}: {count}"
        )

    print()
    print("ZAPISANO HARMONOGRAM")
    print(OUTPUT_PATH)

    print()
    print("RAPORTY CSV")

    for report_name, path in report_paths.items():
        print(
            f"  {report_name}: {path}"
        )


if __name__ == "__main__":
    main()