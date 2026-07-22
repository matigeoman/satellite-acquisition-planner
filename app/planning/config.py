from __future__ import annotations

from dataclasses import dataclass


def _validate_memory_reserve_ratio(value: float) -> None:
    if not 0.0 <= value <= 1.0:
        raise ValueError("memory_reserve_ratio musi należeć do zakresu [0, 1]")


def _validate_nonnegative_values(values: dict[str, float]) -> None:
    for name, value in values.items():
        if value < 0.0:
            raise ValueError(f"{name} nie może być wartością ujemną")


def _validate_objective_weights(
    *,
    priority_weight: float,
    quality_weight: float,
    coverage_weight: float,
    mandatory_bonus: float,
    dual_optional_second_bonus: float,
) -> None:
    _validate_nonnegative_values(
        {
            "priority_weight": priority_weight,
            "quality_weight": quality_weight,
            "coverage_weight": coverage_weight,
            "mandatory_bonus": mandatory_bonus,
            "dual_optional_second_bonus": dual_optional_second_bonus,
        }
    )


def _validate_research_heuristic_weights(
    *,
    scarcity_bonus_weight: float,
    conflict_cost_weight: float,
    duration_cost_weight: float,
    memory_cost_weight: float,
) -> None:
    _validate_nonnegative_values(
        {
            "scarcity_bonus_weight": scarcity_bonus_weight,
            "conflict_cost_weight": conflict_cost_weight,
            "duration_cost_weight": duration_cost_weight,
            "memory_cost_weight": memory_cost_weight,
        }
    )


def _validate_operational_parameters(
    *,
    eo_stabilization_time_s: float,
    sar_stabilization_time_s: float,
    sar_side_switch_penalty_s: float,
    sar_mode_switch_penalty_s: float,
    sar_slew_rate_deg_s: float,
    sar_pass_gap_s: float,
    sar_max_acquisitions_per_pass: int,
) -> None:
    _validate_nonnegative_values(
        {
            "eo_stabilization_time_s": eo_stabilization_time_s,
            "sar_stabilization_time_s": sar_stabilization_time_s,
            "sar_side_switch_penalty_s": sar_side_switch_penalty_s,
            "sar_mode_switch_penalty_s": sar_mode_switch_penalty_s,
            "sar_pass_gap_s": sar_pass_gap_s,
        }
    )
    if sar_slew_rate_deg_s <= 0.0:
        raise ValueError("sar_slew_rate_deg_s musi być większe od zera")
    if sar_max_acquisitions_per_pass <= 0:
        raise ValueError("sar_max_acquisitions_per_pass musi być większe od zera")


@dataclass(frozen=True)
class GreedyPlannerConfig:
    """Parametry ograniczeń i funkcji celu algorytmu Greedy."""

    memory_reserve_ratio: float = 0.0

    use_dynamic_transition_model: bool = False
    eo_stabilization_time_s: float = 3.0
    sar_stabilization_time_s: float = 10.0
    sar_side_switch_penalty_s: float = 60.0
    sar_mode_switch_penalty_s: float = 15.0
    sar_slew_rate_deg_s: float = 2.0
    sar_pass_gap_s: float = 900.0
    sar_max_acquisitions_per_pass: int = 3

    priority_weight: float = 10.0
    quality_weight: float = 3.0
    coverage_weight: float = 2.0
    mandatory_bonus: float = 100.0
    dual_optional_second_bonus: float = 5.0

    use_opportunity_cost_heuristic: bool = False
    scarcity_bonus_weight: float = 2.0
    conflict_cost_weight: float = 0.20
    duration_cost_weight: float = 0.010
    memory_cost_weight: float = 0.00010

    def __post_init__(self) -> None:
        _validate_memory_reserve_ratio(self.memory_reserve_ratio)
        _validate_operational_parameters(
            eo_stabilization_time_s=self.eo_stabilization_time_s,
            sar_stabilization_time_s=self.sar_stabilization_time_s,
            sar_side_switch_penalty_s=self.sar_side_switch_penalty_s,
            sar_mode_switch_penalty_s=self.sar_mode_switch_penalty_s,
            sar_slew_rate_deg_s=self.sar_slew_rate_deg_s,
            sar_pass_gap_s=self.sar_pass_gap_s,
            sar_max_acquisitions_per_pass=self.sar_max_acquisitions_per_pass,
        )
        _validate_objective_weights(
            priority_weight=self.priority_weight,
            quality_weight=self.quality_weight,
            coverage_weight=self.coverage_weight,
            mandatory_bonus=self.mandatory_bonus,
            dual_optional_second_bonus=self.dual_optional_second_bonus,
        )
        _validate_research_heuristic_weights(
            scarcity_bonus_weight=self.scarcity_bonus_weight,
            conflict_cost_weight=self.conflict_cost_weight,
            duration_cost_weight=self.duration_cost_weight,
            memory_cost_weight=self.memory_cost_weight,
        )


