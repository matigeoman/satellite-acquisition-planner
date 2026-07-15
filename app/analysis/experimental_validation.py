from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, stdev
from time import perf_counter

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from app.models.enums import PlanningAlgorithm
from app.scenarios.experiment import (
    DEFAULT_EXPERIMENT_PROFILES,
    ExperimentProfile,
    ExperimentScenarioVariant,
    build_experiment_variant,
)
from app.services.comparison_service import (
    PlanningComparisonResult,
    PlanningComparisonService,
)
from app.services.planning_service import PlanningOptions
from app.services.scenario_service import LoadedScenario


RUN_FIELDNAMES = [
    "profile_id",
    "profile_name",
    "repetition",
    "random_seed",
    "resource_ratio",
    "opportunity_dropout_ratio",
    "request_count",
    "mandatory_request_count",
    "source_feasible_opportunity_count",
    "feasible_opportunity_count",
    "dropped_opportunity_count",
    "algorithm",
    "solver_status",
    "schedule_status",
    "objective_value",
    "fully_satisfied_requests",
    "partially_satisfied_requests",
    "unassigned_requests",
    "mandatory_satisfied_requests",
    "satisfaction_ratio",
    "mandatory_satisfaction_ratio",
    "total_acquisitions",
    "average_selected_quality",
    "average_selected_coverage",
    "runtime_s",
]

PAIR_FIELDNAMES = [
    "profile_id",
    "repetition",
    "random_seed",
    "resource_ratio",
    "opportunity_dropout_ratio",
    "dropped_opportunity_count",
    "greedy_objective_value",
    "cp_sat_objective_value",
    "objective_difference",
    "objective_improvement_pct",
    "greedy_fully_satisfied_requests",
    "cp_sat_fully_satisfied_requests",
    "fully_satisfied_difference",
    "greedy_mandatory_satisfied_requests",
    "cp_sat_mandatory_satisfied_requests",
    "mandatory_satisfied_difference",
    "greedy_runtime_s",
    "cp_sat_runtime_s",
    "runtime_ratio",
    "cp_sat_solver_status",
]

SUMMARY_FIELDNAMES = [
    "profile_id",
    "profile_name",
    "algorithm",
    "run_count",
    "objective_mean",
    "objective_std",
    "objective_min",
    "objective_max",
    "satisfaction_ratio_mean",
    "satisfaction_ratio_std",
    "mandatory_satisfaction_ratio_mean",
    "fully_satisfied_requests_mean",
    "unassigned_requests_mean",
    "runtime_mean_s",
    "runtime_std_s",
]


@dataclass(frozen=True)
class ExperimentalValidationConfig:
    """Konfiguracja serii porównań Greedy i CP-SAT."""

    profiles: tuple[ExperimentProfile, ...] = (
        DEFAULT_EXPERIMENT_PROFILES
    )
    repetitions: int = 5
    base_seed: int = 20260720

    memory_reserve_ratio: float = 0.15
    cp_sat_time_limit_s: float = 2.0
    cp_sat_num_search_workers: int = 1

    def __post_init__(self) -> None:
        if not self.profiles:
            raise ValueError(
                "profiles nie może być puste"
            )

        profile_ids = [
            profile.profile_id
            for profile in self.profiles
        ]
        if len(profile_ids) != len(set(profile_ids)):
            raise ValueError(
                "profiles zawiera powtórzone profile_id"
            )

        if self.repetitions <= 0:
            raise ValueError(
                "repetitions musi być większe od zera"
            )

        if self.base_seed < 0:
            raise ValueError(
                "base_seed nie może być ujemny"
            )

        if not 0.0 <= self.memory_reserve_ratio <= 1.0:
            raise ValueError(
                "memory_reserve_ratio musi należeć "
                "do zakresu [0, 1]"
            )

        if self.cp_sat_time_limit_s <= 0.0:
            raise ValueError(
                "cp_sat_time_limit_s musi być większe od zera"
            )

        if self.cp_sat_num_search_workers <= 0:
            raise ValueError(
                "cp_sat_num_search_workers musi być większe od zera"
            )


