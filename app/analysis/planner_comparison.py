from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from app.analysis.schedule_report import ScheduleAnalysis
from app.models.schedule import Schedule


COMPARISON_FIELDNAMES = [
    "scenario_id",
    "algorithm",
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
    "solver_runtime_s",
    "objective_difference_vs_greedy",
    "objective_improvement_pct_vs_greedy",
    "fully_satisfied_difference_vs_greedy",
    "unassigned_reduction_vs_greedy",
    "runtime_ratio_vs_greedy",
]


@dataclass(frozen=True)
class PlannerSnapshot:
    """Najważniejsze wyniki jednego algorytmu."""

    algorithm: str
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

    solver_runtime_s: float


@dataclass(frozen=True)
class PlannerComparison:
    """Porównanie harmonogramów Greedy i CP-SAT."""

    scenario_id: str
    greedy: PlannerSnapshot
    cp_sat: PlannerSnapshot

    @property
    def objective_difference(self) -> float:
        return round(
            (
                self.cp_sat.objective_value
                - self.greedy.objective_value
            ),
            6,
        )

    @property
    def objective_improvement_ratio(self) -> float:
        if self.greedy.objective_value == 0.0:
            return 0.0

        return (
            self.objective_difference
            / self.greedy.objective_value
        )

    @property
    def objective_improvement_pct(self) -> float:
        return round(
            self.objective_improvement_ratio * 100.0,
            6,
        )

    @property
    def additional_fully_satisfied_requests(self) -> int:
        return (
            self.cp_sat.fully_satisfied_requests
            - self.greedy.fully_satisfied_requests
        )

    @property
    def unassigned_request_reduction(self) -> int:
        return (
            self.greedy.unassigned_requests
            - self.cp_sat.unassigned_requests
        )

    @property
    def runtime_ratio(self) -> float | None:
        if self.greedy.solver_runtime_s <= 0.0:
            return None

        return round(
            (
                self.cp_sat.solver_runtime_s
                / self.greedy.solver_runtime_s
            ),
            6,
        )

    def csv_rows(self) -> list[dict[str, object]]:
        """Buduje dwa wiersze raportu: Greedy i CP-SAT."""

        greedy_row = self._snapshot_to_row(
            snapshot=self.greedy,
            objective_difference=0.0,
            objective_improvement_pct=0.0,
            fulfilled_difference=0,
            unassigned_reduction=0,
            runtime_ratio=1.0,
        )

        cp_sat_row = self._snapshot_to_row(
            snapshot=self.cp_sat,
            objective_difference=self.objective_difference,
            objective_improvement_pct=(
                self.objective_improvement_pct
            ),
            fulfilled_difference=(
                self.additional_fully_satisfied_requests
            ),
            unassigned_reduction=(
                self.unassigned_request_reduction
            ),
            runtime_ratio=self.runtime_ratio,
        )

        return [
            greedy_row,
            cp_sat_row,
        ]

    def _snapshot_to_row(
        self,
        *,
        snapshot: PlannerSnapshot,
        objective_difference: float,
        objective_improvement_pct: float,
        fulfilled_difference: int,
        unassigned_reduction: int,
        runtime_ratio: float | None,
    ) -> dict[str, object]:
        return {
            "scenario_id": self.scenario_id,
            "algorithm": snapshot.algorithm,
            "solver_status": snapshot.solver_status,
            "schedule_status": snapshot.schedule_status,
            "schedule_id": snapshot.schedule_id,
            "objective_value": round(
                snapshot.objective_value,
                6,
            ),
            "fully_satisfied_requests": (
                snapshot.fully_satisfied_requests
            ),
            "partially_satisfied_requests": (
                snapshot.partially_satisfied_requests
            ),
            "unassigned_requests": (
                snapshot.unassigned_requests
            ),
            "mandatory_satisfied_requests": (
                snapshot.mandatory_satisfied_requests
            ),
            "total_acquisitions": (
                snapshot.total_acquisitions
            ),
            "sar_acquisitions": (
                snapshot.sar_acquisitions
            ),
            "optical_acquisitions": (
                snapshot.optical_acquisitions
            ),
            "total_duration_s": round(
                snapshot.total_duration_s,
                6,
            ),
            "total_data_volume_mb": round(
                snapshot.total_data_volume_mb,
                6,
            ),
            "average_selected_quality": round(
                snapshot.average_selected_quality,
                6,
            ),
            "average_selected_coverage": round(
                snapshot.average_selected_coverage,
                6,
            ),
            "satisfaction_ratio": round(
                snapshot.satisfaction_ratio,
                6,
            ),
            "solver_runtime_s": round(
                snapshot.solver_runtime_s,
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
            "fully_satisfied_difference_vs_greedy": (
                fulfilled_difference
            ),
            "unassigned_reduction_vs_greedy": (
                unassigned_reduction
            ),
            "runtime_ratio_vs_greedy": (
                ""
                if runtime_ratio is None
                else round(runtime_ratio, 6)
            ),
        }


def build_planner_comparison(
    *,
    scenario_id: str,
    greedy_schedule: Schedule,
    cp_sat_schedule: Schedule,
    greedy_analysis: ScheduleAnalysis,
    cp_sat_analysis: ScheduleAnalysis,
    cp_sat_solver_status: str | None = None,
) -> PlannerComparison:
    """Buduje porównanie dwóch gotowych harmonogramów."""

    normalized_scenario_id = scenario_id.strip()

    if not normalized_scenario_id:
        raise ValueError(
            "scenario_id nie może być pusty"
        )

    _validate_comparison_inputs(
        greedy_schedule=greedy_schedule,
        cp_sat_schedule=cp_sat_schedule,
        greedy_analysis=greedy_analysis,
        cp_sat_analysis=cp_sat_analysis,
    )

    greedy_snapshot = _build_snapshot(
        schedule=greedy_schedule,
        analysis=greedy_analysis,
        solver_status="NOT_APPLICABLE",
    )

    cp_sat_snapshot = _build_snapshot(
        schedule=cp_sat_schedule,
        analysis=cp_sat_analysis,
        solver_status=(
            cp_sat_solver_status
            or extract_solver_status(
                cp_sat_schedule.notes
            )
            or "UNKNOWN"
        ),
    )

    return PlannerComparison(
        scenario_id=normalized_scenario_id,
        greedy=greedy_snapshot,
        cp_sat=cp_sat_snapshot,
    )


def export_planner_comparison(
    comparison: PlannerComparison,
    output_directory: str | Path,
    *,
    prefix: str = "stress_comparison",
) -> dict[str, Path]:
    """Eksportuje CSV oraz trzy wykresy PNG."""

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
        "comparison_csv": (
            directory
            / f"{normalized_prefix}.csv"
        ),
        "objective_chart": (
            directory
            / f"{normalized_prefix}_objective.png"
        ),
        "fulfilled_chart": (
            directory
            / (
                f"{normalized_prefix}"
                "_fulfilled_requests.png"
            )
        ),
        "runtime_chart": (
            directory
            / f"{normalized_prefix}_runtime.png"
        ),
    }

    _write_comparison_csv(
        comparison=comparison,
        path=paths["comparison_csv"],
    )

    _save_bar_chart(
        labels=[
            comparison.greedy.algorithm,
            comparison.cp_sat.algorithm,
        ],
        values=[
            comparison.greedy.objective_value,
            comparison.cp_sat.objective_value,
        ],
        title="Wartość funkcji celu",
        y_label="Punkty funkcji celu",
        path=paths["objective_chart"],
    )

    _save_bar_chart(
        labels=[
            comparison.greedy.algorithm,
            comparison.cp_sat.algorithm,
        ],
        values=[
            float(
                comparison
                .greedy
                .fully_satisfied_requests
            ),
            float(
                comparison
                .cp_sat
                .fully_satisfied_requests
            ),
        ],
        title="Liczba w pełni zrealizowanych zleceń",
        y_label="Liczba zleceń",
        path=paths["fulfilled_chart"],
    )

    runtime_values = [
        comparison.greedy.solver_runtime_s,
        comparison.cp_sat.solver_runtime_s,
    ]

    use_log_scale = all(
        value > 0.0
        for value in runtime_values
    )

    _save_bar_chart(
        labels=[
            comparison.greedy.algorithm,
            comparison.cp_sat.algorithm,
        ],
        values=runtime_values,
        title="Czas działania algorytmu",
        y_label="Czas [s]",
        path=paths["runtime_chart"],
        log_scale=use_log_scale,
    )

    return paths