@dataclass(frozen=True)
class CpSatPlannerConfig:
    """Parametry ograniczeń, funkcji celu i solvera CP-SAT."""

    memory_reserve_ratio: float = 0.0

    use_dynamic_transition_model: bool = False
    eo_stabilization_time_s: float = 3.0
    sar_stabilization_time_s: float = 10.0
    sar_side_switch_penalty_s: float = 60.0
    sar_mode_switch_penalty_s: float = 15.0
    sar_slew_rate_deg_s: float = 2.0
    sar_pass_gap_s: float = 900.0
    sar_max_acquisitions_per_pass: int = 3

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
        _validate_memory_reserve_ratio(self.memory_reserve_ratio)
        _validate_operational_parameters(
            eo_stabilization_time_s=self.eo_stabilization_time_s,
            sar_stabilization_time_s=self.sar_stabilization_time_s,
            sar_side_switch_penalty_s=self.sar_side_switch_penalty_s,
            sar_mode_switch_penalty_s=self.sar_mode_switch_penalty_s,
            sar_slew_rate_deg_s=self.sar_slew_rate_deg_s,
            sar_pass_gap_s=self.sar_pass_gap_s,
            sar_max_acquisitions_per_pass=self.sar_max_acquisitions_per_pass,
        )
        _validate_objective_weights(
            priority_weight=self.priority_weight,
            quality_weight=self.quality_weight,
            coverage_weight=self.coverage_weight,
            mandatory_bonus=self.mandatory_bonus,
            dual_optional_second_bonus=self.dual_optional_second_bonus,
        )
        if self.max_time_s <= 0.0:
            raise ValueError("max_time_s musi być większe od zera")
        if self.num_search_workers <= 0:
            raise ValueError("num_search_workers musi być większe od zera")
        if self.random_seed < 0:
            raise ValueError("random_seed nie może być ujemny")
        if self.objective_scale <= 0:
            raise ValueError("objective_scale musi być większe od zera")
        if self.resource_scale <= 0:
            raise ValueError("resource_scale musi być większe od zera")


