from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.models.enums import PlanningAlgorithm
from app.services.contracts.planning import PlanningResult
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
