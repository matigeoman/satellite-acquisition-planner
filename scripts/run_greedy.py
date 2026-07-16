from datetime import datetime, timezone
from pathlib import Path


from _bootstrap import PROJECT_PATHS, PROJECT_ROOT


from app.io import load_system_catalog
from app.io import load_opportunity_set
from app.planning.greedy import (
    GreedyPlannerConfig,
    build_greedy_schedule,
)
from app.io import load_request_set
from app.io import save_schedule


CATALOG_PATH = PROJECT_PATHS.scenario("EXAMPLE").catalog

REQUEST_SET_PATH = PROJECT_PATHS.scenario("EXAMPLE").requests

OPPORTUNITY_SET_PATH = PROJECT_PATHS.scenario("EXAMPLE").opportunities

OUTPUT_PATH = PROJECT_PATHS.reference_schedule(scenario_id="EXAMPLE", algorithm_value="GREEDY")


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

    config = GreedyPlannerConfig(
        memory_reserve_ratio=0.0,
        priority_weight=10.0,
        quality_weight=3.0,
        coverage_weight=2.0,
        mandatory_bonus=100.0,
    )

    schedule = build_greedy_schedule(
        catalog=catalog,
        request_set=request_set,
        opportunity_set=opportunity_set,
        config=config,
        schedule_id="SCHEDULE-GREEDY-001",
        name="Przykładowy dobowy harmonogram Greedy",
        created_at_utc=datetime(
            2026,
            7,
            14,
            22,
            0,
            0,
            tzinfo=timezone.utc,
        ),
    )

    save_schedule(
        schedule,
        OUTPUT_PATH,
    )

    mandatory_unassigned = sorted(
        request.request_id
        for request in request_set.mandatory_requests
        if request.request_id
        in schedule.unassigned_request_ids
    )

    print("GREEDY SCHEDULER")
    print()
    print(f"Status: {schedule.status.value}")
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
        f"Obowiązkowe nieprzypisane: "
        f"{len(mandatory_unassigned)}"
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
        f"Czas działania algorytmu: "
        f"{schedule.solver_runtime_s:.6f} s"
    )
    print()
    print("Użyte satelity:")
    for satellite_id in schedule.satellites_used:
        count = sum(
            entry.satellite_id == satellite_id
            for entry in schedule.active_entries
        )

        print(
            f"  {satellite_id}: {count}"
        )

    print()
    print("Zapisano harmonogram do:")
    print(OUTPUT_PATH)


if __name__ == "__main__":
    main()