def extract_solver_status(
    notes: str | None,
) -> str | None:
    """Odczytuje status CP-SAT zapisany w polu notes."""

    if not notes:
        return None

    match = re.search(
        r"Status solvera:\s*([A-Z_]+)",
        notes,
    )

    if match is None:
        return None

    return match.group(1)


def _build_snapshot(
    *,
    schedule: Schedule,
    analysis: ScheduleAnalysis,
    solver_status: str,
) -> PlannerSnapshot:
    return PlannerSnapshot(
        algorithm=schedule.algorithm.value,
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
        solver_runtime_s=float(
            schedule.solver_runtime_s
            or 0.0
        ),
    )


def _validate_comparison_inputs(
    *,
    greedy_schedule: Schedule,
    cp_sat_schedule: Schedule,
    greedy_analysis: ScheduleAnalysis,
    cp_sat_analysis: ScheduleAnalysis,
) -> None:
    if (
        greedy_schedule.horizon_start_utc
        != cp_sat_schedule.horizon_start_utc
        or greedy_schedule.horizon_end_utc
        != cp_sat_schedule.horizon_end_utc
    ):
        raise ValueError(
            "Porównywane harmonogramy mają różne horyzonty"
        )

    if (
        greedy_analysis.schedule_id
        != greedy_schedule.schedule_id
    ):
        raise ValueError(
            "Analiza Greedy nie odpowiada harmonogramowi Greedy"
        )

    if (
        cp_sat_analysis.schedule_id
        != cp_sat_schedule.schedule_id
    ):
        raise ValueError(
            "Analiza CP-SAT nie odpowiada harmonogramowi CP-SAT"
        )

    if (
        greedy_analysis.total_active_requests
        != cp_sat_analysis.total_active_requests
    ):
        raise ValueError(
            "Analizy dotyczą różnej liczby aktywnych zleceń"
        )


