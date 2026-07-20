from __future__ import annotations

import argparse
import filecmp
import shutil
from pathlib import Path

from _bootstrap import PROJECT_PATHS


LEGACY_FILE_MAP = {
    "example_system.json": PROJECT_PATHS.scenario("EXAMPLE").catalog,
    "example_requests.json": PROJECT_PATHS.scenario("EXAMPLE").requests,
    "example_opportunities.json": PROJECT_PATHS.scenario("EXAMPLE").opportunities,
    "stress_system.json": PROJECT_PATHS.scenario("STRESS").catalog,
    "stress_requests.json": PROJECT_PATHS.scenario("STRESS").requests,
    "stress_opportunities.json": PROJECT_PATHS.scenario("STRESS").opportunities,
    "example_schedule_greedy.json": PROJECT_PATHS.reference_schedule(
        scenario_id="EXAMPLE", algorithm_value="GREEDY"
    ),
    "example_schedule_cp_sat.json": PROJECT_PATHS.reference_schedule(
        scenario_id="EXAMPLE", algorithm_value="CP_SAT"
    ),
    "stress_schedule_greedy.json": PROJECT_PATHS.reference_schedule(
        scenario_id="STRESS", algorithm_value="GREEDY"
    ),
    "stress_schedule_cp_sat.json": PROJECT_PATHS.reference_schedule(
        scenario_id="STRESS", algorithm_value="CP_SAT"
    ),
    "example_schedule_replanned_cp_sat.json": PROJECT_PATHS.generated_schedule(
        scenario_id="EXAMPLE", name="replanned_cp_sat"
    ),
    "example_schedule_disrupted_cp_sat.json": PROJECT_PATHS.generated_schedule(
        scenario_id="EXAMPLE", name="disrupted_cp_sat"
    ),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Przenosi starszy płaski układ katalogu data do uporządkowanej "
            "struktury scenarios, reference_schedules i generated."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Wykonuje kopiowanie. Bez tej flagi działa jako podgląd.",
    )
    parser.add_argument(
        "--remove-legacy",
        action="store_true",
        help="Po weryfikacji usuwa stare pliki i katalogi.",
    )
    return parser


def _copy_file(source: Path, destination: Path, *, apply: bool) -> None:
    print(
        f"FILE  {source.relative_to(PROJECT_PATHS.root)} -> "
        f"{destination.relative_to(PROJECT_PATHS.root)}"
    )
    if not apply or not source.is_file():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _copy_directory(source: Path, destination: Path, *, apply: bool) -> None:
    print(
        f"DIR   {source.relative_to(PROJECT_PATHS.root)} -> "
        f"{destination.relative_to(PROJECT_PATHS.root)}"
    )
    if not apply or not source.is_dir():
        return
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination, dirs_exist_ok=True)


def _verified_copy(source: Path, destination: Path) -> bool:
    return (
        source.is_file()
        and destination.is_file()
        and filecmp.cmp(source, destination, shallow=False)
    )


def main() -> int:
    args = build_parser().parse_args()
    data = PROJECT_PATHS.data
    PROJECT_PATHS.ensure_output_directories()

    print("MIGRACJA UKŁADU DANYCH")
    print(f"Tryb: {'APPLY' if args.apply else 'DRY-RUN'}")
    print()

    for legacy_name, destination in LEGACY_FILE_MAP.items():
        _copy_file(data / legacy_name, destination, apply=args.apply)

    _copy_directory(
        data / "reports",
        PROJECT_PATHS.generated_reports,
        apply=args.apply,
    )
    _copy_directory(
        data / "benchmarks",
        PROJECT_PATHS.generated_benchmarks,
        apply=args.apply,
    )

    if args.remove_legacy:
        if not args.apply:
            raise SystemExit("--remove-legacy wymaga jednocześnie --apply")

        print()
        print("USUWANIE STAREGO UKŁADU")
        for legacy_name, destination in LEGACY_FILE_MAP.items():
            source = data / legacy_name
            if not source.exists():
                continue
            if not _verified_copy(source, destination):
                raise RuntimeError(f"Nie można potwierdzić kopii pliku {source}")
            source.unlink()
            print(f"REMOVE {source.relative_to(PROJECT_PATHS.root)}")

        for legacy_directory in (data / "reports", data / "benchmarks"):
            if legacy_directory.exists():
                shutil.rmtree(legacy_directory)
                print(f"REMOVE {legacy_directory.relative_to(PROJECT_PATHS.root)}")

    print()
    print("Migracja zakończona.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
