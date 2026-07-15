from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from time import perf_counter
from typing import Iterable

from app.models.catalog import SystemCatalog
from app.models.enums import (
    PlanningAlgorithm,
    RequestMode,
    ScheduleEntryStatus,
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
from app.planning.fixed import FixedOpportunityAssignment


@dataclass(frozen=True)
class GreedyPlannerConfig:
    """Parametry funkcji celu i ograniczeń algorytmu Greedy."""

    memory_reserve_ratio: float = 0.0

    priority_weight: float = 10.0
    quality_weight: float = 3.0
    coverage_weight: float = 2.0
    mandatory_bonus: float = 100.0

    dual_optional_second_bonus: float = 5.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.memory_reserve_ratio <= 1.0:
            raise ValueError(
                "memory_reserve_ratio musi należeć do zakresu [0, 1]"
            )

        nonnegative_parameters = {
            "priority_weight": self.priority_weight,
            "quality_weight": self.quality_weight,
            "coverage_weight": self.coverage_weight,
            "mandatory_bonus": self.mandatory_bonus,
            "dual_optional_second_bonus": (
                self.dual_optional_second_bonus
            ),
        }

        for name, value in nonnegative_parameters.items():
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
        fixed_assignments: Iterable[
            FixedOpportunityAssignment
        ] | None = None,
        frozen_until_utc: datetime | None = None,
    ) -> None:
        self.catalog = catalog
        self.request_set = request_set
        self.opportunity_set = opportunity_set
        self.config = config or GreedyPlannerConfig()
        self.frozen_until_utc = self._normalize_frozen_until(
            frozen_until_utc
        )
        self.fixed_assignments = tuple(
            fixed_assignments or ()
        )
        self._fixed_assignments_by_id = {
            assignment.opportunity_id: assignment
            for assignment in self.fixed_assignments
        }

        if (
            len(self._fixed_assignments_by_id)
            != len(self.fixed_assignments)
        ):
            raise ValueError(
                "fixed_assignments zawiera powtórzone "
                "opportunity_id"
            )

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

        self._feasible_opportunities_by_id = {
            opportunity.opportunity_id: opportunity
            for opportunity
            in opportunity_set.feasible_opportunities
        }

        for opportunity in opportunity_set.feasible_opportunities:
            if not self._is_candidate_available(
                opportunity
            ):
                continue

            self._opportunities_by_request[
                opportunity.request_id
            ].append(opportunity)

        self._states: dict[
            str,
            _SatellitePlanState,
        ] = {}

        self._selected_opportunities: list[
            AcquisitionOpportunity
        ] = []

        self._validate_input_sets()
        self._validate_fixed_assignments()

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

    def _normalize_frozen_until(
        self,
        value: datetime | None,
    ) -> datetime | None:
        if value is None:
            return None

        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(
                "frozen_until_utc musi zawierać strefę czasową"
            )

        normalized = value.astimezone(
            timezone.utc
        )

        if not (
            self.request_set.horizon_start_utc
            <= normalized
            <= self.request_set.horizon_end_utc
        ):
            raise ValueError(
                "frozen_until_utc musi znajdować się "
                "wewnątrz horyzontu planowania"
            )

        return normalized

    def _validate_fixed_assignments(self) -> None:
        for assignment in self.fixed_assignments:
            opportunity = (
                self._feasible_opportunities_by_id.get(
                    assignment.opportunity_id
                )
            )

            if opportunity is None:
                raise ValueError(
                    "Stała okazja nie istnieje albo nie jest "
                    f"wykonalna: {assignment.opportunity_id}"
                )

            if (
                opportunity.request_id
                not in {
                    request.request_id
                    for request in self.request_set.active_requests
                }
            ):
                raise ValueError(
                    "Stała okazja odwołuje się do nieaktywnego "
                    f"zlecenia: {assignment.opportunity_id}"
                )

            if (
                assignment.status
                == ScheduleEntryStatus.FROZEN
                and self.frozen_until_utc is None
            ):
                raise ValueError(
                    "Stała okazja FROZEN wymaga "
                    "frozen_until_utc"
                )

            if (
                self.frozen_until_utc is not None
                and opportunity.start_utc
                >= self.frozen_until_utc
            ):
                raise ValueError(
                    "Stała okazja musi rozpoczynać się przed "
                    f"frozen_until_utc: {assignment.opportunity_id}"
                )

    def _is_candidate_available(
        self,
        opportunity: AcquisitionOpportunity,
    ) -> bool:
        if (
            opportunity.opportunity_id
            in self._fixed_assignments_by_id
        ):
            return True

        if self.frozen_until_utc is None:
            return True

        return (
            opportunity.start_utc
            >= self.frozen_until_utc
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
        self._commit_fixed_assignments()

        for request in self._sorted_requests():
            self._plan_request(request)

        objective_contributions = (
            self._calculate_objective_contributions()
        )

        entries = [
            self._create_schedule_entry(
                opportunity=opportunity,
                objective_contribution=(
                    objective_contributions[
                        opportunity.opportunity_id
                    ]
                ),
            )
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
            frozen_until_utc=self.frozen_until_utc,
            memory_reserve_ratio=(
                self.config.memory_reserve_ratio
            ),
            objective_value=objective_value,
            solver_runtime_s=solver_runtime_s,
            unassigned_request_ids=unassigned_request_ids,
            notes=(
                "Harmonogram wygenerowany deterministycznym "
                "algorytmem zachłannym. Nagroda priorytetowa jest "
                "naliczana raz na zrealizowane zlecenie. "
                f"Liczba stałych akwizycji: "
                f"{len(self.fixed_assignments)}."
            ),
        )

    def _reset_state(self) -> None:
        self._states = {
            satellite.satellite_id: _SatellitePlanState()
            for satellite in self.catalog.satellites
        }

        self._selected_opportunities = []

    def _commit_fixed_assignments(self) -> None:
        ordered_assignments = sorted(
            self.fixed_assignments,
            key=lambda assignment: (
                self._feasible_opportunities_by_id[
                    assignment.opportunity_id
                ].start_utc,
                assignment.opportunity_id,
            ),
        )

        for assignment in ordered_assignments:
            opportunity = (
                self._feasible_opportunities_by_id[
                    assignment.opportunity_id
                ]
            )

            if not self._can_assign(opportunity):
                raise ValueError(
                    "Stała okazja narusza ograniczenia zasobów "
                    "albo przejść satelity: "
                    f"{assignment.opportunity_id}"
                )

            self._commit(opportunity)

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
        already_selected = [
            opportunity
            for opportunity in self._selected_opportunities
            if opportunity.request_id == request.request_id
        ]

        candidates = self._sorted_candidates(
            [
                opportunity
                for opportunity
                in self._opportunities_by_request.get(
                    request.request_id,
                    [],
                )
                if opportunity.opportunity_id
                not in {
                    selected.opportunity_id
                    for selected in already_selected
                }
            ],
        )

        if request.request_mode == RequestMode.SINGLE:
            if already_selected:
                return

            self._plan_single(candidates)
            return

        selected_sensor_types = {
            opportunity.sensor_type
            for opportunity in already_selected
        }

        if request.request_mode == RequestMode.DUAL_OPTIONAL:
            self._plan_dual_optional(
                candidates,
                selected_sensor_types=selected_sensor_types,
            )
            return

        self._plan_dual_required(
            candidates,
            selected_sensor_types=selected_sensor_types,
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
        candidates: list[AcquisitionOpportunity],
        *,
        selected_sensor_types: set[SensorType],
    ) -> None:
        if selected_sensor_types == {
            SensorType.SAR,
            SensorType.OPTICAL,
        }:
            return

        if selected_sensor_types:
            missing_sensor_type = (
                SensorType.OPTICAL
                if SensorType.SAR in selected_sensor_types
                else SensorType.SAR
            )

            second_opportunity = self._first_assignable(
                self._sorted_candidates(
                    [
                        opportunity
                        for opportunity in candidates
                        if opportunity.sensor_type
                        == missing_sensor_type
                    ]
                )
            )

            if second_opportunity is not None:
                self._commit(second_opportunity)

            return

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
        candidates: list[AcquisitionOpportunity],
        *,
        selected_sensor_types: set[SensorType],
    ) -> None:
        if selected_sensor_types == {
            SensorType.SAR,
            SensorType.OPTICAL,
        }:
            return

        if selected_sensor_types:
            missing_sensor_type = (
                SensorType.OPTICAL
                if SensorType.SAR in selected_sensor_types
                else SensorType.SAR
            )

            missing_opportunity = self._first_assignable(
                self._sorted_candidates(
                    [
                        opportunity
                        for opportunity in candidates
                        if opportunity.sensor_type
                        == missing_sensor_type
                    ]
                )
            )

            if missing_opportunity is not None:
                self._commit(missing_opportunity)

            return

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
                    self._acquisition_score(pair[0])
                    + self._acquisition_score(pair[1])
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
        candidates: list[AcquisitionOpportunity],
    ) -> list[AcquisitionOpportunity]:
        return sorted(
            candidates,
            key=lambda opportunity: (
                -self._acquisition_score(opportunity),
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

    def _request_reward(
        self,
        request: ObservationRequest,
    ) -> float:
        """Nagroda przyznawana raz za realizację zlecenia."""

        reward = (
            request.priority
            * self.config.priority_weight
        )

        if request.is_mandatory:
            reward += self.config.mandatory_bonus

        return round(
            reward,
            6,
        )

    def _acquisition_score(
        self,
        opportunity: AcquisitionOpportunity,
    ) -> float:
        """Ocena jakości pojedynczej akwizycji."""

        score = (
            opportunity.quality_score
            * self.config.quality_weight
            + opportunity.coverage_ratio
            * self.config.coverage_weight
        )

        return round(
            score,
            6,
        )

    def _calculate_objective_contributions(
        self,
    ) -> dict[str, float]:
        """Rozdziela nagrodę zlecenia pomiędzy wybrane wpisy."""

        selected_by_request: dict[
            str,
            list[AcquisitionOpportunity],
        ] = defaultdict(list)

        for opportunity in self._selected_opportunities:
            selected_by_request[
                opportunity.request_id
            ].append(opportunity)

        contributions: dict[str, float] = {}

        for request_id, opportunities in (
            selected_by_request.items()
        ):
            request = self.request_set.get_request(
                request_id
            )

            request_reward = self._request_reward(
                request
            )

            if request.request_mode == RequestMode.SINGLE:
                opportunity = opportunities[0]

                contributions[
                    opportunity.opportunity_id
                ] = round(
                    request_reward
                    + self._acquisition_score(opportunity),
                    6,
                )

                continue

            if (
                request.request_mode
                == RequestMode.DUAL_REQUIRED
            ):
                sensor_types = {
                    opportunity.sensor_type
                    for opportunity in opportunities
                }

                is_complete = (
                    len(opportunities) == 2
                    and sensor_types
                    == {
                        SensorType.SAR,
                        SensorType.OPTICAL,
                    }
                )

                if is_complete:
                    reward_share = (
                        request_reward
                        / len(opportunities)
                    )
                else:
                    reward_share = 0.0

                for opportunity in opportunities:
                    contributions[
                        opportunity.opportunity_id
                    ] = round(
                        reward_share
                        + self._acquisition_score(opportunity),
                        6,
                    )

                continue

            ordered_opportunities = sorted(
                opportunities,
                key=lambda opportunity: (
                    -self._acquisition_score(opportunity),
                    opportunity.opportunity_id,
                ),
            )

            primary_opportunity = ordered_opportunities[0]

            contributions[
                primary_opportunity.opportunity_id
            ] = round(
                request_reward
                + self._acquisition_score(
                    primary_opportunity
                ),
                6,
            )

            for secondary_opportunity in (
                ordered_opportunities[1:]
            ):
                contributions[
                    secondary_opportunity.opportunity_id
                ] = round(
                    self._acquisition_score(
                        secondary_opportunity
                    )
                    + self.config.dual_optional_second_bonus,
                    6,
                )

        return contributions

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
        *,
        opportunity: AcquisitionOpportunity,
        objective_contribution: float,
    ) -> ScheduleEntry:
        entry_suffix = opportunity.opportunity_id.removeprefix(
            "OPP-"
        )

        fixed_assignment = (
            self._fixed_assignments_by_id.get(
                opportunity.opportunity_id
            )
        )

        status = (
            fixed_assignment.status
            if fixed_assignment is not None
            else ScheduleEntryStatus.PLANNED
        )

        lock_reason = (
            fixed_assignment.lock_reason
            if fixed_assignment is not None
            else None
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
            status=status,
            estimated_data_volume_mb=(
                opportunity.estimated_data_volume_mb
            ),
            objective_contribution=(
                objective_contribution
            ),
            lock_reason=lock_reason,
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
    fixed_assignments: Iterable[
        FixedOpportunityAssignment
    ] | None = None,
    frozen_until_utc: datetime | None = None,
) -> Schedule:
    """Funkcja pomocnicza budująca harmonogram Greedy."""

    scheduler = GreedyScheduler(
        catalog=catalog,
        request_set=request_set,
        opportunity_set=opportunity_set,
        config=config,
        fixed_assignments=fixed_assignments,
        frozen_until_utc=frozen_until_utc,
    )

    return scheduler.build_schedule(
        schedule_id=schedule_id,
        name=name,
        created_at_utc=created_at_utc,
    )