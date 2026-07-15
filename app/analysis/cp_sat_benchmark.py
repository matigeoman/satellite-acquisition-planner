from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from app.analysis.schedule_report import ScheduleAnalysis
from app.models.schedule import Schedule


BENCHMARK_FIELDNAMES = [
    "scenario_id",
    "algorithm",
    "time_limit_s",
    "solver_status",
    "schedule_status",
    "schedule_id",
    "objective_value",
    "fully_satisfied_requests",
    "partially_satisfied_requests",
    "unassigned_requests",
    "mandatory_satisfied_requests",
    "total_acquisitions",
    "sar_acquisitions",
    "optical_acquisitions",
    "total_duration_s",
    "total_data_volume_mb",
    "average_selected_quality",
    "average_selected_coverage",
    "satisfaction_ratio",
    "runtime_s",
    "objective_difference_vs_greedy",
    "objective_improvement_pct_vs_greedy",
    "fulfilled_difference_vs_greedy",
    "unassigned_reduction_vs_greedy",
    "runtime_ratio_vs_greedy",
    "schedule_path",
]


@dataclass(frozen=True)
class BenchmarkResult:
    """Wynik pojedynczego uruchomienia algorytmu."""

    algorithm: str
    time_limit_s: float | None

    solver_status: str
    schedule_status: str
    schedule_id: str

    objective_value: float

    fully_satisfied_requests: int
    partially_satisfied_requests: int
    unassigned_requests: int
    mandatory_satisfied_requests: int

    total_acquisitions: int
    sar_acquisitions: int
    optical_acquisitions: int

    total_duration_s: float
    total_data_volume_mb: float

    average_selected_quality: float
    average_selected_coverage: float
    satisfaction_ratio: float

    runtime_s: float
    schedule_path: str

    def __post_init__(self) -> None:
        if self.algorithm not in {
            "GREEDY",
            "CP_SAT",
        }:
            raise ValueError(
                "algorithm musi mieć wartość GREEDY albo CP_SAT"
            )

        if self.algorithm == "GREEDY":
            if self.time_limit_s is not None:
                raise ValueError(
                    "Greedy nie może posiadać time_limit_s"
                )
        else:
            if (
                self.time_limit_s is None
                or self.time_limit_s <= 0.0
            ):
                raise ValueError(
                    "CP_SAT wymaga dodatniego time_limit_s"
                )

        if self.objective_value < 0.0:
            raise ValueError(
                "objective_value nie może być ujemne"
            )

        if self.runtime_s < 0.0:
            raise ValueError(
                "runtime_s nie może być ujemne"
            )

        count_values = {
            "fully_satisfied_requests": (
                self.fully_satisfied_requests
            ),
            "partially_satisfied_requests": (
                self.partially_satisfied_requests
            ),
            "unassigned_requests": (
                self.unassigned_requests
            ),
            "mandatory_satisfied_requests": (
                self.mandatory_satisfied_requests
            ),
            "total_acquisitions": (
                self.total_acquisitions
            ),
            "sar_acquisitions": (
                self.sar_acquisitions
            ),
            "optical_acquisitions": (
                self.optical_acquisitions
            ),
        }

        for name, value in count_values.items():
            if value < 0:
                raise ValueError(
                    f"{name} nie może być ujemne"
                )

        ratio_values = {
            "average_selected_quality": (
                self.average_selected_quality
            ),
            "average_selected_coverage": (
                self.average_selected_coverage
            ),
            "satisfaction_ratio": (
                self.satisfaction_ratio
            ),
        }

        for name, value in ratio_values.items():
            if not 0.0 <= value <= 1.0:
                raise ValueError(
                    f"{name} musi należeć do zakresu [0, 1]"
                )


