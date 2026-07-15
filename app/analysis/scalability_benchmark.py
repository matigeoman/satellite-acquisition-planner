from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt


SCALABILITY_FIELDNAMES = [
    "scenario_id",
    "request_count",
    "opportunity_count",
    "selection_variable_count",
    "request_variable_count",
    "auxiliary_variable_count",
    "estimated_boolean_variable_count",
    "algorithm",
    "time_limit_s",
    "solver_status",
    "schedule_status",
    "objective_value",
    "fully_satisfied_requests",
    "unassigned_requests",
    "satisfaction_ratio",
    "total_acquisitions",
    "runtime_s",
    "objective_difference_vs_greedy",
    "objective_improvement_pct_vs_greedy",
    "fulfilled_difference_vs_greedy",
    "unassigned_reduction_vs_greedy",
    "schedule_path",
]


@dataclass(frozen=True)
class ScalabilityRunResult:
    """Wynik jednego algorytmu dla jednego rozmiaru problemu."""

    request_count: int
    opportunity_count: int

    selection_variable_count: int
    request_variable_count: int
    auxiliary_variable_count: int

    algorithm: str
    time_limit_s: float | None
    solver_status: str
    schedule_status: str

    objective_value: float
    fully_satisfied_requests: int
    unassigned_requests: int
    satisfaction_ratio: float
    total_acquisitions: int
    runtime_s: float

    schedule_path: str

    def __post_init__(self) -> None:
        if self.request_count <= 0:
            raise ValueError(
                "request_count musi być większe od zera"
            )

        if self.opportunity_count <= 0:
            raise ValueError(
                "opportunity_count musi być większe od zera"
            )

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
                    "Greedy nie może posiadać limitu czasu"
                )
        elif (
            self.time_limit_s is None
            or self.time_limit_s <= 0.0
        ):
            raise ValueError(
                "CP_SAT wymaga dodatniego limitu czasu"
            )

        count_values = {
            "selection_variable_count": (
                self.selection_variable_count
            ),
            "request_variable_count": (
                self.request_variable_count
            ),
            "auxiliary_variable_count": (
                self.auxiliary_variable_count
            ),
            "fully_satisfied_requests": (
                self.fully_satisfied_requests
            ),
            "unassigned_requests": (
                self.unassigned_requests
            ),
            "total_acquisitions": (
                self.total_acquisitions
            ),
        }

        for name, value in count_values.items():
            if value < 0:
                raise ValueError(
                    f"{name} nie może być ujemne"
                )

        if self.objective_value < 0.0:
            raise ValueError(
                "objective_value nie może być ujemne"
            )

        if self.runtime_s < 0.0:
            raise ValueError(
                "runtime_s nie może być ujemne"
            )

        if not 0.0 <= self.satisfaction_ratio <= 1.0:
            raise ValueError(
                "satisfaction_ratio musi należeć "
                "do zakresu [0, 1]"
            )

    @property
    def estimated_boolean_variable_count(self) -> int:
        return (
            self.selection_variable_count
            + self.request_variable_count
            + self.auxiliary_variable_count
        )


