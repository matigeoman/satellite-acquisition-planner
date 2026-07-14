from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from time import perf_counter

from app.models.catalog import SystemCatalog
from app.models.enums import (
    PlanningAlgorithm,
    RequestMode,
    ScheduleStatus,
    SensorType,
)
from app.models.opportunity import AcquisitionOpportunity
from app.models.opportunity_set import AcquisitionOpportunitySet
from app.models.request import ObservationRequest
from app.models.request_set import ObservationRequestSet
from app.models.satellite import Satellite
from app.models.schedule import Schedule, ScheduleEntry
from app.models.sensor import Sensor


@dataclass(frozen=True)
class GreedyPlannerConfig:
    """Parametry funkcji celu i ograniczeń algorytmu Greedy."""

    memory_reserve_ratio: float = 0.0

    priority_weight: float = 10.0
    quality_weight: float = 3.0
    coverage_weight: float = 2.0
    mandatory_bonus: float = 100.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.memory_reserve_ratio <= 1.0:
            raise ValueError(
                "memory_reserve_ratio musi należeć do zakresu [0, 1]"
            )

        weights = {
            "priority_weight": self.priority_weight,
            "quality_weight": self.quality_weight,
            "coverage_weight": self.coverage_weight,
            "mandatory_bonus": self.mandatory_bonus,
        }

        for name, value in weights.items():
            if value < 0.0:
                raise ValueError(
                    f"{name} nie może być wartością ujemną"
                )


@dataclass
class _SatellitePlanState:
    """Bieżące wykorzystanie zasobów pojedynczego satelity."""

    opportunities: list[AcquisitionOpportunity] = field(
        default_factory=list
    )

    data_volume_mb: float = 0.0
    imaging_time_s: float = 0.0
    acquisition_count: int = 0