@dataclass(frozen=True)
class BenchmarkReport:
    """Seria wyników Greedy i CP-SAT."""

    scenario_id: str
    greedy: BenchmarkResult
    cp_sat_runs: tuple[BenchmarkResult, ...]

    def __post_init__(self) -> None:
        normalized_scenario_id = self.scenario_id.strip()

        if not normalized_scenario_id:
            raise ValueError(
                "scenario_id nie może być pusty"
            )

        object.__setattr__(
            self,
            "scenario_id",
            normalized_scenario_id,
        )

        if self.greedy.algorithm != "GREEDY":
            raise ValueError(
                "Pole greedy musi zawierać wynik GREEDY"
            )

        if not self.cp_sat_runs:
            raise ValueError(
                "Benchmark wymaga co najmniej jednego wyniku CP_SAT"
            )

        if any(
            result.algorithm != "CP_SAT"
            for result in self.cp_sat_runs
        ):
            raise ValueError(
                "cp_sat_runs może zawierać tylko wyniki CP_SAT"
            )

        limits = [
            result.time_limit_s
            for result in self.cp_sat_runs
        ]

        if len(limits) != len(set(limits)):
            raise ValueError(
                "Limity czasu CP-SAT nie mogą się powtarzać"
            )

        sorted_runs = tuple(
            sorted(
                self.cp_sat_runs,
                key=lambda result: (
                    result.time_limit_s
                    or 0.0
                ),
            )
        )

        object.__setattr__(
            self,
            "cp_sat_runs",
            sorted_runs,
        )

    @property
    def best_cp_sat_run(self) -> BenchmarkResult:
        """Najlepszy wynik CP-SAT znaleziony w benchmarku."""

        return max(
            self.cp_sat_runs,
            key=lambda result: (
                result.objective_value,
                result.fully_satisfied_requests,
                -result.runtime_s,
            ),
        )

    @property
    def best_objective_difference(self) -> float:
        return round(
            (
                self.best_cp_sat_run.objective_value
                - self.greedy.objective_value
            ),
            6,
        )

    @property
    def best_objective_improvement_pct(self) -> float:
        if self.greedy.objective_value <= 0.0:
            return 0.0

        return round(
            (
                self.best_objective_difference
                / self.greedy.objective_value
                * 100.0
            ),
            6,
        )

    def csv_rows(self) -> list[dict[str, object]]:
        """Buduje wiersz Greedy oraz wiersze kolejnych CP-SAT."""

        rows = [
            self._result_to_row(
                result=self.greedy,
            )
        ]

        rows.extend(
            self._result_to_row(
                result=result,
            )
            for result in self.cp_sat_runs
        )

        return rows

    def _result_to_row(
        self,
        *,
        result: BenchmarkResult,
    ) -> dict[str, object]:
        if result.algorithm == "GREEDY":
            objective_difference = 0.0
            improvement_pct = 0.0
            fulfilled_difference = 0
            unassigned_reduction = 0
            runtime_ratio: float | str = 1.0
        else:
            objective_difference = (
                result.objective_value
                - self.greedy.objective_value
            )

            if self.greedy.objective_value > 0.0:
                improvement_pct = (
                    objective_difference
                    / self.greedy.objective_value
                    * 100.0
                )
            else:
                improvement_pct = 0.0

            fulfilled_difference = (
                result.fully_satisfied_requests
                - self.greedy.fully_satisfied_requests
            )

            unassigned_reduction = (
                self.greedy.unassigned_requests
                - result.unassigned_requests
            )

            if self.greedy.runtime_s > 0.0:
                runtime_ratio = (
                    result.runtime_s
                    / self.greedy.runtime_s
                )
            else:
                runtime_ratio = ""

        return {
            "scenario_id": self.scenario_id,
            "algorithm": result.algorithm,
            "time_limit_s": (
                ""
                if result.time_limit_s is None
                else result.time_limit_s
            ),
            "solver_status": result.solver_status,
            "schedule_status": result.schedule_status,
            "schedule_id": result.schedule_id,
            "objective_value": round(
                result.objective_value,
                6,
            ),
            "fully_satisfied_requests": (
                result.fully_satisfied_requests
            ),
            "partially_satisfied_requests": (
                result.partially_satisfied_requests
            ),
            "unassigned_requests": (
                result.unassigned_requests
            ),
            "mandatory_satisfied_requests": (
                result.mandatory_satisfied_requests
            ),
            "total_acquisitions": (
                result.total_acquisitions
            ),
            "sar_acquisitions": (
                result.sar_acquisitions
            ),
            "optical_acquisitions": (
                result.optical_acquisitions
            ),
            "total_duration_s": round(
                result.total_duration_s,
                6,
            ),
            "total_data_volume_mb": round(
                result.total_data_volume_mb,
                6,
            ),
            "average_selected_quality": round(
                result.average_selected_quality,
                6,
            ),
            "average_selected_coverage": round(
                result.average_selected_coverage,
                6,
            ),
            "satisfaction_ratio": round(
                result.satisfaction_ratio,
                6,
            ),
            "runtime_s": round(
                result.runtime_s,
                6,
            ),
            "objective_difference_vs_greedy": round(
                objective_difference,
                6,
            ),
            "objective_improvement_pct_vs_greedy": round(
                improvement_pct,
                6,
            ),
            "fulfilled_difference_vs_greedy": (
                fulfilled_difference
            ),
            "unassigned_reduction_vs_greedy": (
                unassigned_reduction
            ),
            "runtime_ratio_vs_greedy": (
                ""
                if runtime_ratio == ""
                else round(
                    float(runtime_ratio),
                    6,
                )
            ),
            "schedule_path": result.schedule_path,
        }


