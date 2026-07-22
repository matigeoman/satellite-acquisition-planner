from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from statistics import mean, stdev
from typing import Iterable


@dataclass(frozen=True)
class AlgorithmBenchmarkConfig:
    """Konfiguracja benchmarku skalowalności Greedy, CP-SAT i Hybrid."""

    request_counts: tuple[int, ...] = (20, 50, 100)
    repetitions: int = 1
    cp_sat_time_limits_s: tuple[float, ...] = (2.0,)
    cp_sat_num_search_workers: int = 1
    base_seed: int = 20260717
    memory_reserve_ratio: float = 0.15
    use_dynamic_transition_model: bool = True
    include_hybrid: bool = False

    def __post_init__(self) -> None:
        if not self.request_counts:
            raise ValueError("request_counts nie może być puste")
        normalized_counts = tuple(sorted(set(self.request_counts)))
        if any(value <= 0 for value in normalized_counts):
            raise ValueError("request_counts muszą być dodatnie")
        if max(normalized_counts) > 500:
            raise ValueError("Maksymalny obsługiwany rozmiar to 500 zleceń")
        object.__setattr__(self, "request_counts", normalized_counts)

        if self.repetitions <= 0:
            raise ValueError("repetitions musi być większe od zera")
        if self.repetitions > 20:
            raise ValueError("repetitions nie może przekraczać 20")

        if not self.cp_sat_time_limits_s:
            raise ValueError("cp_sat_time_limits_s nie może być puste")
        normalized_limits = tuple(sorted(set(self.cp_sat_time_limits_s)))
        if any(value <= 0.0 for value in normalized_limits):
            raise ValueError("Limity CP-SAT muszą być dodatnie")
        object.__setattr__(self, "cp_sat_time_limits_s", normalized_limits)

        if self.cp_sat_num_search_workers <= 0:
            raise ValueError("cp_sat_num_search_workers musi być dodatnie")
        if self.base_seed < 0:
            raise ValueError("base_seed nie może być ujemny")
        if not 0.0 <= self.memory_reserve_ratio <= 1.0:
            raise ValueError(
                "memory_reserve_ratio musi należeć do zakresu [0, 1]"
            )

    @property
    def expected_run_count(self) -> int:
        solver_variants = len(self.cp_sat_time_limits_s)
        if self.include_hybrid:
            solver_variants *= 2
        per_problem = 1 + solver_variants
        return len(self.request_counts) * self.repetitions * per_problem

    @property
    def estimated_cp_sat_budget_s(self) -> float:
        multiplier = 2 if self.include_hybrid else 1
        return round(
            len(self.request_counts)
            * self.repetitions
            * sum(self.cp_sat_time_limits_s)
            * multiplier,
            3,
        )


@dataclass(frozen=True)
class BenchmarkRunRecord:
    request_count: int
    repetition: int
    algorithm: str
    time_limit_s: float | None
    random_seed: int
    opportunity_count: int
    feasible_opportunity_count: int
    estimated_boolean_variable_count: int
    solver_status: str
    schedule_status: str
    objective_value: float
    fully_satisfied_requests: int
    partially_satisfied_requests: int
    unassigned_requests: int
    mandatory_satisfied_requests: int
    satisfaction_ratio: float
    total_acquisitions: int
    sar_acquisitions: int
    optical_acquisitions: int
    total_duration_s: float
    total_data_volume_mb: float
    average_selected_quality: float
    runtime_s: float
    transition_rejections: int
    memory_rejections: int
    acquisition_limit_rejections: int
    imaging_time_rejections: int
    dual_separation_rejections: int
    error_message: str = ""

    @property
    def successful(self) -> bool:
        return not self.error_message

    @property
    def algorithm_variant(self) -> str:
        if self.algorithm == "GREEDY":
            return "GREEDY"
        if self.algorithm == "HYBRID":
            return f"HYBRID {self.time_limit_s:g}s"
        return f"CP-SAT {self.time_limit_s:g}s"


@dataclass(frozen=True)
class BenchmarkPairRecord:
    request_count: int
    repetition: int
    time_limit_s: float
    random_seed: int
    greedy_objective_value: float
    cp_sat_objective_value: float | None
    objective_difference: float | None
    objective_improvement_pct: float | None
    greedy_fully_satisfied_requests: int
    cp_sat_fully_satisfied_requests: int | None
    fully_satisfied_difference: int | None
    greedy_runtime_s: float
    cp_sat_runtime_s: float | None
    runtime_ratio: float | None
    cp_sat_solver_status: str
    cp_sat_successful: bool


