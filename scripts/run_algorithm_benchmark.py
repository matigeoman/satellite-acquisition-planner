from __future__ import annotations

import argparse
from pathlib import Path

from _bootstrap import PROJECT_ROOT

from app.analysis.algorithm_benchmark import AlgorithmBenchmarkConfig
from app.services.benchmark_service import AlgorithmBenchmarkService
from app.services.scenario_service import ScenarioService
from app.ui.benchmark_view import build_benchmark_export_zip


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Benchmark skalowalności Greedy i CP-SAT."
    )
    parser.add_argument(
        "--request-counts",
        type=int,
        nargs="+",
        default=[20, 50, 100],
        help="Rozmiary scenariuszy, np. 20 50 100 200 500.",
    )
    parser.add_argument(
        "--repetitions",
        type=int,
        default=1,
        help="Liczba powtórzeń każdego rozmiaru.",
    )
    parser.add_argument(
        "--cp-sat-limits",
        type=float,
        nargs="+",
        default=[2.0],
        help="Limity czasu CP-SAT w sekundach.",
    )
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--base-seed", type=int, default=20260717)
    parser.add_argument(
        "--memory-reserve",
        type=float,
        default=0.15,
        help="Rezerwa pamięci w zakresie 0–1.",
    )
    parser.add_argument(
        "--disable-dynamic-constraints",
        action="store_true",
        help="Wyłącza dynamiczny model przeorientowania.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT
        / "data"
        / "generated"
        / "benchmark"
        / "algorithm_benchmark_results.zip",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = AlgorithmBenchmarkConfig(
        request_counts=tuple(args.request_counts),
        repetitions=args.repetitions,
        cp_sat_time_limits_s=tuple(args.cp_sat_limits),
        cp_sat_num_search_workers=args.workers,
        base_seed=args.base_seed,
        memory_reserve_ratio=args.memory_reserve,
        use_dynamic_transition_model=(not args.disable_dynamic_constraints),
    )
    scenario = ScenarioService(project_root=PROJECT_ROOT).load("STRESS")

    print("BENCHMARK GREEDY VS CP-SAT")
    print(f"Rozmiary: {config.request_counts}")
    print(f"Powtórzenia: {config.repetitions}")
    print(f"Limity CP-SAT: {config.cp_sat_time_limits_s}")
    print(f"Planowane przebiegi: {config.expected_run_count}")
    print(f"Minimalny budżet solvera: {config.estimated_cp_sat_budget_s:.1f} s")

    result = AlgorithmBenchmarkService().run(
        base_scenario=scenario,
        config=config,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(build_benchmark_export_zip(result))

    print()
    print(f"Poprawne przebiegi: {result.successful_run_count}")
    print(f"Nieudane przebiegi: {result.failed_run_count}")
    print(f"Średnia poprawa celu CP-SAT: {result.mean_objective_improvement_pct:+.2f}%")
    print(f"Czas całkowity: {result.wall_clock_runtime_s:.3f} s")
    print(f"Pakiet wyników: {args.output.resolve()}")


if __name__ == "__main__":
    main()
