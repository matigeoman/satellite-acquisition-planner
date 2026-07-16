from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from app.models.enums import ScheduleEntryStatus
from app.models.opportunity import AcquisitionOpportunity
from app.models.schedule import Schedule, ScheduleEntry
from app.planning.fixed import FixedOpportunityAssignment
from app.services.contracts.planning import PlanningOptions
from app.services.contracts.replanning import ReplanningResult
from app.services.planning_service import PlanningService
from app.services.scenario_service import LoadedScenario


DEFAULT_FREEZE_DURATION = timedelta(hours=2)
DEFAULT_FREEZE_REASON = (
    "Akwizycja znajduje się w operacyjnym oknie zamrożonym "
    "podczas przeplanowania."
)


class ReplanningService:
    """Zamraża bliski okres i ponownie planuje resztę horyzontu."""

    def __init__(
        self,
        planning_service: PlanningService | None = None,
    ) -> None:
        self.planning_service = (
            planning_service
            or PlanningService()
        )

    def run(
        self,
        *,
        scenario: LoadedScenario,
        previous_schedule: Schedule,
        options: PlanningOptions,
        replan_at_utc: datetime,
        freeze_duration: timedelta = DEFAULT_FREEZE_DURATION,
        schedule_id: str | None = None,
        schedule_name: str | None = None,
    ) -> ReplanningResult:
        replan_at = self._normalize_utc(
            replan_at_utc,
            field_name="replan_at_utc",
        )

        self._validate_freeze_duration(
            freeze_duration
        )
        self._validate_schedule_horizon(
            scenario=scenario,
            previous_schedule=previous_schedule,
        )
        self._validate_replan_time(
            scenario=scenario,
            replan_at_utc=replan_at,
        )

        frozen_until = min(
            replan_at + freeze_duration,
            scenario.request_set.horizon_end_utc,
        )

        opportunities_by_id = {
            opportunity.opportunity_id: opportunity
            for opportunity
            in scenario.opportunity_set.opportunities
        }

        self._validate_schedule_entries(
            previous_schedule=previous_schedule,
            opportunities_by_id=opportunities_by_id,
        )

        fixed_assignments = self._build_fixed_assignments(
            previous_schedule=previous_schedule,
            replan_at_utc=replan_at,
            frozen_until_utc=frozen_until,
        )

        resolved_schedule_id = (
            schedule_id
            or self._build_replanned_schedule_id(
                scenario_id=scenario.scenario_id,
                algorithm=options.algorithm.value,
                replan_at_utc=replan_at,
            )
        )

        resolved_schedule_name = (
            schedule_name
            or (
                f"{scenario.name} — przeplanowanie "
                f"{options.algorithm.value.replace('_', '-')}"
            )
        )

        planning_result = self.planning_service.run(
            scenario=scenario,
            options=options,
            schedule_id=resolved_schedule_id,
            schedule_name=resolved_schedule_name,
            created_at_utc=replan_at,
            fixed_assignments=fixed_assignments,
            frozen_until_utc=frozen_until,
        )

        return ReplanningResult(
            previous_schedule=previous_schedule,
            planning_result=planning_result,
            replan_at_utc=replan_at,
            frozen_until_utc=frozen_until,
            fixed_assignments=fixed_assignments,
        )

    @staticmethod
    def _validate_freeze_duration(
        freeze_duration: timedelta,
    ) -> None:
        if not isinstance(
            freeze_duration,
            timedelta,
        ):
            raise TypeError(
                "freeze_duration musi być wartością timedelta"
            )

        if freeze_duration <= timedelta(0):
            raise ValueError(
                "freeze_duration musi być większe od zera"
            )

    @staticmethod
    def _validate_schedule_horizon(
        *,
        scenario: LoadedScenario,
        previous_schedule: Schedule,
    ) -> None:
        if (
            previous_schedule.horizon_start_utc
            != scenario.request_set.horizon_start_utc
            or previous_schedule.horizon_end_utc
            != scenario.request_set.horizon_end_utc
        ):
            raise ValueError(
                "Poprzedni harmonogram i scenariusz mają "
                "różne horyzonty planowania"
            )

    @staticmethod
    def _validate_replan_time(
        *,
        scenario: LoadedScenario,
        replan_at_utc: datetime,
    ) -> None:
        if not (
            scenario.request_set.horizon_start_utc
            <= replan_at_utc
            < scenario.request_set.horizon_end_utc
        ):
            raise ValueError(
                "replan_at_utc musi znajdować się wewnątrz "
                "horyzontu planowania"
            )

    def _validate_schedule_entries(
        self,
        *,
        previous_schedule: Schedule,
        opportunities_by_id: dict[
            str,
            AcquisitionOpportunity,
        ],
    ) -> None:
        for entry in previous_schedule.active_entries:
            opportunity = opportunities_by_id.get(
                entry.opportunity_id
            )

            if opportunity is None:
                raise ValueError(
                    "Wpis poprzedniego harmonogramu odwołuje się "
                    "do nieznanej okazji: "
                    f"{entry.opportunity_id}"
                )

            self._validate_entry_against_opportunity(
                entry=entry,
                opportunity=opportunity,
            )

    @staticmethod
    def _validate_entry_against_opportunity(
        *,
        entry: ScheduleEntry,
        opportunity: AcquisitionOpportunity,
    ) -> None:
        comparable_fields = {
            "request_id": (
                entry.request_id,
                opportunity.request_id,
            ),
            "satellite_id": (
                entry.satellite_id,
                opportunity.satellite_id,
            ),
            "sensor_id": (
                entry.sensor_id,
                opportunity.sensor_id,
            ),
            "mode_id": (
                entry.mode_id,
                opportunity.mode_id,
            ),
            "sensor_type": (
                entry.sensor_type,
                opportunity.sensor_type,
            ),
            "start_utc": (
                entry.start_utc,
                opportunity.start_utc,
            ),
            "end_utc": (
                entry.end_utc,
                opportunity.end_utc,
            ),
        }

        for field_name, (
            entry_value,
            opportunity_value,
        ) in comparable_fields.items():
            if entry_value != opportunity_value:
                raise ValueError(
                    f"Wpis {entry.entry_id} jest niezgodny "
                    f"z okazją w polu {field_name}"
                )

        if abs(
            entry.estimated_data_volume_mb
            - opportunity.estimated_data_volume_mb
        ) > 1e-6:
            raise ValueError(
                f"Wpis {entry.entry_id} ma niezgodną "
                "estimated_data_volume_mb"
            )

    @staticmethod
    def _build_fixed_assignments(
        *,
        previous_schedule: Schedule,
        replan_at_utc: datetime,
        frozen_until_utc: datetime,
    ) -> tuple[
        FixedOpportunityAssignment,
        ...,
    ]:
        assignments: list[
            FixedOpportunityAssignment
        ] = []

        for entry in sorted(
            previous_schedule.active_entries,
            key=lambda item: (
                item.start_utc,
                item.opportunity_id,
            ),
        ):
            if entry.start_utc >= frozen_until_utc:
                continue

            if entry.end_utc <= replan_at_utc:
                assignment = FixedOpportunityAssignment(
                    opportunity_id=entry.opportunity_id,
                    status=ScheduleEntryStatus.EXECUTED,
                    lock_reason=None,
                )
            else:
                assignment = FixedOpportunityAssignment(
                    opportunity_id=entry.opportunity_id,
                    status=ScheduleEntryStatus.FROZEN,
                    lock_reason=DEFAULT_FREEZE_REASON,
                )

            assignments.append(
                assignment
            )

        return tuple(assignments)

    @staticmethod
    def _build_replanned_schedule_id(
        *,
        scenario_id: str,
        algorithm: str,
        replan_at_utc: datetime,
    ) -> str:
        normalized_scenario = re.sub(
            r"[^A-Z0-9-]+",
            "-",
            scenario_id.strip().upper(),
        ).strip("-")

        normalized_algorithm = re.sub(
            r"[^A-Z0-9-]+",
            "-",
            algorithm.strip().upper(),
        ).strip("-")

        timestamp = replan_at_utc.strftime(
            "%Y%m%dT%H%M%SZ"
        )

        return (
            f"SCHEDULE-{normalized_scenario}-"
            f"{normalized_algorithm}-REPLAN-{timestamp}"
        )

    @staticmethod
    def _normalize_utc(
        value: datetime,
        *,
        field_name: str,
    ) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(
                f"{field_name} musi zawierać strefę czasową"
            )

        return value.astimezone(
            timezone.utc
        )


__all__ = [
    "DEFAULT_FREEZE_DURATION",
    "DEFAULT_FREEZE_REASON",
    "ReplanningResult",
    "ReplanningService",
]