def build_benchmark_result(
    *,
    schedule: Schedule,
    analysis: ScheduleAnalysis,
    solver_status: str,
    time_limit_s: float | None,
    schedule_path: str | Path,
) -> BenchmarkResult:
    """Buduje pojedynczy wynik benchmarku."""

    if analysis.schedule_id != schedule.schedule_id:
        raise ValueError(
            "Analiza nie odpowiada przekazanemu harmonogramowi"
        )

    return BenchmarkResult(
        algorithm=schedule.algorithm.value,
        time_limit_s=time_limit_s,
        solver_status=solver_status,
        schedule_status=schedule.status.value,
        schedule_id=schedule.schedule_id,
        objective_value=float(
            schedule.objective_value
            or 0.0
        ),
        fully_satisfied_requests=(
            analysis.fully_satisfied_requests
        ),
        partially_satisfied_requests=(
            analysis.partially_satisfied_requests
        ),
        unassigned_requests=(
            analysis.unassigned_requests
        ),
        mandatory_satisfied_requests=(
            analysis.mandatory_satisfied_requests
        ),
        total_acquisitions=(
            analysis.total_acquisitions
        ),
        sar_acquisitions=(
            analysis.sar_acquisitions
        ),
        optical_acquisitions=(
            analysis.optical_acquisitions
        ),
        total_duration_s=(
            analysis.total_duration_s
        ),
        total_data_volume_mb=(
            analysis.total_data_volume_mb
        ),
        average_selected_quality=(
            analysis.average_selected_quality
        ),
        average_selected_coverage=(
            analysis.average_selected_coverage
        ),
        satisfaction_ratio=(
            analysis.satisfaction_ratio
        ),
        runtime_s=float(
            schedule.solver_runtime_s
            or 0.0
        ),
        schedule_path=str(
            schedule_path
        ),
    )


def build_benchmark_report(
    *,
    scenario_id: str,
    greedy: BenchmarkResult,
    cp_sat_runs: list[BenchmarkResult]
    | tuple[BenchmarkResult, ...],
) -> BenchmarkReport:
    """Buduje kompletny raport benchmarku."""

    return BenchmarkReport(
        scenario_id=scenario_id,
        greedy=greedy,
        cp_sat_runs=tuple(
            cp_sat_runs
        ),
    )


def export_benchmark_report(
    report: BenchmarkReport,
    output_directory: str | Path,
    *,
    prefix: str = "cp_sat_benchmark",
) -> dict[str, Path]:
    """Eksportuje CSV i wykresy benchmarku."""

    directory = Path(
        output_directory
    )

    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

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
        "csv": (
            directory
            / f"{normalized_prefix}.csv"
        ),
        "objective_chart": (
            directory
            / f"{normalized_prefix}_objective.png"
        ),
        "fulfilled_chart": (
            directory
            / f"{normalized_prefix}_fulfilled.png"
        ),
        "runtime_chart": (
            directory
            / f"{normalized_prefix}_runtime.png"
        ),
    }

    _write_csv(
        report=report,
        path=paths["csv"],
    )

    _save_objective_chart(
        report=report,
        path=paths["objective_chart"],
    )

    _save_fulfilled_chart(
        report=report,
        path=paths["fulfilled_chart"],
    )

    _save_runtime_chart(
        report=report,
        path=paths["runtime_chart"],
    )

    return paths


def format_time_limit_label(
    time_limit_s: float,
) -> str:
    """Buduje fragment identyfikatora bez kropki dziesiętnej."""

    if time_limit_s <= 0.0:
        raise ValueError(
            "time_limit_s musi być większe od zera"
        )

    if float(time_limit_s).is_integer():
        return f"{int(time_limit_s)}S"

    normalized = (
        f"{time_limit_s:g}"
        .replace(".", "P")
    )

    return f"{normalized}S"