@dataclass(frozen=True)
class ScalabilityBenchmarkReport:
    """Raport dla kilku rozmiarów problemu."""

    scenario_id: str
    results: tuple[ScalabilityRunResult, ...]

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

        if not self.results:
            raise ValueError(
                "Raport musi zawierać co najmniej jeden wynik"
            )

        grouped = self.grouped_results

        for request_count, algorithms in grouped.items():
            if set(algorithms) != {
                "GREEDY",
                "CP_SAT",
            }:
                raise ValueError(
                    f"Rozmiar {request_count} musi zawierać "
                    "dokładnie GREEDY oraz CP_SAT"
                )

        sorted_results = tuple(
            sorted(
                self.results,
                key=lambda result: (
                    result.request_count,
                    0
                    if result.algorithm == "GREEDY"
                    else 1,
                ),
            )
        )

        object.__setattr__(
            self,
            "results",
            sorted_results,
        )

    @property
    def grouped_results(
        self,
    ) -> dict[
        int,
        dict[str, ScalabilityRunResult],
    ]:
        grouped: dict[
            int,
            dict[str, ScalabilityRunResult],
        ] = {}

        for result in self.results:
            algorithm_results = grouped.setdefault(
                result.request_count,
                {},
            )

            if result.algorithm in algorithm_results:
                raise ValueError(
                    "Powtórzony wynik algorytmu "
                    f"{result.algorithm} dla "
                    f"{result.request_count} zleceń"
                )

            algorithm_results[
                result.algorithm
            ] = result

        return grouped

    @property
    def request_counts(self) -> list[int]:
        return sorted(
            self.grouped_results
        )

    def csv_rows(self) -> list[dict[str, object]]:
        rows = []

        grouped = self.grouped_results

        for request_count in sorted(grouped):
            greedy = grouped[
                request_count
            ]["GREEDY"]

            cp_sat = grouped[
                request_count
            ]["CP_SAT"]

            rows.append(
                self._build_row(
                    result=greedy,
                    greedy=greedy,
                )
            )

            rows.append(
                self._build_row(
                    result=cp_sat,
                    greedy=greedy,
                )
            )

        return rows

    def _build_row(
        self,
        *,
        result: ScalabilityRunResult,
        greedy: ScalabilityRunResult,
    ) -> dict[str, object]:
        if result.algorithm == "GREEDY":
            objective_difference = 0.0
            objective_improvement_pct = 0.0
            fulfilled_difference = 0
            unassigned_reduction = 0
        else:
            objective_difference = (
                result.objective_value
                - greedy.objective_value
            )

            if greedy.objective_value > 0.0:
                objective_improvement_pct = (
                    objective_difference
                    / greedy.objective_value
                    * 100.0
                )
            else:
                objective_improvement_pct = 0.0

            fulfilled_difference = (
                result.fully_satisfied_requests
                - greedy.fully_satisfied_requests
            )

            unassigned_reduction = (
                greedy.unassigned_requests
                - result.unassigned_requests
            )

        return {
            "scenario_id": self.scenario_id,
            "request_count": result.request_count,
            "opportunity_count": result.opportunity_count,
            "selection_variable_count": (
                result.selection_variable_count
            ),
            "request_variable_count": (
                result.request_variable_count
            ),
            "auxiliary_variable_count": (
                result.auxiliary_variable_count
            ),
            "estimated_boolean_variable_count": (
                result.estimated_boolean_variable_count
            ),
            "algorithm": result.algorithm,
            "time_limit_s": (
                ""
                if result.time_limit_s is None
                else result.time_limit_s
            ),
            "solver_status": result.solver_status,
            "schedule_status": result.schedule_status,
            "objective_value": round(
                result.objective_value,
                6,
            ),
            "fully_satisfied_requests": (
                result.fully_satisfied_requests
            ),
            "unassigned_requests": (
                result.unassigned_requests
            ),
            "satisfaction_ratio": round(
                result.satisfaction_ratio,
                6,
            ),
            "total_acquisitions": (
                result.total_acquisitions
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
                objective_improvement_pct,
                6,
            ),
            "fulfilled_difference_vs_greedy": (
                fulfilled_difference
            ),
            "unassigned_reduction_vs_greedy": (
                unassigned_reduction
            ),
            "schedule_path": result.schedule_path,
        }


def build_scalability_report(
    *,
    scenario_id: str,
    results: list[ScalabilityRunResult]
    | tuple[ScalabilityRunResult, ...],
) -> ScalabilityBenchmarkReport:
    return ScalabilityBenchmarkReport(
        scenario_id=scenario_id,
        results=tuple(results),
    )