@dataclass(frozen=True)
class BenchmarkSummaryRecord:
    request_count: int
    algorithm: str
    time_limit_s: float | None
    run_count: int
    success_count: int
    error_count: int
    objective_mean: float | None
    objective_std: float | None
    satisfaction_ratio_mean: float | None
    fully_satisfied_requests_mean: float | None
    runtime_mean_s: float | None
    runtime_std_s: float | None
    total_acquisitions_mean: float | None
    data_volume_mean_mb: float | None

    @property
    def algorithm_variant(self) -> str:
        if self.algorithm == "GREEDY":
            return "GREEDY"
        if self.algorithm == "HYBRID":
            return f"HYBRID {self.time_limit_s:g}s"
        return f"CP-SAT {self.time_limit_s:g}s"


@dataclass(frozen=True)
class AlgorithmBenchmarkResult:
    base_scenario_id: str
    config: AlgorithmBenchmarkConfig
    run_records: tuple[BenchmarkRunRecord, ...]
    pair_records: tuple[BenchmarkPairRecord, ...]
    summary_records: tuple[BenchmarkSummaryRecord, ...]
    started_at_utc: datetime
    completed_at_utc: datetime
    wall_clock_runtime_s: float

    def __post_init__(self) -> None:
        if len(self.run_records) != self.config.expected_run_count:
            raise ValueError("Niepoprawna liczba rekordów benchmarku")
        expected_pairs = (
            len(self.config.request_counts)
            * self.config.repetitions
            * len(self.config.cp_sat_time_limits_s)
        )
        if len(self.pair_records) != expected_pairs:
            raise ValueError("Niepoprawna liczba porównań benchmarku")
        if self.wall_clock_runtime_s < 0.0:
            raise ValueError("wall_clock_runtime_s nie może być ujemny")

    @property
    def successful_run_count(self) -> int:
        return sum(record.successful for record in self.run_records)

    @property
    def failed_run_count(self) -> int:
        return len(self.run_records) - self.successful_run_count

    @property
    def cp_sat_better_count(self) -> int:
        return sum(
            pair.objective_difference is not None
            and pair.objective_difference > 1e-9
            for pair in self.pair_records
        )

    @property
    def cp_sat_not_worse_count(self) -> int:
        return sum(
            pair.objective_difference is not None
            and pair.objective_difference >= -1e-9
            for pair in self.pair_records
        )

    @property
    def mean_objective_improvement_pct(self) -> float:
        values = [
            pair.objective_improvement_pct
            for pair in self.pair_records
            if pair.objective_improvement_pct is not None
        ]
        return round(mean(values), 6) if values else 0.0

    def _challenger_improvements(self, algorithm: str) -> list[float]:
        grouped: dict[tuple[int, int], list[BenchmarkRunRecord]] = {}
        for record in self.run_records:
            grouped.setdefault(
                (record.request_count, record.repetition), []
            ).append(record)
        values: list[float] = []
        for runs in grouped.values():
            greedy = next(
                (run for run in runs if run.algorithm == "GREEDY" and run.successful),
                None,
            )
            if greedy is None:
                continue
            for challenger in runs:
                if challenger.algorithm != algorithm or not challenger.successful:
                    continue
                difference = challenger.objective_value - greedy.objective_value
                values.append(
                    difference / greedy.objective_value * 100.0
                    if greedy.objective_value > 0.0
                    else 0.0
                )
        return values

    @property
    def hybrid_better_count(self) -> int:
        return sum(value > 1e-9 for value in self._challenger_improvements("HYBRID"))

    @property
    def hybrid_not_worse_count(self) -> int:
        return sum(value >= -1e-9 for value in self._challenger_improvements("HYBRID"))

    @property
    def mean_hybrid_improvement_pct(self) -> float:
        values = self._challenger_improvements("HYBRID")
        return round(mean(values), 6) if values else 0.0

    def metadata_dict(self) -> dict[str, object]:
        return {
            "base_scenario_id": self.base_scenario_id,
            "config": asdict(self.config),
            "started_at_utc": self.started_at_utc.isoformat(),
            "completed_at_utc": self.completed_at_utc.isoformat(),
            "wall_clock_runtime_s": self.wall_clock_runtime_s,
            "successful_run_count": self.successful_run_count,
            "failed_run_count": self.failed_run_count,
            "cp_sat_better_count": self.cp_sat_better_count,
            "cp_sat_not_worse_count": self.cp_sat_not_worse_count,
            "mean_objective_improvement_pct": (
                self.mean_objective_improvement_pct
            ),
            "hybrid_better_count": self.hybrid_better_count,
            "hybrid_not_worse_count": self.hybrid_not_worse_count,
            "mean_hybrid_improvement_pct": self.mean_hybrid_improvement_pct,
        }