class GreedyScheduler:
    """Deterministyczny algorytm zachłanny budujący harmonogram."""

    def __init__(
        self,
        catalog: SystemCatalog,
        request_set: ObservationRequestSet,
        opportunity_set: AcquisitionOpportunitySet,
        config: GreedyPlannerConfig | None = None,
    ) -> None:
        self.catalog = catalog
        self.request_set = request_set
        self.opportunity_set = opportunity_set
        self.config = config or GreedyPlannerConfig()

        self._satellites_by_id = {
            satellite.satellite_id: satellite
            for satellite in catalog.satellites
        }

        self._sensors_by_id = {
            sensor.sensor_id: sensor
            for sensor in catalog.sensors
        }

        self._opportunities_by_request: dict[
            str,
            list[AcquisitionOpportunity],
        ] = defaultdict(list)

        for opportunity in opportunity_set.feasible_opportunities:
            self._opportunities_by_request[
                opportunity.request_id
            ].append(opportunity)

        self._states: dict[str, _SatellitePlanState] = {}
        self._selected_opportunities: list[
            AcquisitionOpportunity
        ] = []

        self._validate_input_sets()

    def _validate_input_sets(self) -> None:
        self.opportunity_set.validate_against(
            self.catalog,
            self.request_set,
        )

        if (
            self.request_set.horizon_start_utc
            != self.opportunity_set.horizon_start_utc
        ):
            raise ValueError(
                "Początek horyzontu zleceń i okazji jest niezgodny"
            )

        if (
            self.request_set.horizon_end_utc
            != self.opportunity_set.horizon_end_utc
        ):
            raise ValueError(
                "Koniec horyzontu zleceń i okazji jest niezgodny"
            )

    def build_schedule(
        self,
        *,
        schedule_id: str = "SCHEDULE-GREEDY-001",
        name: str = "Dobowy harmonogram Greedy",
        created_at_utc: datetime | None = None,
    ) -> Schedule:
        """Buduje nowy harmonogram od początku."""

        calculation_start = perf_counter()

        self._reset_state()

        for request in self._sorted_requests():
            self._plan_request(request)

        entries = [
            self._create_schedule_entry(opportunity)
            for opportunity in sorted(
                self._selected_opportunities,
                key=lambda item: (
                    item.start_utc,
                    item.satellite_id,
                    item.opportunity_id,
                ),
            )
        ]

        selected_request_ids = {
            entry.request_id
            for entry in entries
        }

        unassigned_request_ids = sorted(
            request.request_id
            for request in self.request_set.active_requests
            if request.request_id not in selected_request_ids
        )

        mandatory_unassigned = {
            request.request_id
            for request in self.request_set.mandatory_requests
            if request.request_id not in selected_request_ids
        }

        if mandatory_unassigned:
            schedule_status = ScheduleStatus.INFEASIBLE
        else:
            schedule_status = ScheduleStatus.FEASIBLE

        objective_value = round(
            sum(
                entry.objective_contribution
                for entry in entries
            ),
            6,
        )

        solver_runtime_s = round(
            perf_counter() - calculation_start,
            6,
        )

        if created_at_utc is None:
            created_at_utc = datetime.now(timezone.utc)

        return Schedule(
            schedule_id=schedule_id,
            name=name,
            horizon_start_utc=self.request_set.horizon_start_utc,
            horizon_end_utc=self.request_set.horizon_end_utc,
            created_at_utc=created_at_utc,
            algorithm=PlanningAlgorithm.GREEDY,
            status=schedule_status,
            entries=entries,
            frozen_until_utc=None,
            memory_reserve_ratio=(
                self.config.memory_reserve_ratio
            ),
            objective_value=objective_value,
            solver_runtime_s=solver_runtime_s,
            unassigned_request_ids=unassigned_request_ids,
            notes=(
                "Harmonogram wygenerowany deterministycznym "
                "algorytmem zachłannym."
            ),
        )

    def _reset_state(self) -> None:
        self._states = {
            satellite.satellite_id: _SatellitePlanState()
            for satellite in self.catalog.satellites
        }

        self._selected_opportunities = []

    def _sorted_requests(self) -> list[ObservationRequest]:
        mode_rank = {
            RequestMode.DUAL_REQUIRED: 0,
            RequestMode.SINGLE: 1,
            RequestMode.DUAL_OPTIONAL: 2,
        }

        return sorted(
            self.request_set.active_requests,
            key=lambda request: (
                -int(request.is_mandatory),
                -request.priority,
                mode_rank[request.request_mode],
                request.latest_end_utc,
                request.request_id,
            ),
        )

    def _plan_request(
        self,
        request: ObservationRequest,
    ) -> None:
        candidates = self._sorted_candidates(
            request,
            self._opportunities_by_request.get(
                request.request_id,
                [],
            ),
        )

        if not candidates:
            return

        if request.request_mode == RequestMode.SINGLE:
            self._plan_single(candidates)
            return

        if request.request_mode == RequestMode.DUAL_OPTIONAL:
            self._plan_dual_optional(
                request,
                candidates,
            )
            return

        self._plan_dual_required(
            request,
            candidates,
        )

    def _plan_single(
        self,
        candidates: list[AcquisitionOpportunity],
    ) -> None:
        opportunity = self._first_assignable(
            candidates
        )

        if opportunity is not None:
            self._commit(opportunity)

    def _plan_dual_optional(
        self,
        request: ObservationRequest,
        candidates: list[AcquisitionOpportunity],
    ) -> None:
        first_opportunity = self._first_assignable(
            candidates
        )

        if first_opportunity is None:
            return

        self._commit(first_opportunity)

        other_sensor_type = (
            SensorType.OPTICAL
            if first_opportunity.sensor_type == SensorType.SAR
            else SensorType.SAR
        )

        second_candidates = self._sorted_candidates(
            request,
            [
                opportunity
                for opportunity in candidates
                if opportunity.sensor_type == other_sensor_type
            ],
        )

        second_opportunity = self._first_assignable(
            second_candidates
        )

        if second_opportunity is not None:
            self._commit(second_opportunity)

    def _plan_dual_required(
        self,
        request: ObservationRequest,
        candidates: list[AcquisitionOpportunity],
    ) -> None:
        sar_candidates = [
            opportunity
            for opportunity in candidates
            if opportunity.sensor_type == SensorType.SAR
        ]

        optical_candidates = [
            opportunity
            for opportunity in candidates
            if opportunity.sensor_type == SensorType.OPTICAL
        ]

        pairs: list[
            tuple[
                AcquisitionOpportunity,
                AcquisitionOpportunity,
            ]
        ] = []

        for sar_opportunity in sar_candidates:
            for optical_opportunity in optical_candidates:
                pairs.append(
                    (
                        sar_opportunity,
                        optical_opportunity,
                    )
                )

        pairs.sort(
            key=lambda pair: (
                -(
                    self._score_opportunity(
                        pair[0],
                        request,
                    )
                    + self._score_opportunity(
                        pair[1],
                        request,
                    )
                ),
                max(
                    pair[0].end_utc,
                    pair[1].end_utc,
                ),
                pair[0].opportunity_id,
                pair[1].opportunity_id,
            )
        )

        for sar_opportunity, optical_opportunity in pairs:
            if not self._can_assign(sar_opportunity):
                continue

            if not self._can_assign(optical_opportunity):
                continue

            self._commit(sar_opportunity)
            self._commit(optical_opportunity)
            return

    def _sorted_candidates(
        self,
        request: ObservationRequest,
        candidates: list[AcquisitionOpportunity],
    ) -> list[AcquisitionOpportunity]:
        return sorted(
            candidates,
            key=lambda opportunity: (
                -self._score_opportunity(
                    opportunity,
                    request,
                ),
                opportunity.start_utc,
                opportunity.opportunity_id,
            ),
        )

    def _first_assignable(
        self,
        candidates: list[AcquisitionOpportunity],
    ) -> AcquisitionOpportunity | None:
        for opportunity in candidates:
            if self._can_assign(opportunity):
                return opportunity

        return None

    def _score_opportunity(
        self,
        opportunity: AcquisitionOpportunity,
        request: ObservationRequest,
    ) -> float:
        mandatory_bonus_share = 0.0

        if request.is_mandatory:
            mandatory_bonus_share = (
                self.config.mandatory_bonus
                / request.maximum_allowed_acquisitions
            )

        score = (
            request.priority
            * self.config.priority_weight
            + opportunity.quality_score
            * self.config.quality_weight
            + opportunity.coverage_ratio
            * self.config.coverage_weight
            + mandatory_bonus_share
        )

        return round(score, 6)

    def _can_assign(
        self,
        opportunity: AcquisitionOpportunity,
    ) -> bool:
        satellite = self._satellites_by_id[
            opportunity.satellite_id
        ]

        if not satellite.is_available_for_planning:
            return False

        state = self._states[
            satellite.satellite_id
        ]

        if (
            state.acquisition_count + 1
            > satellite.max_acquisitions_per_day
        ):
            return False

        if (
            state.imaging_time_s
            + opportunity.duration_s
            > satellite.max_imaging_time_per_day_s
            + 1e-9
        ):
            return False

        usable_memory_mb = (
            satellite.memory_capacity_mb
            * (
                1.0
                - self.config.memory_reserve_ratio
            )
        )

        projected_memory_usage_mb = (
            satellite.initial_memory_usage_mb
            + state.data_volume_mb
            + opportunity.estimated_data_volume_mb
        )

        if (
            projected_memory_usage_mb
            > usable_memory_mb + 1e-9
        ):
            return False

        transition_time_s = self._transition_time_s(
            satellite
        )

        transition_delta = timedelta(
            seconds=transition_time_s
        )

        for existing in state.opportunities:
            separated_before = (
                opportunity.end_utc
                + transition_delta
                <= existing.start_utc
            )

            separated_after = (
                existing.end_utc
                + transition_delta
                <= opportunity.start_utc
            )

            if not (
                separated_before
                or separated_after
            ):
                return False

        return True

    def _transition_time_s(
        self,
        satellite: Satellite,
    ) -> float:
        sensor = self._sensors_by_id[
            satellite.sensor_id
        ]

        sensor_transition_s = (
            sensor.cooldown_time_s
            + sensor.warmup_time_s
        )

        return max(
            satellite.minimum_transition_time_s,
            sensor_transition_s,
        )

    def _commit(
        self,
        opportunity: AcquisitionOpportunity,
    ) -> None:
        state = self._states[
            opportunity.satellite_id
        ]

        state.opportunities.append(
            opportunity
        )

        state.data_volume_mb += (
            opportunity.estimated_data_volume_mb
        )

        state.imaging_time_s += (
            opportunity.duration_s
        )

        state.acquisition_count += 1

        self._selected_opportunities.append(
            opportunity
        )

    def _create_schedule_entry(
        self,
        opportunity: AcquisitionOpportunity,
    ) -> ScheduleEntry:
        request = self.request_set.get_request(
            opportunity.request_id
        )

        entry_suffix = opportunity.opportunity_id.removeprefix(
            "OPP-"
        )

        return ScheduleEntry(
            entry_id=f"ENTRY-{entry_suffix}",
            opportunity_id=opportunity.opportunity_id,
            request_id=opportunity.request_id,
            satellite_id=opportunity.satellite_id,
            sensor_id=opportunity.sensor_id,
            mode_id=opportunity.mode_id,
            sensor_type=opportunity.sensor_type,
            start_utc=opportunity.start_utc,
            end_utc=opportunity.end_utc,
            status="PLANNED",
            estimated_data_volume_mb=(
                opportunity.estimated_data_volume_mb
            ),
            objective_contribution=(
                self._score_opportunity(
                    opportunity,
                    request,
                )
            ),
            lock_reason=None,
            notes=None,
        )


def build_greedy_schedule(
    catalog: SystemCatalog,
    request_set: ObservationRequestSet,
    opportunity_set: AcquisitionOpportunitySet,
    *,
    config: GreedyPlannerConfig | None = None,
    schedule_id: str = "SCHEDULE-GREEDY-001",
    name: str = "Dobowy harmonogram Greedy",
    created_at_utc: datetime | None = None,
) -> Schedule:
    """Funkcja pomocnicza budująca harmonogram Greedy."""

    scheduler = GreedyScheduler(
        catalog=catalog,
        request_set=request_set,
        opportunity_set=opportunity_set,
        config=config,
    )

    return scheduler.build_schedule(
        schedule_id=schedule_id,
        name=name,
        created_at_utc=created_at_utc,
    )