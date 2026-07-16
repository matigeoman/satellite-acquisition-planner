import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path


from _bootstrap import PROJECT_PATHS, PROJECT_ROOT


from app.analysis.disruption_report import export_disruption_report
from app.analysis.schedule_report import export_schedule_analysis
from app.models.enums import PlanningAlgorithm
from app.io import load_schedule, save_schedule
from app.scenarios.disruption import build_example_disruption_plan
from app.services.disruption_service import DisruptionReplanningService
from app.services.planning_service import PlanningOptions
from app.services.scenario_service import ScenarioService


DEFAULT_REPLAN_AT = "2026-07-15T06:00:00Z"


def parse_utc_datetime(value: str) -> datetime:
    normalized = value.strip().replace("Z", "+00:00")

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "Czas musi mieć format ISO 8601, np. "
            "2026-07-15T06:00:00Z"
        ) from error

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise argparse.ArgumentTypeError(
            "Czas musi zawierać strefę czasową"
        )

    return parsed.astimezone(timezone.utc)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Dynamiczne przeplanowanie po awarii satelity, zmianie "
            "pogody i dodaniu pilnego zlecenia."
        )
    )
    parser.add_argument(
        "--algorithm",
        default="CP_SAT",
        choices=("GREEDY", "CP_SAT"),
    )
    parser.add_argument(
        "--replan-at",
        type=parse_utc_datetime,
        default=parse_utc_datetime(DEFAULT_REPLAN_AT),
    )
    parser.add_argument(
        "--freeze-hours",
        type=float,
        default=2.0,
    )
    parser.add_argument(
        "--previous-schedule",
        type=Path,
        default=(
            PROJECT_PATHS.reference_schedule(
                scenario_id="EXAMPLE",
                algorithm_value="CP_SAT",
            )
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--cp-sat-time-limit",
        type=float,
        default=30.0,
    )
    return parser


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()

    if args.freeze_hours <= 0.0:
        parser.error("--freeze-hours musi być większe od zera")

    algorithm = PlanningAlgorithm(args.algorithm)
    freeze_duration = timedelta(hours=args.freeze_hours)

    scenario = ScenarioService(project_root=PROJECT_ROOT).load("EXAMPLE")

    previous_schedule_path = args.previous_schedule

    if not previous_schedule_path.is_absolute():
        previous_schedule_path = PROJECT_ROOT / previous_schedule_path

    previous_schedule = load_schedule(previous_schedule_path)

    plan = build_example_disruption_plan(
        scenario=scenario,
        previous_schedule=previous_schedule,
        replan_at_utc=args.replan_at,
        freeze_duration=freeze_duration,
    )

    result = DisruptionReplanningService().run(
        scenario=scenario,
        previous_schedule=previous_schedule,
        plan=plan,
        options=PlanningOptions(
            algorithm=algorithm,
            memory_reserve_ratio=0.0,
            cp_sat_time_limit_s=args.cp_sat_time_limit,
            cp_sat_num_search_workers=1,
            cp_sat_force_mandatory_requests=True,
        ),
        replan_at_utc=args.replan_at,
        freeze_duration=freeze_duration,
    )

    algorithm_slug = algorithm.value.lower()
    output_path = args.output

    if output_path is None:
        output_path = (
            PROJECT_PATHS.generated_schedule(
                scenario_id="EXAMPLE",
                name=f"disrupted_{algorithm_slug}",
            )
        )
    elif not output_path.is_absolute():
        output_path = PROJECT_ROOT / output_path

    save_schedule(result.schedule, output_path)

    report_directory = PROJECT_PATHS.reports
    schedule_report_paths = export_schedule_analysis(
        result.analysis,
        report_directory,
        prefix=f"disrupted_{algorithm_slug}",
    )
    disruption_report_paths = export_disruption_report(
        result,
        report_directory,
        prefix=f"disruption_{algorithm_slug}",
    )

    application = result.application_result
    outage = application.plan.satellite_outages[0]
    weather = application.plan.cloud_cover_updates[0]
    urgent = application.plan.urgent_requests[0]

    print("PRZEPLANOWANIE PO ZAKŁÓCENIU")
    print()
    print(f"Algorytm: {algorithm.value}")
    print(f"Status solvera: {result.solver_status}")
    print(f"Status harmonogramu: {result.schedule.status.value}")
    print()
    print("ZDARZENIA")
    print(
        f"  awaria: {outage.satellite_id} od "
        f"{outage.effective_from_utc.isoformat()}"
    )
    print(
        "  unieważnione przez awarię: "
        f"{len(application.outage_invalidated_opportunity_ids)}"
    )
    print(
        f"  pogoda: {weather.opportunity_id}, "
        f"zachmurzenie {weather.cloud_cover:.0%}"
    )
    print(
        "  unieważnione przez pogodę: "
        f"{len(application.weather_invalidated_opportunity_ids)}"
    )
    print(
        "  pilne zlecenie: "
        f"{urgent.request.request_id}"
    )
    print()
    print("ZMIANY HARMONOGRAMU PO OKNIE ZAMROŻONYM")
    print(f"  bez zmian: {len(result.unchanged_opportunity_ids)}")
    print(f"  dodane: {len(result.added_opportunity_ids)}")
    print(f"  usunięte: {len(result.removed_opportunity_ids)}")
    print(
        "  wcześniej wybrane okazje unieważnione przez zdarzenia: "
        f"{len(result.invalidated_previous_selection_ids)}"
    )
    print()
    print("WYNIK")
    print(
        "  zrealizowane zlecenia: "
        f"{result.analysis.fully_satisfied_requests}/"
        f"{result.analysis.total_active_requests}"
    )
    print(
        "  obowiązkowe: "
        f"{result.analysis.mandatory_satisfied_requests}/"
        f"{result.analysis.mandatory_requests}"
    )
    print(f"  poprzednia funkcja celu: {result.previous_objective_value:.6f}")
    print(f"  nowa funkcja celu: {result.new_objective_value:.6f}")
    print(f"  zmiana funkcji celu: {result.objective_delta:+.6f}")
    print()
    print("ZAPISANO HARMONOGRAM")
    print(output_path)
    print()
    print("RAPORTY HARMONOGRAMU")

    for name, path in schedule_report_paths.items():
        print(f"  {name}: {path}")

    print()
    print("RAPORTY ZAKŁÓCENIA")

    for name, path in disruption_report_paths.items():
        print(f"  {name}: {path}")


if __name__ == "__main__":
    main()
