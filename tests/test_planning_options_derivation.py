from dataclasses import fields

import pytest

from app.models.enums import PlanningAlgorithm
from app.services.contracts import PlanningOptions


_CHANGED_FIELDS = {
    "algorithm",
    "memory_reserve_ratio",
    "cp_sat_time_limit_s",
    "cp_sat_num_search_workers",
    "cp_sat_force_mandatory_requests",
}


def test_derive_for_replanning_changes_only_explicit_fields() -> None:
    original = PlanningOptions(
        algorithm=PlanningAlgorithm.GREEDY,
        memory_reserve_ratio=0.15,
        enable_downlink_planning=True,
        require_full_downlink=True,
        allow_simultaneous_imaging_downlink=True,
        downlink_capacity_reserve_ratio=0.23,
        use_dynamic_transition_model=True,
        eo_stabilization_time_s=4.5,
        sar_stabilization_time_s=12.0,
        sar_side_switch_penalty_s=71.0,
        sar_mode_switch_penalty_s=19.0,
        sar_slew_rate_deg_s=1.7,
        sar_pass_gap_s=840.0,
        sar_max_acquisitions_per_pass=4,
        priority_weight=13.0,
        quality_weight=4.0,
        coverage_weight=3.0,
        mandatory_bonus=120.0,
        dual_optional_second_bonus=8.0,
        use_opportunity_cost_heuristic=True,
        scarcity_bonus_weight=2.7,
        conflict_cost_weight=0.31,
        duration_cost_weight=0.022,
        memory_cost_weight=0.00021,
        cp_sat_time_limit_s=10.0,
        cp_sat_num_search_workers=1,
        cp_sat_random_seed=98765,
        cp_sat_force_mandatory_requests=True,
        cp_sat_log_search_progress=True,
        hybrid_neighborhood_request_limit=17,
        hybrid_max_neighborhoods=9,
        hybrid_minimum_improvement=0.001,
    )

    derived = original.derive_for_replanning(
        algorithm=PlanningAlgorithm.HYBRID,
        memory_reserve_ratio=0.30,
        cp_sat_time_limit_s=30.0,
        cp_sat_num_search_workers=6,
        cp_sat_force_mandatory_requests=False,
    )

    assert derived is not original
    assert derived.algorithm is PlanningAlgorithm.HYBRID
    assert derived.memory_reserve_ratio == pytest.approx(0.30)
    assert derived.cp_sat_time_limit_s == pytest.approx(30.0)
    assert derived.cp_sat_num_search_workers == 6
    assert not derived.cp_sat_force_mandatory_requests

    for field in fields(PlanningOptions):
        if field.name in _CHANGED_FIELDS:
            continue
        assert getattr(derived, field.name) == getattr(original, field.name), (
            f"Pole {field.name} nie powinno zmienić się podczas przeplanowania"
        )


def test_derive_for_replanning_revalidates_overrides() -> None:
    original = PlanningOptions()

    with pytest.raises(ValueError, match="memory_reserve_ratio"):
        original.derive_for_replanning(
            algorithm=PlanningAlgorithm.GREEDY,
            memory_reserve_ratio=1.5,
            cp_sat_time_limit_s=10.0,
            cp_sat_num_search_workers=1,
            cp_sat_force_mandatory_requests=True,
        )