@dataclass(frozen=True)
class ExperimentRunRecord:
    profile_id: str
    profile_name: str
    repetition: int
    random_seed: int
    resource_ratio: float
    opportunity_dropout_ratio: float
    request_count: int
    mandatory_request_count: int
    source_feasible_opportunity_count: int
    feasible_opportunity_count: int
    dropped_opportunity_count: int
    algorithm: str
    solver_status: str
    schedule_status: str
    objective_value: float
    fully_satisfied_requests: int
    partially_satisfied_requests: int
    unassigned_requests: int
    mandatory_satisfied_requests: int
    satisfaction_ratio: float
    mandatory_satisfaction_ratio: float
    total_acquisitions: int
    average_selected_quality: float
    average_selected_coverage: float
    runtime_s: float


@dataclass(frozen=True)
class ExperimentPairRecord:
    profile_id: str
    repetition: int
    random_seed: int
    resource_ratio: float
    opportunity_dropout_ratio: float
    dropped_opportunity_count: int
    greedy_objective_value: float
    cp_sat_objective_value: float
    objective_difference: float
    objective_improvement_pct: float
    greedy_fully_satisfied_requests: int
    cp_sat_fully_satisfied_requests: int
    fully_satisfied_difference: int
    greedy_mandatory_satisfied_requests: int
    cp_sat_mandatory_satisfied_requests: int
    mandatory_satisfied_difference: int
    greedy_runtime_s: float
    cp_sat_runtime_s: float
    runtime_ratio: float | None
    cp_sat_solver_status: str


@dataclass(frozen=True)
class ExperimentSummaryRecord:
    profile_id: str
    profile_name: str
    algorithm: str
    run_count: int
    objective_mean: float
    objective_std: float
    objective_min: float
    objective_max: float
    satisfaction_ratio_mean: float
    satisfaction_ratio_std: float
    mandatory_satisfaction_ratio_mean: float
    fully_satisfied_requests_mean: float
    unassigned_requests_mean: float
    runtime_mean_s: float
    runtime_std_s: float


@dataclass(frozen=True)
class ExperimentalValidationResult:
    """Kompletny wynik eksperymentu wielokrotnego."""

    base_scenario_id: str
    config: ExperimentalValidationConfig
    run_records: tuple[ExperimentRunRecord, ...]
    pair_records: tuple[ExperimentPairRecord, ...]
    summary_records: tuple[ExperimentSummaryRecord, ...]
    started_at_utc: datetime
    completed_at_utc: datetime
    wall_clock_runtime_s: float

    def __post_init__(self) -> None:
        expected_pair_count = (
            len(self.config.profiles)
            * self.config.repetitions
        )
        expected_run_count = expected_pair_count * 2

        if len(self.pair_records) != expected_pair_count:
            raise ValueError(
                "Niepoprawna liczba rekordów par"
            )

        if len(self.run_records) != expected_run_count:
            raise ValueError(
                "Niepoprawna liczba rekordów uruchomień"
            )

        if self.wall_clock_runtime_s < 0.0:
            raise ValueError(
                "wall_clock_runtime_s nie może być ujemny"
            )

    @property
    def cp_sat_better_objective_count(self) -> int:
        return sum(
            record.objective_difference > 1e-9
            for record in self.pair_records
        )

    @property
    def cp_sat_not_worse_objective_count(self) -> int:
        return sum(
            record.objective_difference >= -1e-9
            for record in self.pair_records
        )

    @property
    def mean_objective_improvement_pct(self) -> float:
        return round(
            mean(
                record.objective_improvement_pct
                for record in self.pair_records
            ),
            6,
        )


