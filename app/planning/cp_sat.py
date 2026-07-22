from collections import defaultdict
from datetime import datetime, timedelta, timezone
from time import perf_counter
from typing import Iterable, Mapping

from ortools.sat.python import cp_model

from app.models.catalog import SystemCatalog
from app.models.downlink import DownlinkOpportunity
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
from app.planning.fixed import FixedOpportunityAssignment
from app.planning.config import CpSatPlannerConfig
from app.planning.operational import (
    build_pass_index,
    dual_pair_is_compatible,
    request_is_fulfilled,
    required_transition_time_s,
)
from app.planning.resources import evaluate_planned_downlinks
from app.planning.scoring import (
    acquisition_score,
    calculate_objective_contributions,
    request_reward,
)


class CpSatScheduler:
    """Dokładny model harmonogramowania wykorzystujący CP-SAT."""

    def __init__(
        self,
        catalog: SystemCatalog,
        request_set: ObservationRequestSet,
        opportunity_set: AcquisitionOpportunitySet,
        downlink_set: DownlinkOpportunitySet | None = None,
        config: CpSatPlannerConfig | None = None,
        fixed_assignments: Iterable[
            FixedOpportunityAssignment
        ] | None = None,
        frozen_until_utc: datetime | None = None,
        fixed_selection: Mapping[str, bool] | None = None,
        solution_hint_ids: Iterable[str] | None = None,
    ) -> None:
        self.catalog = catalog
        self.request_set = request_set
        self.opportunity_set = opportunity_set
        self.downlink_set = downlink_set
        self.config = config or CpSatPlannerConfig()
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
        self.fixed_selection = {
            str(opportunity_id).strip().upper(): bool(selected)
            for opportunity_id, selected in (fixed_selection or {}).items()
        }
        self.solution_hint_ids = frozenset(
            str(opportunity_id).strip().upper()
            for opportunity_id in (solution_hint_ids or ())
        )

        if (
            len(self._fixed_assignments_by_id)
            != len(self.fixed_assignments)
        ):
            raise ValueError(
                "fixed_assignments zawiera powtórzone "
                "opportunity_id"
            )

        self.last_solver_status: str | None = None

        self._satellites_by_id = {
            satellite.satellite_id: satellite
            for satellite in catalog.satellites
        }

        self._sensors_by_id = {
            sensor.sensor_id: sensor
            for sensor in catalog.sensors
        }
        self._modes_by_id = {
            mode.mode_id: mode
            for sensor in catalog.sensors
            for mode in sensor.imaging_modes
        }

        self._active_requests_by_id = {
            request.request_id: request
            for request in request_set.active_requests
        }

        self._feasible_opportunities_by_id = {
            opportunity.opportunity_id: opportunity
            for opportunity
            in opportunity_set.feasible_opportunities
        }

        self._candidate_opportunities = [
            opportunity
            for opportunity
            in opportunity_set.feasible_opportunities
            if opportunity.request_id
            in self._active_requests_by_id
        ]

        active_station_ids = {
            station.ground_station_id
            for station in catalog.ground_stations
            if station.is_active
        }
        active_satellite_ids = {
            satellite.satellite_id
            for satellite in catalog.satellites
            if satellite.is_available_for_planning
        }
        self._candidate_downlinks: list[DownlinkOpportunity] = (
            [
                item
                for item in downlink_set.feasible_opportunities
                if item.ground_station_id in active_station_ids
                and item.satellite_id in active_satellite_ids
            ]
            if downlink_set is not None
            else []
        )
        self._downlinks_by_satellite: dict[
            str, list[DownlinkOpportunity]
        ] = defaultdict(list)
        self._downlinks_by_station: dict[
            str, list[DownlinkOpportunity]
        ] = defaultdict(list)
        for downlink in self._candidate_downlinks:
            self._downlinks_by_satellite[downlink.satellite_id].append(downlink)
            self._downlinks_by_station[downlink.ground_station_id].append(downlink)

        self._opportunities_by_request: dict[
            str,
            list[AcquisitionOpportunity],
        ] = defaultdict(list)

        self._opportunities_by_satellite: dict[
            str,
            list[AcquisitionOpportunity],
        ] = defaultdict(list)

        for opportunity in self._candidate_opportunities:
            self._opportunities_by_request[
                opportunity.request_id
            ].append(opportunity)

            self._opportunities_by_satellite[
                opportunity.satellite_id
            ].append(opportunity)

        self._selection_variables: dict[
            str,
            cp_model.IntVar,
        ] = {}

        self._request_fulfilled_variables: dict[
            str,
            cp_model.IntVar,
        ] = {}

        self._dual_optional_second_variables: dict[
            str,
            cp_model.IntVar,
        ] = {}

        self._downlink_used_variables: dict[str, cp_model.IntVar] = {}
        self._downlink_amount_variables: dict[str, cp_model.IntVar] = {}

        self._validate_input_sets()
        self._validate_downlink_configuration()
        self._validate_fixed_assignments()
        self._validate_research_constraints()

    def _validate_research_constraints(self) -> None:
        candidate_ids = {
            opportunity.opportunity_id
            for opportunity in self._candidate_opportunities
        }
        unknown_fixed = sorted(set(self.fixed_selection) - candidate_ids)
        if unknown_fixed:
            raise ValueError(
                "fixed_selection zawiera nieznane okazje: "
                + ", ".join(unknown_fixed[:5])
            )
        unknown_hints = sorted(set(self.solution_hint_ids) - candidate_ids)
        if unknown_hints:
            raise ValueError(
                "solution_hint_ids zawiera nieznane okazje: "
                + ", ".join(unknown_hints[:5])
            )
        for opportunity_id in self._fixed_assignments_by_id:
            if self.fixed_selection.get(opportunity_id) is False:
                raise ValueError(
                    "fixed_selection nie może wyłączyć stałej okazji: "
                    f"{opportunity_id}"
                )

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
                "Początek horyzontu zleceń i okazji "
                "jest niezgodny"
            )

        if (
            self.request_set.horizon_end_utc
            != self.opportunity_set.horizon_end_utc
        ):
            raise ValueError(
                "Koniec horyzontu zleceń i okazji "
                "jest niezgodny"
            )

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
                not in self._active_requests_by_id
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

    def build_schedule(
        self,
        *,
        schedule_id: str = "SCHEDULE-CP-SAT-001",
        name: str = "Dobowy harmonogram CP-SAT",
        created_at_utc: datetime | None = None,
    ) -> Schedule:
        """Buduje harmonogram przez rozwiązanie modelu CP-SAT."""

        model = self._build_model()

        solver = cp_model.CpSolver()

        solver.parameters.max_time_in_seconds = (
            self.config.max_time_s
        )
        solver.parameters.num_search_workers = (
            self.config.num_search_workers
        )
        solver.parameters.random_seed = (
            self.config.random_seed
        )
        solver.parameters.log_search_progress = (
            self.config.log_search_progress
        )

        calculation_start = perf_counter()

        status = solver.solve(model)

        solver_runtime_s = round(
            perf_counter() - calculation_start,
            6,
        )

        self.last_solver_status = solver.status_name(
            status
        )

        if created_at_utc is None:
            created_at_utc = datetime.now(
                timezone.utc
            )

        if status == cp_model.MODEL_INVALID:
            raise ValueError(
                "Model CP-SAT został uznany za niepoprawny"
            )

        if status == cp_model.UNKNOWN:
            raise RuntimeError(
                "CP-SAT zakończył pracę bez znalezienia "
                "rozwiązania i bez dowodu niewykonalności"
            )

        if status == cp_model.INFEASIBLE:
            return self._build_infeasible_schedule(
                schedule_id=schedule_id,
                name=name,
                created_at_utc=created_at_utc,
                solver_runtime_s=solver_runtime_s,
            )

        if status not in {
            cp_model.OPTIMAL,
            cp_model.FEASIBLE,
        }:
            raise RuntimeError(
                f"Nieobsługiwany status CP-SAT: "
                f"{self.last_solver_status}"
            )

        selected_opportunities = [
            opportunity
            for opportunity in self._candidate_opportunities
            if solver.value(
                self._selection_variables[
                    opportunity.opportunity_id
                ]
            )
            == 1
        ]

        objective_contributions = (
            self._calculate_objective_contributions(
                selected_opportunities
            )
        )

        resource_result = None
        if self.config.enable_downlink_planning:
            assert self.downlink_set is not None
            planned_amounts_mb = {
                identifier: (
                    solver.value(variable) / self.config.resource_scale
                )
                for identifier, variable in self._downlink_amount_variables.items()
                if solver.value(variable) > 0
            }
            resource_result = evaluate_planned_downlinks(
                catalog=self.catalog,
                acquisitions=selected_opportunities,
                downlink_set=self.downlink_set,
                planned_amounts_mb=planned_amounts_mb,
                memory_reserve_ratio=self.config.memory_reserve_ratio,
                require_full_downlink=self.config.require_full_downlink,
                downlink_capacity_reserve_ratio=(
                    self.config.downlink_capacity_reserve_ratio
                ),
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
                selected_opportunities,
                key=lambda item: (
                    item.start_utc,
                    item.satellite_id,
                    item.opportunity_id,
                ),
            )
        ]

        selected_by_request: dict[str, list[AcquisitionOpportunity]] = (
            defaultdict(list)
        )
        for opportunity in selected_opportunities:
            selected_by_request[opportunity.request_id].append(opportunity)
        selected_request_ids = {
            request.request_id
            for request in self.request_set.active_requests
            if request_is_fulfilled(
                request,
                selected_by_request.get(request.request_id, []),
            )
        }

        unassigned_request_ids = sorted(
            request.request_id
            for request in self.request_set.active_requests
            if request.request_id
            not in selected_request_ids
        )

        mandatory_unassigned = {
            request.request_id
            for request in self.request_set.mandatory_requests
            if request.request_id
            not in selected_request_ids
        }

        if mandatory_unassigned:
            schedule_status = ScheduleStatus.INFEASIBLE
        else:
            schedule_status = ScheduleStatus.FEASIBLE
        if resource_result is not None and not resource_result.feasible:
            schedule_status = ScheduleStatus.INFEASIBLE

        objective_value = round(
            sum(
                entry.objective_contribution
                for entry in entries
            ),
            6,
        )

        return Schedule(
            schedule_id=schedule_id,
            name=name,
            horizon_start_utc=(
                self.request_set.horizon_start_utc
            ),
            horizon_end_utc=(
                self.request_set.horizon_end_utc
            ),
            created_at_utc=created_at_utc,
            algorithm=PlanningAlgorithm.CP_SAT,
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
            memory_reserve_ratio=(
                self.config.memory_reserve_ratio
            ),
            objective_value=objective_value,
            solver_runtime_s=solver_runtime_s,
            unassigned_request_ids=(
                unassigned_request_ids
            ),
            notes=(
                "Harmonogram wygenerowany przez CP-SAT. "
                f"Status solvera: {self.last_solver_status}. "
                "Nagroda priorytetowa jest naliczana raz "
                "na zrealizowane zlecenie. "
                f"Liczba stałych akwizycji: "
                f"{len(self.fixed_assignments)}. "
                + (
                    "Model zawiera zmienne objętości downlinku i dynamiczne "
                    "ograniczenia pamięci. "
                    if self.config.enable_downlink_planning
                    else ""
                )
            ),
        )

    def _build_model(
        self,
    ) -> cp_model.CpModel:
        model = cp_model.CpModel()

        self._selection_variables = {
            opportunity.opportunity_id: (
                model.new_bool_var(
                    self._variable_name(
                        "select",
                        opportunity.opportunity_id,
                    )
                )
            )
            for opportunity in self._candidate_opportunities
        }

        self._request_fulfilled_variables = {}
        self._dual_optional_second_variables = {}
        self._downlink_used_variables = {}
        self._downlink_amount_variables = {}

        if self.config.enable_downlink_planning:
            for downlink in self._candidate_downlinks:
                identifier = downlink.downlink_opportunity_id
                used = model.new_bool_var(
                    self._variable_name("downlink_used", identifier)
                )
                capacity = self._scale_resource(
                    downlink.capacity_mb
                    * (1.0 - self.config.downlink_capacity_reserve_ratio)
                )
                amount = model.new_int_var(
                    0,
                    max(0, capacity),
                    self._variable_name("downlink_amount", identifier),
                )
                model.add(amount <= capacity * used)
                model.add(amount >= used)
                self._downlink_used_variables[identifier] = used
                self._downlink_amount_variables[identifier] = amount

        if self.solution_hint_ids:
            for opportunity_id, variable in self._selection_variables.items():
                model.add_hint(
                    variable,
                    1 if opportunity_id in self.solution_hint_ids else 0,
                )

        self._add_request_constraints(model)
        self._add_fixed_opportunity_constraints(model)
        self._add_satellite_constraints(model)
        if self.config.enable_downlink_planning:
            self._add_downlink_constraints(model)
        self._set_objective(model)

        return model

    def _add_request_constraints(
        self,
        model: cp_model.CpModel,
    ) -> None:
        for request in self.request_set.active_requests:
            candidates = self._opportunities_by_request.get(
                request.request_id,
                [],
            )

            candidate_variables = [
                self._selection_variables[
                    opportunity.opportunity_id
                ]
                for opportunity in candidates
            ]

            sar_variables = [
                self._selection_variables[
                    opportunity.opportunity_id
                ]
                for opportunity in candidates
                if opportunity.sensor_type
                == SensorType.SAR
            ]

            optical_variables = [
                self._selection_variables[
                    opportunity.opportunity_id
                ]
                for opportunity in candidates
                if opportunity.sensor_type
                == SensorType.OPTICAL
            ]

            fulfilled = model.new_bool_var(
                self._variable_name(
                    "fulfilled",
                    request.request_id,
                )
            )

            self._request_fulfilled_variables[
                request.request_id
            ] = fulfilled

            if request.request_mode == RequestMode.SINGLE:
                model.add(
                    fulfilled
                    == sum(candidate_variables)
                )

            elif (
                request.request_mode
                == RequestMode.DUAL_OPTIONAL
            ):
                sar_total = sum(sar_variables)
                optical_total = sum(optical_variables)
                total = (
                    sar_total
                    + optical_total
                )

                if sar_variables:
                    model.add(
                        sar_total <= 1
                    )

                if optical_variables:
                    model.add(
                        optical_total <= 1
                    )

                model.add(
                    fulfilled <= total
                )
                model.add(
                    total <= 2 * fulfilled
                )

                second_acquisition = (
                    model.new_bool_var(
                        self._variable_name(
                            "dual_second",
                            request.request_id,
                        )
                    )
                )

                self._dual_optional_second_variables[
                    request.request_id
                ] = second_acquisition

                model.add(
                    second_acquisition
                    <= sar_total
                )
                model.add(
                    second_acquisition
                    <= optical_total
                )
                model.add(
                    second_acquisition
                    >= (
                        sar_total
                        + optical_total
                        - 1
                    )
                )

            else:
                sar_total = sum(sar_variables)
                optical_total = sum(optical_variables)

                model.add(
                    fulfilled == sar_total
                )
                model.add(
                    fulfilled == optical_total
                )

            if request.request_mode != RequestMode.SINGLE:
                for sar_opportunity in candidates:
                    if sar_opportunity.sensor_type != SensorType.SAR:
                        continue
                    for optical_opportunity in candidates:
                        if (
                            optical_opportunity.sensor_type
                            != SensorType.OPTICAL
                        ):
                            continue
                        if dual_pair_is_compatible(
                            request,
                            sar_opportunity,
                            optical_opportunity,
                        ):
                            continue
                        model.add(
                            self._selection_variables[
                                sar_opportunity.opportunity_id
                            ]
                            + self._selection_variables[
                                optical_opportunity.opportunity_id
                            ]
                            <= 1
                        )

            if (
                request.is_mandatory
                and self.config.force_mandatory_requests
            ):
                model.add(
                    fulfilled == 1
                )

    def _add_fixed_opportunity_constraints(
        self,
        model: cp_model.CpModel,
    ) -> None:
        for opportunity in self._candidate_opportunities:
            variable = self._selection_variables[
                opportunity.opportunity_id
            ]

            if (
                opportunity.opportunity_id
                in self._fixed_assignments_by_id
            ):
                model.add(
                    variable == 1
                )

            elif opportunity.opportunity_id in self.fixed_selection:
                model.add(
                    variable
                    == int(self.fixed_selection[opportunity.opportunity_id])
                )

            elif (
                self.frozen_until_utc is not None
                and opportunity.start_utc
                < self.frozen_until_utc
            ):
                model.add(
                    variable == 0
                )

    def _add_satellite_constraints(
        self,
        model: cp_model.CpModel,
    ) -> None:
        for satellite in self.catalog.satellites:
            opportunities = (
                self._opportunities_by_satellite.get(
                    satellite.satellite_id,
                    [],
                )
            )

            if not opportunities:
                continue

            variables = [
                self._selection_variables[
                    opportunity.opportunity_id
                ]
                for opportunity in opportunities
            ]

            if not satellite.is_available_for_planning:
                for variable in variables:
                    model.add(
                        variable == 0
                    )

                continue

            model.add(
                sum(variables)
                <= satellite.max_acquisitions_per_day
            )

            duration_expression = sum(
                self._scale_resource(
                    opportunity.duration_s
                )
                * self._selection_variables[
                    opportunity.opportunity_id
                ]
                for opportunity in opportunities
            )

            model.add(
                duration_expression
                <= self._scale_resource(
                    satellite.max_imaging_time_per_day_s
                )
            )

            if not self.config.enable_downlink_planning:
                planning_memory_limit_mb = (
                    satellite.memory_capacity_mb
                    * (
                        1.0
                        - self.config.memory_reserve_ratio
                    )
                )

                available_memory_mb = (
                    planning_memory_limit_mb
                    - satellite.initial_memory_usage_mb
                )

                if available_memory_mb < -1e-9:
                    contradiction = model.new_bool_var(
                        self._variable_name(
                            "memory_contradiction",
                            satellite.satellite_id,
                        )
                    )

                    model.add(
                        contradiction == 0
                    )
                    model.add(
                        contradiction == 1
                    )
                else:
                    data_expression = sum(
                        self._scale_resource(
                            opportunity.estimated_data_volume_mb
                        )
                        * self._selection_variables[
                            opportunity.opportunity_id
                        ]
                        for opportunity in opportunities
                    )

                    model.add(
                        data_expression
                        <= self._scale_resource(
                            max(
                                0.0,
                                available_memory_mb,
                            )
                        )
                    )

            if self.config.use_dynamic_transition_model:
                sar_opportunities = [
                    opportunity
                    for opportunity in opportunities
                    if opportunity.sensor_type == SensorType.SAR
                ]
                pass_index = build_pass_index(
                    sar_opportunities,
                    pass_gap_s=self.config.sar_pass_gap_s,
                )
                variables_by_pass: dict[int, list[cp_model.IntVar]] = (
                    defaultdict(list)
                )
                for opportunity in sar_opportunities:
                    variables_by_pass[
                        pass_index[opportunity.opportunity_id]
                    ].append(
                        self._selection_variables[opportunity.opportunity_id]
                    )
                for pass_variables in variables_by_pass.values():
                    model.add(
                        sum(pass_variables)
                        <= self.config.sar_max_acquisitions_per_pass
                    )

            self._add_transition_conflicts(
                model=model,
                satellite=satellite,
                opportunities=opportunities,
            )

    def _add_downlink_constraints(self, model: cp_model.CpModel) -> None:
        assert self.downlink_set is not None

        # Jedna antena satelity nie może obsługiwać nakładających się kontaktów.
        for opportunities in self._downlinks_by_satellite.values():
            ordered = sorted(
                opportunities,
                key=lambda item: (
                    item.start_utc,
                    item.end_utc,
                    item.downlink_opportunity_id,
                ),
            )
            for index, first in enumerate(ordered):
                for second in ordered[index + 1 :]:
                    if second.start_utc >= first.end_utc:
                        break
                    model.add(
                        self._downlink_used_variables[
                            first.downlink_opportunity_id
                        ]
                        + self._downlink_used_variables[
                            second.downlink_opportunity_id
                        ]
                        <= 1
                    )

        # Stacja może posiadać więcej niż jeden równoległy kanał odbiorczy.
        for station_id, opportunities in self._downlinks_by_station.items():
            station = self.catalog.get_ground_station(station_id)
            boundaries = sorted(
                {item.start_utc for item in opportunities}
                | {item.end_utc for item in opportunities}
            )
            for start, end in zip(boundaries, boundaries[1:]):
                if start >= end:
                    continue
                active = [
                    self._downlink_used_variables[item.downlink_opportunity_id]
                    for item in opportunities
                    if item.start_utc < end and start < item.end_utc
                ]
                if active:
                    model.add(
                        sum(active) <= station.max_simultaneous_contacts
                    )

        if not self.config.allow_simultaneous_imaging_downlink:
            for downlink in self._candidate_downlinks:
                used = self._downlink_used_variables[
                    downlink.downlink_opportunity_id
                ]
                for acquisition in self._opportunities_by_satellite.get(
                    downlink.satellite_id, []
                ):
                    if (
                        acquisition.start_utc < downlink.end_utc
                        and downlink.start_utc < acquisition.end_utc
                    ):
                        model.add(
                            used
                            + self._selection_variables[
                                acquisition.opportunity_id
                            ]
                            <= 1
                        )

        for satellite in self.catalog.satellites:
            acquisitions = self._opportunities_by_satellite.get(
                satellite.satellite_id, []
            )
            downlinks = self._downlinks_by_satellite.get(
                satellite.satellite_id, []
            )
            initial_memory = self._scale_resource(
                satellite.initial_memory_usage_mb
            )
            memory_limit = self._scale_resource(
                satellite.memory_capacity_mb
                * (1.0 - self.config.memory_reserve_ratio)
            )

            if initial_memory > memory_limit:
                contradiction = model.new_bool_var(
                    self._variable_name(
                        "initial_memory_contradiction",
                        satellite.satellite_id,
                    )
                )
                model.add(contradiction == 0)
                model.add(contradiction == 1)

            if not downlinks:
                if self.config.require_full_downlink:
                    for acquisition in acquisitions:
                        model.add(
                            self._selection_variables[
                                acquisition.opportunity_id
                            ]
                            == 0
                        )
                    if initial_memory > 0:
                        contradiction = model.new_bool_var(
                            self._variable_name(
                                "missing_downlink_contradiction",
                                satellite.satellite_id,
                            )
                        )
                        model.add(contradiction == 0)
                        model.add(contradiction == 1)
                else:
                    acquired_without_downlink = [
                        self._scale_resource(
                            acquisition.estimated_data_volume_mb
                        )
                        * self._selection_variables[
                            acquisition.opportunity_id
                        ]
                        for acquisition in acquisitions
                    ]
                    model.add(
                        initial_memory + sum(acquired_without_downlink)
                        <= memory_limit
                    )
                continue

            # Ilość wysłana w danym oknie nie może obejmować danych,
            # które pojawią się dopiero po jego rozpoczęciu.
            for current in downlinks:
                previous_downloads = [
                    self._downlink_amount_variables[
                        item.downlink_opportunity_id
                    ]
                    for item in downlinks
                    if item.end_utc <= current.start_utc
                ]
                available_acquisitions = [
                    self._scale_resource(item.estimated_data_volume_mb)
                    * self._selection_variables[item.opportunity_id]
                    for item in acquisitions
                    if item.end_utc <= current.start_utc
                ]
                model.add(
                    self._downlink_amount_variables[
                        current.downlink_opportunity_id
                    ]
                    + sum(previous_downloads)
                    <= initial_memory + sum(available_acquisitions)
                )

            checkpoints = sorted(
                {item.end_utc for item in acquisitions}
                | {item.end_utc for item in downlinks}
            )
            for checkpoint in checkpoints:
                acquired = [
                    self._scale_resource(item.estimated_data_volume_mb)
                    * self._selection_variables[item.opportunity_id]
                    for item in acquisitions
                    if item.end_utc <= checkpoint
                ]
                # Dane są zwalniane dopiero po zakończeniu kontaktu.
                # Przy wspólnym znaczniku czasu akwizycja jest księgowana
                # przed downlinkiem, dlatego bieżący kontakt nie może ukryć
                # chwilowego przekroczenia pamięci.
                downloaded = [
                    self._downlink_amount_variables[
                        item.downlink_opportunity_id
                    ]
                    for item in downlinks
                    if item.end_utc < checkpoint
                ]
                model.add(
                    initial_memory + sum(acquired) - sum(downloaded)
                    <= memory_limit
                )

            all_acquired = [
                self._scale_resource(item.estimated_data_volume_mb)
                * self._selection_variables[item.opportunity_id]
                for item in acquisitions
            ]
            all_downloaded = [
                self._downlink_amount_variables[item.downlink_opportunity_id]
                for item in downlinks
            ]
            model.add(sum(all_downloaded) <= initial_memory + sum(all_acquired))
            if self.config.require_full_downlink:
                model.add(
                    sum(all_downloaded) >= initial_memory + sum(all_acquired)
                )

    def _add_transition_conflicts(
        self,
        *,
        model: cp_model.CpModel,
        satellite: Satellite,
        opportunities: list[AcquisitionOpportunity],
    ) -> None:
        sorted_opportunities = sorted(
            opportunities,
            key=lambda opportunity: (
                opportunity.start_utc,
                opportunity.end_utc,
                opportunity.opportunity_id,
            ),
        )

        sensor = self._sensors_by_id[satellite.sensor_id]
        for first_index, first in enumerate(sorted_opportunities):
            for second in sorted_opportunities[first_index + 1 :]:
                transition_s = required_transition_time_s(
                    first=first,
                    second=second,
                    satellite=satellite,
                    sensor=sensor,
                    modes_by_id=self._modes_by_id,
                    config=self.config,
                )
                if (
                    first.end_utc + timedelta(seconds=transition_s)
                    <= second.start_utc
                ):
                    continue

                model.add(
                    self._selection_variables[first.opportunity_id]
                    + self._selection_variables[second.opportunity_id]
                    <= 1
                )

    def _set_objective(
        self,
        model: cp_model.CpModel,
    ) -> None:
        objective_terms = []

        for opportunity in self._candidate_opportunities:
            coefficient = self._scale_objective(
                self._acquisition_score(
                    opportunity
                )
            )

            objective_terms.append(
                coefficient
                * self._selection_variables[
                    opportunity.opportunity_id
                ]
            )

        for request in self.request_set.active_requests:
            request_coefficient = (
                self._scale_objective(
                    self._request_reward(
                        request
                    )
                )
            )

            objective_terms.append(
                request_coefficient
                * self._request_fulfilled_variables[
                    request.request_id
                ]
            )

            second_variable = (
                self._dual_optional_second_variables.get(
                    request.request_id
                )
            )

            if second_variable is not None:
                second_coefficient = (
                    self._scale_objective(
                        self.config
                        .dual_optional_second_bonus
                    )
                )

                objective_terms.append(
                    second_coefficient
                    * second_variable
                )

        model.maximize(
            sum(objective_terms)
        )

    def _build_infeasible_schedule(
        self,
        *,
        schedule_id: str,
        name: str,
        created_at_utc: datetime,
        solver_runtime_s: float,
    ) -> Schedule:
        fixed_opportunities = [
            self._feasible_opportunities_by_id[
                assignment.opportunity_id
            ]
            for assignment in self.fixed_assignments
        ]

        fixed_contributions = (
            self._calculate_objective_contributions(
                fixed_opportunities
            )
        )

        entries = [
            self._create_schedule_entry(
                opportunity=opportunity,
                objective_contribution=(
                    fixed_contributions.get(
                        opportunity.opportunity_id,
                        self._acquisition_score(
                            opportunity
                        ),
                    )
                ),
            )
            for opportunity in sorted(
                fixed_opportunities,
                key=lambda item: (
                    item.start_utc,
                    item.satellite_id,
                    item.opportunity_id,
                ),
            )
        ]

        fixed_by_request: dict[str, list[AcquisitionOpportunity]] = (
            defaultdict(list)
        )
        for opportunity in fixed_opportunities:
            fixed_by_request[opportunity.request_id].append(opportunity)
        selected_request_ids = {
            request.request_id
            for request in self.request_set.active_requests
            if request_is_fulfilled(
                request,
                fixed_by_request.get(request.request_id, []),
            )
        }

        return Schedule(
            schedule_id=schedule_id,
            name=name,
            horizon_start_utc=(
                self.request_set.horizon_start_utc
            ),
            horizon_end_utc=(
                self.request_set.horizon_end_utc
            ),
            created_at_utc=created_at_utc,
            algorithm=PlanningAlgorithm.CP_SAT,
            status=ScheduleStatus.INFEASIBLE,
            entries=entries,
            frozen_until_utc=self.frozen_until_utc,
            memory_reserve_ratio=(
                self.config.memory_reserve_ratio
            ),
            objective_value=round(
                sum(
                    entry.objective_contribution
                    for entry in entries
                ),
                6,
            ),
            solver_runtime_s=solver_runtime_s,
            unassigned_request_ids=sorted(
                request.request_id
                for request
                in self.request_set.active_requests
                if request.request_id
                not in selected_request_ids
            ),
            notes=(
                "Model CP-SAT jest niewykonalny. "
                f"Status solvera: {self.last_solver_status}. "
                "Zachowano stałe akwizycje z okresu "
                "zamrożonego."
            ),
        )

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
        selected_opportunities: list[AcquisitionOpportunity],
    ) -> dict[str, float]:
        return calculate_objective_contributions(
            request_set=self.request_set,
            selected_opportunities=selected_opportunities,
            config=self.config,
        )

    def _scale_objective(
        self,
        value: float,
    ) -> int:
        return int(
            round(
                value
                * self.config.objective_scale
            )
        )

    def _scale_resource(
        self,
        value: float,
    ) -> int:
        return int(
            round(
                value
                * self.config.resource_scale
            )
        )

    @staticmethod
    def _variable_name(
        prefix: str,
        identifier: str,
    ) -> str:
        normalized_identifier = (
            identifier
            .replace("-", "_")
            .replace(" ", "_")
        )

        return (
            f"{prefix}_{normalized_identifier}"
        )

    def _create_schedule_entry(
        self,
        *,
        opportunity: AcquisitionOpportunity,
        objective_contribution: float,
    ) -> ScheduleEntry:
        entry_suffix = (
            opportunity.opportunity_id.removeprefix(
                "OPP-"
            )
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


def build_cp_sat_schedule(
    catalog: SystemCatalog,
    request_set: ObservationRequestSet,
    opportunity_set: AcquisitionOpportunitySet,
    *,
    downlink_set: DownlinkOpportunitySet | None = None,
    config: CpSatPlannerConfig | None = None,
    schedule_id: str = "SCHEDULE-CP-SAT-001",
    name: str = "Dobowy harmonogram CP-SAT",
    created_at_utc: datetime | None = None,
    fixed_assignments: Iterable[
        FixedOpportunityAssignment
    ] | None = None,
    frozen_until_utc: datetime | None = None,
    fixed_selection: Mapping[str, bool] | None = None,
    solution_hint_ids: Iterable[str] | None = None,
) -> Schedule:
    """Funkcja pomocnicza budująca harmonogram CP-SAT."""

    scheduler = CpSatScheduler(
        catalog=catalog,
        request_set=request_set,
        opportunity_set=opportunity_set,
        downlink_set=downlink_set,
        config=config,
        fixed_assignments=fixed_assignments,
        frozen_until_utc=frozen_until_utc,
        fixed_selection=fixed_selection,
        solution_hint_ids=solution_hint_ids,
    )

    return scheduler.build_schedule(
        schedule_id=schedule_id,
        name=name,
        created_at_utc=created_at_utc,
    )