from __future__ import annotations

import argparse
from pathlib import Path


from _bootstrap import PROJECT_PATHS, PROJECT_ROOT


from app.analysis.experimental_validation import (
    ExperimentalValidationConfig,
    ExperimentalValidationService,
    export_experimental_validation,
)
from app.services.scenario_service import ScenarioService


DEFAULT_OUTPUT_DIRECTORY = PROJECT_PATHS.experimental_validation_reports


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Wielokrotna walidacja Greedy i CP-SAT "
            "na wariantach scenariusza stresowego."
        )
    )
    parser.add_argument(
        "--repetitions",
        type=int,
        default=5,
        help="Liczba powtórzeń każdego profilu (domyślnie 5).",
    )
    parser.add_argument(
        "--base-seed",
        type=int,
        default=20260720,
        help="Pierwsze ziarno generatora wariantów.",
    )
    parser.add_argument(
        "--cp-sat-time-limit",
        type=float,
        default=2.0,
        help="Limit czasu CP-SAT dla pojedynczego przebiegu [s].",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Liczba wątków CP-SAT; 1 zapewnia powtarzalność.",
    )
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=DEFAULT_OUTPUT_DIRECTORY,
        help="Katalog raportów CSV, JSON i PNG.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()

    scenario = ScenarioService(
        project_root=PROJECT_ROOT
    ).load("STRESS")

    config = ExperimentalValidationConfig(
        repetitions=args.repetitions,
        base_seed=args.base_seed,
        cp_sat_time_limit_s=args.cp_sat_time_limit,
        cp_sat_num_search_workers=args.workers,
    )

    print("WALIDACJA EKSPERYMENTALNA GREEDY I CP-SAT")
    print()
    print(f"Scenariusz bazowy: {scenario.scenario_id}")
    print(f"Profile: {len(config.profiles)}")
    print(f"Powtórzenia na profil: {config.repetitions}")
    print(
        "Łączna liczba uruchomień planerów: "
        f"{len(config.profiles) * config.repetitions * 2}"
    )
    print(
        "Limit CP-SAT na przebieg: "
        f"{config.cp_sat_time_limit_s:.3f} s"
    )
    print()

    result = ExperimentalValidationService().run(
        base_scenario=scenario,
        config=config,
    )

    paths = export_experimental_validation(
        result,
        args.output_directory,
    )

    summary_by_key = {
        (record.profile_id, record.algorithm): record
        for record in result.summary_records
    }

    print("WYNIKI ŚREDNIE")

    for profile in config.profiles:
        greedy = summary_by_key[
            (profile.profile_id, "GREEDY")
        ]
        cp_sat = summary_by_key[
            (profile.profile_id, "CP_SAT")
        ]
        pair_values = [
            record
            for record in result.pair_records
            if record.profile_id == profile.profile_id
        ]
        improvement = sum(
            record.objective_improvement_pct
            for record in pair_values
        ) / len(pair_values)

        print()
        print(profile.profile_id)
        print(
            "  funkcja celu Greedy: "
            f"{greedy.objective_mean:.3f}"
        )
        print(
            "  funkcja celu CP-SAT: "
            f"{cp_sat.objective_mean:.3f}"
        )
        print(
            "  średnia poprawa CP-SAT: "
            f"{improvement:+.2f}%"
        )
        print(
            "  zrealizowane zlecenia Greedy: "
            f"{greedy.fully_satisfied_requests_mean:.2f}"
        )
        print(
            "  zrealizowane zlecenia CP-SAT: "
            f"{cp_sat.fully_satisfied_requests_mean:.2f}"
        )
        print(
            "  czas Greedy: "
            f"{greedy.runtime_mean_s:.6f} s"
        )
        print(
            "  czas CP-SAT: "
            f"{cp_sat.runtime_mean_s:.6f} s"
        )

    print()
    print("PODSUMOWANIE")
    print(
        "  CP-SAT lepszy pod względem funkcji celu: "
        f"{result.cp_sat_better_objective_count}/"
        f"{len(result.pair_records)}"
    )
    print(
        "  CP-SAT nie gorszy pod względem funkcji celu: "
        f"{result.cp_sat_not_worse_objective_count}/"
        f"{len(result.pair_records)}"
    )
    print(
        "  średnia poprawa funkcji celu: "
        f"{result.mean_objective_improvement_pct:+.2f}%"
    )
    print(
        "  całkowity czas eksperymentu: "
        f"{result.wall_clock_runtime_s:.3f} s"
    )

    print()
    print("ZAPISANE RAPORTY")
    for label, path in paths.items():
        print(f"  {label}: {path.resolve()}")


if __name__ == "__main__":
    main()
