from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from time import perf_counter

from app.models.enums import PlanningAlgorithm
from app.services.planning_service import (
    PlanningOptions,
    PlanningResult,
    PlanningService,
)
from app.services.scenario_service import LoadedScenario


@dataclass(frozen=True)
class PlanningComparisonResult:
    """Wyniki Greedy i CP-SAT dla tego samego scenariusza."""

    scenario: LoadedScenario
    greedy: PlanningResult
    cp_sat: PlanningResult
    started_at_utc: datetime
    completed_at_utc: datetime
    wall_clock_runtime_s: float

    def __post_init__(self) -> None:
        if self.greedy.algorithm != PlanningAlgorithm.GREEDY:
            raise ValueError(
                "Pole greedy musi zawierać wynik algorytmu GREEDY"
            )

        if self.cp_sat.algorithm != PlanningAlgorithm.CP_SAT:
            raise ValueError(
                "Pole cp_sat musi zawierać wynik algorytmu CP_SAT"
            )

        if (
            self.greedy.scenario.scenario_id
            != self.scenario.scenario_id
            or self.cp_sat.scenario.scenario_id
            != self.scenario.scenario_id
        ):
            raise ValueError(
                "Oba wyniki muszą dotyczyć tego samego scenariusza"
            )

        if (
            self.greedy.schedule.horizon_start_utc
            != self.cp_sat.schedule.horizon_start_utc
            or self.greedy.schedule.horizon_end_utc
            != self.cp_sat.schedule.horizon_end_utc
        ):
            raise ValueError(
                "Porównywane harmonogramy muszą mieć ten sam horyzont"
            )

        if (
            self.started_at_utc.tzinfo is None
            or self.started_at_utc.utcoffset() is None
            or self.completed_at_utc.tzinfo is None
            or self.completed_at_utc.utcoffset() is None
        ):
            raise ValueError(
                "Znaczniki czasu porównania muszą zawierać strefę czasową"
            )

        if self.completed_at_utc < self.started_at_utc:
            raise ValueError(
                "completed_at_utc nie może być wcześniejsze od started_at_utc"
            )

        if self.wall_clock_runtime_s < 0.0:
            raise ValueError(
                "wall_clock_runtime_s nie może być ujemny"
            )

    @property
    def objective_difference(self) -> float:
        return round(
            self.cp_sat.objective_value
            - self.greedy.objective_value,
            6,
        )

    @property
    def objective_improvement_ratio(self) -> float:
        if self.greedy.objective_value <= 0.0:
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
    def fully_satisfied_difference(self) -> int:
        return (
            self.cp_sat.fully_satisfied_requests
            - self.greedy.fully_satisfied_requests
        )

    @property
    def unassigned_reduction(self) -> int:
        return (
            self.greedy.unassigned_requests
            - self.cp_sat.unassigned_requests
        )

    @property
    def acquisition_difference(self) -> int:
        return (
            self.cp_sat.total_acquisitions
            - self.greedy.total_acquisitions
        )

    @property
    def runtime_ratio(self) -> float | None:
        greedy_runtime = self.greedy.wall_clock_runtime_s

        if greedy_runtime <= 0.0:
            return None

        return (
            self.cp_sat.wall_clock_runtime_s
            / greedy_runtime
        )


class PlanningComparisonService:
    """Uruchamia Greedy i CP-SAT z tymi samymi parametrami celu."""

    def __init__(
        self,
        *,
        planning_service: PlanningService | None = None,
    ) -> None:
        self.planning_service = (
            planning_service
            if planning_service is not None
            else PlanningService()
        )

    def run(
        self,
        *,
        scenario: LoadedScenario,
        options: PlanningOptions,
        created_at_utc: datetime | None = None,
    ) -> PlanningComparisonResult:
        created_at = _normalize_datetime(
            created_at_utc
        )

        started_at = datetime.now(
            timezone.utc
        )

        timer_start = perf_counter()

        greedy_options = replace(
            options,
            algorithm=PlanningAlgorithm.GREEDY,
        )

        cp_sat_options = replace(
            options,
            algorithm=PlanningAlgorithm.CP_SAT,
        )

        greedy_result = self.planning_service.run(
            scenario=scenario,
            options=greedy_options,
            schedule_id=_build_comparison_schedule_id(
                scenario=scenario,
                algorithm=PlanningAlgorithm.GREEDY,
            ),
            schedule_name=(
                f"{scenario.name} — porównanie Greedy"
            ),
            created_at_utc=created_at,
        )

        cp_sat_result = self.planning_service.run(
            scenario=scenario,
            options=cp_sat_options,
            schedule_id=_build_comparison_schedule_id(
                scenario=scenario,
                algorithm=PlanningAlgorithm.CP_SAT,
            ),
            schedule_name=(
                f"{scenario.name} — porównanie CP-SAT"
            ),
            created_at_utc=created_at,
        )

        wall_clock_runtime_s = round(
            perf_counter() - timer_start,
            6,
        )

        completed_at = datetime.now(
            timezone.utc
        )

        return PlanningComparisonResult(
            scenario=scenario,
            greedy=greedy_result,
            cp_sat=cp_sat_result,
            started_at_utc=started_at,
            completed_at_utc=completed_at,
            wall_clock_runtime_s=wall_clock_runtime_s,
        )


def _build_comparison_schedule_id(
    *,
    scenario: LoadedScenario,
    algorithm: PlanningAlgorithm,
) -> str:
    standard_id = PlanningService.build_schedule_id(
        scenario_id=scenario.scenario_id,
        algorithm=algorithm,
    )

    return standard_id.replace(
        "SCHEDULE-",
        "SCHEDULE-COMPARE-",
        1,
    )


def _normalize_datetime(
    value: datetime | None,
) -> datetime:
    if value is None:
        return datetime.now(
            timezone.utc
        )

    if (
        value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(
            "created_at_utc musi zawierać strefę czasową"
        )

    return value.astimezone(
        timezone.utc
    )