@dataclass(frozen=True)
class HybridPlannerConfig:
    """Konfiguracja hybrydy Greedy + lokalna poprawa CP-SAT."""

    memory_reserve_ratio: float = 0.0

    use_dynamic_transition_model: bool = False
    eo_stabilization_time_s: float = 3.0
    sar_stabilization_time_s: float = 10.0
    sar_side_switch_penalty_s: float = 60.0
    sar_mode_switch_penalty_s: float = 15.0
    sar_slew_rate_deg_s: float = 2.0
    sar_pass_gap_s: float = 900.0
    sar_max_acquisitions_per_pass: int = 3

    priority_weight: float = 10.0
    quality_weight: float = 3.0
    coverage_weight: float = 2.0
    mandatory_bonus: float = 100.0
    dual_optional_second_bonus: float = 5.0

    scarcity_bonus_weight: float = 2.0
    conflict_cost_weight: float = 0.20
    duration_cost_weight: float = 0.010
    memory_cost_weight: float = 0.00010

    force_mandatory_requests: bool = True
    max_time_s: float = 10.0
    num_search_workers: int = 1
    random_seed: int = 20260716
    log_search_progress: bool = False

    neighborhood_request_limit: int = 12
    max_neighborhoods: int = 6
    minimum_improvement: float = 1e-6

    def __post_init__(self) -> None:
        GreedyPlannerConfig(
            memory_reserve_ratio=self.memory_reserve_ratio,
            use_dynamic_transition_model=self.use_dynamic_transition_model,
            eo_stabilization_time_s=self.eo_stabilization_time_s,
            sar_stabilization_time_s=self.sar_stabilization_time_s,
            sar_side_switch_penalty_s=self.sar_side_switch_penalty_s,
            sar_mode_switch_penalty_s=self.sar_mode_switch_penalty_s,
            sar_slew_rate_deg_s=self.sar_slew_rate_deg_s,
            sar_pass_gap_s=self.sar_pass_gap_s,
            sar_max_acquisitions_per_pass=self.sar_max_acquisitions_per_pass,
            priority_weight=self.priority_weight,
            quality_weight=self.quality_weight,
            coverage_weight=self.coverage_weight,
            mandatory_bonus=self.mandatory_bonus,
            dual_optional_second_bonus=self.dual_optional_second_bonus,
            use_opportunity_cost_heuristic=True,
            scarcity_bonus_weight=self.scarcity_bonus_weight,
            conflict_cost_weight=self.conflict_cost_weight,
            duration_cost_weight=self.duration_cost_weight,
            memory_cost_weight=self.memory_cost_weight,
        )
        if self.max_time_s <= 0.0:
            raise ValueError("max_time_s musi być większe od zera")
        if self.num_search_workers <= 0:
            raise ValueError("num_search_workers musi być większe od zera")
        if self.random_seed < 0:
            raise ValueError("random_seed nie może być ujemny")
        if self.neighborhood_request_limit <= 0:
            raise ValueError("neighborhood_request_limit musi być dodatnie")
        if self.max_neighborhoods <= 0:
            raise ValueError("max_neighborhoods musi być dodatnie")
        if self.minimum_improvement < 0.0:
            raise ValueError("minimum_improvement nie może być ujemne")

    def greedy_config(self) -> GreedyPlannerConfig:
        return GreedyPlannerConfig(
            memory_reserve_ratio=self.memory_reserve_ratio,
            use_dynamic_transition_model=self.use_dynamic_transition_model,
            eo_stabilization_time_s=self.eo_stabilization_time_s,
            sar_stabilization_time_s=self.sar_stabilization_time_s,
            sar_side_switch_penalty_s=self.sar_side_switch_penalty_s,
            sar_mode_switch_penalty_s=self.sar_mode_switch_penalty_s,
            sar_slew_rate_deg_s=self.sar_slew_rate_deg_s,
            sar_pass_gap_s=self.sar_pass_gap_s,
            sar_max_acquisitions_per_pass=self.sar_max_acquisitions_per_pass,
            priority_weight=self.priority_weight,
            quality_weight=self.quality_weight,
            coverage_weight=self.coverage_weight,
            mandatory_bonus=self.mandatory_bonus,
            dual_optional_second_bonus=self.dual_optional_second_bonus,
            use_opportunity_cost_heuristic=True,
            scarcity_bonus_weight=self.scarcity_bonus_weight,
            conflict_cost_weight=self.conflict_cost_weight,
            duration_cost_weight=self.duration_cost_weight,
            memory_cost_weight=self.memory_cost_weight,
        )

    def cp_sat_config(self, *, max_time_s: float, random_seed: int) -> CpSatPlannerConfig:
        return CpSatPlannerConfig(
            memory_reserve_ratio=self.memory_reserve_ratio,
            use_dynamic_transition_model=self.use_dynamic_transition_model,
            eo_stabilization_time_s=self.eo_stabilization_time_s,
            sar_stabilization_time_s=self.sar_stabilization_time_s,
            sar_side_switch_penalty_s=self.sar_side_switch_penalty_s,
            sar_mode_switch_penalty_s=self.sar_mode_switch_penalty_s,
            sar_slew_rate_deg_s=self.sar_slew_rate_deg_s,
            sar_pass_gap_s=self.sar_pass_gap_s,
            sar_max_acquisitions_per_pass=self.sar_max_acquisitions_per_pass,
            priority_weight=self.priority_weight,
            quality_weight=self.quality_weight,
            coverage_weight=self.coverage_weight,
            mandatory_bonus=self.mandatory_bonus,
            dual_optional_second_bonus=self.dual_optional_second_bonus,
            force_mandatory_requests=self.force_mandatory_requests,
            max_time_s=max_time_s,
            num_search_workers=self.num_search_workers,
            random_seed=random_seed,
            log_search_progress=self.log_search_progress,
        )


__all__ = ["CpSatPlannerConfig", "GreedyPlannerConfig", "HybridPlannerConfig"]
