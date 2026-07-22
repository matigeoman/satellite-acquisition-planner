from __future__ import annotations

import re
from datetime import datetime, timezone
from time import perf_counter
from typing import Iterable

from app.analysis.schedule import analyze_schedule
from app.models.enums import PlanningAlgorithm
from app.models.schedule import Schedule
from app.planning.config import HybridPlannerConfig
from app.planning.cp_sat import (
    CpSatPlannerConfig,
    CpSatScheduler,
)
from app.planning.hybrid import HybridScheduler
from app.planning.fixed import FixedOpportunityAssignment
from app.planning.greedy import (
    GreedyPlannerConfig,
    build_greedy_schedule,
)
from app.services.contracts.planning import (
    PlanningOptions,
    PlanningResult,
)
from app.services.scenario_service import LoadedScenario


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

        elif options.algorithm == PlanningAlgorithm.HYBRID:
            schedule, solver_status = self._run_hybrid(
                scenario=scenario,
                options=options,
                schedule_id=resolved_schedule_id,
                schedule_name=resolved_schedule_name,
                created_at_utc=created_at,
                fixed_assignments=normalized_fixed_assignments,
                frozen_until_utc=normalized_frozen_until,
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
            use_dynamic_transition_model=(
                options.use_dynamic_transition_model
            ),
            eo_stabilization_time_s=options.eo_stabilization_time_s,
            sar_stabilization_time_s=options.sar_stabilization_time_s,
            sar_side_switch_penalty_s=(
                options.sar_side_switch_penalty_s
            ),
            sar_mode_switch_penalty_s=(
                options.sar_mode_switch_penalty_s
            ),
            sar_slew_rate_deg_s=options.sar_slew_rate_deg_s,
            sar_pass_gap_s=options.sar_pass_gap_s,
            sar_max_acquisitions_per_pass=(
                options.sar_max_acquisitions_per_pass
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
            use_opportunity_cost_heuristic=(
                options.use_opportunity_cost_heuristic
            ),
            scarcity_bonus_weight=options.scarcity_bonus_weight,
            conflict_cost_weight=options.conflict_cost_weight,
            duration_cost_weight=options.duration_cost_weight,
            memory_cost_weight=options.memory_cost_weight,
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
            use_dynamic_transition_model=(
                options.use_dynamic_transition_model
            ),
            eo_stabilization_time_s=options.eo_stabilization_time_s,
            sar_stabilization_time_s=options.sar_stabilization_time_s,
            sar_side_switch_penalty_s=(
                options.sar_side_switch_penalty_s
            ),
            sar_mode_switch_penalty_s=(
                options.sar_mode_switch_penalty_s
            ),
            sar_slew_rate_deg_s=options.sar_slew_rate_deg_s,
            sar_pass_gap_s=options.sar_pass_gap_s,
            sar_max_acquisitions_per_pass=(
                options.sar_max_acquisitions_per_pass
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

    def _run_hybrid(
        self,
        *,
        scenario: LoadedScenario,
        options: PlanningOptions,
        schedule_id: str,
        schedule_name: str,
        created_at_utc: datetime,
        fixed_assignments: tuple[FixedOpportunityAssignment, ...],
        frozen_until_utc: datetime | None,
    ) -> tuple[Schedule, str]:
        config = HybridPlannerConfig(
            memory_reserve_ratio=options.memory_reserve_ratio,
            use_dynamic_transition_model=options.use_dynamic_transition_model,
            eo_stabilization_time_s=options.eo_stabilization_time_s,
            sar_stabilization_time_s=options.sar_stabilization_time_s,
            sar_side_switch_penalty_s=options.sar_side_switch_penalty_s,
            sar_mode_switch_penalty_s=options.sar_mode_switch_penalty_s,
            sar_slew_rate_deg_s=options.sar_slew_rate_deg_s,
            sar_pass_gap_s=options.sar_pass_gap_s,
            sar_max_acquisitions_per_pass=(
                options.sar_max_acquisitions_per_pass
            ),
            priority_weight=options.priority_weight,
            quality_weight=options.quality_weight,
            coverage_weight=options.coverage_weight,
            mandatory_bonus=options.mandatory_bonus,
            dual_optional_second_bonus=options.dual_optional_second_bonus,
            scarcity_bonus_weight=options.scarcity_bonus_weight,
            conflict_cost_weight=options.conflict_cost_weight,
            duration_cost_weight=options.duration_cost_weight,
            memory_cost_weight=options.memory_cost_weight,
            force_mandatory_requests=(
                options.cp_sat_force_mandatory_requests
            ),
            max_time_s=options.cp_sat_time_limit_s,
            num_search_workers=options.cp_sat_num_search_workers,
            random_seed=options.cp_sat_random_seed,
            log_search_progress=options.cp_sat_log_search_progress,
            neighborhood_request_limit=(
                options.hybrid_neighborhood_request_limit
            ),
            max_neighborhoods=options.hybrid_max_neighborhoods,
            minimum_improvement=options.hybrid_minimum_improvement,
        )
        scheduler = HybridScheduler(
            catalog=scenario.catalog,
            request_set=scenario.request_set,
            opportunity_set=scenario.opportunity_set,
            config=config,
            fixed_assignments=fixed_assignments,
            frozen_until_utc=frozen_until_utc,
        )
        schedule = scheduler.build_schedule(
            schedule_id=schedule_id,
            name=schedule_name,
            created_at_utc=created_at_utc,
        )
        return schedule, scheduler.last_solver_status or "UNKNOWN"

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


__all__ = ["PlanningOptions", "PlanningResult", "PlanningService"]