def export_scalability_report(
    report: ScalabilityBenchmarkReport,
    output_directory: str | Path,
    *,
    prefix: str = "scalability_benchmark",
) -> dict[str, Path]:
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
        "improvement_chart": (
            directory
            / f"{normalized_prefix}_improvement.png"
        ),
    }

    _write_csv(
        report=report,
        path=paths["csv"],
    )

    _save_algorithm_chart(
        report=report,
        value_name="objective_value",
        title="Funkcja celu względem liczby zleceń",
        y_label="Wartość funkcji celu",
        path=paths["objective_chart"],
    )

    _save_algorithm_chart(
        report=report,
        value_name="fully_satisfied_requests",
        title="Realizacja zleceń względem rozmiaru problemu",
        y_label="W pełni zrealizowane zlecenia",
        path=paths["fulfilled_chart"],
    )

    _save_algorithm_chart(
        report=report,
        value_name="runtime_s",
        title="Czas działania względem liczby zleceń",
        y_label="Czas działania [s]",
        path=paths["runtime_chart"],
        log_scale=True,
    )

    _save_improvement_chart(
        report=report,
        path=paths["improvement_chart"],
    )

    return paths


def _write_csv(
    *,
    report: ScalabilityBenchmarkReport,
    path: Path,
) -> None:
    with path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=SCALABILITY_FIELDNAMES,
        )

        writer.writeheader()
        writer.writerows(
            report.csv_rows()
        )


def _save_algorithm_chart(
    *,
    report: ScalabilityBenchmarkReport,
    value_name: str,
    title: str,
    y_label: str,
    path: Path,
    log_scale: bool = False,
) -> None:
    grouped = report.grouped_results
    request_counts = report.request_counts

    greedy_values = [
        float(
            getattr(
                grouped[count]["GREEDY"],
                value_name,
            )
        )
        for count in request_counts
    ]

    cp_sat_values = [
        float(
            getattr(
                grouped[count]["CP_SAT"],
                value_name,
            )
        )
        for count in request_counts
    ]

    figure, axis = plt.subplots(
        figsize=(8.0, 5.0)
    )

    axis.plot(
        request_counts,
        greedy_values,
        marker="o",
        label="Greedy",
    )

    axis.plot(
        request_counts,
        cp_sat_values,
        marker="o",
        label="CP-SAT",
    )

    axis.set_title(
        title
    )

    axis.set_xlabel(
        "Liczba zleceń"
    )

    axis.set_ylabel(
        y_label
    )

    axis.grid(
        alpha=0.3,
    )

    axis.legend()

    if log_scale and all(
        value > 0.0
        for value in [
            *greedy_values,
            *cp_sat_values,
        ]
    ):
        axis.set_yscale(
            "log"
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


def _save_improvement_chart(
    *,
    report: ScalabilityBenchmarkReport,
    path: Path,
) -> None:
    grouped = report.grouped_results
    request_counts = report.request_counts

    improvement_values = []

    for request_count in request_counts:
        greedy = grouped[
            request_count
        ]["GREEDY"]

        cp_sat = grouped[
            request_count
        ]["CP_SAT"]

        if greedy.objective_value > 0.0:
            improvement = (
                (
                    cp_sat.objective_value
                    - greedy.objective_value
                )
                / greedy.objective_value
                * 100.0
            )
        else:
            improvement = 0.0

        improvement_values.append(
            improvement
        )

    figure, axis = plt.subplots(
        figsize=(8.0, 5.0)
    )

    axis.plot(
        request_counts,
        improvement_values,
        marker="o",
    )

    axis.axhline(
        0.0,
        linestyle="--",
    )

    axis.set_title(
        "Poprawa CP-SAT względem Greedy"
    )

    axis.set_xlabel(
        "Liczba zleceń"
    )

    axis.set_ylabel(
        "Poprawa funkcji celu [%]"
    )

    axis.grid(
        alpha=0.3,
    )

    for request_count, improvement in zip(
        request_counts,
        improvement_values,
        strict=True,
    ):
        axis.annotate(
            f"{improvement:.2f}%",
            xy=(
                request_count,
                improvement,
            ),
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