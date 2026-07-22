from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from app.analysis import export_schedule_analysis
from app.config.paths import DEFAULT_PATHS, ProjectPaths
from app.io import save_schedule
from app.models.enums import PlanningAlgorithm
from app.quality import (
    run_project_audit,
    run_release_check,
    run_runtime_healthcheck,
)
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

    audit_parser = subparsers.add_parser(
        "audit",
        help="Wykonuje audyt repozytorium, środowiska i danych.",
    )
    audit_parser.add_argument(
        "--strict",
        action="store_true",
        help="Traktuje ostrzeżenia jako błąd polecenia.",
    )
    audit_parser.add_argument(
        "--json",
        type=Path,
        default=None,
        dest="json_output",
        help="Opcjonalny plik JSON z pełnym wynikiem audytu.",
    )
    audit_parser.set_defaults(handler=_handle_audit)

    health_parser = subparsers.add_parser(
        "health",
        help=(
            "Sprawdza środowisko uruchomieniowe, solver, dane, zapis "
            "i opcjonalnie endpoint Streamlit."
        ),
    )
    health_parser.add_argument(
        "--url",
        default="http://127.0.0.1:8501/_stcore/health",
        help="Endpoint zdrowia Streamlit sprawdzany w trybie HTTP.",
    )
    health_parser.add_argument(
        "--skip-http",
        action="store_true",
        help="Pomija kontrolę endpointu HTTP, np. podczas budowy obrazu.",
    )
    health_parser.add_argument(
        "--timeout",
        type=float,
        default=3.0,
        help="Limit czasu żądania HTTP w sekundach.",
    )
    health_parser.add_argument(
        "--json",
        type=Path,
        default=None,
        dest="json_output",
        help="Opcjonalny plik JSON z wynikiem kontroli.",
    )
    health_parser.add_argument(
        "--quiet",
        action="store_true",
        help="Nie wypisuje raportu tekstowego; zachowuje kod wyjścia.",
    )
    health_parser.set_defaults(handler=_handle_health)

    release_parser = subparsers.add_parser(
        "release-check",
        help=(
            "Uruchamia końcowy test E2E: audyt, planowanie, archiwum "
            "projektu i generator raportu."
        ),
    )
    release_parser.add_argument(
        "--algorithm",
        choices=("GREEDY", "CP_SAT", "HYBRID", "BOTH", "ALL"),
        default="BOTH",
    )
    release_parser.add_argument(
        "--cp-sat-time-limit",
        type=float,
        default=2.0,
    )
    release_parser.add_argument(
        "--output-directory",
        type=Path,
        default=None,
        help="Opcjonalny katalog na archiwum projektu i pakiet raportowy.",
    )
    release_parser.add_argument(
        "--json",
        type=Path,
        default=None,
        dest="json_output",
        help="Opcjonalny plik JSON z wynikiem testu wydania.",
    )
    release_parser.set_defaults(handler=_handle_release_check)

    plan_parser = subparsers.add_parser(
        "plan",
        help="Uruchamia Greedy, CP-SAT albo Hybrid dla wybranego scenariusza.",
    )
    plan_parser.add_argument(
        "--scenario",
        choices=("EXAMPLE", "STRESS", "POLAND_DEMO"),
        default="EXAMPLE",
    )
    plan_parser.add_argument(
        "--algorithm",
        choices=("GREEDY", "CP_SAT", "HYBRID"),
        default="HYBRID",
    )
    plan_parser.add_argument(
        "--memory-reserve-ratio",
        type=float,
        default=0.15,
    )
    plan_parser.add_argument(
        "--enable-downlink",
        action="store_true",
        help="Włącza dynamiczną pamięć i planowanie okien transmisji.",
    )
    plan_parser.add_argument(
        "--require-full-downlink",
        action="store_true",
        help="Wymaga opróżnienia pamięci do końca horyzontu.",
    )
    plan_parser.add_argument(
        "--allow-simultaneous-imaging-downlink",
        action="store_true",
        help="Pozwala na jednoczesne obrazowanie i transmisję.",
    )
    plan_parser.add_argument(
        "--downlink-capacity-reserve-ratio",
        type=float,
        default=0.10,
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
        print(f"  okna downlinku: {scenario.downlink_opportunity_count}")

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


def _handle_audit(args: argparse.Namespace, paths: ProjectPaths) -> int:
    report = run_project_audit(paths)

    print("AUDYT PROJEKTU")
    print(f"Wersja aplikacji: {report.application_version}")
    print(f"Python: {report.python_version}")
    print(f"Katalog główny: {report.project_root}")
    print()

    for check in report.checks:
        print(f"[{check.status.value}] {check.name}: {check.message}")
        for detail in check.details:
            print(f"  - {detail}")

    print()
    print(
        "Podsumowanie: "
        f"{len(report.failures)} błędów, "
        f"{len(report.warnings)} ostrzeżeń."
    )

    if args.json_output is not None:
        output_path = args.json_output
        if not output_path.is_absolute():
            output_path = paths.root / output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"Raport JSON: {output_path.resolve()}")

    if report.failures:
        return 1
    if args.strict and report.warnings:
        return 1
    return 0


