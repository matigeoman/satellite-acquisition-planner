from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from time import perf_counter

from app.models.enums import PlanningAlgorithm
from app.services.contracts.comparison import PlanningComparisonResult
from app.services.contracts.planning import PlanningOptions
from app.services.planning_service import PlanningService
from app.services.scenario_service import LoadedScenario

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


__all__ = ["PlanningComparisonResult", "PlanningComparisonService"]