def build_benchmark_pairs(
    records: Iterable[BenchmarkRunRecord],
) -> tuple[BenchmarkPairRecord, ...]:
    grouped: dict[tuple[int, int], list[BenchmarkRunRecord]] = {}
    for record in records:
        grouped.setdefault(
            (record.request_count, record.repetition), []
        ).append(record)

    pairs: list[BenchmarkPairRecord] = []
    for key in sorted(grouped):
        runs = grouped[key]
        greedy = next(run for run in runs if run.algorithm == "GREEDY")
        cp_runs = sorted(
            (run for run in runs if run.algorithm == "CP_SAT"),
            key=lambda run: run.time_limit_s or 0.0,
        )
        for cp_run in cp_runs:
            if cp_run.successful and greedy.successful:
                difference = cp_run.objective_value - greedy.objective_value
                improvement = (
                    difference / greedy.objective_value * 100.0
                    if greedy.objective_value > 0.0
                    else 0.0
                )
                fulfilled_difference = (
                    cp_run.fully_satisfied_requests
                    - greedy.fully_satisfied_requests
                )
                runtime_ratio = (
                    cp_run.runtime_s / greedy.runtime_s
                    if greedy.runtime_s > 0.0
                    else None
                )
                cp_objective: float | None = cp_run.objective_value
                cp_fulfilled: int | None = cp_run.fully_satisfied_requests
                cp_runtime: float | None = cp_run.runtime_s
            else:
                difference = None
                improvement = None
                fulfilled_difference = None
                runtime_ratio = None
                cp_objective = None
                cp_fulfilled = None
                cp_runtime = None

            pairs.append(
                BenchmarkPairRecord(
                    request_count=cp_run.request_count,
                    repetition=cp_run.repetition,
                    time_limit_s=float(cp_run.time_limit_s or 0.0),
                    random_seed=cp_run.random_seed,
                    greedy_objective_value=greedy.objective_value,
                    cp_sat_objective_value=cp_objective,
                    objective_difference=(
                        None if difference is None else round(difference, 6)
                    ),
                    objective_improvement_pct=(
                        None if improvement is None else round(improvement, 6)
                    ),
                    greedy_fully_satisfied_requests=(
                        greedy.fully_satisfied_requests
                    ),
                    cp_sat_fully_satisfied_requests=cp_fulfilled,
                    fully_satisfied_difference=fulfilled_difference,
                    greedy_runtime_s=greedy.runtime_s,
                    cp_sat_runtime_s=cp_runtime,
                    runtime_ratio=(
                        None
                        if runtime_ratio is None
                        else round(runtime_ratio, 6)
                    ),
                    cp_sat_solver_status=cp_run.solver_status,
                    cp_sat_successful=cp_run.successful,
                )
            )
    return tuple(pairs)


def build_benchmark_summary(
    records: Iterable[BenchmarkRunRecord],
) -> tuple[BenchmarkSummaryRecord, ...]:
    grouped: dict[
        tuple[int, str, float | None], list[BenchmarkRunRecord]
    ] = {}
    for record in records:
        grouped.setdefault(
            (record.request_count, record.algorithm, record.time_limit_s), []
        ).append(record)

    summaries: list[BenchmarkSummaryRecord] = []
    for (request_count, algorithm, time_limit_s), group in sorted(
        grouped.items(),
        key=lambda item: (
            item[0][0],
            {"GREEDY": 0, "CP_SAT": 1, "HYBRID": 2}.get(item[0][1], 9),
            item[0][2] or 0.0,
        ),
    ):
        successful = [record for record in group if record.successful]
        summaries.append(
            BenchmarkSummaryRecord(
                request_count=request_count,
                algorithm=algorithm,
                time_limit_s=time_limit_s,
                run_count=len(group),
                success_count=len(successful),
                error_count=len(group) - len(successful),
                objective_mean=_mean_or_none(
                    record.objective_value for record in successful
                ),
                objective_std=_stdev_or_none(
                    record.objective_value for record in successful
                ),
                satisfaction_ratio_mean=_mean_or_none(
                    record.satisfaction_ratio for record in successful
                ),
                fully_satisfied_requests_mean=_mean_or_none(
                    record.fully_satisfied_requests for record in successful
                ),
                runtime_mean_s=_mean_or_none(
                    record.runtime_s for record in successful
                ),
                runtime_std_s=_stdev_or_none(
                    record.runtime_s for record in successful
                ),
                total_acquisitions_mean=_mean_or_none(
                    record.total_acquisitions for record in successful
                ),
                data_volume_mean_mb=_mean_or_none(
                    record.total_data_volume_mb for record in successful
                ),
            )
        )
    return tuple(summaries)


def _mean_or_none(values: Iterable[float]) -> float | None:
    items = [float(value) for value in values]
    return round(mean(items), 6) if items else None


def _stdev_or_none(values: Iterable[float]) -> float | None:
    items = [float(value) for value in values]
    if not items:
        return None
    if len(items) == 1:
        return 0.0
    return round(stdev(items), 6)
