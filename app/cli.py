from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from app.analysis import export_schedule_analysis
from app.config.paths import DEFAULT_PATHS, ProjectPaths
from app.io import save_schedule
from app.models.enums import PlanningAlgorithm
from app.services import PlanningOptions, PlanningService, ScenarioService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="satplan",
        description=(
            "Narzędzia wiersza poleceń projektu Satellite Acquisition Planner."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    check_parser = subparsers.add_parser(
        "check",
        help="Sprawdza strukturę danych i ładuje wszystkie scenariusze.",
    )
    check_parser.set_defaults(handler=_handle_check)

    paths_parser = subparsers.add_parser(
        "paths",
        help="Wyświetla najważniejsze katalogi projektu.",
    )
    paths_parser.set_defaults(handler=_handle_paths)

    plan_parser = subparsers.add_parser(
        "plan",
        help="Uruchamia Greedy albo CP-SAT dla wybranego scenariusza.",
    )
    plan_parser.add_argument(
        "--scenario",
        choices=("EXAMPLE", "STRESS"),
        default="EXAMPLE",
    )
    plan_parser.add_argument(
        "--algorithm",
        choices=("GREEDY", "CP_SAT"),
        default="CP_SAT",
    )
    plan_parser.add_argument(
        "--memory-reserve-ratio",
        type=float,
        default=0.15,
    )
    plan_parser.add_argument(
        "--cp-sat-time-limit",
        type=float,
        default=10.0,
    )
    plan_parser.add_argument(
        "--workers",
        type=int,
        default=1,
    )
    plan_parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Opcjonalna ścieżka pliku JSON z harmonogramem.",
    )
    plan_parser.add_argument(
        "--report-prefix",
        default=None,
        help="Prefiks raportów CSV. Domyślnie scenariusz i algorytm.",
    )
    plan_parser.set_defaults(handler=_handle_plan)

    return parser


def _handle_check(args: argparse.Namespace, paths: ProjectPaths) -> int:
    paths.ensure_output_directories()
    service = ScenarioService(project_root=paths.root)

    print("KONTROLA PROJEKTU")
    print(f"Katalog główny: {paths.root}")
    print()

    for scenario_id in service.scenario_ids:
        scenario = service.load(scenario_id)
        print(scenario_id)
        print(f"  satelity: {scenario.satellite_count}")
        print(f"  aktywne zlecenia: {scenario.active_request_count}")
        print(f"  okazje: {scenario.opportunity_count}")
        print(f"  wykonalne okazje: {scenario.feasible_opportunity_count}")

    print()
    print("Struktura i dane wejściowe są poprawne.")
    return 0


def _handle_paths(args: argparse.Namespace, paths: ProjectPaths) -> int:
    print("ŚCIEŻKI PROJEKTU")
    print(f"root: {paths.root}")
    print(f"scenarios: {paths.scenarios}")
    print(f"reference_schedules: {paths.reference_schedules}")
    print(f"generated_schedules: {paths.generated_schedules}")
    print(f"generated_reports: {paths.generated_reports}")
    print(f"generated_benchmarks: {paths.generated_benchmarks}")
    print(f"stk_imports: {paths.stk_imports}")
    return 0


def _handle_plan(args: argparse.Namespace, paths: ProjectPaths) -> int:
    algorithm = PlanningAlgorithm(args.algorithm)
    scenario = ScenarioService(project_root=paths.root).load(args.scenario)

    options = PlanningOptions(
        algorithm=algorithm,
        memory_reserve_ratio=args.memory_reserve_ratio,
        cp_sat_time_limit_s=args.cp_sat_time_limit,
        cp_sat_num_search_workers=args.workers,
    )
    result = PlanningService().run(
        scenario=scenario,
        options=options,
    )

    output_path = args.output
    if output_path is None:
        output_path = paths.generated_schedule(
            scenario_id=scenario.scenario_id,
            name=algorithm.value.lower(),
        )
    elif not output_path.is_absolute():
        output_path = paths.root / output_path

    save_schedule(result.schedule, output_path)

    prefix = args.report_prefix or (
        f"{scenario.scenario_id.lower()}_{algorithm.value.lower()}"
    )
    report_paths = export_schedule_analysis(
        result.analysis,
        paths.generated_reports,
        prefix=prefix,
    )

    print("PLANOWANIE")
    print(f"Scenariusz: {scenario.scenario_id}")
    print(f"Algorytm: {algorithm.value}")
    print(f"Status solvera: {result.solver_status}")
    print(f"Status harmonogramu: {result.schedule.status.value}")
    print(f"Akwizycje: {result.total_acquisitions}")
    print(
        "Zrealizowane zlecenia: "
        f"{result.fully_satisfied_requests}/"
        f"{result.analysis.total_active_requests}"
    )
    print(f"Funkcja celu: {result.objective_value:.6f}")
    print(f"Czas: {result.wall_clock_runtime_s:.6f} s")
    print(f"Harmonogram: {output_path.resolve()}")
    print("Raporty:")
    for name, path in report_paths.items():
        print(f"  {name}: {path.resolve()}")

    return 0


def main(
    argv: Sequence[str] | None = None,
    *,
    paths: ProjectPaths = DEFAULT_PATHS,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.handler(args, paths))


if __name__ == "__main__":
    raise SystemExit(main())
