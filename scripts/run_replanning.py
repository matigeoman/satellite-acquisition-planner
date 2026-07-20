import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path


from _bootstrap import PROJECT_PATHS, PROJECT_ROOT


from app.analysis.schedule_report import export_schedule_analysis
from app.models.enums import PlanningAlgorithm
from app.io import load_schedule, save_schedule
from app.services.planning_service import PlanningOptions
from app.services.replanning_service import ReplanningService
from app.services.scenario_service import ScenarioService


DEFAULT_REPLAN_AT = "2026-07-15T06:00:00Z"


def parse_utc_datetime(value: str) -> datetime:
    normalized = value.strip().replace(
        "Z",
        "+00:00",
    )

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "Czas musi mieć format ISO 8601, np. 2026-07-15T06:00:00Z"
        ) from error

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise argparse.ArgumentTypeError("Czas musi zawierać strefę czasową")

    return parsed.astimezone(timezone.utc)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Dynamiczne przeplanowanie harmonogramu z operacyjnym oknem zamrożonym."
        )
    )

    parser.add_argument(
        "--scenario",
        default="EXAMPLE",
        choices=("EXAMPLE", "STRESS"),
        help="Identyfikator scenariusza.",
    )
    parser.add_argument(
        "--algorithm",
        default="CP_SAT",
        choices=("GREEDY", "CP_SAT"),
        help="Algorytm użyty do przeplanowania.",
    )
    parser.add_argument(
        "--replan-at",
        type=parse_utc_datetime,
        default=parse_utc_datetime(DEFAULT_REPLAN_AT),
        help=("Moment przeplanowania w UTC, np. 2026-07-15T06:00:00Z."),
    )
    parser.add_argument(
        "--freeze-hours",
        type=float,
        default=2.0,
        help="Długość okna zamrożonego w godzinach.",
    )
    parser.add_argument(
        "--previous-schedule",
        type=Path,
        default=None,
        help=(
            "Ścieżka do poprzedniego harmonogramu JSON. "
            "Domyślnie referencyjny CP-SAT wybranego scenariusza."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Opcjonalna ścieżka harmonogramu wynikowego.",
    )
    parser.add_argument(
        "--memory-reserve-ratio",
        type=float,
        default=0.0,
        help="Rezerwa pamięci satelity w zakresie [0, 1].",
    )
    parser.add_argument(
        "--cp-sat-time-limit",
        type=float,
        default=30.0,
        help="Limit czasu CP-SAT w sekundach.",
    )

    return parser


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()

    if args.freeze_hours <= 0.0:
        parser.error("--freeze-hours musi być większe od zera")

    algorithm = PlanningAlgorithm(args.algorithm)

    scenario = ScenarioService(project_root=PROJECT_ROOT).load(args.scenario)

    previous_schedule_path = args.previous_schedule
    if previous_schedule_path is None:
        previous_schedule_path = PROJECT_PATHS.reference_schedule(
            scenario_id=args.scenario,
            algorithm_value="CP_SAT",
        )
    elif not previous_schedule_path.is_absolute():
        previous_schedule_path = PROJECT_ROOT / previous_schedule_path

    previous_schedule = load_schedule(previous_schedule_path)

    options = PlanningOptions(
        algorithm=algorithm,
        memory_reserve_ratio=(args.memory_reserve_ratio),
        cp_sat_time_limit_s=(args.cp_sat_time_limit),
        cp_sat_num_search_workers=1,
        cp_sat_force_mandatory_requests=True,
    )

    result = ReplanningService().run(
        scenario=scenario,
        previous_schedule=previous_schedule,
        options=options,
        replan_at_utc=args.replan_at,
        freeze_duration=timedelta(hours=args.freeze_hours),
    )

    algorithm_slug = algorithm.value.lower()

    output_path = args.output

    if output_path is None:
        output_path = PROJECT_PATHS.generated_schedule(
            scenario_id=args.scenario,
            name=f"replanned_{algorithm_slug}",
        )
    elif not output_path.is_absolute():
        output_path = PROJECT_ROOT / output_path

    save_schedule(
        result.schedule,
        output_path,
    )

    report_paths = export_schedule_analysis(
        result.analysis,
        PROJECT_PATHS.reports,
        prefix=f"replanned_{algorithm_slug}",
    )

    print("DYNAMICZNE PRZEPLANOWANIE")
    print()
    print(f"Scenariusz: {scenario.scenario_id}")
    print(f"Algorytm: {algorithm.value}")
    print(f"Moment przeplanowania: {result.replan_at_utc.isoformat()}")
    print(f"Koniec okna zamrożonego: {result.frozen_until_utc.isoformat()}")
    print(f"Status solvera: {result.solver_status}")
    print(f"Status harmonogramu: {result.schedule.status.value}")
    print()
    print("ZACHOWANE AKWIZYCJE")
    print(f"  wykonane: {result.executed_count}")
    print(f"  zamrożone: {result.frozen_count}")
    print(f"  razem stałe: {result.fixed_count}")
    print()
    print("ZMIANY PO OKNIE ZAMROŻONYM")
    print(f"  bez zmian: {len(result.unchanged_replannable_opportunity_ids)}")
    print(f"  dodane: {len(result.added_opportunity_ids)}")
    print(f"  usunięte: {len(result.removed_opportunity_ids)}")
    print()
    print("WYNIK")
    print(f"  akwizycje: {result.schedule.total_acquisitions}")
    print(f"  zlecenia w harmonogramie: {len(result.schedule.scheduled_request_ids)}")
    print(f"  funkcja celu: {float(result.schedule.objective_value or 0.0):.6f}")
    print(f"  czas solvera: {float(result.schedule.solver_runtime_s or 0.0):.6f} s")
    print()
    print("ZAPISANO HARMONOGRAM")
    print(output_path)
    print()
    print("RAPORTY CSV")

    for report_name, path in report_paths.items():
        print(f"  {report_name}: {path}")


if __name__ == "__main__":
    main()