def _handle_health(args: argparse.Namespace, paths: ProjectPaths) -> int:
    if args.timeout <= 0:
        raise ValueError("--timeout musi być dodatni")

    report = run_runtime_healthcheck(
        paths,
        streamlit_url=None if args.skip_http else args.url,
        timeout_s=args.timeout,
    )

    if not args.quiet:
        print("KONTROLA ŚRODOWISKA URUCHOMIENIOWEGO")
        print(f"Wersja aplikacji: {report.application_version}")
        print(f"Python: {report.python_version}")
        print()
        for check in report.checks:
            marker = "PASS" if check.healthy else "FAIL"
            print(f"[{marker}] {check.name}: {check.message}")
        print()
        print("Stan: HEALTHY" if report.healthy else "Stan: UNHEALTHY")

    if args.json_output is not None:
        output_path = args.json_output
        if not output_path.is_absolute():
            output_path = paths.root / output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report.to_json(), encoding="utf-8")
        if not args.quiet:
            print(f"Raport JSON: {output_path.resolve()}")

    return 0 if report.healthy else 1


def _handle_release_check(args: argparse.Namespace, paths: ProjectPaths) -> int:
    if args.cp_sat_time_limit <= 0:
        raise ValueError("--cp-sat-time-limit musi być dodatni")

    algorithms = {
        "GREEDY": (PlanningAlgorithm.GREEDY,),
        "CP_SAT": (PlanningAlgorithm.CP_SAT,),
        "HYBRID": (PlanningAlgorithm.HYBRID,),
        "BOTH": (PlanningAlgorithm.GREEDY, PlanningAlgorithm.CP_SAT),
        "ALL": (
            PlanningAlgorithm.GREEDY,
            PlanningAlgorithm.CP_SAT,
            PlanningAlgorithm.HYBRID,
        ),
    }[args.algorithm]
    report = run_release_check(
        paths,
        algorithms=algorithms,
        cp_sat_time_limit_s=args.cp_sat_time_limit,
        output_directory=args.output_directory,
    )

    print("KONTROLA WYDANIA")
    print(f"Wersja aplikacji: {report.application_version}")
    print(f"Katalog główny: {report.project_root}")
    print()
    for step in report.steps:
        marker = "PASS" if step.passed else "FAIL"
        print(f"[{marker}] {step.name}: {step.message}")
        for detail in step.details:
            print(f"  - {detail}")
    for artifact in report.artifact_paths:
        print(f"Artefakt: {artifact.resolve()}")
    print()
    print("Stan: RELEASE READY" if report.passed else "Stan: RELEASE BLOCKED")

    if args.json_output is not None:
        output_path = args.json_output
        if not output_path.is_absolute():
            output_path = paths.root / output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report.to_json(), encoding="utf-8")
        print(f"Raport JSON: {output_path.resolve()}")

    return 0 if report.passed else 1


def _handle_plan(args: argparse.Namespace, paths: ProjectPaths) -> int:
    algorithm = PlanningAlgorithm(args.algorithm)
    scenario = ScenarioService(project_root=paths.root).load(args.scenario)

    options = PlanningOptions(
        algorithm=algorithm,
        memory_reserve_ratio=args.memory_reserve_ratio,
        enable_downlink_planning=args.enable_downlink,
        require_full_downlink=args.require_full_downlink,
        allow_simultaneous_imaging_downlink=(
            args.allow_simultaneous_imaging_downlink
        ),
        downlink_capacity_reserve_ratio=(
            args.downlink_capacity_reserve_ratio
        ),
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
    print(f"Okna downlinku: {result.schedule.selected_downlink_windows}")
    print(
        "Wysłane dane: "
        f"{result.schedule.total_downlinked_data_mb:.3f} MB"
    )
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
