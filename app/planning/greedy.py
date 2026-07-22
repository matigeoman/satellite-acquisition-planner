from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from math import log1p
from time import perf_counter
from typing import Iterable

from app.models.catalog import SystemCatalog
from app.models.downlink_set import DownlinkOpportunitySet
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
from app.planning.conflict_graph import (
    OpportunityConflictGraph,
    build_opportunity_conflict_graph,
)
from app.planning.fixed import FixedOpportunityAssignment
from app.planning.config import GreedyPlannerConfig
from app.planning.operational import (
    build_pass_index,
    dual_pair_is_compatible,
    request_is_fulfilled,
    required_transition_time_s,
)
from app.planning.resources import allocate_downlinks_greedily
from app.planning.scoring import (
    acquisition_score,
    calculate_objective_contributions,
    request_reward,
)


@dataclass
class _SatellitePlanState:
    """Bieżące wykorzystanie zasobów pojedynczego satelity."""

    opportunities: list[AcquisitionOpportunity] = field(default_factory=list)

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
        downlink_set: DownlinkOpportunitySet | None = None,
        config: GreedyPlannerConfig | None = None,
        fixed_assignments: Iterable[FixedOpportunityAssignment] | None = None,
        frozen_until_utc: datetime | None = None,
    ) -> None:
        self.catalog = catalog
        self.request_set = request_set
        self.opportunity_set = opportunity_set
        self.downlink_set = downlink_set
        self.config = config or GreedyPlannerConfig()
        self.frozen_until_utc = self._normalize_frozen_until(frozen_until_utc)
        self.fixed_assignments = tuple(fixed_assignments or ())
        self._fixed_assignments_by_id = {
            assignment.opportunity_id: assignment
            for assignment in self.fixed_assignments
        }

        if len(self._fixed_assignments_by_id) != len(self.fixed_assignments):
            raise ValueError("fixed_assignments zawiera powtórzone opportunity_id")

        self._satellites_by_id = {
            satellite.satellite_id: satellite for satellite in catalog.satellites
        }

        self._sensors_by_id = {sensor.sensor_id: sensor for sensor in catalog.sensors}
        self._modes_by_id = {
            mode.mode_id: mode
            for sensor in catalog.sensors
            for mode in sensor.imaging_modes
        }

        self._opportunities_by_request: dict[
            str,
            list[AcquisitionOpportunity],
        ] = defaultdict(list)

        self._feasible_opportunities_by_id = {
            opportunity.opportunity_id: opportunity
            for opportunity in opportunity_set.feasible_opportunities
        }

        for opportunity in opportunity_set.feasible_opportunities:
            if not self._is_candidate_available(opportunity):
                continue

            self._opportunities_by_request[opportunity.request_id].append(opportunity)

        self._opportunities_by_id = {
            opportunity.opportunity_id: opportunity
            for opportunities in self._opportunities_by_request.values()
            for opportunity in opportunities
        }
        self._conflict_graph: OpportunityConflictGraph | None = None
        if self.config.use_opportunity_cost_heuristic:
            self._conflict_graph = build_opportunity_conflict_graph(
                catalog=self.catalog,
                request_set=self.request_set,
                opportunity_set=self.opportunity_set,
                config=self.config,
            )

        self._sar_pass_by_opportunity_id: dict[str, int] = {}
        for satellite in catalog.satellites:
            satellite_sar_opportunities = [
                opportunity
                for opportunity in opportunity_set.feasible_opportunities
                if opportunity.satellite_id == satellite.satellite_id
                and opportunity.sensor_type == SensorType.SAR
            ]
            self._sar_pass_by_opportunity_id.update(
                build_pass_index(
                    satellite_sar_opportunities,
                    pass_gap_s=self.config.sar_pass_gap_s,
                )
            )

        self._states: dict[
            str,
            _SatellitePlanState,
        ] = {}

        self._selected_opportunities: list[AcquisitionOpportunity] = []

        self._validate_input_sets()
        self._validate_downlink_configuration()
        self._validate_fixed_assignments()

    def _validate_input_sets(self) -> None:
        self.opportunity_set.validate_against(
            self.catalog,
            self.request_set,
        )

        if self.request_set.horizon_start_utc != self.opportunity_set.horizon_start_utc:
            raise ValueError("Początek horyzontu zleceń i okazji jest niezgodny")

        if self.request_set.horizon_end_utc != self.opportunity_set.horizon_end_utc:
            raise ValueError("Koniec horyzontu zleceń i okazji jest niezgodny")

    def _validate_downlink_configuration(self) -> None:
        if self.config.enable_downlink_planning:
            if self.downlink_set is None:
                raise ValueError(
                    "Zintegrowane planowanie downlinku wymaga downlink_set"
                )
            self.downlink_set.validate_against(self.catalog)
            if (
                self.downlink_set.horizon_start_utc
                != self.request_set.horizon_start_utc
                or self.downlink_set.horizon_end_utc
                != self.request_set.horizon_end_utc
            ):
                raise ValueError(
                    "Horyzont zbioru downlinków jest niezgodny ze scenariuszem"
                )

    def _normalize_frozen_until(
        self,
        value: datetime | None,
    ) -> datetime | None:
        if value is None:
            return None

        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("frozen_until_utc musi zawierać strefę czasową")

        normalized = value.astimezone(timezone.utc)

        if not (
            self.request_set.horizon_start_utc
            <= normalized
            <= self.request_set.horizon_end_utc
        ):
            raise ValueError(
                "frozen_until_utc musi znajdować się wewnątrz horyzontu planowania"
            )

        return normalized

    def _validate_fixed_assignments(self) -> None:
        for assignment in self.fixed_assignments:
            opportunity = self._feasible_opportunities_by_id.get(
                assignment.opportunity_id
            )

            if opportunity is None:
                raise ValueError(
                    "Stała okazja nie istnieje albo nie jest "
                    f"wykonalna: {assignment.opportunity_id}"
                )

            if opportunity.request_id not in {
                request.request_id for request in self.request_set.active_requests
            }:
                raise ValueError(
                    "Stała okazja odwołuje się do nieaktywnego "
                    f"zlecenia: {assignment.opportunity_id}"
                )

            if (
                assignment.status == ScheduleEntryStatus.FROZEN
                and self.frozen_until_utc is None
            ):
                raise ValueError("Stała okazja FROZEN wymaga frozen_until_utc")

            if (
                self.frozen_until_utc is not None
                and opportunity.start_utc >= self.frozen_until_utc
            ):
                raise ValueError(
                    "Stała okazja musi rozpoczynać się przed "
                    f"frozen_until_utc: {assignment.opportunity_id}"
                )

    def _is_candidate_available(
        self,
        opportunity: AcquisitionOpportunity,
    ) -> bool:
        if opportunity.opportunity_id in self._fixed_assignments_by_id:
            return True

        if self.frozen_until_utc is None:
            return True

        return opportunity.start_utc >= self.frozen_until_utc

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

        objective_contributions = self._calculate_objective_contributions()

        entries = [
            self._create_schedule_entry(
                opportunity=opportunity,
                objective_contribution=(
                    objective_contributions[opportunity.opportunity_id]
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

        selected_request_ids = self._fulfilled_request_ids()

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
            sum(entry.objective_contribution for entry in entries),
            6,
        )

        solver_runtime_s = round(
            perf_counter() - calculation_start,
            6,
        )

        if created_at_utc is None:
            created_at_utc = datetime.now(timezone.utc)

        resource_result = None
        if self.config.enable_downlink_planning:
            assert self.downlink_set is not None
            resource_result = allocate_downlinks_greedily(
                catalog=self.catalog,
                acquisitions=self._selected_opportunities,
                downlink_set=self.downlink_set,
                memory_reserve_ratio=self.config.memory_reserve_ratio,
                require_full_downlink=self.config.require_full_downlink,
                allow_simultaneous_imaging_downlink=(
                    self.config.allow_simultaneous_imaging_downlink
                ),
                downlink_capacity_reserve_ratio=(
                    self.config.downlink_capacity_reserve_ratio
                ),
            )
            if not resource_result.feasible:
                schedule_status = ScheduleStatus.INFEASIBLE

        return Schedule(
            schedule_id=schedule_id,
            name=name,
            horizon_start_utc=self.request_set.horizon_start_utc,
            horizon_end_utc=self.request_set.horizon_end_utc,
            created_at_utc=created_at_utc,
            algorithm=PlanningAlgorithm.GREEDY,
            status=schedule_status,
            entries=entries,
            downlink_entries=(
                list(resource_result.downlink_entries)
                if resource_result is not None
                else []
            ),
            resource_summaries=(
                list(resource_result.summaries)
                if resource_result is not None
                else []
            ),
            memory_timeline=(
                list(resource_result.memory_timeline)
                if resource_result is not None
                else []
            ),
            frozen_until_utc=self.frozen_until_utc,
            memory_reserve_ratio=(self.config.memory_reserve_ratio),
            objective_value=objective_value,
            solver_runtime_s=solver_runtime_s,
            unassigned_request_ids=unassigned_request_ids,
            notes=(
                "Harmonogram wygenerowany deterministycznym "
                "algorytmem zachłannym. "
                + (
                    "Ranking okazji uwzględnia koszt utraconych "
                    "alternatyw i rzadkość okien. "
                    if self.config.use_opportunity_cost_heuristic
                    else ""
                )
                + "Nagroda priorytetowa jest "
                "naliczana raz na zrealizowane zlecenie. "
                f"Liczba stałych akwizycji: "
                f"{len(self.fixed_assignments)}. "
                + (
                    "Pamięć jest liczona dynamicznie i zwalniana po "
                    "zaplanowanych transmisjach. "
                    if self.config.enable_downlink_planning
                    else ""
                )
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
                self._feasible_opportunities_by_id[assignment.opportunity_id].start_utc,
                assignment.opportunity_id,
            ),
        )

        for assignment in ordered_assignments:
            opportunity = self._feasible_opportunities_by_id[assignment.opportunity_id]

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

        if not self.config.use_opportunity_cost_heuristic:
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

        return sorted(
            self.request_set.active_requests,
            key=lambda request: (
                -int(request.is_mandatory),
                -request.priority,
                len(self._opportunities_by_request.get(request.request_id, [])),
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
                for opportunity in self._opportunities_by_request.get(
                    request.request_id,
                    [],
                )
                if opportunity.opportunity_id
                not in {selected.opportunity_id for selected in already_selected}
            ],
        )

        if request.request_mode == RequestMode.SINGLE:
            if already_selected:
                return

            self._plan_single(candidates)
            return

        selected_sensor_types = {
            opportunity.sensor_type for opportunity in already_selected
        }

        if request.request_mode == RequestMode.DUAL_OPTIONAL:
            self._plan_dual_optional(
                request,
                candidates,
                selected_sensor_types=selected_sensor_types,
            )
            return

        self._plan_dual_required(
            request,
            candidates,
            selected_sensor_types=selected_sensor_types,
        )

    def _plan_single(
        self,
        candidates: list[AcquisitionOpportunity],
    ) -> None:
        opportunity = self._first_assignable(candidates)

        if opportunity is not None:
            self._commit(opportunity)

    def _plan_dual_optional(
        self,
        request: ObservationRequest,
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
            selected = next(
                opportunity
                for opportunity in self._selected_opportunities
                if opportunity.request_id == request.request_id
            )

            second_opportunity = self._first_assignable(
                self._sorted_candidates(
                    [
                        opportunity
                        for opportunity in candidates
                        if opportunity.sensor_type == missing_sensor_type
                        and dual_pair_is_compatible(
                            request,
                            selected,
                            opportunity,
                        )
                    ]
                )
            )

            if second_opportunity is not None:
                self._commit(second_opportunity)

            return

        first_opportunity = self._first_assignable(candidates)

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
                and dual_pair_is_compatible(
                    request,
                    first_opportunity,
                    opportunity,
                )
            ],
        )

        second_opportunity = self._first_assignable(second_candidates)

        if second_opportunity is not None:
            self._commit(second_opportunity)

    def _plan_dual_required(
        self,
        request: ObservationRequest,
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
            selected = next(
                opportunity
                for opportunity in self._selected_opportunities
                if opportunity.request_id == request.request_id
            )

            missing_opportunity = self._first_assignable(
                self._sorted_candidates(
                    [
                        opportunity
                        for opportunity in candidates
                        if opportunity.sensor_type == missing_sensor_type
                        and dual_pair_is_compatible(
                            request,
                            selected,
                            opportunity,
                        )
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
                if not dual_pair_is_compatible(
                    request,
                    sar_opportunity,
                    optical_opportunity,
                ):
                    continue
                pairs.append(
                    (
                        sar_opportunity,
                        optical_opportunity,
                    )
                )

        pairs.sort(
            key=lambda pair: (
                -(
                    self._candidate_priority_score(pair[0])
                    + self._candidate_priority_score(pair[1])
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
                -self._candidate_priority_score(opportunity),
                opportunity.start_utc,
                opportunity.opportunity_id,
            ),
        )

    def _candidate_priority_score(
        self,
        opportunity: AcquisitionOpportunity,
    ) -> float:
        base_score = self._acquisition_score(opportunity)
        if not self.config.use_opportunity_cost_heuristic:
            return base_score

        alternatives = self._opportunities_by_request.get(
            opportunity.request_id,
            [],
        )
        scarcity_bonus = self.config.scarcity_bonus_weight / max(
            1,
            len(alternatives),
        )
        duration_cost = (
            self.config.duration_cost_weight * opportunity.duration_s
        )
        memory_cost = (
            self.config.memory_cost_weight
            * opportunity.estimated_data_volume_mb
        )

        conflict_cost = 0.0
        if self._conflict_graph is not None:
            external_neighbors = [
                self._opportunities_by_id[neighbor_id]
                for neighbor_id in self._conflict_graph.neighbors(
                    opportunity.opportunity_id
                )
                if neighbor_id in self._opportunities_by_id
                and self._opportunities_by_id[neighbor_id].request_id
                != opportunity.request_id
            ]
            if external_neighbors:
                blocked_by_request: dict[str, float] = {}
                for neighbor in external_neighbors:
                    blocked_by_request[neighbor.request_id] = max(
                        blocked_by_request.get(neighbor.request_id, 0.0),
                        self._acquisition_score(neighbor),
                    )
                mean_blocked_value = sum(blocked_by_request.values()) / len(
                    blocked_by_request
                )
                conflict_cost = (
                    self.config.conflict_cost_weight
                    * mean_blocked_value
                    * log1p(len(blocked_by_request))
                )

        return round(
            base_score
            + scarcity_bonus
            - duration_cost
            - memory_cost
            - conflict_cost,
            6,
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
        return request_reward(request, self.config)

    def _acquisition_score(
        self,
        opportunity: AcquisitionOpportunity,
    ) -> float:
        return acquisition_score(opportunity, self.config)

    def _calculate_objective_contributions(
        self,
    ) -> dict[str, float]:
        return calculate_objective_contributions(
            request_set=self.request_set,
            selected_opportunities=self._selected_opportunities,
            config=self.config,
        )

    def _can_assign(
        self,
        opportunity: AcquisitionOpportunity,
    ) -> bool:
        satellite = self._satellites_by_id[opportunity.satellite_id]

        if not satellite.is_available_for_planning:
            return False

        state = self._states[satellite.satellite_id]

        if state.acquisition_count + 1 > satellite.max_acquisitions_per_day:
            return False

        if (
            state.imaging_time_s + opportunity.duration_s
            > satellite.max_imaging_time_per_day_s + 1e-9
        ):
            return False

        if self.config.enable_downlink_planning:
            assert self.downlink_set is not None
            tentative = [*self._selected_opportunities, opportunity]
            resource_result = allocate_downlinks_greedily(
                catalog=self.catalog,
                acquisitions=tentative,
                downlink_set=self.downlink_set,
                memory_reserve_ratio=self.config.memory_reserve_ratio,
                require_full_downlink=self.config.require_full_downlink,
                allow_simultaneous_imaging_downlink=(
                    self.config.allow_simultaneous_imaging_downlink
                ),
                downlink_capacity_reserve_ratio=(
                    self.config.downlink_capacity_reserve_ratio
                ),
            )
            if not resource_result.feasible:
                return False
        else:
            usable_memory_mb = satellite.memory_capacity_mb * (
                1.0 - self.config.memory_reserve_ratio
            )

            projected_memory_usage_mb = (
                satellite.initial_memory_usage_mb
                + state.data_volume_mb
                + opportunity.estimated_data_volume_mb
            )

            if projected_memory_usage_mb > usable_memory_mb + 1e-9:
                return False

        if (
            self.config.use_dynamic_transition_model
            and opportunity.sensor_type == SensorType.SAR
        ):
            pass_id = self._sar_pass_by_opportunity_id.get(opportunity.opportunity_id)
            selected_in_pass = sum(
                self._sar_pass_by_opportunity_id.get(existing.opportunity_id) == pass_id
                for existing in state.opportunities
                if existing.sensor_type == SensorType.SAR
            )
            if selected_in_pass + 1 > self.config.sar_max_acquisitions_per_pass:
                return False

        for existing in state.opportunities:
            before_transition_s = self._transition_time_s(
                opportunity,
                existing,
                satellite,
            )
            after_transition_s = self._transition_time_s(
                existing,
                opportunity,
                satellite,
            )
            separated_before = (
                opportunity.end_utc + timedelta(seconds=before_transition_s)
                <= existing.start_utc
            )
            separated_after = (
                existing.end_utc + timedelta(seconds=after_transition_s)
                <= opportunity.start_utc
            )

            if not (separated_before or separated_after):
                return False

        return True

    def _transition_time_s(
        self,
        first: AcquisitionOpportunity,
        second: AcquisitionOpportunity,
        satellite: Satellite,
    ) -> float:
        sensor = self._sensors_by_id[satellite.sensor_id]
        return required_transition_time_s(
            first=first,
            second=second,
            satellite=satellite,
            sensor=sensor,
            modes_by_id=self._modes_by_id,
            config=self.config,
        )

    def _fulfilled_request_ids(self) -> set[str]:
        selected_by_request: dict[str, list[AcquisitionOpportunity]] = defaultdict(list)
        for opportunity in self._selected_opportunities:
            selected_by_request[opportunity.request_id].append(opportunity)

        return {
            request.request_id
            for request in self.request_set.active_requests
            if request_is_fulfilled(
                request,
                selected_by_request.get(request.request_id, []),
            )
        }

    def _commit(
        self,
        opportunity: AcquisitionOpportunity,
    ) -> None:
        state = self._states[opportunity.satellite_id]

        state.opportunities.append(opportunity)

        state.data_volume_mb += opportunity.estimated_data_volume_mb

        state.imaging_time_s += opportunity.duration_s

        state.acquisition_count += 1

        self._selected_opportunities.append(opportunity)

    def _create_schedule_entry(
        self,
        *,
        opportunity: AcquisitionOpportunity,
        objective_contribution: float,
    ) -> ScheduleEntry:
        entry_suffix = opportunity.opportunity_id.removeprefix("OPP-")

        fixed_assignment = self._fixed_assignments_by_id.get(opportunity.opportunity_id)

        status = (
            fixed_assignment.status
            if fixed_assignment is not None
            else ScheduleEntryStatus.PLANNED
        )

        lock_reason = (
            fixed_assignment.lock_reason if fixed_assignment is not None else None
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
            estimated_data_volume_mb=(opportunity.estimated_data_volume_mb),
            objective_contribution=(objective_contribution),
            lock_reason=lock_reason,
            notes=None,
        )


def build_greedy_schedule(
    catalog: SystemCatalog,
    request_set: ObservationRequestSet,
    opportunity_set: AcquisitionOpportunitySet,
    *,
    downlink_set: DownlinkOpportunitySet | None = None,
    config: GreedyPlannerConfig | None = None,
    schedule_id: str = "SCHEDULE-GREEDY-001",
    name: str = "Dobowy harmonogram Greedy",
    created_at_utc: datetime | None = None,
    fixed_assignments: Iterable[FixedOpportunityAssignment] | None = None,
    frozen_until_utc: datetime | None = None,
) -> Schedule:
    """Funkcja pomocnicza budująca harmonogram Greedy."""

    scheduler = GreedyScheduler(
        catalog=catalog,
        request_set=request_set,
        opportunity_set=opportunity_set,
        downlink_set=downlink_set,
        config=config,
        fixed_assignments=fixed_assignments,
        frozen_until_utc=frozen_until_utc,
    )

    return scheduler.build_schedule(
        schedule_id=schedule_id,
        name=name,
        created_at_utc=created_at_utc,
    )
