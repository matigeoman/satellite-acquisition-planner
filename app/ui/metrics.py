from __future__ import annotations

import json
import re
from dataclasses import dataclass

from app.services.planning_service import (
    PlanningResult,
)


@dataclass(frozen=True)
class PlanningMetrics:
    """Najważniejsze KPI prezentowane w interfejsie."""

    scenario_id: str
    scenario_name: str

    algorithm: str
    schedule_status: str
    solver_status: str

    objective_value: float

    total_active_requests: int
    fully_satisfied_requests: int
    partially_satisfied_requests: int
    unassigned_requests: int

    mandatory_requests: int
    mandatory_satisfied_requests: int

    total_acquisitions: int
    sar_acquisitions: int
    optical_acquisitions: int

    satisfaction_ratio: float
    mandatory_satisfaction_ratio: float

    solver_runtime_s: float
    wall_clock_runtime_s: float


def build_planning_metrics(
    result: PlanningResult,
) -> PlanningMetrics:
    """Buduje zestaw KPI z wyniku planowania."""

    mandatory_requests = (
        result.analysis.mandatory_requests
    )

    mandatory_satisfied_requests = (
        result
        .analysis
        .mandatory_satisfied_requests
    )

    if mandatory_requests > 0:
        mandatory_satisfaction_ratio = (
            mandatory_satisfied_requests
            / mandatory_requests
        )
    else:
        mandatory_satisfaction_ratio = 1.0

    return PlanningMetrics(
        scenario_id=result.scenario.scenario_id,
        scenario_name=result.scenario.name,
        algorithm=result.algorithm.value,
        schedule_status=(
            result.schedule.status.value
        ),
        solver_status=result.solver_status,
        objective_value=result.objective_value,
        total_active_requests=(
            result.analysis.total_active_requests
        ),
        fully_satisfied_requests=(
            result
            .analysis
            .fully_satisfied_requests
        ),
        partially_satisfied_requests=(
            result
            .analysis
            .partially_satisfied_requests
        ),
        unassigned_requests=(
            result.analysis.unassigned_requests
        ),
        mandatory_requests=mandatory_requests,
        mandatory_satisfied_requests=(
            mandatory_satisfied_requests
        ),
        total_acquisitions=(
            result.analysis.total_acquisitions
        ),
        sar_acquisitions=(
            result.analysis.sar_acquisitions
        ),
        optical_acquisitions=(
            result.analysis.optical_acquisitions
        ),
        satisfaction_ratio=(
            result.analysis.satisfaction_ratio
        ),
        mandatory_satisfaction_ratio=(
            mandatory_satisfaction_ratio
        ),
        solver_runtime_s=float(
            result.schedule.solver_runtime_s
            or 0.0
        ),
        wall_clock_runtime_s=(
            result.wall_clock_runtime_s
        ),
    )


def build_schedule_json(
    result: PlanningResult,
    *,
    indent: int = 2,
) -> str:
    """Serializuje harmonogram do czytelnego JSON."""

    if indent < 0:
        raise ValueError(
            "indent nie może być ujemny"
        )

    return (
        json.dumps(
            result.schedule.model_dump(
                mode="json"
            ),
            ensure_ascii=False,
            indent=indent,
        )
        + "\n"
    )


def build_schedule_download_filename(
    result: PlanningResult,
) -> str:
    """Buduje bezpieczną nazwę pliku harmonogramu."""

    normalized = re.sub(
        r"[^a-z0-9]+",
        "_",
        result.schedule.schedule_id.lower(),
    ).strip("_")

    if not normalized:
        normalized = "schedule"

    return f"{normalized}.json"


def format_percent(
    value: float,
    *,
    digits: int = 1,
) -> str:
    """Formatuje współczynnik 0–1 jako wartość procentową."""

    if digits < 0:
        raise ValueError(
            "digits nie może być ujemne"
        )

    return f"{value * 100.0:.{digits}f}%"