from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.models.enums import ScheduleEntryStatus
from app.models.schedule import Schedule
from app.planning.fixed import FixedOpportunityAssignment
from app.services.contracts.planning import PlanningResult

@dataclass(frozen=True)
class ReplanningResult:
    """Wynik dynamicznego przeplanowania harmonogramu."""

    previous_schedule: Schedule
    planning_result: PlanningResult

    replan_at_utc: datetime
    frozen_until_utc: datetime

    fixed_assignments: tuple[
        FixedOpportunityAssignment,
        ...,
    ]

    def __post_init__(self) -> None:
        for field_name, value in {
            "replan_at_utc": self.replan_at_utc,
            "frozen_until_utc": self.frozen_until_utc,
        }.items():
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(
                    f"{field_name} musi zawierać strefę czasową"
                )

        if self.frozen_until_utc < self.replan_at_utc:
            raise ValueError(
                "frozen_until_utc nie może być wcześniejsze "
                "niż replan_at_utc"
            )

        if (
            self.schedule.frozen_until_utc
            != self.frozen_until_utc
        ):
            raise ValueError(
                "Harmonogram wynikowy ma niezgodną granicę "
                "okna zamrożonego"
            )

        fixed_ids = {
            assignment.opportunity_id
            for assignment in self.fixed_assignments
        }

        result_ids = {
            entry.opportunity_id
            for entry in self.schedule.active_entries
        }

        missing_fixed_ids = fixed_ids - result_ids

        if missing_fixed_ids:
            raise ValueError(
                "Harmonogram wynikowy nie zachował stałych okazji: "
                + ", ".join(sorted(missing_fixed_ids))
            )

    @property
    def schedule(self) -> Schedule:
        return self.planning_result.schedule

    @property
    def analysis(self):
        return self.planning_result.analysis

    @property
    def solver_status(self) -> str:
        return self.planning_result.solver_status

    @property
    def executed_count(self) -> int:
        return sum(
            assignment.status
            == ScheduleEntryStatus.EXECUTED
            for assignment in self.fixed_assignments
        )

    @property
    def frozen_count(self) -> int:
        return sum(
            assignment.status
            == ScheduleEntryStatus.FROZEN
            for assignment in self.fixed_assignments
        )

    @property
    def fixed_count(self) -> int:
        return len(self.fixed_assignments)

    @property
    def previous_replannable_opportunity_ids(
        self,
    ) -> set[str]:
        return {
            entry.opportunity_id
            for entry in self.previous_schedule.active_entries
            if entry.start_utc >= self.frozen_until_utc
        }

    @property
    def new_replannable_opportunity_ids(
        self,
    ) -> set[str]:
        return {
            entry.opportunity_id
            for entry in self.schedule.active_entries
            if entry.start_utc >= self.frozen_until_utc
        }

    @property
    def added_opportunity_ids(self) -> list[str]:
        return sorted(
            self.new_replannable_opportunity_ids
            - self.previous_replannable_opportunity_ids
        )

    @property
    def removed_opportunity_ids(self) -> list[str]:
        return sorted(
            self.previous_replannable_opportunity_ids
            - self.new_replannable_opportunity_ids
        )

    @property
    def unchanged_replannable_opportunity_ids(
        self,
    ) -> list[str]:
        return sorted(
            self.previous_replannable_opportunity_ids
            & self.new_replannable_opportunity_ids
        )