class ExperimentalValidationService:
    """Uruchamia serię powtarzalnych eksperymentów porównawczych."""

    def __init__(
        self,
        *,
        comparison_service: PlanningComparisonService | None = None,
    ) -> None:
        self.comparison_service = (
            comparison_service
            if comparison_service is not None
            else PlanningComparisonService()
        )

    def run(
        self,
        *,
        base_scenario: LoadedScenario,
        config: ExperimentalValidationConfig,
    ) -> ExperimentalValidationResult:
        started_at = datetime.now(timezone.utc)
        timer_start = perf_counter()

        run_records: list[ExperimentRunRecord] = []
        pair_records: list[ExperimentPairRecord] = []

        for profile_index, profile in enumerate(
            config.profiles
        ):
            for repetition in range(1, config.repetitions + 1):
                random_seed = (
                    config.base_seed
                    + profile_index * 10_000
                    + repetition - 1
                )

                variant = build_experiment_variant(
                    base_scenario=base_scenario,
                    profile=profile,
                    random_seed=random_seed,
                )

                comparison = self.comparison_service.run(
                    scenario=variant.scenario,
                    options=PlanningOptions(
                        algorithm=PlanningAlgorithm.CP_SAT,
                        memory_reserve_ratio=(
                            config.memory_reserve_ratio
                        ),
                        cp_sat_time_limit_s=(
                            config.cp_sat_time_limit_s
                        ),
                        cp_sat_num_search_workers=(
                            config.cp_sat_num_search_workers
                        ),
                        cp_sat_random_seed=random_seed,
                        cp_sat_force_mandatory_requests=False,
                    ),
                    created_at_utc=started_at,
                )

                greedy_record = _build_run_record(
                    variant=variant,
                    repetition=repetition,
                    algorithm="GREEDY",
                    comparison=comparison,
                )
                cp_sat_record = _build_run_record(
                    variant=variant,
                    repetition=repetition,
                    algorithm="CP_SAT",
                    comparison=comparison,
                )

                run_records.extend(
                    [greedy_record, cp_sat_record]
                )
                pair_records.append(
                    _build_pair_record(
                        variant=variant,
                        repetition=repetition,
                        comparison=comparison,
                    )
                )

        summary_records = _build_summary_records(
            run_records
        )

        completed_at = datetime.now(timezone.utc)
        wall_clock_runtime_s = round(
            perf_counter() - timer_start,
            6,
        )

        return ExperimentalValidationResult(
            base_scenario_id=base_scenario.scenario_id,
            config=config,
            run_records=tuple(run_records),
            pair_records=tuple(pair_records),
            summary_records=tuple(summary_records),
            started_at_utc=started_at,
            completed_at_utc=completed_at,
            wall_clock_runtime_s=wall_clock_runtime_s,
        )



