from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from time import perf_counter

from ortools.sat.python import cp_model

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
class CpSatPlannerConfig:
    """Konfiguracja modelu optymalizacyjnego CP-SAT."""

    memory_reserve_ratio: float = 0.0

    priority_weight: float = 10.0
    quality_weight: float = 3.0
    coverage_weight: float = 2.0
    mandatory_bonus: float = 100.0

    dual_optional_second_bonus: float = 5.0

    force_mandatory_requests: bool = True

    max_time_s: float = 30.0
    num_search_workers: int = 1
    random_seed: int = 20260715
    log_search_progress: bool = False

    objective_scale: int = 1_000_000
    resource_scale: int = 1_000

    def __post_init__(self) -> None:
        if not 0.0 <= self.memory_reserve_ratio <= 1.0:
            raise ValueError(
                "memory_reserve_ratio musi należeć "
                "do zakresu [0, 1]"
            )

        if self.max_time_s <= 0.0:
            raise ValueError(
                "max_time_s musi być większe od zera"
            )

        if self.num_search_workers <= 0:
            raise ValueError(
                "num_search_workers musi być większe od zera"
            )

        if self.random_seed < 0:
            raise ValueError(
                "random_seed nie może być ujemny"
            )

        if self.objective_scale <= 0:
            raise ValueError(
                "objective_scale musi być większe od zera"
            )

        if self.resource_scale <= 0:
            raise ValueError(
                "resource_scale musi być większe od zera"
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


class CpSatScheduler:
    """Dokładny model harmonogramowania wykorzystujący CP-SAT."""

    def __init__(
        self,
        catalog: SystemCatalog,
        request_set: ObservationRequestSet,
        opportunity_set: AcquisitionOpportunitySet,
        config: CpSatPlannerConfig | None = None,
    ) -> None:
        self.catalog = catalog
        self.request_set = request_set
        self.opportunity_set = opportunity_set
        self.config = config or CpSatPlannerConfig()

        self.last_solver_status: str | None = None

        self._satellites_by_id = {
            satellite.satellite_id: satellite
            for satellite in catalog.satellites
        }

        self._sensors_by_id = {
            sensor.sensor_id: sensor
            for sensor in catalog.sensors
        }

        self._active_requests_by_id = {
            request.request_id: request
            for request in request_set.active_requests
        }

        self._candidate_opportunities = [
            opportunity
            for opportunity
            in opportunity_set.feasible_opportunities
            if opportunity.request_id
            in self._active_requests_by_id
        ]

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

        selected_request_ids = {
            entry.request_id
            for entry in entries
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
            frozen_until_utc=None,
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
                "na zrealizowane zlecenie."
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

        self._add_request_constraints(model)
        self._add_satellite_constraints(model)
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

            if (
                request.is_mandatory
                and self.config.force_mandatory_requests
            ):
                model.add(
                    fulfilled == 1
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

            self._add_transition_conflicts(
                model=model,
                satellite=satellite,
                opportunities=opportunities,
            )

    def _add_transition_conflicts(
        self,
        *,
        model: cp_model.CpModel,
        satellite: Satellite,
        opportunities: list[
            AcquisitionOpportunity
        ],
    ) -> None:
        transition_delta = timedelta(
            seconds=self._transition_time_s(
                satellite
            )
        )

        sorted_opportunities = sorted(
            opportunities,
            key=lambda opportunity: (
                opportunity.start_utc,
                opportunity.end_utc,
                opportunity.opportunity_id,
            ),
        )

        for first_index, first in enumerate(
            sorted_opportunities
        ):
            for second in sorted_opportunities[
                first_index + 1:
            ]:
                if (
                    first.end_utc
                    + transition_delta
                    <= second.start_utc
                ):
                    break

                model.add(
                    self._selection_variables[
                        first.opportunity_id
                    ]
                    + self._selection_variables[
                        second.opportunity_id
                    ]
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
            entries=[],
            frozen_until_utc=None,
            memory_reserve_ratio=(
                self.config.memory_reserve_ratio
            ),
            objective_value=0.0,
            solver_runtime_s=solver_runtime_s,
            unassigned_request_ids=sorted(
                request.request_id
                for request
                in self.request_set.active_requests
            ),
            notes=(
                "Model CP-SAT jest niewykonalny. "
                f"Status solvera: {self.last_solver_status}."
            ),
        )

    def _request_reward(
        self,
        request: ObservationRequest,
    ) -> float:
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
        selected_opportunities: list[
            AcquisitionOpportunity
        ],
    ) -> dict[str, float]:
        selected_by_request: dict[
            str,
            list[AcquisitionOpportunity],
        ] = defaultdict(list)

        for opportunity in selected_opportunities:
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
                    + self._acquisition_score(
                        opportunity
                    ),
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
                        + self._acquisition_score(
                            opportunity
                        ),
                        6,
                    )

                continue

            ordered_opportunities = sorted(
                opportunities,
                key=lambda opportunity: (
                    -self._acquisition_score(
                        opportunity
                    ),
                    opportunity.opportunity_id,
                ),
            )

            primary_opportunity = (
                ordered_opportunities[0]
            )

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
                    + self.config
                    .dual_optional_second_bonus,
                    6,
                )

        return contributions

    def _transition_time_s(
        self,
        satellite: Satellite,
    ) -> float:
        sensor: Sensor = self._sensors_by_id[
            satellite.sensor_id
        ]

        sensor_transition_s = (
            sensor.warmup_time_s
            + sensor.cooldown_time_s
        )

        return max(
            satellite.minimum_transition_time_s,
            sensor_transition_s,
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
                objective_contribution
            ),
            lock_reason=None,
            notes=None,
        )


def build_cp_sat_schedule(
    catalog: SystemCatalog,
    request_set: ObservationRequestSet,
    opportunity_set: AcquisitionOpportunitySet,
    *,
    config: CpSatPlannerConfig | None = None,
    schedule_id: str = "SCHEDULE-CP-SAT-001",
    name: str = "Dobowy harmonogram CP-SAT",
    created_at_utc: datetime | None = None,
) -> Schedule:
    """Funkcja pomocnicza budująca harmonogram CP-SAT."""

    scheduler = CpSatScheduler(
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