def _write_comparison_csv(
    *,
    comparison: PlannerComparison,
    path: Path,
) -> None:
    with path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=COMPARISON_FIELDNAMES,
        )

        writer.writeheader()
        writer.writerows(
            comparison.csv_rows()
        )


def _save_bar_chart(
    *,
    labels: list[str],
    values: list[float],
    title: str,
    y_label: str,
    path: Path,
    log_scale: bool = False,
) -> None:
    figure, axis = plt.subplots(
        figsize=(7.0, 4.5)
    )

    bars = axis.bar(
        labels,
        values,
    )

    axis.set_title(
        title
    )

    axis.set_ylabel(
        y_label
    )

    axis.grid(
        axis="y",
        alpha=0.3,
    )

    if log_scale:
        axis.set_yscale(
            "log"
        )

    for bar, value in zip(
        bars,
        values,
        strict=True,
    ):
        axis.annotate(
            _format_chart_value(value),
            xy=(
                bar.get_x()
                + bar.get_width() / 2.0,
                bar.get_height(),
            ),
            xytext=(0, 4),
            textcoords="offset points",
            ha="center",
            va="bottom",
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


def _format_chart_value(
    value: float,
) -> str:
    absolute_value = abs(value)

    if absolute_value >= 1000.0:
        return f"{value:.2f}"

    if absolute_value >= 10.0:
        return f"{value:.2f}"

    if absolute_value >= 1.0:
        return f"{value:.3f}"

    return f"{value:.6f}"