def _write_csv(
    *,
    report: BenchmarkReport,
    path: Path,
) -> None:
    with path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=BENCHMARK_FIELDNAMES,
        )

        writer.writeheader()
        writer.writerows(
            report.csv_rows()
        )


def _save_objective_chart(
    *,
    report: BenchmarkReport,
    path: Path,
) -> None:
    limits = [
        result.time_limit_s or 0.0
        for result in report.cp_sat_runs
    ]

    objectives = [
        result.objective_value
        for result in report.cp_sat_runs
    ]

    figure, axis = plt.subplots(
        figsize=(7.5, 4.8)
    )

    axis.plot(
        limits,
        objectives,
        marker="o",
        label="CP-SAT",
    )

    axis.axhline(
        report.greedy.objective_value,
        linestyle="--",
        label="Greedy",
    )

    axis.set_title(
        "Wpływ limitu czasu na funkcję celu"
    )

    axis.set_xlabel(
        "Limit czasu CP-SAT [s]"
    )

    axis.set_ylabel(
        "Wartość funkcji celu"
    )

    axis.grid(
        alpha=0.3,
    )

    axis.legend()

    for limit, value in zip(
        limits,
        objectives,
        strict=True,
    ):
        axis.annotate(
            f"{value:.2f}",
            xy=(limit, value),
            xytext=(0, 6),
            textcoords="offset points",
            ha="center",
        )

    figure.tight_layout()

    figure.savefig(
        path,
        dpi=160,
        bbox_inches="tight",
    )

    plt.close(
        figure
    )


def _save_fulfilled_chart(
    *,
    report: BenchmarkReport,
    path: Path,
) -> None:
    limits = [
        result.time_limit_s or 0.0
        for result in report.cp_sat_runs
    ]

    fulfilled = [
        result.fully_satisfied_requests
        for result in report.cp_sat_runs
    ]

    figure, axis = plt.subplots(
        figsize=(7.5, 4.8)
    )

    axis.plot(
        limits,
        fulfilled,
        marker="o",
        label="CP-SAT",
    )

    axis.axhline(
        report.greedy.fully_satisfied_requests,
        linestyle="--",
        label="Greedy",
    )

    axis.set_title(
        "Wpływ limitu czasu na realizację zleceń"
    )

    axis.set_xlabel(
        "Limit czasu CP-SAT [s]"
    )

    axis.set_ylabel(
        "W pełni zrealizowane zlecenia"
    )

    axis.grid(
        alpha=0.3,
    )

    axis.legend()

    for limit, value in zip(
        limits,
        fulfilled,
        strict=True,
    ):
        axis.annotate(
            str(value),
            xy=(limit, value),
            xytext=(0, 6),
            textcoords="offset points",
            ha="center",
        )

    figure.tight_layout()

    figure.savefig(
        path,
        dpi=160,
        bbox_inches="tight",
    )

    plt.close(
        figure
    )


def _save_runtime_chart(
    *,
    report: BenchmarkReport,
    path: Path,
) -> None:
    limits = [
        result.time_limit_s or 0.0
        for result in report.cp_sat_runs
    ]

    runtimes = [
        result.runtime_s
        for result in report.cp_sat_runs
    ]

    figure, axis = plt.subplots(
        figsize=(7.5, 4.8)
    )

    axis.plot(
        limits,
        runtimes,
        marker="o",
        label="Rzeczywisty czas CP-SAT",
    )

    axis.plot(
        limits,
        limits,
        linestyle="--",
        label="Ustawiony limit",
    )

    axis.set_title(
        "Rzeczywisty czas działania CP-SAT"
    )

    axis.set_xlabel(
        "Limit czasu CP-SAT [s]"
    )

    axis.set_ylabel(
        "Rzeczywisty czas [s]"
    )

    axis.grid(
        alpha=0.3,
    )

    axis.legend()

    for limit, runtime in zip(
        limits,
        runtimes,
        strict=True,
    ):
        axis.annotate(
            f"{runtime:.3f}",
            xy=(limit, runtime),
            xytext=(0, 6),
            textcoords="offset points",
            ha="center",
        )

    figure.tight_layout()

    figure.savefig(
        path,
        dpi=160,
        bbox_inches="tight",
    )

    plt.close(
        figure
    )