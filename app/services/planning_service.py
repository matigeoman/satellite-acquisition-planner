from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from time import perf_counter
from typing import Iterable

from app.analysis.schedule_report import (
    ScheduleAnalysis,
    analyze_schedule,
)
from app.models.enums import PlanningAlgorithm
from app.models.schedule import Schedule
from app.planning.cp_sat import (
    CpSatPlannerConfig,
    CpSatScheduler,
)
from app.planning.fixed import FixedOpportunityAssignment
from app.planning.greedy import (
    GreedyPlannerConfig,
    build_greedy_schedule,
)
from app.services.scenario_service import (
    LoadedScenario,
)


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


class PlanningService:
    """Uruchamia wybrany algorytm i analizuje jego wynik."""

    def run(
        self,
        *,
        scenario: LoadedScenario,
        options: PlanningOptions,
        schedule_id: str | None = None,
        schedule_name: str | None = None,
        created_at_utc: datetime | None = None,
        fixed_assignments: Iterable[
            FixedOpportunityAssignment
        ] | None = None,
        frozen_until_utc: datetime | None = None,
    ) -> PlanningResult:
        created_at = self._normalize_created_at(
            created_at_utc
        )
        normalized_frozen_until = (
            self._normalize_optional_utc(
                frozen_until_utc,
                field_name="frozen_until_utc",
            )
        )
        normalized_fixed_assignments = tuple(
            fixed_assignments or ()
        )

        resolved_schedule_id = (
            schedule_id
            or self.build_schedule_id(
                scenario_id=scenario.scenario_id,
                algorithm=options.algorithm,
            )
        )

        resolved_schedule_name = (
            schedule_name
            or self.build_schedule_name(
                scenario_name=scenario.name,
                algorithm=options.algorithm,
            )
        )

        started_at = datetime.now(
            timezone.utc
        )

        timer_start = perf_counter()

        if (
            options.algorithm
            == PlanningAlgorithm.GREEDY
        ):
            schedule = self._run_greedy(
                scenario=scenario,
                options=options,
                schedule_id=resolved_schedule_id,
                schedule_name=resolved_schedule_name,
                created_at_utc=created_at,
                fixed_assignments=(
                    normalized_fixed_assignments
                ),
                frozen_until_utc=(
                    normalized_frozen_until
                ),
            )

            solver_status = (
                "NOT_APPLICABLE"
            )

        elif (
            options.algorithm
            == PlanningAlgorithm.CP_SAT
        ):
            (
                schedule,
                solver_status,
            ) = self._run_cp_sat(
                scenario=scenario,
                options=options,
                schedule_id=resolved_schedule_id,
                schedule_name=resolved_schedule_name,
                created_at_utc=created_at,
                fixed_assignments=(
                    normalized_fixed_assignments
                ),
                frozen_until_utc=(
                    normalized_frozen_until
                ),
            )

        else:
            raise ValueError(
                "Nieobsługiwany algorytm: "
                f"{options.algorithm}"
            )

        wall_clock_runtime_s = round(
            perf_counter() - timer_start,
            6,
        )

        completed_at = datetime.now(
            timezone.utc
        )

        analysis = analyze_schedule(
            catalog=scenario.catalog,
            request_set=scenario.request_set,
            opportunity_set=(
                scenario.opportunity_set
            ),
            schedule=schedule,
        )

        return PlanningResult(
            scenario=scenario,
            options=options,
            schedule=schedule,
            analysis=analysis,
            solver_status=solver_status,
            started_at_utc=started_at,
            completed_at_utc=completed_at,
            wall_clock_runtime_s=(
                wall_clock_runtime_s
            ),
        )

    def _run_greedy(
        self,
        *,
        scenario: LoadedScenario,
        options: PlanningOptions,
        schedule_id: str,
        schedule_name: str,
        created_at_utc: datetime,
        fixed_assignments: tuple[
            FixedOpportunityAssignment, ...
        ],
        frozen_until_utc: datetime | None,
    ) -> Schedule:
        config = GreedyPlannerConfig(
            memory_reserve_ratio=(
                options.memory_reserve_ratio
            ),
            priority_weight=(
                options.priority_weight
            ),
            quality_weight=(
                options.quality_weight
            ),
            coverage_weight=(
                options.coverage_weight
            ),
            mandatory_bonus=(
                options.mandatory_bonus
            ),
            dual_optional_second_bonus=(
                options.dual_optional_second_bonus
            ),
        )

        return build_greedy_schedule(
            catalog=scenario.catalog,
            request_set=scenario.request_set,
            opportunity_set=(
                scenario.opportunity_set
            ),
            config=config,
            schedule_id=schedule_id,
            name=schedule_name,
            created_at_utc=created_at_utc,
            fixed_assignments=fixed_assignments,
            frozen_until_utc=frozen_until_utc,
        )

    def _run_cp_sat(
        self,
        *,
        scenario: LoadedScenario,
        options: PlanningOptions,
        schedule_id: str,
        schedule_name: str,
        created_at_utc: datetime,
        fixed_assignments: tuple[
            FixedOpportunityAssignment, ...
        ],
        frozen_until_utc: datetime | None,
    ) -> tuple[Schedule, str]:
        config = CpSatPlannerConfig(
            memory_reserve_ratio=(
                options.memory_reserve_ratio
            ),
            priority_weight=(
                options.priority_weight
            ),
            quality_weight=(
                options.quality_weight
            ),
            coverage_weight=(
                options.coverage_weight
            ),
            mandatory_bonus=(
                options.mandatory_bonus
            ),
            dual_optional_second_bonus=(
                options.dual_optional_second_bonus
            ),
            force_mandatory_requests=(
                options
                .cp_sat_force_mandatory_requests
            ),
            max_time_s=(
                options.cp_sat_time_limit_s
            ),
            num_search_workers=(
                options
                .cp_sat_num_search_workers
            ),
            random_seed=(
                options.cp_sat_random_seed
            ),
            log_search_progress=(
                options
                .cp_sat_log_search_progress
            ),
        )

        scheduler = CpSatScheduler(
            catalog=scenario.catalog,
            request_set=scenario.request_set,
            opportunity_set=(
                scenario.opportunity_set
            ),
            config=config,
            fixed_assignments=fixed_assignments,
            frozen_until_utc=frozen_until_utc,
        )

        schedule = scheduler.build_schedule(
            schedule_id=schedule_id,
            name=schedule_name,
            created_at_utc=created_at_utc,
        )

        return (
            schedule,
            scheduler.last_solver_status
            or "UNKNOWN",
        )

    @staticmethod
    def build_schedule_id(
        *,
        scenario_id: str,
        algorithm: PlanningAlgorithm,
    ) -> str:
        normalized_scenario = re.sub(
            r"[^A-Z0-9-]+",
            "-",
            scenario_id.strip().upper(),
        ).strip("-")

        if not normalized_scenario:
            raise ValueError(
                "scenario_id nie może być pusty"
            )

        normalized_algorithm = re.sub(
            r"[^A-Z0-9-]+",
            "-",
            algorithm.value.strip().upper(),
        ).strip("-")

        if not normalized_algorithm:
            raise ValueError(
                "algorithm nie może tworzyć "
                "pustego identyfikatora"
            )

        return (
            f"SCHEDULE-{normalized_scenario}-"
            f"{normalized_algorithm}"
        )

    @staticmethod
    def build_schedule_name(
        *,
        scenario_name: str,
        algorithm: PlanningAlgorithm,
    ) -> str:
        normalized_name = (
            scenario_name.strip()
        )

        if not normalized_name:
            raise ValueError(
                "scenario_name nie może być pusta"
            )

        algorithm_label = (
            algorithm.value
            .replace("_", "-")
        )

        return (
            f"{normalized_name} — "
            f"{algorithm_label}"
        )

    @staticmethod
    def _normalize_optional_utc(
        value: datetime | None,
        *,
        field_name: str,
    ) -> datetime | None:
        if value is None:
            return None

        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(
                f"{field_name} musi zawierać strefę czasową"
            )

        return value.astimezone(
            timezone.utc
        )

    @staticmethod
    def _normalize_created_at(
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
                "created_at_utc musi zawierać "
                "strefę czasową"
            )

        return value.astimezone(
            timezone.utc
        )