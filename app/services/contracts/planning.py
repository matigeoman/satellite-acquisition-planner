from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.analysis.schedule import ScheduleAnalysis
from app.models.enums import PlanningAlgorithm
from app.models.schedule import Schedule
from app.services.scenario_service import LoadedScenario

@dataclass(frozen=True)
class PlanningOptions:
    """Parametry wspólnego interfejsu planowania."""

    algorithm: PlanningAlgorithm = (
        PlanningAlgorithm.GREEDY
    )

    memory_reserve_ratio: float = 0.15

    priority_weight: float = 10.0
    quality_weight: float = 3.0
    coverage_weight: float = 2.0
    mandatory_bonus: float = 100.0
    dual_optional_second_bonus: float = 5.0

    cp_sat_time_limit_s: float = 10.0
    cp_sat_num_search_workers: int = 1
    cp_sat_random_seed: int = 20260716
    cp_sat_force_mandatory_requests: bool = True
    cp_sat_log_search_progress: bool = False

    def __post_init__(self) -> None:
        algorithm = self.algorithm

        if isinstance(
            algorithm,
            str,
        ):
            try:
                algorithm = PlanningAlgorithm(
                    algorithm.strip().upper()
                )
            except ValueError as error:
                raise ValueError(
                    "Nieobsługiwany algorytm: "
                    f"{self.algorithm}"
                ) from error

            object.__setattr__(
                self,
                "algorithm",
                algorithm,
            )

        if not isinstance(
            algorithm,
            PlanningAlgorithm,
        ):
            raise TypeError(
                "algorithm musi być wartością "
                "PlanningAlgorithm"
            )

        if algorithm not in {
            PlanningAlgorithm.GREEDY,
            PlanningAlgorithm.CP_SAT,
        }:
            raise ValueError(
                "PlanningService obsługuje wyłącznie "
                "GREEDY i CP_SAT"
            )

        if not 0.0 <= self.memory_reserve_ratio <= 1.0:
            raise ValueError(
                "memory_reserve_ratio musi należeć "
                "do zakresu [0, 1]"
            )

        nonnegative_values = {
            "priority_weight": self.priority_weight,
            "quality_weight": self.quality_weight,
            "coverage_weight": self.coverage_weight,
            "mandatory_bonus": self.mandatory_bonus,
            "dual_optional_second_bonus": (
                self.dual_optional_second_bonus
            ),
        }

        for name, value in nonnegative_values.items():
            if value < 0.0:
                raise ValueError(
                    f"{name} nie może być ujemne"
                )

        if self.cp_sat_time_limit_s <= 0.0:
            raise ValueError(
                "cp_sat_time_limit_s musi być "
                "większe od zera"
            )

        if self.cp_sat_num_search_workers <= 0:
            raise ValueError(
                "cp_sat_num_search_workers musi być "
                "większe od zera"
            )

        if self.cp_sat_random_seed < 0:
            raise ValueError(
                "cp_sat_random_seed nie może być ujemny"
            )


@dataclass(frozen=True)
class PlanningResult:
    """Kompletny wynik uruchomienia planera."""

    scenario: LoadedScenario
    options: PlanningOptions

    schedule: Schedule
    analysis: ScheduleAnalysis

    solver_status: str

    started_at_utc: datetime
    completed_at_utc: datetime
    wall_clock_runtime_s: float

    def __post_init__(self) -> None:
        if (
            self.started_at_utc.tzinfo is None
            or self.started_at_utc.utcoffset()
            is None
        ):
            raise ValueError(
                "started_at_utc musi zawierać "
                "strefę czasową"
            )

        if (
            self.completed_at_utc.tzinfo is None
            or self.completed_at_utc.utcoffset()
            is None
        ):
            raise ValueError(
                "completed_at_utc musi zawierać "
                "strefę czasową"
            )

        if (
            self.completed_at_utc
            < self.started_at_utc
        ):
            raise ValueError(
                "completed_at_utc nie może być "
                "wcześniejsze niż started_at_utc"
            )

        if self.wall_clock_runtime_s < 0.0:
            raise ValueError(
                "wall_clock_runtime_s nie może być ujemny"
            )

        if (
            self.analysis.schedule_id
            != self.schedule.schedule_id
        ):
            raise ValueError(
                "Analiza nie odpowiada harmonogramowi"
            )

    @property
    def algorithm(self) -> PlanningAlgorithm:
        return self.schedule.algorithm

    @property
    def objective_value(self) -> float:
        return float(
            self.schedule.objective_value
            or 0.0
        )

    @property
    def fully_satisfied_requests(self) -> int:
        return (
            self.analysis.fully_satisfied_requests
        )

    @property
    def unassigned_requests(self) -> int:
        return (
            self.analysis.unassigned_requests
        )

    @property
    def total_acquisitions(self) -> int:
        return (
            self.analysis.total_acquisitions
        )