def export_experimental_validation(
    result: ExperimentalValidationResult,
    output_directory: str | Path,
    *,
    prefix: str = "experimental_validation",
) -> dict[str, Path]:
    """Eksportuje surowe wyniki, statystyki i osobne wykresy."""

    directory = Path(output_directory)
    directory.mkdir(parents=True, exist_ok=True)

    normalized_prefix = prefix.strip()
    if not normalized_prefix:
        raise ValueError(
            "prefix nie może być pusty"
        )

    if Path(normalized_prefix).name != normalized_prefix:
        raise ValueError(
            "prefix nie może zawierać separatorów ścieżki"
        )

    paths = {
        "runs_csv": directory / f"{normalized_prefix}_runs.csv",
        "pairs_csv": directory / f"{normalized_prefix}_pairs.csv",
        "summary_csv": (
            directory / f"{normalized_prefix}_summary.csv"
        ),
        "metadata_json": (
            directory / f"{normalized_prefix}_metadata.json"
        ),
        "objective_chart": (
            directory / f"{normalized_prefix}_objective.png"
        ),
        "satisfaction_chart": (
            directory / f"{normalized_prefix}_satisfaction.png"
        ),
        "runtime_chart": (
            directory / f"{normalized_prefix}_runtime.png"
        ),
        "improvement_chart": (
            directory / f"{normalized_prefix}_improvement.png"
        ),
    }

    _write_dataclass_csv(
        paths["runs_csv"],
        RUN_FIELDNAMES,
        result.run_records,
    )
    _write_dataclass_csv(
        paths["pairs_csv"],
        PAIR_FIELDNAMES,
        result.pair_records,
    )
    _write_dataclass_csv(
        paths["summary_csv"],
        SUMMARY_FIELDNAMES,
        result.summary_records,
    )

    metadata = {
        "base_scenario_id": result.base_scenario_id,
        "started_at_utc": result.started_at_utc.isoformat(),
        "completed_at_utc": result.completed_at_utc.isoformat(),
        "wall_clock_runtime_s": result.wall_clock_runtime_s,
        "repetitions": result.config.repetitions,
        "base_seed": result.config.base_seed,
        "cp_sat_time_limit_s": (
            result.config.cp_sat_time_limit_s
        ),
        "cp_sat_num_search_workers": (
            result.config.cp_sat_num_search_workers
        ),
        "profiles": [
            asdict(profile)
            for profile in result.config.profiles
        ],
        "pair_count": len(result.pair_records),
        "cp_sat_better_objective_count": (
            result.cp_sat_better_objective_count
        ),
        "cp_sat_not_worse_objective_count": (
            result.cp_sat_not_worse_objective_count
        ),
        "mean_objective_improvement_pct": (
            result.mean_objective_improvement_pct
        ),
    }

    paths["metadata_json"].write_text(
        json.dumps(
            metadata,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    _plot_summary_metric(
        result=result,
        metric_name="objective_mean",
        ylabel="Średnia wartość funkcji celu",
        title="Wartość funkcji celu: Greedy i CP-SAT",
        output_path=paths["objective_chart"],
    )
    _plot_summary_metric(
        result=result,
        metric_name="satisfaction_ratio_mean",
        ylabel="Średni udział zrealizowanych zleceń",
        title="Skuteczność realizacji zleceń",
        output_path=paths["satisfaction_chart"],
    )
    _plot_summary_metric(
        result=result,
        metric_name="runtime_mean_s",
        ylabel="Średni czas obliczeń [s]",
        title="Czas obliczeń algorytmów",
        output_path=paths["runtime_chart"],
        logarithmic=True,
    )
    _plot_improvement(
        result=result,
        output_path=paths["improvement_chart"],
    )

    return paths



def _build_run_record(
    *,
    variant: ExperimentScenarioVariant,
    repetition: int,
    algorithm: str,
    comparison: PlanningComparisonResult,
) -> ExperimentRunRecord:
    planning_result = (
        comparison.greedy
        if algorithm == "GREEDY"
        else comparison.cp_sat
    )
    analysis = planning_result.analysis

    return ExperimentRunRecord(
        profile_id=variant.profile.profile_id,
        profile_name=variant.profile.name,
        repetition=repetition,
        random_seed=variant.random_seed,
        resource_ratio=variant.profile.resource_ratio,
        opportunity_dropout_ratio=(
            variant.profile.opportunity_dropout_ratio
        ),
        request_count=variant.scenario.active_request_count,
        mandatory_request_count=(
            variant.scenario.mandatory_request_count
        ),
        source_feasible_opportunity_count=(
            variant.source_feasible_opportunity_count
        ),
        feasible_opportunity_count=(
            variant.feasible_opportunity_count
        ),
        dropped_opportunity_count=(
            variant.dropped_opportunity_count
        ),
        algorithm=algorithm,
        solver_status=planning_result.solver_status,
        schedule_status=planning_result.schedule.status.value,
        objective_value=planning_result.objective_value,
        fully_satisfied_requests=(
            analysis.fully_satisfied_requests
        ),
        partially_satisfied_requests=(
            analysis.partially_satisfied_requests
        ),
        unassigned_requests=analysis.unassigned_requests,
        mandatory_satisfied_requests=(
            analysis.mandatory_satisfied_requests
        ),
        satisfaction_ratio=analysis.satisfaction_ratio,
        mandatory_satisfaction_ratio=(
            analysis.mandatory_satisfaction_ratio
        ),
        total_acquisitions=analysis.total_acquisitions,
        average_selected_quality=(
            analysis.average_selected_quality
        ),
        average_selected_coverage=(
            analysis.average_selected_coverage
        ),
        runtime_s=planning_result.wall_clock_runtime_s,
    )



def _build_pair_record(
    *,
    variant: ExperimentScenarioVariant,
    repetition: int,
    comparison: PlanningComparisonResult,
) -> ExperimentPairRecord:
    greedy_analysis = comparison.greedy.analysis
    cp_sat_analysis = comparison.cp_sat.analysis

    runtime_ratio = comparison.runtime_ratio

    return ExperimentPairRecord(
        profile_id=variant.profile.profile_id,
        repetition=repetition,
        random_seed=variant.random_seed,
        resource_ratio=variant.profile.resource_ratio,
        opportunity_dropout_ratio=(
            variant.profile.opportunity_dropout_ratio
        ),
        dropped_opportunity_count=(
            variant.dropped_opportunity_count
        ),
        greedy_objective_value=(
            comparison.greedy.objective_value
        ),
        cp_sat_objective_value=(
            comparison.cp_sat.objective_value
        ),
        objective_difference=comparison.objective_difference,
        objective_improvement_pct=(
            comparison.objective_improvement_pct
        ),
        greedy_fully_satisfied_requests=(
            greedy_analysis.fully_satisfied_requests
        ),
        cp_sat_fully_satisfied_requests=(
            cp_sat_analysis.fully_satisfied_requests
        ),
        fully_satisfied_difference=(
            comparison.fully_satisfied_difference
        ),
        greedy_mandatory_satisfied_requests=(
            greedy_analysis.mandatory_satisfied_requests
        ),
        cp_sat_mandatory_satisfied_requests=(
            cp_sat_analysis.mandatory_satisfied_requests
        ),
        mandatory_satisfied_difference=(
            cp_sat_analysis.mandatory_satisfied_requests
            - greedy_analysis.mandatory_satisfied_requests
        ),
        greedy_runtime_s=(
            comparison.greedy.wall_clock_runtime_s
        ),
        cp_sat_runtime_s=(
            comparison.cp_sat.wall_clock_runtime_s
        ),
        runtime_ratio=(
            None
            if runtime_ratio is None
            else round(runtime_ratio, 6)
        ),
        cp_sat_solver_status=(
            comparison.cp_sat.solver_status
        ),
    )



def _build_summary_records(
    run_records: list[ExperimentRunRecord],
) -> list[ExperimentSummaryRecord]:
    grouped: dict[
        tuple[str, str],
        list[ExperimentRunRecord],
    ] = {}

    for record in run_records:
        grouped.setdefault(
            (record.profile_id, record.algorithm),
            [],
        ).append(record)

    summary_records: list[ExperimentSummaryRecord] = []

    for (profile_id, algorithm), records in sorted(
        grouped.items()
    ):
        profile_name = records[0].profile_name
        objective_values = [
            record.objective_value
            for record in records
        ]
        satisfaction_values = [
            record.satisfaction_ratio
            for record in records
        ]
        runtime_values = [
            record.runtime_s
            for record in records
        ]

        summary_records.append(
            ExperimentSummaryRecord(
                profile_id=profile_id,
                profile_name=profile_name,
                algorithm=algorithm,
                run_count=len(records),
                objective_mean=round(
                    mean(objective_values),
                    6,
                ),
                objective_std=round(
                    _sample_std(objective_values),
                    6,
                ),
                objective_min=round(
                    min(objective_values),
                    6,
                ),
                objective_max=round(
                    max(objective_values),
                    6,
                ),
                satisfaction_ratio_mean=round(
                    mean(satisfaction_values),
                    6,
                ),
                satisfaction_ratio_std=round(
                    _sample_std(satisfaction_values),
                    6,
                ),
                mandatory_satisfaction_ratio_mean=round(
                    mean(
                        record.mandatory_satisfaction_ratio
                        for record in records
                    ),
                    6,
                ),
                fully_satisfied_requests_mean=round(
                    mean(
                        record.fully_satisfied_requests
                        for record in records
                    ),
                    6,
                ),
                unassigned_requests_mean=round(
                    mean(
                        record.unassigned_requests
                        for record in records
                    ),
                    6,
                ),
                runtime_mean_s=round(
                    mean(runtime_values),
                    6,
                ),
                runtime_std_s=round(
                    _sample_std(runtime_values),
                    6,
                ),
            )
        )

    return summary_records



def _sample_std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return stdev(values)



def _write_dataclass_csv(
    path: Path,
    fieldnames: list[str],
    records: tuple[object, ...],
) -> None:
    with path.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )
        writer.writeheader()

        for record in records:
            writer.writerow(asdict(record))



def _plot_summary_metric(
    *,
    result: ExperimentalValidationResult,
    metric_name: str,
    ylabel: str,
    title: str,
    output_path: Path,
    logarithmic: bool = False,
) -> None:
    profile_ids = [
        profile.profile_id
        for profile in result.config.profiles
    ]

    values_by_algorithm: dict[str, list[float]] = {
        "GREEDY": [],
        "CP_SAT": [],
    }
    errors_by_algorithm: dict[str, list[float]] = {
        "GREEDY": [],
        "CP_SAT": [],
    }

    summary_by_key = {
        (record.profile_id, record.algorithm): record
        for record in result.summary_records
    }

    std_field = {
        "objective_mean": "objective_std",
        "satisfaction_ratio_mean": "satisfaction_ratio_std",
        "runtime_mean_s": "runtime_std_s",
    }[metric_name]

    for algorithm in ("GREEDY", "CP_SAT"):
        for profile_id in profile_ids:
            record = summary_by_key[
                (profile_id, algorithm)
            ]
            values_by_algorithm[algorithm].append(
                float(getattr(record, metric_name))
            )
            errors_by_algorithm[algorithm].append(
                float(getattr(record, std_field))
            )

    positions = list(range(len(profile_ids)))
    width = 0.36

    figure, axis = plt.subplots(figsize=(9, 5.5))

    axis.bar(
        [position - width / 2 for position in positions],
        values_by_algorithm["GREEDY"],
        width,
        yerr=errors_by_algorithm["GREEDY"],
        capsize=4,
        label="Greedy",
    )
    axis.bar(
        [position + width / 2 for position in positions],
        values_by_algorithm["CP_SAT"],
        width,
        yerr=errors_by_algorithm["CP_SAT"],
        capsize=4,
        label="CP-SAT",
    )

    axis.set_xticks(positions, profile_ids)
    axis.set_ylabel(ylabel)
    axis.set_title(title)
    axis.legend()
    axis.grid(axis="y", alpha=0.25)

    if logarithmic:
        axis.set_yscale("log")

    figure.tight_layout()
    figure.savefig(output_path, dpi=180)
    plt.close(figure)



def _plot_improvement(
    *,
    result: ExperimentalValidationResult,
    output_path: Path,
) -> None:
    profile_ids = [
        profile.profile_id
        for profile in result.config.profiles
    ]

    grouped: dict[str, list[float]] = {
        profile_id: []
        for profile_id in profile_ids
    }

    for record in result.pair_records:
        grouped[record.profile_id].append(
            record.objective_improvement_pct
        )

    means = [
        mean(grouped[profile_id])
        for profile_id in profile_ids
    ]
    errors = [
        _sample_std(grouped[profile_id])
        for profile_id in profile_ids
    ]

    figure, axis = plt.subplots(figsize=(9, 5.5))
    axis.bar(
        profile_ids,
        means,
        yerr=errors,
        capsize=4,
    )
    axis.axhline(0.0, linewidth=1.0)
    axis.set_ylabel("Poprawa funkcji celu CP-SAT względem Greedy [%]")
    axis.set_title("Średnia przewaga CP-SAT w profilach degradacji")
    axis.grid(axis="y", alpha=0.25)

    figure.tight_layout()
    figure.savefig(output_path, dpi=180)
    plt.close(figure)
